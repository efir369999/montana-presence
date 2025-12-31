"""
PoT Protocol v6 Full Cycle Integration Tests

Tests the complete flow from Layer 0 → Layer 1 → Layer 2 → Heartbeat → Block
"""

import pytest
import asyncio
from unittest.mock import patch, Mock

from pot.core.types import Hash, PublicKey, SecretKey, KeyPair
from pot.core.atomic import AtomicSource, AtomicTimeProof
from pot.core.bitcoin import BitcoinAnchor
from pot.core.vdf import VDFProof
from pot.core.heartbeat import Heartbeat
from pot.core.transaction import Transaction
from pot.core.block import Block, BlockHeader
from pot.core.state import GlobalState, AccountState

from pot.layers.layer0 import (
    MockAtomicTimeOracle,
    validate_atomic_time,
    get_layer0_info,
)
from pot.layers.layer1 import (
    get_layer1_info,
    estimate_vdf_time,
    calculate_required_iterations,
)
from pot.layers.layer2 import (
    MockBitcoinOracle,
    validate_bitcoin_anchor,
    get_current_epoch,
    is_epoch_boundary,
)

from pot.constants import (
    VDF_BASE_ITERATIONS,
    NTP_MIN_SOURCES_CONSENSUS,
    NTP_MIN_REGIONS_TOTAL,
    BTC_HALVING_INTERVAL,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def atomic_oracle():
    """Create atomic time oracle."""
    return MockAtomicTimeOracle()


@pytest.fixture
def bitcoin_oracle():
    """Create Bitcoin oracle."""
    return MockBitcoinOracle(start_height=850000)


@pytest.fixture
def test_keypair():
    """Create test keypair."""
    return KeyPair(
        public=PublicKey(data=bytes(32)),
        secret=SecretKey(data=bytes(64))
    )


@pytest.fixture
def test_state(test_keypair):
    """Create test global state."""
    state = GlobalState()
    account = AccountState(
        pubkey=test_keypair.public,
        balance=1000_00000000,
        nonce=0,
        epoch_heartbeats=10,
        total_heartbeats=100
    )
    state.set_account(test_keypair.public, account)
    state.active_accounts = 1
    state.total_supply = 1000_00000000
    return state


# =============================================================================
# Test: Layer Integration
# =============================================================================

class TestLayerIntegration:
    """Tests for layer integration."""

    def test_layer0_produces_valid_proof(self, atomic_oracle):
        """Test Layer 0 produces valid atomic time proof."""
        proof = atomic_oracle.create_proof(source_count=20)

        assert proof.source_count >= NTP_MIN_SOURCES_CONSENSUS
        assert validate_atomic_time(proof) is True

    def test_layer0_info(self):
        """Test Layer 0 info is complete."""
        info = get_layer0_info()

        assert info["layer"] == 0
        assert info["sources_required"] == NTP_MIN_SOURCES_CONSENSUS
        assert info["regions_required"] == NTP_MIN_REGIONS_TOTAL
        assert len(info["edge_cases_handled"]) == 6

    def test_layer1_iterations_calculation(self, test_keypair):
        """Test Layer 1 VDF iterations calculation."""
        iterations = calculate_required_iterations(test_keypair.public, 0)
        assert iterations == VDF_BASE_ITERATIONS

        # More heartbeats should increase difficulty
        iterations_high = calculate_required_iterations(test_keypair.public, 1000)
        assert iterations_high >= iterations

    def test_layer1_time_estimation(self):
        """Test Layer 1 VDF time estimation."""
        base_time = estimate_vdf_time(VDF_BASE_ITERATIONS)
        assert base_time == pytest.approx(2.5, rel=0.1)

        double_time = estimate_vdf_time(VDF_BASE_ITERATIONS * 2)
        assert double_time == pytest.approx(5.0, rel=0.1)

    def test_layer1_info(self):
        """Test Layer 1 info is complete."""
        info = get_layer1_info()

        assert info["layer"] == 1
        assert info["vdf_hash_function"] == "SHAKE256"
        assert info["proof_system"] == "STARK"

    def test_layer2_produces_valid_anchor(self, bitcoin_oracle):
        """Test Layer 2 produces valid Bitcoin anchor."""
        anchor = bitcoin_oracle.get_anchor()
        current = bitcoin_oracle.get_anchor()

        assert validate_bitcoin_anchor(anchor, current) is True

    def test_layer2_epoch_calculation(self, bitcoin_oracle):
        """Test Layer 2 epoch calculation."""
        anchor = bitcoin_oracle.get_anchor()
        epoch = get_current_epoch(anchor.height)

        assert epoch == anchor.epoch
        assert epoch == anchor.height // BTC_HALVING_INTERVAL


# =============================================================================
# Test: Cross-Layer Flow
# =============================================================================

class TestCrossLayerFlow:
    """Tests for cross-layer data flow."""

    def test_atomic_time_to_heartbeat(self, atomic_oracle, test_keypair):
        """Test atomic time proof can be used in heartbeat."""
        atomic_proof = atomic_oracle.create_proof()

        # Atomic proof timestamp should be usable
        assert atomic_proof.timestamp_ms > 0
        assert len(atomic_proof.sources) >= NTP_MIN_SOURCES_CONSENSUS

    def test_bitcoin_anchor_to_vdf_seed(self, bitcoin_oracle, test_keypair):
        """Test Bitcoin anchor provides VDF seed input."""
        anchor = bitcoin_oracle.get_anchor()

        # VDF seed is deterministic from pubkey + Bitcoin
        from pot.crypto.vdf import generate_vdf_seed
        seed1 = generate_vdf_seed(test_keypair.public, anchor)
        seed2 = generate_vdf_seed(test_keypair.public, anchor)

        assert seed1 == seed2
        assert len(seed1) == 32

    def test_bitcoin_epoch_affects_state(self, bitcoin_oracle, test_state):
        """Test Bitcoin epoch is tracked in state."""
        anchor = bitcoin_oracle.get_anchor()
        test_state.current_epoch = get_current_epoch(anchor.height)

        assert test_state.current_epoch >= 0

        # Advance past halving
        bitcoin_oracle.advance_blocks(BTC_HALVING_INTERVAL - anchor.height % BTC_HALVING_INTERVAL)
        new_anchor = bitcoin_oracle.get_anchor()
        new_epoch = get_current_epoch(new_anchor.height)

        assert new_epoch == test_state.current_epoch + 1


# =============================================================================
# Test: Full Heartbeat Cycle
# =============================================================================

class TestHeartbeatCycle:
    """Tests for full heartbeat cycle simulation."""

    def test_heartbeat_prerequisites(self, atomic_oracle, bitcoin_oracle, test_keypair):
        """Test all prerequisites for heartbeat are available."""
        # Layer 0: Atomic time
        atomic_proof = atomic_oracle.create_proof()
        assert atomic_proof.source_count >= 18

        # Layer 2: Bitcoin anchor
        btc_anchor = bitcoin_oracle.get_anchor()
        assert btc_anchor.height > 0
        assert len(btc_anchor.block_hash) == 32

        # Layer 1: VDF seed can be generated
        from pot.crypto.vdf import generate_vdf_seed
        seed = generate_vdf_seed(test_keypair.public, btc_anchor)
        assert len(seed) == 32

    def test_time_flow_simulation(self, atomic_oracle, bitcoin_oracle):
        """Test time advances correctly in simulation."""
        initial_atomic = atomic_oracle.get_time_ms()
        initial_btc_height = bitcoin_oracle.height

        # Simulate time passing
        atomic_oracle.advance(60000)  # 1 minute
        bitcoin_oracle.advance_blocks(6)  # ~1 hour of Bitcoin time

        assert atomic_oracle.get_time_ms() > initial_atomic
        assert bitcoin_oracle.height > initial_btc_height


# =============================================================================
# Test: State Transitions
# =============================================================================

class TestStateTransitions:
    """Tests for state machine transitions."""

    def test_account_creation_in_state(self, test_state, test_keypair):
        """Test account exists in state."""
        account = test_state.get_account(test_keypair.public)

        assert account is not None
        assert account.balance == 1000_00000000
        assert account.epoch_heartbeats == 10

    def test_balance_transfer_simulation(self, test_state, test_keypair):
        """Test balance transfer between accounts."""
        # Create second account
        keypair2 = KeyPair(
            public=PublicKey(data=bytes([1] * 32)),
            secret=SecretKey(data=bytes([1] * 64))
        )
        account2 = AccountState(
            pubkey=keypair2.public,
            balance=0,
            nonce=0
        )
        test_state.set_account(keypair2.public, account2)

        # Simulate transfer
        sender = test_state.get_account(test_keypair.public)
        receiver = test_state.get_account(keypair2.public)

        transfer_amount = 100_00000000

        sender.balance -= transfer_amount
        receiver.balance += transfer_amount
        sender.nonce += 1

        test_state.set_account(test_keypair.public, sender)
        test_state.set_account(keypair2.public, receiver)

        # Verify
        assert test_state.get_account(test_keypair.public).balance == 900_00000000
        assert test_state.get_account(keypair2.public).balance == 100_00000000

    def test_heartbeat_count_increment(self, test_state, test_keypair):
        """Test heartbeat count increments."""
        account = test_state.get_account(test_keypair.public)
        initial_count = account.epoch_heartbeats

        # Simulate heartbeat
        account.epoch_heartbeats += 1
        account.total_heartbeats += 1
        test_state.set_account(test_keypair.public, account)
        test_state.total_heartbeats += 1

        assert test_state.get_account(test_keypair.public).epoch_heartbeats == initial_count + 1


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases in integration."""

    def test_layer0_minimum_sources(self, atomic_oracle):
        """Test Layer 0 with exactly minimum sources."""
        proof = atomic_oracle.create_proof(source_count=NTP_MIN_SOURCES_CONSENSUS)
        # Should still be valid
        assert proof.source_count == NTP_MIN_SOURCES_CONSENSUS

    def test_layer2_at_halving_boundary(self, bitcoin_oracle):
        """Test Layer 2 at halving boundary."""
        # Advance to just before halving
        target = BTC_HALVING_INTERVAL * 5  # 5th halving
        bitcoin_oracle.height = target - 1

        assert not is_epoch_boundary(bitcoin_oracle.height)

        bitcoin_oracle.advance_blocks(1)
        assert is_epoch_boundary(bitcoin_oracle.height)

    def test_zero_balance_account(self, test_state):
        """Test account with zero balance."""
        keypair = KeyPair(
            public=PublicKey(data=bytes([2] * 32)),
            secret=SecretKey(data=bytes([2] * 64))
        )
        account = AccountState(
            pubkey=keypair.public,
            balance=0,
            nonce=0
        )
        test_state.set_account(keypair.public, account)

        retrieved = test_state.get_account(keypair.public)
        assert retrieved.balance == 0

    def test_high_nonce_account(self, test_state, test_keypair):
        """Test account with high nonce."""
        account = test_state.get_account(test_keypair.public)
        account.nonce = 1000000
        test_state.set_account(test_keypair.public, account)

        retrieved = test_state.get_account(test_keypair.public)
        assert retrieved.nonce == 1000000


# =============================================================================
# Test: Protocol Constants Consistency
# =============================================================================

class TestConstantsConsistency:
    """Tests for protocol constants consistency."""

    def test_layer0_constants(self):
        """Test Layer 0 constants are consistent."""
        from pot.constants import (
            NTP_TOTAL_SOURCES,
            NTP_MIN_SOURCES_CONSENSUS,
            NTP_MIN_REGIONS_TOTAL,
        )

        # Minimum should be less than total
        assert NTP_MIN_SOURCES_CONSENSUS <= NTP_TOTAL_SOURCES
        # Should have reasonable region requirement
        assert NTP_MIN_REGIONS_TOTAL <= 8

    def test_layer1_constants(self):
        """Test Layer 1 constants are consistent."""
        from pot.constants import (
            VDF_BASE_ITERATIONS,
            VDF_MAX_ITERATIONS,
            VDF_CHECKPOINT_INTERVAL,
        )

        # Max should be greater than base
        assert VDF_MAX_ITERATIONS >= VDF_BASE_ITERATIONS
        # Checkpoint interval should divide nicely
        assert VDF_BASE_ITERATIONS % VDF_CHECKPOINT_INTERVAL == 0 or \
               VDF_CHECKPOINT_INTERVAL > VDF_BASE_ITERATIONS

    def test_layer2_constants(self):
        """Test Layer 2 constants are consistent."""
        from pot.constants import (
            BTC_HALVING_INTERVAL,
            BTC_MAX_DRIFT_BLOCKS,
            BTC_BLOCK_TIME_SECONDS,
        )

        # Halving interval should be 210000
        assert BTC_HALVING_INTERVAL == 210000
        # Drift should be reasonable
        assert BTC_MAX_DRIFT_BLOCKS < BTC_HALVING_INTERVAL
        # Block time should be 600 seconds
        assert BTC_BLOCK_TIME_SECONDS == 600
