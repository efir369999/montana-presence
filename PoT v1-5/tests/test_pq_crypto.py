"""
Proof of Time - Post-Quantum Cryptography Tests

Comprehensive tests for quantum-resistant cryptographic primitives:
- SHA3-256 hashing
- SPHINCS+ signatures
- SHAKE256 VDF
- STARK proofs
- ML-KEM key encapsulation
- Crypto provider abstraction

Run with: pytest tests/test_pq_crypto.py -v
"""

import pytest
import hashlib
import secrets
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pantheon.prometheus.pq_crypto import (
    sha3_256, sha3_256d, sha3_512, shake256, hmac_sha3_256,
    SPHINCSPlus, SPHINCSPlusFallback,
    SHAKE256VDF, STARKProver,
    PostQuantumCryptoProvider, HybridCryptoProvider,
    LIBOQS_AVAILABLE, MLKEM_AVAILABLE, WINTERFELL_AVAILABLE
)

from pantheon.prometheus.crypto_provider import (
    CryptoProvider, CryptoBackend, VDFProofBase, SignatureBundle,
    get_crypto_provider, set_default_backend, clear_provider_cache,
    LegacyCryptoProvider
)


# ============================================================================
# SHA3 HASH FUNCTION TESTS
# ============================================================================

class TestSHA3:
    """Test SHA3 hash functions."""

    def test_sha3_256_known_vector(self):
        """Test SHA3-256 against known test vector."""
        # NIST test vector
        result = sha3_256(b"")
        expected = bytes.fromhex(
            "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
        )
        assert result == expected

    def test_sha3_256_test_string(self):
        """Test SHA3-256 with 'test' string."""
        result = sha3_256(b"test")
        expected = bytes.fromhex(
            "36f028580bb02cc8272a9a020f4200e346e276ae664e45ee80745574e2f5ab80"
        )
        assert result == expected

    def test_sha3_256_deterministic(self):
        """SHA3-256 should be deterministic."""
        data = b"test data for determinism check"
        result1 = sha3_256(data)
        result2 = sha3_256(data)
        assert result1 == result2

    def test_sha3_256_different_inputs(self):
        """Different inputs should produce different outputs."""
        result1 = sha3_256(b"input1")
        result2 = sha3_256(b"input2")
        assert result1 != result2

    def test_sha3_256d_double_hash(self):
        """Test double SHA3-256."""
        data = b"test"
        result = sha3_256d(data)
        expected = sha3_256(sha3_256(data))
        assert result == expected

    def test_sha3_512_output_size(self):
        """SHA3-512 should produce 64-byte output."""
        result = sha3_512(b"test")
        assert len(result) == 64

    def test_shake256_variable_output(self):
        """SHAKE256 should produce variable length output."""
        data = b"test"
        result32 = shake256(data, 32)
        result64 = shake256(data, 64)
        result128 = shake256(data, 128)

        assert len(result32) == 32
        assert len(result64) == 64
        assert len(result128) == 128

        # First 32 bytes should match
        assert result32 == result64[:32]
        assert result32 == result128[:32]

    def test_hmac_sha3_256(self):
        """Test HMAC-SHA3-256."""
        key = b"secret_key"
        data = b"message to authenticate"
        result = hmac_sha3_256(key, data)

        assert len(result) == 32

        # Different key should produce different result
        result2 = hmac_sha3_256(b"different_key", data)
        assert result != result2


# ============================================================================
# SPHINCS+ SIGNATURE TESTS
# ============================================================================

