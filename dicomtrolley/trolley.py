"""Combines WADO, RAD69, MINT and DICOM-QR to make make getting DICOM studies easy.

Notes
-----
Design choices:

WADO, RAD69, MINT and DICOM-QR modules should be stand-alone. They are not allowed to
use each other's classes. Trolley has knowledge of all and converts between them if
needed
"""
import tempfile
from typing import List, Optional, Sequence, Tuple, Union

from dicomtrolley.core import (
    DICOMObject,
    Downloader,
    Instance,
    InstanceReference,
    Searcher,
    Study,
)
from dicomtrolley.parsing import DICOMObjectTree
from dicomtrolley.storage import DICOMDiskStorage, StorageDir
from dicomtrolley.types import DICOMDownloadable


class Trolley:
    """Combines a search and download method to get DICOM studies easily"""

    def __init__(
        self,
        downloader: Downloader,
        searcher: Searcher,
        query_missing=True,
        storage: Optional[DICOMDiskStorage] = None,
    ):
        """

        Parameters
        ----------
        downloader: Downloader
            The module to use for downloads
        searcher: Searcher
            The module to use for queries
        query_missing: bool, optional
            if True, Trolley.download() will query for missing DICOM instances. For
            example when passing a Study obtained from a study-level query, which does
            not contain any information on instances
            if False, missing instances will not be downloaded
        storage: DICOMDiskStorage instance, optional
            All downloads are saved to disk by calling this objects' save() method.
            Defaults to basic StorageDir (saves as /studyid/seriesid/instanceid)
        """
        self.downloader = downloader
        self.searcher = searcher
        self._searcher_cache = DICOMObjectTree([])
        self.query_missing = query_missing
        if storage:
            self.storage = storage
        else:
            self.storage = StorageDir(tempfile.gettempdir())

    def find_studies(self, query) -> List[Study]:
        """Find study information

        Parameters
        ----------
        query:
            Search for these criteria

        Returns
        -------
        List[Study]
        """
        return list(self.searcher.find_studies(query))

    def find_study(self, query) -> Study:
        """Like find study, but returns exactly one result or raises exception.

        For queries using study identifiers such as StudyInstanceUID,AccessionNumber

        Parameters
        ----------
        query
            Search for these criteria. Query documentation for more info.

        Returns
        -------
        Study
        """
        return self.searcher.find_study(query)

    def download(
        self,
        objects: Union[DICOMDownloadable, Sequence[DICOMDownloadable]],
        output_dir,
        use_async=False,
        max_workers=None,
    ):
        """Download the given objects to output dir."""
        if not isinstance(objects, Sequence):
            objects = [objects]  # if just a single item to download is passed
        if use_async:
            datasets = self.fetch_all_datasets_async(
                objects=objects, max_workers=max_workers
            )
        else:
            datasets = self.fetch_all_datasets(objects=objects)

        for dataset in datasets:
            self.storage.save(dataset=dataset, path=output_dir)

    def fetch_all_datasets(self, objects: Sequence[DICOMDownloadable]):
        """Get full DICOM dataset for all instances contained in objects.

        Returns
        -------
        Iterator[Dataset]
            The downloaded dataset and the context that was used to download it
        """

        yield from self.downloader.datasets(
            self.objects_to_references(objects)
        )

    def objects_to_references(
        self, objects: Sequence[DICOMDownloadable]
    ) -> Sequence[InstanceReference]:
        """Find all instances contained in the given objects. Query for missing"""
        references, dicom_objects = self.split_references(objects)
        if self.query_missing:
            dicom_objects = self.ensure_instances(dicom_objects)
        return references + self.extract_references(dicom_objects)

    @staticmethod
    def split_references(
        objects,
    ) -> Tuple[List[InstanceReference], List[DICOMObject]]:
        references, dicom_objects = [], []
        for item in objects:
            references.append(item) if isinstance(
                item, InstanceReference
            ) else dicom_objects.append(item)
        return references, dicom_objects

    @staticmethod
    def extract_references(
        objects: Sequence[DICOMDownloadable],
    ) -> List[InstanceReference]:
        """Get all individual instances from input.

        A pre-processing step for getting datasets.

        Parameters
        ----------
        objects: list[DICOMDownloadable]
            Any combination of Study, Series and Instance objects

        Returns
        -------
        List[InstanceReference]
            A reference to each instance (slice)
        """
        instances: List[InstanceReference]
        instances = []
        for item in objects:
            if isinstance(item, InstanceReference):
                instances.append(item)
            else:
                instances = instances + [
                    to_instance_reference(x) for x in item.all_instances()
                ]
        return instances

    def ensure_instances(self, objects: Sequence[DICOMObject]):
        """Ensure that all objects contain instances. Perform additional image-level
        queries with searcher if needed.

        Note
        ----
        This method fires additional search queries and might take a long time to
        return depending on the number of objects and missing instances
        """

        def has_instances(item_in):
            return bool(item_in.all_instances())

        # all information on studies, series and instances we have
        self._searcher_cache = DICOMObjectTree(objects)
        cache = self._searcher_cache

        ensured = []
        for item in objects:
            if has_instances(item):
                ensured.append(item)  # No work needed
            else:
                retrieved = cache.retrieve(
                    item.reference()
                )  # have we cached before?
                if has_instances(retrieved):  # yes we have. Add that
                    ensured.append(retrieved)
                else:  # No instances, we'll have to query for them
                    study = self.searcher.find_full_study_by_id(
                        item.root().uid
                    )
                    cache.add_study(study)
                    ensured.append(cache.retrieve(item.reference()))

        self._searcher_cache = DICOMObjectTree([])
        return ensured

    def fetch_all_datasets_async(self, objects, max_workers=None):
        """Get DICOM dataset for each instance given objects using multiple threads.

        Parameters
        ----------
        objects: Sequence[DICOMDownloadable]
            get dataset for each instance contained in these objects
        max_workers: int, optional
            Max number of ThreadPoolExecutor workers to use. Defaults to
            ThreadPoolExecutor default

        Raises
        ------
        DICOMTrolleyError
            If getting or parsing of any instance fails

        Returns
        -------
        Iterator[Dataset, None, None]
            The downloaded dataset and the context that was used to download it
        """

        yield from self.downloader.datasets_async(
            instances=self.objects_to_references(objects),
            max_workers=max_workers,
        )


def to_instance_reference(
    item: Union[Instance, InstanceReference]
) -> InstanceReference:
    """Simplify a more extensive instance to an InstanceReference.

    needed for calls to WADO functions.

    Opted to check for type here as I don't want put this functionality in core.
    """
    if isinstance(item, InstanceReference):
        return item
    else:
        return InstanceReference(
            study_instance_uid=item.parent.parent.uid,
            series_instance_uid=item.parent.uid,
            sop_instance_uid=item.uid,
        )
