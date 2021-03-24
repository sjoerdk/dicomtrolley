import pytest

from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.https import VitreaConnectionLogin
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