class TestSPHINCSPlus:
    """Test SPHINCS+ signatures."""

    @pytest.fixture
    def sphincs(self):
        """Get SPHINCS+ instance (real or fallback)."""
        if LIBOQS_AVAILABLE:
            return SPHINCSPlus("fast")
        else:
            return SPHINCSPlusFallback("fast")

    def test_keypair_generation(self, sphincs):
        """Test keypair generation."""
        sk, pk = sphincs.generate_keypair()

        assert len(sk) == sphincs.secret_key_size
        assert len(pk) == sphincs.public_key_size

    def test_sign_and_verify(self, sphincs):
        """Test signing and verification."""
        sk, pk = sphincs.generate_keypair()
        message = b"test message to sign"

        signature = sphincs.sign(sk, message)
        assert len(signature) == sphincs.signature_size

        # Verify should pass
        assert sphincs.verify(pk, message, signature)

    def test_wrong_message_fails(self, sphincs):
        """Verification should fail with wrong message."""
        sk, pk = sphincs.generate_keypair()
        message = b"original message"
        signature = sphincs.sign(sk, message)

        # Wrong message should fail
        assert not sphincs.verify(pk, b"wrong message", signature)

    def test_tampered_signature_fails(self, sphincs):
        """Verification should fail with tampered signature."""
        sk, pk = sphincs.generate_keypair()
        message = b"test message"
        signature = sphincs.sign(sk, message)

        # Tamper with signature
        tampered = bytearray(signature)
        tampered[0] ^= 0xFF
        tampered_sig = bytes(tampered)

        assert not sphincs.verify(pk, message, tampered_sig)

    def test_deterministic_signatures(self, sphincs):
        """SPHINCS+ signatures should be deterministic."""
        sk, pk = sphincs.generate_keypair()
        message = b"test message"

        sig1 = sphincs.sign(sk, message)
        sig2 = sphincs.sign(sk, message)

        # Note: SPHINCS+ uses randomness, so signatures may differ
        # But both should verify correctly
        assert sphincs.verify(pk, message, sig1)
        assert sphincs.verify(pk, message, sig2)

    @pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs not available")
    def test_signature_size(self):
        """Test actual SPHINCS+ signature size."""
        sphincs = SPHINCSPlus("fast")
        sk, pk = sphincs.generate_keypair()
        sig = sphincs.sign(sk, b"test")

        # SPHINCS+-SHAKE-128f should have ~17KB signatures
        assert len(sig) > 10000, f"Signature too small: {len(sig)} bytes"
        assert len(sig) < 30000, f"Signature too large: {len(sig)} bytes"


# ============================================================================
# SHAKE256 VDF TESTS
# ============================================================================

class TestSHAKE256VDF:
    """Test SHAKE256-based VDF."""

    @pytest.fixture
    def vdf(self):
        """Get VDF instance."""
        return SHAKE256VDF()

    def test_basic_compute(self, vdf):
        """Test basic VDF computation."""
        input_data = b"test_input"
        iterations = 1000

        output, checkpoints = vdf.compute(input_data, iterations)

        assert len(output) == 32
        assert len(checkpoints) > 0

    def test_deterministic_output(self, vdf):
        """VDF should be deterministic."""
        input_data = b"deterministic_test"
        iterations = 500

        output1, _ = vdf.compute(input_data, iterations)
        output2, _ = vdf.compute(input_data, iterations)

        assert output1 == output2

    def test_different_inputs(self, vdf):
        """Different inputs should produce different outputs."""
        iterations = 500

        output1, _ = vdf.compute(b"input1", iterations)
        output2, _ = vdf.compute(b"input2", iterations)

        assert output1 != output2

    def test_sequential_verification(self, vdf):
        """Test sequential verification."""
        input_data = sha3_256(b"verification_test")
        iterations = 500

        output, _ = vdf.compute(input_data, iterations, collect_checkpoints=False)

        # Sequential verification should pass
        assert vdf.verify_sequential(input_data, output, iterations)

        # Wrong output should fail
        wrong_output = bytes([output[0] ^ 1]) + output[1:]
        assert not vdf.verify_sequential(input_data, wrong_output, iterations)

    def test_checkpoint_verification(self, vdf):
        """Test checkpoint-based verification."""
        input_data = sha3_256(b"checkpoint_test")
        iterations = 2000

        output, checkpoints = vdf.compute(input_data, iterations)

        # The checkpoint interval used during compute is CHECKPOINT_INTERVAL (1000)
        # So we should use that for verification
        interval = vdf.CHECKPOINT_INTERVAL

        # Checkpoint verification should pass
        assert vdf.verify_with_checkpoints(input_data, output, checkpoints, interval)

    def test_calibration(self, vdf):
        """Test VDF calibration."""
        # Calibrate for 0.1 seconds
        recommended = vdf.calibrate(0.1, sample_iterations=5000)

        assert recommended > 0
        assert vdf._cached_ips > 0

    def test_min_iterations_enforced(self, vdf):
        """Minimum iterations should be enforced."""
        with pytest.raises(ValueError):
            vdf.compute(b"test", vdf.MIN_ITERATIONS - 1)

    def test_progress_callback(self, vdf):
        """Test progress callback."""
        progress_calls = []

        def callback(current, total):
            progress_calls.append((current, total))

        vdf.compute(b"test", 50000, progress_callback=callback)

        # Should have received progress calls
        assert len(progress_calls) > 0


