# ATC: Asymptotic Trust Consensus

### Physics-First Protocol Architecture

> **Trust that approaches certainty — grounded in physical law, not faith in algorithms.**

```
                                    ╭─────────────────────────── 1.0 (certainty)
         Trust                     ╱
           ↑                    ╱
       1.0 ┤              ══════
           │          ════╯
           │       ═══╯        ← You are here: 10⁻¹⁷ — 10⁻¹⁹ precision
           │    ═══╯
           │  ══╯
           │══╯
       0.0 ┼────────────────────────────────────────→ Evidence

           lim(evidence → ∞) Trust = 1
           ∀t: Trust(t) < 1

           "We approach, we never claim to arrive."
```

[![Layer -1](https://img.shields.io/badge/Layer%20--1-v2.1-blue)](ATC%20v9/Layer%20-1/layer_minus_1.md)
[![Layer 0](https://img.shields.io/badge/Layer%200-v1.0-blue)](ATC%20v9/Layer%200/layer_0.md)
[![Layer 1](https://img.shields.io/badge/Layer%201-v1.1-blue)](ATC%20v9/Layer%201/layer_1.md)
[![Layer 2](https://img.shields.io/badge/Layer%202-v1.0-blue)](ATC%20v9/Layer%202/layer_2.md)
[![Layer 3+](https://img.shields.io/badge/Layer%203%2B-Montana%20v1.0-purple)](Montana/MONTANA_TECHNICAL_SPECIFICATION.md)
[![Rating](https://img.shields.io/badge/rating-10%2F10-brightgreen)](ATC%20v9/Layer%20-1/HYPERCRITICISM_PROOF.md)
[![Physics](https://img.shields.io/badge/foundation-physics-orange)](ATC%20v9/Layer%20-1/layer_minus_1.md)

---

## The One-Liner

**ATC is a protocol architecture where security proofs begin with physics, not assumptions.**

---

## Why Physics First?

```
Traditional Cryptography:          ATC Architecture:

"Secure if P ≠ NP"                 Layer -1: Physics      ← IMPOSSIBLE
       ↓                                  ↓
  (unproven)                       Layer 0:  Computation  ← HARD
       ↓                                  ↓
"Trust us"                         Layer 1:  Primitives   ← BUILDABLE
                                          ↓
                                   Layer 2:  Consensus    ← AGREEABLE
```

**The difference:**
- Traditional: Security hangs on unproven mathematical conjectures
- ATC: Security is rooted in experimentally verified physical law

**If P = NP tomorrow:**
- Traditional crypto: Everything breaks
- ATC: Physical bounds still hold — Landauer, Bekenstein, light speed

---

## The Layer Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3+: Implementations (Montana v1.0)                      │
│  ─────────────────────────────────────────────────────────────  │
│  Specific protocols, networks, cryptocurrencies                │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Consensus Protocols                        v1.0      │
│  ─────────────────────────────────────────────────────────────  │
│  What is AGREEABLE: Safety, Liveness, Finality, BFT           │
│  Types: A/B/C/P/S/I (inherited) + N (network-dependent)        │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Protocol Primitives                        v1.1      │
│  ─────────────────────────────────────────────────────────────  │
│  What is BUILDABLE: VDF, VRF, Commitment, Timestamp, Ordering  │
│  Types: A/B/C/P (inherited) + S (composition) + I (impl)       │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: Computational Constraints                   v1.0     │
│  ─────────────────────────────────────────────────────────────  │
│  What is HARD: OWF, Lattice, CRHF, VDF, NIST PQC              │
│  Types: A (proven) → B (reduction) → C (empirical) → D (conjecture)
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer -1: Physical Constraints                       v2.1     │
│  ─────────────────────────────────────────────────────────────  │
│  What is IMPOSSIBLE: Thermodynamics, Light speed, Landauer    │
│  Precision: 10⁻¹⁷ — 10⁻¹⁹ | Tested: 150+ years               │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  ██████████████████  PHYSICAL REALITY  ██████████████████████  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Insight

> **Any adversary operates within known physics.**

This is the minimal assumption required for "security" to be meaningful.

An adversary unconstrained by physics could:
- Reverse entropy (undo any computation)
- Signal faster than light (violate causality)
- Store infinite information (break all bounds)
- Violate mathematical axioms themselves

**We don't assume P ≠ NP. We assume physics.**

---

## Layer -1: Physical Constraints

*What is IMPOSSIBLE — tested to 10⁻¹⁷ precision*

| ID | Constraint | Evidence |
|----|------------|----------|
| L-1.1 | Thermodynamic Arrow | 150+ years, no macroscopic violation |
| L-1.2 | Atomic Time | 5.5×10⁻¹⁹ (Marshall et al. 2025) |
| L-1.3 | Landauer Limit | Experimentally approached |
| L-1.4 | Speed of Light | 10⁻¹⁷ isotropy (GPS continuous) |
| L-1.5 | Time Uniformity | mm-scale optical clocks |
| L-1.6 | Bekenstein Bound | Indirect (GR + QM) |
| L-1.7 | Thermal Noise | Confirmed since 1928 |
| L-1.8 | Decoherence | Many scales confirmed |

**→ [Full specification](ATC%20v9/Layer%20-1/layer_minus_1.md)**

---

## Layer 0: Computational Constraints

*What is HARD — given that physics holds*

| Tier | Content | Stability |
|------|---------|-----------|
| 1 | Information-theoretic (Shannon, Birthday) | Eternal |
| 2 | Physical bounds (Landauer → computation) | 100+ years |
| 3 | Hardness classes (OWF, Lattice, CRHF) | 50+ years |
| 4 | Primitives (SHA-3, ML-KEM, ML-DSA) | 10-30 years |

**Post-Quantum Ready:** NIST FIPS 203/204/205 from day one.

**→ [Full specification](ATC%20v9/Layer%200/layer_0.md)**

---

## Layer 1: Protocol Primitives

*What is BUILDABLE — cryptographic building blocks*

| Primitive | Description | PQ Status |
|-----------|-------------|-----------|
| VDF | Verifiable Delay Functions | Hash-based: Secure |
| VRF | Verifiable Random Functions | Lattice: Secure |
| Commitment | Hide-then-reveal schemes | Hash-based: Secure |
| Timestamp | Temporal existence proofs | Hash-based: Secure |
| Ordering | Event sequencing (Lamport, DAG) | Math only (no crypto) |

**Types:** A/B/C/P (inherited) + S (composition) + I (implementation)

**→ [Full specification](ATC%20v9/Layer%201/layer_1.md)**

---

## Layer 2: Consensus Protocols

*What is AGREEABLE — given physics, computation, and primitives*

| Concept | Description | Type |
|---------|-------------|------|
| Safety | No conflicting decisions | A (proven) |
| Liveness | Eventually decide | N (network-dependent) |
| Finality | Irreversible decision | A/P/C |
| BFT | f < n/3 Byzantine tolerance | A (proven) |
| FLP | No async consensus with 1 fault | A (proven) |

**Network Models:** Synchronous, Asynchronous, Partial Synchrony

**Types:** A/B/C/P/S/I (inherited) + N (network-dependent)

**→ [Full specification](ATC%20v9/Layer%202/layer_2.md)**

---

## Layer 3+: Protocol Implementations

*What is DEPLOYABLE — concrete protocols built on ATC*

| Implementation | Description | Status |
|----------------|-------------|--------|
| Montana | Time-based consensus with Bitcoin anchoring | v1.0 |

**Reference Implementation:** Montana v1.0

| Feature | Montana Choice |
|---------|----------------|
| Consensus | DAG-PHANTOM + VDF + Bitcoin anchor |
| Cryptography | SPHINCS+ (signatures), ML-KEM (encryption) |
| Time Source | 34 NTP servers, 8 geographic regions |
| Token | Ɉ (seconds), 1.26B supply, fair launch |

**→ [Layer 3+ Overview](ATC%20v9/Layer%203%2B/README.md)**
**→ [Montana Specification](Montana/MONTANA_TECHNICAL_SPECIFICATION.md)**
**→ [ATC Mapping](ATC%20v9/Layer%203%2B/MONTANA_ATC_MAPPING.md)**

---

## Asymptotic — Not Absolute

| What we claim | What we don't claim |
|---------------|---------------------|
| Maximal empirical confidence | Metaphysical certainty |
| 150+ years of verification | Eternal truth |
| 10⁻¹⁷ precision | Infinite precision |
| Best current physics | Final physics |

**This is the asymptote:**
- We approach certainty
- We never claim to reach it
- Each year of non-violation brings us closer
- We remain epistemically honest

---

## Repository Structure

```
ATC v9/
├── Layer -1/                      Physical Constraints (v2.1)
│   ├── layer_minus_1.md               Specification
│   ├── HYPERCRITICISM_PROOF.md        Certification
│   ├── EVALUATION_QUICK_REFERENCE.md  Assessment card
│   └── RELEASE_v2.1.md                Release notes
│
├── Layer 0/                       Computational Constraints (v1.0)
│   ├── layer_0.md                     Specification
│   ├── HYPERCRITICISM_PROOF.md        Certification
│   ├── EVALUATION_QUICK_REFERENCE.md  Assessment card
│   └── RELEASE_v1.0.md                Release notes
│
├── Layer 1/                       Protocol Primitives (v1.1)
│   ├── layer_1.md                     Specification + Implementation Appendix
│   ├── HYPERCRITICISM_PROOF.md        Certification
│   ├── EVALUATION_QUICK_REFERENCE.md  Assessment card
│   └── RELEASE_v1.1.md                Release notes
│
├── Layer 2/                       Consensus Protocols (v1.0)
│   ├── layer_2.md                     Specification
│   ├── HYPERCRITICISM_PROOF.md        Certification
│   ├── EVALUATION_QUICK_REFERENCE.md  Assessment card
│   └── RELEASE_v1.0.md                Release notes
│
└── Layer 3+/                      Protocol Implementations
    ├── README.md                      Overview
    └── MONTANA_ATC_MAPPING.md         Montana ↔ ATC mapping

Montana/                           Reference Implementation
└── MONTANA_TECHNICAL_SPECIFICATION.md  v1.0 Specification

CLAUDE.md                          AI Architect role definition
```

---

## Quick Links

| Document | Layer | Description |
|----------|-------|-------------|
| [Layer -1 Spec](ATC%20v9/Layer%20-1/layer_minus_1.md) | -1 | Physical constraints |
| [Layer 0 Spec](ATC%20v9/Layer%200/layer_0.md) | 0 | Computational constraints |
| [Layer 1 Spec](ATC%20v9/Layer%201/layer_1.md) | 1 | Protocol primitives |
| [Layer 2 Spec](ATC%20v9/Layer%202/layer_2.md) | 2 | Consensus protocols |
| [Layer 3+ Overview](ATC%20v9/Layer%203%2B/README.md) | 3+ | Implementations |
| [Montana Spec](Montana/MONTANA_TECHNICAL_SPECIFICATION.md) | 3+ | Reference implementation |
| [Montana Mapping](ATC%20v9/Layer%203%2B/MONTANA_ATC_MAPPING.md) | 3+ | ATC layer mapping |

---

## The Name Explained

```
A S Y M P T O T I C
        ↓
    Approaching but never reaching
    Honest about limits
    Scientific humility

T R U S T
    ↓
    Not blind faith
    Earned through evidence
    Grounded in physics

C O N S E N S U S
        ↓
    Scientific community (NIST, BIPM, PTB)
    Cryptographic community (IACR, NIST PQC)
    Network participants
```

**ATC = The protocol that earns trust asymptotically, through physics.**

---

## Releases

| Release | Version | Tag | Status |
|---------|---------|-----|--------|
| **ATC** | **v9.0.0** | [atc-v9.0.0](https://github.com/afgrouptime/atc/releases/tag/atc-v9.0.0) | **Complete Stack** |
| Layer -1 | v2.1.0 | [layer-1-v2.1.0](https://github.com/afgrouptime/atc/releases/tag/layer-1-v2.1.0) | 10/10 |
| Layer 0 | v1.0.0 | [layer-0-v1.0.0](https://github.com/afgrouptime/atc/releases/tag/layer-0-v1.0.0) | 10/10 |
| Layer 1 | v1.1.0 | [layer-1-v1.1.0](https://github.com/afgrouptime/atc/releases/tag/layer-1-v1.1.0) | 10/10 + 100% impl |
| Layer 2 | v1.0.0 | [layer-2-v1.0.0](https://github.com/afgrouptime/atc/releases/tag/layer-2-v1.0.0) | 10/10 |
| Layer 3+ | Montana v1.0 | [layer-3-montana-v1.0.0](https://github.com/afgrouptime/atc/releases/tag/layer-3-montana-v1.0.0) | Reference impl |

---

## Foundational References

**Physics (Layer -1):**
- Einstein (1905, 1915) — Relativity
- Landauer (1961) — Computation thermodynamics
- Bekenstein (1981) — Information bounds
- Marshall et al. (2025) — Atomic clocks at 10⁻¹⁹

**Computation (Layer 0):**
- Shannon (1948) — Information theory
- NIST FIPS 203/204/205 (2024) — Post-quantum standards
- Regev (2005) — Lattice cryptography

**Protocol Primitives (Layer 1):**
- Boneh et al. (2018) — Verifiable Delay Functions
- Micali et al. (1999) — Verifiable Random Functions
- Lamport (1978) — Time, Clocks, and Ordering

**Consensus Protocols (Layer 2):**
- Lamport, Shostak, Pease (1982) — Byzantine Generals
- Fischer, Lynch, Paterson (1985) — FLP Impossibility
- Castro, Liskov (1999) — PBFT
- Yin et al. (2019) — HotStuff

---

## License

MIT License

---

## Closing Principle

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   "Implementations may assume weaker guarantees at each layer; │
│    they cannot assume stronger guarantees                      │
│    without leaving the domain of known science."               │
│                                                                │
│    Layer -1: Physics      → Cannot exceed physical bounds      │
│    Layer 0:  Computation  → Cannot break hardness assumptions  │
│    Layer 1:  Primitives   → Cannot exceed primitive security   │
│    Layer 2:  Consensus    → Cannot exceed consensus guarantees │
│                                                                │
│                              — ATC Closing Principle           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

<div align="center">

*Dedicated to the memory of*

**Hal Finney** (1956–2014)

*First recipient of a Bitcoin transaction. Creator of RPOW.*

*"Running bitcoin" — January 11, 2009*

---

**ATC: Where security begins with physics.**

</div>
