"""
Ɉ Montana Finality Accumulator v3.5

Layer 2: UTC Finality per MONTANA_TECHNICAL_SPECIFICATION.md §6.

Implements three finality levels through UTC time boundaries:
- Soft:   1 boundary  (1 minute)  - Block included in checkpoint
- Medium: 2 boundaries (2 minutes) - High certainty
- Hard:   3 boundaries (3 minutes) - Maximum security

Class Group VDF (Wesolowski 2019) proves participation within a time window.
Hardware advantage eliminated — fast hardware waits for UTC boundary.

UTC Quantum Neutralization:
- Quantum attacker computes VDF in 0.001 sec → waits 59.999 sec → 1 heartbeat
- Classical node computes VDF in 30 sec → waits 30 sec → 1 heartbeat
- UTC boundary is the rate limiter, VDF speed is irrelevant

Security: Type B (mathematical reduction to class group order problem)
"""

from __future__ import annotations
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import IntEnum

from montana.constants import (
    VDF_CHECKPOINT_TIME_SEC,
    FINALITY_SOFT_CHECKPOINTS,
    FINALITY_MEDIUM_CHECKPOINTS,
    FINALITY_HARD_CHECKPOINTS,
    VDF_BASE_ITERATIONS,
    TIME_TOLERANCE_SEC,
    FINALITY_INTERVAL_SEC,
)
from montana.core.types import Hash
from montana.core.vdf import VDFOutput, VDFProof, ClassGroupVDF, get_vdf

logger = logging.getLogger(__name__)


class FinalityLevel(IntEnum):
    """
    Finality levels per §6.2.

    Each level represents accumulated VDF checkpoints providing
    increasing confidence in temporal ordering.
    """
    NONE = 0      # No finality (pending)
    SOFT = 1      # 1 checkpoint (~2.5s)
    MEDIUM = 2    # 100 checkpoints (~4min)
    HARD = 3      # 1000 checkpoints (~40min)


@dataclass
class FinalityThresholds:
    """Checkpoint thresholds for each finality level."""
    soft: int = FINALITY_SOFT_CHECKPOINTS      # 1
    medium: int = FINALITY_MEDIUM_CHECKPOINTS  # 100
    hard: int = FINALITY_HARD_CHECKPOINTS      # 1000


@dataclass
class AccumulatedState:
    """
    Accumulated VDF state for a block or transaction.

    Tracks the accumulation of VDF checkpoints to determine
    current finality level.
    """
    block_hash: Hash                           # Block this state belongs to
    initial_vdf_output: Hash                   # VDF output at block creation
    accumulated_checkpoints: int = 0           # Total accumulated checkpoints
    last_checkpoint_time: float = 0.0          # Timestamp of last checkpoint
    proofs: List[VDFProof] = field(default_factory=list)  # Accumulated proofs

    @property
    def finality_level(self) -> FinalityLevel:
        """Determine current finality level from accumulated checkpoints."""
        if self.accumulated_checkpoints >= FINALITY_HARD_CHECKPOINTS:
            return FinalityLevel.HARD
        elif self.accumulated_checkpoints >= FINALITY_MEDIUM_CHECKPOINTS:
            return FinalityLevel.MEDIUM
        elif self.accumulated_checkpoints >= FINALITY_SOFT_CHECKPOINTS:
            return FinalityLevel.SOFT
        return FinalityLevel.NONE

    @property
    def estimated_time_to_hard(self) -> float:
        """Estimate seconds until hard finality."""
        remaining = FINALITY_HARD_CHECKPOINTS - self.accumulated_checkpoints
        if remaining <= 0:
            return 0.0
        return remaining * VDF_CHECKPOINT_TIME_SEC

    def add_checkpoint(self, proof: VDFProof) -> FinalityLevel:
        """
        Add a VDF checkpoint and return new finality level.

        Args:
            proof: VDF proof for this checkpoint

        Returns:
            Current finality level after adding checkpoint
        """
        self.accumulated_checkpoints += 1
        self.last_checkpoint_time = time.time()
        self.proofs.append(proof)
        return self.finality_level


