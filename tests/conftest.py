import pytest

from tests.mockresponses import (
    LOGIN_DENIED,
    LOGIN_SUCCESS,
    MINT_SEARCH_INSTANCE_LEVEL,
    MINT_SEARCH_SERIES_LEVEL,
    MINT_SEARCH_STUDY_LEVEL,
    set_mock_response,
)


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
