# Layer 3+: Protocol Implementations

**Status:** Reference implementations available
**Reference Implementation:** Montana v1.0

---

## Overview

Layer 3+ encompasses concrete protocol implementations that build upon the ATC stack (Layers -1, 0, 1, 2). Unlike lower layers which define constraints and abstractions, Layer 3+ contains actual deployable protocols with specific design choices.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3+: Implementations                                      │
│  Specific protocols, networks, cryptocurrencies                │
│  Examples: Montana, future protocols                            │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Consensus Protocols                        v1.0      │
│  What is AGREEABLE: Safety, Liveness, Finality, BFT           │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Protocol Primitives                        v1.1      │
│  What is BUILDABLE: VDF, VRF, Commitment, Timestamp, Ordering  │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: Computational Constraints                   v1.0     │
│  What is HARD: OWF, Lattice, CRHF, VDF, NIST PQC              │
└─────────────────────────────────────────────────────────────────┘
                              ↑ builds on
┌─────────────────────────────────────────────────────────────────┐
│  Layer -1: Physical Constraints                       v2.1     │
│  What is IMPOSSIBLE: Thermodynamics, Light speed, Landauer    │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Layer 3+ Contains

| Aspect | Description |
|--------|-------------|
| **Network topology** | Peer discovery, connection management |
| **Economic incentives** | Token distribution, fees, rewards |
| **Governance** | Upgrade mechanisms, voting |
| **State management** | Accounts, UTXO, mempool |
| **API/RPC** | External interfaces |
| **Storage** | Database schema, pruning |

---

## What Layer 3+ Inherits

From lower layers, implementations inherit constraints they cannot violate:

| From Layer | Constraint |
|------------|------------|
| L-1 | Physical bounds (light speed, Landauer, Bekenstein) |
| L0 | Computational hardness (SHA-3, ML-KEM, MLWE) |
| L1 | Primitive security (VDF sequentiality, VRF uniqueness) |
| L2 | Consensus properties (safety, liveness under model) |

**Closing principle applies:** Implementations may assume weaker guarantees; they cannot assume stronger guarantees without leaving known science.

---

## Reference Implementation: Montana

**Montana v1.0** serves as the reference implementation of the ATC stack.

| Aspect | Montana Choice |
|--------|----------------|
| Consensus | DAG-PHANTOM + VDF + Bitcoin anchor |
| Cryptography | SPHINCS+ signatures, ML-KEM encryption |
| Time source | 34 NTP servers, 8 geographic regions |
| Finality | VDF (soft) + Bitcoin (hard) |
| Token | Ɉ (seconds), 1.26B supply, fair launch |

**Specification:** [MONTANA_TECHNICAL_SPECIFICATION.md](../../Montana/MONTANA_TECHNICAL_SPECIFICATION.md)

---

## ATC Layer Mapping

Montana uses internal layer naming. Here is the mapping to ATC layers:

| Montana Internal | ATC Layer | Description |
|------------------|-----------|-------------|
| Layer 0: Atomic Time | L-1.2, L-1.5 | Atomic time reproducibility, terrestrial uniformity |
| Layer 1: VDF | L-1.1 | VDF primitive (SHAKE256 hash chain) |
| Layer 2: Bitcoin Anchor | L-2.6.4 | Anchor-based finality |
| Heartbeat System | L-1.4 | Timestamp primitive |
| ECVRF Eligibility | L-1.2 | VRF primitive |
| DAG-PHANTOM | L-2.5.2 | DAG chain model |

---

## Implementation Checklist

For any Layer 3+ implementation:

### Required
- [ ] Uses only L0 cryptographic primitives or stronger
- [ ] Respects L1 primitive security properties
- [ ] Implements L2 consensus properties correctly
- [ ] Documents all L-1 physical assumptions
- [ ] Specifies network model (sync/async/partial)
- [ ] Documents fault threshold

### Recommended
- [ ] Post-quantum cryptography from day one
- [ ] Fair launch (no pre-mine)
- [ ] Explicit type classification for all claims
- [ ] Upgrade path documented

---

## Future Implementations

The ATC stack is designed to support multiple Layer 3+ implementations:

- **Montana:** Time-based consensus with Bitcoin anchoring
- **[Future]:** Application-specific chains
- **[Future]:** Privacy-focused variants
- **[Future]:** Cross-chain bridges

Each implementation makes its own design choices within ATC constraints.

---

## Versioning

Layer 3+ implementations have their own version numbers independent of ATC layers.

| Implementation | Version | ATC Compatibility |
|----------------|---------|-------------------|
| Montana | v1.0 | ATC v8.1 (L-1 v2.1, L0 v1.0, L1 v1.1, L2 v1.0) |

---

*Layer 3+ represents concrete protocol implementations built on the ATC foundation. Each implementation inherits the guarantees of lower layers while making specific design choices for its use case.*
