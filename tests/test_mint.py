from datetime import date, datetime
from unittest.mock import Mock
from xml.etree.ElementTree import Element

import pytest

from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.mint import (
    MintAttribute,
    MintQuery,
    MintSeries,
    QueryLevels,
    parse_attribs,
)
from tests.conftest import set_mock_response
from tests.mock_responses import MINT_SEARCH_STUDY_LEVEL_ERROR_500


def test_search_study_level(a_mint, mock_mint_responses):
    """Default query level receives info in study only"""
    response = a_mint.find_studies(query=MintQuery(patientName="B*"))
    assert response[2].series == []


def test_search_series_level(a_mint, mock_mint_responses):
    """Series query level will populate studies with series"""
    response = a_mint.find_studies(
        query=MintQuery(patientName="B*", queryLevel=QueryLevels.SERIES)
    )
    assert len(response[1].series) == 2


def test_search_instance_level(a_mint, mock_mint_responses):
    """Instance query level returns series per study and also instances per study"""
    response = a_mint.find_studies(
        query=MintQuery(patientName="B*", queryLevel=QueryLevels.INSTANCE)
    )
    assert len(response[0].series[1].instances) == 13


def test_search_error_500(a_mint, requests_mock):
    """Internal errors in the mint server might be communicated by plain html
    instead mint format. This should be handled
    """
    set_mock_response(requests_mock, MINT_SEARCH_STUDY_LEVEL_ERROR_500)
    with pytest.raises(DICOMTrolleyError) as e:
        a_mint.find_studies(query=MintQuery(patientName="B*"))
    assert "Could not parse" in str(e)


def test_find_study_exception(a_mint, some_studies):
    """Using a find_study query that returns multiple studies is not allowed"""
    a_mint.find_studies = Mock(return_value=some_studies)
    with pytest.raises(DICOMTrolleyError):
        a_mint.find_study(MintQuery())


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
            "includeFields": ["BitsAllocated"],
            "queryLevel": QueryLevels.STUDY,
        },  # invalid include for this level
    ),
)
def test_query_validation_error(query_params):
    """These queries should fail validation"""
    with pytest.raises(ValueError):
        MintQuery(**query_params)


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
    MintQuery(**query_params)


def test_query_dates():
    """Date parameters should be passed in proper format"""
    query = MintQuery(
        minStudyDate=datetime(year=2019, month=1, day=2),
        maxStudyDate=datetime(year=2020, month=3, day=1),
        patientBirthDate=date(year=1983, month=8, day=11),
    )
    assert query.as_parameters()["minStudyDate"] == "20190102"
    assert query.as_parameters()["maxStudyDate"] == "20200301"
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


def test_study_dump(a_study_with_instances):
    dump = a_study_with_instances.dump_content()
    assert "BEELDENZORG" in dump
    assert "85551.608" in dump
