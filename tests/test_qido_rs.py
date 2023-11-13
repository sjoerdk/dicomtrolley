from datetime import datetime

import pytest

from dicomtrolley.core import Query, QueryLevels
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


@pytest.mark.parametrize(
    "query,expected_url",
    [
        # For this basic study-level query suid should be a parameter
        (
            HierarchicalQuery(
                StudyInstanceUID="123", query_level=QueryLevels.STUDY
            ),
            "/qido/studies?StudyInstanceUID=123",
        ),
        # But for series-level query suid becomes part of the path, not parameter
        (
            HierarchicalQuery(
                StudyInstanceUID="123", query_level=QueryLevels.SERIES
            ),
            "/qido/studies/123/series",
        ),
    ],
)
def test_hierarchical_query_uri_suid_only(
    requests_mock, a_qido, query, expected_url
):
    """Exposes issue #49 - Query containing SeriesInstanceUID only is not
    translated properly. This test check more broadly how hierarchical queries
    generate they urls to make sure this is sane.
    """
    # Return a valid response to avoid errors. We're only interested in the called url
    set_mock_response(requests_mock, QIDO_RS_STUDY_LEVEL)

    # Simple query for a single StudyInstanceUID
    a_qido.find_studies(query)

    # This should translate to a qido url call including the StudyInstanceUID
    hist = requests_mock.request_history
    assert len(hist) == 1  # sanity check
    called = hist[0].path
    if hist[0].query:
        called = called + "?" + hist[0].query
    assert called.lower() == expected_url.lower()


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


def test_ensure_query_type(a_qido):
    """Exposes bug where Series level Relational query calles a study url"""
    ensured = a_qido.ensure_query_type(
        Query(AccessionNumber="123", query_level=QueryLevels.SERIES)
    )
    assert ensured.uri_base() == "/series"
