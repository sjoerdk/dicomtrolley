from datetime import date, datetime
from typing import List

import pytest
import requests

from dicomtrolley.core import Query, Series, Study
from dicomtrolley.dicom_qr import DICOMQR
from dicomtrolley.mint import Mint, MintStudy, parse_mint_studies_response
from dicomtrolley.wado import Wado
from tests.factories import (
    create_c_find_image_response,
    create_c_find_study_response,
)
from tests.mock_responses import (
    LOGIN_DENIED,
    LOGIN_SUCCESS,
    MINT_SEARCH_INSTANCE_LEVEL,
    MINT_SEARCH_SERIES_LEVEL,
    MINT_SEARCH_STUDY_LEVEL,
    MockUrls,
)


@pytest.fixture
def a_session(requests_mock):
    """Calling requests_mock fixture here will mock all calls to requests"""
    return requests.session()


@pytest.fixture
def login_works(requests_mock):
    """Call to mock login url will succeed"""
    return set_mock_response(requests_mock, LOGIN_SUCCESS)


@pytest.fixture
def login_denied(requests_mock):
    """Call to mock login url will fail"""
    return set_mock_response(requests_mock, LOGIN_DENIED)


@pytest.fixture
def mock_mint_responses(requests_mock):
    """Calling MINT MockUrls will return mocked responses"""
    for mock in (
        MINT_SEARCH_STUDY_LEVEL,
        MINT_SEARCH_SERIES_LEVEL,
        MINT_SEARCH_INSTANCE_LEVEL,
    ):
        set_mock_response(requests_mock, mock)


@pytest.fixture
def a_mint(a_session):
    """Mint search with faked urls"""
    return Mint(session=a_session, url=MockUrls.MINT_URL)


@pytest.fixture
def a_wado(a_session):
    return Wado(session=a_session, url=MockUrls.WADO_URL)


@pytest.fixture
def a_mint_study_with_instances() -> MintStudy:
    """An example MintStudy object"""
    studies = parse_mint_studies_response(MINT_SEARCH_INSTANCE_LEVEL.text)
    return studies[0]


@pytest.fixture
def a_mint_study_without_instances() -> MintStudy:
    """An example MintStudy object"""
    studies = parse_mint_studies_response(MINT_SEARCH_STUDY_LEVEL.text)
    return studies[0]


@pytest.fixture
def some_mint_studies(
    a_mint_study_with_instances, a_mint_study_without_instances
):
    return [a_mint_study_with_instances, a_mint_study_without_instances]


def set_mock_response(requests_mock, response):
    """Register the given MockResponse with requests_mock"""
    requests_mock.register_uri(**response.as_dict())
    return response


@pytest.fixture
def an_image_level_study() -> List[Study]:
    """A study with series and slice info"""
    response = create_c_find_image_response(
        study_instance_uid="Study1",
        series_instance_uids=["Series1", "Series2"],
        sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
    )
    return DICOMQR.parse_c_find_response(response)


@pytest.fixture
def an_image_level_series() -> Series:
    """A study with series and slice info"""
    response = create_c_find_image_response(
        study_instance_uid="Study1",
        series_instance_uids=["Series1"],
        sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
    )
    study = DICOMQR.parse_c_find_response(response)[0]
    return study.get("Series1")


@pytest.fixture
def another_image_level_series() -> Series:
    """A study with series and slice info"""
    response = create_c_find_image_response(
        study_instance_uid="Study1",
        series_instance_uids=["Series2"],
        sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
    )
    study = DICOMQR.parse_c_find_response(response)[0]
    return study.get("Series2")


@pytest.fixture
def a_study_level_study():
    """Study witnout slice info"""
    return DICOMQR.parse_c_find_response(
        create_c_find_study_response(study_instance_uids=["Study2"])
    )


@pytest.fixture
def some_studies(an_image_level_study, a_study_level_study):
    """Two studies. One at image level, with all slice info included. One at
    study level, without slice info
    """

    return an_image_level_study + a_study_level_study


@pytest.fixture
def a_basic_query():
    """A Query with all possible parameters filled in"""

    dicom_parameters = {
        "AccessionNumber": "123",
        "InstitutionName": "Hospital",
        "InstitutionalDepartmentName": "Department",
        "ModalitiesInStudy": "MR*",
        "PatientID": "1234",
        "PatientName": "Patient*",
        "PatientSex": "F",
        "StudyDescription": "A study",
        "StudyInstanceUID": "4567",
    }

    meta_parameters = {
        "query_level": "INSTANCE",
        "PatientBirthDate": date(year=1990, month=1, day=1),
        "min_study_date": datetime(year=2020, month=3, day=1),
        "max_study_date": datetime(year=2020, month=3, day=5),
        "include_fields": ["NumberOfStudyRelatedInstances"],
    }

    all_parameters = {**dicom_parameters, **meta_parameters}
    return Query(**all_parameters)
