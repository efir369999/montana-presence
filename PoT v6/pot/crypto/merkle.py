"""
PoT Protocol v6 Merkle Tree
Part XII of Technical Specification

Binary Merkle tree with SHA3-256 for block content commitment.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
from dataclasses import dataclass

from pot.core.types import Hash
from pot.crypto.hash import sha3_256, sha3_256_raw


def is_power_of_two(n: int) -> bool:
    """Check if n is a power of 2."""
    return n > 0 and (n & (n - 1)) == 0


def next_power_of_two(n: int) -> int:
    """Return the smallest power of 2 >= n."""
    if n <= 0:
        return 1
    n -= 1
    n |= n >> 1
    n |= n >> 2
    n |= n >> 4
    n |= n >> 8
    n |= n >> 16
    n |= n >> 32
    return n + 1


def merkle_root(hashes: List[Hash]) -> Hash:
    """
    Compute Merkle root from a list of hashes.

    Per specification:
    - Empty list returns zero hash
    - Single element returns that element
    - Otherwise, pad to power of 2 and build tree bottom-up

    Args:
        hashes: List of leaf hashes

    Returns:
        Merkle root hash
    """
    if len(hashes) == 0:
        return Hash.zero()

    if len(hashes) == 1:
        return hashes[0]

    # Make a mutable copy
    leaves = list(hashes)

    # Pad to power of 2 by duplicating last element
    while not is_power_of_two(len(leaves)):
        leaves.append(leaves[-1])

    # Build tree bottom-up
    while len(leaves) > 1:
        next_level = []
        for i in range(0, len(leaves), 2):
            combined = leaves[i].data + leaves[i + 1].data
            next_level.append(sha3_256(combined))
        leaves = next_level

    return leaves[0]


@dataclass
class MerkleProof:
    """
    Merkle inclusion proof.

    Contains the sibling hashes and position flags needed to
    reconstruct the root from a leaf.
    """
    leaf: Hash
    siblings: List[Hash]
    # For each sibling, True if sibling is on the right
    sibling_positions: List[bool]

    def verify(self, root: Hash) -> bool:
        """
        Verify this proof against the expected root.

        Args:
            root: Expected Merkle root

        Returns:
            True if proof is valid
        """
        current = self.leaf

        for sibling, is_right in zip(self.siblings, self.sibling_positions):
            if is_right:
                combined = current.data + sibling.data
            else:
                combined = sibling.data + current.data
            current = sha3_256(combined)

        return current == root

    def serialize(self) -> bytes:
        """Serialize proof to bytes."""
        from pot.core.serialization import serialize_varint

        parts = [
            self.leaf.serialize(),
            serialize_varint(len(self.siblings)),
        ]

        for sibling, is_right in zip(self.siblings, self.sibling_positions):
            parts.append(bytes([1 if is_right else 0]))
            parts.append(sibling.serialize())

        return b"".join(parts)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["MerkleProof", int]:
        """Deserialize proof from bytes."""
        from pot.core.serialization import deserialize_varint

        leaf, consumed = Hash.deserialize(data, offset)
        pos = offset + consumed

        count, consumed = deserialize_varint(data, pos)
        pos += consumed

        siblings = []
        sibling_positions = []

        for _ in range(count):
            is_right = data[pos] == 1
            pos += 1

            sibling, consumed = Hash.deserialize(data, pos)
            pos += consumed

            siblings.append(sibling)
            sibling_positions.append(is_right)

        return cls(leaf=leaf, siblings=siblings, sibling_positions=sibling_positions), pos - offset


class MerkleTree:
    """
    Complete Merkle tree with proof generation.
    """

    def __init__(self, leaves: List[Hash]):
        """
        Build a Merkle tree from leaf hashes.

        Args:
            leaves: List of leaf hashes (must be non-empty for proofs)
        """
        self._original_leaves = list(leaves)
        self._leaves: List[Hash] = []
        self._levels: List[List[Hash]] = []

        if len(leaves) == 0:
            self._root = Hash.zero()
            return

        if len(leaves) == 1:
            self._leaves = list(leaves)
            self._levels = [self._leaves]
            self._root = leaves[0]
            return

        # Pad to power of 2
        self._leaves = list(leaves)
        while not is_power_of_two(len(self._leaves)):
            self._leaves.append(self._leaves[-1])

        # Build all levels
        self._levels = [self._leaves]
        current = self._leaves

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                combined = current[i].data + current[i + 1].data
                next_level.append(sha3_256(combined))
            self._levels.append(next_level)
            current = next_level

        self._root = current[0]

    @property
    def root(self) -> Hash:
        """Return the Merkle root."""
        return self._root

    @property
    def leaf_count(self) -> int:
        """Return the original number of leaves (before padding)."""
        return len(self._original_leaves)

    @property
    def padded_leaf_count(self) -> int:
        """Return the number of leaves after padding."""
        return len(self._leaves)

    @property
    def height(self) -> int:
        """Return the tree height (number of levels)."""
        return len(self._levels)

    def get_proof(self, index: int) -> Optional[MerkleProof]:
        """
        Generate a Merkle proof for the leaf at the given index.

        Args:
            index: Index of the leaf (0-based, in original list)

        Returns:
            MerkleProof if index is valid, None otherwise
        """
        if index < 0 or index >= len(self._original_leaves):
            return None

        if len(self._original_leaves) == 1:
            return MerkleProof(
                leaf=self._original_leaves[0],
                siblings=[],
                sibling_positions=[]
            )

        siblings = []
        sibling_positions = []
        current_index = index

        for level in self._levels[:-1]:  # Exclude root level
            # Find sibling index
            if current_index % 2 == 0:
                sibling_index = current_index + 1
                is_right = True
            else:
                sibling_index = current_index - 1
                is_right = False

            siblings.append(level[sibling_index])
            sibling_positions.append(is_right)

            # Move to parent index
            current_index //= 2

        return MerkleProof(
            leaf=self._original_leaves[index],
            siblings=siblings,
            sibling_positions=sibling_positions
        )

    def verify_proof(self, proof: MerkleProof) -> bool:
        """
        Verify a Merkle proof against this tree's root.

        Args:
            proof: Merkle proof to verify

        Returns:
            True if proof is valid
        """
        return proof.verify(self._root)

    def contains(self, leaf: Hash) -> bool:
        """
        Check if a leaf is in the original tree.

        Args:
            leaf: Hash to check

        Returns:
            True if leaf is in the tree
        """
        return leaf in self._original_leaves

    def find_index(self, leaf: Hash) -> Optional[int]:
        """
        Find the index of a leaf in the original list.

        Args:
            leaf: Hash to find

        Returns:
            Index if found, None otherwise
        """
        try:
            return self._original_leaves.index(leaf)
        except ValueError:
            return None


def compute_merkle_root_incremental(hashes: List[Hash]) -> Hash:
    """
    Compute Merkle root incrementally (memory-efficient for large trees).

    This version doesn't store the full tree, just computes the root.
    Uses the same algorithm as merkle_root() but more explicitly.

    Args:
        hashes: List of leaf hashes

    Returns:
        Merkle root hash
    """
    if len(hashes) == 0:
        return Hash.zero()

    if len(hashes) == 1:
        return hashes[0]

    # Pad to power of 2
    padded_count = next_power_of_two(len(hashes))
    current = list(hashes)
    while len(current) < padded_count:
        current.append(current[-1])

    # Process level by level
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            combined = current[i].data + current[i + 1].data
            next_level.append(sha3_256(combined))
        current = next_level

    return current[0]
