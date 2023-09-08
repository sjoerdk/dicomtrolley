"""Tests the scripts in /examples for basic errors"""
from unittest.mock import Mock

import pytest

from dicomtrolley.storage import StorageDir
from examples.go_shopping import go_shopping
from examples.go_shopping_rad69 import go_shopping_rad69
from examples.search_for_studies_dicom_qr import search_for_studies_dicom_qr
from examples.search_for_studies_mint import search_for_studies_mint
from examples.use_wado_only import use_wado_only
from tests.conftest import set_mock_response
from tests.factories import create_c_find_image_response
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
    monkeypatch.setenv("HOST", "a_host")
    monkeypatch.setenv("PORT", "1000")
    monkeypatch.setenv("AET", "THEIR_NAME")
    monkeypatch.setenv("AEC", "MY_NAME")


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


@pytest.fixture()
def example_setup(mock_requests, no_storage, example_env):
    """Seed env, no real requests, no storage"""
    pass


def test_go_shopping(example_setup):
    go_shopping()


def test_go_shopping_rad69(example_setup):
    go_shopping_rad69()


def test_search_for_studies_dicom_qr(example_setup, monkeypatch):
    send_c_find = Mock(
        return_value=create_c_find_image_response(
            study_instance_uid="Study1",
            series_instance_uids=["Series1"],
            sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
        )
    )
    # make cfind work without calling any server
    monkeypatch.setattr(
        "examples.search_for_studies_dicom_qr.DICOMQR.send_c_find", send_c_find
    )
    search_for_studies_dicom_qr()


def test_search_for_studies_mint(example_setup):
    search_for_studies_mint()


def test_use_wado_only(example_setup):
    use_wado_only()
