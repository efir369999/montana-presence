"""
PoT Protocol v6 Heartbeat Protocol
Part VII of Technical Specification

A heartbeat is proof of temporal presence across all three layers.
"""

from __future__ import annotations
import logging
from typing import Optional

from pot.constants import (
    PROTOCOL_VERSION,
    BTC_BLOCK_TIME_SECONDS,
    NTP_MIN_SOURCES_CONSENSUS,
    NTP_MIN_REGIONS_TOTAL,
    NTP_MAX_DRIFT_MS,
)
from pot.core.types import Hash, PublicKey, KeyPair, empty_signature
from pot.core.atomic import AtomicTimeProof
from pot.core.vdf import VDFProof
from pot.core.bitcoin import BitcoinAnchor
from pot.core.heartbeat import Heartbeat
from pot.core.state import AccountState, GlobalState
from pot.layers.layer0 import query_atomic_time, validate_atomic_time
from pot.layers.layer1 import compute_temporal_proof, verify_temporal_proof
from pot.layers.layer2 import query_bitcoin, validate_bitcoin_anchor
from pot.crypto.sphincs import sphincs_sign, sphincs_verify
from pot.crypto.vdf import generate_vdf_seed, get_vdf_iterations
from pot.crypto.hash import sha3_256
from pot.errors import (
    InvalidAtomicTime,
    VDFSeedMismatchError,
    InsufficientVDFIterationsError,
    InvalidVDFProofError,
    InvalidBitcoinAnchorError,
    CrossLayerInconsistentError,
    InvalidHeartbeatSequenceError,
    InvalidHeartbeatSignatureError,
)

logger = logging.getLogger(__name__)


# For import compatibility
class InvalidAtomicTime(Exception):
    pass


async def create_heartbeat(
    keypair: KeyPair,
    state: GlobalState
) -> Heartbeat:
    """
    Create a new heartbeat with all three layers.

    Per specification (Part VII):
    1. Query physical time (Layer 0)
    2. Query Bitcoin (Layer 2) - needed for VDF seed
    3. Compute VDF (Layer 1)
    4. Sign heartbeat

    Args:
        keypair: Node's key pair for signing
        state: Current global state

    Returns:
        Complete signed Heartbeat
    """
    # Layer 0: Query physical time
    atomic_time = await query_atomic_time()

    # Layer 2: Query Bitcoin (needed for VDF seed)
    btc_anchor = await query_bitcoin()

    # Get account state for sequence number and VDF difficulty
    account = state.get_account(keypair.public)
    epoch_heartbeats = account.epoch_heartbeats if account else 0
    sequence = (account.total_heartbeats + 1) if account else 1

    # Layer 1: Compute VDF with STARK proof
    _, vdf_proof = compute_temporal_proof(
        keypair.public,
        btc_anchor,
        epoch_heartbeats
    )

    # Create unsigned heartbeat
    hb = Heartbeat(
        pubkey=keypair.public,
        atomic_time=atomic_time,
        vdf_proof=vdf_proof,
        btc_anchor=btc_anchor,
        sequence=sequence,
        version=PROTOCOL_VERSION,
        signature=empty_signature()
    )

    # Sign
    message = hb.serialize_for_signing()
    signature = sphincs_sign(keypair.secret, message)

    # Update with signature
    hb = Heartbeat(
        pubkey=hb.pubkey,
        atomic_time=hb.atomic_time,
        vdf_proof=hb.vdf_proof,
        btc_anchor=hb.btc_anchor,
        sequence=hb.sequence,
        version=hb.version,
        signature=signature
    )

    return hb


def create_heartbeat_sync(keypair: KeyPair, state: GlobalState) -> Heartbeat:
    """Synchronous wrapper for create_heartbeat."""
    import asyncio
    return asyncio.run(create_heartbeat(keypair, state))


async def validate_heartbeat(hb: Heartbeat, state: GlobalState) -> bool:
    """
    Validate a heartbeat against all protocol rules.

    Per specification (Part VII):
    1. Validate Layer 0 (atomic time)
    2. Validate Layer 1 (VDF proof)
    3. Validate Layer 2 (Bitcoin anchor)
    4. Check cross-layer consistency
    5. Check sequence number
    6. Verify signature

    Args:
        hb: Heartbeat to validate
        state: Current global state

    Returns:
        True if heartbeat is valid
    """
    try:
        await validate_heartbeat_strict(hb, state)
        return True
    except Exception as e:
        logger.debug(f"Heartbeat validation failed: {e}")
        return False


