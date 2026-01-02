"""
Ɉ Montana Fork Choice Tests v3.5

Tests for cascade tiebreaker fork choice rule per §6.9.

Cascade levels:
1. More participants (heartbeats) → larger active network
2. Higher total VDF iterations → more proven time
3. Higher aggregate score → more reliable participants
4. Lower checkpoint hash → deterministic last resort
"""

import pytest
from montana.core.vdf_accumulator import (
    FinalityCheckpoint,
    FinalityCheckpointManager,
    HeartbeatData,
    FinalityLevel,
    EMPTY_HASH,
    resolve_checkpoint_conflict,
    get_conflict_resolution_reason,
    create_finality_checkpoint,
    find_common_checkpoint,
    merge_partition_chains,
    compute_merkle_root,
)
from montana.constants import FINALITY_INTERVAL_SEC


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def boundary_ms():
    """Standard boundary timestamp (aligned to 60s)."""
    return 1704067200000  # 2024-01-01 00:00:00 UTC


@pytest.fixture
def checkpoint_a(boundary_ms):
    """Checkpoint A with 100 participants, 1M VDF iterations, score 5000."""
    return FinalityCheckpoint(
        boundary_timestamp_ms=boundary_ms,
        blocks_merkle_root=b'\x01' * 32,
        vdf_proofs_root=b'\x02' * 32,
        participants_count=100,
        total_vdf_iterations=1_000_000,
        aggregate_score=5000,
        previous_checkpoint_hash=EMPTY_HASH,
    )


@pytest.fixture
def checkpoint_b(boundary_ms):
    """Checkpoint B with 80 participants (fewer than A)."""
    return FinalityCheckpoint(
        boundary_timestamp_ms=boundary_ms,
        blocks_merkle_root=b'\x03' * 32,
        vdf_proofs_root=b'\x04' * 32,
        participants_count=80,
        total_vdf_iterations=1_000_000,
        aggregate_score=5000,
        previous_checkpoint_hash=EMPTY_HASH,
    )


# ==============================================================================
# LEVEL 1: PARTICIPANTS COUNT
# ==============================================================================

class TestLevel1ParticipantsCount:
    """Test Level 1: More participants wins."""

    def test_more_participants_wins(self, checkpoint_a, checkpoint_b):
        """Checkpoint with more participants wins at Level 1."""
        winner = resolve_checkpoint_conflict(checkpoint_a, checkpoint_b)
        assert winner is checkpoint_a
        assert winner.participants_count == 100

    def test_resolution_reason_level_1(self, checkpoint_a, checkpoint_b):
        """Resolution reason correctly identifies Level 1."""
        winner, level, reason = get_conflict_resolution_reason(checkpoint_a, checkpoint_b)
        assert winner is checkpoint_a
        assert level == 1
        assert "Level 1" in reason
        assert "participants" in reason.lower()

    def test_60_40_split(self, boundary_ms):
        """60/40 network split resolved by participant count."""
        partition_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=600,  # 60%
            total_vdf_iterations=10_000_000,
            aggregate_score=50000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        partition_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=400,  # 40%
            total_vdf_iterations=10_000_000,
            aggregate_score=50000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner = resolve_checkpoint_conflict(partition_a, partition_b)
        assert winner is partition_a


# ==============================================================================
# LEVEL 2: VDF ITERATIONS
# ==============================================================================

class TestLevel2VDFIterations:
    """Test Level 2: More VDF iterations wins when participants equal."""

    def test_more_vdf_wins(self, boundary_ms):
        """Checkpoint with more VDF iterations wins at Level 2."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,  # Same
            total_vdf_iterations=2_000_000,  # More
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=100,  # Same
            total_vdf_iterations=1_500_000,  # Less
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner, level, reason = get_conflict_resolution_reason(cp_a, cp_b)
        assert winner is cp_a
        assert level == 2
        assert "VDF" in reason

    def test_50_50_different_vdf(self, boundary_ms):
        """50/50 split with different VDF iterations resolved at Level 2."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=500,
            total_vdf_iterations=8_400_000_000,  # More proven time
            aggregate_score=50000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=500,
            total_vdf_iterations=8_100_000_000,
            aggregate_score=50000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner = resolve_checkpoint_conflict(cp_a, cp_b)
        assert winner is cp_a