class VDFAccumulator:
    """
    VDF checkpoint accumulator for finality per §6.

    Manages the accumulation of VDF checkpoints across blocks,
    computing finality levels and chain selection.
    """

    def __init__(
        self,
        thresholds: Optional[FinalityThresholds] = None,
        vdf: Optional[ClassGroupVDF] = None,
    ):
        """
        Initialize accumulator.

        Args:
            thresholds: Custom finality thresholds
            vdf: VDF instance to use (defaults to global)
        """
        self.thresholds = thresholds or FinalityThresholds()
        self.vdf = vdf or get_vdf()

        # State tracking per block
        self._states: Dict[Hash, AccumulatedState] = {}

        # Current chain tip
        self._chain_tip: Optional[Hash] = None

    def register_block(self, block_hash: Hash, vdf_output: Hash) -> AccumulatedState:
        """
        Register a new block for finality tracking.

        Args:
            block_hash: Hash of the block
            vdf_output: VDF output included in block

        Returns:
            New AccumulatedState for the block
        """
        if block_hash in self._states:
            return self._states[block_hash]

        state = AccumulatedState(
            block_hash=block_hash,
            initial_vdf_output=vdf_output,
            last_checkpoint_time=time.time(),
        )
        self._states[block_hash] = state

        logger.debug(f"Registered block {block_hash.hex()[:16]} for finality tracking")
        return state

    def add_checkpoint(self, block_hash: Hash, proof: VDFProof) -> Optional[FinalityLevel]:
        """
        Add a VDF checkpoint to a block's finality.

        Args:
            block_hash: Block to add checkpoint to
            proof: VDF proof for this checkpoint

        Returns:
            New finality level, or None if block not found
        """
        state = self._states.get(block_hash)
        if state is None:
            logger.warning(f"Block {block_hash.hex()[:16]} not registered")
            return None

        # Verify proof chains from previous state
        if state.proofs:
            last_proof = state.proofs[-1]
            if proof.input_hash != last_proof.output_hash:
                logger.warning("VDF proof doesn't chain from previous output")
                return None
        else:
            if proof.input_hash != state.initial_vdf_output:
                logger.warning("VDF proof doesn't chain from block VDF output")
                return None

        # Verify the proof itself
        if not self.vdf.verify_proof(proof):
            logger.warning("VDF proof verification failed")
            return None

        # Add checkpoint
        old_level = state.finality_level
        new_level = state.add_checkpoint(proof)

        if new_level != old_level:
            logger.info(
                f"Block {block_hash.hex()[:16]} reached {new_level.name} finality "
                f"({state.accumulated_checkpoints} checkpoints)"
            )

        return new_level

    def get_finality(self, block_hash: Hash) -> FinalityLevel:
        """Get current finality level for a block."""
        state = self._states.get(block_hash)
        if state is None:
            return FinalityLevel.NONE
        return state.finality_level

    def get_state(self, block_hash: Hash) -> Optional[AccumulatedState]:
        """Get accumulated state for a block."""
        return self._states.get(block_hash)

    def compare_finality(self, hash_a: Hash, hash_b: Hash) -> int:
        """
        Compare finality between two blocks.

        Returns:
            1 if A has more finality, -1 if B has more, 0 if equal
        """
        level_a = self.get_finality(hash_a)
        level_b = self.get_finality(hash_b)

        if level_a > level_b:
            return 1
        elif level_b > level_a:
            return -1

        # Same level - compare checkpoint counts
        state_a = self._states.get(hash_a)
        state_b = self._states.get(hash_b)

        if state_a and state_b:
            if state_a.accumulated_checkpoints > state_b.accumulated_checkpoints:
                return 1
            elif state_b.accumulated_checkpoints > state_a.accumulated_checkpoints:
                return -1

        return 0

    def select_chain_tip(self, candidates: List[Hash]) -> Optional[Hash]:
        """
        Select chain tip from candidates based on accumulated finality.

        This implements the fork choice rule per §6.3:
        "The chain with the most accumulated VDF work is canonical."

        Args:
            candidates: List of candidate block hashes

        Returns:
            Hash of the block with most accumulated finality
        """
        if not candidates:
            return None

        best = candidates[0]
        for candidate in candidates[1:]:
            if self.compare_finality(candidate, best) > 0:
                best = candidate

        self._chain_tip = best
        return best

    def prune_old_states(self, keep_hashes: set[Hash]) -> int:
        """
        Remove states for blocks not in keep_hashes.

        Args:
            keep_hashes: Set of block hashes to keep

        Returns:
            Number of states pruned
        """
        to_remove = [h for h in self._states if h not in keep_hashes]
        for h in to_remove:
            del self._states[h]
        return len(to_remove)

    @property
    def chain_tip(self) -> Optional[Hash]:
        """Current chain tip based on finality."""
        return self._chain_tip

    def get_finality_stats(self) -> Dict[str, int]:
        """Get statistics about tracked blocks by finality level."""
        stats = {level.name: 0 for level in FinalityLevel}
        for state in self._states.values():
            stats[state.finality_level.name] += 1
        return stats


# Global accumulator instance
_accumulator: Optional[VDFAccumulator] = None


def get_accumulator() -> VDFAccumulator:
    """Get or create global VDF accumulator."""
    global _accumulator
    if _accumulator is None:
        _accumulator = VDFAccumulator()
    return _accumulator


