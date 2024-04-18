from datetime import datetime, timedelta

import pytest

from dicomtrolley.datastructures import (
    ExpiringCollection,
    PruneStrategy,
    TreeNode,
    addr,
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


def test_parsing_node_exists_check():
    node = TreeNode()
    node["a"]["b"]["c"].data = "some data"
    assert node.exists(address=["a", "b", "c"])
    assert not node.exists(address=["a", "b", "d"])
    assert not node.exists(address=["f", "s"])


def test_parsing_node_addressing():
    """You should be able to use dict notation (tree[key1][key2]) and List of strings
    (Tree.get(['key1'.'key2']))
    """

    node = TreeNode()
    _ = node["a"]["b"]  # addressing means creating
    assert node.exists(addr("a.b"))

    # checking existence does not create
    assert not node.exists(addr("d.b"))
    assert not node.exists(addr("d.b"))

    # checking with get_node does create
    _ = node.get_node(addr("d.b"))
    assert node.exists(addr("d.b"))


def test_parsing_node_prune():
    """You can remove nodes yes"""

    # simple parent with two child nodes
    root = TreeNode()
    _ = root.get_node(addr("a.b"))
    _ = root.get_node(addr("a.c"))
    _ = root.get_node(addr("a.d"))
    assert root.exists(addr("a.b"))
    assert root.exists(addr("a.c"))
    assert root.exists(addr("a.d"))

    # Pruning child will leave siblings
    root.prune(addr("a.b"))
    assert not root.exists(addr("a.b"))
    assert root.exists(addr("a.c"))

    # Pruning parent will remove siblings
    root.prune(addr("a"))
    assert not root.exists(addr("a.c"))

    # this should not work
    with pytest.raises(KeyError):
        root.prune([])


def test_parsing_node_prune_leaf():
    root = TreeNode()
    _ = root.get_node(addr("a.b"))

    # not allowed to prune stem node
    with pytest.raises(ValueError):
        root.prune_leaf(addr("a"))

    # but leaf is ok
    root.prune_leaf(addr("a.b"))
    root.prune_leaf(addr("a"))

    # this should not work
    with pytest.raises(KeyError):
        root.prune_leaf([])


def test_parsing_node_prune_all():
    """When pruning many nodes at once, make sure to handle parent-child relations"""

    # You can pass the stem before the leaf, prune_leaf_all will sort
    tree1 = TreeNode.init_from_addresses([addr("a.b.d"), addr("a.c")])
    tree1.prune_all(
        [addr("a.b"), addr("a.b.d")], strategy=PruneStrategy.CHECK_FIRST
    )

    # Prune all won't prune 'a' as 'a.c' still exists
    tree2 = TreeNode.init_from_addresses([addr("a.b.d"), addr("a.c")])
    with pytest.raises(KeyError):
        tree2.prune_all(
            [addr("a"), addr("a.b.d")], strategy=PruneStrategy.CHECK_FIRST
        )

    # If you pass 'a.c' for pruning as well there is no problem
    tree3 = TreeNode.init_from_addresses([addr("a.b.d"), addr("a.c")])
    tree3.prune_all(
        [addr("a.b"), addr("a.b.d"), addr("a.c")],
        strategy=PruneStrategy.CHECK_FIRST,
    )


@pytest.fixture()
def an_expiring_collection():
    """A 5 minute-expiring collection with a .set_time function for debugging"""
    collection = ExpiringCollection(expire_after_seconds=300)
    now = datetime.now()

    def set_time(secs):
        collection._now = lambda: now + timedelta(seconds=secs)

    return collection, set_time


def test_expiring_collection(an_expiring_collection):
    collection, set_time = an_expiring_collection

    # you can get a thing
    collection.add("a_thing")
    assert collection.items
    assert not collection.collect_expired()

    # unless its expired
    set_time(600)

    assert not collection.items
    assert collection.collect_expired() == ["a_thing"]

    # adding a thing a second time will update the times
    set_time(0)
    collection.add(12)  # add '12' at time 0. should expire in 300
    set_time(200)
    collection.add(12)  # add it again
    assert collection.items == [12]  # no doubles
    set_time(400)
    assert collection.items == [12]  # last add was less than 300 ago

    set_time(700)
    assert collection.items == []  # but now that too has timed out


def test_expiring_collection_update_clash(an_expiring_collection):
    """If you update an object timestamp, order of timestamps should be maintained"""
    collection, set_time = an_expiring_collection
    collection.add_all(["item1", "item2"])
    set_time(200)
    collection.add("item1")  # item2 should now expire before item1
    set_time(400)  # item 2 should now be expired. Is it handled properly?
    assert collection.collect_expired() == ["item2"]
    assert collection.items == ["item1"]


@pytest.fixture
def a_tree():
    """Produce this tree:
    #       A
    #     /  \
    #    B    C
    #   / \
    #  D   E
    """

    return TreeNode.init_from_addresses(
        [addr("a.b.d"), addr("a.b.e"), addr("a.c")]
    )


@pytest.mark.parametrize(
    "strategy, result",
    [
        (PruneStrategy.FORCE, {"ac"}),
        (PruneStrategy.WHERE_POSSIBLE, {"abe", "ac"}),
        (PruneStrategy.CHECK_FIRST, {"abd", "abe", "ac"}),
    ],
)
def test_prune_strategies(a_tree, strategy, result):
    try:
        a_tree.prune_all(
            addresses=[addr("a.b"), addr("a.b.d")], strategy=strategy
        )
    except KeyError:
        pass

    addresses = [x for x in a_tree.iter_leaf_addresses()]
    address_strings = {"".join(x) for x in addresses}

    assert address_strings == result
