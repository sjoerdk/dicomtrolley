import pytest

from dicomtrolley.exceptions import DICOMTrolleyException
from tests.conftest import set_mock_response
from tests.mockresponses import (
    MockWadoParameters,
    WADO_RESPONSE_DICOM,
    WADO_RESPONSE_INVALID_DICOM,
)


def test_wado_get_dataset(a_wado, requests_mock):
    """Retrieve dicom data via a wado call"""
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM)

    ds = a_wado.get_dataset(
        study_instance_uid=MockWadoParameters.study_instance_uid,
        series_instance_uid=MockWadoParameters.series_instance_uid,
        sop_instance_iud=MockWadoParameters.sop_instance_iud,
    )

    assert ds.PatientName == "Jane"
    assert ds.StudyDescription == "Test"


def test_wado_get_faulty_dataset(a_wado, requests_mock):
    """Server can return strange invalid dicom-like responses. Catch these"""
    set_mock_response(requests_mock, WADO_RESPONSE_INVALID_DICOM)

    with pytest.raises(DICOMTrolleyException) as e:
        a_wado.get_dataset(
            study_instance_uid=MockWadoParameters.study_instance_uid,
            series_instance_uid=MockWadoParameters.series_instance_uid,
            sop_instance_iud=MockWadoParameters.sop_instance_iud,
        )
    assert "Error retrieving instance" in str(e)
