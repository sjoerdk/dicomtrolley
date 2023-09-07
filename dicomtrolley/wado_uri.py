"""Models the WADO-uri protocol

[DICOM part18 chapter 9]
(https://dicom.nema.org/medical/dicom/current/output/chtml/part18/chapter_9.html)
"""
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Sequence

from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread
from requests.models import Response
from requests_futures.sessions import FuturesSession

from dicomtrolley.core import (
    DICOMDownloadable,
    Downloader,
    InstanceReference,
    to_instance_refs,
)
from dicomtrolley.exceptions import DICOMTrolleyError


class WadoURI(Downloader):
    """A connection to a WADO-URI server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged in session over which WADO calls can be made
        url: str
            WADO-URI endpoint, including protocol and port. Like
            https://server:8080/wado
        """

        self.session = session
        self.url = url

    @staticmethod
    def to_wado_parameters(instance):
        """WADO url parameters for to retrieve instance

        Returns
        -------
        Dict[str]
            All parameters for a standard WADO get request
        """
        return {
            "requestType": "WADO",
            "studyUID": instance.study_uid,
            "seriesUID": instance.series_uid,
            "objectUID": instance.instance_uid,
            "contentType": "application/dicom",
        }

    @staticmethod
    def parse_wado_response(response: Response) -> Dataset:
        """Create a Dataset out of http response from WADO server

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
        raw = DicomBytesIO(response.content)
        try:
            return dcmread(raw)
        except InvalidDicomError as e:
            raise DICOMTrolleyError(
                f"Error parsing response as dicom: {e}."
                f" Response content (first 300 elements) was"
                f" {str(response.content[:300])}"
            ) from e

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
        return self.parse_wado_response(
            self.session.get(
                self.url, params=self.to_wado_parameters(instance)
            )
        )

    def datasets(self, objects: Sequence[DICOMDownloadable]):
        """Retrieve each instance in objects

        Returns
        -------
        Iterator[Dataset, None, None]

        Raises
        ------
        NonInstanceParameterError
            If objects contain non-instance targets like a StudyInstanceUID.
            wado_uri can only download instances

        """
        instances = to_instance_refs(objects)  # raise exception if needed
        for instance in instances:
            yield self.get_dataset(instance)

    def datasets_async(
        self, objects: Sequence[DICOMDownloadable], max_workers=None
    ):
        """Retrieve each instance via WADO

        Parameters
        ----------
        objects: Sequence[DICOMDownloadable]
            Retrieve dataset for each of these instances
        max_workers: int, optional
            Use this number of workers in ThreadPoolExecutor. Defaults to
            default for ThreadPoolExecutor

        Raises
        ------
        DICOMTrolleyError
            When a server response cannot be parsed as DICOM
        NonInstanceParameterError
            If objects contain non-instance targets like a StudyInstanceUID and
            download can only process Instance targets. See Exception docstring
            for rationale

        Returns
        -------
        Iterator[Dataset, None, None]
        """

        with FuturesSession(
            session=self.session,
            executor=ThreadPoolExecutor(max_workers=max_workers),
        ) as futures_session:
            futures = []
            for instance in objects:
                futures.append(
                    futures_session.get(
                        self.url, params=self.to_wado_parameters(instance)
                    )
                )

            for future in as_completed(futures):
                yield self.parse_wado_response(future.result())
