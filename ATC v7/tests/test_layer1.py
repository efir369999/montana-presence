"""
ATC Protocol v7 Layer 1 Tests
Tests for Temporal Proof (VDF + STARK)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from atc.core.types import Hash, PublicKey
from atc.core.bitcoin import BitcoinAnchor
from atc.core.vdf import VDFProof
from atc.layers.layer1 import (
    compute_temporal_proof,
    verify_temporal_proof,
    validate_temporal_proof_strict,
    calculate_required_iterations,
    estimate_vdf_time,
    get_layer1_info,
    TemporalProver,
    get_temporal_prover,
)
from atc.crypto.vdf import generate_vdf_seed, get_vdf_iterations
from atc.crypto.hash import sha3_256
from atc.constants import (
    VDF_BASE_ITERATIONS,
    VDF_MAX_ITERATIONS,
    VDF_CHECKPOINT_INTERVAL,
    VDF_DIFFICULTY_SCALE,
    VDF_SEED_PREFIX,
)
from atc.errors import (
    VDFSeedMismatchError,
    InsufficientVDFIterationsError,
    InvalidVDFProofError,
    STARKVerificationFailedError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_pubkey():
    """Create a mock public key."""
    return PublicKey(data=bytes(32))


@pytest.fixture
def mock_btc_anchor():
    """Create a mock Bitcoin anchor."""
    return BitcoinAnchor(
        height=800000,
        block_hash=bytes.fromhex("00" * 32),
        merkle_root=bytes.fromhex("11" * 32),
        timestamp=1704067200,  # Unix seconds
        difficulty=50000000000000,
        epoch=3,  # Post third halving
        confirmations=6
    )


@pytest.fixture
def mock_vdf_proof(mock_pubkey, mock_btc_anchor):
    """Create a mock VDF proof."""
    seed = generate_vdf_seed(mock_pubkey, mock_btc_anchor)
    seed_hash = sha3_256(seed)
    initial_checkpoint = sha3_256(VDF_SEED_PREFIX + seed_hash.data)
    output = Hash(data=bytes.fromhex("ff" * 32))

    iterations = VDF_BASE_ITERATIONS
    checkpoint_count = (iterations // VDF_CHECKPOINT_INTERVAL) + 2

    # Create mock checkpoints
    checkpoints = [initial_checkpoint] + [
        Hash(data=bytes([i % 256] * 32))
        for i in range(1, checkpoint_count - 1)
    ] + [output]

    return VDFProof(
        seed=seed_hash,
        output=output,
        iterations=iterations,
        checkpoint_count=len(checkpoints),
        checkpoints=checkpoints,
        stark_proof=bytes(100)
    )


# =============================================================================
# Test: VDF Iterations Calculation
# =============================================================================

class TestVDFIterations:
    """Tests for VDF iteration calculation."""

    def test_base_iterations(self):
        """Test base iterations for new nodes."""
        iterations = get_vdf_iterations(0)
        assert iterations == VDF_BASE_ITERATIONS

    def test_increased_iterations_with_heartbeats(self):
        """Test iterations increase with more heartbeats."""
        base = get_vdf_iterations(0)
        with_heartbeats = get_vdf_iterations(VDF_DIFFICULTY_SCALE)
        assert with_heartbeats >= base

    def test_max_iterations_cap(self):
        """Test iterations capped at maximum."""
        iterations = get_vdf_iterations(1000000)
        assert iterations <= VDF_MAX_ITERATIONS

    def test_calculate_required_iterations(self, mock_pubkey):
        """Test calculate_required_iterations function."""
        iterations = calculate_required_iterations(mock_pubkey, 0)
        assert iterations == VDF_BASE_ITERATIONS


# =============================================================================
# Test: VDF Seed Generation
# =============================================================================

class TestVDFSeed:
    """Tests for VDF seed generation."""

    def test_seed_determinism(self, mock_pubkey, mock_btc_anchor):
        """Test seed generation is deterministic."""
        seed1 = generate_vdf_seed(mock_pubkey, mock_btc_anchor)
        seed2 = generate_vdf_seed(mock_pubkey, mock_btc_anchor)
        assert seed1 == seed2

    def test_seed_uniqueness_pubkey(self, mock_pubkey, mock_btc_anchor):
        """Test different pubkeys produce different seeds."""
        seed1 = generate_vdf_seed(mock_pubkey, mock_btc_anchor)

        other_pubkey = PublicKey(data=bytes([1] * 32))
        seed2 = generate_vdf_seed(other_pubkey, mock_btc_anchor)

        assert seed1 != seed2

    def test_seed_uniqueness_btc(self, mock_pubkey, mock_btc_anchor):
        """Test different Bitcoin anchors produce different seeds."""
        seed1 = generate_vdf_seed(mock_pubkey, mock_btc_anchor)

        other_anchor = BitcoinAnchor(
            height=800001,  # Different height
            block_hash=bytes.fromhex("22" * 32),
            merkle_root=bytes.fromhex("11" * 32),
            timestamp=1704067200,
            difficulty=50000000000000,
            epoch=3,
            confirmations=6
        )
        seed2 = generate_vdf_seed(mock_pubkey, other_anchor)

        assert seed1 != seed2


# =============================================================================
# Test: Time Estimation
# =============================================================================

class TestTimeEstimation:
    """Tests for VDF time estimation."""

    def test_base_time_estimate(self):
        """Test base iterations time estimate."""
        time = estimate_vdf_time(VDF_BASE_ITERATIONS)
        assert time == pytest.approx(2.5, rel=0.1)

    def test_double_iterations_double_time(self):
        """Test time scales linearly."""
        base_time = estimate_vdf_time(VDF_BASE_ITERATIONS)
        double_time = estimate_vdf_time(VDF_BASE_ITERATIONS * 2)
        assert double_time == pytest.approx(base_time * 2, rel=0.1)

    def test_zero_iterations(self):
        """Test zero iterations returns zero time."""
        time = estimate_vdf_time(0)
        assert time == 0.0


# =============================================================================
# Test: Temporal Prover Class
# =============================================================================

class TestTemporalProver:
    """Tests for TemporalProver class."""

    def test_initial_state(self):
        """Test prover initial state."""
        prover = TemporalProver()
        assert prover.is_computing() is False

    def test_get_cached_proof_empty(self, mock_pubkey, mock_btc_anchor):
        """Test cache returns None when empty."""
        prover = TemporalProver()
        cached = prover.get_cached_proof(mock_pubkey, mock_btc_anchor)
        assert cached is None

    def test_clear_cache(self, mock_pubkey, mock_btc_anchor, mock_vdf_proof):
        """Test cache clearing."""
        prover = TemporalProver()
        prover._last_proof = mock_vdf_proof
        prover._last_pubkey = mock_pubkey
        prover._last_btc_height = mock_btc_anchor.height

        prover.clear_cache()

        assert prover._last_proof is None
        assert prover._last_pubkey is None
        assert prover._last_btc_height is None

    def test_global_prover_singleton(self):
        """Test global prover is accessible."""
        prover1 = get_temporal_prover()
        prover2 = get_temporal_prover()
        assert prover1 is prover2


# =============================================================================
# Test: Layer 1 Info
# =============================================================================

class TestLayer1Info:
    """Tests for layer info functions."""

    def test_get_layer1_info(self):
        """Test layer 1 info retrieval."""
        info = get_layer1_info()
        assert info["layer"] == 1
        assert info["name"] == "Temporal Proof"
        assert info["vdf_hash_function"] == "SHAKE256"
        assert info["vdf_base_iterations"] == VDF_BASE_ITERATIONS
        assert info["vdf_max_iterations"] == VDF_MAX_ITERATIONS
        assert info["proof_system"] == "STARK"
        assert "stark_available" in info

    def test_info_has_trust_formula(self):
        """Test info includes trust formula."""
        info = get_layer1_info()
        assert "trust_formula" in info
        assert "1/√c" in info["trust_formula"]


# =============================================================================
# Test: Proof Verification (Mocked)
# =============================================================================

class TestProofVerification:
    """Tests for proof verification with mocks."""

    @patch('pot.layers.layer1.verify_vdf')
    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_verify_valid_proof(
        self,
        mock_gen_seed,
        mock_verify_vdf,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test verification of valid proof."""
        # Setup mocks
        mock_gen_seed.return_value = bytes(32)
        mock_verify_vdf.return_value = True

        # Create matching seed hash
        mock_vdf_proof.seed = sha3_256(bytes(32))

        result = verify_temporal_proof(
            mock_vdf_proof,
            mock_pubkey,
            mock_btc_anchor,
            min_iterations=1000
        )

        assert result is True

    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_verify_seed_mismatch(
        self,
        mock_gen_seed,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test verification fails on seed mismatch."""
        # Setup mock to return different seed
        mock_gen_seed.return_value = bytes([0xff] * 32)

        result = verify_temporal_proof(
            mock_vdf_proof,
            mock_pubkey,
            mock_btc_anchor,
            min_iterations=1000
        )

        assert result is False

    @patch('pot.layers.layer1.verify_vdf')
    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_verify_insufficient_iterations(
        self,
        mock_gen_seed,
        mock_verify_vdf,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test verification fails on insufficient iterations."""
        mock_gen_seed.return_value = bytes(32)
        mock_vdf_proof.seed = sha3_256(bytes(32))
        mock_vdf_proof.iterations = 1000  # Too low

        result = verify_temporal_proof(
            mock_vdf_proof,
            mock_pubkey,
            mock_btc_anchor,
            min_iterations=1000000  # Required is higher
        )

        assert result is False

    @patch('pot.layers.layer1.verify_vdf')
    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_verify_vdf_failure(
        self,
        mock_gen_seed,
        mock_verify_vdf,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test verification fails when VDF verification fails."""
        mock_gen_seed.return_value = bytes(32)
        mock_vdf_proof.seed = sha3_256(bytes(32))
        mock_verify_vdf.return_value = False

        result = verify_temporal_proof(
            mock_vdf_proof,
            mock_pubkey,
            mock_btc_anchor,
            min_iterations=1000
        )

        assert result is False


# =============================================================================
# Test: Strict Validation Exceptions
# =============================================================================

class TestStrictValidation:
    """Tests for strict validation with exceptions."""

    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_strict_seed_mismatch_raises(
        self,
        mock_gen_seed,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test strict validation raises on seed mismatch."""
        mock_gen_seed.return_value = bytes([0xff] * 32)

        with pytest.raises(VDFSeedMismatchError):
            validate_temporal_proof_strict(
                mock_vdf_proof,
                mock_pubkey,
                mock_btc_anchor,
                min_iterations=1000
            )

    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_strict_insufficient_iterations_raises(
        self,
        mock_gen_seed,
        mock_pubkey,
        mock_btc_anchor,
        mock_vdf_proof
    ):
        """Test strict validation raises on insufficient iterations."""
        mock_gen_seed.return_value = bytes(32)
        mock_vdf_proof.seed = sha3_256(bytes(32))
        mock_vdf_proof.iterations = 1000

        with pytest.raises(InsufficientVDFIterationsError):
            validate_temporal_proof_strict(
                mock_vdf_proof,
                mock_pubkey,
                mock_btc_anchor,
                min_iterations=1000000
            )


# =============================================================================
# Test: Progress Callback
# =============================================================================

class TestProgressCallback:
    """Tests for progress callback functionality."""

    @patch('pot.layers.layer1.compute_vdf')
    @patch('pot.layers.layer1._generate_vdf_seed')
    def test_progress_callback_called(
        self,
        mock_gen_seed,
        mock_compute_vdf,
        mock_pubkey,
        mock_btc_anchor
    ):
        """Test progress callback is passed to compute_vdf."""
        mock_gen_seed.return_value = bytes(32)
        mock_output = Hash(data=bytes(32))
        mock_proof = Mock()
        mock_compute_vdf.return_value = (mock_output, mock_proof)

        callback = Mock()

        compute_temporal_proof(
            mock_pubkey,
            mock_btc_anchor,
            epoch_heartbeats=0,
            progress_callback=callback
        )

        # Verify callback was passed
        mock_compute_vdf.assert_called_once()
        args, kwargs = mock_compute_vdf.call_args
        assert callback in args or callback == kwargs.get('progress_callback')
