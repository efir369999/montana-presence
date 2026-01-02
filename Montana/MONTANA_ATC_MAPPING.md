# Ɉ Montana: Temporal Time Unit ↔ ATC Layer Mapping

**Ɉ Montana Version:** 3.6
**Ticker:** $MONT
**Architecture:** Timechain
**ATC Version:** 10.0 (L-1 v2.1, L0 v1.0, L1 v1.1, L2 v1.0)

---

## Overview

**Ɉ** (inverted t) is a Temporal Time Unit. **Montana** is the Timechain that produces it.

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

**Timechain:** chain of time, bounded by physics.

**v3.6:** Timechain architecture, UTC finality, ±5s tolerance, platform-independent light clients.

This document maps Ɉ Montana components to their foundational ATC layers, showing exactly which constraints and primitives the mechanism relies upon.

---

## Layer -1: Physical Constraints

Montana relies on these L-1 physical constraints:

| L-1 Constraint | Montana Usage | Montana Component |
|----------------|---------------|-------------------|
| **L-1.1** Thermodynamic Arrow | Irreversibility of VDF computation | VDF, Block finality |
| **L-1.3** Landauer Limit | Bounds adversary computation | Anti-spam PoW |
| **L-1.4** Speed of Light | Minimum network propagation delay | Block timing (600s) |
| **L-1.5** Time Uniformity | Sequential computation is universal | VDF consistency |

### Montana VDF Sequentiality → L-1

```python
# Montana core assumption
# Class Group squaring is sequential - no algorithm computes
# g^(2^T) faster than T sequential squarings

# Maps to L-1: Physical constraint that time is sequential
# Computation must happen step-by-step
```

**Type:** Physical (Type P) + Mathematical (Type B)

---

## Layer 0: Computational Constraints

Montana relies on these L0 computational primitives:

| L0 Primitive | Montana Usage | Type |
|--------------|---------------|------|
| **L-0.3.3** SHA-3 | sha3_256 for hashing | Type C |
| **L-0.4.2** ML-KEM-768 | Key encapsulation | Type B |
| **L-0.4.4** SPHINCS+-SHAKE-128f | Transaction/heartbeat signatures | Type C |
| **L-0.3.2** HMAC (PRF) | Key derivation | Type B |
| **L-0.2.1** Birthday Bound | Ring signature security | Type A |
| **Class Groups** | VDF sequential computation | Type B |

### Montana Cryptography → L0

```python
# Montana choices
SIGNATURE_SCHEME = "SPHINCS+-SHAKE-128f"  # L-0.4.4
KEY_ENCAPSULATION = "ML-KEM-768"          # L-0.4.2
HASH_FUNCTION = "SHA3-256"                # L-0.3.3
VDF_TYPE = "class_group"                  # Wesolowski 2019
```

**Post-Quantum Status:** Montana is post-quantum secure from day one, using NIST FIPS 203/204/205 standards.

---

## Layer 1: Protocol Primitives

Montana uses these L1 primitives:

| L1 Primitive | Montana Implementation | Section |
|--------------|------------------------|---------|
| **L-1.1** VDF | Class Group VDF (Wesolowski 2019), T = 2²⁴ base | §5 |
| **L-1.2** VRF | ECVRF for eligibility | §10 |
| **L-1.3** Commitment | Pedersen (privacy), Hash (general) | §14 |
| **L-1.4** Timestamp | Linked timestamps with VDF chain | §7 |
| **L-1.5** Ordering | DAG-PHANTOM | §10 |

### Montana Class Group VDF → L-1.1

Montana uses Class Group VDF with Wesolowski proofs (Wesolowski 2019).

| Property | Montana (Class Group VDF) |
|----------|---------------------------|
| Construction | Wesolowski 2019 |
| Sequentiality basis | Mathematical (group structure) |
| Security type | Type B (reduction to class group order problem) |
| Proof size | ~256 bytes |
| Verification | O(log T) |
| Trusted setup | None required |

