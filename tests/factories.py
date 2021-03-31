from io import BytesIO

from pydicom.dataset import Dataset
from pydicom.tag import Tag


def quick_dataset(*_, **kwargs) -> Dataset:
    """Creates a pydicom dataset with keyword args as tagname - value pairs

    Examples
    --------
    >>> ds = quick_dataset(PatientName='Jane',StudyDescription='Test')
    >>> ds.PatientName
    'Jane'
    >>> ds.StudyDescription
    'Test'

    Raises
    ------
    ValueError
        If any input key is not a valid DICOM keyword

    """
    dataset = Dataset()
    for tag_name, value in kwargs.items():
        Tag(tag_name)  # assert valid dicom keyword. pydicom will not do this.
        dataset.__setattr__(tag_name, value)
    return dataset


def create_dicom_bytestream(dataset):
    """Bytes constituting a valid dicom dataset"""
    content = BytesIO()
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.save_as(content, write_like_original=False)
    content.seek(0)
    return content.read()
