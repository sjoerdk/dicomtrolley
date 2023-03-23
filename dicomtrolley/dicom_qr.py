"""Implements DICOM QR (Query Retrieve), a method for getting information from a VNA

See http://dicom.nema.org/dicom/2013/output/chtml/part04/sect_C.3.html
"""

from typing import Dict, List

from pydicom.datadict import tag_for_keyword
from pydicom.dataset import Dataset
from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind

from dicomtrolley.core import Query, QueryLevels, Searcher, Study
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMParseTree


class QueryRetrieveLevels:
    """Valid values for DICOMQR. Differs slightly from the MINT version."""

    STUDY = "STUDY"
    SERIES = "SERIES"
    IMAGE = "IMAGE"

    ALL = {STUDY, SERIES, IMAGE}

    @classmethod
    def translate(cls, value):
        """Translate from base levels. For converting between queries"""
        translation = {
            QueryLevels.STUDY: cls.STUDY,
            QueryLevels.SERIES: cls.SERIES,
            QueryLevels.INSTANCE: cls.IMAGE,
        }
        return translation[value]


class DICOMQuery(Query):
    """Things you can search for with DICOM QR.

    Notes
    -----
    * Incomplete: this class implements only a minimal core of DICOM QR search.
      It can be extended should the need arise
    * All string arguments support (*) as a wildcard
    * non-pep8 parameter naming format follows DICOM parameter convention.
      Other parameters match MINTQuery conventions, query parameters are similar.

    """

    Modality: str = ""
    ProtocolName: str = ""
    StudyID: str = ""

    class Config:
        extra = "forbid"  # raise ValueError when passing an unknown keyword to init

    @staticmethod
    def get_default_include_fields(query_level):
        """Include fields you definitely want to get back"""
        if query_level == QueryRetrieveLevels.STUDY:
            return ["StudyInstanceUID"]
        elif query_level == QueryRetrieveLevels.SERIES:
            return ["StudyInstanceUID", "SeriesInstanceUID"]
        elif query_level == QueryRetrieveLevels.IMAGE:
            return ["StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"]

    @staticmethod
    def parse_date(date):
        if date:
            return date.strftime("%Y%m%d")
        else:
            return ""

    @classmethod
    def get_study_date(cls, min_study_date, max_study_date):
        """Get value for CFIND parameter StudyDate"""
        min_sd = cls.parse_date(min_study_date)
        max_sd = cls.parse_date(max_study_date)
        if min_sd or max_sd:
            return min_sd + "-" + max_sd
        else:
            return None

    def as_parameters(self) -> Dict[str, str]:
        """Parameters that can be used in constructing a DICOM QR query"""

        # remove non-DICOM parameters and replace with DICOM tags based on them
        parameters = {
            x: y for x, y in self.dict().items()
        }  # all params for query
        parameters["StudyDate"] = self.get_study_date(
            parameters.pop("min_study_date"), parameters.pop("max_study_date")
        )

        # translate values and change parameter name to fit DICOM-QR naming
        parameters["QueryRetrieveLevel"] = QueryRetrieveLevels.translate(
            parameters.pop("query_level")
        )

        # add useful default include fields
        default_fields = self.get_default_include_fields(
            parameters["QueryRetrieveLevel"]
        )
        parameters["include_fields"] = list(
            set(parameters["include_fields"]) | set(default_fields)
        )

        return parameters

    def as_dataset(self):
        """A dataset that can be used as a CFIND query."""
        parameters = self.as_parameters()
        ds = Dataset()
        # in CFIND, empty elements are interpreted as 'need to be returned filled'
        for field in parameters.pop(
            "include_fields"
        ):  # for each include field
            if tag_for_keyword(field):
                setattr(ds, field, "")  # add an empty DICOM element
        parameters = {
            x: y for x, y in parameters.items() if y
        }  # Skip None values

        for parameter, value in parameters.items():
            setattr(ds, parameter, value)

        return ds


class DICOMQR(Searcher):
    """A connection to a DICOM QR enabled server."""

    def __init__(
        self, host, port, aet="DICOMTROLLEY", aec="ANY-SCP", debug=False
    ):
        """

        Parameters
        ----------
        host: str
            Hostname of DICOM-QR-enabled server
        port: int
            Port for DICOM-QR
        aet: str, optional
            Application Entity Title - Name of the calling entity (this class).
            Defaults to 'DICOMTROLLEY'
        aec: str, optional
            Application Entity Called - The name of the server you are calling.
            Defaults to 'ANY-SCP'
        debug: bool, optional
            If True, prints debug logging to console. This can be very useful as
            exceptions often do not contain detailed information.
        """
        self.host = host
        self.port = port
        self.aet = aet
        self.aec = aec
        self.debug = debug

    def find_studies(self, query: Query):
        """

        Parameters
        ----------
        query: Query
            Find arguments matching this query

        Raises
        ------
        DICOMTrolleyError
            When finding fails

        Returns
        -------
        List[Study]
        """
        return self.parse_c_find_response(
            self.send_c_find(DICOMQuery.from_query(query))
        )

    @staticmethod
    def parse_c_find_response(responses) -> List[Study]:
        """Parse flat list of datasets from CFIND into a study/series/instance tree

        CFIND returns a flat list of datasets on the queries' QueryRetrieveLevel.
        For instance at IMAGE level, there is one dataset for each matching instance.
        Each dataset should contain Series and Study information. Parse this into a
        dicomtrolley study/series/instance tree that can be used as input for
        download functions

        Parameters
        ----------
        responses: Sequence[Dataset]
            Datasets coming from a pydicom cfind query

        Returns
        -------
        List[Study]
            Each study populated with series and instance objects, if provided
        """

        tree = DICOMParseTree()
        for response in responses:
            tree.insert_dataset(response)
        return tree.as_studies()

    def send_c_find(self, query):
        """Perform a CFIND with the given query

        Raises
        ------
        DICOMTrolleyError
            When finding fails
        """
        if self.debug:
            debug_logger()
        ae = AE(ae_title=bytes(self.aet, encoding="utf-8"))
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        assoc = ae.associate(
            self.host, self.port, ae_title=bytes(self.aec, encoding="utf-8")
        )
        responses = []
        if assoc.is_established:
            # Send the C-FIND request
            c_find_response = assoc.send_c_find(
                query.as_dataset(),
                StudyRootQueryRetrieveInformationModelFind,
            )
            for (status, identifier) in c_find_response:
                if status:
                    # I don't understand this status. For now just collect non-None
                    if identifier:
                        responses.append(identifier)

                else:
                    raise DICOMTrolleyError(
                        "Connection timed out, was aborted or"
                        " received invalid response"
                    )

            assoc.release()
        else:
            raise DICOMTrolleyError(
                "Association rejected, aborted or never connected"
            )

        return responses

    def find_full_study_by_id(self, study_uid: str) -> Study:
        return self.find_study(
            DICOMQuery(
                StudyInstanceUID=study_uid,
                query_level=QueryLevels.INSTANCE,
            )
        )
