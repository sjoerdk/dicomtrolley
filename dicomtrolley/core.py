"""Provides common base classes that allow modules to talk to each other."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, IntEnum
from itertools import chain
from typing import (
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from pydantic import ConfigDict, Field, ValidationError, field_validator
from pydantic.main import BaseModel
from pydicom.datadict import tag_for_keyword
from pydicom.dataset import Dataset

from dicomtrolley.exceptions import (
    DICOMTrolleyError,
    NoReferencesFoundError,
    UnSupportedParameterError,
)
from dicomtrolley.logs import get_module_logger

logger = get_module_logger("core")


class DICOMObjectLevels(IntEnum):
    """Represents DICOM study->series->instance structure

    Level is ordered. Study is highest, instance the lowest level.

    Notes
    -----
    Similar to core.QueryLevels, but different enough to warrant separate classes.
    DICOMObjectLevel is a property of a DICOM object. QueryLevel is a property of
    a Query.
    """

    STUDY = 2
    SERIES = 1
    INSTANCE = 0

    @classmethod
    def from_query_level(cls, level: "QueryLevels"):
        if level == QueryLevels.STUDY:
            return cls.STUDY
        elif level == QueryLevels.SERIES:
            return cls.SERIES
        elif level == QueryLevels.INSTANCE:
            return cls.INSTANCE
        else:
            raise ValueError(f"Unknown DICOMObjectLevels {level}")


class DICOMDownloadable:
    """An object that can be downloaded by a Downloader"""

    def reference(self) -> "DICOMObjectReference":
        raise NotImplementedError()

    def contained_references(
        self, max_level: DICOMObjectLevels
    ) -> Tuple["DICOMObjectReference", ...]:
        """DICOM object references contained in this object at the given level.

        For example, a Study might contain information for all its Instances. In
        this case sub_references(max_level=Instance) will return InstanceReferences

        Parameters
        ----------
        max_level:
            The returned references will be this level or lower. For example, an
            instance will return a reference to itself when max_level is Series:
                >>> Instance.contained_references(max_level=Series)
                (InstanceReference,)
            A study will be broken up:
                >>> Study.contained_references(max_level=Series)
                (SeriesReference, SeriesReference, ...)

        Returns
        -------
        Tuple of references. Of max_level or lower

        Raises
        ------
        NoReferencesFoundError
            If sub-references cannot be obtained from this downloadable.

        """
        raise NotImplementedError()


@dataclass(frozen=True)  # make this hashable and non-modifyable
class DICOMObjectReference(DICOMDownloadable):
    """Points to a study, series, or instance by uid

    Contrary to DICOMObjects, DICOMObjectReferences are shallow. They do
    not have parents or children and do not contain any additional information.

    They were created to use in object-level downloads (download study X)
    """

    study_uid: str

    @property
    def level(self):
        """Does this reference point to Study, Series or Instance?
        Returns
        -------
        str
            One of the values in DICOMObjectLevels.all
        """
        return NotImplementedError()

    def reference(self):
        return self

    def contained_references(
        self, max_level: DICOMObjectLevels
    ) -> Tuple["DICOMObjectReference", ...]:
        """DICOM object references either return themselves or an error"""
        if max_level < self.level:
            raise NoReferencesFoundError(
                f"{self} does not contain references of {str(max_level)} or lower"
            )
        else:
            return (self.reference(),)


@dataclass(frozen=True)
class InstanceReference(DICOMObjectReference):
    """All information needed to download a single slice (SOPInstance)"""

    study_uid: str
    series_uid: str
    instance_uid: str

    def __str__(self):
        return (
            f"InstanceReference {self.study_uid} -> {self.series_uid} "
            f"-> {self.instance_uid}"
        )

    @property
    def level(self):
        return DICOMObjectLevels.INSTANCE


@dataclass(frozen=True)
class SeriesReference(DICOMObjectReference):
    """Reference to a single Series, part of a study"""

    study_uid: str
    series_uid: str

    def __str__(self):
        return f"SeriesReference {self.study_uid} -> {self.series_uid} "

    @property
    def level(self):
        return DICOMObjectLevels.SERIES


@dataclass(frozen=True)
class StudyReference(DICOMObjectReference):
    """Reference to a single study"""

    study_uid: str

    def __str__(self):
        return f"StudyReference {self.study_uid}"

    @property
    def level(self):
        return DICOMObjectLevels.STUDY


class DICOMObject(BaseModel, DICOMDownloadable):
    """An object in the DICOM world. Base for Study, Series, Instance.

    dicomtrolley search methods always return instances based on DICOMObject
    dicomtrolley download methods take instances based on DICOMObject as input

    DICOMObjects know where they are in the DICOM tree; what their parents and
    children are. They can also contain additional information in the form of
    a DICOM dataset
    """

    # allows the use of Dataset type below
    model_config = ConfigDict(arbitrary_types_allowed=True)

    uid: str
    data: Dataset

    def __str__(self):
        return type(self).__name__ + " " + self.uid

    def children(self):
        """

        Returns
        -------
        Sequence[DICOMObject]
            All direct child objects or empty list if none. Useful for iterating
        """
        raise NotImplementedError()

    def root(self):
        """The parent or parents parent or etc.

        Returns
        -------
        DICOMObject
        """
        raise NotImplementedError()

    def all_instances(self) -> List["Instance"]:
        """

        Returns
        -------
        List[Instance]
            All instances contained in this object
        """
        raise NotImplementedError()

    def all_series(self) -> List["Series"]:
        """

        Returns
        -------
        List[Series]
            All Series contained in this object
        """
        raise NotImplementedError()

    def max_object_depth(self) -> DICOMObjectLevels:
        """What is the deepest object level? Does contain only Study or also Series,
        Instances?
        """
        raise NotImplementedError()

    @staticmethod
    def extract_refs(
        objects: Iterable["DICOMObject"],
    ) -> Tuple[DICOMObjectReference, ...]:
        """Extract reference from each object and put in a tuple, raise error for
        empty objects. For cleaner code in DICOMObject.contained_references()

        Raises
        ------
        NoReferencesFoundError
            if objects is empty
        """
        if not objects:
            raise NoReferencesFoundError()
        return tuple(x.reference() for x in objects)


class Instance(DICOMObject):
    parent: "Series"

    def all_instances(self):
        """A list containing this instance itself. To match other signatures"""
        return [self]

    def all_series(self) -> List["Series"]:
        return [self.parent]

    def children(self):
        return []

    def root(self):
        return self.parent.parent

    def reference(self) -> InstanceReference:
        """Return a Reference to this object using uids"""
        return InstanceReference(
            study_uid=self.parent.parent.uid,
            series_uid=self.parent.uid,
            instance_uid=self.uid,
        )

    def contained_references(
        self, max_level: DICOMObjectLevels
    ) -> Tuple["DICOMObjectReference", ...]:
        return (self.reference(),)  # instance is deepest level so always OK

    def max_object_depth(self) -> DICOMObjectLevels:
        """What is the deepest object level? Does contain only Study or also Series,
        Instances?
        """
        return DICOMObjectLevels.INSTANCE


class Series(DICOMObject):
    instances: Sequence[Instance]
    parent: "Study"

    def __getitem__(self, instance_uid):
        return self.get(instance_uid)

    def all_instances(self):
        """Each instance contained in this series"""
        return self.instances

    def all_series(self) -> List["Series"]:
        return [self]

    def children(self):
        return self.instances

    def root(self):
        return self.parent

    def get(self, instance_uid: str) -> Instance:
        """Get instance with this uid"""
        try:
            return next(x for x in self.instances if x.uid == instance_uid)
        except StopIteration as e:
            raise KeyError(
                f'instance with uid "{instance_uid}" not found in series'
            ) from e

    def reference(self) -> SeriesReference:
        """Return a Reference to this object using uids"""
        return SeriesReference(study_uid=self.parent.uid, series_uid=self.uid)

    def contained_references(
        self, max_level: DICOMObjectLevels
    ) -> Tuple["DICOMObjectReference", ...]:

        if max_level == DICOMObjectLevels.STUDY:
            return self.extract_refs([self])
        elif max_level == DICOMObjectLevels.SERIES:
            return self.extract_refs([self])
        elif max_level == DICOMObjectLevels.INSTANCE:
            return self.extract_refs(self.all_instances())
        else:
            raise ValueError(f'unknown DICOMObjectLevel "{str(max_level)}"')

    def max_object_depth(self) -> DICOMObjectLevels:
        """What is the deepest object level? Does contain only Study or also Series,
        Instances?
        """
        if self.instances:
            return DICOMObjectLevels.INSTANCE
        else:
            return DICOMObjectLevels.SERIES


class Study(DICOMObject):
    series: Sequence[Series]

    def __getitem__(self, series_uid) -> Series:
        return self.get(series_uid)

    def all_instances(self):
        """Return each instance contained in this study"""
        return list(chain(*(x.instances for x in self.series)))

    def all_series(self) -> List["Series"]:
        return list(self.children())

    def children(self):
        return self.series

    def root(self):
        return self

    def get(self, series_uid: str) -> Series:
        """Get series with this uid"""
        try:
            return next(x for x in self.series if x.uid == series_uid)
        except StopIteration as e:
            raise KeyError(
                f'series with uid "{series_uid}" not found in study'
            ) from e

    def reference(self) -> StudyReference:
        """Return a Reference to this object using uids"""
        return StudyReference(study_uid=self.uid)

    def contained_references(
        self, max_level: DICOMObjectLevels
    ) -> Tuple["DICOMObjectReference", ...]:

        if max_level == DICOMObjectLevels.STUDY:
            return self.extract_refs([self])
        elif max_level == DICOMObjectLevels.SERIES:
            return self.extract_refs(self.all_series())
        elif max_level == DICOMObjectLevels.INSTANCE:
            return self.extract_refs(self.all_instances())
        else:
            raise ValueError(f'unknown DICOMObjectLevel "{str(max_level)}"')

    def max_object_depth(self) -> DICOMObjectLevels:
        """What is the deepest object level? Does contain only Study or also Series,
        Instances?
        """
        if self.series:
            return self.series[0].max_object_depth()
        else:
            return DICOMObjectLevels.STUDY


class NonInstanceParameterError(DICOMTrolleyError):
    """A DICOMDownloadable could not be converted into its constituent instances.

    Trolley allows the downloading of higher-level DICOM objects like
    download(StudyInstanceUID='1234'). Some Downloader implementations can handle
    this out of the box. Others, like WADO-URI, cannot, and instead require the
    download target to be split into separate instances. This splitting requires
    additional queries, which can only be performed outside the Downloader instance
    itself.
    By raising this error a Downloader method can signal that it cannot process
    the non-instance components of an input parameter. The caller then has an
    opportunity to split the input parameters into instances and try again.

    """


class NonSeriesParameterError(DICOMTrolleyError):
    """A DICOMDownloadable could not be converted into Series or Instance reference.
    Weaker version of NonInstanceParameterError
    """


def to_instance_refs(objects: Sequence[DICOMDownloadable]):
    """Convert all to instance references. See to_refs()"""
    try:
        return to_references(objects, max_level=DICOMObjectLevels.INSTANCE)
    except NoReferencesFoundError as e:
        raise NonInstanceParameterError(
            f"Cannot obtain instance references: {e}"
        ) from e


def to_series_level_refs(objects: Sequence[DICOMDownloadable]):
    """Convert all to at least series references."""
    try:
        return to_references(objects, max_level=DICOMObjectLevels.SERIES)
    except NoReferencesFoundError as e:
        raise NonSeriesParameterError(
            f"Cannot obtain series references: {e}"
        ) from e


def to_references(
    objects: Sequence[DICOMDownloadable], max_level: DICOMObjectLevels
) -> List[DICOMObjectReference]:
    """Make sure all input objects are of max_level or lower. Extract lower level
    references if possible. For example, if max_level is series, try to extract
    series references from a study. Raise exceptions if not possible.

    Parameters
    ----------
    objects:
        Convert these objects
    max_level:
        Return references of this level or lower, otherwise raise exception.

    Returns
    -------
    List[Union[SeriesReference, InstanceReference]]
        References to series and instances contained in input objects

    Notes
    -----
    This is a common pre-processing step used by Downloader classes. Many cannot
    download higher-level objects like 'study 123' directly, but instead require
    you to query all instances contained in 'study 123' first and pass those to
    the downloader.

    Raises
    ------
    NoReferencesFoundError
        If any input object could not be converted into instances. This is the
        case for higher-level references like StudyReference, or for DICOMObjects
        that do not contain any deeper-level information, such as a Study that
        contains no Series (which is a correct result for Study-level queries).

    """
    refs: List[DICOMObjectReference] = []
    for obj in objects:
        refs.extend(obj.contained_references(max_level=max_level))
    return refs


class Downloader:
    """Something that can download DICOM images. Base class."""

    def get_dataset(self, instance: InstanceReference):
        """Get DICOM dataset for the given instance (slice)

        Raises
        ------
        DICOMTrolleyError
            If getting does not work for some reason

        Returns
        -------
        Dataset
            A pydicom dataset
        """
        raise NotImplementedError

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
                Raises

        DICOMTrolleyError
            If getting does not work for some reason
        """
        raise NotImplementedError()


