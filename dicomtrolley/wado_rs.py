"""Models WADO-RS

https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.4.html

Notes
-----
Models only the parts of WADO-RS directly related to downloading DICOM image data.
WADO-RS also supports downloading metadata and rendered images, but these are
outside the scope of the dicomtrolley project
"""
from dicomtrolley.core import Downloader, Searcher


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
