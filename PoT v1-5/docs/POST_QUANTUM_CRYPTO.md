# Post-Quantum Cryptography for Proof of Time

## Overview

Proof of Time v2.7.0 introduces quantum-resistant cryptographic primitives following NIST post-quantum standards. This document describes the implementation, migration strategy, and usage.

## Quantum Threat Model

### Current Vulnerabilities (Legacy Mode)

| Primitive | Algorithm | Vulnerability | Timeline |
|-----------|-----------|---------------|----------|
| Signatures | Ed25519 | Shor's algorithm | ~10-15 years |
| VDF | Wesolowski (RSA) | Shor's algorithm | ~10-15 years |
| Hashing | SHA-256 | Grover (sqrt speedup) | Secure (128-bit) |

### Post-Quantum Solutions

| Primitive | Algorithm | Standard | Security |
|-----------|-----------|----------|----------|
| Signatures | SPHINCS+ | NIST FIPS 205 | Hash-based, quantum-safe |
| Hashing | SHA3-256 | NIST FIPS 202 | 256-bit quantum security |
| VDF | SHAKE256 + STARK | Hash-based | Quantum-safe |
| Key Exchange | ML-KEM (Kyber) | NIST FIPS 203 | Lattice-based |

## Architecture

```
                    ┌─────────────────────────────┐
                    │       NodeConfig            │
                    │   crypto: CryptoConfig      │
                    └─────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │      CryptoProvider         │
                    │    (Abstract Interface)     │
                    │                             │
                    │  hash(data) -> bytes        │
                    │  sign(sk, msg) -> bytes     │
                    │  verify(pk, msg, sig) -> bool│
                    │  vdf_compute(...) -> Proof  │
                    │  vdf_verify(proof) -> bool  │
                    └─────────────────────────────┘
                          │         │         │
           ┌──────────────┼─────────┼─────────┼──────────────┐
           ▼              ▼         ▼         ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  Legacy   │  │    PQ     │  │  Hybrid   │  │  Future   │
    │           │  │           │  │           │  │           │
    │ Ed25519   │  │ SPHINCS+  │  │ Ed25519 + │  │ ML-DSA    │
    │ SHA-256   │  │ SHA3-256  │  │ SPHINCS+  │  │ SLH-DSA   │
    │ Wesolowski│  │ SHAKE256  │  │           │  │           │
    └───────────┘  └───────────┘  └───────────┘  └───────────┘
```

## Crypto Backends

### 1. Legacy (Default)
- **Signatures**: Ed25519 (64-byte signatures)
- **Hashing**: SHA-256
- **VDF**: Wesolowski over RSA-2048
- **Status**: VULNERABLE to quantum computers

### 2. Post-Quantum
- **Signatures**: SPHINCS+-SHAKE-128f (~17KB signatures)
- **Hashing**: SHA3-256 (NIST FIPS 202)
- **VDF**: SHAKE256 iterations + STARK proofs
- **Status**: QUANTUM-RESISTANT

### 3. Hybrid (Transition)
- Signs with BOTH Ed25519 AND SPHINCS+
- Accepts either signature during transition
- **Use for**: Gradual migration

## Usage

### Configuration

```python
from config import NodeConfig, CryptoConfig

# Post-quantum mode
config = NodeConfig()
config.crypto = CryptoConfig(
    backend="post_quantum",
    sphincs_variant="fast",  # or "secure"
    vdf_backend="shake256",
    stark_proofs_enabled=True
)

# Initialize provider
provider = config.crypto.initialize_provider()
```

### Environment Variables

```bash
# Set crypto backend
export POT_CRYPTO_BACKEND=post_quantum  # legacy|post_quantum|hybrid

# SPHINCS+ variant
export POT_SPHINCS_VARIANT=fast  # fast (~17KB) or secure (~29KB)

# VDF backend
export POT_VDF_BACKEND=shake256  # wesolowski|shake256
```

### Direct API Usage

```python
from pantheon.prometheus import get_crypto_provider, CryptoBackend

# Get post-quantum provider
pq = get_crypto_provider(CryptoBackend.POST_QUANTUM)

# Hashing (SHA3-256)
hash_value = pq.hash(b"data")

# Key generation
secret_key, public_key = pq.generate_keypair()

# Signing (SPHINCS+)
signature = pq.sign(secret_key, message)  # ~17KB signature
valid = pq.verify(public_key, message, signature)

# VDF computation
proof = pq.vdf_compute(input_data, difficulty=1_000_000)
valid = pq.vdf_verify(proof)

# VRF (post-quantum)
beta, vrf_proof = pq.vrf_prove(secret_key, alpha)
valid = pq.vrf_verify(public_key, alpha, beta, vrf_proof)
```

## SPHINCS+ Signatures

### Variants

