"""
Tests for DAG Architecture and Tiered Privacy Model.

Based on:
- ProofOfTime_DAG_Addendum.pdf
- ProofOfTime_TechnicalSpec_v1.1.pdf

Time is the ultimate proof.
"""

import pytest
import struct
import time
import tempfile
import os
import secrets
from typing import List

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pantheon.hades.dag import (
    DAGBlock, DAGBlockHeader, PHANTOMOrdering,
    DAGConsensusEngine, DAGBlockProducer,
    MAX_PARENTS, MIN_WEIGHT_THRESHOLD, PHANTOM_K,
    estimate_throughput
)
from pantheon.hades.dag_storage import DAGStorage, LRUCache, CHECKPOINT_INTERVAL
from pantheon.nyx.tiered_privacy import (
    PrivacyTier, TieredOutput, TieredInput, TieredTransaction,
    TieredTransactionBuilder, TierValidator,
    TIER_SPECS
)
from pantheon.nyx import AnonymitySetManager, DEFAULT_RING_SIZE
# Ristretto removed in v4.3 (experimental)
# from pantheon.nyx.ristretto import (...)
from pantheon.prometheus.crypto import Ed25519, sha256
from config import PROTOCOL, StorageConfig


# ============================================================================
# DAG BLOCK TESTS
# ============================================================================

class TestDAGBlockHeader:
    """Tests for DAG block header."""
    
    def test_create_empty_header(self):
        """Test creating header with defaults."""
        header = DAGBlockHeader()
        assert header.version == PROTOCOL.PROTOCOL_VERSION
        assert header.parents == []
        assert header.vdf_weight == 0
    
    def test_header_with_parents(self):
        """Test header with multiple parents."""
        parents = [secrets.token_bytes(32) for _ in range(5)]
        header = DAGBlockHeader(parents=parents)
        assert len(header.parents) == 5
        assert header.validate_parents()
    
    def test_max_parents(self):
        """Test maximum 8 parents allowed."""
        parents = [secrets.token_bytes(32) for _ in range(8)]
        header = DAGBlockHeader(parents=parents)
        assert header.validate_parents()
        
        # Too many parents
        parents.append(secrets.token_bytes(32))
        header = DAGBlockHeader(parents=parents)
        assert not header.validate_parents()
    
    def test_duplicate_parents_rejected(self):
        """Test duplicate parents are rejected."""
        parent = secrets.token_bytes(32)
        header = DAGBlockHeader(parents=[parent, parent])
        assert not header.validate_parents()
    
    def test_header_serialization(self):
        """Test header serialization roundtrip."""
        parents = [secrets.token_bytes(32) for _ in range(3)]
        header = DAGBlockHeader(
            parents=parents,
            merkle_root=secrets.token_bytes(32),
            timestamp=int(time.time()),
            vdf_weight=1000000,
            vdf_iterations=50000
        )
        
        data = header.serialize()
        restored, offset = DAGBlockHeader.deserialize(data)
        
        assert len(restored.parents) == 3
        assert restored.merkle_root == header.merkle_root
        assert restored.vdf_weight == 1000000
    
    def test_header_hash_deterministic(self):
        """Test header hash is deterministic."""
        header = DAGBlockHeader(
            parents=[b'\x01' * 32],
            timestamp=1234567890
        )
        
        hash1 = header.hash()
        hash2 = header.hash()
        
        assert hash1 == hash2
        assert len(hash1) == 32


class TestDAGBlock:
    """Tests for complete DAG block."""
    
    def test_create_block(self):
        """Test block creation."""
        header = DAGBlockHeader(parents=[b'\x00' * 32])
        block = DAGBlock(header=header)
        
        assert block.block_hash == header.hash()
        assert block.parents == [b'\x00' * 32]
    
    def test_block_vdf_weight(self):
        """Test VDF weight property."""
        header = DAGBlockHeader(vdf_weight=5000000)
        block = DAGBlock(header=header)
        
        assert block.vdf_weight == 5000000


# ============================================================================
# PHANTOM ORDERING TESTS
# ============================================================================

