"""Models WADO-RS

https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.4.html

Notes
-----
Models only the parts of WADO-RS directly related to downloading DICOM image data.
WADO-RS also supports downloading metadata and rendered images, but these are
outside the scope of the dicomtrolley project.

Specifically, from DICOM PS3.18 section 10.4

Download supported by dicomtrolley:
* Instance resources (download all instances)

Download Not Supported by dicomtrolley:
* Metadata resources
* Rendered resources
* Thumbnail resources
* Bulkdata resources
* Pixel Data resources
"""
from itertools import chain
from typing import Iterator, Sequence

from pydicom import Dataset, dcmread
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO

from dicomtrolley.core import (
    DICOMDownloadable,
    DICOMObjectReference,
    Downloader,
    InstanceReference,
    Searcher,
    SeriesReference,
    StudyReference,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.http import HTTPMultiPartStream
from dicomtrolley.logging import get_module_logger

logger = get_module_logger("wado_rs")


class WadoRS(Searcher, Downloader):
    """A connection to a WADO-RS server"""

    def __init__(self, session, url, http_chunk_size=5242880):
        """
        Parameters
        ----------
        session: requests.session
            A logged-in session over which WADO calls can be made
        url: str
            WADO-RS endpoint, including protocol and port. Like
            https://server:8080/wado
        http_chunk_size: int, optional
            Number of bytes to read each time when streaming chunked rad69 responses.
            Defaults to 5MB (5242880 bytes)
        """

        self.session = session
        self.url = url
        self.http_chunk_size = http_chunk_size

    def datasets(self, objects: Sequence[DICOMDownloadable]):
        """Retrieve each instance

        Returns
        -------
        Iterator[Dataset, None, None]

        Raises
        ------
        NonInstanceParameterError
            If objects contain non-instance targets like a StudyInstanceUID and
            download can only process Instance targets. See Exception docstring
            for rationale
        """
        if isinstance(objects, DICOMDownloadable):
            objects = [objects]  # handle passing single object instead of list
        return chain.from_iterable(
            self.download_iterator(obj) for obj in objects
        )

    def download_iterator(self, downloadable: DICOMDownloadable):
        """Perform a wado RS request and iterate over the returned datasets

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets included in the response
        """
        uri = self.wado_rs_instance_uri(downloadable.reference())
        logger.debug(f"Calling {uri}")
        response = self.session.get(
            url=uri,
            stream=True,
        )

        return self.parse(response)

    def parse(self, response) -> Iterator[Dataset]:
        """Extract datasets out of http response from a rad69 server

        Parameters
        ----------
        response:
            A requests response objects, requests with stream=True

        Raises
        ------
        DICOMTrolleyError
            If response is not as expected or if parsing fails

        Returns
        -------
        Iterator[Dataset, None, None]
            All datasets included in this response
        """

        logger.debug("Parsing WADO-RS response")

        self.check_for_response_errors(response)

        part_stream = HTTPMultiPartStream(
            response, stream_chunk_size=self.http_chunk_size
        )
        for part in part_stream:
            raw = DicomBytesIO(part.content)
            try:
                yield dcmread(raw)
            except InvalidDicomError as e:
                raise DICOMTrolleyError(
                    f"Error parsing response as dicom: {e}."
                    f" Response content (first 300 elements) was"
                    f" {str(response.content[:300])}"
                ) from e

    @staticmethod
    def check_for_response_errors(response):
        """Raise exceptions if this response is not a valid WADO-RS response.

        Parameters
        ----------
        response: response
            response as returned from a wado-rs call

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

    def wado_rs_instance_uri(self, reference: DICOMObjectReference):
        """WADO-RS URI to request all instances contained in referenced object"""
        uri = self.url.rstrip(
            "/"
        )  # self.url might or might not have trailing /
        if isinstance(reference, StudyReference):
            return f"{uri}/studies/{reference.study_uid}"
        elif isinstance(reference, SeriesReference):
            return (
                f"{uri}/studies/{reference.study_uid}/series"
                f"/{reference.series_uid}"
            )
        elif isinstance(reference, InstanceReference):
            return (
                f"{uri}/studies/{reference.study_uid}/series"
                f"/{reference.series_uid}/instances/{reference.instance_uid}"
            )
