"""Models the WADO protocol

https://www.dicomstandard.org/dicomweb/retrieve-wado-rs-and-wado-uri/
"""
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Sequence

from pydantic.dataclasses import dataclass
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread
from requests.models import Response
from requests_futures.sessions import FuturesSession

from dicomtrolley.exceptions import DICOMTrolleyException


@dataclass
class InstanceReference:
    """All information needed to download a single slice (SOPInstance) in WADO"""

    study_instance_uid: str
    series_instance_uid: str
    sop_instance_iud: str

    def __str__(self):
        return f"InstanceReference {self.sop_instance_iud}"


class Wado:
    """A connection to a WADO server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged in session over which WADO calls can be made
        url: str
            WADO endpoint, including protocol and port. Like https://server:8080/wado
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
            "studyUID": instance.study_instance_uid,
            "seriesUID": instance.series_instance_uid,
            "objectUID": instance.sop_instance_iud,
            "contentType": "application/dicom",
        }

    @staticmethod
    def parse_wado_response(response: Response) -> Dataset:
        """Create a Dataset out of http response from WADO server

        Raises
        ------
        DICOMTrolleyException
            If response is not as expected or if parsing fails

        Returns
        -------
        Dataset
        """
        if response.status_code != 200:

            raise DICOMTrolleyException(
                f"Calling {response.url} failed ({response.status_code} - "
                f"{response.reason})\n"
                f"response content was {str(response.content[:300])}"
            )
        raw = DicomBytesIO(response.content)
        try:
            return dcmread(raw)
        except InvalidDicomError as e:
            raise DICOMTrolleyException(
                f"Error parsing response as dicom: {e}."
                f" Response content (first 300 elements) was"
                f" {str(response.content[:300])}"
            )

    def get_dataset(self, instance: InstanceReference):
        """Get DICOM dataset for the given instance (slice)

        Raises
        ------
        DICOMTrolleyException
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

    def datasets(self, instances: Sequence[InstanceReference]):
        """Retrieve each instance via WADO

        Returns
        -------
        Iterator[Dataset, None, None]
        """
        for instance in instances:
            yield self.get_dataset(instance)

    def datasets_async(
        self, instances: Sequence[InstanceReference], max_workers=None
    ):
        """Retrieve each instance via WADO

        Parameters
        ----------
        instances: Sequence[InstanceReference]
            Retrieve dataset for each of these instances
        max_workers: int, optional
            Use this number of workers in ThreadPoolExecutor. Defaults to
            default for ThreadPoolExecutor

        Raises
        ------
        DICOMTrolleyException
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
                    futures_session.get(
                        self.url, params=self.to_wado_parameters(instance)
                    )
                )

            for future in as_completed(futures):
                yield self.parse_wado_response(future.result())