class QueryLevels(str, Enum):
    """Used in dicom queries to indicate how rich the search should be"""

    STUDY = "STUDY"
    SERIES = "SERIES"
    INSTANCE = "INSTANCE"

    @classmethod
    def from_object_level(cls, level: DICOMObjectLevels):
        """Convert from DICOMObjectLevel enum. See docstring there for reason"""
        if level == DICOMObjectLevels.STUDY:
            return cls.STUDY
        elif level == DICOMObjectLevels.SERIES:
            return cls.SERIES
        elif level == DICOMObjectLevels.INSTANCE:
            return cls.INSTANCE
        else:
            raise ValueError(f"Unknown DICOMObjectLevels {level}")


# Used in Query.init_from_query() type annotation
QuerySubType = TypeVar("QuerySubType", bound="Query")


class Query(BaseModel):
    """A simple DICOM query that is acceptable to all Searcher classes

    Limited parameters but can be used in all Searcher backends

    Notes
    -----
    *  Different backends use slightly different query parameters. This class
       implements all common parameters.

    *  DICOM queries consist of a number of DICOM tags followed by a search
       criterion. The naming format for these parameters follows DICOM conventions
       (CamelCase). In addition, a query has non-DICOM meta-parameters. Here regular
       python (lower_case_underscore) naming is used

    General notes on subclassing Query

    A Searcher class often has its own associated Query subclass. For instance,
    the Mint searcher function Mint.find_study(query) can take a MintQuery instance
    which uniquely allows the setting of the MINT-specific parameter `limit`.
    Any Searcher can however also take a generic Query instance as input. This
    makes it possible to use a simple Query in your code and be independent
    of searcher backend.
    An issue with the scheme is that it is in principle allowed to use the Query
    baseclass as input, it should also be allowed to use any Query subclass in
    any searcher. This, for example, would be legal:

    ```python
    query = QidoRelationalQuery(qido_specific_setting=1)
    studies = Mint().find_study(query)
    ```
    This is weird but not unthinkable. The problem is that the Mint searcher
    cannot do anything with the `qido_specific_setting` set for the query. If
    Mint just uses the basic Query parameters for its query, information would
    be ignored or lost. On the other hand, if we enforce that Mint().find_study()
    only takes MintQuery objects, we lose the ability to use a Query as a
    backend-agnostic general query.

    The tradeoff in structure is between the convenience of having a
    backend-agnostic query on the one hand, and having tight type definitions
    for input arguments on the other.

    In the end, decided that the backend-agnostic query is too useful to lose.
    However, there should be no silent ignoring of parameters. So we will have
    Searcher methods raise UnSupportedParameterError if using an input query would
    result in information being lost.
    """

    # Dicom parameters
    StudyInstanceUID: str = ""
    AccessionNumber: str = ""
    PatientName: str = ""
    PatientID: str = ""
    ModalitiesInStudy: str = ""
    SeriesInstanceUID: str = ""

    # non-DICOM parameters. Translated into derived parameters when querying
    query_level: QueryLevels = (
        QueryLevels.STUDY
    )  # to which depth to return results
    max_study_date: Optional[datetime] = None
    min_study_date: Optional[datetime] = None
    include_fields: Optional[List[str]] = Field(default_factory=list)
    # raise ValueError when passing an unknown keyword to init
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def init_from_query(
        cls: Type[QuerySubType], query: "Query"
    ) -> QuerySubType:
        """Create an instance of this class based on any Query instance

        This function enables Query to be used in all backends. See Query
        notes for rationale

        Parameters
        ----------
        query: Query
            Use all non-falsy parameters from this to create new instance

        Returns
        -------
        An instance of this class based on input query

        Raises
        ------
        UnSupportedParameterError
            If query contains non-default parameters that are not supported in
            this class
        """
        # remove empty, None and 0 values
        params = {key: val for key, val in query.model_dump().items() if val}
        try:
            return cls(**params)
        except ValidationError as e:
            raise UnSupportedParameterError(
                f"Conversion from {query.to_short_string()} would ignore one more "
                f"parameters. You are probably converting between incompatible "
                f"query subtypes. Use a basic Query instance to avoid this error. "
                f"See ValidationError for details on which parameter is causing "
                f"the problem. Original error: {str(e)}"
            ) from e

    @staticmethod
    def validate_keyword(keyword):
        if not tag_for_keyword(keyword):
            raise ValueError(f"{keyword} is not a valid DICOM keyword")

    @field_validator("include_fields")
    @classmethod
    def include_fields_check(cls, include_fields, values):  # noqa: B902, N805
        """Include fields should be valid dicom tag names"""
        for field in include_fields:
            if not tag_for_keyword(field):
                raise ValueError(f"{field} is not a valid DICOM keyword")

        return include_fields

    def to_short_string(self):
        """A more information-dense str repr. For human reading"""
        filled_fields = {
            key: val for key, val in self.model_dump().items() if val
        }
        filled_fields["query_level"] = filled_fields["query_level"].value
        return f"{type(self).__name__}: {filled_fields}"


