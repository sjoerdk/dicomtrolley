from datetime import datetime
from unittest.mock import Mock

import pynetdicom
import pytest as pytest

from dicomtrolley.core import BasicQuery
from dicomtrolley.dicom_qr import DICOMQR, DICOMQuery, QueryRetrieveLevels
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.mint import QueryLevels
from tests.factories import (
    create_c_find_image_response,
    create_c_find_study_response,
    quick_dataset,
)


def test_qr_query():
    """A dicom qr query should be rendered into a query dataset"""

    dicom_parameters = {
        "AccessionNumber": "123",
        "Modality": "US",
        "PatientID": "1234",
        "PatientName": "Patient*",
        "ProtocolName": "A procotol",
        "SeriesDescription": "A series",
        "StudyDescription": "A study",
        "StudyID": "12345",
        "StudyInstanceUID": "4567",
    }
    meta_parameters = {
        "query_retrieve_level": "IMAGE",
        "min_study_date": datetime(year=2020, month=3, day=1),
        "max_study_date": datetime(year=2020, month=3, day=5),
        "include_fields": ["NumberOfStudyRelatedInstances"],
    }

    all_parameters = {**dicom_parameters, **meta_parameters}
    query = DICOMQuery(**all_parameters)
    dataset = query.as_dataset()

    # Regular dicom parameters should all have been translated
    for keyword, expected in dicom_parameters.items():
        assert dataset[keyword].value == expected

    # meta parameter should have been converted
    assert dataset["StudyDate"].value == "20200301-20200305"
    assert dataset.query_retrieve_level == "IMAGE"
    assert "NumberOfStudyRelatedInstances" in dataset


def test_qr_query_exclude_default_params():
    """If a parameter has not been explicitly given to a DICOMQuery, it should not
    pollute any DICOM query so should be ignored
    """
    query = DICOMQuery(StudyInstanceUID="123")
    assert (
        query.PatientName == ""
    )  # not passed in init, so default empty value
    assert (
        "StudyInstanceUID" in query.as_dataset()
    )  # SID was passed so should exist
    assert "PatientName" not in query.as_dataset()  # not passed, so ignored


def test_qr_query_do_not_overwrite_parameters():
    """If a parameter is passed in init and also in IncludeFields, don't overwrite
    the init value
    """
    query = DICOMQuery(
        StudyInstanceUID="123",
        ProtocolName="foo",
        include_fields=["StudyInstanceUID", "ProtocolName"],
    )
    assert query.StudyInstanceUID == "123"
    assert query.ProtocolName == "foo"
    ds = query.as_dataset()
    assert ds.StudyInstanceUID == "123"
    assert ds.ProtocolName == "foo"


@pytest.mark.parametrize(
    "parameters",
    [
        {
            "StudyInstanceUID": "123",
            "query_retrieve_level": QueryLevels.SERIES,
            "min_study_date": datetime(year=2020, month=3, day=1),
        },
        {
            "AccessionNumber": "123",
            "query_retrieve_level": QueryRetrieveLevels.IMAGE,
        },
        {"StudyID": "123", "query_retrieve_level": QueryRetrieveLevels.STUDY},
    ],
)
def test_qr_query_allowed_parameters(parameters):
    """These should work without problems"""
    assert DICOMQuery(**parameters).as_dataset()


@pytest.mark.parametrize(
    "parameters",
    [
        {"StudyThing": "123"},  # invalid dicom tag
        {"query_retrieve_level": "Something"},  # invalid retrieve level
        {"unknown": "123"},  # trying to set non-existent parameter
    ],
)
def test_qr_query_exceptions(parameters):
    with pytest.raises(ValueError):
        DICOMQuery(**parameters)


def test_query_from_basic(a_basic_query):
    query = DICOMQuery.init_from_basic_query(a_basic_query)

    # check that query level has been translated properly
    assert a_basic_query.query_level == "INSTANCE"
    assert query.query_retrieve_level == "IMAGE"
    assert "query_level" not in query.dict()

    # and all other basic values have been passed along
    for key, value in a_basic_query.dict().items():
        if key != "query_level":
            assert query.dict()[key] == value


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


def test_find_study_with_basic_query():
    """Basic query should be converted"""

    qr = DICOMQR(host="host", port=123)
    qr.send_c_find = Mock()
    qr.parse_c_find_response = Mock()

    qr.find_studies(query=BasicQuery(PatientID="test"))
    called = qr.send_c_find.call_args.args[0]
    assert type(called) == DICOMQuery
    assert called.PatientID == "test"


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
    with pytest.raises(DICOMTrolleyError):
        qr.send_c_find(query=DICOMQuery())
