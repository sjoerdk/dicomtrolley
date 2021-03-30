"""Models the WADO protocol

https://www.dicomstandard.org/dicomweb/retrieve-wado-rs-and-wado-uri/
"""
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread


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

    def get_dataset(
        self, study_instance_uid, series_instance_uid, sop_instance_iud
    ):
        """Get all DICOM data the given instance (slice)

        Returns
        -------
        Dataset
            A pydicom dataset
        """

        response = self.session.get(
            self.url,
            params={
                "requestType": "WADO",
                "studyUID": study_instance_uid,
                "seriesUID": series_instance_uid,
                "objectUID": sop_instance_iud,
                "contentType": "application/dicom",
            },
        )
        raw = DicomBytesIO(response.content)
        return dcmread(raw)
