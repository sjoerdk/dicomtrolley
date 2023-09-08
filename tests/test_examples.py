"""Tests the scripts in /examples for basic errors"""
import pytest

from dicomtrolley.storage import StorageDir
from examples.go_shopping import go_shopping
from examples.go_shopping_rad69 import go_shopping_rad69
from tests.conftest import set_mock_response
from tests.mock_responses import LOGIN_SUCCESS, MockUrls, RAD69_RESPONSE_ANY
from tests.mock_servers import (
    MINT_SEARCH_INSTANCE_LEVEL_ANY,
    WADO_URI_RESPONSE_DICOM_ANY,
)


class NoSaveStorageDir(StorageDir):
    def save(self, dataset, path=None):
        """Do not actually write to disk"""
        pass


@pytest.fixture
def no_storage(monkeypatch):
    """Replaces default trolley storage class with one that does not touch disk"""

    monkeypatch.setattr("dicomtrolley.trolley.StorageDir", NoSaveStorageDir)
    return NoSaveStorageDir


@pytest.fixture()
def example_env(monkeypatch):
    """Set up all env values used in examples"""
    monkeypatch.setenv("USER", "Username")
    monkeypatch.setenv("PASSWORD", "Password")
    monkeypatch.setenv("REALM", "a_realm")
    monkeypatch.setenv("LOGIN_URL", MockUrls.LOGIN)
    monkeypatch.setenv("MINT_URL", MockUrls.MINT_URL)
    monkeypatch.setenv("WADO_URL", MockUrls.WADO_URI_URL)
    monkeypatch.setenv("RAD69_URL", MockUrls.RAD69_URL)
    monkeypatch.setenv("DOWNLOAD_PATH", "/tmp")


@pytest.fixture
def mock_requests(requests_mock):
    """Make sure no actual requests are made and that
    requests return some reasonable mock data
    """
    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)
    set_mock_response(requests_mock, WADO_URI_RESPONSE_DICOM_ANY)
    set_mock_response(requests_mock, LOGIN_SUCCESS)
    set_mock_response(requests_mock, RAD69_RESPONSE_ANY)
    return requests_mock


def test_go_shopping(mock_requests, no_storage, example_env):
    go_shopping()


def test_go_shopping_rad69(mock_requests, no_storage, example_env):
    go_shopping_rad69()
