"""Retrieve data from servers using the rad69 protocol

see https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set
And the corresponding transaction: https://profiles.ihe.net/ITI/TF/Volume2/ITI-43.html
"""
import math
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from jinja2.environment import Template
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread
from requests_futures.sessions import FuturesSession
from requests_toolbelt.multipart import decoder

from dicomtrolley.core import Downloader, InstanceReference
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMParseTree
from dicomtrolley.xml_templates import RAD69_SOAP_REQUEST_TEMPLATE


class Rad69(Downloader):
    """A connection to a Rad69 server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged in session over which rad69 calls can be made
        url: str
            rad69 endpoint, including protocol and port. Like https://server:2525/rids
        """

        self.session = session
        self.url = url
        self.template = RAD69_SOAP_REQUEST_TEMPLATE
        self.post_headers = {"Content-Type": "application/soap+xml"}

    def datasets(self, instances: Sequence[InstanceReference]):
        """Retrieve all instances by querying rad69 for all in one request

        Returns
        -------
        Iterator[Dataset, None, None]
        """

        response = self.session.post(
            url=self.url,
            headers=self.post_headers,
            data=self.create_instances_request(instances),
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
            transfer_syntax_list=["1.2.840.10008.1.2", "1.2.840.10008.1.2.1"],
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
    def parse_rad69_response(response):
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
            raise DICOMTrolleyError(
                f"Expected multipart response, but got this content type in "
                f'response: {response.headers["Content-Type"]}'
            )

        multipart_data = decoder.MultipartDecoder.from_response(response)
        # Disregarding soap part. Just data for now
        # soap = multipart_data.parts[0].text
        # TODO: Check this multipart yield better here
        for part in multipart_data.parts[1:]:
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
