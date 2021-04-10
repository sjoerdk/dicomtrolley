from io import BytesIO
from typing import List

from pydicom.dataset import Dataset
from pydicom.tag import Tag


def quick_dataset(*_, **kwargs) -> Dataset:
    """Creates a pydicom dataset with keyword args as tagname - value pairs

    Examples
    --------
    >>> ds = quick_dataset(PatientName='Jane', StudyDescription='Test')
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
    dataset.is_little_endian = True  # required common meta header choice
    dataset.is_implicit_VR = False  # required common meta header choice
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


def create_c_find_image_response(
    study_instance_uid,
    series_instance_uids: List[str],
    sop_class_uids: List[str],
) -> List[Dataset]:
    """Datasets like the ones returned from a successful IMAGE level CFIND with
    PatientRootQueryRetrieveInformationModelFind
    Instances that each contain uids to their containing series and studies
    """
    responses = []
    for series_instance_uid in series_instance_uids:
        for sop_instance_uid in sop_class_uids:
            responses.append(
                quick_dataset(
                    StudyInstanceUID=study_instance_uid,
                    SeriesInstanceUID=series_instance_uid,
                    SOPInstanceUID=sop_instance_uid,
                )
            )
    return responses


def create_c_find_study_response(study_instance_uids) -> List[Dataset]:
    """Datasets like the ones returned from a successful STUDY level CFIND with
    PatientRootQueryRetrieveInformationModelFind
    """
    response = []
    for study_instance_uid in study_instance_uids:
        response.append(
            quick_dataset(StudyInstanceUID=study_instance_uid, Modality="CT")
        )

    return response
