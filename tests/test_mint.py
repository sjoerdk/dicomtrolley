from datetime import date, datetime
from unittest.mock import Mock
from xml.etree.ElementTree import Element

import pytest

from dicomtrolley.core import Query
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.mint import (
    MintAttribute,
    MintQuery,
    MintSeries,
    QueryLevels,
    parse_attribs,
)
from tests.conftest import set_mock_response
from tests.mock_responses import (
    MINT_SEARCH_ANY,
    MINT_SEARCH_STUDY_LEVEL_ERROR_500,
)


def test_search_study_level(a_mint, mock_mint_responses):
    """Default query level receives info in study only"""
    response = a_mint.find_studies(query=MintQuery(PatientName="B*"))
    assert response[2].series == []


def test_search_series_level(a_mint, mock_mint_responses):
    """Series query level will populate studies with series"""
    response = a_mint.find_studies(
        query=MintQuery(PatientName="B*", query_level=QueryLevels.SERIES)
    )
    assert len(response[1].series) == 2


def test_search_instance_level(a_mint, mock_mint_responses):
    """Instance query level returns series per study and also instances per study"""
    response = a_mint.find_studies(
        query=MintQuery(PatientName="B*", query_level=QueryLevels.INSTANCE)
    )
    assert len(response[0].series[1].instances) == 13


def test_search_error_500(a_mint, requests_mock):
    """Internal errors in the mint server might be communicated by plain html
    instead mint format. This should be handled
    """
    set_mock_response(requests_mock, MINT_SEARCH_STUDY_LEVEL_ERROR_500)
    with pytest.raises(DICOMTrolleyError) as e:
        a_mint.find_studies(query=MintQuery(PatientName="B*"))
    assert "Could not parse" in str(e)


def test_find_study_exception(a_mint, some_mint_studies):
    """Using a find_study query that returns multiple studies is not allowed"""
    a_mint.find_studies = Mock(return_value=some_mint_studies)
    with pytest.raises(DICOMTrolleyError):
        a_mint.find_study(MintQuery())


def test_find_study_with_basic_query(requests_mock, a_mint):
    """Basic query should be converted"""
    params = MINT_SEARCH_ANY.as_dict()
    requests_mock.register_uri(**params)
    a_mint.find_studies(Query(PatientID="test"))


@pytest.mark.parametrize(
    "query_params",
    (
        {
            "min_study_date": datetime(year=2020, month=3, day=1)
        },  # forgot max_study_date
        {
            "max_study_date": datetime(year=2020, month=3, day=1)
        },  # forgot min_study_date
        {
            "min_study_date": datetime(year=2020, month=3, day=1),
            "max_study_date": "not a date object",
        },
        {"include_fields": "not a list"},
        {"include_fields": ["unknown_field"]},
        {
            "include_fields": ["BitsAllocated"],
            "query_level": QueryLevels.STUDY,
        },  # invalid include for this level
    ),
)
def test_query_validation_error(query_params):
    """These queries should fail validation"""
    with pytest.raises(ValueError):
        MintQuery(**query_params)


def test_query_include_fields_validator():
    """Check issue with pydantic validators on inherited classes"""
    with pytest.raises(ValueError):
        MintQuery(
            **{
                "include_fields": "not a list",
                "query_level": QueryLevels.STUDY,
            }
        )


@pytest.mark.parametrize(
    "query_params",
    (
        {
            "min_study_date": datetime(year=2020, month=3, day=1),
            "max_study_date": datetime(year=2020, month=3, day=1),
        },
        {"PatientID": "Some_name"},
        {"include_fields": ["PatientID"]},
        {
            "include_fields": ["OperatorsName"],
            "query_level": QueryLevels.SERIES,
        },
    ),
)
def test_query_should_pass(query_params):
    """These queries should pass validation"""
    MintQuery(**query_params)


def test_query_dates():
    """Date parameters should be passed in proper format"""
    query = MintQuery(
        min_study_date=datetime(year=2019, month=1, day=2),
        max_study_date=datetime(year=2020, month=3, day=1),
        PatientBirthDate=date(year=1983, month=8, day=11),
    )
    assert query.as_parameters()["min_study_date"] == "20190102"
    assert query.as_parameters()["max_study_date"] == "20200301"
    assert query.as_parameters()["PatientBirthDate"] == "19830811"


def test_parse_attribs_empty_val():
    """Empty dicom tags can be returned without value. This should be OK"""
    series = Element(MintSeries.xml_element)
    series.append(
        Element(
            MintAttribute.xml_element, attrib={"tag": "PatientID", "vr": "PN"}
        )
    )

    assert parse_attribs(element=series).PatientID == ""


def test_query_full():
    """Make sure all parameters of a mint query are checked"""
    dicom_parameters = {
        "AccessionNumber": "123",
        "InstitutionName": "Hospital",
        "InstitutionalDepartmentName": "Department",
        "ModalitiesInStudy": "MR*",
        "PatientID": "1234",
        "PatientName": "Patient*",
        "PatientSex": "F",
        "StudyDescription": "A study",
        "StudyInstanceUID": "4567",
    }
    meta_parameters = {
        "query_level": "INSTANCE",
        "PatientBirthDate": date(year=1990, month=1, day=1),
        "min_study_date": datetime(year=2020, month=3, day=1),
        "max_study_date": datetime(year=2020, month=3, day=5),
        "include_fields": ["NumberOfStudyRelatedInstances"],
        "limit": 10,
    }

    all_parameters = {**dicom_parameters, **meta_parameters}
    query = MintQuery(**all_parameters)
    parameters = query.as_parameters()

    # Regular dicom parameters should all have been translated
    for keyword, expected in dicom_parameters.items():
        assert parameters[keyword] == expected

    # meta parameter should have been converted
    assert parameters["min_study_date"] == "20200301"
    assert parameters["max_study_date"] == "20200305"
    assert parameters["QueryLevel"] == "INSTANCE"
    assert "NumberOfStudyRelatedInstances" in parameters["IncludeFields"]


def test_study_instance_iterator(
    a_mint_study_with_instances, a_mint_study_without_instances
):

    assert len([x for x in a_mint_study_with_instances.all_instances()]) == 14
    assert (
        len([x for x in a_mint_study_without_instances.all_instances()]) == 0
    )


def test_study_dump(a_mint_study_with_instances):
    dump = a_mint_study_with_instances.dump_content()
    assert "BEELDENZORG" in dump
    assert "85551.608" in dump
