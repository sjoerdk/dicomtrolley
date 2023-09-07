"""Special doctest Pytest configuration. Other configuration in tests/conftest.py"""
from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock, create_autospec

import pytest
import requests
from requests import Session
from sybil import Sybil
from sybil.parsers.myst import PythonCodeBlockParser

from dicomtrolley.auth import VitreaAuth
from dicomtrolley.core import (
    Downloader,
    InstanceReference,
    Query,
    QueryLevels,
    Searcher,
    SeriesReference,
    StudyReference,
)
from dicomtrolley.dicom_qr import DICOMQR
from dicomtrolley.mint import Mint, MintQuery
from dicomtrolley.qido_rs import QidoRS
from dicomtrolley.rad69 import Rad69
from dicomtrolley.storage import StorageDir
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado_rs import WadoRS
from dicomtrolley.wado_uri import WadoURI
from tests.conftest import set_mock_response
from tests.mock_responses import LOGIN_SUCCESS
from tests.mock_servers import (
    MINT_SEARCH_INSTANCE_LEVEL_ANY,
    WADO_URI_RESPONSE_DICOM_ANY,
)


@pytest.fixture
def mock_requests(requests_mock):
    """Requests_mock fixture replaces requests with mock. Returns this mock

    Still needs original import to work apparently
    """
    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)
    set_mock_response(requests_mock, WADO_URI_RESPONSE_DICOM_ANY)
    set_mock_response(requests_mock, LOGIN_SUCCESS)
    return requests_mock


@pytest.fixture
def trolley(a_trolley):
    """Used when 'trolley' is called in docs examples"""
    # Avoid 'could not find x' exceptions for trolley.download(x)
    a_trolley.download = create_autospec(a_trolley.download)

    return a_trolley


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
    """All imports done before each of the examples in docs"""
    to_add = {
        "requests": requests,
        "Trolley": Trolley,
        "Mint": Mint,
        "WadoURI": WadoURI,
        "WadoRS": WadoRS,
        "Rad69": Rad69,
        "QidoRS": QidoRS,
        "Query": Query,
        "DICOMQR": DICOMQR,
        "QueryLevels": QueryLevels,
        "datetime": datetime,
        "MintQuery": MintQuery,
        "a_session": Mock(spec=Session),
        "a_searcher": Mock(spec=Searcher),
        "a_downloader": Mock(spec=Downloader),
        "StudyReference": StudyReference,
        "SeriesReference": SeriesReference,
        "InstanceReference": InstanceReference,
    }
    to_add_authentication = {"VitreaAuth": VitreaAuth}  # for authentication.md

    namespace.update(to_add)
    namespace.update(to_add_authentication)


pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()],
    pattern="*.md",
    fixtures=["mock_requests", "no_storage", "trolley"],
    setup=setup_namespace,
).pytest()
