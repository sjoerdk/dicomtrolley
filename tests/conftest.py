import pytest
import requests

from dicomtrolley.mint import Mint, MintStudy, parse_mint_studies_response
from dicomtrolley.wado import Wado
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
    return Mint(session=a_session, url=MockUrls.MINT_URL)


@pytest.fixture
def a_wado(a_session):
    return Wado(session=a_session, url=MockUrls.WADO_URL)


@pytest.fixture
def a_study_with_instances() -> MintStudy:
    """An example MintStudy object"""
    studies = parse_mint_studies_response(MINT_SEARCH_INSTANCE_LEVEL.text)
    return studies[0]


@pytest.fixture
def a_study_without_instances() -> MintStudy:
    """An example MintStudy object"""
    studies = parse_mint_studies_response(MINT_SEARCH_STUDY_LEVEL.text)
    return studies[0]


@pytest.fixture
def some_studies(a_study_with_instances, a_study_without_instances):
    return [a_study_with_instances, a_study_with_instances]


def set_mock_response(requests_mock, response):
    """Register the given MockResponse with requests_mock"""
    requests_mock.register_uri(**response.as_dict())
    return response
