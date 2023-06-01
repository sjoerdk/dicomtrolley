"""Combines WADO, RAD69, MINT and DICOM-QR to make make getting DICOM studies easy.

Notes
-----
Design choices:

WADO, RAD69, MINT and DICOM-QR modules should be stand-alone. They are not allowed to
use each other's classes. Trolley has knowledge of all and converts between them if
needed
"""
import itertools
import logging
import tempfile
from typing import List, Optional, Sequence, Union

from dicomtrolley.core import (
    DICOMDownloadable,
    DICOMObject,
    DICOMObjectReference,
    Downloader,
    Instance,
    InstanceReference,
    NonInstanceParameterError,
    Searcher,
    Study,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMObjectNotFound, DICOMObjectTree
from dicomtrolley.storage import DICOMDiskStorage, StorageDir


logger = logging.getLogger("trolley")


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
        self._searcher_cache = CachedSearcher(searcher)
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
        logger.info(f"Downloading {len(objects)} object(s) to '{output_dir}'")
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
        try:
            yield from self.downloader.datasets(objects)
        except NonInstanceParameterError:
            # downloader wants only instance input. Do extra work.
            yield from self.downloader.datasets(
                self.convert_to_instances(objects)
            )

    def convert_to_instances(
        self, objects_in: Sequence[DICOMDownloadable]
    ) -> List[InstanceReference]:
        """Find all instances contained in objects, running additional image-level
        queries with searcher if needed.

        Holds DICOMObjects in an internal cache, avoiding queries as much as
        possible.

        Note
        ----
        This method can fire additional search queries and might take a long time to
        return depending on the number of objects and missing instances
        """
        return list(
            itertools.chain.from_iterable(
                self._searcher_cache.retrieve_instance_references(x)
                for x in objects_in
            )
        )

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
        try:
            yield from self.downloader.datasets_async(
                instances=objects,
                max_workers=max_workers,
            )
        except NonInstanceParameterError:
            yield from self.downloader.datasets_async(
                instances=self.convert_to_instances(objects),
                max_workers=max_workers,
            )


class NoInstancesFoundError(DICOMTrolleyError):
    pass


class CachedSearcher:
    def __init__(
        self, searcher: Searcher, cache: Optional[DICOMObjectTree] = None
    ):
        """A DICOMObject tree (study/series/instances) that will launch
        queries to expand itself if needed. Tries to query as little as
        possible.

        Created this to efficiently get all instances for download based on a
        variable collection of DICOMDownloadable objects.

        Parameters
        ----------
        searcher: Searcher
            Use this searcher to search for missing elements in cache
        cache: DICOMObjectTree, Optional
            Use this tree as cache. Defaults to an empty tree

        """
        self.searcher = searcher
        if not cache:
            cache = DICOMObjectTree([])
        self.cache = cache

    def retrieve_instance_references(
        self, downloadable: DICOMDownloadable
    ) -> List[InstanceReference]:
        """Get references for all instances contained in downloadable, performing
        additional queries if needed
        """
        # DICOMObject might already contain all required info
        if isinstance(downloadable, DICOMObject):
            instances = downloadable.all_instances()
            if instances:
                return [x.reference() for x in instances]

        # No instances in downloadable. Do we have instances in cache for this?
        reference = downloadable.reference()
        try:
            return [
                x.reference() for x in self.get_instances_from_cache(reference)
            ]
        except NoInstancesFoundError:  # not found, we'll have to query
            logger.debug(f"No instances cached for {reference}. Querying")
            self.query_for_study(reference)
            return [
                x.reference() for x in self.get_instances_from_cache(reference)
            ]

    def get_instances_from_cache(
        self, reference: DICOMObjectReference
    ) -> List[Instance]:
        """Retrieve all instances for this reference. Raise exception if not found

        Raises
        ------
        NoInstancesFoundError
            If no instances are found in cache
        """
        try:
            return self.cache.retrieve(reference).all_instances()
        except DICOMObjectNotFound as e:
            raise NoInstancesFoundError(
                f"No instances found for {reference}"
            ) from e

    def query_for_study(self, reference: DICOMObjectReference):
        study = self.searcher.find_full_study_by_id(reference.study_uid)
        self.cache.add_study(study)


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
            study_uid=item.parent.parent.uid,
            series_uid=item.parent.uid,
            instance_uid=item.uid,
        )