def get_finality_time(level: FinalityLevel) -> float:
    """
    Get expected time to reach finality level (UTC model).

    Args:
        level: Target finality level

    Returns:
        Expected time in seconds
    """
    # UTC finality: 1 boundary = 1 minute
    boundaries = {
        FinalityLevel.NONE: 0,
        FinalityLevel.SOFT: 1,      # 1 minute
        FinalityLevel.MEDIUM: 2,    # 2 minutes
        FinalityLevel.HARD: 3,      # 3 minutes
    }
    return boundaries.get(level, 0) * FINALITY_INTERVAL_SEC


# ==============================================================================
# UTC FINALITY CHECKPOINT (v3.4)
# ==============================================================================

@dataclass
class FinalityCheckpoint:
    """
    Finality checkpoint at UTC boundary per §6.6.

    Created every FINALITY_INTERVAL_SEC (1 minute) at UTC boundaries.
    Contains all blocks and heartbeats from the time window.
    """
    boundary_timestamp_ms: int      # UTC boundary (e.g., 00:10:00.000)
    blocks_merkle_root: bytes       # 32 bytes - Merkle root of blocks in window
    vdf_proofs_root: bytes          # 32 bytes - Merkle root of VDF proofs
    participants_count: int         # Number of participating nodes (heartbeats)
    total_vdf_iterations: int       # Sum of all VDF iterations in window
    aggregate_score: int            # Sum of participant scores (√heartbeats history)
    previous_checkpoint_hash: bytes # 32 bytes - Hash of previous checkpoint

    def checkpoint_hash(self) -> bytes:
        """Compute SHA3-256 hash of checkpoint."""
        from montana.crypto.hash import sha3_256_raw
        data = (
            self.boundary_timestamp_ms.to_bytes(8, 'big') +
            self.blocks_merkle_root +
            self.vdf_proofs_root +
            self.participants_count.to_bytes(4, 'big') +
            self.total_vdf_iterations.to_bytes(8, 'big') +
            self.aggregate_score.to_bytes(8, 'big') +
            self.previous_checkpoint_hash
        )
        return sha3_256_raw(data)


def resolve_checkpoint_conflict(
    checkpoint_a: FinalityCheckpoint,
    checkpoint_b: FinalityCheckpoint
) -> FinalityCheckpoint:
    """
    Resolve conflicting checkpoints at the same UTC boundary.

    Cascade tiebreakers per §6.9 (each level has semantic meaning):
    1. More participants (heartbeats) → larger active network
    2. Higher total VDF iterations → more proven time
    3. Higher aggregate score → more reliable participants
    4. Lower checkpoint hash → deterministic last resort

    Level 4 is reached only with perfect 50/50, identical participants,
    identical VDF. Probability → 0.

    Args:
        checkpoint_a: First checkpoint
        checkpoint_b: Second checkpoint

    Returns:
        Canonical checkpoint
    """
    # Must be same UTC boundary
    if checkpoint_a.boundary_timestamp_ms != checkpoint_b.boundary_timestamp_ms:
        raise ValueError("Checkpoints must be at same UTC boundary")

    cp_a, cp_b = checkpoint_a, checkpoint_b

    # 1. More participants → larger active network
    if cp_a.participants_count != cp_b.participants_count:
        return max(cp_a, cp_b, key=lambda c: c.participants_count)

    # 2. More VDF iterations → more proven time
    if cp_a.total_vdf_iterations != cp_b.total_vdf_iterations:
        return max(cp_a, cp_b, key=lambda c: c.total_vdf_iterations)

    # 3. Higher aggregate score → more reliable participants
    if cp_a.aggregate_score != cp_b.aggregate_score:
        return max(cp_a, cp_b, key=lambda c: c.aggregate_score)

    # 4. Hash — only if ALL equal (astronomically rare)
    return min(cp_a, cp_b, key=lambda c: c.checkpoint_hash())


