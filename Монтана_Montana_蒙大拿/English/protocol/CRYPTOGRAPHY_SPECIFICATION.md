# Montana Protocol Cryptography Specification

**Post-Quantum Cryptography from Genesis**
**Montana Protocol v1.0**

---

## Executive Summary

Montana Protocol uses **post-quantum cryptography** (ML-DSA-65, ML-KEM-768) from genesis. Unlike Bitcoin/Ethereum which will require hard forks when quantum computers arrive, Montana is already protected.

**Key Innovation:**
```
Bitcoin/Ethereum: ECDSA → hard fork later
Montana: ML-DSA-65 from genesis → already protected
```

---

## 1. Core Cryptographic Primitives

### 1.1 Digital Signatures: ML-DSA-65

**Standard:** FIPS 204 (Module-Lattice-Based Digital Signature Algorithm)
**Security Level:** NIST Level 3 (equivalent to 128-bit post-quantum security)

**Parameters:**
```rust
Algorithm:       ML-DSA-65 (Dilithium variant)
Private key:     4000 bytes
Public key:      1952 bytes
Signature:       3293 bytes
Base:            Lattice-based cryptography
Quantum attack:  Resistant (no Shor's algorithm)
```

**Operations:**
```rust
// Key generation
(private_key, public_key) = ML-DSA-65.KeyGen()

// Signing
signature = ML-DSA-65.Sign(private_key, message)

// Verification
valid = ML-DSA-65.Verify(public_key, message, signature)
```

**Usage in Montana:**
- Node identity signatures
- Transaction signatures
- Presence proof signatures
- Block producer signatures

### 1.2 Key Encapsulation: ML-KEM-768

**Standard:** FIPS 203 (Module-Lattice-Based Key Encapsulation Mechanism)
**Security Level:** NIST Level 3

**Parameters:**
```rust
Algorithm:       ML-KEM-768 (Kyber variant)
Public key:      1184 bytes
Ciphertext:      1088 bytes
Shared secret:   32 bytes
Base:            Lattice-based cryptography
```

**Operations:**
```rust
// Key generation
(private_key, public_key) = ML-KEM-768.KeyGen()

// Encapsulation
(ciphertext, shared_secret) = ML-KEM-768.Encaps(public_key)

// Decapsulation
shared_secret = ML-KEM-768.Decaps(private_key, ciphertext)
```

**Usage in Montana:**
- Encrypted channels between nodes
- Key exchange in Noise XX protocol
- Secure communication initialization

### 1.3 Hash Functions

**Primary:** SHA3-256 (Keccak)
```rust
hash = SHA3-256(data)
```

**Usage:**
- Block hashes
- Transaction hashes
- Merkle tree construction
- Lottery seed generation
- Address derivation (see section 2)

---

## 2. Address System

### 2.1 Node Address Format

Montana uses **cryptographic addresses** derived from public keys, not IP addresses.

**Format:**
```
Address = "mt" + SHA256(public_key)[:20].hex()
```

**Structure:**
```
mt + <40 hex characters>
│    └── First 20 bytes (40 hex chars) of SHA256 hash
└── Montana prefix

Example: mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a
```

**Length:**
- Prefix: 2 characters (`mt`)
- Hash: 40 hex characters (20 bytes)
- Total: 42 characters

**Generation Algorithm:**
```rust
fn public_key_to_address(public_key: &[u8]) -> String {
    // 1. SHA256 hash of public key
    let hash = sha256(public_key);

    // 2. Take first 20 bytes
    let address_bytes = &hash[..20];

    // 3. Hex encode and add prefix
    format!("mt{}", hex::encode(address_bytes))
}
```

**Security Properties:**
- ✅ **Collision resistance:** SHA256 security
- ✅ **Preimage resistance:** Cannot derive public key from address
- ✅ **IP independence:** Address doesn't depend on network location
- ✅ **Post-quantum:** Derived from ML-DSA-65 public key

### 2.2 User Addresses

For simplified user experience, Montana Protocol supports multiple address types:

1. **Full Node:** Cryptographic address (mt...)
2. **Light Client:** Cryptographic address (mt...)
3. **Social Identity:** External ID (e.g., Telegram ID for UX)

