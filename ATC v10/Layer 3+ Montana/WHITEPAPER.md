# Ɉ Montana

**Version:** 3.1
**Date:** January 2026
**Ticker:** $MONT

---

> *"Time is the only resource distributed equally to all humans."*

---

## Abstract

**Ɉ Montana** is a mechanism for asymptotic trust in the value of time.

**Ɉ** is a **Temporal Time Unit** (TTU) — a unit that asymptotically approaches the definition:

```
lim(evidence → ∞) 1 Ɉ → 1 second
∀t: 1 Ɉ(t) ≈ 1 second
```

Montana builds trust in time value through the **Asymptotic Trust Consensus** (ATC) architecture — physical constraints, computational hardness, protocol primitives, and consensus mechanisms.

**Montana v3.0** is fully self-sovereign: no external blockchain dependencies. Finality derives entirely from physics — accumulated VDF computation that cannot be accelerated beyond physical limits.

The more evidence accumulates, the closer Ɉ approaches its definition. We never claim to arrive; we asymptotically approach.

---

## 1. Temporal Time Unit

### 1.1 Definition

```
Ɉ (Montana) — Temporal Time Unit

1 Ɉ     = 1 second
60 Ɉ    = 1 minute
3600 Ɉ  = 1 hour
86400 Ɉ = 1 day

Total Supply: 1,260,000,000 Ɉ = 21 million minutes
```

### 1.2 Why Time?

Time is unique among all quantities:

| Property | Time | Other Resources |
|----------|------|-----------------|
| **Distribution** | Equal (24h/day for everyone) | Unequal |
| **Creation** | Impossible | Possible |
| **Destruction** | Impossible | Possible |
| **Accumulation** | Limited by lifespan | Unlimited |
| **Measurement** | 10⁻¹⁹ precision (atomic) | Varies |
| **Universality** | Absolute | Relative |

**Time cannot be counterfeited.** Every second is physically verified by thermodynamics (irreversibility) and atomic physics (clock precision).

### 1.3 Purpose

Montana answers one question:

> **"Can we verify that one second has passed?"**

Yes — through:
1. **Atomic clocks** (34 sources, 8 regions)
2. **VDF computation** (sequential, non-parallelizable)
3. **Accumulated finality** (physics-based irreversibility)

---

## 2. Physical Foundation

### 2.1 Time Is Physical

The Temporal Time Unit rests on physics — constraints tested for 150+ years.

| Constraint | Implication | Precision |
|------------|-------------|-----------|
| **Thermodynamic Arrow** | Time flows one direction | 10⁻³¹⁵ reversal probability |
| **Atomic Universality** | All clocks of same isotope tick identically | 5.5×10⁻¹⁹ |
| **Speed of Light** | Maximum information transfer | 10⁻¹⁷ isotropy |
| **Landauer Limit** | Computation requires energy | Verified |

These are not assumptions. These are **the most precisely tested facts in science**.

### 2.2 Physical Guarantees

An adversary operating within known physics **cannot**:
- Reverse time (thermodynamics)
- Create time (conservation)
- Signal faster than light (relativity)
- Compute without energy (Landauer)
- **Accelerate VDF beyond sequential limit** (parallelization impossible)

The TTU's integrity degrades only if physics requires revision at protocol-relevant scales.

### 2.3 Self-Sovereign Finality

Montana achieves finality through **accumulated VDF** — sequential computation that proves elapsed time.

| Property | Guarantee |
|----------|-----------|
| Security basis | Physical (time is sequential) |
| Attack cost | Rewriting N seconds requires N seconds |
| Dependencies | None (physics only) |
| Trust model | Physics |

**To rewrite N seconds of Montana history requires N seconds of real time.**

This is a **physical law**.

---

## 3. Verification

Montana verifies each Temporal Time Unit through three layers:

### 3.1 Atomic Time Consensus

```
34 NTP servers across 8 geographic regions
├─ Europe: 8 sources (PTB, NPL, SYRTE, METAS, INRIM, VSL, ROA, GUM)
├─ Asia: 7 sources (NICT, NIM, KRISS, NPLI, VNIIFTRI, TL, INPL)
├─ North America: 4 sources (NIST, USNO, NRC, CENAM)
├─ South America: 3 sources (INMETRO, INTI, INN)
├─ Africa: 3 sources (NMISA, NIS, KEBS)
├─ Oceania: 3 sources (NMI, MSL, NMC)
├─ Antarctica: 3 sources (McMurdo, Amundsen-Scott, Concordia)
└─ Arctic: 3 sources (Ny-Ålesund, Thule, Alert)

Consensus: >50% (18+) must agree within 1 second
Geographic: Minimum 5 regions required
```