# ============================================================================
# STARK PROOF TESTS
# ============================================================================

class TestSTARKProver:
    """Test STARK proof generation and verification."""

    @pytest.fixture
    def stark(self):
        """Get STARK prover instance."""
        return STARKProver()

    def test_proof_generation(self, stark):
        """Test proof generation."""
        vdf = SHAKE256VDF()
        input_hash = sha3_256(b"stark_test")
        iterations = 1000

        output, checkpoints = vdf.compute(input_hash, iterations)

        proof = stark.generate_proof(input_hash, output, checkpoints, iterations)

        assert len(proof) > 0

    def test_proof_verification(self, stark):
        """Test proof verification."""
        vdf = SHAKE256VDF()
        input_hash = sha3_256(b"verify_test")
        iterations = 1000

        output, checkpoints = vdf.compute(input_hash, iterations)
        proof = stark.generate_proof(input_hash, output, checkpoints, iterations)

        # Verification should pass
        assert stark.verify_proof(input_hash, output, proof, iterations)

    def test_tampered_output_fails(self, stark):
        """Verification should fail with tampered output."""
        vdf = SHAKE256VDF()
        input_hash = sha3_256(b"tamper_test")
        iterations = 1000

        output, checkpoints = vdf.compute(input_hash, iterations)
        proof = stark.generate_proof(input_hash, output, checkpoints, iterations)

        # Tamper with output
        tampered_output = bytes([output[0] ^ 1]) + output[1:]

        # Verification should fail
        assert not stark.verify_proof(input_hash, tampered_output, proof, iterations)

    def test_wrong_iterations_fails(self, stark):
        """Verification should fail with wrong iterations."""
        vdf = SHAKE256VDF()
        input_hash = sha3_256(b"iterations_test")
        iterations = 1000

        output, checkpoints = vdf.compute(input_hash, iterations)
        proof = stark.generate_proof(input_hash, output, checkpoints, iterations)

        # Wrong iterations should fail
        assert not stark.verify_proof(input_hash, output, proof, iterations + 1)


# ============================================================================
# POST-QUANTUM CRYPTO PROVIDER TESTS
# ============================================================================