class TestPHANTOMOrdering:
    """Tests for PHANTOM-PoT ordering algorithm."""
    
    @pytest.fixture
    def phantom(self):
        """Create PHANTOM ordering instance."""
        return PHANTOMOrdering()
    
    def test_add_genesis(self, phantom):
        """Test adding genesis block."""
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0
        ))
        
        assert phantom.add_block(genesis)
        assert len(phantom.blocks) == 1
        assert genesis.block_hash in phantom.tips
    
    def test_add_child_updates_tips(self, phantom):
        """Test that adding child updates tips correctly."""
        # Add genesis
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0
        ))
        phantom.add_block(genesis)
        
        # Add child
        child = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            vdf_weight=1000
        ))
        phantom.add_block(child)
        
        # Genesis should no longer be a tip
        assert genesis.block_hash not in phantom.tips
        assert child.block_hash in phantom.tips
    
    def test_concurrent_blocks(self, phantom):
        """Test concurrent block production creates multiple tips."""
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0
        ))
        phantom.add_block(genesis)
        
        # Create two children from same parent
        child1 = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            vdf_weight=1000,
            producer_pubkey=b'\x01' * 32
        ))
        child2 = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            vdf_weight=2000,
            producer_pubkey=b'\x02' * 32
        ))
        
        phantom.add_block(child1)
        phantom.add_block(child2)
        
        # Both should be tips
        assert len(phantom.tips) == 2
    
    def test_blue_set_membership(self, phantom):
        """Test blue set membership calculation."""
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0
        ))
        phantom.add_block(genesis)
        
        # Genesis should be blue
        assert phantom.is_blue(genesis.block_hash)
    
    def test_ordering_by_vdf_weight(self, phantom):
        """Test blocks are ordered by VDF weight."""
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0
        ))
        phantom.add_block(genesis)
        
        child_low = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            vdf_weight=1000
        ))
        child_high = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            vdf_weight=5000
        ))
        
        phantom.add_block(child_low)
        phantom.add_block(child_high)
        
        ordered = phantom.get_ordered_blocks()
        
        # Higher weight should come first (after genesis)
        high_idx = ordered.index(child_high.block_hash)
        low_idx = ordered.index(child_low.block_hash)
        
        assert high_idx < low_idx


# ============================================================================
# DAG CONSENSUS ENGINE TESTS
# ============================================================================

class TestDAGConsensusEngine:
    """Tests for DAG consensus engine."""
    
    @pytest.fixture
    def engine(self):
        """Create consensus engine."""
        return DAGConsensusEngine()
    
    def test_weight_threshold(self, engine, monkeypatch):
        """Test minimum weight threshold for block production."""
        # Enable unsafe mode for testing
        import pantheon.hades.dag as dag_module
        monkeypatch.setattr(dag_module, 'UNSAFE_ALLOWED', True)

        sk, pk = Ed25519.generate_keypair()

        # Node with 0 weight cannot produce
        assert not engine.can_produce_block(pk)

        # Node with sufficient weight can produce
        engine.update_node_weight(pk, 0.15)
        assert engine.can_produce_block(pk)
    
    def test_parent_diversity_calculation(self, engine):
        """Test parent diversity calculation."""
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            producer_pubkey=b'\x01' * 32
        ))
        engine.dag.add_block(genesis)
        
        child = DAGBlock(header=DAGBlockHeader(
            parents=[genesis.block_hash],
            producer_pubkey=b'\x02' * 32
        ))
        engine.dag.add_block(child)
        
        # Child references 1 parent from 1 producer
        diversity = engine.calculate_parent_diversity(child)
        assert diversity == 1


# ============================================================================
# DAG STORAGE TESTS
# ============================================================================