async def validate_heartbeat_strict(hb: Heartbeat, state: GlobalState) -> None:
    """
    Strictly validate heartbeat, raising exceptions on failure.

    Raises specific exceptions for each validation failure.
    """
    # === LAYER 0: PHYSICAL TIME ===

    if not validate_atomic_time(hb.atomic_time):
        raise InvalidAtomicTime("Atomic time proof is invalid")

    # === LAYER 1: TEMPORAL PROOF ===

    # Verify VDF seed
    expected_seed = generate_vdf_seed(hb.pubkey, hb.btc_anchor)
    expected_seed_hash = sha3_256(expected_seed)
    if hb.vdf_proof.seed != expected_seed_hash:
        raise VDFSeedMismatchError(expected_seed_hash.data, hb.vdf_proof.seed.data)

    # Verify iterations meet minimum
    account = state.get_account(hb.pubkey)
    epoch_heartbeats = account.epoch_heartbeats if account else 0
    required_iterations = get_vdf_iterations(epoch_heartbeats)

    if hb.vdf_proof.iterations < required_iterations:
        raise InsufficientVDFIterationsError(
            hb.vdf_proof.iterations,
            required_iterations
        )

    # Verify VDF proof
    if not verify_temporal_proof(
        hb.vdf_proof,
        hb.pubkey,
        hb.btc_anchor,
        required_iterations
    ):
        raise InvalidVDFProofError("VDF proof verification failed")

    # === LAYER 2: BITCOIN ===

    current_btc = await query_bitcoin()
    if not validate_bitcoin_anchor(hb.btc_anchor, current_btc):
        raise InvalidBitcoinAnchorError("Bitcoin anchor is invalid or too old")

    # === CROSS-LAYER CONSISTENCY ===

    # Atomic time should be close to BTC block time
    btc_time_ms = hb.btc_anchor.timestamp * 1000
    time_diff = abs(hb.atomic_time.timestamp_ms - btc_time_ms)
    max_diff = BTC_BLOCK_TIME_SECONDS * 2 * 1000  # 20 minutes

    if time_diff > max_diff:
        raise CrossLayerInconsistentError(
            f"Time difference {time_diff}ms exceeds maximum {max_diff}ms"
        )

    # === SEQUENCE ===

    expected_seq = (account.total_heartbeats + 1) if account else 1
    if hb.sequence != expected_seq:
        raise InvalidHeartbeatSequenceError(hb.sequence, expected_seq)

    # === SIGNATURE ===

    message = hb.serialize_for_signing()
    if not sphincs_verify(hb.pubkey, message, hb.signature):
        raise InvalidHeartbeatSignatureError()


def validate_heartbeat_basic(hb: Heartbeat) -> bool:
    """
    Perform basic structural validation (no state or network required).

    Checks:
    - Version is correct
    - Atomic time has minimum sources
    - VDF proof has valid structure
    - Cross-layer times are roughly consistent
    """
    # Version check
    if hb.version != PROTOCOL_VERSION:
        logger.debug(f"Invalid version: {hb.version}")
        return False

    # Atomic time basic checks
    if hb.atomic_time.source_count < NTP_MIN_SOURCES_CONSENSUS:
        logger.debug(f"Insufficient atomic sources: {hb.atomic_time.source_count}")
        return False

    if hb.atomic_time.region_count() < NTP_MIN_REGIONS_TOTAL:
        logger.debug(f"Insufficient regions: {hb.atomic_time.region_count()}")
        return False

    if abs(hb.atomic_time.median_drift_ms) > NTP_MAX_DRIFT_MS:
        logger.debug(f"Excessive drift: {hb.atomic_time.median_drift_ms}")
        return False

    # VDF proof structure
    if not hb.vdf_proof.has_valid_structure():
        logger.debug("Invalid VDF proof structure")
        return False

    # Cross-layer consistency
    if not hb.is_cross_layer_consistent():
        logger.debug("Cross-layer time inconsistency")
        return False

    # Bitcoin epoch
    if not hb.btc_anchor.is_epoch_valid():
        logger.debug("Invalid Bitcoin epoch")
        return False

    return True


def validate_heartbeat_sync(hb: Heartbeat, state: GlobalState) -> bool:
    """Synchronous wrapper for validate_heartbeat."""
    import asyncio
    return asyncio.run(validate_heartbeat(hb, state))


def serialize_heartbeat_for_signing(hb: Heartbeat) -> bytes:
    """
    Serialize heartbeat for signing.

    Per specification:
    version || pubkey || atomic_time || vdf_proof || btc_anchor || sequence
    """
    return hb.serialize_for_signing()