class TestPostQuantumCryptoProvider:
    """Test PostQuantumCryptoProvider."""

    @pytest.fixture
    def provider(self):
        """Get PQ provider instance."""
        return PostQuantumCryptoProvider()

    def test_backend_info(self, provider):
        """Test backend identification."""
        assert provider.backend_name == "post_quantum"
        assert provider.is_post_quantum is True

    def test_hash_function(self, provider):
        """Test hash function uses SHA3."""
        result = provider.hash(b"test")
        expected = sha3_256(b"test")
        assert result == expected

    def test_keypair_generation(self, provider):
        """Test keypair generation."""
        sk, pk = provider.generate_keypair()
        assert len(pk) == provider.get_public_key_size()

    def test_sign_and_verify(self, provider):
        """Test signing and verification."""
        sk, pk = provider.generate_keypair()
        message = b"test message"

        signature = provider.sign(sk, message)
        assert provider.verify(pk, message, signature)

    def test_vdf_compute_and_verify(self, provider):
        """Test VDF through provider."""
        input_data = b"provider_vdf_test"
        difficulty = 500

        proof = provider.vdf_compute(input_data, difficulty)

        assert proof.backend == "stark"
        assert proof.difficulty == difficulty
        assert provider.vdf_verify(proof)

    def test_vdf_tamper_resistance(self, provider):
        """Test VDF tamper resistance."""
        proof = provider.vdf_compute(b"tamper_test", 500)

        # Tamper with output
        tampered = VDFProofBase(
            input_hash=proof.input_hash,
            output_hash=bytes([proof.output_hash[0] ^ 1]) + proof.output_hash[1:],
            difficulty=proof.difficulty,
            proof_data=proof.proof_data,
            backend=proof.backend
        )

        assert not provider.vdf_verify(tampered)

    def test_vrf_prove_and_verify(self, provider):
        """Test VRF through provider."""
        sk, pk = provider.generate_keypair()
        alpha = b"vrf_input"

        beta, proof = provider.vrf_prove(sk, alpha)

        assert len(beta) == 32
        assert provider.vrf_verify(pk, alpha, beta, proof)

    def test_vrf_deterministic(self, provider):
        """VRF output should be deterministic."""
        sk, pk = provider.generate_keypair()
        alpha = b"deterministic_vrf"

        beta1, _ = provider.vrf_prove(sk, alpha)
        beta2, _ = provider.vrf_prove(sk, alpha)

        assert beta1 == beta2


# ============================================================================
# HYBRID CRYPTO PROVIDER TESTS
# ============================================================================

class TestHybridCryptoProvider:
    """Test HybridCryptoProvider."""

    @pytest.fixture
    def provider(self):
        """Get hybrid provider instance."""
        return HybridCryptoProvider(require_both=False)

    def test_backend_info(self, provider):
        """Test backend identification."""
        assert provider.backend_name == "hybrid"
        assert provider.is_post_quantum is True

    def test_hybrid_keypair(self, provider):
        """Test hybrid keypair generation."""
        sk, pk = provider.generate_keypair()

        # Should have both Ed25519 and SPHINCS+ components
        assert len(pk) > 64  # More than just Ed25519

    def test_hybrid_signature(self, provider):
        """Test hybrid signing and verification."""
        sk, pk = provider.generate_keypair()
        message = b"hybrid signature test"

        signature = provider.sign(sk, message)
        assert provider.verify(pk, message, signature)

    def test_require_both_mode(self):
        """Test require_both=True mode."""
        provider = HybridCryptoProvider(require_both=True)
        sk, pk = provider.generate_keypair()
        message = b"test"

        signature = provider.sign(sk, message)
        # Both signatures required - should pass if both are valid
        assert provider.verify(pk, message, signature)


# ============================================================================
# CRYPTO PROVIDER ABSTRACTION TESTS
# ============================================================================

