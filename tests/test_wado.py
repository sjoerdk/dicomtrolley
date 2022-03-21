import pytest

from dicomtrolley.core import InstanceReference
from dicomtrolley.exceptions import DICOMTrolleyError
from tests.conftest import set_mock_response
from tests.mock_responses import (
    MockWadoParameters,
    WADO_RESPONSE_DICOM,
    WADO_RESPONSE_INVALID_DICOM,
    WADO_RESPONSE_INVALID_NON_DICOM,
)


def test_wado_get_dataset(a_wado, requests_mock):
    """Retrieve dicom data via a wado call"""
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM)

    ds = a_wado.get_dataset(
        InstanceReference(
            study_instance_uid=MockWadoParameters.study_instance_uid,
            series_instance_uid=MockWadoParameters.series_instance_uid,
            sop_instance_uid=MockWadoParameters.sop_instance_uid,
        )
    )

    assert ds.PatientName == "Jane"
    assert ds.StudyDescription == "Test"


@pytest.mark.parametrize(
    "mock_response",
    [WADO_RESPONSE_INVALID_DICOM, WADO_RESPONSE_INVALID_NON_DICOM],
)
def test_wado_get_faulty_dataset(a_wado, requests_mock, mock_response):
    """Server can return strange invalid dicom-like responses. Catch these"""
    set_mock_response(requests_mock, mock_response)

    with pytest.raises(DICOMTrolleyError):
        a_wado.get_dataset(
            InstanceReference(
                study_instance_uid=MockWadoParameters.study_instance_uid,
                series_instance_uid=MockWadoParameters.series_instance_uid,
                sop_instance_uid=MockWadoParameters.sop_instance_uid,
            )
        )


def test_instance_reference():
    assert "333" in str(MockWadoParameters.as_instance_reference())


def test_wado_datasets(a_wado, requests_mock):
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM)

    instances = [
        MockWadoParameters.as_instance_reference(),
        MockWadoParameters.as_instance_reference(),
    ]

    datasets = [x for x in a_wado.datasets(instances)]
    assert len(datasets) == 2
    assert datasets[0].PatientName == "Jane"


def test_wado_datasets_async(a_wado, requests_mock):
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM)

    instances = [
        MockWadoParameters.as_instance_reference(),
        MockWadoParameters.as_instance_reference(),
    ]

    datasets = [x for x in a_wado.datasets_async(instances)]
    assert len(datasets) == 2
    assert datasets[0].PatientName == "Jane"
