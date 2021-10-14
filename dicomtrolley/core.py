"""Provides common base classes that allow different modules to talk to each other."""
from itertools import chain
from typing import Sequence

from pydantic.main import BaseModel
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
