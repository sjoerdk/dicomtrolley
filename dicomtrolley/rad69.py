"""Retrieve data from servers using the rad69 protocol

see https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set
And the corresponding transaction: https://profiles.ihe.net/ITI/TF/Volume2/ITI-43.html
"""

import math
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import chain
from typing import Dict, List, Sequence
from xml.etree import ElementTree

from jinja2.environment import Template
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread
from requests_futures.sessions import FuturesSession

from dicomtrolley.core import (
    DICOMDownloadable,
    Downloader,
    InstanceReference,
    extract_instances,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.http import HTTPMultiPartStream
from dicomtrolley.logging import get_module_logger
from dicomtrolley.parsing import DICOMParseTree
from dicomtrolley.xml_templates import (
    RAD69_SOAP_REQUEST_TEMPLATE,
    RAD69_SOAP_RESPONSE_ERROR_XPATH,
)

logger = get_module_logger("rad69")


class Rad69(Downloader):
    """A connection to a Rad69 server"""

    def __init__(
        self,
        session,
        url,
        http_chunk_size=5242880,
        request_per_series=True,
        errors_to_ignore=None,
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
            Defaults to 5MB (5242880 bytes)
        request_per_series: bool, optional
            If true, split rad69 requests per series when downloading. If false,
            request all instances at once. Splitting reduces load on server.
            defaults to True.
        errors_to_ignore: List[Type], optional
            Errors of this type encountered during download are caught and skipped.
            Defaults to empty list, meaning any error is propagated
        """

        self.session = session
        self.url = url
        self.http_chunk_size = http_chunk_size
        if errors_to_ignore is None:
            errors_to_ignore = []
        self.errors_to_ignore = errors_to_ignore
        self.template = RAD69_SOAP_REQUEST_TEMPLATE
        self.post_headers = {"Content-Type": "application/soap+xml"}
        self.request_per_series = request_per_series

    def datasets(self, objects: Sequence[DICOMDownloadable]):
        """Retrieve all instances via rad69

        A Rad69 request typically contains multiple instances. The data for all
        instances is then streamed back as one multipart http response

        Raises
        ------
        NonInstanceParameterError
            If objects contain non-instance targets like a StudyInstanceUID.
            Rad69 can only download instances

        Returns
        -------
        Iterator[Dataset, None, None]
        """
        instances = extract_instances(objects)  # raise exception if needed
        logger.info(f"Downloading {len(instances)} instances")
        if self.request_per_series:
            per_series: Dict[str, List[InstanceReference]] = defaultdict(list)
            for x in instances:
                per_series[x.series_uid].append(x)
            logger.info(
                f"Splitting per series. Found {len(per_series)} series"
            )
            return chain.from_iterable(
                self.series_download_iterator(x, index)
                for index, x in enumerate(per_series.values())
            )

        else:
            return self.download_iterator(instances)

    def series_download_iterator(
        self, instances: Sequence[InstanceReference], index=0
    ):
        """Identical to create_download_iterator, except adds a debug log call"""
        if instances:
            logger.debug(
                f"Downloading series {index}: " f"{instances[0].series_uid}"
            )
        return self.download_iterator(instances)

    def download_iterator(self, instances: Sequence[InstanceReference]):
        """Perform a rad69 request and iterate over the returned datasets

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets included in the response
        """
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
                study_uid=instance.study_uid,
                series_uid=instance.series_uid,
                instance_uid=instance.instance_uid,
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

    def verify_response(self, response):
        """Check for errors in rad69 response and handle them"""

    @staticmethod
    def check_for_response_errors(response):
        """Raise exceptions if this response is not a multi-part rad69 soap response.

        Parameters
        ----------
        response: response
            response as returned from a rad69 call

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
        XDSMissingDocumentError:
            If data for any requested id could not be found
        Rad69ServerError
            For any unspecified but valid rad69 error response
        DICOMTrolleyError
            if this is not a valid rad69 error response.

        Notes
        -----
        This just pragmatically interprets the first error returned and assumes the
        rest are the same. Not quite right but let's not overdo it.
        """

        tree = ElementTree.fromstring(response.text)
        errors = tree.findall(RAD69_SOAP_RESPONSE_ERROR_XPATH)
        if not errors:
            raise DICOMTrolleyError(
                f"Could not find any rad69 soap errors in "
                f"response: {response.content[:900]}"
            )

        error_code = errors[0].attrib.get("errorCode")
        error_text = (
            f"Server returns {len(errors)} errors. "
            f"First error: {str(errors[0].attrib)}"
        )
        if error_code == "XDSMissingDocument":
            raise XDSMissingDocumentError(error_text)
        else:
            raise Rad69ServerError(error_text)

    def parse_rad69_response(self, response):
        """Extract datasets out of http response from a rad69 server

        Raises
        ------
        DICOMTrolleyError
            If response is not as expected or if parsing fails

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets included in this response
        """
        logger.debug("Parsing rad69 response")
        try:
            self.check_for_response_errors(response)
        except DICOMTrolleyError as e:
            self.handle_response_error(e)  # might re-raise
            return None  # error not re-raised. Skip this response # noqa

        part_stream = HTTPMultiPartStream(
            response, stream_chunk_size=self.http_chunk_size
        )
        soap_part = None
        for part in part_stream:
            if not soap_part:
                logger.debug("Discarding initial rad69 soap part")
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

    def handle_response_error(self, error):
        """Handle exceptions raised during rad69 request or download"""
        if any(issubclass(type(error), x) for x in self.errors_to_ignore):
            logger.warning(f"Ignoring error on ignore list: {str(error)}")
            return None
        else:
            raise error

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


class Rad69ServerError(DICOMTrolleyError):
    """Represents a valid error response from a rad69 server"""

    pass


class XDSMissingDocumentError(Rad69ServerError):
    """Some requested ID could not be found on the server"""

    pass
