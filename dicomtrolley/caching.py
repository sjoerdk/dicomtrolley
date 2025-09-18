"""Storing DICOM query results locally to avoid unneeded calls to server"""

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from dicomtrolley.core import (
    DICOMObject,
    DICOMObjectLevels,
    DICOMObjectReference,
    InstanceReference,
    Query,
    QueryLevels,
    Searcher,
    SeriesReference,
    Study,
    StudyReference,
)
from dicomtrolley.datastructures import (
    ExpiringCollection,
    TreeAddress,
    TreeNode,
)
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.logs import get_module_logger

logger = get_module_logger("caching")


class DICOMObjectCache:
    def __init__(
        self,
        initial_objects: Optional[List[DICOMObject]] = None,
        expiry_seconds: Optional[int] = 600,
    ):
        """A tree holding expiring DICOM objects. Objects can be retrieved by
        study/series/instance UID tuples:

        >>>cache = DICOMObjectCache()
        >>>cache.add(a_study)    # with uid 'study1' and full series and instance info
        >>>cache.retrieve(reference=('study1','series'))
        <Series>
        >>>cache.retrieve(reference=('study1','series','instance'))
        <Instance>
        # 20 minutes later... study has expired
        >>>cache.retrieve(reference=('study1','series'))
        <NodeNotFound "Data for study1,series1 is not cached">

        Parameters
        ----------
        initial_objects, optional
            Shorthand for add() on all objects in this list. Defaults to empty

        expiry_seconds, optional
            Expire objects after this many seconds. If set to None, will disable
            expiry. Defaults to 600 (10 minutes)

        Notes
        -----
        The functionality here is similar to dicomtrolley.parsing.TreeNode, but the
        use case is different enough to warrant a separate class I think

        """
        if expiry_seconds is None:
            self.expiry = None
        else:
            self.expiry = ExpiringCollection(
                expire_after_seconds=expiry_seconds
            )
        self.root = TreeNode()
        self._awaiting_prune: List[TreeAddress] = []
        if initial_objects:  # not none or empty:
            if not isinstance(initial_objects, list):
                raise ValueError(
                    f"Expected list but got {initial_objects}. Did you"
                    f"forget [braces] for initial_objects value?"
                )
            for x in initial_objects:
                self.add(x)

    def add_all(self, objects: Iterable[DICOMObject]):
        if isinstance(objects, DICOMObject):
            # This mistake is common (for me) and causes unreadable errors. Avoid.
            raise ValueError(
                "parameter 'objects' should be an iterable of "
                "DICOMObjects, not a single object"
            )
        self.prune_expired()
        for obj in objects:
            self.add(obj, prune=False)

    def add(self, obj: DICOMObject, prune=True):
        """Add this object to cache

        Returns
        -------
        The input DICOMObject. Just so you can add and return a value in a single
        line in calling code. Like new_dicom = cache.add(get_new_dicom())
        """
        logger.debug(f"Adding to cache: {obj}")
        if prune:
            self.prune_expired()
        address = self.to_address(obj.reference())
        self.root.add(obj, address=address)
        if self.expiry:
            self.expiry.add(address)

        if obj.children():
            for x in obj.children():
                self.add(
                    x, prune=False
                )  # avoid too many calls to prune_expired

    def retrieve(self, reference: DICOMObjectReference):
        """Try to retrieve object from cache

        Parameters
        ----------
        reference
            The dicom object you would like to retrieve

        Raises
        ------
        NodeNotFound
            If the object does not exist in cache or has expired

        Returns
        -------
        DICOMObject
            The cached object
        """
        self.prune_expired()
        try:
            data = self.root.get_node(
                self.to_address(reference), create=False
            ).data
            if data:
                return data
            else:
                raise NodeNotFound(
                    f"Node found in cache, but no data for reference "
                    f"{reference}"
                )
        except KeyError as e:
            raise NodeNotFound(
                f"No node found in cache for reference {reference}"
            ) from e

    def prune_expired(self):
        """Remove all expired nodes"""
        if not self.expiry:
            logger.debug("prune: not pruning as self.expiry = False")
            return  # don't do anything
        expired = self.expiry.collect_expired()
        self._awaiting_prune = self._awaiting_prune + expired
        self._awaiting_prune.sort(key=lambda x: len(x))
        prune_later = []
        pruned = []
        while self._awaiting_prune:
            address = self._awaiting_prune.pop()  # work from last
            try:
                self.root.prune_leaf(address)
                pruned.append(address)
            except ValueError:
                #  was not a leaf. Make empty and save for later
                self.root.get_node(address).data = None
                prune_later.append(address)
        if pruned:
            msg = f"prune: Pruned away {len(pruned)} leaves: ({pruned})"
            if prune_later:
                msg += f"could not prune {len(prune_later)}. Leaving those for later"
            logger.debug(msg)

        self._awaiting_prune = prune_later

    @staticmethod
    def to_address(ref: DICOMObjectReference) -> TreeAddress:
        """Convert reference to address that can be used in TreeNode"""
        if isinstance(ref, StudyReference):
            return (ref.study_uid,)
        elif isinstance(ref, SeriesReference):
            return ref.study_uid, ref.series_uid
        elif isinstance(ref, InstanceReference):
            return ref.study_uid, ref.series_uid, ref.instance_uid
        else:
            raise ValueError(f"Expected DICOM object reference, but got {ref}")


