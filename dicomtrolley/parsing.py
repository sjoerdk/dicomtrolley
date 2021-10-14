"""Models parsing things into study/series/instance structure"""
from typing import Any, DefaultDict, Dict, List, Sequence

from pydicom.dataset import Dataset

from dicomtrolley.core import (
    DICOMObject,
    DICOMObjectLevels,
    DICOMObjectReference,
    Instance,
    Series,
    Study,
)
from dicomtrolley.exceptions import DICOMTrolleyError


def flatten(dicom_object) -> List[DICOMObject]:
    """All nodes and as a flat list, study, series"""
    nodes = [dicom_object]
    for child in dicom_object.children():
        nodes = nodes + flatten(child)
    return nodes


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

    @classmethod
    def init_from_objects(cls, objects: Sequence[DICOMObject]):
        """Create a tree from given objects. Useful for augmenting query results

        Notes
        -----
        Parent objects for instances and series will be created to maintain to
        ensure all nodes are connected to the tree root. For example, running this
        method with only a single instance as input will result in a regular
        root->study->series->instance tree. This is possible because all DICOMObjects
        maintain links to their parent objects

        Returns
        -------
        DICOMParseTree
        """

        tree = cls(allow_overwrite=True)
        for item in objects:
            tree.update(item)

        return tree

    def update(self, other):
        """Add all nodes in other to this tree. Overwrite existing

        Parameters
        ----------
        other: DICOMObject
            Dicom object to add to this tree
        """
        for item in flatten(other):
            self.insert_dicom_object(item)

    def insert(self, data, study_uid, series_uid=None, instance_uid=None):
        """Insert data at the given level in tree. Will complain about missing
        branches

        Raises
        ------
        DICOMTrolleyError
            If inserting fails for any reason
        """
        if instance_uid and not series_uid:
            DICOMTrolleyError(
                f"Instance was given ({instance_uid}) but series was not. I can "
                f"not insert this into a study/series/instance tree"
            )
        try:
            if series_uid:
                if instance_uid:
                    self.root[study_uid][series_uid][instance_uid].data = data
                else:
                    self.root[study_uid][series_uid].data = data
            else:
                self.root[study_uid].data = data
        except ValueError as e:
            raise DICOMTrolleyError(
                f"Error inserting dataset into "
                f"{study_uid}/{series_uid}/{instance_uid}: {e}"
            ) from e

    def insert_dataset(self, ds: Dataset):
        self.insert(
            data=ds,
            study_uid=ds.get("StudyInstanceUID"),
            series_uid=ds.get("SeriesInstanceUID"),
            instance_uid=ds.get("SOPInstanceUID"),
        )

    def insert_dicom_object(self, dicom_object: DICOMObject):
        """Insert dicomtrolley dicom object"""

        if isinstance(dicom_object, Study):
            self.insert(data=dicom_object.data, study_uid=dicom_object.uid)
        elif isinstance(dicom_object, Series):
            self.insert(
                data=dicom_object.data,
                study_uid=dicom_object.parent.uid,
                series_uid=dicom_object.uid,
            )
        elif isinstance(dicom_object, Instance):
            self.insert(
                data=dicom_object.data,
                study_uid=dicom_object.parent.parent.uid,
                series_uid=dicom_object.parent.uid,
                instance_uid=dicom_object.uid,
            )
        else:
            raise DICOMTrolleyError(
                f"Unknown DICOM object {dicom_object}. I do "
                f"not know where to insert this in the DICOM "
                f"tree"
            )

    @staticmethod
    def as_study(study_node_in) -> Study:
        """Tree node at the study level into a Study containing Series, Instances"""

        def value_or_dataset(val):
            if val:
                return val
            else:
                return Dataset()

        study_instance_uid, study_node = study_node_in

        study = Study(
            uid=study_instance_uid,
            data=value_or_dataset(study_node.data),
            series=tuple(),
        )
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
        return study

    def as_studies(self) -> List[Study]:
        """Tree as DICOMObject instances: Study containing Series, Instance"""

        return [self.as_study(node) for node in self.root.items()]


class DICOMObjectNotFound(DICOMTrolleyError):
    pass


class DICOMObjectTree:
    """For querying, adding and modifying collections of DICOM objects

    Serves a different purpose from parsing.TreeNode. parsing.TreeNode is meant
    to build internally coherent(with parents, children) DICOMObjects from raw input.
    DICOMObjectTree allows manipulating these objects when they have already been
    created

    Notes
    -----
    If series or instances are added to the store, parent study or series
    will be created and added automatically.
    """

    def __init__(self, objects: Sequence[DICOMObject]):
        # make sure the tree is complete and all objects are based in studies
        studies = DICOMParseTree.init_from_objects(objects).as_studies()
        self._study_dict: Dict[str, Study] = {x.uid: x for x in studies}

    def __getitem__(self, series_uid) -> Study:
        return self._study_dict[series_uid]

    @property
    def studies(self):
        return list(self._study_dict.values())

    def add_study(self, study: Study):
        """Add given study to tree, overwriting exiting"""
        self._study_dict[study.uid] = study

    def retrieve(self, reference: DICOMObjectReference) -> DICOMObject:
        """Retrieve data for the given study, series or instance from tree

        Raises
        ------
        DICOMObjectNotFound
            If data for the given parameters does not exist in tree
        """

        try:
            if reference.level == DICOMObjectLevels.STUDY:
                return self[reference.study_uid]
            elif reference.level == DICOMObjectLevels.SERIES:
                return self[reference.study_uid].get(reference.series_uid)
            elif reference.level == DICOMObjectLevels.INSTANCE:
                return (
                    self[reference.study_uid]
                    .get(reference.series_uid)
                    .get(reference.instance_uid)
                )
            else:
                raise DICOMTrolleyError(
                    f"Unknown object level {reference.level}"
                )
        except KeyError as e:
            raise DICOMObjectNotFound(
                f"Study with uid {reference.study_uid} not found in tree"
            ) from e
