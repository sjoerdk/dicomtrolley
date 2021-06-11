"""Combines WADO, MINT and DICOM-QR to make make getting DICOM studies easy.

Notes
-----
Design choices:

WADO, MINT and DICOM-QR modules should be stand-alone. They are not allowed to use
each other's classes. Core has knowledge of all and converts between them if needed

"""
from pathlib import Path
from typing import List, Sequence, Union

from dicomtrolley.core import DICOMObject, Instance, Searcher, Study
from dicomtrolley.wado import InstanceReference, Wado


class Trolley:
    """Combines WADO and MINT or DICOM-QR to make make getting DICOM studies easy."""

    def __init__(self, wado: Wado, searcher: Searcher):
        self.wado = wado
        self.searcher = searcher

    def find_studies(self, query) -> List[Study]:
        """Find study information using MINT.

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
        objects: Union[DICOMObject, Sequence[DICOMObject]],
        output_dir,
        use_async=False,
        max_workers=None,
    ):
        """Download the given objects to output dir."""
        if not isinstance(objects, Sequence):
            objects = [objects]
        storage = DICOMStorageDir(output_dir)
        if use_async:
            datasets = self.fetch_all_datasets_async(
                objects=objects, max_workers=max_workers
            )
        else:
            datasets = self.fetch_all_datasets(objects=objects)

        for dataset in datasets:
            storage.save(dataset)

    def fetch_all_datasets(self, objects: Sequence[DICOMObject]):
        """Get full DICOM dataset for each instance in study.

        Returns
        -------
        Iterator[Dataset]
            The downloaded dataset and the context that was used to download it
        """
        yield from self.wado.datasets(self.extract_instances(objects))

    @staticmethod
    def extract_instances(
        objects: Sequence[Union[DICOMObject, InstanceReference]]
    ):
        """Get all individual instances from input.

        A pre-processing step for getting datasets.

        Parameters
        ----------
        objects: list[Union[DICOMObject, InstanceReference]]
            Any combination of Study, Series and Instance objects

        Returns
        -------
        List[InstanceReference]
            A reference to each instance (slice)
        """
        instances = []
        for item in objects:
            if isinstance(item, InstanceReference):
                instances.append(item)
            else:
                instances = instances + [
                    to_wado_reference(x) for x in item.all_instances()
                ]
        return instances

    def fetch_all_datasets_async(self, objects, max_workers=None):
        """Get DICOM dataset for each instance given objects using multiple threads.

        Parameters
        ----------
        objects: List[DICOMObject]
            get dataset for each instance contained in these objects
        max_workers: int, optional
            Max number of ThreadPoolExecutor workers to use. Defaults to
            ThreadPoolExecutor default

        Raises
        ------
        DICOMTrolleyException
            If getting or parsing of any instance fails

        Returns
        -------
        Iterator[Dataset, None, None]
            The downloaded dataset and the context that was used to download it
        """

        yield from self.wado.datasets_async(
            instances=self.extract_instances(objects),
            max_workers=max_workers,
        )


def to_wado_reference(instance: Instance) -> InstanceReference:
    """Simplify a more extensive MINT instance to an InstanceReference.

    needed for calls to WADO functions
    """
    return InstanceReference(
        study_instance_uid=instance.parent.parent.uid,
        series_instance_uid=instance.parent.uid,
        sop_instance_iud=instance.uid,
    )


class DICOMStorageDir:
    """A directory that you can write datasets to."""

    def __init__(self, path: str):
        self.path = path

    def __str__(self):
        return f"DICOMStorageDir at {self.path}"

    def save(self, dataset):
        """Write dataset. Creates sub-folders if needed."""

        slice_path = Path(self.path) / self.generate_path(dataset)
        slice_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(slice_path)

    def generate_path(self, dataset):
        """A path studyid/seriesid/instanceid to save a slice to."""

        stu_uid = self.get_value(dataset, "StudyInstanceUID")
        ser_uid = self.get_value(dataset, "SeriesInstanceUID")
        sop_uid = self.get_value(dataset, "SOPInstanceUID")
        return Path(self.path) / stu_uid / ser_uid / sop_uid

    @staticmethod
    def get_value(dataset, tag_name):
        """Extract value for use in path. If not found return default."""
        default = "unknown"
        return str(dataset.get(tag_name, default)).replace(".", "_")
