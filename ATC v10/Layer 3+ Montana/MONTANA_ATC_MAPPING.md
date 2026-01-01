# Ɉ Montana ↔ ATC Layer Mapping

**Ɉ Montana Version:** 3.1
**Ticker:** $MONT
**ATC Version:** 10.0 (L-1 v2.1, L0 v1.0, L1 v1.1, L2 v1.0)

---

## Overview

**Ɉ Montana** is a mechanism for asymptotic trust in the value of time.

**Ɉ** is a Temporal Time Unit (TTU): lim(evidence → ∞) 1 Ɉ → 1 second

**v3.0:** Self-sovereign finality through accumulated VDF. No external dependencies.

This document maps Ɉ Montana components to their foundational ATC layers, showing exactly which constraints and primitives the mechanism relies upon.

---

## Layer -1: Physical Constraints

Montana relies on these L-1 physical constraints:

| L-1 Constraint | Montana Usage | Montana Component |
|----------------|---------------|-------------------|
| **L-1.1** Thermodynamic Arrow | Irreversibility of VDF computation | VDF, Block finality |
| **L-1.2** Atomic Time | 34 NTP sources from atomic standards | Layer 0: Atomic Time |
| **L-1.3** Landauer Limit | Bounds adversary computation | Anti-spam PoW |
| **L-1.4** Speed of Light | Minimum network propagation delay | Block timing (600s) |
| **L-1.5** Time Uniformity | All nodes measure time consistently | Heartbeat validation |
| **L-1.7** Thermal Noise | NTP_MAX_DRIFT_MS = 1000ms tolerance | Atomic time consensus |

### Montana Atomic Time → L-1.2

```python
# Montana requirement
NTP_MIN_SOURCES_CONSENSUS = 18      # >50% of 34 sources
NTP_MIN_REGIONS_TOTAL = 5           # Geographic diversity

# Maps to L-1.2: Atomic Time Reproducibility
# "Isolated atoms of a given isotope exhibit identical transition frequencies"
# Precision: Δf/f < 9.4 × 10⁻¹⁹ (²⁷Al⁺)
```

**Type:** Physical (Type 1 in L-1 classification)

---

## Layer 0: Computational Constraints

Montana relies on these L0 computational primitives:

| L0 Primitive | Montana Usage | Type |
|--------------|---------------|------|
| **L-0.3.3** SHA-3 | sha3_256 for hashing, SHAKE256 for VDF | Type C |
| **L-0.4.2** ML-KEM-768 | Key encapsulation | Type B |
| **L-0.4.4** SPHINCS+-SHAKE-128f | Transaction/heartbeat signatures | Type C |
| **L-0.3.2** HMAC (PRF) | Key derivation | Type B |
| **L-0.2.1** Birthday Bound | Ring signature security | Type A |

### Montana Cryptography → L0

```python
# Montana choices
SIGNATURE_SCHEME = "SPHINCS+-SHAKE-128f"  # L-0.4.4
KEY_ENCAPSULATION = "ML-KEM-768"          # L-0.4.2
HASH_FUNCTION = "SHA3-256"                # L-0.3.3
VDF_HASH = "SHAKE256"                     # L-0.3.3
```

**Post-Quantum Status:** Montana is post-quantum secure from day one, using NIST FIPS 203/204/205 standards.

---

## Layer 1: Protocol Primitives

Montana uses these L1 primitives:

| L1 Primitive | Montana Implementation | Section |
|--------------|------------------------|---------|
| **L-1.1** VDF | SHAKE256 hash chain, T = 2²⁴ base | §5 |
| **L-1.2** VRF | ECVRF for eligibility | §10 |
| **L-1.3** Commitment | Pedersen (privacy), Hash (general) | §14 |
| **L-1.4** Timestamp | Linked timestamps with atomic time | §7 |
| **L-1.5** Ordering | DAG-PHANTOM | §10 |

### Montana VDF → L-1.1

```python
# Montana VDF parameters
VDF_HASH_FUNCTION = "SHAKE256"
VDF_BASE_ITERATIONS = 16777216  # 2²⁴ (~2.5 seconds)
VDF_STARK_CHECKPOINT_INTERVAL = 1000

# Maps to L-1.1.4: SHAKE256 Hash Chain VDF
# Security: Type P (physical) + Type C (empirical)
# Property: Sequential computation, no parallelization
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
Montana Three-Layer Finality (Self-Sovereign):

1. Soft Finality (seconds)
   └─ VDF checkpoint every 2.5 seconds
   └─ Maps to L-2.6.3: VDF-based finality
   └─ Type: P (physical)

2. Medium Finality (minutes)
   └─ DAG-PHANTOM ordering + 100 VDF checkpoints
   └─ Maps to L-2.5.2: DAG model + L-2.6.3
   └─ Type: P + C (physical + empirical)

3. Hard Finality (40+ minutes)
   └─ 1000+ accumulated VDF checkpoints
   └─ Maps to L-2.6.3: VDF-based finality
   └─ Type: P (physical)

Attack cost: Rewriting N checkpoints requires N × 2.5 seconds
This is a PHYSICAL BOUND — cannot be reduced by more hardware or money.
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
| NTP disagreement | L-2.8.3 Time source | Require supermajority |
| Network partition | L-2.8.1 Partition | Wait for GST |
| Byzantine nodes | L-2.8.2 Threshold | Bounded by f < n/3 |
| VDF speedup | L-2.8.4 VDF speedup | Physical bound (impossible) |

---

## Type Classification Summary

| Montana Component | Primary Type | Notes |
|-------------------|--------------|-------|
| Atomic time consensus | Type 1 (L-1) | Physical measurement |
| VDF computation | Type P + C | Physical + empirical |
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
| Time measurement | Atomic clock consensus | Physics (L-1.2) |
| Temporal proof | VDF sequential computation | Physics (L-1.1) |
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
   ✓ Uses atomic time sources
   ✓ VDF respects Landauer bound
   ✓ No FTL assumptions

2. Computational constraints (L0):
   ✓ SHA-3/SHAKE256 for hashing
   ✓ SPHINCS+ for signatures
   ✓ ML-KEM for encryption

3. Primitive security (L1):
   ✓ VDF sequentiality preserved
   ⚠ VRF uniqueness (ECVRF) — quantum-vulnerable, upgrade path defined
   ✓ Commitment binding (hash-based: PQ-safe; Pedersen: hiding only)

4. Consensus properties (L2):
   ✓ Safety: DAG partial order
   ✓ Liveness: After GST
   ✓ Finality: Accumulated VDF (self-sovereign)

→ Montana v3.0 COMPLIES with ATC v10
→ Montana v3.0 is SELF-SOVEREIGN (no external dependencies)
```

---

## References

- Montana Technical Specification v3.0
- ATC Layer -1 v2.1
- ATC Layer 0 v1.0
- ATC Layer 1 v1.1
- ATC Layer 2 v1.0

---

*This mapping enables verification that Montana correctly inherits ATC layer guarantees and does not assume stronger properties than lower layers provide.*

*Montana v3.0: Self-sovereign finality through physics.*
