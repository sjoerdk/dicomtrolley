from datetime import datetime
from unittest.mock import Mock

import pynetdicom
import pytest as pytest

from dicomtrolley.dicom_qr import DICOMQR, DICOMQuery, QueryRetrieveLevels
from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.mint import QueryLevels
from tests.factories import (
    create_c_find_image_response,
    create_c_find_study_response,
    quick_dataset,
)


def test_qr_query():
    query = DICOMQuery(
        StudyInstanceUID="123",
        QueryRetrieveLevel=QueryLevels.SERIES,
        minStudyDate=datetime(year=2020, month=3, day=1),
    )
    ds = query.as_dataset()
    assert ds.StudyInstanceUID == "123"
    assert ds.StudyDate == "20200301-"
    assert ds.QueryRetrieveLevel == QueryLevels.SERIES
    assert (
        ds.SeriesInstanceUID == ""
    )  # should be added as default for QueryLevel


@pytest.mark.parametrize(
    "parameters",
    [
        {
            "StudyInstanceUID": "123",
            "QueryRetrieveLevel": QueryLevels.SERIES,
            "minStudyDate": datetime(year=2020, month=3, day=1),
        },
        {
            "AccessionNumber": "123",
            "QueryRetrieveLevel": QueryRetrieveLevels.IMAGE,
        },
        {"StudyID": "123", "QueryRetrieveLevel": QueryRetrieveLevels.STUDY},
    ],
)
def test_qr_query_allowed_parameters(parameters):
    """These should work without problems"""
    assert DICOMQuery(**parameters).as_dataset()


@pytest.mark.parametrize(
    "parameters",
    [
        {"StudyThing": "123"},  # invalid dicom tag
        {"QueryRetrieveLevel": "Something"},  # invalid retrieve level
        {"unknown": "123"},  # trying to set non-existent parameter
    ],
)
def test_qr_query_exceptions(parameters):
    with pytest.raises(ValueError):
        DICOMQuery(**parameters)


def test_find_studies(monkeypatch):
    qr = DICOMQR(host="host", port=123)
    qr.send_c_find = Mock(
        return_value=create_c_find_image_response(
            study_instance_uid="Study1",
            series_instance_uids=["Series1"],
            sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
        )
    )

    studies = qr.find_studies(query=None)
    assert len(studies) == 1
    assert studies[0].uid == "Study1"
    assert len(studies[0].series[0].instances) == 9


def test_parse_instance_response():
    """Parse CFIND response for IMAGE level. This should yield a full-depth
    study/series/instance object
    """
    qr = DICOMQR(host="host", port=123)
    parsed = qr.parse_c_find_response(
        create_c_find_image_response(
            study_instance_uid="Study1",
            series_instance_uids=["Series1"],
            sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
        )
    )

    assert len(parsed) == 1
    assert len(parsed[0].series) == 1
    assert len(parsed[0].series[0].instances) == 9


def test_parse_study_response():
    """Parse CFIND response for STUDY level. This is missing any series or instance
    info and should yield studies with no series
    """
    qr = DICOMQR(host="host", port=123)
    parsed = qr.parse_c_find_response(
        create_c_find_study_response(
            study_instance_uids=[f"Study{i}" for i in range(1, 10)]
        )
    )

    assert len(parsed) == 9
    assert len(parsed[0].series) == 0


@pytest.fixture
def a_mock_ae_associate():
    """Mock the main function used in retrieving DICOM-QR information"""
    assoc = Mock(spec=pynetdicom.association.Association)
    assoc.send_c_find = Mock(
        return_value=iter(
            [
                ("status", quick_dataset(PatientName="patient")),
                ("status2", quick_dataset(PatientName="patient2")),
            ]
        )
    )
    assoc.is_established = True
    return assoc


def test_send_cfind(a_mock_ae_associate, monkeypatch):
    monkeypatch.setattr(
        "dicomtrolley.dicom_qr.AE.associate",
        Mock(return_value=a_mock_ae_associate),
    )
    qr = DICOMQR(host="host", port=123)
    results = qr.send_c_find(query=DICOMQuery())
    assert len(results) == 2
    assert results[0].PatientName == "patient"


def test_send_cfind_no_connection(a_mock_ae_associate, monkeypatch):
    a_mock_ae_associate.is_established = False
    monkeypatch.setattr(
        "dicomtrolley.dicom_qr.AE.associate",
        Mock(return_value=a_mock_ae_associate),
    )

    qr = DICOMQR(host="host", port=123)
    with pytest.raises(DICOMTrolleyException):
        qr.send_c_find(query=DICOMQuery())
