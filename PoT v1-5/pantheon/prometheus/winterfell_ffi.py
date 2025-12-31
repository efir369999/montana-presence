"""
Winterfell STARK FFI - Python Stub

This module provides the Python interface to the Winterfell STARK prover.

When the Rust extension is compiled (via maturin), this module is replaced
by the native extension. This stub provides fallback functionality using
checkpoint-based verification.

To compile the native extension:
    cd winterfell_stark
    maturin develop --release

Or install as package:
    maturin build --release
    pip install target/wheels/*.whl
"""

import hashlib
import struct
import logging
from typing import List

logger = logging.getLogger("proof_of_time.winterfell_ffi")

# Try to import native extension
try:
    from winterfell_stark import prove_vdf as _native_prove, verify_vdf as _native_verify
    NATIVE_AVAILABLE = True
    logger.info("Winterfell native extension loaded")
except ImportError:
    NATIVE_AVAILABLE = False
    logger.warning("Winterfell native extension not available - using Python fallback")


def shake256(data: bytes, length: int = 32) -> bytes:
    """Compute SHAKE256."""
    return hashlib.shake_256(data).digest(length)


def prove_vdf(
    input_hash: bytes,
    output_hash: bytes,
    checkpoints: List[bytes],
    iterations: int
) -> bytes:
    """
    Generate STARK proof for VDF computation.

    When native extension is available, generates real STARK proof (~50-200KB).
    Otherwise, uses checkpoint-based proof (fallback).

    Args:
        input_hash: 32-byte VDF input
        output_hash: 32-byte VDF output
        checkpoints: List of intermediate states
        iterations: Total number of iterations

    Returns:
        Proof bytes
    """
    if len(input_hash) != 32 or len(output_hash) != 32:
        raise ValueError("Input and output must be 32 bytes")

    if NATIVE_AVAILABLE:
        # Use native STARK prover
        checkpoint_list = [list(cp) for cp in checkpoints]
        return bytes(_native_prove(list(input_hash), list(output_hash), checkpoint_list, iterations))

    # Fallback: checkpoint-based proof
    logger.debug("Using checkpoint-based proof (fallback)")
    return _checkpoint_proof(input_hash, output_hash, checkpoints, iterations)


def verify_vdf(
    input_hash: bytes,
    output_hash: bytes,
    proof: bytes,
    iterations: int
) -> bool:
    """
    Verify STARK proof for VDF computation.

    When native extension is available, uses O(log T) STARK verification.
    Otherwise, uses checkpoint-based verification (fallback).

    Args:
        input_hash: 32-byte VDF input
        output_hash: 32-byte VDF output
        proof: Proof bytes from prove_vdf()
        iterations: Expected number of iterations

    Returns:
        True if proof is valid
    """
    if len(input_hash) != 32 or len(output_hash) != 32:
        raise ValueError("Input and output must be 32 bytes")

    # Check proof type
    if len(proof) >= 4 and proof[:4] == b'CPPT':
        # Checkpoint-based proof
        return _verify_checkpoint_proof(input_hash, output_hash, proof, iterations)

    if NATIVE_AVAILABLE:
        # Use native STARK verifier
        try:
            return _native_verify(list(input_hash), list(output_hash), list(proof), iterations)
        except Exception as e:
            logger.error(f"Native verification failed: {e}")
            return False

    # Unknown proof type
    logger.warning("Unknown proof type and native verifier not available")
    return False


def _checkpoint_proof(
    input_hash: bytes,
    output_hash: bytes,
    checkpoints: List[bytes],
    iterations: int
) -> bytes:
    """
    Create checkpoint-based proof (fallback when STARK not available).

    This is NOT cryptographically sound as a STARK proof, but allows
    probabilistic verification by sampling checkpoint segments.
    """
    data = bytearray()

    # Magic bytes to identify checkpoint proof
    data.extend(b'CPPT')  # CheckPoint Proof Type

    # Version
    data.append(0x01)

    # Metadata
    data.extend(struct.pack('<Q', iterations))

    # Checkpoint interval (calculated from checkpoints)
    if len(checkpoints) > 1:
        interval = iterations // (len(checkpoints) - 1)
    else:
        interval = iterations
    data.extend(struct.pack('<I', interval))

    # Number of checkpoints
    data.extend(struct.pack('<I', len(checkpoints)))

    # Checkpoints
    for cp in checkpoints:
        if len(cp) != 32:
            raise ValueError(f"Checkpoint must be 32 bytes, got {len(cp)}")
        data.extend(cp)

    # Proof hash (for integrity)
    proof_hash = hashlib.sha3_256(bytes(data)).digest()
    data.extend(proof_hash)

    return bytes(data)