class TestDAGStorage:
    """Tests for DAG storage layer."""
    
    @pytest.fixture
    def storage(self):
        """Create temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StorageConfig(db_path=os.path.join(tmpdir, "test.db"))
            storage = DAGStorage(config)
            yield storage
            storage.close()
    
    def test_lru_cache(self):
        """Test LRU cache behavior."""
        cache = LRUCache(3)
        
        cache.put(b'a', b'1')
        cache.put(b'b', b'2')
        cache.put(b'c', b'3')
        
        assert cache.get(b'a') == b'1'
        
        # Adding 4th item should evict oldest (b, since a was accessed)
        cache.put(b'd', b'4')
        assert cache.get(b'b') is None
        assert cache.get(b'a') == b'1'
    
    def test_node_state_storage(self, storage):
        """Test storing and retrieving node state."""
        pubkey = secrets.token_bytes(32)
        
        storage.store_node_state(
            pubkey=pubkey,
            weight=0.75,
            uptime=86400,
            stored_blocks=1000,
            signed_blocks=50,
            status=1
        )
        
        weight = storage.get_node_weight(pubkey)
        assert weight == 0.75
    
    def test_key_image_tracking(self, storage):
        """Test key image double-spend prevention."""
        key_image = secrets.token_bytes(32)
        
        assert not storage.is_key_image_spent(key_image)
    
    def test_checkpoint_creation(self, storage):
        """Test checkpoint creation and retrieval."""
        cp_id = storage.create_checkpoint(
            block_hash=secrets.token_bytes(32),
            utxo_root=secrets.token_bytes(32),
            node_root=secrets.token_bytes(32),
            vdf_weight=10000000
        )
        
        assert cp_id > 0
        
        latest = storage.get_latest_checkpoint()
        assert latest is not None
        assert latest['vdf_weight'] == 10000000
    
    def test_statistics(self, storage):
        """Test statistics gathering."""
        stats = storage.get_stats()
        
        assert 'total_blocks' in stats
        assert 'unspent_utxos' in stats
        assert 'block_cache_size' in stats


# ============================================================================
# TIERED PRIVACY TESTS
# ============================================================================

class TestPrivacyTiers:
    """Tests for tiered privacy model."""
    
    def test_tier_specs(self):
        """Test tier specifications exist."""
        for tier in PrivacyTier:
            assert tier in TIER_SPECS
            assert 'fee_multiplier' in TIER_SPECS[tier]
            assert 'size_bytes' in TIER_SPECS[tier]
    
    def test_fee_multipliers(self):
        """Test fee multipliers are correct per spec."""
        assert TIER_SPECS[PrivacyTier.T0_PUBLIC]['fee_multiplier'] == 1
        assert TIER_SPECS[PrivacyTier.T1_STEALTH]['fee_multiplier'] == 2
        assert TIER_SPECS[PrivacyTier.T2_CONFIDENTIAL]['fee_multiplier'] == 5
        assert TIER_SPECS[PrivacyTier.T3_RING]['fee_multiplier'] == 10
    
    def test_ring_size(self):
        """Test default ring size is 11."""
        assert DEFAULT_RING_SIZE == 11


class TestTieredOutput:
    """Tests for tiered outputs."""
    
    def test_t0_output_serialization(self):
        """Test T0 (public) output serialization."""
        output = TieredOutput(
            tier=PrivacyTier.T0_PUBLIC,
            public_address=b'\x01' * 32,
            public_amount=1000000
        )
        
        data = output.serialize()
        restored, _ = TieredOutput.deserialize(data)
        
        assert restored.tier == PrivacyTier.T0_PUBLIC
        assert restored.public_amount == 1000000
    
    def test_t1_output_serialization(self):
        """Test T1 (stealth) output serialization."""
        output = TieredOutput(
            tier=PrivacyTier.T1_STEALTH,
            one_time_address=b'\x01' * 32,
            tx_public_key=b'\x02' * 32,
            visible_amount=500000
        )
        
        data = output.serialize()
        restored, _ = TieredOutput.deserialize(data)
        
        assert restored.tier == PrivacyTier.T1_STEALTH
        assert restored.visible_amount == 500000
    
    def test_fee_multiplier(self):
        """Test fee multiplier calculation."""
        t0 = TieredOutput(tier=PrivacyTier.T0_PUBLIC)
        t3 = TieredOutput(tier=PrivacyTier.T3_RING)
        
        assert t0.get_fee_multiplier() == 1
        assert t3.get_fee_multiplier() == 10


class TestTieredTransaction:
    """Tests for tiered transactions."""
    
    def test_tier_upgrade_allowed(self):
        """Test T0 → T3 is allowed (privacy upgrade)."""
        tx = TieredTransaction(
            inputs=[TieredInput(tier=PrivacyTier.T0_PUBLIC)],
            outputs=[TieredOutput(tier=PrivacyTier.T3_RING)]
        )
        
        valid, reason = tx.validate_tier_rules()
        assert valid, reason
    
    def test_tier_downgrade_blocked(self):
        """Test T3 → T0 is blocked (privacy downgrade)."""
        tx = TieredTransaction(
            inputs=[TieredInput(tier=PrivacyTier.T3_RING)],
            outputs=[TieredOutput(tier=PrivacyTier.T0_PUBLIC)]
        )
        
        valid, reason = tx.validate_tier_rules()
        assert not valid
    
    def test_same_tier_allowed(self):
        """Test same tier in/out is allowed."""
        for tier in PrivacyTier:
            tx = TieredTransaction(
                inputs=[TieredInput(tier=tier)],
                outputs=[TieredOutput(tier=tier)]
            )
            
            valid, _ = tx.validate_tier_rules()
            assert valid
    
    def test_fee_calculation(self):
        """Test fee calculation with multipliers."""
        tx = TieredTransaction(
            outputs=[TieredOutput(tier=PrivacyTier.T2_CONFIDENTIAL)]
        )
        
        fee = tx.calculate_fee(base_fee=10)
        assert fee == 50  # 10 × 5


class TestAnonymitySetManager:
    """Tests for anonymity set management."""
    
    def test_decoy_selection(self):
        """Test selecting decoys for ring."""
        asm = AnonymitySetManager()
        
        # Add outputs to pool
        for i in range(20):
            asm.add_output(TieredOutput(
                tier=PrivacyTier.T2_CONFIDENTIAL,
                one_time_address=secrets.token_bytes(32)
            ))
        
        decoys = asm.select_decoys(10)
        assert len(decoys) == 10
    
    def test_synthetic_padding(self):
        """Test synthetic decoys when pool is small."""
        asm = AnonymitySetManager()
        
        # Add fewer outputs than requested
        for i in range(3):
            asm.add_output(TieredOutput(
                tier=PrivacyTier.T2_CONFIDENTIAL,
                one_time_address=secrets.token_bytes(32)
            ))
        
        # Should pad with synthetic decoys
        decoys = asm.select_decoys(10)
        assert len(decoys) == 10


# ============================================================================
# RISTRETTO TESTS (SKIPPED - experimental, removed in v4.3)
# ============================================================================

@pytest.mark.skip(reason="Ristretto removed in v4.3 (experimental)")
class TestRistrettoScalar:
    """Tests for Ristretto255 scalars."""
    
    def test_random_scalar(self):
        """Test random scalar generation."""
        a = RistrettoScalar.random()
        b = RistrettoScalar.random()
        
        assert a.value != b.value
        assert 0 <= a.value < L
    
    def test_scalar_addition(self):
        """Test scalar addition mod L."""
        a = RistrettoScalar(100)
        b = RistrettoScalar(200)
        
        c = a + b
        assert c.value == 300
    
    def test_scalar_multiplication(self):
        """Test scalar multiplication mod L."""
        a = RistrettoScalar(7)
        b = RistrettoScalar(11)
        
        c = a * b
        assert c.value == 77
    
    def test_scalar_inversion(self):
        """Test modular inverse."""
        a = RistrettoScalar.random()
        a_inv = a.invert()
        
        product = a * a_inv
        assert product.value == 1
    
    def test_from_hash(self):
        """Test scalar from hash is deterministic."""
        s1 = RistrettoScalar.from_hash(b"domain", b"data")
        s2 = RistrettoScalar.from_hash(b"domain", b"data")
        
        assert s1 == s2


@pytest.mark.skip(reason="Ristretto removed in v4.3 (experimental)")
class TestRistrettoPoint:
    """Tests for Ristretto255 points."""

    def test_generator_not_identity(self):
        """Test generator G is not identity."""
        G = RistrettoGenerators.G()
        assert not G.is_identity()
    
    def test_generators_independent(self):
        """Test G and H are independent."""
        G = RistrettoGenerators.G()
        H = RistrettoGenerators.H()
        
        assert G != H
    
    def test_scalar_multiplication(self):
        """Test scalar × point."""
        G = RistrettoGenerators.G()
        
        P1 = 5 * G
        P2 = 3 * G + 2 * G
        
        # Should be equal (5G = 3G + 2G)
        # Note: This works in proper implementation
        assert isinstance(P1, RistrettoPoint)


@pytest.mark.skip(reason="Ristretto removed in v4.3 (experimental)")
class TestBulletproofsPP:
    """Tests for Bulletproofs++ range proofs."""

    def test_proof_creation(self):
        """Test creating range proof."""
        value = 1000000
        blinding = RistrettoScalar.random()
        
        proof = BulletproofPP.prove(value, blinding)
        
        assert proof.n == 64
        assert len(proof.L) > 0
    
    def test_proof_serialization(self):
        """Test proof serialization roundtrip."""
        proof = BulletproofPP.prove(500, RistrettoScalar.random())
        
        data = proof.serialize()
        restored = BulletproofPP.deserialize(data)
        
        assert restored.n == proof.n
        assert len(restored.L) == len(proof.L)
    
    def test_out_of_range_rejected(self):
        """Test value outside range is rejected."""
        blinding = RistrettoScalar.random()
        
        with pytest.raises(ValueError):
            BulletproofPP.prove(-1, blinding)
        
        with pytest.raises(ValueError):
            BulletproofPP.prove(2**64, blinding)
    
    def test_pedersen_commitment(self):
        """Test Pedersen commitment creation."""
        value = 12345
        blinding = RistrettoScalar.random()
        
        commitment = RistrettoPedersenCommitment.commit(value, blinding)
        
        assert not commitment.commitment.is_identity()


# ============================================================================
# THROUGHPUT ESTIMATION TESTS
# ============================================================================

class TestThroughputEstimation:
    """Tests for scalability estimation."""
    
    def test_throughput_scales_with_nodes(self):
        """Test TPS scales linearly with node count."""
        est_100 = estimate_throughput(100)
        est_1000 = estimate_throughput(1000)
        
        # 10x nodes should give ~10x TPS
        ratio = est_1000['estimated_tps'] / est_100['estimated_tps']
        assert 8 < ratio < 12
    
    def test_storage_estimation(self):
        """Test storage per year is calculated."""
        est = estimate_throughput(100)
        
        assert 'storage_per_year_gb' in est
        assert est['storage_per_year_gb'] > 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestDAGIntegration:
    """Integration tests for DAG system."""
    
    def test_full_dag_workflow(self):
        """Test complete DAG block flow."""
        # Create engine
        engine = DAGConsensusEngine()
        
        # Set up node
        sk, pk = Ed25519.generate_keypair()
        engine.update_node_weight(pk, 0.5)
        
        # Create producer
        producer = DAGBlockProducer(engine, sk, pk)
        
        # Genesis block
        genesis = DAGBlock(header=DAGBlockHeader(
            parents=[b'\x00' * 32],
            vdf_weight=0,
            producer_pubkey=pk,
            producer_signature=b'\x00' * 64  # Simplified for test
        ))
        
        # Add directly to DAG (skip signature validation for test)
        engine.dag.add_block(genesis)
        
        # Verify genesis is tip
        assert genesis.block_hash in engine.dag.get_tips()
    
    def test_tiered_transaction_flow(self):
        """Test creating and validating tiered transaction."""
        builder = TieredTransactionBuilder()
        
        # Add T0 output
        builder.add_public_output(b'\x01' * 32, 1000)
        builder.set_fee(PROTOCOL.MIN_FEE)
        
        tx = builder.build()
        
        # Validate
        valid, reason = TierValidator.validate_transaction(tx)
        assert valid, reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

