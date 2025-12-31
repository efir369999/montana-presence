"""
ATC Protocol v7 Fork Choice Rule
Part X of Technical Specification

Chain selection based on cumulative score weight.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, TYPE_CHECKING

from atc.constants import (
    FORK_CHOICE_DEPTH,
    FINALITY_DEPTH,
    MAX_REORG_DEPTH,
)
from atc.core.types import Hash
from atc.consensus.score import compute_block_weight

if TYPE_CHECKING:
    from atc.core.block import Block
    from atc.core.state import GlobalState

logger = logging.getLogger(__name__)


def chain_weight(blocks: List["Block"]) -> float:
    """
    Compute total weight of a chain.

    Per specification (Part X):
    Chain weight = Σ(block_weights)
    Block weight = Σ(signer_scores)

    Args:
        blocks: List of blocks in the chain

    Returns:
        Total chain weight
    """
    total = 0.0
    for block in blocks:
        total += compute_block_weight(block.signers)
    return total


def select_best_chain(
    chains: List[List["Block"]],
    state: "GlobalState"
) -> int:
    """
    Select the best chain using the fork choice rule.

    Per specification (Part X):
    - Primary: Highest cumulative weight
    - Tiebreaker 1: Longest chain
    - Tiebreaker 2: Lowest block hash (deterministic)

    Args:
        chains: List of candidate chains
        state: Current global state

    Returns:
        Index of the best chain
    """
    if not chains:
        raise ValueError("No chains provided")

    if len(chains) == 1:
        return 0

    best_idx = 0
    best_weight = chain_weight(chains[0])
    best_length = len(chains[0])
    best_tip_hash = chains[0][-1].block_hash() if chains[0] else Hash.zero()

    for i, chain in enumerate(chains[1:], 1):
        weight = chain_weight(chain)
        length = len(chain)
        tip_hash = chain[-1].block_hash() if chain else Hash.zero()

        # Primary comparison: weight
        if weight > best_weight:
            best_idx = i
            best_weight = weight
            best_length = length
            best_tip_hash = tip_hash
        elif weight == best_weight:
            # Tiebreaker 1: length
            if length > best_length:
                best_idx = i
                best_weight = weight
                best_length = length
                best_tip_hash = tip_hash
            elif length == best_length:
                # Tiebreaker 2: lowest hash (deterministic)
                if tip_hash.data < best_tip_hash.data:
                    best_idx = i
                    best_weight = weight
                    best_length = length
                    best_tip_hash = tip_hash

    return best_idx


@dataclass
class ChainHead:
    """Represents a chain head (tip of a branch)."""
    block_hash: Hash
    height: int
    weight: float
    parent_hash: Hash


@dataclass
class ForkChoiceRule:
    """
    Fork choice rule implementation with chain tracking.

    Maintains multiple chain heads and selects the best one
    based on cumulative weight.
    """
    # Current best chain tip
    best_tip: Optional[Hash] = None
    best_weight: float = 0.0
    best_height: int = 0

    # All known chain heads
    heads: Dict[bytes, ChainHead] = field(default_factory=dict)

    # Block to weight mapping (for efficient reorg calculation)
    block_weights: Dict[bytes, float] = field(default_factory=dict)

    # Parent hash mapping
    parent_map: Dict[bytes, Hash] = field(default_factory=dict)

    # Height mapping
    height_map: Dict[bytes, int] = field(default_factory=dict)

    # Finalized blocks (cannot be reorged)
    finalized: Set[bytes] = field(default_factory=set)

    def add_block(self, block: "Block") -> bool:
        """
        Add a new block and update fork choice.

        Args:
            block: Block to add

        Returns:
            True if this block is on the best chain
        """
        block_hash = block.block_hash()
        hash_bytes = block_hash.data
        parent_bytes = block.header.parent_hash.data

        # Calculate block weight
        weight = compute_block_weight(block.signers)
        self.block_weights[hash_bytes] = weight

        # Store mappings
        self.parent_map[hash_bytes] = block.header.parent_hash
        self.height_map[hash_bytes] = block.header.height

        # Calculate cumulative weight to this block
        cumulative_weight = self._get_cumulative_weight(hash_bytes)

        # Update heads
        # Remove parent from heads if it was a head
        if parent_bytes in self.heads:
            del self.heads[parent_bytes]

        # Add this block as a head
        self.heads[hash_bytes] = ChainHead(
            block_hash=block_hash,
            height=block.header.height,
            weight=cumulative_weight,
            parent_hash=block.header.parent_hash
        )

        # Check if this is the new best
        is_best = self._update_best(block_hash, cumulative_weight, block.header.height)

        # Update finality
        self._update_finality(block.header.height)

        return is_best

    def _get_cumulative_weight(self, block_hash: bytes) -> float:
        """Get cumulative weight from genesis to this block."""
        total = 0.0
        current = block_hash

        while current in self.block_weights:
            total += self.block_weights[current]
            if current in self.parent_map:
                current = self.parent_map[current].data
            else:
                break

        return total

    def _update_best(
        self,
        block_hash: Hash,
        weight: float,
        height: int
    ) -> bool:
        """Update best chain if this block is better."""
        is_better = False

        if weight > self.best_weight:
            is_better = True
        elif weight == self.best_weight:
            if height > self.best_height:
                is_better = True
            elif height == self.best_height:
                # Tiebreaker: lowest hash
                if self.best_tip is None or block_hash.data < self.best_tip.data:
                    is_better = True

        if is_better:
            self.best_tip = block_hash
            self.best_weight = weight
            self.best_height = height
            logger.debug(
                f"New best chain: height={height}, weight={weight:.4f}, "
                f"tip={block_hash.hex()[:16]}"
            )

        return is_better

    def _update_finality(self, current_height: int) -> None:
        """Mark blocks as finalized based on depth."""
        finality_height = current_height - FINALITY_DEPTH

        if finality_height <= 0:
            return

        # Find blocks at or below finality height on the best chain
        if self.best_tip is None:
            return

        current = self.best_tip.data
        while current in self.height_map:
            height = self.height_map[current]
            if height <= finality_height:
                if current not in self.finalized:
                    self.finalized.add(current)
                    logger.debug(f"Block finalized at height {height}")
            if current in self.parent_map:
                current = self.parent_map[current].data
            else:
                break

    def get_best_chain(self) -> Optional[Hash]:
        """Get the current best chain tip."""
        return self.best_tip

    def get_heads(self) -> List[ChainHead]:
        """Get all current chain heads."""
        return list(self.heads.values())

    def is_finalized(self, block_hash: Hash) -> bool:
        """Check if a block is finalized."""
        return block_hash.data in self.finalized

    def can_reorg_to(self, block_hash: Hash) -> bool:
        """
        Check if a reorg to this block is allowed.

        Per specification:
        - Cannot reorg past finalized blocks
        - Cannot reorg deeper than MAX_REORG_DEPTH
        """
        if block_hash.data not in self.height_map:
            return False

        target_height = self.height_map[block_hash.data]

        # Check finality
        if any(
            self.height_map.get(h, 0) >= target_height
            for h in self.finalized
        ):
            return False

        # Check reorg depth
        if self.best_height - target_height > MAX_REORG_DEPTH:
            return False

        return True

    def get_common_ancestor(
        self,
        hash1: Hash,
        hash2: Hash
    ) -> Optional[Hash]:
        """
        Find the common ancestor of two blocks.

        Args:
            hash1: First block hash
            hash2: Second block hash

        Returns:
            Hash of common ancestor or None
        """
        # Build ancestor sets
        ancestors1: Set[bytes] = set()
        current = hash1.data
        while current in self.parent_map:
            ancestors1.add(current)
            current = self.parent_map[current].data
        ancestors1.add(current)

        # Walk up from hash2 until we find a common ancestor
        current = hash2.data
        while current not in ancestors1:
            if current not in self.parent_map:
                return None
            current = self.parent_map[current].data

        if current in self.height_map:
            return Hash(current)
        return None

    def get_fork_point(self, new_tip: Hash) -> Optional[Hash]:
        """
        Get the fork point between current best and a new tip.

        Args:
            new_tip: Proposed new chain tip

        Returns:
            Hash of fork point
        """
        if self.best_tip is None:
            return None

        return self.get_common_ancestor(self.best_tip, new_tip)

    def get_reorg_blocks(
        self,
        new_tip: Hash
    ) -> tuple:
        """
        Get blocks to remove and add for a reorg.

        Args:
            new_tip: New chain tip

        Returns:
            Tuple of (blocks_to_remove, blocks_to_add) as lists of hashes
        """
        if self.best_tip is None:
            # No current chain, just add
            to_add = []
            current = new_tip.data
            while current in self.parent_map:
                to_add.append(Hash(current))
                current = self.parent_map[current].data
            to_add.append(Hash(current))
            return [], list(reversed(to_add))

        fork_point = self.get_fork_point(new_tip)
        if fork_point is None:
            return [], []

        # Blocks to remove (from best tip to fork point)
        to_remove = []
        current = self.best_tip.data
        while current != fork_point.data:
            to_remove.append(Hash(current))
            if current in self.parent_map:
                current = self.parent_map[current].data
            else:
                break

        # Blocks to add (from new tip to fork point)
        to_add = []
        current = new_tip.data
        while current != fork_point.data:
            to_add.append(Hash(current))
            if current in self.parent_map:
                current = self.parent_map[current].data
            else:
                break

        return to_remove, list(reversed(to_add))

    def clear(self) -> None:
        """Clear all state."""
        self.best_tip = None
        self.best_weight = 0.0
        self.best_height = 0
        self.heads.clear()
        self.block_weights.clear()
        self.parent_map.clear()
        self.height_map.clear()
        self.finalized.clear()


def compute_fork_quality(
    fork_blocks: List["Block"],
    main_blocks: List["Block"]
) -> float:
    """
    Compare quality of a fork vs main chain.

    Returns ratio of fork weight to main weight.

    Args:
        fork_blocks: Blocks on the fork
        main_blocks: Corresponding blocks on main chain

    Returns:
        Quality ratio (>1.0 means fork is better)
    """
    fork_weight = chain_weight(fork_blocks)
    main_weight = chain_weight(main_blocks)

    if main_weight == 0:
        return float('inf') if fork_weight > 0 else 1.0

    return fork_weight / main_weight


def should_switch_chain(
    current_weight: float,
    candidate_weight: float,
    reorg_depth: int
) -> bool:
    """
    Determine if we should switch to a candidate chain.

    Per specification (Part X):
    - Candidate must have higher weight
    - Deeper reorgs require proportionally higher weight advantage

    Args:
        current_weight: Weight of current best chain
        candidate_weight: Weight of candidate chain
        reorg_depth: How many blocks would be reorged

    Returns:
        True if we should switch
    """
    if candidate_weight <= current_weight:
        return False

    if reorg_depth > MAX_REORG_DEPTH:
        return False

    # Require higher advantage for deeper reorgs
    # Each block of depth requires 0.1% additional advantage
    required_advantage = 1.0 + (reorg_depth * 0.001)
    actual_advantage = candidate_weight / current_weight if current_weight > 0 else float('inf')

    return actual_advantage >= required_advantage


def get_fork_choice_info() -> dict:
    """Get information about fork choice rule."""
    return {
        "rule": "Heaviest chain (cumulative score)",
        "tiebreakers": ["chain length", "lowest tip hash"],
        "fork_choice_depth": FORK_CHOICE_DEPTH,
        "finality_depth": FINALITY_DEPTH,
        "max_reorg_depth": MAX_REORG_DEPTH,
    }