def _verify_checkpoint_proof(
    input_hash: bytes,
    output_hash: bytes,
    proof: bytes,
    iterations: int
) -> bool:
    """
    Verify checkpoint-based proof.

    Performs probabilistic verification by:
    1. Checking boundary conditions (input and output match)
    2. Sampling and verifying random checkpoint segments
    """
    try:
        offset = 0

        # Check magic
        if proof[offset:offset + 4] != b'CPPT':
            logger.warning("Invalid proof magic")
            return False
        offset += 4

        # Version
        version = proof[offset]
        if version != 0x01:
            logger.warning(f"Unknown proof version: {version}")
            return False
        offset += 1

        # Iterations
        proof_iterations = struct.unpack_from('<Q', proof, offset)[0]
        if proof_iterations != iterations:
            logger.warning(f"Iterations mismatch: {proof_iterations} vs {iterations}")
            return False
        offset += 8

        # Checkpoint interval
        interval = struct.unpack_from('<I', proof, offset)[0]
        offset += 4

        # Number of checkpoints
        num_checkpoints = struct.unpack_from('<I', proof, offset)[0]
        offset += 4

        # Read checkpoints
        checkpoints = []
        for _ in range(num_checkpoints):
            cp = proof[offset:offset + 32]
            checkpoints.append(cp)
            offset += 32

        # Verify proof hash
        proof_hash = proof[offset:offset + 32]
        expected_hash = hashlib.sha3_256(proof[:offset]).digest()
        if proof_hash != expected_hash:
            logger.warning("Proof integrity check failed")
            return False

        # Verify boundaries
        if not checkpoints:
            logger.warning("No checkpoints in proof")
            return False

        if checkpoints[0] != input_hash:
            logger.warning("Input hash mismatch")
            return False

        if checkpoints[-1] != output_hash:
            logger.warning("Output hash mismatch")
            return False

        # Sample and verify random segments
        import random
        num_samples = min(len(checkpoints) - 1, 5)  # Verify up to 5 segments

        if num_samples > 0:
            segments = random.sample(range(len(checkpoints) - 1), num_samples)

            for seg_idx in segments:
                start_state = checkpoints[seg_idx]
                expected_end = checkpoints[seg_idx + 1]

                # Compute segment
                state = start_state
                for _ in range(interval):
                    state = shake256(state, 32)

                if state != expected_end:
                    logger.warning(f"Checkpoint segment {seg_idx} verification failed")
                    return False

        return True

    except Exception as e:
        logger.error(f"Checkpoint proof verification error: {e}")
        return False


def estimate_proof_size(iterations: int, checkpoint_interval: int = 1000) -> int:
    """
    Estimate STARK proof size.

    Args:
        iterations: Number of VDF iterations
        checkpoint_interval: Interval between checkpoints

    Returns:
        Estimated proof size in bytes
    """
    if NATIVE_AVAILABLE:
        # STARK proof size is roughly O(log^2(iterations))
        import math
        log_n = math.log2(iterations) if iterations > 0 else 1
        # Approximate: ~50KB base + ~5KB per log level
        return int(50000 + 5000 * log_n)
    else:
        # Checkpoint proof size
        num_checkpoints = iterations // checkpoint_interval + 2
        # Header + checkpoints + hash
        return 5 + 8 + 4 + 4 + (num_checkpoints * 32) + 32


def get_backend_info() -> dict:
    """Get information about the current backend."""
    return {
        "native_available": NATIVE_AVAILABLE,
        "backend": "winterfell" if NATIVE_AVAILABLE else "checkpoint_fallback",
        "verification_complexity": "O(log T)" if NATIVE_AVAILABLE else "O(samples * interval)",
        "proof_type": "STARK" if NATIVE_AVAILABLE else "checkpoint",
    }


# Self-test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Winterfell FFI Backend Info:")
    for k, v in get_backend_info().items():
        print(f"  {k}: {v}")

    # Test proof generation and verification
    print("\nTesting proof generation...")
    input_hash = shake256(b"test_input", 32)

    # Compute VDF
    state = input_hash
    checkpoints = [state]
    iterations = 1000
    for i in range(iterations):
        state = shake256(state, 32)
        if i % 200 == 199:
            checkpoints.append(state)
    checkpoints.append(state)
    output_hash = state

    print(f"  Input:  {input_hash.hex()[:16]}...")
    print(f"  Output: {output_hash.hex()[:16]}...")
    print(f"  Checkpoints: {len(checkpoints)}")

    # Generate proof
    proof = prove_vdf(input_hash, output_hash, checkpoints, iterations)
    print(f"  Proof size: {len(proof)} bytes")

    # Verify proof
    valid = verify_vdf(input_hash, output_hash, proof, iterations)
    print(f"  Verification: {'PASSED' if valid else 'FAILED'}")

    # Test tampered output
    bad_output = bytes([output_hash[0] ^ 1]) + output_hash[1:]
    invalid = verify_vdf(input_hash, bad_output, proof, iterations)
    print(f"  Tamper detection: {'PASSED' if not invalid else 'FAILED'}")
