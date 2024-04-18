from datetime import datetime, timedelta

import pytest

from dicomtrolley.caching import CachedSearcher, DICOMObjectCache, NodeNotFound
from dicomtrolley.core import Query, QueryLevels
from tests.mock_responses import MINT_SEARCH_MATCH_SUID


def test_object_cache(some_studies):
    """Test basics of cache. Adding and retrieving"""
    cache = DICOMObjectCache()
    a_study = some_studies[0]

    # Nothing has been added yet. Retrieving should fail
    with pytest.raises(NodeNotFound):
        cache.retrieve(a_study.reference())

    # After adding, retrieve should work and fetch the right thing
    cache.add(a_study)
    assert a_study == cache.retrieve(a_study.reference())


def test_object_cache_child_objects(some_studies):
    """If you add a full study, you should be able to retrieve the series from that
    study from cache.
    """
    a_study = some_studies[0]
    cache = DICOMObjectCache(initial_objects=[a_study])

    a_series = a_study.series[0]
    assert a_series == cache.retrieve(a_series.reference())


def test_object_cache_no_unneeded_leaves(some_studies):
    """Checking whether a node exists should not create an empty node there"""

    cache = DICOMObjectCache()
    assert not cache.root.items()

    with pytest.raises(NodeNotFound):
        cache.retrieve(some_studies[0].reference())

    assert not cache.root.items()


def test_object_cache_expiry(some_studies):
    a_study = some_studies[0]
    cache = DICOMObjectCache(initial_objects=[a_study], expiry_seconds=300)

    # item is not expired and can be retrieved
    assert cache.retrieve(a_study.reference())
    # retrieved item is the actual study that was put in
    assert cache.retrieve(a_study.reference()).series[0].instances[2]

    # now its 20 minutes later
    cache.expiry._now = lambda: datetime.utcnow() + timedelta(seconds=600)

    # item should no longer be available
    with pytest.raises(NodeNotFound):
        cache.retrieve(a_study.reference())


def test_cached_searcher_queries(requests_mock, a_cached_searcher):
    """Check caching of calls to find_studies(Query)"""

    searcher, set_time = a_cached_searcher

    assert len(requests_mock.request_history) == 0  # no network calls yet
    assert searcher.find_studies(
        Query(StudyInstanceUID="1000")
    )  # something comes back
    assert len(requests_mock.request_history) == 1  # due to a network call

    # now the result should have been cached
    assert searcher.find_studies(
        Query(StudyInstanceUID="1000")
    )  # something comes back
    assert len(requests_mock.request_history) == 1  # but no more network calls

    set_time(200)  # later, but nothing has expired yet
    # results to other queries are not cached yet so cause network call
    assert searcher.find_studies(Query(StudyInstanceUID="9999"))
    assert len(requests_mock.request_history) == 2

    set_time(
        400
    )  # First query result should have expired so again network call
    assert searcher.find_studies(Query(StudyInstanceUID="1000"))
    assert len(requests_mock.request_history) == 3

    # but other query has not expired, so should not cause network call
    assert searcher.find_studies(Query(StudyInstanceUID="9999"))
    assert len(requests_mock.request_history) == 3


def test_cached_searcher_query_by_id(requests_mock, a_cached_searcher):
    """Check caching for calls to .find_study_by_id(study_id, level)"""
    searcher, set_time = a_cached_searcher

    assert len(requests_mock.request_history) == 0
    assert searcher.find_study_by_id(
        study_uid="1000", query_level=QueryLevels.STUDY
    )
    assert len(requests_mock.request_history) == 1

    assert searcher.find_study_by_id(
        study_uid="1000", query_level=QueryLevels.STUDY
    )
    assert len(requests_mock.request_history) == 1

    set_time(400)
    assert searcher.find_study_by_id(
        study_uid="1000", query_level=QueryLevels.STUDY
    )
    assert len(requests_mock.request_history) == 2


def test_cached_searcher_shared_cache(requests_mock, a_cached_searcher):
    """Methods .find_studies(Query) and  .find_study_by_id(study_id, level) share
    their cache
    """
    searcher, set_time = a_cached_searcher

    assert len(requests_mock.request_history) == 0
    # Query a study at Study level
    assert searcher.find_studies(
        Query(StudyInstanceUID="1000", query_level=QueryLevels.STUDY)
    )
    assert len(requests_mock.request_history) == 1

    # This study should now also be available from cache
    searcher.find_study_by_id(study_uid="1000", query_level=QueryLevels.STUDY)
    assert len(requests_mock.request_history) == 1

    # however, series info is not available, so this should cause another call
    searcher.find_study_by_id(study_uid="1000", query_level=QueryLevels.SERIES)
    assert len(requests_mock.request_history) == 2

    # Even though everything is available, a different query will not use cache.
    # It's beyond scope to parse the semantics of a query
    assert searcher.find_studies(
        Query(StudyInstanceUID="1000", query_level=QueryLevels.SERIES)
    )
    assert len(requests_mock.request_history) == 3


def test_cached_searcher_complex(requests_mock, a_cached_searcher):
    """Cache saves objects as a tree structure. As such it is possible to update
    a leaf without its stem, making the stem expire before the leaf. Handle this.


    """
    searcher, set_time = a_cached_searcher  # default expiry is 300 secs

    # Query a study at full depth.
    assert len(requests_mock.request_history) == 0
    study = searcher.find_study(
        Query(StudyInstanceUID="1000", query_level=QueryLevels.INSTANCE)
    )
    assert len(requests_mock.request_history) == 1
    # This is then saved in cache (no new request)
    assert searcher.find_study(
        Query(StudyInstanceUID="1000", query_level=QueryLevels.INSTANCE)
    )
    assert len(requests_mock.request_history) == 1

    set_time(200)  # later, a single instance is updated
    updated_instance = study.series[1].instances[0]
    searcher.cache.add(updated_instance)

    set_time(400)  # Now everything is expired except for this single instance
    # you can retrieve the instance
    assert searcher.cache.retrieve(updated_instance.reference())
    # but not the expired parent study
    with pytest.raises(NodeNotFound):
        assert searcher.cache.retrieve(study.reference())

    # And trying the query again should send request again
    assert len(requests_mock.request_history) == 1
    assert searcher.find_study(
        Query(StudyInstanceUID="1000", query_level=QueryLevels.INSTANCE)
    )
    assert len(requests_mock.request_history) == 2


def test_mop_up():
    """Odds and ends I would like to just make sure about"""
    cache = DICOMObjectCache()
    with pytest.raises(ValueError):
        cache.to_address("not a ref!")


@pytest.fixture
def a_cached_searcher(requests_mock, a_mint):
    """A cached searcher with working mocked search backend, a 300 second expiry
    and a method to set its now() so you can test expiry
    """

    # set up working response to a call to a_mint
    requests_mock.register_uri(**MINT_SEARCH_MATCH_SUID.as_dict())

    # set up a cache that you can set the current time on
    cache = DICOMObjectCache(expiry_seconds=300)
    now = datetime.now()

    def set_time(secs):
        cache.expiry._now = lambda: now + timedelta(seconds=secs)

    searcher = CachedSearcher(searcher=a_mint, cache=cache)
    return searcher, set_time