**UTC Quantum Neutralization:**
- Class Group VDF is vulnerable to Shor's algorithm
- Montana's UTC finality model makes quantum speedup irrelevant
- Quantum attacker computes VDF in 0.001 sec → waits 59.999 sec → 1 heartbeat
- Classical node computes VDF in 30 sec → waits 30 sec → 1 heartbeat
- UTC boundary is the rate limiter, VDF speed provides no advantage

```python
# Montana Class Group VDF parameters
VDF_TYPE = "class_group"                  # Wesolowski construction
VDF_BASE_ITERATIONS = 16777216            # 2²⁴ sequential squarings
VDF_DISCRIMINANT_BITS = 2048              # Security parameter for Δ
VDF_CHALLENGE_BITS = 128                  # Wesolowski challenge size

# Maps to L-1.1: Class Group VDF
# Security: Type B (mathematical reduction to class group order problem)
# Verification: O(log T) via Wesolowski proof
# Proof: ~256 bytes, no trusted setup
```

### Montana VRF → L-1.2

**Quantum Status:** ECVRF is BROKEN by Shor's algorithm (ATC L-1.2.3). Montana accepts this for block eligibility because:
1. Eligibility proofs have short-term validity (current epoch only)
2. SPHINCS+ signatures provide long-term security for transactions
3. Upgrade path documented in Montana spec §16.4

```python
# Montana uses ECVRF for block eligibility
# Quantum-vulnerable but acceptable for short-term proofs

# L-1.2 provides post-quantum alternatives:
# - Lattice-VRF (L-1.B): Post-quantum, Type B
# - Hash-VRF (L-1.C): Post-quantum, Type B+C

# Upgrade path: Replace ECVRF with Lattice-VRF for full PQ security
```

### Montana Ordering → L-1.5

```python
# Montana uses DAG-PHANTOM
# Maps to L-1.5.4: DAG with PHANTOM ordering

# Properties inherited:
# - Partial order → total order
# - Anticone-based tip selection
# - k-cluster resilience
```

---

## Layer 2: Consensus Protocols

Montana implements these L2 consensus patterns:

| L2 Concept | Montana Implementation | Section |
|------------|------------------------|---------|
| **L-2.1.3** Partial Sync | Network assumes GST eventually | §17 |
| **L-2.2.2** Byzantine | f < n/3 with score weighting | §8 |
| **L-2.5.2** DAG Model | PHANTOM ordering | §10 |
| **L-2.6.1** Quorum Finality | Score-weighted signers | §9 |
| **L-2.6.3** VDF Finality | Accumulated VDF depth | §6 |
| **L-2.7.2** VDF Time | Epoch progression via VDF | §5 |

### Montana Finality Model

```
Montana UTC Finality (Self-Sovereign):

1. Soft Finality (1 minute)
   └─ 1 UTC boundary passed
   └─ Maps to L-2.6.3: Time-based finality
   └─ Type: P (physical)

2. Medium Finality (2 minutes)
   └─ 2 UTC boundaries passed
   └─ Maps to L-2.6.3: Time-based finality
   └─ Type: P (physical)

3. Hard Finality (3 minutes)
   └─ 3 UTC boundaries passed
   └─ Maps to L-2.6.3: Time-based finality
   └─ Type: P (physical)

Attack cost: Requires advancing UTC. Time is physical.
Hardware advantage bounded by UTC — fast nodes wait for boundary.
Time tolerance: ±5 seconds (covers propagation, drift, jitter).
```

### Montana Consensus Properties

| Property | Montana Guarantee | L2 Mapping | Type |
|----------|-------------------|------------|------|
| Safety | No conflicting blocks in same DAG path | L-2.3.1 | A |
| Liveness | Eventually produce blocks (after GST) | L-2.3.2 | N |
| Finality | Accumulated VDF irreversible | L-2.3.5 | P |

---

## Composition Patterns

