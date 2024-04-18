"""Additional datastructures that do not belong to any specific dicomtrolley
class or function

"""
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    DefaultDict,
    Hashable,
    Iterable,
    Iterator,
    List,
    Sequence,
    Tuple,
)
from typing import OrderedDict as OrderedDictType

# Used in TreeNode functions
TreeAddress = Tuple[str, ...]


def addr(dot_address: str):
    """Convenience method for creating an address with dot notation

    Works quick and readable as long as you don't have dots in your address keys.
    If you do, just use a ['list','of','strings','with.dots.if.you.have.to']
    """
    return tuple(dot_address.split("."))


class PruneStrategy(str, Enum):
    """How to handle pruning multiple nodes at once.
    Consider this tree with five nodes:
          A
        /  \
       B    C
      / \
     D   E

    I want to prune node B and E.
    There are two choices to be made with regard to this.
    Choice 1:
        Pruning node B will orphan node D, and make it inaccessible. Is this OK?
    Choice 2:
        If orphaning node D is not OK, is it still ok to remove E? Or should we just
        disallow the whole pruning?

    These two choices inform tree strategies:
    FORCE
        Just prune. Yes you can prune B. D and E will disappear and that's fine

    WHERE_POSSIBLE
        Let's not get overzealous. You can't prune B, but you can still prune E.

    CHECK_FIRST
        Let's be very careful. Only prune if ALL nodes can be pruned. This
        assures that a successful prune removes all nodes

    """

    FORCE = "Force"  # prune all nodes, don't check for anything

    WHERE_POSSIBLE = (
        "Where_possible"  # prune nodes without children where you can
    )

    CHECK_FIRST = "Check_first"  # only prune if all targets can be pruned


