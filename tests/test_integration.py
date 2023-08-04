"""Any test that does not belong to a single module

Initially created this to test casting between different query types.
Is casting between queries working as intended? This is slightly murky to me.
Test to clarify
"""
import pytest

from dicomtrolley.core import Query
from dicomtrolley.dicom_qr import DICOMQuery
from dicomtrolley.exceptions import (
    DICOMTrolleyError,
    UnSupportedParameterError,
)
from dicomtrolley.mint import MintQuery
from dicomtrolley.qido_rs import HierarchicalQuery
from tests.conftest import set_mock_response
from tests.mock_servers import MINT_SEARCH_INSTANCE_LEVEL_ANY


def test_mint_from_query(requests_mock, a_mint):
    """Mint find_studies() uses query conversion. Does it pass through special
    parameters correctly?
    """

    # Query.from_basic_query()
    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)

    a_mint.find_studies(MintQuery(limit=10))
    assert requests_mock.request_history[-1].qs.get("limit") == ["10"]
    requests_mock.reset_mock()


def test_dicom_query_mint_cast(requests_mock, a_mint):
    """Feeding one Query type into a different type searcher. Maybe not probable
    but definitely allowed. Does that work?
    """

    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)
    with pytest.raises(DICOMTrolleyError):
        # should fail, casting to mint would lose unsupported StudyID parameter
        a_mint.find_studies(DICOMQuery(StudyID=123))


def test_from_query():
    """Converting between queries should be possible as long as no information is
    lost in the conversion
    """

    # From basic anything should go
    MintQuery.init_from_query(Query(StudyInstanceUID="123"))
    DICOMQuery.init_from_query(Query(StudyInstanceUID="123"))
    HierarchicalQuery.init_from_query(Query(StudyInstanceUID="123"))

    # from mint to dicomqr should work for simple, shared parameters
    DICOMQuery.init_from_query(MintQuery(StudyInstanceUID="123"))

    # but not for mint-specific parameters, as they are not supported in a DICOMQuery
    with pytest.raises(UnSupportedParameterError):
        DICOMQuery.init_from_query(MintQuery(StudyInstanceUID="123", limit=1))

    # Conversion between queries should also work for non-standard parameters
    # StudyDescription is not in Query but is shared between Mint and DICOMQuery
    MintQuery.init_from_query(DICOMQuery(StudyDescription="thing"))