class ExtendedQuery(Query):
    """Query with additional parameters. Base for Mint and DICOM-QR.

    Made this to avoid duplicate extra fields in Mint and DICOM-QR searchers
    """

    InstitutionName: str = ""
    PatientSex: str = ""
    StudyDescription: str = ""
    SeriesDescription: str = ""
    InstitutionalDepartmentName: str = ""
    PatientBirthDate: Optional[date] = None


class Searcher:
    """Something that can search for DICOM studies. Base class."""

    def find_studies(self, query: Query) -> Sequence[Study]:
        raise NotImplementedError()

    def find_study(self, query: Query) -> Study:
        """Like find_studies, but guarantees exactly one result. Exception if not.

        This method is meant for searches that contain unique identifiers like
        StudyInstanceUID, AccessionNumber, etc.

        Raises
        ------
        DICOMTrolleyError
            If no results or more than one result is returned by query
        """
        results = self.find_studies(query)
        if len(results) > 1:
            logger.debug(
                f"Found too many results!({len(results)}, expected 1)\n {results}"
            )
            raise DICOMTrolleyError(
                f"Expected exactly one study for query '{query.to_short_string()}',"
                f" but found {len(results)}"
            )
        if len(results) == 0 or len(results) > 1:
            raise DICOMTrolleyError(
                f"Expected exactly one study for query '{query.to_short_string()}',"
                f" but found none"
            )
        return results[0]

    def find_study_by_id(
        self, study_uid: str, query_level: QueryLevels = QueryLevels.STUDY
    ) -> Study:
        """Find a single study at the given depth

        Useful for automatically finding all instances for a study. Meant to be
        implemented in child classes

        Parameters
        ----------
        study_uid: str
            Study to search for
        query_level: QueryLevels
            Depth of search. Whether to find only study level info or go deeper into
            series or instances. Deeper levels will result in slower, more extensive
            searches

        Returns
        -------
        Study
            Potentially containing series or instances, dependent on query_level


        Raises
        ------
        DICOMTrolleyError
            If no results or more than one result is returned by query
        """
        return self.find_study(
            Query(StudyInstanceUID=study_uid, query_level=query_level)
        )


Instance.model_rebuild()  # enables pydantic validation
Series.model_rebuild()