class TreeNode(DefaultDict[str, "TreeNode"]):
    """Recursive defaultdict with a 'data' property. Helps parse to tree structures.

    There is no native tree datastructure in python as far as I know.

    Some properties:
    * Inherits 'access-means-creation' functionality from defaultdict:
      ```
       >>> root = TreeNode()
       >>> root['study1']['series1']['instance1'].data = 'some instance info'
       >>> 'study1' in root
       True
      ```
    * Address nodes by nested dict notation or by list of strings:
      ```
      >>> root = TreeNode()
      >>> root['study1']['series1']['instance1'].data = 'some instance info'
      >>> 'study1' in root
      True
      ```

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

    @classmethod
    def init_from_addresses(cls, addresses: Sequence[TreeAddress]):
        """Create TreeNode and make sure all given addresses exist"""
        root = cls()
        for address in addresses:
            root.get_node(address)
        return root

    def iter_leaf_addresses(
        self,
        address_so_far: Tuple[str, ...] = (),
    ) -> Iterator[TreeAddress]:
        """Generate addresses for all this nodes' children, depth-first"""

        if not self.keys():
            yield address_so_far
        else:
            for key in self.keys():
                yield from self[key].iter_leaf_addresses(
                    address_so_far=address_so_far + tuple(key)
                )

    def exists(self, address: TreeAddress) -> bool:
        """Check whether a node exists at address without creating any new nodes

        Parameters
        ----------
        address:
            subsequent keys. To check TreeNode()['a']['b']['c'], use ['a', 'b', 'c'],
            for example
        """
        if not address:
            return True  # required for recursive calls below to work
        else:
            key, address = address[0], address[1:]
            child = self.get(key)
            if child is not None:
                return child.exists(address)  # recurse
            else:
                return False

    def add(self, object_in: Any, address: TreeAddress):
        self.get_node(address).data = object_in

    def copy(self) -> "TreeNode":
        """Create a copy of this node and all children"""
        copied = TreeNode(data=self.data, allow_overwrite=self.allow_overwrite)
        for key, item in self.items():
            copied[key] = item.copy()

        return copied

    def pop_address(self, address: TreeAddress):
        """Pop off the leaf node at this address. Leave stem nodes.

        Raises
        ------
        KeyError
            If node at address does not exist. Follows dict.pop() behaviour.
        """
        if not address:
            raise KeyError("Address was empty. Cannot pop self!")

        key, address = address[0], address[1:]
        try:
            if not address:  # last key in address has been reached. We can pop
                return self.pop(key)
            else:  #
                return self.get_node(tuple(key), create=False).pop_address(
                    address
                )
        except KeyError as e:
            raise KeyError(f"No node found at {address}.{key}") from e

    def prune(self, address: TreeAddress):
        """Remove the node at this address, including any child nodes

        Raises
        ------
        KeyError
            If node at address does not exist
        """
        _ = self.pop_address(address)

    def is_leaf(self):
        return not self.keys()

    def prune_leaf(self, address: TreeAddress):
        """Prune node at this address only if it has no children

        Raises
        ------
        KeyError
            When the referenced node does not exist
        ValueError
            When referenced node is not a leaf (still has child nodes)
        """

        if not address:
            raise KeyError("Address was empty. Cannot prune self!")

        key, address_rest = address[0], address[1:]
        try:
            child = self.get_node((key,), create=False)
        except KeyError as e:
            raise KeyError(
                f"Cannot prune non-existing node at {address}"
            ) from e

        if address_rest:  # more address to traverse. Recurse
            child.prune_leaf(address_rest)
        else:  # no more address. Child should be a leaf
            if child.is_leaf():
                self.pop(key)
            else:
                raise ValueError(f"Node at {address} is not a child node")

    def prune_all(  # noqa: C901  # not too complex I think. Just elifs
        self,
        addresses: List[TreeAddress],
        strategy: PruneStrategy = PruneStrategy.WHERE_POSSIBLE,
    ):
        """Prune the leaf at each address. You can pass non-leaf addresses as well
        provided that all children of this leaf are passed as well.

        Parameters
        ----------
        addresses
            Prune nodes at these locations
        strategy
            Indicates how to handle child nodes and invalid targets.
            See PruneStrategy docstring

        Raises
        ------
        KeyError
            If strategy is PruneStrategy.CHECK_FIRST and illegal addresses are passed.
            Illegal meaning 'would remove unlisted child nodes'
        """
        if strategy == PruneStrategy.FORCE:
            for address in addresses:
                try:
                    self.prune(address)
                except KeyError:
                    continue
        elif strategy == PruneStrategy.WHERE_POSSIBLE:
            for address in addresses:
                try:
                    self.prune_leaf(address)
                except ValueError:
                    continue
        elif strategy == PruneStrategy.CHECK_FIRST:
            # simulate subtree first to avoid leaving tree in half-pruned state after
            # error
            simtree = self.copy()
            addresses.sort(key=lambda x: len(x), reverse=True)
            try:
                for address in addresses:
                    simtree.prune_leaf(address=address)
            except ValueError as e:
                raise KeyError(
                    f"Cannot prune all addresses: {e}. Pruning cancelled"
                ) from e
            # No exceptions. We can safely remove
            for address in addresses:
                self.pop_address(address)
        else:
            raise ValueError(f"Unknown strategy '{strategy}'")

    def get_node(self, address: TreeAddress, create=True):
        """Get node at given address, creating if it does not exist

        Parameters
        ----------
        address
            Address to get
        create: Bool, optional
            If true, create non-existing address. Else, raise exception
             Defaults to True

        Raises
        ------
        KeyError
            If address does not exist and create is False

        Returns
        -------
        TreeNode
            The treenode at this address
        """
        if not address:
            return self
        else:
            key = address[0]
            if not create and key not in self.keys():
                raise KeyError(f"Key {key} not found")
            return self[key].get_node(address[1:], create=create)


class ExpiringCollection:
    """A collection of objects that expires after a set time

    Collects expired items in .expired_items list.
    """

    def __init__(self, expire_after_seconds: int):
        self.expire_after_seconds = expire_after_seconds
        self.stamped_items = LastUpdatedOrderedDict()
        self.expired_items: List[Any] = []

    @staticmethod
    def _now():
        return datetime.now()

    def add(self, item):
        self.stamped_items[item] = self._now()

    def add_all(self, items: Iterable[Hashable]):
        for item in items:
            self.add(item)

    @property
    def items(self):
        self.check_expired()
        return list(self.stamped_items.keys())

    def check_expired(self):
        """Move expired to expired_items list"""
        expired = []
        for item, timestamp in self.stamped_items.items():
            if (self._now() - timestamp).seconds > self.expire_after_seconds:
                expired.append(item)
            else:
                break  # timestamps should be ordered so we can stop checking

        self.expired_items = self.expired_items + expired
        [self.stamped_items.pop(x) for x in expired]

    def collect_expired(self) -> List[Hashable]:
        """Returns all expired items and removes them from local list"""
        self.check_expired()
        expired = self.expired_items
        self.expired_items = []
        return expired


class LastUpdatedOrderedDict(OrderedDictType[Any, Any]):
    """Store items in the order the keys were last added"""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
