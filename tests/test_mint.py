from datetime import date, datetime
from xml.etree.ElementTree import Element

import pytest

from dicomtrolley.mint import (
    Mint,
    MintAttribute,
    MintSeries,
    Query,
    QueryLevels,
    parse_attribs,
)
from tests.mockresponses import MockUrls


@pytest.fixture
def a_mint(a_session):
    return Mint(session=a_session, url=MockUrls.MINT_URL)


def test_search_study_level(a_mint, mock_mint_responses):
    """Default query level receives info in study only"""
    response = a_mint.find_studies(query=Query(patientName="B*"))
    assert response[2].series == ()


def test_search_series_level(a_mint, mock_mint_responses):
    """Series query level will populate studies with series"""
    response = a_mint.find_studies(
        query=Query(patientName="B*", queryLevel=QueryLevels.SERIES)
    )
    assert len(response[1].series) == 2


def test_search_instance_level(a_mint, mock_mint_responses):
    """Instance query level returns series per study and also instances per study"""
    response = a_mint.find_studies(
        query=Query(patientName="B*", queryLevel=QueryLevels.INSTANCE)
    )
    assert len(response[0].series[1].instances) == 13


@pytest.mark.parametrize(
    "query_params",
    (
        {
            "minStudyDate": datetime(year=2020, month=3, day=1)
        },  # forgot maxStudyDate
        {
            "maxStudyDate": datetime(year=2020, month=3, day=1)
        },  # forgot minStudyDate
        {
            "minStudyDate": datetime(year=2020, month=3, day=1),
            "maxStudyDate": "not a date object",
        },
        {"includeFields": "not a list"},
        {"includeFields": ["unknown_field"]},
        {
            "includeFields": ["PatientID"],
            "queryLevel": QueryLevels.INSTANCE,
        },  # invalid include for this level
    ),
)
def test_query_validation_error(query_params):
    """These queries should fail validation"""
    with pytest.raises(ValueError):
        Query(**query_params)


@pytest.mark.parametrize(
    "query_params",
    (
        {
            "minStudyDate": datetime(year=2020, month=3, day=1),
            "maxStudyDate": datetime(year=2020, month=3, day=1),
        },
        {"patientID": "Some_name"},
        {"includeFields": ["PatientID"]},
        {"includeFields": ["OperatorsName"], "queryLevel": QueryLevels.SERIES},
    ),
)
def test_query_should_pass(query_params):
    """These queries should pass validation"""
    Query(**query_params)


def test_query_dates():
    """Date parameters should be passed in proper format"""
    query = Query(
        minStudyDate=datetime(year=2019, month=1, day=2),
        maxStudyDate=datetime(year=2020, month=3, day=1),
        patientBirthDate=date(year=1983, month=8, day=11),
    )
    assert query.as_parameters()["minStudyDate"] == "20190102T000000Z"
    assert query.as_parameters()["maxStudyDate"] == "20200301T000000Z"
    assert query.as_parameters()["patientBirthDate"] == "19830811"


def test_parse_attribs_empty_val():
    """Empty dicom tags can be returned without value. This should be OK"""
    series = Element(MintSeries.xml_element)
    series.append(
        Element(
            MintAttribute.xml_element, attrib={"tag": "PatientID", "vr": "PN"}
        )
    )

    assert parse_attribs(element=series).PatientID == ""


def test_study_instance_iterator(
    a_study_with_instances, a_study_without_instances
):

    assert len([x for x in a_study_with_instances.all_instances()]) == 14
    assert len([x for x in a_study_without_instances.all_instances()]) == 0
