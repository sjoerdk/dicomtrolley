"""Classes and functions for writing downloaded results to disk"""

from pathlib import Path
from typing import Optional

from pydicom.dataset import Dataset

from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.logs import get_module_logger

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
        """Write dataset. Creates subfolders if needed.

        Raises
        ------
        StorageError
            If writing to disk does not work for some reason.
        """
        if not path:
            path = self.path

        slice_path = Path(path) / self.generate_path(dataset)
        slice_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f'Saving to "{slice_path}"')
        try:
            dataset.save_as(slice_path)
        except ValueError as e:
            raise StorageError() from e

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


def remove_illegal_elements_for_writing(dataset):
    """Remove elements for which the contents do not match the Value Representation

    These exist in certain private tags obtained via /metadata. It is unclear
    whether this is an issue in the WADO-RS server implementation or pydicom.

    Removing them is a workaround until the underlying issue can be resolved.

    This function is inside WadoRSMetadata because this is the only downloader
    for which the output has this problem.

    Notes
    -----
    Modifies input dataset in-place! Even if you do not assign this function's
    output to a variable, the input Dataset will still be modified.
    """

    def is_illegal(element_in):
        return element_in.VR == "UN" and type(element_in.value) not in (
            str,
            bytes,
        )

    illegal_elements = [x for x in dataset if is_illegal(x)]
    for element in illegal_elements:
        del dataset[element.tag]
        logger.debug(
            f"Removing illegal element {element}. US (Unknown bytes) VR "
            f"but content is not byte-like"
        )
    return dataset


def make_writable(ds):
    """Make alterations to a dataset to make it writable"""
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.TransferSyntaxUID = (
        "1.2.840.10008.1.2.1"  # Explicit VR Little Endian
    )
    ds.file_meta = file_meta
    ds.implicit_vr = False

    ds = remove_illegal_elements_for_writing(ds)

    return ds


class StorageError(DICOMTrolleyError):
    pass
