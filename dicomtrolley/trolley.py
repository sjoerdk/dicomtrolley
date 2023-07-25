"""Combines WADO, RAD69, MINT and DICOM-QR to make getting DICOM studies easy.

Notes
-----
Design choices:

WADO, RAD69, MINT and DICOM-QR modules should be stand-alone. They are not allowed to
use each other's classes. Trolley has knowledge of all and converts between them if
needed
"""
import itertools
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
    NonSeriesParameterError,
    Searcher,
    Series,
    SeriesReference,
    Study,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.logs import get_module_logger
from dicomtrolley.parsing import DICOMObjectNotFound, DICOMObjectTree
from dicomtrolley.storage import DICOMDiskStorage, StorageDir


logger = get_module_logger("trolley")


class Trolley:
    """Combines a search and download method to get DICOM studies easily

    Features:
    * Searching for DICOM using a Query instance is backend-agnostic.
    * If a download method requires additional information such as all instance UIDs,
      trolley can query for these in the background.
    * Saves to disk in reasonable (uid based) folder structure.
    """

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
            if False, missing instances will raise MissingObjectInformationError
        storage: DICOMDiskStorage instance, optional
            All downloads are saved to disk by calling this objects' save() method.
            Defaults to basic StorageDir (saves as /studyid/seriesid/instanceid)
        """
        self.downloader = downloader
        self.searcher = searcher
        self._searcher_cache = CachedSearcher(
            searcher, query_missing=query_missing
        )
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
        except NonSeriesParameterError:
            # downloader wants at least series level information. Do extra work.
            series_lvl_objects = self.ensure_to_series_level(objects)
            yield from self.downloader.datasets(series_lvl_objects)
        except NonInstanceParameterError:
            # downloader wants only instance input. Do extra work.
            instances = self.convert_to_instances(objects)
            yield from self.downloader.datasets(instances)

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

    def ensure_to_series_level(
        self, objects_in: Sequence[DICOMDownloadable]
    ) -> Sequence[Union[InstanceReference, SeriesReference]]:
        """Make sure all input is converted to instance or series

        ----
        This method can fire additional search queries and might take a long time to
        return depending on the number of objects and missing instances or series
        """
        return list(
            itertools.chain.from_iterable(
                self._searcher_cache.ensure_series_level_references(x)
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


class CachedSearcher:
    def __init__(
        self,
        searcher: Searcher,
        cache: Optional[DICOMObjectTree] = None,
        query_missing: Optional[bool] = True,
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
        query_missing: Bool, optional
            Launch queries to find missing information. If False, will raise
            MissingObjectInformationError. Defaults to True
        """
        self.searcher = searcher
        if not cache:
            cache = DICOMObjectTree([])
        self.cache = cache
        self.query_missing = query_missing

    def retrieve_instance_references(
        self, downloadable: DICOMDownloadable
    ) -> List[InstanceReference]:
        """Get references for all instances contained in downloadable, performing
        additional queries if needed

        Raises
        ------
        MissingObjectInformationError
            If Trolley.query_missing is False and queries would be required to
            retrieve all instances.

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
        except MissingObjectInformationError as e:  # not found, we'll have to query
            if not self.query_missing:
                raise MissingObjectInformationError(
                    f"No instances cached for {reference} "
                    f"and query_missing was False"
                ) from e

            logger.debug(f"No instances cached for {reference}. Querying")
            self.query_study_instances(reference)
            return [
                x.reference() for x in self.get_instances_from_cache(reference)
            ]

    def ensure_series_level_references(
        self, downloadable: DICOMDownloadable
    ) -> List[Union[InstanceReference, SeriesReference]]:
        """Extract references of at least series level. Query if not found

        Raises
        ------
        MissingObjectInformationError
            If Trolley.query_missing is False and queries would be required to
            retrieve Series.


        TODO: Strong whiffs of code smell here. This method should not be this
        long. Some pointers for refactoring: Get rid of explicit type checking.
        possibly move logic to DICOMDownloadable classes. Why does this method
        take a DICOMDownloadable and not just a reference? It seems conversion logic
        is shoehorned into CachedSearcher and Trolley classes. CachedSearcher should
        govern a cache of DICOM information, Trolley should handle high level
        requests. Neither are quite right for conversion. Possibly create separate
        class for this.
        """
        # Instance and Series should just be left as is
        if isinstance(
            downloadable,
            (Instance, Series, InstanceReference, SeriesReference),
        ):
            return [downloadable.reference()]
        # If its a study, it might need work

        elif isinstance(downloadable, Study):
            series: Sequence[
                Union[Instance, Series]
            ] = downloadable.all_series()
            if series:  # there were series inside Study already
                return [x.reference() for x in series]

        # no studies. Maybe they are in cache?
        reference = downloadable.reference()
        try:
            series = self.get_series_level_from_cache(reference)
            if series:
                return [x.reference() for x in series]
            else:
                raise MissingObjectInformationError()  # not expected. Being careful.

        except MissingObjectInformationError as e:  # not found, we'll have to query
            if not self.query_missing:
                raise MissingObjectInformationError(
                    f"No series cached for {reference} "
                    f"and query_missing was False"
                ) from e

            logger.debug(f"No series cached for {reference}. Querying")
            self.query_study_series(reference)
            return [
                x.reference()
                for x in self.get_series_level_from_cache(reference)
            ]

    def get_instances_from_cache(
        self, reference: DICOMObjectReference
    ) -> List[Instance]:
        """Retrieve all instances for this reference. Raise exception if not found

        Raises
        ------
        MissingObjectInformationError
            If no instances are found in cache
        """
        try:
            instances = self.cache.retrieve(reference).all_instances()
            if instances:
                return instances
            else:
                # reference was in cache, but there are no instances
                raise MissingObjectInformationError(
                    f"No instances found for {reference}"
                )
        except DICOMObjectNotFound as e:
            # reference was not in cache
            raise MissingObjectInformationError(
                f"No instances found for {reference}"
            ) from e

    def get_series_level_from_cache(
        self, reference: DICOMObjectReference
    ) -> Sequence[Union[Instance, Series]]:
        """Retrieve series this reference, or instance if required.
        Raise exception if not found

        Raises
        ------
        MissingObjectInformationError
            If no series or instance can be found for this reference
        """
        try:
            series: Sequence[Union[Instance, Series]] = self.cache.retrieve(
                reference
            ).all_series()
            if series:
                return series
            else:
                # reference was in cache, but there are no instances
                raise MissingObjectInformationError(
                    f"No series found for {reference}"
                )
        except DICOMObjectNotFound as e:
            # reference was not in cache
            raise MissingObjectInformationError(
                f"No series found for {reference}"
            ) from e

    def query_study_instances(self, reference: DICOMObjectReference):
        study = self.searcher.find_study_at_instance_level(reference.study_uid)
        self.cache.add_study(study)

    def query_study_series(self, reference: DICOMObjectReference):
        study = self.searcher.find_study_at_series_level(reference.study_uid)
        self.cache.add_study(study)


class MissingObjectInformationError(DICOMTrolleyError):
    """An operation on a DICOM object cannot complete because the required information
    is not available. For example, trying to extract all instances from a Study that
    was retrieved without instance information
    """

    pass
