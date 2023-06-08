"""Models WADO-RS
For download, uses
https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.4.html

For qeueries, uses
https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.6.html#sect_10.6.1.2

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
from datetime import datetime
from itertools import chain
from typing import Dict, Iterator, List, Optional, Sequence, Union

from pydantic import root_validator
from pydicom import Dataset, dcmread
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO

from dicomtrolley.core import (
    DICOMDownloadable,
    DICOMObjectReference,
    Downloader,
    InstanceReference,
    Query,
    QueryLevels,
    Searcher,
    SeriesReference,
    Study,
    StudyReference,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.http import HTTPMultiPartStream
from dicomtrolley.logging import get_module_logger

logger = get_module_logger("wado_rs")


class WadoRSQueryBase(Query):
    """Base query class as defined in DICOM PS3.18 2023b section 8.3.4
    table 8.3.4-1
    """

    limit: int = 0  # How many results to return. 0 = all
    offset: int = 0  # Number of skipped results

    @root_validator()
    def min_max_study_date_xor(cls, values):  # noqa: B902, N805
        """Min and max should both be given or both be empty"""
        min_date = values.get("min_study_date")
        max_date = values.get("max_study_date")
        if min_date and not max_date:
            raise ValueError(
                f"min_study_date parameter was passed"
                f"({min_date}), "
                f"but max_study_date was not. Both need to be given"
            )
        elif max_date and not min_date:
            raise ValueError(
                f"max_study_date parameter was passed ({max_date}), "
                f"but min_study_date was not. Both need to be given"
            )
        return values

    @staticmethod
    def date_to_str(date_in: Optional[datetime]) -> str:
        """Date to WADO-RS URI format"""
        if not date_in:
            return ""
        return date_in.strftime("%Y%m%d")

    @staticmethod
    def date_range_to_str(
        min_date: Optional[datetime], max_date: Optional[datetime]
    ) -> str:
        """String indicating a date or time range following
        https://dicom.nema.org/medical/dicom/current/output/
        chtml/part04/sect_C.2.2.2.5.html

        Notes
        -----
        For wado-rs, both StudyDate=20001012 and StudyDate=20001012-20001012
        denote the same single day. To keep thing simple this function does not
        collapse 20001012-20001012, just leaves it as is
        """
        if not min_date and not max_date:
            raise ValueError("Cannot create a date range without any dates")
        to_str = WadoRSQueryBase.date_to_str

        return f"{to_str(min_date)}-{to_str(max_date)}"

    def as_uri(self):
        raise NotImplementedError


class HierarchicalQuery(WadoRSQueryBase):
    """WADO-RS Query that uses that traditional study->series->instance structure

    Faster, but requires more information and always constrains search
    """

    @root_validator()
    def uids_should_be_hierarchical(cls, values):  # noqa: B902, N805
        """Any object uids passed should conform to study->series->instance"""
        order = ["StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"]

        def assert_parents_filled(a_hierarchy, value_dict):
            """Assert that if a value in hierarchy is filled, its parent is
            filled too
            """
            if len(a_hierarchy) <= 1:  # if there is only one item, this
                return True  # is either fine, or checked in last iteration
            current = a_hierarchy.pop()
            value = value_dict.get(current)
            parent = value_dict.get(a_hierarchy[-1])
            if value and not parent:  # all parents should be filled then
                raise ValueError(
                    f"This query is not hierarchical. {current} "
                    f"(value:{value})is given , but parent, "
                    f"{a_hierarchy[-1]}, is not. Add parent IDs or "
                    f"use a relational Query instead"
                )
            else:
                return assert_parents_filled(a_hierarchy, value_dict)

        assert_parents_filled(order, values)

        return values

    @root_validator()
    def uids_should_match_query_level(cls, values):  # noqa: B902, N805
        """If a query is for instance level, there should be study and series UIDs"""
        query_level = values["query_level"]

        def assert_key_exists(values_in, query_level_in, missing_key_in):
            if not values_in.get(missing_key_in):
                raise ValueError(
                    f'To search at query level "{query_level_in}" '
                    f"you need to supply a {missing_key_in}. Or use "
                    f"a QIDO-RS relational query"
                )

        if query_level == QueryLevels.STUDY:
            pass  # Fine. you can always look for some studies
        elif query_level == QueryLevels.SERIES:
            assert_key_exists(values, query_level, "StudyInstanceUID")
        elif query_level == QueryLevels.INSTANCE:
            assert_key_exists(values, query_level, "SeriesInstanceUID")
            assert_key_exists(values, query_level, "StudyInstanceUID")

        return values

    def uri_base(self):
        """WADO-RS url to call when performing this query. Full URI also needs
        uri_search_params()

        The non-query part of the URI as defined in
        DICOM PS3.18 section 10.6 table 10.6.1-2
        """

        if self.query_level == QueryLevels.STUDY:
            return "/studies"
        elif self.query_level == QueryLevels.SERIES:
            return f"/studies/{self.StudyInstanceUID}/series"
        elif self.query_level == QueryLevels.INSTANCE:
            return (
                f"/studies/{self.StudyInstanceUID}/series/"
                f"{self.SeriesInstanceUID}/instances"
            )

    def uri_search_params(self) -> Dict[str, Union[str, List[str]]]:
        """The search parameter part of the URI as defined in
        DICOM PS3.18 section 10.6 table 10.6.1-2

        Returns
        -------
        Dict[str, Union[str, List[str]]]
            Output that can be fed directly into a requests post request.
            format is param_name:param_value. If param_value is a list, the param
            will be included multiple times.
            See https://docs.python-requests.org/en/latest/user/quickstart/
            #passing-parameters-in-urls

        Notes
        -----
        Will not output any parameters with Null or empty value (bool(value)==False).
        This does not affect query functionality but makes output cleaner in strings
        """
        search_params: Dict[str, Union[str, List[str]]] = {}

        # parse dates
        if self.min_study_date or self.max_study_date:
            search_params["StudyDate"] = self.date_range_to_str(
                self.min_study_date, self.max_study_date
            )
        # parse include fields
        if self.include_fields:
            search_params["includefield"] = self.include_fields

        # now collect all other Query() fields that can be search params
        exclude_fields = {
            "min_study_date",  # addressed above
            "max_study_date",
            "include_fields",
            "StudyInstanceUID",  # part of url, not search params
            "SeriesInstanceUID",
            "SOPClassInstanceUID",
            "query_level",
        }

        other_search_params = {
            key: val
            for key, val in self.dict().items()
            if key not in exclude_fields
        }

        search_params.update(other_search_params)
        return {
            key: val for key, val in search_params.items() if val
        }  # remove empty


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

    def find_studies(self, query: Query) -> Sequence[Study]:
        # generate query url
        # test = 1
        # post
        # parse results
        raise NotImplementedError()

    def find_full_study_by_id(self, study_uid: str) -> Study:
        """Find a single study at image level

        Useful for automatically finding all instances for a study. Meant to be
        implemented in child classes

        Parameters
        ----------
        study_uid: str
            Study to search for

        Returns
        -------
        Study

        Raises
        ------
        DICOMTrolleyError
            If no results or more than one result is returned by query
        """
        raise NotImplementedError()
