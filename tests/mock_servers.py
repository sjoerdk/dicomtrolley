"""combined individual responses from mock_responses for test utility"""
import re
from copy import deepcopy

from tests.conftest import set_mock_response
from tests.mock_responses import (
    MINT_SEARCH_INSTANCE_LEVEL,
    MockUrls,
    WADO_RESPONSE_DICOM,
)


def default_mock_responses(requests_mock):
    """Any trolly call to mock_responses.MockUrls will yield a reasonable response

    Reasonable means it will at least be parseable. It does not mean a query
    returns the actual data requested. Just if you request any study, you get
    a study back. Don't dig deeper. I'm not implementing a whole server here ok?
    """

    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)
    set_mock_response(requests_mock, WADO_URI_RESPONSE_DICOM_ANY)

    # TODO: detect requests for series study or instance level and respond accordingly
    # TODO: detect queries for multiple or single study (SeriesInstanceUID present?)
    return requests_mock


MINT_SEARCH_INSTANCE_LEVEL_ANY = deepcopy(MINT_SEARCH_INSTANCE_LEVEL)
MINT_SEARCH_INSTANCE_LEVEL_ANY.url = re.compile(f"{MockUrls.MINT_URL}.*")

WADO_URI_RESPONSE_DICOM_ANY = deepcopy(WADO_RESPONSE_DICOM)
WADO_URI_RESPONSE_DICOM_ANY.url = re.compile(f"{MockUrls.WADO_URI_URL}.*")
