"""Provides common base classes that allow different modules to talk to each other."""
from itertools import chain
from typing import Sequence

from pydantic.main import BaseModel
from pydicom.dataset import Dataset

from dicomtrolley.exceptions import DICOMTrolleyException


class DICOMObject(BaseModel):
    """An object in the DICOM world. Base for Study, Series, Instance.

    dicomtrolley search methods always return instances based on DICOMObject
    dicomtrolley download methods take instances based on DICOMObject as input
    """

    uid: str
    data: Dataset

    def __str__(self):
        return type(self).__name__ + " " + self.uid

    def all_instances(self):
        """

        Returns
        -------
        List[Instance]
            All instances contained in this object
        """
        raise NotImplementedError()


class Instance(DICOMObject):
    parent: "Series"

    def all_instances(self):
        """A list containing this instance itself. To match other signatures"""
        return [self]


class Series(DICOMObject):
    instances: Sequence[Instance]
    parent: "Study"

    def all_instances(self):
        """Each instance contained in this series"""
        return self.instances


class Study(DICOMObject):
    series: Sequence[Series]

    def all_instances(self):
        """Return each instance contained in this study"""
        return list(chain(*(x.instances for x in self.series)))


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
        DICOMTrolleyException
            If no results or more than one result is returned by query
        """
        results = self.find_studies(query)
        if len(results) == 0 or len(results) > 1:
            raise DICOMTrolleyException(
                f"Expected exactly one study for query '{query}', but"
                f" found {len(results)}"
            )
        return results[0]


Instance.update_forward_refs()  # enables pydantic validation
Series.update_forward_refs()
