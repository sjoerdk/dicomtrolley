from datetime import datetime

import pytest

from dicomtrolley.core import QueryLevels
from dicomtrolley.qido_rs import HierarchicalQuery, QidoRS, RelationalQuery
from tests.conftest import set_mock_response
from tests.mock_responses import (
    MockUrls,
    QIDO_RS_204_NO_RESULTS,
    QIDO_RS_STUDY_LEVEL,
)


@pytest.mark.parametrize(
    "query_params",
    [
        {"StudyInstanceUID": "123"},
        {"StudyInstanceUID": "123", "SeriesInstanceUID": "456"},
        {
            "min_study_date": datetime(year=2023, month=5, day=29),
            "max_study_date": datetime(year=2023, month=5, day=29),
        },
    ],
)
def test_valid_hierarchical_query(query_params):
    """These queries should not raise any exceptions"""
    assert HierarchicalQuery(**query_params)  # check for no init exceptions


@pytest.mark.parametrize(
    "query_params",
    [
        {"SeriesInstanceUID": "123"},
        {"SOPClassInstanceUID": "789"},
        {"min_study_date": datetime(year=2023, month=5, day=29)},
    ],
)
def test_invalid_hierarchical_query(query_params):
    """These queries are invalid, should not pass init validation"""
    with pytest.raises(ValueError):
        HierarchicalQuery(**query_params)


def test_hierarchical_query_uris():
    """Test splitting into uri"""
    query = HierarchicalQuery(
        limit=25,
        min_study_date=datetime(year=2023, month=5, day=29),
        max_study_date=datetime(year=2023, month=5, day=29),
        StudyInstanceUID="123",
        include_fields=["PatientName", "Modality"],
        query_level=QueryLevels.SERIES,
    )

    parameters = query.uri_search_params()
    url = query.uri_base()

    assert len(parameters) == 3
    assert url == "/studies/123/series"


def test_hierarchical_query_uri_suid_only(requests_mock, a_qido):
    """Exposes issue #49 - Query containing SeriesInstanceUID only is not
    translated properly
    """
    # Return a valid response to avoid errors. We're only interested in the called url
    set_mock_response(requests_mock, QIDO_RS_STUDY_LEVEL)

    # Simple query for a single StudyInstanceUID
    a_qido.find_studies(HierarchicalQuery(StudyInstanceUID="123"))

    # This should translate to a qido url call including the StudyInstanceUID
    assert len(requests_mock.request_history) == 1  # sanity check
    assert (
        requests_mock.request_history[0].path
        == "/qido/studies?StudyInstanceUID=123"
    )


@pytest.mark.parametrize(
    "query_params",
    [
        {"query_level": QueryLevels.INSTANCE},
        {"query_level": QueryLevels.INSTANCE, "PatientName": "a name"},
        {"query_level": QueryLevels.SERIES, "PatientName": "a name"},
        {"StudyInstanceUID": "123", "query_level": QueryLevels.INSTANCE},
        {
            "StudyInstanceUID": "123",
            "SeriesInstanceUID": "456",
            "query_level": QueryLevels.SERIES,
        },
        {
            "min_study_date": datetime(year=2023, month=5, day=29),
            "max_study_date": datetime(year=2023, month=5, day=29),
            "query_level": QueryLevels.SERIES,
        },
    ],
)
def test_valid_relational_query(query_params):
    """These queries should not raise any exceptions"""
    assert RelationalQuery(**query_params)  # check for no init exceptions


@pytest.mark.parametrize(
    "query_params",
    [
        {"SeriesInstanceUID": "123"},
        {"SOPClassInstanceUID": "789"},
        {"min_study_date": datetime(year=2023, month=5, day=29)},
    ],
)
def test_invalid_relational_query(query_params):
    """These queries are invalid, should not pass init validation"""
    with pytest.raises(ValueError):
        HierarchicalQuery(**query_params)


@pytest.fixture
def a_qido(a_session) -> QidoRS:
    """QIDO-RS search with faked urls"""
    return QidoRS(session=a_session, url=MockUrls.QIDO_RS_URL)


def test_qido_searcher(requests_mock, a_qido):
    set_mock_response(requests_mock, QIDO_RS_STUDY_LEVEL)
    result = a_qido.find_studies(HierarchicalQuery())
    assert len(result) == 3


def test_qido_searcher_204(requests_mock, a_qido):
    """QIDO-RS servers should return http 204 for queries with 0 results.
    This should be handled without raising exceptions. Recreates issue 47
    """
    set_mock_response(requests_mock, QIDO_RS_204_NO_RESULTS)
    result = a_qido.find_studies(HierarchicalQuery())
    assert len(result) == 0
