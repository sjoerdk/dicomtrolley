"""Combines WADO and MINT to make make getting DICOM studies easy"""

# Create session

from itertools import chain
from pathlib import Path
from typing import List

from dicomtrolley.mint import (
    Mint,
    MintInstance,
    MintObject,
)
from dicomtrolley.query import Query, QueryLevels
from dicomtrolley.wado import Wado


class Trolley:
    """Combines WADO and MINT to make make getting DICOM studies easy

    Offers three different types of functions:
    * Find - Search for things on server, but do not download yet
    * Download - Quick methods that download some data to disk
    * Get - Return pydicom datasets directly without writing to disk
    """

    def __init__(self, wado: Wado, mint: Mint):
        self.wado = wado
        self.mint = mint

    def find_studies(self, query):
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
        """Get full DICOM dataset for each instance in study. Calls mint and wado

        Parameters
        ----------
        mint_objects: List[MintObject]


        Returns
        -------
        Generator[Dataset, None, None]
            The downloaded dataset and the context that was used to download it
        """

        for instance in self.extract_instances(mint_objects):
            yield self.get_dataset(instance)

    @staticmethod
    def extract_instances(mint_objects: List[MintObject]):
        """Get all individual instances from input.

        mint_objects: List[MintObject]
            Any combination of MintStudy, MintSeries and MintInstance instances

        A pre-processing step for getting datasets
        """
        return list(chain(*(x.all_instances() for x in mint_objects)))

    def get_dataset(self, instance: MintInstance):
        """Get all DICOM data for this instance from server

        Returns
        -------
        Dataset
        """

        return self.wado.get_dataset(
            study_instance_uid=instance.parent.parent.uid,
            series_instance_uid=instance.uid,
            sop_instance_iud=instance.uid,
        )


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
        return dataset.get(tag_name, default).replace(".", "_")
