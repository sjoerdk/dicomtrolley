"""Special doctest Pytest configuration. Other configuration in tests/conftest.py"""

from typing import Any, Dict

import pytest
import requests
from sybil import Sybil
from sybil.parsers.myst import PythonCodeBlockParser

from dicomtrolley.core import Query
from dicomtrolley.mint import Mint
from dicomtrolley.storage import StorageDir
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado_uri import WadoURI
from tests.conftest import set_mock_response
from tests.mock_responses import (
    MINT_SEARCH_INSTANCE_LEVEL_ANY,
    WADO_RESPONSE_DICOM_ANY,
)


@pytest.fixture
def mock_requests(requests_mock):
    """Requests_mock fixture replaces requests with mock. Returns this mock

    Still needs original import to work apparently
    """
    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)
    set_mock_response(requests_mock, WADO_RESPONSE_DICOM_ANY)
    return requests_mock


class NoSaveStorageDir(StorageDir):
    def save(self, dataset, path=None):
        """Do not actually write to disk"""
        pass


@pytest.fixture
def no_storage(monkeypatch):
    """Replaces default trolley storage class with one that does not touch disk"""

    monkeypatch.setattr("dicomtrolley.trolley.StorageDir", NoSaveStorageDir)
    return NoSaveStorageDir


def setup_namespace(namespace: Dict[str, Any]):
    """All imports done before each of the examples"""
    to_add = {
        "requests": requests,
        "Trolley": Trolley,
        "Mint": Mint,
        "WadoURI": WadoURI,
        "Query": Query,
    }

    namespace.update(to_add)


pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()],
    pattern="README.md",
    fixtures=["mock_requests", "no_storage"],
    setup=setup_namespace,
).pytest()
