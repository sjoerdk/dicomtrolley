"""Retrieve data from servers using the rad69 protocol

see https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set
And the corresponding transaction: https://profiles.ihe.net/ITI/TF/Volume2/ITI-43.html
"""
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

    def create_instance_request(self, instance: InstanceReference):
        """Create the SOAP xml structure needed to request an instance from a rad69
        server
        """
        return Template(self.template).render(
            uuid=str(uuid.uuid4()),
            series_instance_uid=instance.series_instance_uid,
            study_instance_uid=instance.study_instance_uid,
            sop_instance_uid=instance.sop_instance_uid,
            transfer_syntax_list=["1.2.840.10008.1.2", "1.2.840.10008.1.2.1"],
        )

    def get_dataset(self, instance: InstanceReference):
        """Get DICOM dataset for the given instance (slice)

        Raises
        ------
        DICOMTrolleyError
            If getting does not work for some reason

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
        return self.parse_rad69_response(response)

    @staticmethod
    def parse_rad69_response(response):
        """Create a Dataset out of http response from a rad69 server

        Raises
        ------
        DICOMTrolleyError
            If response is not as expected or if parsing fails

        Returns
        -------
        Dataset
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
        dicom_bytes = multipart_data.parts[1].content
        raw = DicomBytesIO(dicom_bytes)
        try:
            return dcmread(raw)
        except InvalidDicomError as e:
            raise DICOMTrolleyError(
                f"Error parsing response as dicom: {e}."
                f" Response content (first 300 elements) was"
                f" {str(response.content[:300])}"
            ) from e

    def datasets_async(
        self, instances: Sequence[InstanceReference], max_workers=None
    ):
        """Retrieve each instance via rad69, in separate threads

        Parameters
        ----------
        instances: Sequence[InstanceReference]
            Retrieve dataset for each of these instances
        max_workers: int, optional
            Use this number of workers in ThreadPoolExecutor. Defaults to
            default for ThreadPoolExecutor

        Raises
        ------
        DICOMTrolleyError
            When a server response cannot be parsed as DICOM

        Returns
        -------
        Iterator[Dataset, None, None]
        """

        with FuturesSession(
            session=self.session,
            executor=ThreadPoolExecutor(max_workers=max_workers),
        ) as futures_session:
            futures = []
            for instance in instances:
                futures.append(
                    futures_session.post(
                        url=self.url,
                        headers=self.post_headers,
                        data=self.create_instance_request(instance),
                    )
                )

            for future in as_completed(futures):
                yield self.parse_rad69_response(future.result())