class QueryCache:
    """Caches the response to DICOM queries"""

    def __init__(self, cache: DICOMObjectCache):
        self.cache = cache
        self.queries: Dict[str, Tuple[DICOMObjectReference, ...]] = {}

    def add_response(self, query: Query, response: Sequence[DICOMObject]):
        """Cache response for this query"""
        self.cache.add_all(response)
        references = tuple(x.reference() for x in response)
        self.queries[query.model_dump_json()] = references

    def get_response(self, query: Query) -> List[Study]:
        """Obtain cached response for this query

        Raises
        ------
        NodeNotFound
            If any of the results of query are not in cache or have expired
        """
        try:
            references = self.queries[query.model_dump_json()]
        except KeyError as e:
            raise NodeNotFound(
                f"Query {query.to_short_string()} not found in cache"
            ) from e

        try:
            retrieved = [self.cache.retrieve(x) for x in references]
            logger.debug(
                f"Found all ({len(retrieved)}) objects in cache for "
                f"{query.to_short_string()}. Returning."
            )
            return retrieved
        except NodeNotFound as e:
            # This query response is not (fully) cached anymore. Remove
            self.queries.pop(query.model_dump_json())
            raise NodeNotFound(
                f"One or more response to {query.to_short_string()} "
                f"was not in cache"
            ) from e


class CachedSearcher(Searcher):
    """A cache wrapped around a Searcher instance. Serves search responses from
    cache first. Calls searcher if needed.

    Caches two types of searcher method calls:
    find_studies(Query):
        Caches each returned DICOM object individually and then associates this
        with the incoming query. Only if the query matches exactly is a cached
        response returned.
        Associates DICOM tree address (study/series/instance). Not DICOM object
        identities. This means that an underlying DICOM object can be updated without
        invalidating the cache response. The cached response to a query will be
        returned as long as there are non-expired cached objects at each associated
        tree address

    find_study_by_id(study_id, level):
        Retrieves study_id from cache and checks whether it has children up to
        the required level (depth).

    """

    def __init__(self, searcher: Searcher, cache: DICOMObjectCache):
        self.searcher = searcher
        self.cache = cache
        self.query_cache = QueryCache(cache=cache)

    def __str__(self):
        return f"CachedSearcher for {self.searcher}"

    def find_studies(self, query: Query) -> Sequence[Study]:
        """Try to return from cache, otherwise call searcher."""
        try:
            return self.query_cache.get_response(query)
        except NodeNotFound:
            logger.debug(
                f"No cache for {query.to_short_string()}."
                f"Performing query with {self.searcher}"
            )
            response = self.searcher.find_studies(query)
            self.query_cache.add_response(query, response)
            return response

    def find_study_by_id(
        self, study_uid: str, query_level: QueryLevels = QueryLevels.STUDY
    ) -> Study:
        """Find a single study at the given depth"""
        try:
            from_cache: Study = self.cache.retrieve(
                StudyReference(study_uid=study_uid)
            )
            if (
                from_cache.max_object_depth()
                > DICOMObjectLevels.from_query_level(query_level)
            ):
                raise NodeNotFound(
                    f"{from_cache} found in cache, but did not contain "
                    f"objects up to '{query_level}' level"
                )
            return from_cache
        except NodeNotFound as e:
            logger.debug(
                f"Could not find study in cache ({e}). Launching query to find"
                f"additional info"
            )
            study = self.searcher.find_study_by_id(
                study_uid, query_level=query_level
            )
            self.cache.add(study)
            return study


class NodeNotFound(DICOMTrolleyError):
    pass