| Variant | Signature Size | Sign Time | Verify Time | Use Case |
|---------|---------------|-----------|-------------|----------|
| SPHINCS+-SHAKE-128f | ~17 KB | ~100 ms | ~10 ms | Normal transactions |
| SPHINCS+-SHAKE-256s | ~29 KB | ~200 ms | ~20 ms | Critical operations |

### Trade-offs

**Pros:**
- Quantum-resistant (hash-based)
- No trusted setup
- Stateless (no state management)
- Conservative security assumptions

**Cons:**
- Large signatures (~17-29 KB vs 64 bytes for Ed25519)
- Slower signing (~100 ms vs <1 ms)
- Increased block size

## SHAKE256 VDF

### Design

```
output = SHAKE256(SHAKE256(SHAKE256(...SHAKE256(input)...)))
                          ↑ T iterations
```

### Properties

- **Sequential**: Each iteration depends on previous output
- **Quantum-resistant**: SHAKE256 is secure against Grover
- **Verifiable**: STARK proofs enable O(log T) verification

### STARK Proofs

When Winterfell is compiled:
- Proof size: ~50-200 KB
- Verification: O(log T) operations
- No trusted setup

Fallback (without Winterfell):
- Checkpoint-based verification
- Sample random segments
- Slower but functional

### Building Winterfell Extension

```bash
cd winterfell_stark
./build.sh release

# Or with maturin
maturin develop --release
```

## Migration Strategy

### Phase 1: Preparation (Current)
1. Deploy hybrid mode to testnet
2. Monitor performance impact
3. Collect metrics on signature sizes

### Phase 2: Transition
1. Announce deprecation timeline
2. Enable hybrid mode on mainnet
3. Both signature types accepted

### Phase 3: Enforcement
1. Set activation height
2. Require post-quantum signatures
3. Legacy signatures rejected

### Backward Compatibility

- Historical blocks with Ed25519 signatures remain valid
- Hybrid mode accepts both signature types
- VDF proofs from both backends can be verified

## Performance Impact

### Signature Size Comparison

| Algorithm | Size | Increase |
|-----------|------|----------|
| Ed25519 | 64 B | baseline |
| SPHINCS+-128f | 17,088 B | 267x |
| SPHINCS+-256s | 29,792 B | 465x |

### Block Size Impact

For a block with 1000 transactions:
- Legacy: ~64 KB signatures
- Post-quantum: ~17 MB signatures

**Mitigations:**
- Signature aggregation (future)
- Compression
- Pruning old signatures

### Timing Comparison

| Operation | Ed25519 | SPHINCS+ |
|-----------|---------|----------|
| Key Gen | <1 ms | ~50 ms |
| Sign | <1 ms | ~100 ms |
| Verify | <1 ms | ~10 ms |

## Dependencies

### Required

```
liboqs-python>=0.9.0   # SPHINCS+, ML-KEM
```

### Optional (for STARK)

```
maturin>=1.4.0         # Rust-Python bridge
```

### Installing liboqs

```bash
# macOS
brew install liboqs

# Ubuntu
sudo apt install liboqs-dev

# Then Python bindings
pip install liboqs-python
```

## Security Considerations

### Key Storage

SPHINCS+ keys are larger:
- Secret key: 64 bytes (128f) or 128 bytes (256s)
- Public key: 32 bytes (128f) or 64 bytes (256s)

Ensure secure storage with appropriate encryption.

### Side-Channel Resistance

SPHINCS+ implementation uses constant-time operations for:
- Hash computations
- Signature generation
- Verification

### Randomness

SPHINCS+ signing uses internal randomness. Ensure:
- System RNG is properly seeded
- `/dev/urandom` available on Unix
- `CryptGenRandom` on Windows

## Testing

```bash
# Run all PQ crypto tests
pytest tests/test_pq_crypto.py -v

# Test specific component
pytest tests/test_pq_crypto.py::TestSPHINCSPlus -v
pytest tests/test_pq_crypto.py::TestSHAKE256VDF -v
pytest tests/test_pq_crypto.py::TestPostQuantumCryptoProvider -v
```

## Future Work

1. **ML-DSA (Dilithium)**: Alternative PQ signature with smaller signatures
2. **Signature Aggregation**: Reduce block size impact
3. **Class Group VDF**: Alternative quantum-resistant VDF
4. **Hybrid Encryption**: ML-KEM + X25519

## References

- [NIST FIPS 202](https://csrc.nist.gov/publications/detail/fips/202/final) - SHA-3 Standard
- [NIST FIPS 205](https://csrc.nist.gov/pubs/fips/205/final) - SPHINCS+ (SLH-DSA)
- [NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) - ML-KEM (Kyber)
- [Winterfell](https://github.com/facebook/winterfell) - STARK Prover
- [liboqs](https://github.com/open-quantum-safe/liboqs) - Open Quantum Safe