# ==============================================================================
# LEVEL 3: AGGREGATE SCORE
# ==============================================================================

class TestLevel3AggregateScore:
    """Test Level 3: Higher aggregate score wins when VDF equal."""

    def test_higher_score_wins(self, boundary_ms):
        """Checkpoint with higher aggregate score wins at Level 3."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=6000,  # Higher
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,  # Lower
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner, level, reason = get_conflict_resolution_reason(cp_a, cp_b)
        assert winner is cp_a
        assert level == 3
        assert "score" in reason.lower()

    def test_50_50_same_vdf_different_score(self, boundary_ms):
        """50/50 split with same VDF but different scores resolved at Level 3."""
        # Partition A has more experienced participants (higher cumulative score)
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=500,
            total_vdf_iterations=8_000_000_000,
            aggregate_score=2_847_000,  # More reliable participants
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=500,
            total_vdf_iterations=8_000_000_000,
            aggregate_score=2_134_000,  # Less experienced
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner = resolve_checkpoint_conflict(cp_a, cp_b)
        assert winner is cp_a


# ==============================================================================
# LEVEL 4: HASH TIEBREAKER
# ==============================================================================

class TestLevel4HashTiebreaker:
    """Test Level 4: Lexicographically smaller hash wins (astronomically rare)."""

    def test_perfect_tie_uses_hash(self, boundary_ms):
        """Perfect tie resolved by lexicographically smaller hash."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\x03' * 32,  # Different → different hash
            vdf_proofs_root=b'\x04' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        winner, level, reason = get_conflict_resolution_reason(cp_a, cp_b)
        assert level == 4
        assert "hash" in reason.lower()
        assert "deterministic" in reason.lower()

        # Winner should be the one with smaller hash
        if cp_a.checkpoint_hash() < cp_b.checkpoint_hash():
            assert winner is cp_a
        else:
            assert winner is cp_b

    def test_hash_tiebreaker_is_deterministic(self, boundary_ms):
        """Hash tiebreaker always produces same result."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\xaa' * 32,
            vdf_proofs_root=b'\xbb' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=boundary_ms,
            blocks_merkle_root=b'\xcc' * 32,
            vdf_proofs_root=b'\xdd' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        # Run multiple times
        results = [resolve_checkpoint_conflict(cp_a, cp_b) for _ in range(100)]

        # All results must be identical
        assert all(r is results[0] for r in results)


# ==============================================================================
# CHECKPOINT CREATION
# ==============================================================================

class TestCheckpointCreation:
    """Test checkpoint creation from heartbeats."""

    def test_create_checkpoint_basic(self):
        """Create checkpoint from block hashes and heartbeat data."""
        boundary = 1704067260000  # Aligned to 60s

        block_hashes = [b'\x01' * 32, b'\x02' * 32, b'\x03' * 32]
        heartbeat_data = [
            HeartbeatData(
                node_id=b'\x10' * 32,
                vdf_iterations=16_777_216,
                participant_score=1000,
                vdf_proof_hash=b'\x20' * 32,
            ),
            HeartbeatData(
                node_id=b'\x11' * 32,
                vdf_iterations=16_777_500,
                participant_score=1200,
                vdf_proof_hash=b'\x21' * 32,
            ),
        ]

        checkpoint = create_finality_checkpoint(
            boundary_timestamp_ms=boundary,
            block_hashes=block_hashes,
            heartbeat_data=heartbeat_data,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        assert checkpoint.boundary_timestamp_ms == boundary
        assert checkpoint.participants_count == 2
        assert checkpoint.total_vdf_iterations == 16_777_216 + 16_777_500
        assert checkpoint.aggregate_score == 1000 + 1200
        assert checkpoint.blocks_merkle_root != EMPTY_HASH
        assert checkpoint.vdf_proofs_root != EMPTY_HASH

    def test_create_checkpoint_unaligned_raises(self):
        """Creating checkpoint with unaligned timestamp raises."""
        boundary = 1704067261000  # NOT aligned to 60s

        with pytest.raises(ValueError, match="not aligned"):
            create_finality_checkpoint(
                boundary_timestamp_ms=boundary,
                block_hashes=[],
                heartbeat_data=[],
                previous_checkpoint_hash=EMPTY_HASH,
            )

    def test_create_checkpoint_empty(self):
        """Create checkpoint with no blocks or heartbeats."""
        boundary = 1704067260000

        checkpoint = create_finality_checkpoint(
            boundary_timestamp_ms=boundary,
            block_hashes=[],
            heartbeat_data=[],
            previous_checkpoint_hash=EMPTY_HASH,
        )

        assert checkpoint.participants_count == 0
        assert checkpoint.total_vdf_iterations == 0
        assert checkpoint.aggregate_score == 0
        assert checkpoint.blocks_merkle_root == EMPTY_HASH


# ==============================================================================
# PARTITION HANDLING
# ==============================================================================

class TestPartitionHandling:
    """Test partition detection and chain merge."""

    def test_find_common_checkpoint(self):
        """Find common ancestor between two chains."""
        base = 1704067200000

        # Shared checkpoints
        cp1 = FinalityCheckpoint(
            boundary_timestamp_ms=base,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x01' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp2 = FinalityCheckpoint(
            boundary_timestamp_ms=base + 60000,
            blocks_merkle_root=b'\x02' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=cp1.checkpoint_hash(),
        )

        # Divergent checkpoints
        cp3_a = FinalityCheckpoint(
            boundary_timestamp_ms=base + 120000,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x03' * 32,
            participants_count=60,  # Partition A
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=cp2.checkpoint_hash(),
        )
        cp3_b = FinalityCheckpoint(
            boundary_timestamp_ms=base + 120000,
            blocks_merkle_root=b'\x04' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=40,  # Partition B
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=cp2.checkpoint_hash(),
        )

        chain_a = [cp1, cp2, cp3_a]
        chain_b = [cp1, cp2, cp3_b]

        common = find_common_checkpoint(chain_a, chain_b)
        assert common is not None
        assert common.checkpoint_hash() == cp2.checkpoint_hash()

    def test_merge_partition_chains(self):
        """Merge two partition chains correctly."""
        base = 1704067200000

        # Common checkpoint
        cp1 = FinalityCheckpoint(
            boundary_timestamp_ms=base,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x01' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        # Partition A wins (more participants)
        cp2_a = FinalityCheckpoint(
            boundary_timestamp_ms=base + 60000,
            blocks_merkle_root=b'\x02' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=60,  # Winner
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=cp1.checkpoint_hash(),
        )
        cp2_b = FinalityCheckpoint(
            boundary_timestamp_ms=base + 60000,
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x03' * 32,
            participants_count=40,  # Loser
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=cp1.checkpoint_hash(),
        )

        chain_a = [cp1, cp2_a]
        chain_b = [cp1, cp2_b]

        canonical, orphaned = merge_partition_chains(chain_a, chain_b)

        assert len(canonical) == 2
        assert canonical[0].checkpoint_hash() == cp1.checkpoint_hash()
        assert canonical[1].checkpoint_hash() == cp2_a.checkpoint_hash()
        assert len(orphaned) == 1
        assert orphaned[0].checkpoint_hash() == cp2_b.checkpoint_hash()


# ==============================================================================
# CHECKPOINT MANAGER
# ==============================================================================

class TestFinalityCheckpointManager:
    """Test checkpoint chain manager."""

    def test_create_checkpoint(self):
        """Manager creates checkpoints correctly."""
        manager = FinalityCheckpointManager()
        boundary = 1704067260000

        # Add data
        manager.add_block_to_window(b'\x01' * 32)
        manager.add_heartbeat_to_window(HeartbeatData(
            node_id=b'\x10' * 32,
            vdf_iterations=16_777_216,
            participant_score=1000,
            vdf_proof_hash=b'\x20' * 32,
        ))

        # Create checkpoint
        checkpoint = manager.create_checkpoint_at_boundary(boundary)

        assert checkpoint.participants_count == 1
        assert manager.chain_length == 1
        assert manager.latest_checkpoint is checkpoint

    def test_receive_remote_checkpoint_conflict(self):
        """Manager resolves conflicts from remote checkpoints."""
        manager = FinalityCheckpointManager()
        boundary = 1704067260000

        # Create local checkpoint (weak)
        manager.add_heartbeat_to_window(HeartbeatData(
            node_id=b'\x10' * 32,
            vdf_iterations=16_777_216,
            participant_score=1000,
            vdf_proof_hash=b'\x20' * 32,
        ))
        local = manager.create_checkpoint_at_boundary(boundary)

        # Remote checkpoint (strong - more participants)
        remote = FinalityCheckpoint(
            boundary_timestamp_ms=boundary,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x01' * 32,
            participants_count=100,  # Much more
            total_vdf_iterations=100_000_000,
            aggregate_score=50000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        accepted, reason = manager.receive_remote_checkpoint(remote)

        assert accepted
        assert "Level 1" in reason
        assert manager.latest_checkpoint.participants_count == 100

    def test_finality_level_tracking(self):
        """Manager tracks finality levels correctly."""
        manager = FinalityCheckpointManager()
        base = 1704067200000

        # Create 3 checkpoints
        for i in range(3):
            boundary = base + (i * 60000)
            manager.add_heartbeat_to_window(HeartbeatData(
                node_id=b'\x10' * 32,
                vdf_iterations=16_777_216,
                participant_score=1000,
                vdf_proof_hash=b'\x20' * 32,
            ))
            manager.create_checkpoint_at_boundary(boundary)

        # Block in first window should have HARD finality
        level, checkpoints = manager.get_finality_for_block(
            block_timestamp_ms=base + 1000,
            current_time_ms=base + 180000,
        )

        assert checkpoints >= 2  # At least 2 checkpoints after block


# ==============================================================================
# MERKLE TREE
# ==============================================================================

class TestMerkleTree:
    """Test Merkle root computation."""

    def test_empty_merkle(self):
        """Empty list returns EMPTY_HASH."""
        assert compute_merkle_root([]) == EMPTY_HASH

    def test_single_hash(self):
        """Single hash returns itself."""
        h = b'\x01' * 32
        assert compute_merkle_root([h]) == h

    def test_merkle_deterministic(self):
        """Same input always produces same root."""
        hashes = [b'\x01' * 32, b'\x02' * 32, b'\x03' * 32]
        root1 = compute_merkle_root(hashes)
        root2 = compute_merkle_root(hashes)
        assert root1 == root2

    def test_merkle_order_matters(self):
        """Different order produces different root."""
        h1 = b'\x01' * 32
        h2 = b'\x02' * 32
        root1 = compute_merkle_root([h1, h2])
        root2 = compute_merkle_root([h2, h1])
        assert root1 != root2


# ==============================================================================
# EDGE CASES
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_different_boundaries_raises(self):
        """Resolving checkpoints at different boundaries raises."""
        cp_a = FinalityCheckpoint(
            boundary_timestamp_ms=1704067200000,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )
        cp_b = FinalityCheckpoint(
            boundary_timestamp_ms=1704067260000,  # Different!
            blocks_merkle_root=b'\x03' * 32,
            vdf_proofs_root=b'\x04' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        with pytest.raises(ValueError, match="same UTC boundary"):
            resolve_checkpoint_conflict(cp_a, cp_b)

    def test_merge_empty_chains(self):
        """Merging empty chains returns empty."""
        canonical, orphaned = merge_partition_chains([], [])
        assert canonical == []
        assert orphaned == []

    def test_merge_one_empty_chain(self):
        """Merging with one empty chain returns the non-empty one."""
        cp = FinalityCheckpoint(
            boundary_timestamp_ms=1704067200000,
            blocks_merkle_root=b'\x01' * 32,
            vdf_proofs_root=b'\x02' * 32,
            participants_count=100,
            total_vdf_iterations=1_000_000,
            aggregate_score=5000,
            previous_checkpoint_hash=EMPTY_HASH,
        )

        canonical, orphaned = merge_partition_chains([cp], [])
        assert len(canonical) == 1
        assert canonical[0].checkpoint_hash() == cp.checkpoint_hash()
        assert orphaned == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
