import re
from uuid import uuid4

import pytest
import requests
from jinja2 import Template

from dicomtrolley.core import InstanceReference
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMParseTree
from dicomtrolley.rad69 import (
    HTTPMultiPartStream,
    MultipartContentError,
    Rad69,
)
from dicomtrolley.xml_templates import (
    A_RAD69_RESPONSE_SOAP_HEADER_TEMPLATE,
    RAD69_SOAP_REQUEST_TEMPLATE,
)
from tests.conftest import set_mock_response
from tests.factories import quick_dataset
from tests.mock_responses import (
    MockUrls,
    RAD69_RESPONSE_INVALID_DICOM,
    RAD69_RESPONSE_INVALID_NON_DICOM,
    RAD69_RESPONSE_INVALID_NON_MULTIPART,
    RAD69_RESPONSE_OBJECT_NOT_FOUND,
    create_rad69_response_from_dataset,
    create_rad69_response_from_datasets,
)


@pytest.fixture
def a_rad69(a_session):
    """A basic rad69 module that you can query"""
    return Rad69(session=a_session, url=MockUrls.RAD69_URL)


def test_rad69_get_dataset(a_rad69, requests_mock):
    """Retrieve dicom data via a rad69 call"""
    set_mock_response(
        requests_mock,
        create_rad69_response_from_dataset(
            quick_dataset(PatientName="Jim", StudyDescription="Thing")
        ),
    )

    ds = a_rad69.get_dataset(
        InstanceReference(
            study_instance_uid="1",
            series_instance_uid="2",
            sop_instance_uid="3",
        )
    )

    assert ds.PatientName == "Jim"
    assert ds.StudyDescription == "Thing"


@pytest.mark.parametrize(
    "mock_response, error_contains",
    [
        (RAD69_RESPONSE_INVALID_DICOM, ".*Error parsing response"),
        (RAD69_RESPONSE_INVALID_NON_DICOM, ".*Calling.* failed"),
        (
            RAD69_RESPONSE_INVALID_NON_MULTIPART,
            ".*Expected multipart response",
        ),
        (RAD69_RESPONSE_OBJECT_NOT_FOUND, ".*server returns 2 errors"),
    ],
)
def test_rad69_error_from_server(
    a_rad69, requests_mock, mock_response, error_contains
):
    """Server can return strange invalid dicom-like responses, http error codes
    or errors as in a soap response. Catch these and raise meaningful errors
    """
    set_mock_response(requests_mock, mock_response)

    with pytest.raises(DICOMTrolleyError) as e:
        a_rad69.get_dataset(
            InstanceReference(
                study_instance_uid=1,
                series_instance_uid=2,
                sop_instance_uid=3,
            )
        )
    assert re.match(error_contains, str(e))


def test_rad69_template():
    """Verify that all fields in the main soap template are filled correctly"""
    tree = DICOMParseTree()
    tree.insert(
        data=[],
        study_uid="study1",
        series_uid="series1",
        instance_uid="instance1",
    )
    tree.insert(
        data=[],
        study_uid="study1",
        series_uid="series1",
        instance_uid="instance2",
    )
    tree.insert(
        data=[],
        study_uid="study1",
        series_uid="series2",
        instance_uid="instance1",
    )
    studies = tree.as_studies()
    rendered = Template(RAD69_SOAP_REQUEST_TEMPLATE).render(
        uuid="a_uuid",
        studies=studies,
        transfer_syntax_list=["1.2.840.10008.1.2", "1.2.840.10008.1.2.1"],
    )
    assert "study1" in rendered
    assert "series1" in rendered
    assert "series2" in rendered
    assert "instance1" in rendered
    assert "instance2" in rendered


