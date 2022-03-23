from io import BytesIO
from typing import List

from jinja2.environment import Template
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from dicomtrolley.dicom_qr import DICOMQR
from dicomtrolley.xml_templates import RAD69_SOAP_RESPONSE_TEMPLATE


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


def create_rad69_multipart_response_bytestream(dataset):
    """Quick and dirty example of the multi-part response sent by a rad69 server"""
    response = Template(RAD69_SOAP_RESPONSE_TEMPLATE.replace(" ", "")).render(
        dicom_bytestream=create_dicom_bytestream(dataset)
    )
    return bytes(response, "utf-8")


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
) -> Dataset:
    return DICOMQR.parse_c_find_response(
        create_c_find_image_response(
            study_instance_uid, series_instance_uids, sop_class_uids
        )
    )[0]


def quick_image_level_study(uid) -> Dataset:
    """Study with 2 series and some Instances in each series"""
    return create_image_level_study(
        uid,
        series_instance_uids=["Series1", "series2"],
        sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
    )
