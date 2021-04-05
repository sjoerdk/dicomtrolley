"""Combines WADO and MINT to make make getting DICOM studies easy

Notes
-----
Design choices:

WADO and MINT modules should remain un-entangled so are not allowed to use
each other's classes. Core has knowledge of both an can convert classes between the
two if needed

"""

from pathlib import Path
from typing import List, Sequence, Union

from dicomtrolley.mint import (
    Mint,
    MintInstance,
    MintObject,
    MintStudy,
)
from dicomtrolley.query import Query, QueryLevels
from dicomtrolley.wado import InstanceReference, Wado


class Trolley:
    """Combines WADO and MINT to make make getting DICOM studies easy"""

    def __init__(self, wado: Wado, mint: Mint):
        self.wado = wado
        self.mint = mint

    def find_studies(self, query) -> List[MintStudy]:
        """Find studies but do not download yet

        Parameters
        ----------
        query: Query
            Search for these criteria. See dicomtrolley.mint.Query for options

        Returns
        -------
        List[MintStudy]
        """
        return self.mint.find_studies(query)

    def download_study(self, study_instance_uid, output_dir):
        """Download single study to output dir. Calls both mint and wado

        Parameters
        ----------
        study_instance_uid: str
        output_dir: path

        """
        study = self.mint.find_study(
            Query(
                studyInstanceUID=study_instance_uid,
                queryLevel=QueryLevels.INSTANCE,
            )
        )
        storage = DICOMStorageDir(output_dir)
        for dataset in self.fetch_all_datasets(mint_objects=[study]):
            storage.save(dataset)

    def fetch_all_datasets(self, mint_objects: List[MintObject]):
        """Get full DICOM dataset for each instance in study

        Parameters
        ----------
        mint_objects: List[MintObject]


        Returns
        -------
        Generator[Dataset, None, None]
            The downloaded dataset and the context that was used to download it
        """
        for ds in self.wado.datasets(self.extract_instances(mint_objects)):
            yield ds

    @staticmethod
    def extract_instances(
        objects: Sequence[Union[MintObject, InstanceReference]]
    ):
        """Get all individual instances from input

        A pre-processing step for getting datasets

        Parameters
        ----------
        objects: Sequence[MintObject]
            Any combination of MintStudy, MintSeries and MintInstance instances

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
                    to_reference(x) for x in item.all_instances()
                ]
        return instances

    def fetch_all_datasets_async(self, mint_objects, max_workers=None):
        """Get full DICOM dataset for each instance in study using multiple threads

        Parameters
        ----------
        mint_objects: List[MintObject]
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

        for ds in self.wado.datasets_async(
            instances=self.extract_instances(mint_objects),
            max_workers=max_workers,
        ):
            yield ds


class DICOMStorageDir:
    """A directory that you can write datasets to"""

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return f"DICOMStorageDir at {self.path}"

    def save(self, dataset):
        """Write dataset. Creates sub-folders if needed"""

        slice_path = Path(self.path) / self.generate_path(dataset)
        slice_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(slice_path)

    def generate_path(self, dataset):
        """A path studyid/seriesid/instanceid to save a slice to"""

        stu_uid = self.get_value(dataset, "StudyInstanceUID")
        ser_uid = self.get_value(dataset, "SeriesInstanceUID")
        sop_uid = self.get_value(dataset, "SOPInstanceUID")
        return Path(self.path) / stu_uid / ser_uid / sop_uid

    @staticmethod
    def get_value(dataset, tag_name):
        """Extract value for use in path. If not found return default"""
        default = "unknown"
        return str(dataset.get(tag_name, default)).replace(".", "_")


def to_reference(instance: MintInstance) -> InstanceReference:
    """Simplify a more extensive MINT instance to an InstanceReference
    needed for calls to WADO functions
    """
    return InstanceReference(
        study_instance_uid=instance.parent.parent.uid,
        series_instance_uid=instance.parent.uid,
        sop_instance_iud=instance.uid,
    )
