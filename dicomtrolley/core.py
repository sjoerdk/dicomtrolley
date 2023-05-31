"""Provides common base classes that allow modules to talk to each other."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from itertools import chain
from typing import List, Optional, Sequence, Union

from pydantic.class_validators import validator
from pydantic.main import BaseModel
from pydicom.datadict import tag_for_keyword
from pydicom.dataset import Dataset

from dicomtrolley.exceptions import DICOMTrolleyError


class DICOMObjectLevels:
    """DICOM uses a study->series->instance structure"""

    STUDY = "Study"
    SERIES = "Series"
    INSTANCE = "Instance"


class DICOMObjectReference:
    def __init__(self, study_uid, series_uid=None, instance_uid=None):
        """Designates a study, series or instance uid by uids

        Made this to remove all

        Parameters
        ----------
        study_uid: str
        series_uid: str
        instance_uid: str

        Raises
        ------
        ValueError
            If data for the given parameters does not exist in tree
        """
        if instance_uid and not series_uid:
            raise ValueError(
                f"Instance was given ({instance_uid}) but series was not. I can "
                f"not insert this into a study/series/instance tree"
            )

        self.study_uid = study_uid
        self.series_uid = series_uid
        self.instance_uid = instance_uid

    @property
    def level(self):
        """Does this reference point to Study, Series or Instance?"""
        if self.instance_uid:
            return DICOMObjectLevels.INSTANCE
        elif self.series_uid:
            return DICOMObjectLevels.SERIES
        else:
            return DICOMObjectLevels.STUDY

    def __str__(self):
        return (
            f"{self.level} reference {self.study_uid} -> {self.series_uid} "
            f"-> {self.instance_uid}"
        )


class DICOMObject(BaseModel):
    """An object in the DICOM world. Base for Study, Series, Instance.

    dicomtrolley search methods always return instances based on DICOMObject
    dicomtrolley download methods take instances based on DICOMObject as input
    """

    class Config:
        arbitrary_types_allowed = True  # allows the use of Dataset type below

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

    def all_instances(self):
        """

        Returns
        -------
        List[Instance]
            All instances contained in this object
        """
        raise NotImplementedError()

    def reference(self) -> DICOMObjectReference:
        """Return a Reference to this object using uids"""
        raise NotImplementedError()


class Instance(DICOMObject):
    parent: "Series"

    def all_instances(self):
        """A list containing this instance itself. To match other signatures"""
        return [self]

    def children(self):
        return []

    def root(self):
        return self.parent.parent

    def reference(self) -> DICOMObjectReference:
        """Return a Reference to this object using uids"""
        return DICOMObjectReference(
            study_uid=self.parent.parent.uid,
            series_uid=self.parent.uid,
            instance_uid=self.uid,
        )


class Series(DICOMObject):
    instances: Sequence[Instance]
    parent: "Study"

    def __getitem__(self, instance_uid):
        return self.get(instance_uid)

    def all_instances(self):
        """Each instance contained in this series"""
        return self.instances

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

    def reference(self) -> DICOMObjectReference:
        """Return a Reference to this object using uids"""
        return DICOMObjectReference(
            study_uid=self.parent.uid, series_uid=self.uid
        )


class Study(DICOMObject):
    series: Sequence[Series]

    def __getitem__(self, series_uid) -> Series:
        return self.get(series_uid)

    def all_instances(self):
        """Return each instance contained in this study"""
        return list(chain(*(x.instances for x in self.series)))

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

    def reference(self) -> DICOMObjectReference:
        """Return a Reference to this object using uids"""
        return DICOMObjectReference(study_uid=self.uid)


@dataclass
class InstanceReference:
    """All information needed to download a single slice (SOPInstance)"""

    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str

    def __str__(self):
        return f"InstanceReference {self.sop_instance_uid}"


# Anything that can be downloaded by trolley
DICOMDownloadable = Union[DICOMObject, InstanceReference]


class NonInstanceParameterError(DICOMTrolleyError):
    """A parameter of Sequence[DICOMDownloadable] contained objects other than
    InstanceReference.

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


