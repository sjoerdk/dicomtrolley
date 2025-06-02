import re
from unittest.mock import Mock

import pytest
from requests_toolbelt import MultipartEncoder

from dicomtrolley.core import (
    InstanceReference,
    SeriesReference,
    StudyReference,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.wado_rs import WadoRS
from tests.conftest import set_mock_response
from tests.factories import create_dicom_bytestream, quick_dataset
from tests.mock_responses import MockResponse, MockUrls


@pytest.fixture
def a_wado_rs(a_session):
    """A basic WADO-RS module that you can query"""
    return WadoRS(session=a_session, url=MockUrls.WADO_RS_URL)


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


def create_wado_rs_response(datasets):
    """A MockResponse that will return bytestream containing datasets to any
    wado-rs call
    """
    bytes_parts = [create_dicom_bytestream(dataset) for dataset in datasets]

    multi_part_soap_response = MultipartEncoder(
        fields=[
            (f"part{idx+1}", ("filename", bytes_part, "application/dicom"))
            for idx, bytes_part in enumerate(bytes_parts)
        ]
    )

    return MockResponse(
        url=re.compile(MockUrls.WADO_RS_URL + ".*"),
        content=multi_part_soap_response.read(),
        method="GET",
        headers={"Content-Type": multi_part_soap_response.content_type},
    )


def test_wado_rs(a_wado_rs, requests_mock):
    """Basic wado rs download should"""
    # calling wado rs will yield a dataset
    response = create_wado_rs_response(
        [
            quick_dataset(PatientName="Patient_1"),
            quick_dataset(PatientName="Patient_2"),
        ]
    )
    set_mock_response(requests_mock, response)
    datasets = list(
        a_wado_rs.datasets(SeriesReference(study_uid="123", series_uid="1234"))
    )
    assert datasets[0].PatientName == "Patient_1"
    assert datasets[1].PatientName == "Patient_2"


def test_wado_rs_ioeror(a_wado_rs, requests_mock, monkeypatch):
    """Pydicom can raise IOError if a valid dicomweb response contains an invalid
    DICOM object. Make sure this is handled. Recreates issue sjoerdk/dicomtrolley#58
    """
    # calling wado rs will yield a dataset
    response = create_wado_rs_response(
        [
            quick_dataset(PatientName="Patient_1"),
        ]
    )
    set_mock_response(requests_mock, response)

    # but trying to read the response will fail becuase the dicom is malformed
    monkeypatch.setattr(
        "dicomtrolley.wado_rs.dcmread", Mock(side_effect=OSError("BAD DICOM"))
    )

    with pytest.raises(DICOMTrolleyError):
        _ = list(
            a_wado_rs.datasets(
                SeriesReference(study_uid="123", series_uid="1234")
            )
        )