**Why this works:** Atomic clocks of the same isotope exhibit identical transition frequencies — this is quantum mechanics, not convention.

### 3.2 VDF Temporal Proof

```
VDF(input, T) = SHAKE256^T(input)

T = 2²⁴ iterations (~2.5 seconds)
```

**Verifiable Delay Function** proves elapsed time through sequential computation:
- Cannot be parallelized
- Cannot be accelerated beyond physics
- Verified quickly (STARK proofs)

### 3.3 Accumulated Finality

```
Accumulated VDF depth:
├─ Soft: 1 VDF checkpoint (~2.5 seconds)
├─ Medium: 100 VDF checkpoints (~4 minutes)
└─ Hard: 1000 VDF checkpoints (~40 minutes)
```

**Provides immutable temporal ordering through physics, not external trust.**

To rewrite history at depth D requires D × VDF_time of sequential computation. No parallelization possible.

---

## 4. Finality

```
┌─────────────────────────────────────────────────────────────────┐
│  HARD FINALITY (40+ minutes)                                    │
│  Accumulated VDF: 1000+ sequential checkpoints                  │
│  Attack cost: 40+ minutes of real time (physical impossibility) │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  MEDIUM FINALITY (minutes)                                      │
│  DAG consensus converges + 100 VDF checkpoints                  │
│  Probabilistic certainty                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  SOFT FINALITY (seconds)                                        │
│  VDF checkpoint                                                 │
│  Physical guarantee: time is irreversible                       │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 Finality Properties

| Property | Accumulated VDF |
|----------|-----------------|
| Security | Physical (sequential computation) |
| Attack cost | Time itself (irreducible) |
| Dependencies | None |
| Latency | Configurable (seconds to hours) |

---

## 5. Supply

### 5.1 Total

```
1,260,000,000 Ɉ = 21,000,000 minutes = 350,000 hours
```

A finite, human-comprehensible quantity of time.

### 5.2 Distribution

| Era | Per Block | Cumulative |
|-----|-----------|------------|
| 1 | 3,000 Ɉ (50 min) | 50% |
| 2 | 1,500 Ɉ (25 min) | 75% |
| 3 | 750 Ɉ (12.5 min) | 87.5% |
| ... | ... | ... |
| 33 | 1 Ɉ (1 sec) | 100% |

### 5.3 Zero Pre-allocation

```
PRE_ALLOCATION = 0
FOUNDER_UNITS = 0
RESERVED_UNITS = 0
```

All TTUs distributed through participation. No one starts with an advantage.

---

## 6. Participation

### 6.1 Node Types (2 only)

| Node Type | Storage | Tier |
|-----------|---------|------|
| **Full Node** | Full blockchain history (downloads all) | Tier 1 |
| **Light Node** | From connection moment only (mandatory) | Tier 2 |

### 6.2 Participation Tiers (3 only)

| Tier | Participants | Node Type | Lottery Weight |
|------|--------------|-----------|----------------|
| **1** | Full Node operators | Full Node | **70%** |
| **2** | Light Node operators OR TG Bot/Channel owners | Light Node | **20%** |
| **3** | TG Community participants | — | **10%** |

**Summary:**
- Tier 1 (Full Node): **70%**
- Tier 2 (Light Node): **20%**
- Tier 3 (TG Users): **10%**

### 6.3 Heartbeat

A **heartbeat** proves temporal presence:

```
Full Heartbeat (Tier 1):       Light Heartbeat (Tier 2/3):
├─ Atomic time proof (34 NTP)  ├─ Timestamp (verified)
├─ VDF proof                   ├─ Source (LIGHT_NODE/TG_BOT/TG_USER)
├─ Finality reference          ├─ Community ID
└─ SPHINCS+ signature          └─ SPHINCS+ signature
```

### 6.4 Score

```
Score = √(heartbeats)
```

Square root provides diminishing returns and Sybil resistance.

---

## 7. Technical

### 7.1 Post-Quantum Cryptography

| Function | Primitive | Standard |
|----------|-----------|----------|
| Signatures | SPHINCS+-SHAKE-128f | NIST FIPS 205 |
| Key Exchange | ML-KEM-768 | NIST FIPS 203 |
| Hashing | SHA3-256, SHAKE256 | NIST FIPS 202 |

### 7.2 DAG Structure

```
    ┌─[B1]─┐
    │      │
