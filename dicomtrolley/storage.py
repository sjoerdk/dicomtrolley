"""Classes and functions for writing downloaded results to disk"""

from pathlib import Path
from typing import Optional

from dicomtrolley.logging import get_module_logger

logger = get_module_logger("storage")


class DICOMDiskStorage:
    """A place on disk that you can write datasets to."""

    def save(self, dataset, path: Optional[str] = None) -> None:
        """Write dataset. Creates sub-folders if needed

        Parameters
        ----------
        dataset: Dataset
            Save this pydicom dataset
        path: str, optional
            Save to this path. Defaults to saving to default path

        """
        raise NotImplementedError()


class StorageDir(DICOMDiskStorage):
    """Saves in folder structure studyid/seriesid/instanceid"""

    def __init__(self, path: str):
        self.path = path

    def __str__(self):
        return f"StorageDir at {self.path}"

    def save(self, dataset, path: Optional[str] = None):
        """Write dataset. Creates sub-folders if needed."""
        if not path:
            path = self.path

        slice_path = Path(path) / self.generate_path(dataset)
        slice_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f'Saving to "{slice_path}"')
        dataset.save_as(slice_path)

    def generate_path(self, dataset):
        """A path studyid/seriesid/instanceid to save a slice to."""

        stu_uid = self.get_value(dataset, "StudyInstanceUID")
        ser_uid = self.get_value(dataset, "SeriesInstanceUID")
        sop_uid = self.get_value(dataset, "SOPInstanceUID")
        return Path(stu_uid) / ser_uid / sop_uid

    @staticmethod
    def get_value(dataset, tag_name):
        """Extract value for use in path. If not found return 'unknown'"""
        default = "unknown"
        return str(dataset.get(tag_name, default)).replace(".", "_")


class FlatStorageDir(StorageDir):
    """Stores without sub-folders, only instanceid as filename"""

    def generate_path(self, dataset):
        return Path(self.get_value(dataset, "SOPInstanceUID"))