**Note:** Social IDs are UX convenience only. Protocol-level operations always use cryptographic addresses.

---

## 3. Presence Proof Signatures

### 3.1 Message Format

Every node signs its presence every τ₁ (1 minute):

```rust
message = "MONTANA_PRESENCE_V1:"
        ‖ timestamp             // Unix timestamp (8 bytes)
        ‖ prev_slice_hash       // SHA3-256 hash (32 bytes)
        ‖ pubkey               // ML-DSA-65 public key (1952 bytes)
        ‖ τ₂_index             // T2 slice index (8 bytes)
```

**Total message size:** ~2000 bytes

### 3.2 Signature Generation

```rust
fn sign_presence(
    private_key: &PrivateKey,
    timestamp: u64,
    prev_slice_hash: &[u8; 32],
    pubkey: &PublicKey,
    t2_index: u64
) -> Signature {
    // Construct message
    let mut message = Vec::new();
    message.extend_from_slice(b"MONTANA_PRESENCE_V1:");
    message.extend_from_slice(&timestamp.to_le_bytes());
    message.extend_from_slice(prev_slice_hash);
    message.extend_from_slice(&pubkey.as_bytes());
    message.extend_from_slice(&t2_index.to_le_bytes());

    // Sign with ML-DSA-65
    ML_DSA_65::sign(private_key, &message)
}
```

**Signature size:** 3293 bytes

### 3.3 Verification

```rust
fn verify_presence(
    pubkey: &PublicKey,
    signature: &Signature,
    timestamp: u64,
    prev_slice_hash: &[u8; 32],
    t2_index: u64
) -> bool {
    // Reconstruct message
    let mut message = Vec::new();
    message.extend_from_slice(b"MONTANA_PRESENCE_V1:");
    message.extend_from_slice(&timestamp.to_le_bytes());
    message.extend_from_slice(prev_slice_hash);
    message.extend_from_slice(&pubkey.as_bytes());
    message.extend_from_slice(&t2_index.to_le_bytes());

    // Verify with ML-DSA-65
    ML_DSA_65::verify(pubkey, &message, signature)
}
```

---

## 4. Transaction Signatures

### 4.1 Transaction Format

```rust
struct Transaction {
    from:      Address,        // mt... (42 chars)
    to:        Address,        // mt... (42 chars)
    amount:    u64,            // Seconds of time
    timestamp: u64,            // Unix timestamp
    nonce:     u64,            // Anti-replay
    signature: Signature,      // ML-DSA-65 signature
}
```

### 4.2 Signing Process

```rust
fn sign_transaction(
    private_key: &PrivateKey,
    tx: &Transaction
) -> Signature {
    // Construct canonical message
    let mut message = Vec::new();
    message.extend_from_slice(b"MONTANA_TX_V1:");
    message.extend_from_slice(tx.from.as_bytes());
    message.extend_from_slice(tx.to.as_bytes());
    message.extend_from_slice(&tx.amount.to_le_bytes());
    message.extend_from_slice(&tx.timestamp.to_le_bytes());
    message.extend_from_slice(&tx.nonce.to_le_bytes());

    // Sign with ML-DSA-65
    ML_DSA_65::sign(private_key, &message)
}
```

### 4.3 Verification

```rust
fn verify_transaction(tx: &Transaction) -> bool {
    // 1. Get public key from address
    let pubkey = resolve_address_to_pubkey(&tx.from)?;

    // 2. Reconstruct message
    let mut message = Vec::new();
    message.extend_from_slice(b"MONTANA_TX_V1:");
    message.extend_from_slice(tx.from.as_bytes());
    message.extend_from_slice(tx.to.as_bytes());
    message.extend_from_slice(&tx.amount.to_le_bytes());
    message.extend_from_slice(&tx.timestamp.to_le_bytes());
    message.extend_from_slice(&tx.nonce.to_le_bytes());

    // 3. Verify signature
    ML_DSA_65::verify(&pubkey, &message, &tx.signature)
}
```

---

## 5. Encrypted Communication

### 5.1 Noise XX + ML-KEM Hybrid

Montana uses **hybrid encryption** combining classical and post-quantum algorithms:

```
Classical:        X25519 (Curve25519 ECDH)
Post-quantum:     ML-KEM-768
Protocol:         Noise XX
```

**Security property:**
```
If either X25519 OR ML-KEM-768 is secure → communication is secure
```

### 5.2 Handshake Pattern

```
XX:
  -> e
  <- e, ee, s, es
  -> s, se
```

**With hybrid KEM:**
```
-> e, ML-KEM(e)
<- e, ee, ML-KEM(e), s, es, ML-KEM(s)
-> s, se, ML-KEM(s)
```

### 5.3 Key Derivation

```rust
// After handshake completes
transport_keys = HKDF(
    classical_shared_secret ‖ post_quantum_shared_secret,
    "MONTANA_TRANSPORT_V1"
)
```

---

## 6. Block Producer Selection

### 6.1 Deterministic Lottery

Producer selection uses **deterministic randomness** based on previous block:

```rust
fn select_producer(
    prev_slice_hash: &[u8; 32],
    t2_index: u64,
    eligible_nodes: &[Node]
) -> Node {
    // Generate seed
    let seed = SHA3_256(prev_slice_hash ‖ t2_index);

    // Weighted selection
    weighted_random_select(eligible_nodes, seed)
}
```

### 6.2 Grinding Protection

**CRITICAL:** Seed is fixed BEFORE producer can influence it.

```rust
// ✅ CORRECT:
seed = SHA3(prev_slice_hash ‖ t2_index)

// ❌ WRONG:
seed = SHA3(prev_slice_hash ‖ t2_index ‖ presence_root)
                                       ^^^^^^^^^^^^^^^^
                                       Producer controls this!
```

---

## 7. Attack Resistance

### 7.1 IP Hijacking

**Attack:** Attacker takes over IP address of node

**Defense:**
```
Address = mt + SHA256(public_key)
        ≠ IP address

Attacker has IP but not private key
→ Cannot sign transactions
→ Attack BLOCKED
```

### 7.2 DNS Spoofing

**Attack:** Attacker poisons DNS records

**Defense:**
```
Alias (amsterdam.montana.network) = UX convenience only
Real address = mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a

DNS poisoning doesn't affect cryptographic address
→ Attack BLOCKED
```

### 7.3 Man-in-the-Middle

**Attack:** Intercept and modify messages

**Defense:**
```
All messages signed with ML-DSA-65
Modified message → Invalid signature
→ Attack DETECTED
```

### 7.4 Quantum Computer Attack

**Attack:** Use Shor's algorithm to break ECDSA

**Defense:**
```
Montana uses ML-DSA-65 (lattice-based)
Shor's algorithm doesn't work on lattices
→ Attack IMPOSSIBLE
```

### 7.5 Harvest Now, Decrypt Later

**Attack:** Store encrypted traffic now, decrypt when quantum computer available

**Defense:**
```
Montana uses ML-KEM-768 from genesis
Future quantum computer cannot decrypt
→ Attack BLOCKED
```

---

## 8. Domain Separation

Different keys for different purposes:

```rust
// Presence signatures
const PRESENCE_DOMAIN: &[u8] = b"MONTANA_PRESENCE_V1:";

// Transaction signatures
const TX_DOMAIN: &[u8] = b"MONTANA_TX_V1:";

// Block signatures
const BLOCK_DOMAIN: &[u8] = b"MONTANA_BLOCK_V1:";

// Transport encryption
const TRANSPORT_DOMAIN: &[u8] = b"MONTANA_TRANSPORT_V1";
```

**Security property:** Signature from one domain cannot be replayed in another.

---

## 9. Implementation Notes

### 9.1 Current Status

**Production:**
- ✅ ML-DSA-65 for signatures
- ✅ ML-KEM-768 for key exchange
- ✅ Cryptographic addresses (mt...)
- ✅ Hybrid Noise XX protocol

**In Progress:**
- 🔄 Hardware Security Module (HSM) integration
- 🔄 Multi-signature wallets
- 🔄 Zero-knowledge proofs for privacy

### 9.2 Libraries