[G]─┼─[B2]─┼─[B4]─...
    │      │
    └─[B3]─┘
```

No wasted work. All valid blocks included.

### 7.3 Privacy (Optional)

| Tier | Visibility |
|------|------------|
| T0 | Transparent |
| T1 | Hidden recipient |
| T2 | Hidden amount |
| T3 | Full privacy |

---

## 8. Epistemology

### 8.1 Asymptotic Trust

```
lim(evidence → ∞) Trust = 1
∀t: Trust(t) < 1

"We approach certainty; we never claim to reach it."
```

### 8.2 Classification

| Type | Meaning |
|------|---------|
| A | Proven theorem |
| B | Conditional proof |
| C | Empirical (10+ years) |
| P | Physical bound |
| N | Network-dependent |

Every claim is typed. This is epistemic honesty.

---

## 9. ATC Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3+: Montana — Temporal Time Unit                         │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Consensus (Safety, Liveness, Finality)                │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Primitives (VDF, VRF, Commitment)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: Computation (SHA-3, ML-KEM, SPHINCS+)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer -1: Physics (Thermodynamics, Atomic Time, Light Speed)   │
└─────────────────────────────────────────────────────────────────┘
```

**Montana v3.0:** Fully self-sovereign. No external dependencies.

---

## 10. Principle

**Ɉ Montana** is a mechanism for asymptotic trust in the value of time.

**Ɉ** is a Temporal Time Unit (TTU) that approaches — but never claims to reach — its definition:

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

Like SI units define physical quantities through fundamental constants:
- **Second** → Cesium-133 hyperfine transition
- **Meter** → Speed of light
- **Kilogram** → Planck constant
- **Ɉ** → Asymptotically verified temporal passage

**Time is the universal constant. Ɉ Montana builds trust in its value.**

**Self-sovereign. Physics-based. No external dependencies.**

---

## References

- Einstein (1905, 1915) — Relativity
- Landauer (1961) — Computation thermodynamics
- Marshall et al. (2025) — Atomic clocks 5.5×10⁻¹⁹
- NIST FIPS 203/204/205 (2024) — Post-quantum cryptography
- Sompolinsky, Zohar (2018) — PHANTOM
- Boneh et al. (2018) — VDF
- ATC v10 — Layers -1, 0, 1, 2

---

## Parameters

```python
# Ɉ Montana
PROJECT = "Ɉ Montana"
SYMBOL = "Ɉ"
TICKER = "$MONT"
DEFINITION = "lim(evidence → ∞) 1 Ɉ → 1 second"
TOTAL_SUPPLY = 1_260_000_000

# Node Types (2 only)
NODE_TYPES = 2               # Full Node, Light Node

# Participation Tiers (3 only, numbered 1-2-3)
TIERS = 3                    # Tier 1, 2, 3
TIER_1_WEIGHT = 0.70         # Full Node → 70%
TIER_2_WEIGHT = 0.20         # Light Node / TG Bot owners → 20%
TIER_3_WEIGHT = 0.10         # TG Community users → 10%

# Verification
NTP_SOURCES = 34
NTP_REGIONS = 8
VDF_ITERATIONS = 16_777_216

# Finality (VDF checkpoints)
FINALITY_SOFT = 1           # ~2.5 seconds
FINALITY_MEDIUM = 100       # ~4 minutes
FINALITY_HARD = 1000        # ~40 minutes

# Distribution
PRE_ALLOCATION = 0
INITIAL_DISTRIBUTION = 3000  # Ɉ per block
HALVING_INTERVAL = 210_000
```

---

<div align="center">

**Ɉ Montana**

Mechanism for asymptotic trust in the value of time

*lim(evidence → ∞) 1 Ɉ → 1 second*

**Self-sovereign. Physics-based.**

**$MONT**

</div>
