"""Models parsing things into study/series/instance structure"""

from typing import Any, DefaultDict, List

from pydicom.dataset import Dataset

from dicomtrolley.core import Instance, Series, Study
from dicomtrolley.exceptions import DICOMTrolleyException


class TreeNode(DefaultDict[Any, "TreeNode"]):
    """Recursive defaultdict with a 'data' property. Helps parse to tree structures.

    Examples
    --------
    >>> root = TreeNode()
    >>> root['study1']['series1']['instance1'].data = 'some instance info'
    >>> 'study1' in root
    True
    >>> root['study1']['series2'].data = 'some series data'
    >>> list(root['study1'].keys)
    ['series1', 'series2']
    """

    def __init__(self, data=None, allow_overwrite=True):
        """

        Parameters
        ----------
        data:
            Optional data to associate with this node
        allow_overwrite: bool, optional
            If False, will raise exception when overwriting data attribute
        """
        super().__init__(lambda: TreeNode(allow_overwrite=allow_overwrite))
        self._data = data
        self.allow_overwrite = allow_overwrite

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        if self.allow_overwrite or not self.data:
            self._data = value
        else:
            raise ValueError("Overwriting data is not allowed")


class DICOMParseTree:
    """Models study/series/instance as a tree. Allows arbitrary branch insertions"""

    def __init__(self, root=None, allow_overwrite=False):
        """

        Parameters
        ----------
        root: TreeNode, optional
            Root node. Will contain all. Defaults to empty
        allow_overwrite: bool, optional
            If False, will raise exception when overwriting any TreeNode.data,
            Defaults to False
        """
        if not root:
            self.root = TreeNode(allow_overwrite=allow_overwrite)

    def insert(self, data, study, series=None, instance=None):
        """Insert data at the given level in tree. Will complain about missing
        branches

        Raises
        ------
        DICOMTrolleyException
            If inserting fails for any reason
        """
        if instance and not series:
            DICOMTrolleyException(
                f"Instance was given ({instance}) but series was not. I can "
                f"not insert this into a study/series/instance tree"
            )
        try:
            if series:
                if instance:
                    self.root[study][series][instance].data = data
                else:
                    self.root[study][series].data = data
            else:
                self.root[study].data = data
        except ValueError as e:
            raise DICOMTrolleyException(
                f"Error inserting dataset into {study}/{series}/{instance}: {e}"
            )

    def insert_dataset(self, ds: Dataset):
        self.insert(
            data=ds,
            study=ds.get("StudyInstanceUID"),
            series=ds.get("SeriesInstanceUID"),
            instance=ds.get("SOPInstanceUID"),
        )

    def as_studies(self) -> List[Study]:
        """Tree as DICOMObject instances: Study containing Series, Instance"""

        def value_or_dataset(val):
            if val:
                return val
            else:
                return Dataset()

        studies = []
        for study_instance_uid, study_node in self.root.items():
            study = Study(
                uid=study_instance_uid,
                data=value_or_dataset(study_node.data),
                series=tuple(),
            )
            studies.append(study)
            all_series = []
            for series_instance_uid, series_node in study_node.items():
                series = Series(
                    uid=series_instance_uid,
                    data=value_or_dataset(series_node.data),
                    parent=study,
                    instances=tuple(),
                )
                all_series.append(series)
                all_instances = []
                for sop_instance_uid, instance_node in series_node.items():
                    all_instances.append(
                        Instance(
                            uid=sop_instance_uid,
                            data=value_or_dataset(instance_node.data),
                            parent=series,
                        )
                    )
                series.instances = tuple(all_instances)
            study.series = tuple(all_series)
        return studies