**Rust:**
```toml
[dependencies]
pqcrypto-dilithium = "0.5"    # ML-DSA-65
pqcrypto-kyber = "0.8"        # ML-KEM-768
sha3 = "0.10"                 # SHA3-256
hex = "0.4"                   # Hex encoding
```

**Python (Production):**
```python
from dilithium_py.ml_dsa import ML_DSA_65  # Post-quantum signatures
import hashlib
```

---

## 10. Current Implementation

### MAINNET: ML-DSA-65 Active

**Python bot uses ML-DSA-65 (FIPS 204):**
```python
# node_crypto.py
from dilithium_py.ml_dsa import ML_DSA_65

def generate_keypair():
    public_key, private_key = ML_DSA_65.keygen()
    return private_key.hex(), public_key.hex()

def sign_message(private_key_hex: str, message: str) -> str:
    private_bytes = bytes.fromhex(private_key_hex)
    message_bytes = message.encode('utf-8')
    signature = ML_DSA_65.sign(private_bytes, message_bytes)
    return signature.hex()

def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    public_bytes = bytes.fromhex(public_key_hex)
    message_bytes = message.encode('utf-8')
    signature = bytes.fromhex(signature_hex)
    return ML_DSA_65.verify(public_bytes, message_bytes, signature)
```

**Key Sizes (ML-DSA-65):**
- Private key: 4032 bytes
- Public key: 1952 bytes
- Signature: 3309 bytes

### Why ML-DSA-65 from Genesis:

- Post-quantum protection from day one
- No migration needed when quantum computers arrive
- FIPS 204 NIST standard
- Protects against "harvest now, decrypt later" attacks

### Status: COMPLETE

**Timeline Achieved:**
- **Q1 2026:** ~~Prototype with Ed25519~~ ML-DSA-65 MAINNET
- **Q2-Q4 2026:** Post-quantum ready from genesis

---

## 11. References

### Standards
- [FIPS 204 - ML-DSA](https://csrc.nist.gov/publications/detail/fips/204/final)
- [FIPS 203 - ML-KEM](https://csrc.nist.gov/publications/detail/fips/203/final)
- [Noise Protocol Framework](https://noiseprotocol.org/)

### Montana Protocol
- [001_ACP.md](001_ACP.md) - Atemporal Coordinate Presence
- [007_POST_QUANTUM.md](007_POST_QUANTUM.md) - Post-Quantum from Genesis
- [Montana GitHub](https://github.com/efir369999/junomontanaagibot)

### Research
- [NIST Post-Quantum Cryptography](https://csrc.nist.gov/projects/post-quantum-cryptography)
- [Dilithium Paper](https://pq-crystals.org/dilithium/)
- [Kyber Paper](https://pq-crystals.org/kyber/)

---

## 12. Security Analysis

### Threat Model

**Assumptions:**
- ✅ SHA3-256 is collision resistant
- ✅ Lattice problems are hard (even for quantum computers)
- ✅ Secure hardware (HSM, Secure Element) is uncompromised
- ✅ FIDO2 biometrics cannot be forged

**Adversary capabilities:**
- Quantum computer with Shor's algorithm
- Control of network infrastructure
- Large computational resources
- Social engineering attempts

**Protected against:**
- ✅ Quantum attacks (ML-DSA-65, ML-KEM-768)
- ✅ IP hijacking (cryptographic addresses)
- ✅ DNS spoofing (addresses independent of DNS)
- ✅ MITM (signed messages)
- ✅ Sybil attacks (FIDO2 biometrics)
- ✅ Replay attacks (nonces, timestamps)

**NOT protected against:**
- ❌ Private key theft from compromised device
- ❌ Social engineering of key holders
- ❌ Supply chain attacks on hardware

---

## Conclusion

Montana Protocol implements **post-quantum cryptography from genesis**, making it the first blockchain protected against quantum computers from day one. The use of ML-DSA-65 and ML-KEM-768 (NIST FIPS standards) ensures security even when quantum computers become practical.

**Key innovations:**
1. **Cryptographic addresses** — derived from public keys, not IP addresses
2. **Hybrid encryption** — combining classical and post-quantum algorithms
3. **Post-quantum from genesis** — no migration needed
4. **Domain separation** — preventing cross-context attacks

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
