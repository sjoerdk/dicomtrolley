from datetime import date, datetime

import pytest
from pydicom.dataset import Dataset

from dicomtrolley.core import (
    DICOMObjectReference,
    Instance,
    Query,
    Series,
    Study,
)


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


def test_reference():
    """Incomplete references should yield an error"""
    with pytest.raises(ValueError):
        DICOMObjectReference(study_uid="foo", instance_uid="baz")


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
    Query(**all_parameters)


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
