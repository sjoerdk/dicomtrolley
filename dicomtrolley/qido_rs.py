"""Models QIDO-RS: Query based on ID for dicom Objects by Restful Services
https://www.dicomstandard.org/using/dicomweb/query-qido-rs/

See
https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.6.html#sect_10.6.1.2
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Union

from pydantic import root_validator
from pydicom import Dataset
from requests import Response

from dicomtrolley.core import (
    Query,
    QueryLevels,
    Searcher,
    Study,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.logging import get_module_logger
from dicomtrolley.parsing import DICOMParseTree

logger = get_module_logger("qido_rs")


class QidoRSQueryBase(Query):
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
        to_str = QidoRSQueryBase.date_to_str

        return f"{to_str(min_date)}-{to_str(max_date)}"

    def uri_base(self) -> str:
        """WADO-RS url to call when performing this query. Full URI also needs
        uri_search_params()

        The non-query part of the URI as defined in
        DICOM PS3.18 section 10.6 table 10.6.1-2
        """
        raise NotImplementedError

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
            "StudyInstanceUID",  # potential part of url, not search params
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


class HierarchicalQuery(QidoRSQueryBase):
    """QIDO-RS Query that uses that traditional study->series->instance structure

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

    def uri_base(self) -> str:
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
        else:
            raise ValueError(
                f'Unknown querylevel "{self.query_level}". '
                f'Should be one of "{QueryLevels}"'
            )


class QidoRS(Searcher):
    """A connection to a QIDO-RS server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged-in session over which WADO calls can be made
        url: str
            QIDO-RS endpoint, including protocol and port. Like
            https://server:8080/qido
        """

        self.session = session
        self.url = url

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

    @classmethod
    def ensure_query_type(cls, query: Query) -> QidoRSQueryBase:
        """Make sure query is of a type usable in this searcher. Cast if needed

        Separate casting method needed in addition to Query.init_from_query()
        To properly handle the two QIDO-RS query types
        """
        if isinstance(query, QidoRSQueryBase):
            return query  # no conversion, just us whatever it was
        elif isinstance(query, Query):
            # Choosing hierarchical over relational here, as the former is
            # more similar to wado-uri/dicom-qr queries and faster as well
            return HierarchicalQuery.init_from_query(query)
        else:
            raise ValueError(
                f'Invalid query. Expecting Query, got "{type(query)}")'
            )

    def find_studies(self, query: Query) -> Sequence[Study]:
        logger.debug(f"Firing query {query}")

        query = self.ensure_query_type(query)
        url = self.url.rstrip("/") + query.uri_base()
        response = self.session.get(url=url, params=query.uri_search_params())

        self.check_for_response_errors(response)
        return self.parse_qido_response(json.loads(response.text))

    @staticmethod
    def parse_qido_response(response: Response) -> List[Study]:
        """Assumes response has been json-decoded

        response could contain instances, series or studies
        """
        tree = DICOMParseTree()
        for item in response:
            tree.insert_dataset(Dataset.from_json(item))

        return tree.as_studies()
