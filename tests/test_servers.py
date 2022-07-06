import pytest
import requests

from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.servers import IMPAXDataCenter, VitreaConnection
from tests.conftest import set_mock_response
from tests.mock_responses import (
    LOGIN_DENIED_IMPAX,
    LOGIN_IMPAX_INITIAL,
    LOGIN_SUCCESS_IMPAX,
    MockUrls,
)


@pytest.fixture
def a_login():
    return VitreaConnection(login_url=MockUrls.LOGIN)


def test_login(a_login, login_works):
    """Just check that nothing crashes"""
    session = a_login.log_in(user="test", password="test", realm="test")
    assert session


def test_login_fails(a_login, login_denied):
    """Check that correct exception is raised"""
    with pytest.raises(DICOMTrolleyError) as e:
        a_login.log_in(user="test", password="test", realm="test")
    assert "Unauthorized" in str(e)


@pytest.fixture
def an_impax(requests_mock):
    impax = IMPAXDataCenter(wado_url=MockUrls.LOGIN)
    set_mock_response(requests_mock, LOGIN_IMPAX_INITIAL)
    return impax


def test_impax_login_works(an_impax, requests_mock):
    set_mock_response(requests_mock, LOGIN_SUCCESS_IMPAX)
    assert an_impax.log_in("user", "pass")


def test_impax_login_fails(an_impax, requests_mock):
    set_mock_response(requests_mock, LOGIN_DENIED_IMPAX)
    with pytest.raises(DICOMTrolleyError):
        an_impax.log_in("user", "pass")


def test_impax_login_fails_connection_error(requests_mock):
    requests_mock.register_uri(
        url=MockUrls.LOGIN,
        method="GET",
        exc=requests.exceptions.ConnectionError,
    )
    with pytest.raises(DICOMTrolleyError):
        IMPAXDataCenter(wado_url=MockUrls.LOGIN).log_in("user", "pass")
