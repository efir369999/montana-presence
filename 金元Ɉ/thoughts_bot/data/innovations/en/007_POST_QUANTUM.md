# Post-Quantum from Genesis

**Quantum-Resistant Cryptography from Day One**
**Montana Protocol v1.0**

---

## Abstract

Montana uses post-quantum cryptography (ML-DSA-65, ML-KEM-768) from genesis, not as a retrofit. When quantum computers become a threat, Montana will already be protected. Other networks will be forced to hard fork.

**Key difference:**
```
Bitcoin/Ethereum: ECDSA now → hard fork later
Montana: ML-DSA-65 from genesis → already protected
```

---

## 1. Introduction

### 1.1 Quantum Threat

| Algorithm | Vulnerable | Quantum Attack |
|-----------|------------|----------------|
| ECDSA (Bitcoin) | Yes | Shor's algorithm |
| Ed25519 (Solana) | Yes | Shor's algorithm |
| RSA | Yes | Shor's algorithm |
| **ML-DSA-65** | **No** | **Lattice-based** |

### 1.2 Retrofit Problem

```
Step 1: Quantum computer appears
Step 2: All ECDSA signatures vulnerable
Step 3: Hard fork for key migration
Step 4: Those who didn't migrate — lost funds
```

Montana avoids this by starting with post-quantum cryptography.

---

## 2. Cryptographic Primitives

### 2.1 Signatures: ML-DSA-65

**Source code:** [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs)

```rust
// FIPS 204 — Module-Lattice-Based Digital Signature
// Security level: NIST Level 3 (128-bit post-quantum)
// Signature size: 3293 bytes
// Public key size: 1952 bytes
```

### 2.2 Encryption: ML-KEM-768

```rust
// FIPS 203 — Module-Lattice-Based Key Encapsulation
// Security level: NIST Level 3
// Used in Noise XX for key exchange
```

### 2.3 Hybrid Encryption

**Source code:** [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs)

```rust
// Noise XX + ML-KEM-768
// Classical X25519 + post-quantum ML-KEM
// Protected even if one is broken
```

---

## 3. Why from Genesis?

### 3.1 Strategy Comparison

| Strategy | Complexity | Risk |
|----------|------------|------|
| Retrofit after threat | Hard fork, migration | Fund loss |
| Retrofit in advance | Hard fork, migration | Coordination difficulty |
| **From genesis** | **No migration** | **No risk** |

### 3.2 Harvest Now, Decrypt Later

```
Attacker today:
1. Intercepts encrypted traffic
2. Stores on disk
3. Waits for quantum computer
4. Decrypts everything

Montana is protected from this attack from day one.
```

---

## 4. Scientific Novelty

1. **Post-quantum from genesis** — not retrofit, but original design
2. **Hybrid encryption** — X25519 + ML-KEM (protection from both attack classes)
3. **NIST standards** — not experimental algorithms, but finalized FIPS
4. **Domain separation** — different keys for different purposes

---

## 5. References

| Document | Link |
|----------|------|
| Cryptography code | [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs) |
| Noise code | [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs) |
| FIPS 204 (ML-DSA) | [NIST](https://csrc.nist.gov/publications/detail/fips/204/final) |
| FIPS 203 (ML-KEM) | [NIST](https://csrc.nist.gov/publications/detail/fips/203/final) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