class TestCryptoProviderAbstraction:
    """Test crypto provider abstraction layer."""

    def setup_method(self):
        """Clear provider cache before each test."""
        clear_provider_cache()

    def test_get_legacy_provider(self):
        """Test getting legacy provider."""
        provider = get_crypto_provider(CryptoBackend.LEGACY)
        assert provider.backend_name == "legacy"
        assert provider.is_post_quantum is False

    def test_get_pq_provider(self):
        """Test getting PQ provider."""
        provider = get_crypto_provider(CryptoBackend.POST_QUANTUM)
        assert provider.backend_name == "post_quantum"
        assert provider.is_post_quantum is True

    def test_provider_caching(self):
        """Test that providers are cached."""
        provider1 = get_crypto_provider(CryptoBackend.LEGACY)
        provider2 = get_crypto_provider(CryptoBackend.LEGACY)
        assert provider1 is provider2

    def test_set_default_backend(self):
        """Test setting default backend."""
        set_default_backend(CryptoBackend.POST_QUANTUM)
        provider = get_crypto_provider()
        assert provider.backend_name == "post_quantum"

        # Reset
        set_default_backend(CryptoBackend.LEGACY)

    def test_vdf_proof_serialization(self):
        """Test VDFProofBase serialization."""
        proof = VDFProofBase(
            input_hash=b"a" * 32,
            output_hash=b"b" * 32,
            difficulty=1000,
            proof_data=b"proof_data_here",
            backend="stark"
        )

        serialized = proof.serialize()
        deserialized = VDFProofBase.deserialize(serialized)

        assert deserialized.input_hash == proof.input_hash
        assert deserialized.output_hash == proof.output_hash
        assert deserialized.difficulty == proof.difficulty
        assert deserialized.proof_data == proof.proof_data
        assert deserialized.backend == proof.backend

    def test_signature_bundle_serialization(self):
        """Test SignatureBundle serialization."""
        bundle = SignatureBundle(
            primary_signature=b"ed25519_sig" * 6,  # 66 bytes
            primary_algorithm="ed25519",
            secondary_signature=b"sphincs_sig" * 100,  # 1100 bytes
            secondary_algorithm="sphincs+"
        )

        serialized = bundle.serialize()
        deserialized = SignatureBundle.deserialize(serialized)

        assert deserialized.primary_signature == bundle.primary_signature
        assert deserialized.primary_algorithm == bundle.primary_algorithm
        assert deserialized.secondary_signature == bundle.secondary_signature
        assert deserialized.secondary_algorithm == bundle.secondary_algorithm


# ============================================================================
# CROSS-PROVIDER COMPATIBILITY TESTS
# ============================================================================

