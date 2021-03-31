import pytest

from tests.conftest import set_mock_response
from tests.mockresponses import (
    MockWadoParameters,
    WADO_RESPONSE_DICOM,
)


@pytest.fixture
def mock_wado_response(requests_mock):
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM)
    return WADO_RESPONSE_DICOM


def test_wado_get_dataset(a_wado, mock_wado_response):
    """Retrieve dicom data via a wado call"""

    ds = a_wado.get_dataset(
        study_instance_uid=MockWadoParameters.study_instance_uid,
        series_instance_uid=MockWadoParameters.series_instance_uid,
        sop_instance_iud=MockWadoParameters.sop_instance_iud,
    )

    assert ds.PatientName == "Jane"
    assert ds.StudyDescription == "Test"