def test_wado_datasets_async(a_rad69, requests_mock):
    set_mock_response(
        requests_mock,
        create_rad69_response_from_dataset(
            quick_dataset(PatientName="patient1", StudyDescription="a_study")
        ),
    )

    instances = [
        InstanceReference(
            study_instance_uid=1, series_instance_uid=2, sop_instance_uid=3
        ),
        InstanceReference(
            study_instance_uid=4, series_instance_uid=5, sop_instance_uid=6
        ),
    ]

    datasets = [x for x in a_rad69.datasets_async(instances)]
    assert len(datasets) == 2
    assert datasets[0].PatientName == "patient1"
    assert (
        requests_mock.last_request.headers["Content-type"]
        == "application/soap+xml"
    )


def test_wado_datasets_streamed(a_rad69, requests_mock):
    """Handle streamed / chunked response"""
    datasets = [
        quick_dataset(PatientName=f"Patient_{idx}") for idx in range(3)
    ]
    response = create_rad69_response_from_datasets(datasets)
    set_mock_response(requests_mock, response)

    # check with empty call because mock response does not care
    datasets = [x for x in a_rad69.datasets([])]
    assert len(datasets) == 3


@pytest.fixture
def a_rad69_multipart_response(requests_mock):
    """A http multipart response from a rad69 server"""
    datasets = [
        quick_dataset(PatientName=f"Patient_{idx}") for idx in range(3)
    ]
    set_mock_response(
        requests_mock, create_rad69_response_from_datasets(datasets)
    )
    return requests.post(MockUrls.RAD69_URL)


def test_http_multi_part_stream(a_rad69_multipart_response):
    stream = HTTPMultiPartStream(a_rad69_multipart_response)
    parts = [part for part in stream]
    assert len(parts) == 4


@pytest.mark.parametrize("chunk_size", [1, 2, 16, 64, 1024, 271360])
def test_http_multi_part_stream_chunk_size(
    a_rad69_multipart_response, chunk_size
):
    """Different chunk sizes should not affect function"""
    stream = HTTPMultiPartStream(
        a_rad69_multipart_response, stream_chunk_size=chunk_size
    )
    parts = [part for part in stream]
    assert len(parts) == 4


def test_http_multi_part_stream_exceptions(requests_mock):
    """Corrupted datastreams should raise exceptions"""
    datasets = [
        quick_dataset(PatientName=f"Patient_{idx}") for idx in range(3)
    ]
    mock_response = create_rad69_response_from_datasets(datasets)
    content = mock_response.content
    mock_response.content = content[30:]  # missing part of initial boundary
    set_mock_response(requests_mock, mock_response)

    stream = HTTPMultiPartStream(requests.post(MockUrls.RAD69_URL))
    with pytest.raises(MultipartContentError):
        _ = [part for part in stream]


@pytest.mark.parametrize(
    "boundary, byte_stream, part, rest",
    [
        (
            b"--a_boundary123",
            b"--a_boundary123\r\nsome content--a_boundary123andthensome",
            b"\r\nsome content",
            b"--a_boundary123andthensome",
        ),
        (b"--123", b"--123content--123content2", b"content", b"--123content2"),
        (
            b"--123",
            b"--123contentbutnoendboundary",
            b"",
            b"--123contentbutnoendboundary",
        ),
    ],
)
def test_break_off_first_part(boundary, byte_stream, part, rest):
    """Test the function used to break a bytestream into parts"""
    part_out, rest_out = HTTPMultiPartStream.split_off_first_part(
        byte_stream, boundary
    )
    assert part_out == part
    assert rest_out == rest


def test_huge_xml_part(requests_mock, a_rad69):
    """Do things work if the initial xml part to a response is much larger than
    chunk size? Just to be sure
    """

    big_header = Template(A_RAD69_RESPONSE_SOAP_HEADER_TEMPLATE).render(
        dids=list(uuid4() for i in range(7000))
    )
    set_mock_response(
        requests_mock,
        create_rad69_response_from_datasets(
            [quick_dataset(PatientName="Patient_1")], soap_header=big_header
        ),
    )

    sets = list(
        a_rad69.datasets(instances=[])
    )  # mock call does not care about instances
    assert len(sets) == 1
