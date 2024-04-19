"""Combines Searcher and Downloader to make getting DICOM studies easy.

Notes
-----
Design choices:

Searcher and Downloader classes should be stand-alone. They are not allowed to
communicate directly. Trolley has knowledge of both and is in control.
"""

import tempfile
from typing import List, Optional, Sequence, Union

from dicomtrolley.core import (
    DICOMDownloadable,
    DICOMObjectLevels,
    DICOMObjectReference,
    Downloader,
    NonInstanceParameterError,
    NonSeriesParameterError,
    QueryLevels,
    Searcher,
    Study,
)
from dicomtrolley.exceptions import NoReferencesFoundError
from dicomtrolley.logs import get_module_logger
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
        storage: Optional[DICOMDiskStorage] = None,
    ):
        """

        Parameters
        ----------
        downloader: Downloader
            The module to use for downloads
        searcher: Searcher
            The module to use for queries
        storage: DICOMDiskStorage instance, optional
            All downloads are saved to disk by calling this objects' save() method.
            Defaults to basic StorageDir (saves as /studyid/seriesid/instanceid)
        """
        self.downloader = downloader
        self.searcher = searcher

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

        for dataset in self.fetch_all_datasets(objects=objects):
            self.storage.save(dataset=dataset, path=output_dir)

    def fetch_all_datasets(self, objects: Sequence[DICOMDownloadable]):
        """Get full DICOM dataset for all instances contained in objects.

        Some downloaders require explicit series- or instance level information to be
        able to download. Additional queries might be fired to obtain this
        information.

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets belonging to input objects
        """
        try:
            yield from self.downloader.datasets(objects)
        except NonSeriesParameterError:
            # downloader wants at least series level information. Do extra work.
            series_lvl_refs = self.obtain_references(
                objects=objects, max_level=DICOMObjectLevels.SERIES
            )
            yield from self.downloader.datasets(series_lvl_refs)
        except NonInstanceParameterError:
            # downloader wants only instance input. Do extra work.
            instance_refs = self.obtain_references(
                objects=objects, max_level=DICOMObjectLevels.INSTANCE
            )
            yield from self.downloader.datasets(instance_refs)

    def obtain_references(
        self,
        objects: Sequence[DICOMDownloadable],
        max_level: DICOMObjectLevels,
    ) -> List[DICOMObjectReference]:
        """Get download references for all downloadable objects, at max_level or
        lower. query if needed.

        For example, if level is QueryLevels.Instance and a Study object is given,
        try to extract instances from this study. If those instances or not in the
        study, ask searcher to obtain them

        Returns
        -------
            List[DICOMObjectReference] of the level given or deeper
        """
        references: List[DICOMObjectReference] = []
        for downloadable in objects:
            try:
                references += downloadable.contained_references(
                    max_level=max_level
                )
            except NoReferencesFoundError:
                # Not enough info in object itself. We need searcher
                logger.debug(
                    f"Not enough info to extract '{str(max_level)}-level' "
                    f"references from {downloadable}. Asking searcher."
                )
                study = self.searcher.find_study_by_id(
                    study_uid=downloadable.reference().study_uid,
                    query_level=QueryLevels.from_object_level(max_level),
                )
                references += study.contained_references(max_level=max_level)
        return references