def get_utc_finality_level(block_timestamp_ms: int, current_time_ms: int) -> FinalityLevel:
    """
    Determine finality level based on UTC boundaries passed.

    Args:
        block_timestamp_ms: When block was created
        current_time_ms: Current UTC time

    Returns:
        Current finality level
    """
    # Calculate which boundary the block belongs to
    boundary_ms = FINALITY_INTERVAL_SEC * 1000
    block_boundary = (block_timestamp_ms // boundary_ms) * boundary_ms
    current_boundary = (current_time_ms // boundary_ms) * boundary_ms

    # Count boundaries passed
    boundaries_passed = (current_boundary - block_boundary) // boundary_ms

    if boundaries_passed >= 3:
        return FinalityLevel.HARD
    elif boundaries_passed >= 2:
        return FinalityLevel.MEDIUM
    elif boundaries_passed >= 1:
        return FinalityLevel.SOFT
    return FinalityLevel.NONE


def is_within_time_tolerance(timestamp_ms: int, reference_ms: int) -> bool:
    """
    Check if timestamp is within ±TIME_TOLERANCE_SEC of reference.

    Args:
        timestamp_ms: Timestamp to check
        reference_ms: Reference time (usually local UTC)

    Returns:
        True if within tolerance
    """
    tolerance_ms = TIME_TOLERANCE_SEC * 1000
    return abs(timestamp_ms - reference_ms) <= tolerance_ms


def get_next_boundary_ms(current_time_ms: int) -> int:
    """
    Get the next UTC finality boundary timestamp.

    Args:
        current_time_ms: Current UTC time in milliseconds

    Returns:
        Next boundary timestamp in milliseconds
    """
    boundary_ms = FINALITY_INTERVAL_SEC * 1000
    return ((current_time_ms // boundary_ms) + 1) * boundary_ms


def get_current_boundary_ms(current_time_ms: int) -> int:
    """
    Get the current UTC finality boundary timestamp.

    Args:
        current_time_ms: Current UTC time in milliseconds

    Returns:
        Current boundary timestamp in milliseconds
    """
    boundary_ms = FINALITY_INTERVAL_SEC * 1000
    return (current_time_ms // boundary_ms) * boundary_ms


# ==============================================================================
# MERKLE TREE UTILITIES
# ==============================================================================

EMPTY_HASH = b'\x00' * 32


def compute_merkle_root(hashes: List[bytes]) -> bytes:
    """
    Compute Merkle root from list of hashes.

    Args:
        hashes: List of 32-byte hashes

    Returns:
        32-byte Merkle root
    """
    from montana.crypto.hash import sha3_256_raw

    if not hashes:
        return EMPTY_HASH

    if len(hashes) == 1:
        return hashes[0]

    # Pad to even length
    layer = list(hashes)
    if len(layer) % 2 == 1:
        layer.append(layer[-1])

    # Build tree bottom-up
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            next_layer.append(sha3_256_raw(combined))
        layer = next_layer
        if len(layer) > 1 and len(layer) % 2 == 1:
            layer.append(layer[-1])

    return layer[0]


# ==============================================================================
# CHECKPOINT CREATION (v3.5)
# ==============================================================================

@dataclass
class HeartbeatData:
    """
    Minimal heartbeat data for checkpoint creation.

    Used to aggregate heartbeat information without requiring
    full heartbeat objects.
    """
    node_id: bytes              # 32 bytes
    vdf_iterations: int         # VDF iterations (0 for light heartbeats)
    participant_score: int      # Score with precision scaling
    vdf_proof_hash: bytes       # Hash of VDF proof (or empty for light)

    @classmethod
    def from_full_heartbeat(
        cls,
        heartbeat: "FullHeartbeat",
        score: int
    ) -> "HeartbeatData":
        """Create from FullHeartbeat."""
        from montana.crypto.hash import sha3_256_raw
        return cls(
            node_id=heartbeat.node_id.data,
            vdf_iterations=heartbeat.vdf_iterations,
            participant_score=score,
            vdf_proof_hash=sha3_256_raw(heartbeat.vdf_proof),
        )

    @classmethod
    def from_light_heartbeat(
        cls,
        heartbeat: "LightHeartbeat",
        score: int
    ) -> "HeartbeatData":
        """Create from LightHeartbeat."""
        return cls(
            node_id=heartbeat.node_id.data,
            vdf_iterations=0,
            participant_score=score,
            vdf_proof_hash=EMPTY_HASH,
        )


def create_finality_checkpoint(
    boundary_timestamp_ms: int,
    block_hashes: List[bytes],
    heartbeat_data: List[HeartbeatData],
    previous_checkpoint_hash: bytes,
) -> FinalityCheckpoint:
    """
    Create a finality checkpoint from blocks and heartbeats at UTC boundary.

    Args:
        boundary_timestamp_ms: UTC boundary timestamp (must be aligned)
        block_hashes: List of block hashes in the finality window
        heartbeat_data: List of HeartbeatData from all participants
        previous_checkpoint_hash: Hash of previous checkpoint (EMPTY_HASH for genesis)

    Returns:
        New FinalityCheckpoint

    Raises:
        ValueError: If timestamp is not aligned to boundary
    """
    boundary_ms = FINALITY_INTERVAL_SEC * 1000
    if boundary_timestamp_ms % boundary_ms != 0:
        raise ValueError(
            f"Timestamp {boundary_timestamp_ms} is not aligned to "
            f"{FINALITY_INTERVAL_SEC}s boundary"
        )

    # Compute blocks merkle root
    blocks_merkle_root = compute_merkle_root(block_hashes) if block_hashes else EMPTY_HASH

    # Compute VDF proofs merkle root
    vdf_proof_hashes = [h.vdf_proof_hash for h in heartbeat_data if h.vdf_proof_hash != EMPTY_HASH]
    vdf_proofs_root = compute_merkle_root(vdf_proof_hashes) if vdf_proof_hashes else EMPTY_HASH

    # Aggregate heartbeat data
    participants_count = len(heartbeat_data)
    total_vdf_iterations = sum(h.vdf_iterations for h in heartbeat_data)
    aggregate_score = sum(h.participant_score for h in heartbeat_data)

    return FinalityCheckpoint(
        boundary_timestamp_ms=boundary_timestamp_ms,
        blocks_merkle_root=blocks_merkle_root,
        vdf_proofs_root=vdf_proofs_root,
        participants_count=participants_count,
        total_vdf_iterations=total_vdf_iterations,
        aggregate_score=aggregate_score,
        previous_checkpoint_hash=previous_checkpoint_hash,
    )


# ==============================================================================
# PARTITION HANDLING (v3.5)
# ==============================================================================

def find_common_checkpoint(
    chain_a: List[FinalityCheckpoint],
    chain_b: List[FinalityCheckpoint],
) -> Optional[FinalityCheckpoint]:
    """
    Find the most recent common checkpoint between two chains.

    Args:
        chain_a: First checkpoint chain (ordered by timestamp ascending)
        chain_b: Second checkpoint chain (ordered by timestamp ascending)

    Returns:
        Most recent common checkpoint, or None if no common ancestor
    """
    if not chain_a or not chain_b:
        return None

    # Build hash set from chain_b for O(1) lookup
    b_hashes = {cp.checkpoint_hash(): cp for cp in chain_b}

    # Search chain_a from most recent to oldest
    for cp in reversed(chain_a):
        cp_hash = cp.checkpoint_hash()
        if cp_hash in b_hashes:
            return cp

    # No common checkpoint found - check if chains share genesis
    # by comparing previous_checkpoint_hash of earliest checkpoints
    if chain_a[0].previous_checkpoint_hash == chain_b[0].previous_checkpoint_hash:
        # Both chains start from same genesis but diverged immediately
        return None

    return None


def merge_partition_chains(
    local_chain: List[FinalityCheckpoint],
    remote_chain: List[FinalityCheckpoint],
) -> Tuple[List[FinalityCheckpoint], List[FinalityCheckpoint]]:
    """
    Merge two checkpoint chains after network partition.

    Resolves conflicts at each UTC boundary using cascade tiebreakers.
    Preserves canonical checkpoint at each boundary.

    Args:
        local_chain: Local checkpoint chain (ordered by timestamp ascending)
        remote_chain: Remote checkpoint chain (ordered by timestamp ascending)

    Returns:
        Tuple of (canonical_chain, orphaned_checkpoints)
        - canonical_chain: Merged chain with winning checkpoints
        - orphaned_checkpoints: Non-canonical checkpoints (transactions preserved in DAG)
    """
    if not local_chain and not remote_chain:
        return [], []

    if not local_chain:
        return list(remote_chain), []

    if not remote_chain:
        return list(local_chain), []

    # Find common ancestor
    common = find_common_checkpoint(local_chain, remote_chain)

    canonical: List[FinalityCheckpoint] = []
    orphaned: List[FinalityCheckpoint] = []

    # If no common ancestor, start from genesis
    if common is None:
        local_idx = 0
        remote_idx = 0
    else:
        # Find indices after common ancestor
        common_hash = common.checkpoint_hash()

        local_idx = 0
        for i, cp in enumerate(local_chain):
            if cp.checkpoint_hash() == common_hash:
                local_idx = i + 1
                # Include checkpoints up to and including common
                canonical = local_chain[:local_idx]
                break

        remote_idx = 0
        for i, cp in enumerate(remote_chain):
            if cp.checkpoint_hash() == common_hash:
                remote_idx = i + 1
                break

    # Merge divergent portions
    while local_idx < len(local_chain) or remote_idx < len(remote_chain):
        local_cp = local_chain[local_idx] if local_idx < len(local_chain) else None
        remote_cp = remote_chain[remote_idx] if remote_idx < len(remote_chain) else None

        if local_cp and remote_cp:
            if local_cp.boundary_timestamp_ms == remote_cp.boundary_timestamp_ms:
                # Same boundary - resolve conflict
                winner = resolve_checkpoint_conflict(local_cp, remote_cp)
                loser = remote_cp if winner is local_cp else local_cp

                canonical.append(winner)
                orphaned.append(loser)

                local_idx += 1
                remote_idx += 1

            elif local_cp.boundary_timestamp_ms < remote_cp.boundary_timestamp_ms:
                # Local is older - add and advance
                canonical.append(local_cp)
                local_idx += 1
            else:
                # Remote is older - add and advance
                canonical.append(remote_cp)
                remote_idx += 1

        elif local_cp:
            canonical.append(local_cp)
            local_idx += 1
        else:
            canonical.append(remote_cp)
            remote_idx += 1

    return canonical, orphaned


def get_conflict_resolution_reason(
    checkpoint_a: FinalityCheckpoint,
    checkpoint_b: FinalityCheckpoint,
) -> Tuple[FinalityCheckpoint, int, str]:
    """
    Resolve checkpoint conflict and return the reason.

    Args:
        checkpoint_a: First checkpoint
        checkpoint_b: Second checkpoint

    Returns:
        Tuple of (winner, level, reason):
        - winner: The canonical checkpoint
        - level: Which cascade level decided (1-4)
        - reason: Human-readable explanation
    """
    if checkpoint_a.boundary_timestamp_ms != checkpoint_b.boundary_timestamp_ms:
        raise ValueError("Checkpoints must be at same UTC boundary")

    cp_a, cp_b = checkpoint_a, checkpoint_b

    # Level 1: Participants count
    if cp_a.participants_count != cp_b.participants_count:
        winner = max(cp_a, cp_b, key=lambda c: c.participants_count)
        diff = abs(cp_a.participants_count - cp_b.participants_count)
        return (
            winner,
            1,
            f"Level 1: More participants ({winner.participants_count} vs "
            f"{cp_a.participants_count if winner is cp_b else cp_b.participants_count}, "
            f"diff={diff})"
        )

    # Level 2: VDF iterations
    if cp_a.total_vdf_iterations != cp_b.total_vdf_iterations:
        winner = max(cp_a, cp_b, key=lambda c: c.total_vdf_iterations)
        diff = abs(cp_a.total_vdf_iterations - cp_b.total_vdf_iterations)
        return (
            winner,
            2,
            f"Level 2: More VDF iterations ({winner.total_vdf_iterations:,} vs "
            f"{cp_a.total_vdf_iterations if winner is cp_b else cp_b.total_vdf_iterations:,}, "
            f"diff={diff:,})"
        )

    # Level 3: Aggregate score
    if cp_a.aggregate_score != cp_b.aggregate_score:
        winner = max(cp_a, cp_b, key=lambda c: c.aggregate_score)
        diff = abs(cp_a.aggregate_score - cp_b.aggregate_score)
        return (
            winner,
            3,
            f"Level 3: Higher aggregate score ({winner.aggregate_score:,} vs "
            f"{cp_a.aggregate_score if winner is cp_b else cp_b.aggregate_score:,}, "
            f"diff={diff:,})"
        )

    # Level 4: Hash tiebreaker (astronomically rare)
    winner = min(cp_a, cp_b, key=lambda c: c.checkpoint_hash())
    return (
        winner,
        4,
        f"Level 4: Lexicographically smaller hash (perfect tie resolved deterministically)"
    )


# ==============================================================================
# CHECKPOINT CHAIN MANAGER (v3.5)
# ==============================================================================

class FinalityCheckpointManager:
    """
    Manages finality checkpoint chain for a node.

    Handles:
    - Checkpoint creation at UTC boundaries
    - Chain storage and retrieval
    - Partition detection and merge
    - Fork choice resolution
    """

    def __init__(self):
        self._chain: List[FinalityCheckpoint] = []
        self._by_hash: Dict[bytes, FinalityCheckpoint] = {}
        self._by_boundary: Dict[int, FinalityCheckpoint] = {}
        self._lock = threading.RLock()

        # Pending data for current window
        self._pending_blocks: List[bytes] = []
        self._pending_heartbeats: List[HeartbeatData] = []
        self._current_window_start_ms: int = 0

        logger.debug("FinalityCheckpointManager initialized")

    @property
    def chain_length(self) -> int:
        """Number of checkpoints in chain."""
        return len(self._chain)

    @property
    def latest_checkpoint(self) -> Optional[FinalityCheckpoint]:
        """Most recent checkpoint."""
        with self._lock:
            return self._chain[-1] if self._chain else None

    @property
    def genesis_checkpoint(self) -> Optional[FinalityCheckpoint]:
        """First checkpoint in chain."""
        with self._lock:
            return self._chain[0] if self._chain else None

    def get_checkpoint_by_hash(self, checkpoint_hash: bytes) -> Optional[FinalityCheckpoint]:
        """Get checkpoint by its hash."""
        with self._lock:
            return self._by_hash.get(checkpoint_hash)

    def get_checkpoint_at_boundary(self, boundary_ms: int) -> Optional[FinalityCheckpoint]:
        """Get checkpoint at specific UTC boundary."""
        with self._lock:
            return self._by_boundary.get(boundary_ms)

    def add_block_to_window(self, block_hash: bytes) -> None:
        """Add block hash to current finality window."""
        with self._lock:
            self._pending_blocks.append(block_hash)

    def add_heartbeat_to_window(self, heartbeat_data: HeartbeatData) -> None:
        """Add heartbeat data to current finality window."""
        with self._lock:
            self._pending_heartbeats.append(heartbeat_data)

    def create_checkpoint_at_boundary(self, boundary_ms: int) -> FinalityCheckpoint:
        """
        Create checkpoint at UTC boundary from pending data.

        Args:
            boundary_ms: UTC boundary timestamp

        Returns:
            New checkpoint

        Raises:
            ValueError: If boundary is not properly aligned
        """
        with self._lock:
            # Get previous checkpoint hash
            prev_hash = (
                self._chain[-1].checkpoint_hash()
                if self._chain
                else EMPTY_HASH
            )

            # Create checkpoint
            checkpoint = create_finality_checkpoint(
                boundary_timestamp_ms=boundary_ms,
                block_hashes=self._pending_blocks,
                heartbeat_data=self._pending_heartbeats,
                previous_checkpoint_hash=prev_hash,
            )

            # Add to chain
            self._add_checkpoint(checkpoint)

            # Clear pending data
            self._pending_blocks = []
            self._pending_heartbeats = []
            self._current_window_start_ms = boundary_ms

            logger.info(
                f"Created checkpoint at {boundary_ms}: "
                f"participants={checkpoint.participants_count}, "
                f"vdf={checkpoint.total_vdf_iterations:,}, "
                f"score={checkpoint.aggregate_score:,}"
            )

            return checkpoint

    def _add_checkpoint(self, checkpoint: FinalityCheckpoint) -> None:
        """Add checkpoint to chain (internal, assumes lock held)."""
        cp_hash = checkpoint.checkpoint_hash()

        self._chain.append(checkpoint)
        self._by_hash[cp_hash] = checkpoint
        self._by_boundary[checkpoint.boundary_timestamp_ms] = checkpoint

    def receive_remote_checkpoint(
        self,
        checkpoint: FinalityCheckpoint,
    ) -> Tuple[bool, Optional[str]]:
        """
        Receive checkpoint from remote peer.

        Args:
            checkpoint: Remote checkpoint

        Returns:
            Tuple of (accepted, reason):
            - accepted: True if checkpoint was accepted
            - reason: Explanation if rejected
        """
        with self._lock:
            cp_hash = checkpoint.checkpoint_hash()

            # Already have this checkpoint
            if cp_hash in self._by_hash:
                return True, "Already known"

            boundary_ms = checkpoint.boundary_timestamp_ms

            # Check if we have a checkpoint at this boundary
            existing = self._by_boundary.get(boundary_ms)

            if existing is None:
                # No conflict - accept if it chains properly
                if self._chain:
                    expected_prev = self._chain[-1].checkpoint_hash()
                    if checkpoint.previous_checkpoint_hash != expected_prev:
                        # Gap in chain - need to sync
                        return False, "Chain gap detected"

                self._add_checkpoint(checkpoint)
                return True, "Accepted (no conflict)"

            # Conflict at same boundary - resolve
            winner, level, reason = get_conflict_resolution_reason(existing, checkpoint)

            if winner is checkpoint:
                # Remote wins - replace our checkpoint
                self._replace_checkpoint(existing, checkpoint)
                logger.info(f"Remote checkpoint won: {reason}")
                return True, f"Accepted (won at {reason})"
            else:
                # Local wins - reject remote
                logger.debug(f"Local checkpoint won: {reason}")
                return False, f"Rejected (lost at {reason})"

    def _replace_checkpoint(
        self,
        old: FinalityCheckpoint,
        new: FinalityCheckpoint,
    ) -> None:
        """Replace checkpoint in chain (internal, assumes lock held)."""
        old_hash = old.checkpoint_hash()
        new_hash = new.checkpoint_hash()

        # Find and replace in chain
        for i, cp in enumerate(self._chain):
            if cp.checkpoint_hash() == old_hash:
                self._chain[i] = new
                break

        # Update indices
        del self._by_hash[old_hash]
        self._by_hash[new_hash] = new
        self._by_boundary[new.boundary_timestamp_ms] = new

    def merge_remote_chain(
        self,
        remote_chain: List[FinalityCheckpoint],
    ) -> Tuple[int, int, List[str]]:
        """
        Merge remote checkpoint chain after partition.

        Args:
            remote_chain: Remote peer's checkpoint chain

        Returns:
            Tuple of (accepted_count, rejected_count, resolution_log):
            - accepted_count: Number of remote checkpoints that won
            - rejected_count: Number of remote checkpoints that lost
            - resolution_log: List of resolution reasons
        """
        with self._lock:
            canonical, orphaned = merge_partition_chains(self._chain, remote_chain)

            # Count results
            local_hashes = {cp.checkpoint_hash() for cp in self._chain}
            remote_hashes = {cp.checkpoint_hash() for cp in remote_chain}
            canonical_hashes = {cp.checkpoint_hash() for cp in canonical}

            accepted = sum(1 for h in remote_hashes if h in canonical_hashes and h not in local_hashes)
            rejected = sum(1 for h in remote_hashes if h not in canonical_hashes)

            # Build resolution log
            log = []
            for orphan in orphaned:
                winner = self._by_boundary.get(orphan.boundary_timestamp_ms)
                if winner:
                    _, level, reason = get_conflict_resolution_reason(winner, orphan)
                    log.append(f"Boundary {orphan.boundary_timestamp_ms}: {reason}")

            # Replace chain
            self._chain = canonical
            self._by_hash = {cp.checkpoint_hash(): cp for cp in canonical}
            self._by_boundary = {cp.boundary_timestamp_ms: cp for cp in canonical}

            logger.info(
                f"Chain merge complete: accepted={accepted}, "
                f"rejected={rejected}, new_length={len(canonical)}"
            )

            return accepted, rejected, log

    def get_chain_slice(
        self,
        start_boundary_ms: Optional[int] = None,
        end_boundary_ms: Optional[int] = None,
    ) -> List[FinalityCheckpoint]:
        """
        Get slice of checkpoint chain.

        Args:
            start_boundary_ms: Start boundary (inclusive), None for genesis
            end_boundary_ms: End boundary (inclusive), None for latest

        Returns:
            List of checkpoints in range
        """
        with self._lock:
            if not self._chain:
                return []

            result = []
            for cp in self._chain:
                if start_boundary_ms and cp.boundary_timestamp_ms < start_boundary_ms:
                    continue
                if end_boundary_ms and cp.boundary_timestamp_ms > end_boundary_ms:
                    break
                result.append(cp)

            return result

    def get_finality_for_block(
        self,
        block_timestamp_ms: int,
        current_time_ms: Optional[int] = None,
    ) -> Tuple[FinalityLevel, int]:
        """
        Get finality level for a block based on checkpoint chain.

        Args:
            block_timestamp_ms: Block creation timestamp
            current_time_ms: Current time (defaults to now)

        Returns:
            Tuple of (finality_level, checkpoints_passed)
        """
        if current_time_ms is None:
            current_time_ms = int(time.time() * 1000)

        # Find which boundary the block belongs to
        boundary_ms = FINALITY_INTERVAL_SEC * 1000
        block_boundary = (block_timestamp_ms // boundary_ms) * boundary_ms

        with self._lock:
            # Count checkpoints after block's boundary
            checkpoints_passed = sum(
                1 for cp in self._chain
                if cp.boundary_timestamp_ms > block_boundary
            )

        # Determine finality level
        if checkpoints_passed >= 3:
            return FinalityLevel.HARD, checkpoints_passed
        elif checkpoints_passed >= 2:
            return FinalityLevel.MEDIUM, checkpoints_passed
        elif checkpoints_passed >= 1:
            return FinalityLevel.SOFT, checkpoints_passed

        return FinalityLevel.NONE, 0

    def get_stats(self) -> Dict:
        """Get checkpoint manager statistics."""
        with self._lock:
            if not self._chain:
                return {
                    "chain_length": 0,
                    "total_participants": 0,
                    "total_vdf_iterations": 0,
                    "total_aggregate_score": 0,
                }

            return {
                "chain_length": len(self._chain),
                "latest_boundary_ms": self._chain[-1].boundary_timestamp_ms,
                "total_participants": sum(cp.participants_count for cp in self._chain),
                "total_vdf_iterations": sum(cp.total_vdf_iterations for cp in self._chain),
                "total_aggregate_score": sum(cp.aggregate_score for cp in self._chain),
                "pending_blocks": len(self._pending_blocks),
                "pending_heartbeats": len(self._pending_heartbeats),
            }


# Global checkpoint manager
_checkpoint_manager: Optional[FinalityCheckpointManager] = None


def get_checkpoint_manager() -> FinalityCheckpointManager:
    """Get or create global checkpoint manager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = FinalityCheckpointManager()
    return _checkpoint_manager
