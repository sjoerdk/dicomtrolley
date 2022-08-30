"""Retrieve data from servers using the rad69 protocol

see https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set
And the corresponding transaction: https://profiles.ihe.net/ITI/TF/Volume2/ITI-43.html
"""

import email.parser
import math
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Sequence, Tuple
from xml.etree import ElementTree

from jinja2.environment import Template
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread
from requests.exceptions import ChunkedEncodingError
from requests.structures import CaseInsensitiveDict
from requests_futures.sessions import FuturesSession
from urllib3.exceptions import ProtocolError

from dicomtrolley.core import Downloader, InstanceReference
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMParseTree
from dicomtrolley.xml_templates import (
    RAD69_SOAP_REQUEST_TEMPLATE,
    RAD69_SOAP_RESPONSE_ERROR_XPATH,
)


class Rad69(Downloader):
    """A connection to a Rad69 server"""

    def __init__(
        self, session, url, http_chunk_size=65536, request_per_series=True
    ):
        """
        Parameters
        ----------
        session: requests.session
            A logged in session over which rad69 calls can be made
        url: str
            rad69 endpoint, including protocol and port. Like https://server:2525/rids
        http_chunk_size: int, optional
            Number of bytes to read each time when streaming chunked rad69 responses.
            Defaults to 64 Kb (65536 bytes)
        request_per_series: bool, optional
            If true, split rad69 requests per series when downloading. If false,
            request all instances at once. Splitting reduces load on server.
            defaults to True.
        """

        self.session = session
        self.url = url
        self.http_chunk_size = http_chunk_size
        self.template = RAD69_SOAP_REQUEST_TEMPLATE
        self.post_headers = {"Content-Type": "application/soap+xml"}
        self.request_per_series = request_per_series

    def datasets(self, instances: Sequence[InstanceReference]):
        """Retrieve all instances by querying rad69 for all in one request

        Returns
        -------
        Iterator[Dataset, None, None]
        """
        if self.request_per_series:
            per_series: Dict[str, List[InstanceReference]] = defaultdict(list)
            for x in instances:
                per_series[x.series_instance_uid].append(x)

        # TODO: create a chained iterator that posts only when needed
        response = self.session.post(
            url=self.url,
            headers=self.post_headers,
            data=self.create_instances_request(instances),
            stream=True,
        )
        return self.parse_rad69_response(response)

    def create_instance_request(self, instance: InstanceReference):
        """Create the SOAP xml structure needed to request an instance from a rad69
        server
        """
        return self.create_instances_request(instances=[instance])

    def create_instances_request(self, instances: Sequence[InstanceReference]):
        """Create the SOAP xml structure to request all given instances from server"""
        # Turn instanceReference list back into study level
        tree = DICOMParseTree()
        for instance in instances:
            tree.insert(
                data=[],
                study_uid=instance.study_instance_uid,
                series_uid=instance.series_instance_uid,
                instance_uid=instance.sop_instance_uid,
            )
        studies = tree.as_studies()

        return Template(self.template).render(
            uuid=str(uuid.uuid4()),
            studies=studies,
            transfer_syntax_list=[
                "1.2.840.10008.1.2.4.70",
                "1.2.840.10008.1.2",
                "1.2.840.10008.1.2.1",
            ],
        )

    def get_dataset(self, instance: InstanceReference):
        """Get DICOM dataset for the given instance (slice)

        Raises
        ------
        DICOMTrolleyError
            If getting does not work for some reason

        Note
        ----
        Getting single datasets is not efficient in rad69. If you want to loop
        this function, use Rad69.datasets() instead

        Returns
        -------
        Dataset
            A pydicom dataset
        """

        response = self.session.post(
            url=self.url,
            headers=self.post_headers,
            data=self.create_instance_request(instance),
        )
        return list(self.parse_rad69_response(response))[0]

    @staticmethod
    def verify_rad69_response(response):
        """Raise exceptions if this response is not a multi-part rad69 soap response.

        Raises
        ------
        DICOMTrolleyError
            If response is not as expected
        """
        if response.status_code != 200:
            raise DICOMTrolleyError(
                f"Calling {response.url} failed ({response.status_code} - "
                f"{response.reason})\n"
                f"response content was {str(response.content[:300])}"
            )

        # check multipart
        if "Content-type" not in response.headers:
            raise DICOMTrolleyError(
                f"Expected multipart response, but got no content type for this"
                f" response. Start of response: {str(response.content[:300])}"
            )

        if "multipart" not in response.headers["Content-Type"].lower():
            # Maybe server is sending back a valid soap error document.
            Rad69.parse_rad69_soap_error_response(response)

    @staticmethod
    def parse_rad69_soap_error_response(response):
        """Interpret response as rad69 error, raise more helpful exceptions

        Raises
        ------
        DICOMTrolleyError
            if this is a valid rad69 error response. Raise nothing otherwise
        """

        tree = ElementTree.fromstring(response.text)
        errors = tree.findall(RAD69_SOAP_RESPONSE_ERROR_XPATH)
        if not errors:
            raise DICOMTrolleyError(
                f"Could not find any rad69 soap errors in "
                f"response: {response.content[:900]}"
            )
        else:
            raise DICOMTrolleyError(
                f"Rad69 server returns {len(errors)} errors:"
                f" {[str(error.attrib) for error in errors]}"
            )

    def parse_rad69_response(self, response):
        """Create a Dataset out of http response from a rad69 server

        Raises
        ------
        DICOMTrolleyError
            If response is not as expected or if parsing fails

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets included in this response
        """
        self.verify_rad69_response(response)
        part_stream = HTTPMultiPartStream(
            response, stream_chunk_size=self.http_chunk_size
        )
        soap_part = None
        for part in part_stream:
            if not soap_part:
                soap_part = part  # skip soap part of the response
                continue
            dicom_bytes = part.content
            raw = DicomBytesIO(dicom_bytes)
            try:
                yield dcmread(raw)
            except InvalidDicomError as e:
                raise DICOMTrolleyError(
                    f"Error parsing response as dicom: {e}."
                    f" Response content (first 300 elements) was"
                    f" {str(response.content[:300])}"
                ) from e

    @staticmethod
    def split_instances(instances: Sequence[InstanceReference], num_bins):
        """Split the given instance references into even piles"""
        bin_size = math.ceil(len(instances) / num_bins)
        for i in range(0, len(instances), bin_size):
            yield instances[i : i + bin_size]

    def datasets_async(
        self, instances: Sequence[InstanceReference], max_workers=4
    ):
        """Split instances into chunks and retrieve each chunk in separate thread

        Parameters
        ----------
        instances: Sequence[InstanceReference]
            Retrieve dataset for each of these instances
        max_workers: int, optional
            Use this number of workers in ThreadPoolExecutor. Defaults to
            default for ThreadPoolExecutor

        Notes
        -----
        rad69 allows any number of slices to be combined in one request. The response
        is a chunked multi-part http response with all image data. Requesting each
        slice individually is inefficient. Requesting all slices in one thread might
        limit speed. Somewhere in the middle seems the best bet for optimal speed.
        This function splits all instances between the available workers and lets
        workers process the response streams.

        Raises
        ------
        DICOMTrolleyError
            When a server response cannot be parsed as DICOM

        Returns
        -------
        Iterator[Dataset, None, None]
        """
        # max_workers=None means let the executor figure it out. But for rad69 we
        # still need to determine how many instances to retrieve at once with each
        # worker. Unlimited workers make no sense here. Just use a single thread.
        if max_workers is None:
            max_workers = 1

        with FuturesSession(
            session=self.session,
            executor=ThreadPoolExecutor(max_workers=max_workers),
        ) as futures_session:
            futures = []
            for instance_bin in self.split_instances(instances, max_workers):
                futures.append(
                    futures_session.post(
                        url=self.url,
                        headers=self.post_headers,
                        data=self.create_instances_request(instance_bin),
                    )
                )

            for future in as_completed(futures):
                yield from self.parse_rad69_response(future.result())


