import pytest

from dicomtrolley.core import DICOMObjectReference
from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.parsing import DICOMObjectTree, DICOMParseTree, TreeNode
from tests.factories import (
    create_c_find_image_response,
    create_c_find_study_response,
    create_image_level_study,
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


def test_parse_tree_from_studies(some_studies):
    """Sometimes its useful to turn a set of Study objects back into a parse tree.
    for example when augmenting existing data.
    """
    tree = DICOMParseTree.init_from_objects(some_studies)
    recompiled = tree.as_studies()
    for study_org, study_now in zip(some_studies, recompiled):
        assert str(study_org.series) == str(study_now.series)


def test_parse_tree_from_series(some_studies):
    """It should be possible to create a parse tree from studies or instances only"""
    a_series = some_studies[0].series[0]
    tree = DICOMParseTree.init_from_objects([a_series])
    recompiled = tree.as_studies()
    assert str(a_series) == str(recompiled[0].series[0])


def test_parse_tree_exceptions():
    tree = DICOMParseTree()
    tree.insert_dataset(quick_dataset(StudyInstanceUID="1"))
    with pytest.raises(DICOMTrolleyError):
        tree.insert_dataset(quick_dataset(StudyInstanceUID="1"))


@pytest.fixture
def a_tree(some_studies):
    return DICOMObjectTree(objects=some_studies)


def test_object_tree(a_tree):

    # one study has instances, one does not
    assert a_tree["Study1"].all_instances()
    assert not a_tree["Study2"].all_instances()

    # now add study 2 but with instances this time
    a_tree.add_study(
        create_image_level_study(
            study_instance_uid="Study2",
            series_instance_uids=["Series1"],
            sop_class_uids=[f"Instance{i}" for i in range(1, 10)],
        )
    )

    # this should have overwritten existing
    assert len(a_tree.studies) == 2
    assert a_tree["Study2"].all_instances()


def test_object_tree_retrieve(a_tree):
    # retrieving a series should work
    series = a_tree.retrieve(
        DICOMObjectReference(study_uid="Study1", series_uid="Series1")
    )
    assert series.uid == "Series1"

    # retrieving a study should work
    study = a_tree.retrieve(DICOMObjectReference(study_uid="Study2"))
    assert study.uid == "Study2"

    with pytest.raises(DICOMTrolleyError):
        a_tree.retrieve(DICOMObjectReference(study_uid="unknown study"))


def test_object_tree_retrieve_reference(a_tree):
    """You can use DICOMObject.reference() to search for object with
    identical ids
    For pydantic < 1.8.2 this causes a recursion depth exceeded bug
    https://github.com/pydantic/pydantic/issues/4509

    Which is the cause of dicomtrolley pinning pydantic to 1.8.2
    TODO: Once the issue above has been solved, remove the pydantic version pin
    """
    study = a_tree.studies[0]
    series = a_tree.studies[0].series[0]
    instance = a_tree.studies[0].series[0].instances[0]

    for item in [study, series, instance]:
        assert item == a_tree.retrieve(item.reference())
