from datetime import datetime

import pytest

from dicomtrolley.core import (
    InstanceReference,
    QueryLevels,
    SeriesReference,
    StudyReference,
)
from dicomtrolley.wado_rs import WadoRS, HierarchicalQuery


@pytest.mark.parametrize(
    "url,reference,result",
    [
        (
            "prot://test/",
            StudyReference(study_uid="1"),
            "prot://test/studies/1",
        ),
        (
            "prot://test/",
            SeriesReference(study_uid="1", series_uid="2"),
            "prot://test/studies/1/series/2",
        ),
        (
            "prot://test/",
            InstanceReference(study_uid="1", series_uid="2", instance_uid="3"),
            "prot://test/studies/1/series/2/instances/3",
        ),
        (
            "prot://test",
            StudyReference(study_uid="1"),
            "prot://test/studies/1",
        ),
    ],
)
def test_generate_uri(url, reference, result):
    a_wado = WadoRS(session=None, url=url)
    assert a_wado.wado_rs_instance_uri(reference) == result


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
