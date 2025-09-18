from io import BytesIO
from typing import List

import factory
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.tag import Tag

from dicomtrolley.core import (
    InstanceReference,
    SeriesReference,
    Study,
    StudyReference,
)
from dicomtrolley.dicom_qr import DICOMQR


class InstanceReferenceFactory(factory.Factory):
    class Meta:
        model = InstanceReference

    study_uid = factory.Sequence(lambda n: f"study_{n}")
    series_uid = factory.Sequence(lambda n: f"series_{n}")
    instance_uid = factory.Sequence(lambda n: f"instance_{n}")


class SeriesReferenceFactory(factory.Factory):
    class Meta:
        model = SeriesReference

    study_uid = factory.Sequence(lambda n: f"study_{n}")
    series_uid = factory.Sequence(lambda n: f"series_{n}")


class StudyReferenceFactory(factory.Factory):
    class Meta:
        model = StudyReference

    study_uid = factory.Sequence(lambda n: f"study_{n}")


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
    """Bytes constituting a valid dicom dataset

    Disclaimer
    ---------
    Sets a bunch of options and file_meta elements in the hope that things will
    not crash. I just need a bytestream. What was a MediaStorageSOPClassUID again?
    So sorry.
    """
    content = BytesIO()
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False

    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    dataset.file_meta.MediaStorageSOPClassUID = (
        "1.2.840.10008.5.1.4.1.1.2"  # CT
    )
    dataset.file_meta.MediaStorageSOPInstanceUID = "123"

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


def create_image_level_study(
    study_instance_uid,
    series_instance_uids: List[str],
    sop_class_uids: List[str],
) -> Study:
    return DICOMQR.parse_c_find_response(
        create_c_find_image_response(
            study_instance_uid, series_instance_uids, sop_class_uids
        )
    )[0]


def quick_image_level_study(uid) -> Study:
    """Study with 2 series and some Instances in each series"""
    return create_image_level_study(
        uid,
        series_instance_uids=["Series1", "series2"],
        sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
    )
