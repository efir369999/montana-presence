"""
ATC Protocol v7 Layer 1: Temporal Proof
Part V of Technical Specification

ATC Network Nodes providing temporal proof through VDF computation
with STARK verification.

Trust: T₁(c) = 1/√c where c = heartbeat count
Purpose: Temporal proof, network consensus
Mechanism: VDF (SHAKE256), STARK proofs, cryptographic signatures
"""

from __future__ import annotations
import logging
from typing import Optional, Tuple, Callable

from atc.constants import (
    VDF_BASE_ITERATIONS,
    VDF_MAX_ITERATIONS,
    VDF_CHECKPOINT_INTERVAL,
    VDF_DIFFICULTY_SCALE,
    VDF_SEED_PREFIX,
)
from atc.core.types import Hash, PublicKey
from atc.core.bitcoin import BitcoinAnchor
from atc.core.vdf import VDFProof
from atc.crypto.hash import sha3_256
from atc.crypto.vdf import (
    compute_vdf,
    verify_vdf,
    generate_vdf_seed as _generate_vdf_seed,
    get_vdf_iterations,
)
from atc.crypto.stark import (
    generate_stark_proof,
    verify_stark_proof,
    is_stark_available,
)
from atc.errors import (
    VDFSeedMismatchError,
    InsufficientVDFIterationsError,
    InvalidVDFProofError,
    STARKVerificationFailedError,
)

logger = logging.getLogger(__name__)


