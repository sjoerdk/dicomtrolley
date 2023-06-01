"""Models WADO-RS

https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.4.html

Notes
-----
Models only the parts of WADO-RS directly related to downloading DICOM image data.
WADO-RS also supports downloading metadata and rendered images, but these are
outside the scope of the dicomtrolley project
"""
from typing import Sequence

from dicomtrolley.core import DICOMDownloadable, Downloader, Searcher


class WadoRS(Searcher, Downloader):
    """A connection to a WADO-RS server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged-in session over which WADO calls can be made
        url: str
            WADO-RS endpoint, including protocol and port. Like
            https://server:8080/wado
        """

        self.session = session
        self.url = url

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
        # do a post for each element
        # test = 1

        # capture response and start yielding from it

        pass
