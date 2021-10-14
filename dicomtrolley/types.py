"""Custom types for type hints"""
from typing import Union

from dicomtrolley.core import DICOMObject
from dicomtrolley.wado import InstanceReference

# Anything that can be downloaded by trolley
DICOMDownloadable = Union[DICOMObject, InstanceReference]
