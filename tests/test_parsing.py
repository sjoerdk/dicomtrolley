import pytest

from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.parsing import DICOMParseTree, TreeNode
from tests.factories import (
    create_c_find_image_response,
    create_c_find_study_response,
    quick_dataset,
)


def test_parsing_node():
    node = TreeNode()
    node["a"]["b"]["c"].data = "some data"
    assert node["a"]["b"]["c"].data == "some data"

    node["a"]["b2"].data = "some other data"
    assert list(node["a"].keys()) == ["b", "b2"]


def test_parsing_node_exceptions():
    node = TreeNode(allow_overwrite=False)
    node["a"]["b"].data = "some data"
    with pytest.raises(ValueError):
        node["a"]["b"].data = "some other data"

    # this should not raise anything
    node2 = TreeNode(allow_overwrite=True)
    node2["a"]["b"].data = "some data"
    node2["a"]["b"].data = "some other data"


def test_parse_tree():
    """Parse flat datasets into a tree structure"""
    tree = DICOMParseTree()
    responses = create_c_find_study_response(
        study_instance_uids=[f"Study{i}" for i in range(1, 5)]
    )
    responses = responses + create_c_find_image_response(
        study_instance_uid="Study1",
        series_instance_uids=["Series1", "Series2"],
        sop_class_uids=[f"Inst{i}" for i in range(1, 10)],
    )

    for response in responses:
        tree.insert_dataset(response)

    assert (
        tree.root["Study1"]["Series1"]["Inst3"].data.SeriesInstanceUID
        == "Series1"
    )

    studies = tree.as_studies()

    assert len(studies) == 4
    assert studies[0].data.Modality == "CT"
    assert len(studies[0].series) == 2
    assert len(studies[0].series[0].instances) == 9
    assert studies[0].series[0].instances[0].data.StudyInstanceUID == "Study1"


def test_parse_tree_exceptions():
    tree = DICOMParseTree()
    tree.insert_dataset(quick_dataset(StudyInstanceUID="1"))
    with pytest.raises(DICOMTrolleyException):
        tree.insert_dataset(quick_dataset(StudyInstanceUID="1"))
