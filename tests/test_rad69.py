import pytest

from dicomtrolley.core import InstanceReference
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.rad69 import Rad69
from tests.conftest import set_mock_response
from tests.factories import quick_dataset
from tests.mock_responses import (
    MockUrls,
    RAD69_RESPONSE_INVALID_DICOM,
    RAD69_RESPONSE_INVALID_NON_DICOM,
    RAD69_RESPONSE_INVALID_NON_MULTIPART,
    create_rad69_response_from_dataset,
)


@pytest.fixture
def a_rad69(a_session):
    """A basic rad69 module that you can query"""
    return Rad69(session=a_session, url=MockUrls.RAD69_URL)


def test_rad69_get_dataset(a_rad69, requests_mock):
    """Retrieve dicom data via a rad69 call"""
    set_mock_response(
        requests_mock,
        create_rad69_response_from_dataset(
            quick_dataset(PatientName="Jim", StudyDescription="Thing")
        ),
    )

    ds = a_rad69.get_dataset(
        InstanceReference(
            study_instance_uid="1",
            series_instance_uid="2",
            sop_instance_uid="3",
        )
    )

    assert ds.PatientName == "Jim"
    assert ds.StudyDescription == "Thing"


@pytest.mark.parametrize(
    "mock_response",
    [
        RAD69_RESPONSE_INVALID_DICOM,
        RAD69_RESPONSE_INVALID_NON_DICOM,
        RAD69_RESPONSE_INVALID_NON_MULTIPART,
    ],
)
def test_rad69_get_faulty_dataset(a_rad69, requests_mock, mock_response):
    """Server can return strange invalid dicom-like responses, or http error codes
    Catch these
    """
    set_mock_response(requests_mock, mock_response)

    with pytest.raises(DICOMTrolleyError):
        a_rad69.get_dataset(
            InstanceReference(
                study_instance_uid=1,
                series_instance_uid=2,
                sop_instance_uid=3,
            )
        )


def test_wado_datasets_async(a_rad69, requests_mock):
    set_mock_response(
        requests_mock,
        create_rad69_response_from_dataset(
            quick_dataset(PatientName="patient1", StudyDescription="a_study")
        ),
    )

    instances = [
        InstanceReference(
            study_instance_uid=1, series_instance_uid=2, sop_instance_uid=3
        ),
        InstanceReference(
            study_instance_uid=4, series_instance_uid=5, sop_instance_uid=6
        ),
    ]

    datasets = [x for x in a_rad69.datasets_async(instances)]
    assert len(datasets) == 2
    assert datasets[0].PatientName == "patient1"
    assert (
        requests_mock.last_request.headers["Content-type"]
        == "application/soap+xml"
    )