def assert_instances(
    objects: Sequence[DICOMDownloadable],
) -> Sequence[InstanceReference]:
    """Assert that all objects are instances. If not, raise informative error

    Parameters
    ----------
    objects:
        Check these objects

    Returns
    -------
    Sequence[InstanceReference]
        The input unaltered, provided no exception was raised


    Raises
    ------
    NonInstanceParameterError
            If objects contain non-instance targets like a StudyInstanceUID and
            download can only process Instance targets. See Exception docstring
            for rationale
    """
    for obj in objects:
        if not isinstance(obj, InstanceReference):
            raise NonInstanceParameterError(
                f"{obj} is not a direct instance " f"reference"
            )

    return objects  # type: ignore


class Downloader:
    """Something that can fetch DICOM instances. Base class"""

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
        """
        raise NotImplementedError

    def datasets_async(
        self, instances: Sequence[InstanceReference], max_workers=None
    ):
        """Retrieve each instance in multiple threads

        Parameters
        ----------
        instances: Sequence[InstanceReference]
            Retrieve dataset for each of these instances
        max_workers: int, optional
            Use this number of workers in ThreadPoolExecutor. Defaults to
            default for ThreadPoolExecutor

        Raises
        ------
        DICOMTrolleyError
            When a server response cannot be parsed as DICOM

        Returns
        -------
        Iterator[Dataset, None, None]
        """
        raise NotImplementedError


class QueryLevels(str, Enum):
    """Used in dicom queries to indicate how rich the search should be"""

    STUDY = "STUDY"
    SERIES = "SERIES"
    INSTANCE = "INSTANCE"


class Query(BaseModel):
    """All information required to perform a DICOM query

    Notes
    -----
    *  Different backends use slightly different query parameters. This class
       implements all common parameters.
    *  DICOM queries consist of a number of DICOM tags followed by a search
       criterium. The naming format for these parameters follows DICOM conventions
       (CamelCase). In addition, a query has non-DICOM meta-parameters. Here regular
       python (lower_case_underscore) naming is used
    """

    # Dicom parameters
    StudyInstanceUID: str = ""
    AccessionNumber: str = ""
    PatientName: str = ""
    PatientID: str = ""
    ModalitiesInStudy: str = ""
    InstitutionName: str = ""
    PatientSex: str = ""
    StudyDescription: str = ""
    SeriesDescription: str = ""
    SeriesInstanceUID: str = ""
    InstitutionalDepartmentName: str = ""
    PatientBirthDate: Optional[date]

    # non-DICOM parameters. Translated into derived parameters when querying
    query_level: QueryLevels = (
        QueryLevels.STUDY
    )  # to which depth to return results
    max_study_date: Optional[datetime]
    min_study_date: Optional[datetime]
    include_fields: List[str] = []  # which dicom fields to return

    class Config:
        extra = "forbid"  # raise ValueError when passing an unknown keyword to init

    @classmethod
    def from_query(cls, query: "Query"):
        """Create a Query from given query. For casting to child types"""
        return cls(**query.dict())

    @staticmethod
    def validate_keyword(keyword):
        if not tag_for_keyword(keyword):
            raise ValueError(f"{keyword} is not a valid DICOM keyword")

    @validator("include_fields")
    def include_fields_check(cls, include_fields, values):  # noqa: B902, N805
        """Include fields should be valid dicom tag names"""
        for field in include_fields:
            if not tag_for_keyword(field):
                raise ValueError(f"{field} is not a valid DICOM keyword")

        return include_fields

    def to_short_string(self):
        """A more information-dense str repr. For human reading"""
        filled_fields = {key: val for key, val in self.dict().items() if val}
        filled_fields["query_level"] = filled_fields["query_level"].value
        return f"{type(self).__name__}: {filled_fields}"


class Searcher:
    """Something that can search for DICOM studies. Base class."""

    def find_studies(self, query) -> Sequence[Study]:
        raise NotImplementedError()

    def find_study(self, query) -> Study:
        """Like find_studies, but guarantees exactly one result. Exception if not.

        This method is meant for searches that contain unique identifiers like
        StudyInstanceUID, AccessionNumber, etc.

        Raises
        ------
        DICOMTrolleyError
            If no results or more than one result is returned by query
        """
        results = self.find_studies(query)
        if len(results) == 0 or len(results) > 1:
            raise DICOMTrolleyError(
                f"Expected exactly one study for query '{query}', but"
                f" found {len(results)}"
            )
        return results[0]

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


Instance.update_forward_refs()  # enables pydantic validation
Series.update_forward_refs()