Montana uses these L-2.7 composition patterns:

| Pattern | Montana Usage |
|---------|---------------|
| **L-2.7.1** VRF Leader Election | ECVRF for block eligibility |
| **L-2.7.2** VDF Time Progression | Epoch advancement |
| **L-2.7.3** Commit-Reveal | (Not currently used) |
| **L-2.7.4** Timestamp Ordering | Heartbeat sequencing |
| **L-2.7.5** DAG + Consensus | DAG-PHANTOM + Accumulated VDF |

---

## Failure Mode Mapping

| Montana Failure | L2 Failure Mode | Recovery |
|-----------------|-----------------|----------|
| Network partition | L-2.8.1 Partition | Wait for GST |
| Byzantine nodes | L-2.8.2 Threshold | Bounded by f < n/3 |
| VDF speedup | L-2.8.4 VDF speedup | Physical bound (impossible) |

---

## Type Classification Summary

| Montana Component | Primary Type | Notes |
|-------------------|--------------|-------|
| VDF sequentiality | Type P + B | Physical + mathematical |
| VDF computation | Type P + B | Physical + mathematical |
| Accumulated finality | Type P | Physical (sequential time) |
| ECVRF eligibility | Type C | Pre-quantum empirical |
| SPHINCS+ signatures | Type C (L0) | 10+ years empirical |
| DAG ordering | Type C | PHANTOM empirical |
| Safety proofs | Type A | Mathematical |

---

## Self-Sovereign Properties

Montana v3.0 achieves self-sovereignty through:

| Property | Mechanism | Dependency |
|----------|-----------|------------|
| Temporal proof | VDF sequential computation | Physics (L-1) |
| Finality | Accumulated VDF depth | Physics (time is sequential) |
| Fork choice | Greater accumulated VDF | Physics (time cannot fork) |

**No external dependencies.** Montana's security derives entirely from physical constraints.

---

## Upgrade Path

Montana can upgrade components independently:

| Component | Current | Upgrade To | Trigger |
|-----------|---------|------------|---------|
| VRF | ECVRF | Lattice-VRF (L-1.B) | PQ requirement |
| VDF verification | Checkpoints | STARK proofs (L-1.D.3) | Efficiency need |
| Privacy | Ring-11 | Larger rings | Anonymity need |
| Hard Finality | 1000 checkpoints | Configurable | Security posture |

---

## Compliance Verification

To verify Montana compliance with ATC:

```
1. Physical constraints (L-1):
   ✓ VDF sequential computation
   ✓ VDF respects Landauer bound
   ✓ No FTL assumptions

2. Computational constraints (L0):
   ✓ SHA-3 for hashing
   ✓ SPHINCS+ for signatures
   ✓ ML-KEM for encryption
   ✓ Class Group VDF (Type B security)

3. Primitive security (L1):
   ✓ VDF sequentiality preserved (Class Group, Type B)
   ⚠ VRF uniqueness (ECVRF) — quantum-vulnerable, upgrade path defined
   ✓ Commitment binding (hash-based: PQ-safe; Pedersen: hiding only)

4. Consensus properties (L2):
   ✓ Safety: DAG partial order
   ✓ Liveness: After GST
   ✓ Finality: Accumulated VDF (self-sovereign)

→ Montana v3.6 COMPLIES with ATC v10
→ Montana v3.6 is a TIMECHAIN
→ Montana v3.6 is SELF-SOVEREIGN
→ Montana v3.6 uses UTC finality with ±5 second tolerance
→ Montana v3.6 platform-independent light clients
```

---

## References

- Montana Technical Specification v3.6
- ATC Layer -1 v2.1
- ATC Layer 0 v1.0
- ATC Layer 1 v1.1
- ATC Layer 2 v1.0

---

*This mapping enables verification that Montana correctly inherits ATC layer guarantees and does not assume stronger properties than lower layers provide.*

*Montana v3.6: Timechain — self-sovereign UTC finality through physics.*