def _split_on_find(content, bound):
    """Split content string on a substring"""
    point = content.find(bound)
    return content[:point], content[point + len(bound) :]


def parse_headers(content, encoding):
    string = content.decode(encoding)
    return email.parser.HeaderParser().parsestr(string).items()


class HTMLPart:
    """One part of a multi-part http response, without the boundaries"""

    def __init__(self, content, encoding):
        if not encoding:
            encoding = "utf-8"
        self.encoding = encoding
        headers = {}
        # Split into header section (if any) and the content
        if b"\r\n\r\n" in content:
            first, self.content = _split_on_find(content, b"\r\n\r\n")
            if first != b"":
                headers = parse_headers(first.lstrip(), encoding)
        else:
            raise MultipartContentError("content does not contain CR-LF-CR-LF")
        self.headers = CaseInsensitiveDict(headers)

    @property
    def text(self):
        return self.content.decode(self.encoding)


class HTTPMultiPartStream:
    """Converts a streamed http multipart response into separate parts.

    Main use is as an iterator:

        parts = [x for x in HTTPMultiPartStream(response)]

    This iterator is stateful and can only be called once as it consumes the
    response stream
    """

    def __init__(self, response, stream_chunk_size=65536):
        self.response = response
        self.boundary = self._find_boundary(response)

        self._bytes_iterator = self.create_bytes_iterator(
            response, stream_chunk_size
        )
        self._buffer = b""

    @staticmethod
    def create_bytes_iterator(response, stream_chunk_size):
        return iter(response.iter_content(chunk_size=stream_chunk_size))

    @staticmethod
    def _split_on_find(content, bound):
        point = content.find(bound)
        return content[:point], content[point + len(bound) :]

    @classmethod
    def _find_boundary(cls, multipart_response):
        content_type_info = tuple(
            x.strip()
            for x in multipart_response.headers.get("content-type").split(";")
        )
        mimetype = content_type_info[0]
        if mimetype.split("/")[0].lower() != "multipart":
            raise MultipartContentError(
                f"Unexpected mimetype in content-type: '{mimetype}'"
            )
        for item in content_type_info[1:]:
            attr, value = cls._split_on_find(item, "=")
            if attr.lower() == "boundary":
                return value.strip('"').encode("utf-8")

    def __iter__(self):
        return self

    def __next__(self):
        # is there a part between two boundaries in current buffer?
        part = self.get_next_part_from_buffer()
        if not part:
            while not part:
                self._buffer = self._buffer + self.read_next_chunk()
                part = self.get_next_part_from_buffer()
        return HTMLPart(part, encoding=self.response.encoding)

    def read_next_chunk(self):
        """Read next chunk of bytes from iterator"""
        try:
            return next(self._bytes_iterator)
        except ChunkedEncodingError as e:
            raise DICOMTrolleyError(str(e)) from e
        except ProtocolError as e:
            raise DICOMTrolleyError(str(e)) from e

    def get_next_part_from_buffer(self):
        """Return first part in buffer and remove this from buffer"""
        part, rest = self.split_off_first_part(
            self._buffer, b"--" + self.boundary
        )
        if part:
            self._buffer = rest
            return part
        else:
            return None

    @staticmethod
    def split_off_first_part(
        bytes_in: bytes, boundary: bytes
    ) -> Tuple[bytes, bytes]:
        """Find the content between two boundaries.
        Expects bytes_in to start with a boundary

        Returns
        -------
        Tuple[bytes, bytes]
            The content found between first two boundaries and the rest. Rest will
            start with a boundary, content found will not, discarding the boundary
            there.
            If no second boundary is found or bytes_in is empty,
            will return Tuple[b'', bytes_in]

        Raises
        ------
        MultipartContentError
            If bytes_in does not start with a boundary
        """
        if not bytes_in:
            return b"", bytes_in  # Avoid exception for valid empty input
        elif len(bytes_in) < len(boundary):
            return b"", bytes_in  # Not enough bytes to find boundary yet
        elif bytes_in.find(boundary) != 0:
            raise MultipartContentError(
                f"Expected http multipart bytestream to start with "
                f"boundary {boundary.decode()}, but found "
                f"{bytes_in[:len(boundary)].decode()}"
            )

        bytes_to_scan = bytes_in[
            len(boundary) :
        ]  # first boundary not needed anymore

        #  find the next boundary
        next_boundary_idx = bytes_to_scan.find(boundary)
        if next_boundary_idx == -1:
            # not found. There is no part here(yet)
            return b"", bytes_in
        else:
            part_bytes = bytes_to_scan[:next_boundary_idx]
            rest = bytes_to_scan[next_boundary_idx:]
            return part_bytes, rest


class MultipartContentError(DICOMTrolleyError):
    pass