def compute_temporal_proof(
    pubkey: PublicKey,
    btc_anchor: BitcoinAnchor,
    epoch_heartbeats: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[Hash, VDFProof]:
    """
    Compute full temporal proof with VDF and STARK.

    This is the main entry point for Layer 1 proof generation.

    Per specification (Part V):
    - Generate deterministic seed from pubkey + Bitcoin block
    - Compute VDF with adaptive difficulty
    - Generate STARK proof for efficient verification

    Args:
        pubkey: Node's public key
        btc_anchor: Bitcoin block reference
        epoch_heartbeats: Number of heartbeats in current epoch (for difficulty)
        progress_callback: Optional callback(current, total) for progress

    Returns:
        Tuple of (VDF output hash, complete VDFProof with STARK)
    """
    # Generate deterministic seed
    seed = _generate_vdf_seed(pubkey, btc_anchor)

    # Calculate required iterations
    iterations = get_vdf_iterations(epoch_heartbeats)

    logger.debug(
        f"Computing VDF: pubkey={pubkey.data.hex()[:8]}..., "
        f"btc_height={btc_anchor.height}, iterations={iterations}"
    )

    # Compute VDF with checkpoints
    output, proof = compute_vdf(seed, iterations, progress_callback)

    logger.debug(f"VDF complete: output={output.hex()[:16]}...")

    return output, proof


def verify_temporal_proof(
    proof: VDFProof,
    pubkey: PublicKey,
    btc_anchor: BitcoinAnchor,
    min_iterations: int
) -> bool:
    """
    Verify a temporal proof.

    Per specification (Part V):
    - Verify VDF seed matches expected value
    - Verify iterations meet minimum requirement
    - Verify VDF proof structure
    - Verify STARK proof for computational integrity

    Args:
        proof: VDFProof to verify
        pubkey: Expected public key
        btc_anchor: Expected Bitcoin anchor
        min_iterations: Minimum required iterations

    Returns:
        True if proof is valid
    """
    # Verify VDF seed matches expected
    expected_seed = _generate_vdf_seed(pubkey, btc_anchor)
    expected_seed_hash = sha3_256(expected_seed)

    if proof.seed != expected_seed_hash:
        logger.debug(
            f"VDF seed mismatch: expected={expected_seed_hash.hex()[:16]}, "
            f"got={proof.seed.hex()[:16]}"
        )
        return False

    # Verify iterations meet minimum
    if proof.iterations < min_iterations:
        logger.debug(
            f"Insufficient iterations: {proof.iterations} < {min_iterations}"
        )
        return False

    # Verify VDF proof (includes STARK verification)
    if not verify_vdf(proof):
        logger.debug("VDF proof verification failed")
        return False

    return True


def validate_temporal_proof_strict(
    proof: VDFProof,
    pubkey: PublicKey,
    btc_anchor: BitcoinAnchor,
    min_iterations: int
) -> None:
    """
    Strictly validate temporal proof, raising exceptions on failure.

    Same as verify_temporal_proof but raises specific exceptions.
    """
    # Verify VDF seed matches expected
    expected_seed = _generate_vdf_seed(pubkey, btc_anchor)
    expected_seed_hash = sha3_256(expected_seed)

    if proof.seed != expected_seed_hash:
        raise VDFSeedMismatchError(expected_seed_hash.data, proof.seed.data)

    # Verify iterations meet minimum
    if proof.iterations < min_iterations:
        raise InsufficientVDFIterationsError(proof.iterations, min_iterations)

    # Verify basic proof structure
    if not proof.has_valid_structure():
        raise InvalidVDFProofError("Invalid proof structure")

    # Verify checkpoint count
    expected_checkpoints = (proof.iterations // VDF_CHECKPOINT_INTERVAL) + 1
    if proof.iterations % VDF_CHECKPOINT_INTERVAL != 0:
        expected_checkpoints += 1

    if proof.checkpoint_count != expected_checkpoints:
        raise InvalidVDFProofError(
            f"Invalid checkpoint count: {proof.checkpoint_count} "
            f"(expected {expected_checkpoints})"
        )

    # Verify first checkpoint matches seed
    expected_initial = sha3_256(VDF_SEED_PREFIX + proof.seed.data)
    if proof.checkpoints[0] != expected_initial:
        raise InvalidVDFProofError("First checkpoint doesn't match seed")

    # Verify last checkpoint matches output
    if proof.checkpoints[-1] != proof.output:
        raise InvalidVDFProofError("Last checkpoint doesn't match output")

    # Verify STARK proof
    if not verify_stark_proof(
        proof.checkpoints[0],
        proof.output,
        proof.iterations,
        proof.checkpoints,
        proof.stark_proof
    ):
        raise STARKVerificationFailedError()


def calculate_required_iterations(
    pubkey: PublicKey,
    epoch_heartbeats: int
) -> int:
    """
    Calculate required VDF iterations for a node.

    Per specification (Part V):
    - Base iterations: 2^24 (~2.5 seconds)
    - Difficulty doubles every VDF_DIFFICULTY_SCALE heartbeats
    - Maximum: 2^28 (~40 seconds)

    Args:
        pubkey: Node's public key
        epoch_heartbeats: Heartbeats in current epoch

    Returns:
        Required iteration count
    """
    return get_vdf_iterations(epoch_heartbeats)


def estimate_vdf_time(iterations: int) -> float:
    """
    Estimate VDF computation time in seconds.

    Based on benchmarks:
    - VDF_BASE_ITERATIONS (2^24) takes approximately 2.5 seconds
    - Time scales linearly with iterations

    Args:
        iterations: Number of VDF iterations

    Returns:
        Estimated time in seconds
    """
    return (iterations / VDF_BASE_ITERATIONS) * 2.5


def get_layer1_info() -> dict:
    """Get information about Layer 1 implementation."""
    return {
        "layer": 1,
        "name": "Temporal Proof",
        "trust_formula": "T₁(c) = 1/√c where c = heartbeat count",
        "vdf_hash_function": "SHAKE256",
        "vdf_base_iterations": VDF_BASE_ITERATIONS,
        "vdf_max_iterations": VDF_MAX_ITERATIONS,
        "vdf_checkpoint_interval": VDF_CHECKPOINT_INTERVAL,
        "difficulty_scale": VDF_DIFFICULTY_SCALE,
        "proof_system": "STARK",
        "stark_available": is_stark_available(),
        "estimated_base_time_sec": 2.5,
    }


class TemporalProver:
    """
    Stateful temporal proof generator with caching and progress tracking.
    """

    def __init__(self):
        self._in_progress = False
        self._last_proof: Optional[VDFProof] = None
        self._last_pubkey: Optional[PublicKey] = None
        self._last_btc_height: Optional[int] = None

    def is_computing(self) -> bool:
        """Check if VDF computation is in progress."""
        return self._in_progress

    def get_cached_proof(
        self,
        pubkey: PublicKey,
        btc_anchor: BitcoinAnchor
    ) -> Optional[VDFProof]:
        """
        Get cached proof if available for same pubkey and Bitcoin block.
        """
        if (
            self._last_proof is not None and
            self._last_pubkey == pubkey and
            self._last_btc_height == btc_anchor.height
        ):
            return self._last_proof
        return None

    def compute(
        self,
        pubkey: PublicKey,
        btc_anchor: BitcoinAnchor,
        epoch_heartbeats: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[Hash, VDFProof]:
        """
        Compute temporal proof with caching.

        If the same pubkey+Bitcoin block combination was computed recently,
        returns cached result.
        """
        # Check cache
        cached = self.get_cached_proof(pubkey, btc_anchor)
        if cached is not None:
            logger.debug("Returning cached temporal proof")
            return cached.output, cached

        self._in_progress = True
        try:
            output, proof = compute_temporal_proof(
                pubkey,
                btc_anchor,
                epoch_heartbeats,
                progress_callback
            )

            # Update cache
            self._last_proof = proof
            self._last_pubkey = pubkey
            self._last_btc_height = btc_anchor.height

            return output, proof
        finally:
            self._in_progress = False

    def clear_cache(self):
        """Clear cached proof."""
        self._last_proof = None
        self._last_pubkey = None
        self._last_btc_height = None


# Global prover instance
_temporal_prover = TemporalProver()


def get_temporal_prover() -> TemporalProver:
    """Get the global temporal prover instance."""
    return _temporal_prover
