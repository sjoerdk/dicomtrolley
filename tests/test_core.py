from datetime import date, datetime

import pytest
from pydicom.dataset import Dataset

from dicomtrolley.core import (
    ExtendedQuery,
    Instance,
    NonInstanceParameterError,
    Query,
    Series,
    Study,
    StudyReference,
    extract_instances,
)
from dicomtrolley.mint import MintQuery
from tests.factories import InstanceReferenceFactory, quick_image_level_study


@pytest.fixture
def a_study():
    study = Study(uid="stu1", data=Dataset(), series=[])
    series = Series(uid="ser2", data=Dataset(), parent=study, instances=[])
    instance1 = Instance(uid="ins3", data=Dataset(), parent=series)
    instance2 = Instance(uid="ins4", data=Dataset(), parent=series)
    study.series = (series,)
    series.instances = (instance1, instance2)
    return study


def test_object_get(a_study):
    study = a_study
    series = a_study["ser2"]
    instance = a_study["ser2"]["ins3"]

    str(study.reference())
    str(series.reference())
    str(instance.reference())

    assert len(study.all_instances()) == 2
    assert len(series.all_instances()) == 2
    assert len(instance.all_instances()) == 1

    assert str(study) == "Study stu1"
    assert str(series) == "Series ser2"
    assert str(instance) == "Instance ins3"

    assert instance.root().uid == study.uid
    assert series.root().uid == study.uid
    assert study.root().uid == study.uid


def test_object_exceptions(a_study):

    with pytest.raises(KeyError):
        _ = a_study["unknown"]

    with pytest.raises(KeyError):
        _ = a_study["ser2"]["unknown"]


def test_query():
    """Make sure all parameters of a query are checked"""

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
    }

    all_parameters = {**dicom_parameters, **meta_parameters}
    # this should just not raise any validation error
    ExtendedQuery(**all_parameters)


def test_query_to_string(an_extended_query):
    """Test printing query as human-readable"""
    query = Query(PatientName="TestPatient")
    short_string = query.to_short_string()
    assert (
        "ModalitiesInStudy" not in short_string
    )  # empty values should be omitted
    assert (
        "'query_level': 'STUDY'" in short_string
    )  # query level should be string
    assert "TestPatient" in short_string

    # class name should reflect child class
    assert (
        "MintQuery" in MintQuery(AccessionNumber="a_number").to_short_string()
    )


@pytest.mark.parametrize(
    "query_params",
    (
        {
            "query_level": "Unknown_level",
        },
        {"include_fields": ["NotADicomKeyword"]},
    ),
)
def test_query_validation_error(query_params):
    """These queries should fail validation"""
    with pytest.raises(ValueError):
        Query(**query_params)


def test_extract_instances():
    """These extractions should work"""
    assert len(extract_instances([InstanceReferenceFactory()])) == 1
    a_study = quick_image_level_study("123")
    assert len(extract_instances([a_study])) == 18


def test_extract_instances_exceptions(a_study_level_study):
    """These extractions should not work"""
    # cannot use parametrize as I also want to use fixtures
    with pytest.raises(NonInstanceParameterError):
        # A study reference never contains instances
        extract_instances([StudyReference(study_uid="123")])

    with pytest.raises(NonInstanceParameterError):
        # Should raise on any part of input
        extract_instances(
            [InstanceReferenceFactory(), StudyReference(study_uid="123")]
        )

    with pytest.raises(NonInstanceParameterError):
        # A DICOMObject that does not contain full-depth information
        extract_instances(a_study_level_study)
