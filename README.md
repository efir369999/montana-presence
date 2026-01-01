# Layer -1: Physical Constraints

**The boundary conditions imposed by physical law on any information-processing system.**

---

## Overview

Layer -1 enumerates the physical constraints that bound all possible protocols.

This layer contains:
- **No protocol logic**
- **No cryptographic assumptions**
- **No design decisions**

It represents the epistemological foundation upon which any secure system must be built.

---

## Foundational Axiom

**Any adversary operates within known physics.**

This is the minimal assumption required for "security" to be meaningful. An adversary unconstrained by physics could violate mathematical axioms themselves.

---

## Physical Constraints

| ID | Constraint | Precision | Status |
|----|------------|-----------|--------|
| L-1.1 | Thermodynamic Arrow | — | 150+ years, no macroscopic violation |
| L-1.2 | Atomic Time Reproducibility | 10⁻¹⁸ | NIST, PTB, NPL, SYRTE confirmed |
| L-1.3 | Landauer Limit | kT ln(2) | Experimentally approached |
| L-1.4 | Speed of Light | 10⁻¹⁷ | GPS continuous verification |
| L-1.5 | Terrestrial Time Uniformity | 10⁻¹¹ | GPS since 1978 |
| L-1.6 | Bekenstein Bound | — | Indirect (black hole thermodynamics) |
| L-1.7 | Thermal Noise Floor | kT/Hz | Confirmed since 1928 |
| L-1.8 | Quantum Decoherence | — | Many scales confirmed |

---

## Adversary Model

The adversary has **arbitrarily large but finite** physical resources.

The adversary **CANNOT**:

| Action | Violates |
|--------|----------|
| Reverse macroscopic entropy | L-1.1 |
| Fake atomic clock readings | L-1.2 |
| Compute without energy dissipation | L-1.3 |
| Signal faster than light | L-1.4 |
| Create time rate differential > 10⁻¹¹ on Earth | L-1.5 |
| Store infinite information | L-1.6 |
| Measure with infinite precision | L-1.7 |
| Maintain macroscopic superposition | L-1.8 |

---

## Epistemological Status

We do not claim metaphysical certainty.

We claim **maximal empirical confidence**: these constraints have been tested more rigorously than any cryptographic assumption, across scales from 10⁻¹⁸ m to 10²⁶ m.

Violation at protocol-relevant scales would require revision of physics with no observed failure at any tested scale.

---

## Repository Structure

```
ATC v8/                      Current focus: Layer -1
├── layer_minus_1.md             Physical constraints specification

CLAUDE.md                    AI architect role (Layer -1 focused)

ATC v7/                      Archive: Protocol implementation
PoT v1-6/                    Archive: Legacy versions
Montana/                     Token specification
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Layer -1 Specification](ATC%20v8/layer_minus_1.md) | Full physical constraints document |
| [CLAUDE.md](CLAUDE.md) | AI architect role definition |

---

## Explicit Exclusions

Layer -1 excludes by design:

- Computational hardness assumptions (P ≠ NP, factoring)
- Specific cryptographic primitives
- Network topology and latency distributions
- Security definitions
- Quantum computing capabilities

These belong to higher layers (0, 1, 2, ...) which may be developed in the future.

---

## References

Key sources (full list in `layer_minus_1.md`):

- Einstein (1905, 1915) — Special/General Relativity
- Landauer (1961) — Irreversibility and Heat Generation
- Bekenstein (1981) — Entropy-to-Energy Bound
- Bérut et al. (2012) — Landauer limit verification
- Bothwell et al. (2022) — mm-scale gravitational redshift
- BIPM SI Brochure, 9th edition (2019)

---

## License

MIT License

---

## Closing Principle

> *Layer -1 represents the boundary conditions imposed by physical law on any information-processing system.*
> *Protocols may assume weaker physics (additional constraints);*
> *they cannot assume stronger physics (fewer constraints)*
> *without leaving the domain of known science.*

---

*Dedicated to the memory of*

**Hal Finney** (1956-2014)

*First recipient of a Bitcoin transaction. Creator of RPOW.*

*"Running bitcoin" — January 11, 2009*
