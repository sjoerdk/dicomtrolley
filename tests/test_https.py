import pytest

from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.https import VitreaConnectionLogin, log_in_to
from tests.mockresponses import MockUrls


@pytest.fixture
def a_login():
    return VitreaConnectionLogin(url=MockUrls.LOGIN)


def test_login(a_login, login_works):
    """Just check that nothing crashes"""
    session = a_login.get_session(user="test", password="test", realm="test")
    assert session


def test_login_fails(a_login, login_denied):
    """Check that correct exception is raised"""
    with pytest.raises(DICOMTrolleyException) as e:
        a_login.get_session(user="test", password="test", realm="test")
    assert "Unauthorized" in str(e)


def test_get_session_no_env(a_login, login_works):
    """No env has been set. Login should fail"""
    with pytest.raises(DICOMTrolleyException):
        log_in_to(MockUrls.LOGIN)


def test_get_session_works(a_login, login_works, monkeypatch):
    """No env has been set. Login should fail"""
    monkeypatch.setenv("USER", "test_user")
    monkeypatch.setenv("PASSWORD", "test_password")
    monkeypatch.setenv("REALM", "test_realm")

    session = log_in_to(MockUrls.LOGIN)
    assert session