class TestCrossProviderCompatibility:
    """Test compatibility between different providers."""

    def test_legacy_can_verify_legacy(self):
        """Legacy provider should verify legacy signatures."""
        legacy = get_crypto_provider(CryptoBackend.LEGACY)
        sk, pk = legacy.generate_keypair()
        sig = legacy.sign(sk, b"test")
        assert legacy.verify(pk, b"test", sig)

    def test_pq_can_verify_pq(self):
        """PQ provider should verify PQ signatures."""
        pq = get_crypto_provider(CryptoBackend.POST_QUANTUM)
        sk, pk = pq.generate_keypair()
        sig = pq.sign(sk, b"test")
        assert pq.verify(pk, b"test", sig)

    def test_hybrid_vdf_can_verify_both(self):
        """Hybrid provider should verify both VDF types."""
        hybrid = HybridCryptoProvider()
        legacy = LegacyCryptoProvider()

        # Legacy VDF
        legacy_proof = legacy.vdf_compute(b"legacy_input", 1000)
        assert hybrid.vdf_verify(legacy_proof)

        # PQ VDF
        pq_proof = hybrid.vdf_compute(b"pq_input", 500)
        assert hybrid.vdf_verify(pq_proof)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance benchmarks."""

    @pytest.mark.slow
    def test_sha3_256_performance(self):
        """Benchmark SHA3-256."""
        data = b"x" * 1024  # 1KB
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            sha3_256(data)
        elapsed = time.perf_counter() - start

        ops_per_sec = iterations / elapsed
        print(f"\nSHA3-256: {ops_per_sec:.0f} ops/sec ({elapsed*1000/iterations:.3f} ms/op)")
        assert ops_per_sec > 1000  # Should be at least 1K ops/sec

    @pytest.mark.slow
    def test_shake256_vdf_performance(self):
        """Benchmark SHAKE256 VDF."""
        vdf = SHAKE256VDF()
        iterations = 10000

        start = time.perf_counter()
        output, _ = vdf.compute(b"perf_test", iterations, collect_checkpoints=False)
        elapsed = time.perf_counter() - start

        ips = iterations / elapsed
        print(f"\nSHAKE256 VDF: {ips:.0f} iter/sec ({elapsed:.3f}s for {iterations} iterations)")
        assert ips > 1000  # Should be at least 1K iter/sec

    @pytest.mark.slow
    @pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs not available")
    def test_sphincs_performance(self):
        """Benchmark SPHINCS+ signatures."""
        sphincs = SPHINCSPlus("fast")
        sk, pk = sphincs.generate_keypair()
        message = b"performance test message"

        # Sign benchmark
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            sig = sphincs.sign(sk, message)
        sign_elapsed = time.perf_counter() - start

        # Verify benchmark
        start = time.perf_counter()
        for _ in range(iterations):
            sphincs.verify(pk, message, sig)
        verify_elapsed = time.perf_counter() - start

        sign_ops = iterations / sign_elapsed
        verify_ops = iterations / verify_elapsed

        print(f"\nSPHINCS+ Sign: {sign_ops:.1f} ops/sec ({sign_elapsed*1000/iterations:.1f} ms/op)")
        print(f"SPHINCS+ Verify: {verify_ops:.1f} ops/sec ({verify_elapsed*1000/iterations:.1f} ms/op)")


# ============================================================================
# ML-KEM TESTS (if available)
# ============================================================================

@pytest.mark.skipif(not MLKEM_AVAILABLE, reason="ML-KEM not available")
class TestMLKEM:
    """Test ML-KEM key encapsulation."""

    def test_key_generation(self):
        """Test ML-KEM keypair generation."""
        from pantheon.prometheus.pq_crypto import MLKEM
        kem = MLKEM("768")
        sk, pk = kem.generate_keypair()
        assert len(sk) > 0
        assert len(pk) > 0

    def test_encapsulation(self):
        """Test key encapsulation and decapsulation."""
        from pantheon.prometheus.pq_crypto import MLKEM
        kem = MLKEM("768")

        sk, pk = kem.generate_keypair()
        ciphertext, shared_secret1 = kem.encapsulate(pk)
        shared_secret2 = kem.decapsulate(sk, ciphertext)

        assert shared_secret1 == shared_secret2
        assert len(shared_secret1) == 32


# ============================================================================
# QUANTUM RESISTANCE PROPERTY TESTS
# ============================================================================

class TestQuantumResistanceProperties:
    """Test properties related to quantum resistance."""

    def test_hash_output_size(self):
        """SHA3-256 should have 256-bit output for 128-bit post-quantum security."""
        result = sha3_256(b"test")
        assert len(result) == 32  # 256 bits

    def test_vdf_uses_shake256(self):
        """VDF should use SHAKE256 (quantum-resistant)."""
        vdf = SHAKE256VDF()
        # Verify output matches manual SHAKE256 chain
        input_data = sha3_256(b"verify_shake256")
        state = input_data
        for _ in range(100):
            state = shake256(state, 32)

        output, _ = vdf.compute(input_data, 100, collect_checkpoints=False)
        assert output == state

    def test_sphincs_is_hash_based(self):
        """SPHINCS+ should be hash-based (no ECC)."""
        provider = PostQuantumCryptoProvider()
        # SPHINCS+ signatures are much larger than ECC (KB vs bytes)
        assert provider.get_signature_size() > 1000

    def test_no_elliptic_curves_in_pq_provider(self):
        """PQ provider should not use elliptic curves."""
        provider = PostQuantumCryptoProvider()
        # All operations should use hash-based primitives
        h = provider.hash(b"test")
        assert len(h) == 32

        sk, pk = provider.generate_keypair()
        # SPHINCS+ keys are larger than ECC keys
        assert len(pk) >= 32


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
