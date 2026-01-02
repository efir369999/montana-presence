# Ɉ Montana: Temporal Time Unit — Technical Specification v3.6

**Protocol Version:** 9
**Document Version:** 3.6
**Date:** January 2026
**Ticker:** $MONT
**Architecture:** Timechain
**ATC Compatibility:** v10.0 (L-1 v2.1, L0 v1.0, L1 v1.1, L2 v1.0)

> **Ɉ** (inverted t) is a Temporal Time Unit. **Montana** is the Timechain that produces it.
> ```
> lim(evidence → ∞) 1 Ɉ → 1 second
> ```
> **Timechain:** chain of time, bounded by physics.
> Built on ATC Layer 3+. See [MONTANA_ATC_MAPPING.md](MONTANA_ATC_MAPPING.md) for layer mapping.
> **v3.6:** Timechain architecture, UTC finality, ±5s tolerance, platform-independent light clients.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Time Unit Specification](#2-time-unit-specification)
3. [Asymptotic Trust Consensus (ATC)](#3-asymptotic-trust-consensus-atc)
4. [Layer 0: Sequential Computation](#4-layer-0-sequential-computation)
5. [Layer 1: Temporal Proof (Class Group VDF)](#5-layer-1-temporal-proof-class-group-vdf)
6. [Layer 2: Accumulated Finality](#6-layer-2-accumulated-finality)
    - [6.8 Fork Choice Rule](#68-fork-choice-rule)
    - [6.9 Network Partition Handling](#69-network-partition-handling)
    - [6.10 Minimum Viable Network](#610-minimum-viable-network)
7. [Heartbeat Structure](#7-heartbeat-structure)
8. [Score System](#8-score-system)
9. [Block Structure](#9-block-structure)
10. [Block Production](#10-block-production)
11. [Block Reward Distribution](#11-block-reward-distribution)
12. [Transaction Structure](#12-transaction-structure)
13. [Transaction Fees](#13-transaction-fees)
14. [Privacy Tiers](#14-privacy-tiers)
15. [Light Client Protocol](#15-light-client-protocol)
16. [Cryptographic Primitives](#16-cryptographic-primitives)
17. [Network Protocol](#17-network-protocol)
    - [17.4 Peer Discovery](#174-peer-discovery)
    - [17.5 Connection Handshake](#175-connection-handshake)
    - [17.6 Message Format](#176-message-format)
    - [17.7 Address Relay](#177-address-relay)
    - [17.8 Inventory Protocol](#178-inventory-protocol)
    - [17.9 Block Relay](#179-block-relay)
    - [17.10 Ban System](#1710-ban-system)
    - [17.11 Connection Management](#1711-connection-management)
18. [Governance](#18-governance)
19. [Constants Reference](#19-constants-reference)
20. [API Reference](#20-api-reference)
21. [Account State](#21-account-state)
22. [Wallet (PLUTUS)](#22-wallet-plutus)
23. [Mempool Management](#23-mempool-management)
24. [Sync Protocol](#24-sync-protocol)
25. [Storage Structure](#25-storage-structure)
26. [Node Configuration](#26-node-configuration)
27. [Genesis Block](#27-genesis-block)
28. [Constants Reference (Complete)](#28-constants-reference-complete)

---

## 1. Overview

### 1.1 Purpose

This document provides the complete technical specification for implementing the Ɉ Montana protocol. It serves as:
- Implementation guide for developers
- Reference for auditors
- Specification for interoperability

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ɉ MONTANA ARCHITECTURE                      │
│                     Timechain (ATC Layer 3+)                     │
│                     Self-Sovereign • Physics-Based               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  NODE TYPES (2 types only)                                       │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐ │
│  │       FULL NODE          │  │        LIGHT NODE            │ │
│  │  • Full history storage  │  │  • From connection only      │ │
│  │  • VDF computation       │  │  • No VDF                    │ │
│  │  • Full validation       │  │  • Relies on Full Nodes      │ │
│  └────────────┬─────────────┘  └──────────────┬───────────────┘ │
│               │                                │                 │
│  PARTICIPATION TIERS (numbered 1-2-3)          │                 │
│  ┌────────────▼─────────────┐  ┌──────────────▼───────────────┐ │
│  │  TIER 1 (70%)            │  │  TIER 2 (20%) │ TIER 3 (10%) │ │
│  │  Full Node Operators     │  │  Light Node   │ TG Users     │ │
│  └──────────────────────────┘  └──────────────────────────────┘ │
│               │                                │                 │
│               └────────────────┬───────────────┘                 │
│                                │                                 │
│  ┌─────────────────────────────▼─────────────────────────────┐  │
│  │           MONTANA CONSENSUS (ATC L2 Patterns)              │  │
│  │  Accumulated VDF → ATC L-2.6.3 (VDF-based Finality)       │  │
│  │  VDF Temporal    → ATC L-1.1 (VDF Primitive)              │  │
│  │  Sequentiality   → ATC L-1 (Physical Constraints)         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              DAG-PHANTOM (ATC L-2.5.2)                     │  │
│  │  Block ordering without leader selection                   │  │
│  │  ECVRF eligibility (ATC L-1.2.3 — quantum-vulnerable)     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

ATC Foundation:
┌─────────────────────────────────────────────────────────────────┐
│  ATC L2:  Consensus (Safety, Liveness, Finality, BFT)          │
│  ATC L1:  Primitives (VDF, VRF, Commitment, Timestamp)         │
│  ATC L0:  Computation (SHA-3, ML-KEM, SPHINCS+, MLWE)          │
│  ATC L-1: Physics (Sequentiality, Landauer, Light speed)       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Participation Model

Montana has exactly **3 participation tiers** and **2 node types**.

#### 1.3.1 Node Types (2 types only)

```python
class NodeType(IntEnum):
    """
    Montana supports exactly TWO node types.
    No other node types exist in the protocol.
    """
    FULL = 1    # Full Node: Downloads and stores FULL timechain history
    LIGHT = 2   # Light Node: Stores history from connection moment only
```

| Node Type | Storage | VDF | Tier |
|-----------|---------|-----|------|
| **Full Node** | Full timechain history (downloads all) | Yes | Tier 1 |
| **Light Node** | From connection moment only | No | Tier 2 |

**Full Node (Tier 1):**
- Downloads and stores **entire timechain history**
- Computes VDF proofs (sequential, non-parallelizable)
- Validates all blocks and transactions
- Produces full heartbeats (VDF + signature)
- **Required for network security**

**Light Node (Tier 2):**
- Stores history **only from its connection moment** (mandatory)
- Downloads timechain from connection point forward only
- Receives VDF proofs from Full Nodes (validates, does not compute)
- Validates blocks from connection onward
- Produces light heartbeats (timestamp verified against Full Nodes)
- Relies on Full Nodes for historical security

#### 1.3.2 Participation Tiers (3 tiers only)

```python
class ParticipationTier(IntEnum):
    """
    Montana supports exactly THREE participation tiers.
    Tier numbering: 1, 2, 3 (not 0, 1, 2)
    """
    TIER_1 = 1  # Full Node operators
    TIER_2 = 2  # Light Node operators OR Light Client owners
    TIER_3 = 3  # Light Client users (any platform)

# Lottery probability weights
TIER_WEIGHTS = {
    ParticipationTier.TIER_1: 0.70,  # 70% probability
    ParticipationTier.TIER_2: 0.20,  # 20% probability
    ParticipationTier.TIER_3: 0.10,  # 10% probability
}
```

| Tier | Participants | Node Type | Lottery Weight | Purpose |
|------|--------------|-----------|----------------|---------|
| **Tier 1** | Full Node operators | Full Node | **70%** | Network security |
| **Tier 2** | Light Node / Light Client owners | Light Node | **20%** | Infrastructure |
| **Tier 3** | Light Client users | — | **10%** | Mass adoption |

**Summary by Node Type:**
| Node Type | Tiers | Total Lottery Weight |
|-----------|-------|----------------------|
| **Full Node** | Tier 1 | **70%** |
| **Light Node / Light Client** | Tier 2+3 | **30%** |

**Light Client Platforms:**

Montana has **no dependency** on any specific platform. Light clients are interchangeable interfaces:

| Platform | Type | Status |
|----------|------|--------|
| Telegram Bot | Messaging | Initial implementation |
| Discord Bot | Messaging | Planned |
| WeChat Mini Program | Messaging | Planned |
| iOS App (App Store) | Mobile | Planned |
| Android App (Google Play) | Mobile | Planned |
| Web Application | Browser | Planned |

**Design Principle:** Time passes equally for all participants regardless of platform. No platform provides competitive advantage. The only arbiter is physics.

#### 1.3.3 Heartbeat Types

```python
@dataclass
class FullHeartbeat:
    """Tier 1: Full Node heartbeat with complete proofs."""
    pubkey: PublicKey
    vdf_proof: VDFProof              # Sequential computation proof
    finality_ref: FinalityReference
    signature: Signature             # SPHINCS+ (17,088 bytes)

@dataclass
class LightHeartbeat:
    """Tier 2/3: Light heartbeat without VDF computation."""
    pubkey: PublicKey
    timestamp_ms: int                # Verified against VDF timeline
    source: HeartbeatSource          # LIGHT_NODE, LIGHT_CLIENT
    platform_id: Optional[str]       # Platform-specific ID (any supported platform)
    signature: Signature             # SPHINCS+ (17,088 bytes)
```

#### 1.3.4 Tier Requirements

| Requirement | Tier 1 | Tier 2 | Tier 3 |
|-------------|--------|--------|--------|
| Run Full Node | **Yes** | No | No |
| Run Light Node | No | **Yes** (or Light Client) | No |
| Download full history | **Yes** | No | No |
| Store from connection | **Yes** | **Yes** | No |
| VDF computation | **Yes** | No | No |
| Own Light Client | No | Optional | No |
| Use Light Client | No | No | **Yes** |
| Montana wallet | **Yes** | **Yes** | **Yes** |
| Heartbeat cooldown | 1/min | 1/min | 1/min |

---

## 2. Temporal Time Unit Specification

### 2.1 Definition

```python
# Ɉ Montana — Mechanism for asymptotic trust in time value
PROJECT: str = "Ɉ Montana"
SYMBOL: str = "Ɉ"
TICKER: str = "$MONT"
DEFINITION: str = "lim(evidence → ∞) 1 Ɉ → 1 second"
TYPE: str = "Temporal Time Unit"
```

### 2.2 Supply

```python
TOTAL_SUPPLY: int = 1_260_000_000        # 21 million minutes
INITIAL_DISTRIBUTION: int = 3000         # 50 minutes per block
HALVING_INTERVAL: int = 210_000          # Blocks per halving
TOTAL_BLOCKS: int = 6_930_000            # 33 eras × 210,000 blocks
TOTAL_ERAS: int = 33                     # Halving count
```

### 2.3 Zero Pre-allocation

```python
PRE_ALLOCATION: int = 0
FOUNDER_UNITS: int = 0
RESERVED_UNITS: int = 0
```

### 2.4 Unit Conversions

```python
def seconds_to_minutes(seconds: int) -> float:
    return seconds / 60

def seconds_to_hours(seconds: int) -> float:
    return seconds / 3600

def seconds_to_days(seconds: int) -> float:
    return seconds / 86400

def format_montana(amount: int) -> str:
    """Format amount with appropriate unit."""
    if amount >= 86400:
        return f"{amount / 86400:.2f} days"
    elif amount >= 3600:
        return f"{amount / 3600:.2f} hours"
    elif amount >= 60:
        return f"{amount / 60:.2f} minutes"
    else:
        return f"{amount} Ɉ"
```

### 2.5 Block Distribution Function

```python
def get_block_distribution(height: int) -> int:
    """
    Calculate TTU distribution for given block height.

    Args:
        height: Block height

    Returns:
        TTU distribution in Ɉ (seconds)
    """
    halvings = height // HALVING_INTERVAL
    if halvings >= TOTAL_ERAS:
        return 0
    return INITIAL_DISTRIBUTION >> halvings
```

### 2.6 Distribution Schedule

| Era | Height Range | Per Block | Era Total | Cumulative |
|-----|--------------|-----------|-----------|------------|
| 1 | 0 - 209,999 | 3,000 Ɉ (50 min) | 630,000,000 Ɉ | 630,000,000 Ɉ |
| 2 | 210,000 - 419,999 | 1,500 Ɉ (25 min) | 315,000,000 Ɉ | 945,000,000 Ɉ |
| 3 | 420,000 - 629,999 | 750 Ɉ (12.5 min) | 157,500,000 Ɉ | 1,102,500,000 Ɉ |
| 4 | 630,000 - 839,999 | 375 Ɉ (6.25 min) | 78,750,000 Ɉ | 1,181,250,000 Ɉ |
| 5 | 840,000 - 1,049,999 | 187 Ɉ (~3 min) | 39,270,000 Ɉ | 1,220,520,000 Ɉ |
| ... | ... | ... | ... | ... |
| 33 | 6,720,000 - 6,929,999 | 1 Ɉ (1 sec) | Final | 1,260,000,000 Ɉ |

---

## 3. Asymptotic Trust Consensus (ATC)

Montana implements the Asymptotic Trust Consensus architecture. For complete specifications, see:
- [ATC Layer -1: Physical Constraints](../Layer%20-1/layer_minus_1.md)
- [ATC Layer 0: Computational Constraints](../Layer%200/layer_0.md)
- [ATC Layer 1: Protocol Primitives](../Layer%201/layer_1.md)
- [ATC Layer 2: Consensus Protocols](../Layer%202/layer_2.md)

### 3.1 Core Principle

```
lim(evidence → ∞) Trust = 1
∀t: Trust(t) < 1

"We approach certainty; we never claim to reach it."
```

Trust requirements approach certainty asymptotically as evidence accumulates across layers.

### 3.2 Montana's Internal Layers → ATC Mapping

| Montana Internal | ATC Layer | Trust Model | Data Source |
|------------------|-----------|-------------|-------------|
| Layer 0: VDF Computation | ATC L-1.1 | Sequential computation | Class Group squaring |
| Layer 1: VDF Temporal | ATC L-1.1 | Sequential computation | VDF heartbeats |
| Layer 2: Accumulated Finality | ATC L-2.6.3 | VDF-based finality | Accumulated VDF depth |

### 3.3 ATC Layer Dependencies

Montana inherits guarantees from all ATC layers:

| ATC Layer | Montana Uses | Constraint |
|-----------|--------------|------------|
| L-1 (Physics) | Sequentiality, Landauer | Physical bound |
| L0 (Computation) | SHA-3, SPHINCS+, ML-KEM | Post-quantum secure |
| L1 (Primitives) | VDF, VRF, Commitment | Proven security |
| L2 (Consensus) | DAG, BFT, VDF Finality | Formal guarantees |

**Closing Principle:** Montana may assume weaker guarantees than ATC provides. Stronger assumptions require leaving known science.

---

## 4. Montana Layer 0: Sequential Computation

*Maps to ATC L-1 (Physical Constraints)*

Montana's Layer 0 provides the physical foundation for time verification. Time is sequential — each moment depends on the previous. This sequentiality is the basis for VDF security.

### 4.1 Sequentiality Guarantee

```python
# Core guarantee: Class Group squaring is mathematically sequential
# Security reduction to class group order problem (Type B security)

VDF_SEQUENTIALITY_GUARANTEE = """
For imaginary quadratic class group Cl(Δ):
  g^(2^T) requires T sequential squarings

  Security reduction:
    "VDF shortcut exists" → "Class group order efficiently computable"

  Class group order problem: hard for 40+ years (Buchmann, Williams 1988)
"""
```

### 4.2 Mathematical Foundation

The VDF sequentiality property derives from:
- **Group structure:** Class groups require sequential exponentiation
- **Order hardness:** Computing |Cl(Δ)| is subexponential (best known algorithms)
- **40+ years analysis:** Class group order problem remains hard

### 4.3 UTC Neutralization of Quantum Advantage

Class Group VDF is vulnerable to Shor's algorithm. Montana's UTC finality model makes this irrelevant:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UTC BOUNDARY = PHYSICAL EQUALIZER                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Finality window: 60 seconds (UTC boundary to UTC boundary)             │
│                                                                          │
│  Classical node:    VDF in 30 sec → wait 30 sec → 1 heartbeat           │
│  ASIC node:         VDF in 5 sec  → wait 55 sec → 1 heartbeat           │
│  Quantum attacker:  VDF in 0.001s → wait 59.999s → 1 heartbeat          │
│                                                                          │
│  Result: ALL receive exactly ONE heartbeat per finality window          │
│                                                                          │
│  UTC boundary is the rate limiter                                        │
│  VDF speed is irrelevant                                                 │
│  Time passes at the same rate for quantum computers                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Security Analysis:**

| Attacker | VDF Computation | Heartbeats/Minute | Advantage |
|----------|-----------------|-------------------|-----------|
| Classical CPU | 30 seconds | 1 | Baseline |
| ASIC | 5 seconds | 1 | None (waits for UTC) |
| Quantum computer | 0.001 seconds | 1 | None (waits for UTC) |

VDF proves participation eligibility within a finality window. The physical constraint is UTC time itself.

---

## 5. Montana Layer 1: Temporal Proof (Class Group VDF)

*Maps to ATC L-1.1 (Verifiable Delay Functions)*

Montana's Layer 1 uses **Class Group VDF** (Wesolowski 2019) for temporal proof — Type B security with mathematical guarantees.

### 5.1 Class Group VDF

**Type B Security:** Mathematical reduction to class group order problem.

| Property | Guarantee |
|----------|-----------|
| Sequentiality | Mathematical (group structure requires sequential squaring) |
| Security | Type B (reduction to class group order problem) |
| Trusted setup | None required (class groups are parameter-free) |
| Verification | O(log T) using Wesolowski proof |
| Quantum | Shor applies (neutralized by UTC model) |

### 5.2 VDF Parameters

```python
# Class Group VDF (Wesolowski 2019)
VDF_TYPE: str = "class_group"
VDF_DISCRIMINANT_BITS: int = 2048       # Security parameter
VDF_BASE_ITERATIONS: int = 16777216     # 2^24 sequential squarings
VDF_MAX_ITERATIONS: int = 268435456     # 2^28
VDF_PROOF_SIZE_BYTES: int = 2048        # Wesolowski proof ~2KB

# Discriminant generation (deterministic from seed)
VDF_SEED_PREFIX: bytes = b"MONTANA_VDF_V9_CLASS_GROUP_"
```

### 5.3 VDF Structure

```python
@dataclass
class ClassGroupElement:
    """Element of imaginary quadratic class group Cl(Δ)."""
    a: int      # First coefficient
    b: int      # Second coefficient
    # Represents ideal class (a, b, c) where b² - 4ac = Δ

@dataclass
class VDFProof:
    """Class Group VDF proof (Wesolowski construction)."""
    input_element: ClassGroupElement    # g ∈ Cl(Δ)
    output_element: ClassGroupElement   # g^(2^T) ∈ Cl(Δ)
    iterations: int                     # T = number of squarings
    proof_element: ClassGroupElement    # π for Wesolowski verification
    discriminant: int                   # Δ (negative, determines group)

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_class_group_element(self.input_element)
        writer.write_class_group_element(self.output_element)
        writer.write_u64(self.iterations)
        writer.write_class_group_element(self.proof_element)
        writer.write_big_int(self.discriminant)
        return writer.to_bytes()

def compute_vdf(input_data: bytes, iterations: int) -> VDFProof:
    """
    Compute Class Group VDF.

    Sequential: g^(2^T) via T squarings in Cl(Δ)
    """
    # Generate deterministic discriminant from input
    discriminant = generate_discriminant(input_data, VDF_DISCRIMINANT_BITS)

    # Map input to group element
    g = hash_to_class_group(input_data, discriminant)

    # Sequential squaring
    result = g
    for _ in range(iterations):
        result = class_group_square(result, discriminant)

    # Generate Wesolowski proof
    proof_element = generate_wesolowski_proof(g, result, iterations, discriminant)

    return VDFProof(
        input_element=g,
        output_element=result,
        iterations=iterations,
        proof_element=proof_element,
        discriminant=discriminant
    )
```

### 5.4 Wesolowski Verification

```python
def verify_vdf(proof: VDFProof) -> bool:
    """
    Verify Class Group VDF using Wesolowski protocol.

    Verification complexity: O(log T) group operations
    """
    g = proof.input_element
    y = proof.output_element
    pi = proof.proof_element
    T = proof.iterations
    Δ = proof.discriminant

    # Fiat-Shamir challenge
    l = hash_to_prime(g, y, T)

    # Compute r = 2^T mod l
    r = pow(2, T, l)

    # Verify: π^l · g^r == y
    lhs = class_group_multiply(
        class_group_exp(pi, l, Δ),
        class_group_exp(g, r, Δ),
        Δ
    )

    return class_group_equal(lhs, y)
```

### 5.5 Security Properties

**Type B Security Reduction:**

```
Theorem (Wesolowski 2019):
  If an adversary can compute g^(2^T) faster than T sequential squarings,
  then they can compute the order of the class group Cl(Δ).

Class Group Order Problem:
  Given discriminant Δ, compute |Cl(Δ)|

Status:
  - Best classical algorithms: subexponential L[1/2]
  - Quantum: Shor's algorithm applies
  - Practical security: 2048-bit discriminant provides 128-bit classical security
```

**UTC Model Security:**

```
Quantum break of VDF does not affect Montana security:
  - VDF proves eligibility to participate in finality window
  - Faster VDF computation = longer wait until UTC boundary
  - 1 heartbeat per pubkey per 60-second window (UTC enforced)
  - Physical time is the rate limiter, computational speed is irrelevant
```

### 5.6 Implementation References

Montana uses Class Group VDF as implemented in:
- **Chia VDF** (production, open source)
- **chiavdf library** (C++ with Python bindings)

```python
# Integration with chiavdf
from chiavdf import create_discriminant, prove, verify

def compute_vdf_chia(challenge: bytes, iterations: int) -> VDFProof:
    """Compute VDF using Chia's implementation."""
    discriminant = create_discriminant(challenge, VDF_DISCRIMINANT_BITS)
    result, proof = prove(challenge, discriminant, iterations)
    return VDFProof(
        input_element=challenge_to_element(challenge, discriminant),
        output_element=result,
        iterations=iterations,
        proof_element=proof,
        discriminant=discriminant
    )
```

**Design note:** T = 2²⁴ is fixed. Hardware provides constant-factor speedup only. UTC boundaries ensure all participants receive equal heartbeats regardless of computation speed.

---

## 6. Montana Layer 2: UTC Finality

*Maps to ATC L-2.6.3 (Time-Based Finality)*

Montana's Layer 2 achieves finality through **UTC time boundaries** — deterministic points in time when blocks become final. This provides self-sovereign finality based entirely on physics: time itself.

### 6.1 Finality Model

```python
# UTC-based finality (v3.4)
TIME_TOLERANCE_SEC: int = 5              # ±5 seconds UTC tolerance between nodes
FINALITY_INTERVAL_SEC: int = 60          # 1 minute — finality boundary interval

# Finality levels (UTC boundaries passed)
FINALITY_SOFT_BOUNDARIES: int = 1        # 1 minute
FINALITY_MEDIUM_BOUNDARIES: int = 2      # 2 minutes
FINALITY_HARD_BOUNDARIES: int = 3        # 3 minutes
```

### 6.2 UTC Finality Boundaries

```
UTC:     00:00  00:01  00:02  00:03  00:04  00:05  ...
           │      │      │      │      │      │
           ▼      ▼      ▼      ▼      ▼      ▼
        ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
        │ F0 │ │ F1 │ │ F2 │ │ F3 │ │ F4 │ │ F5 │
        └────┘ └────┘ └────┘ └────┘ └────┘ └────┘
           │      │
           │      └─ Finalizes blocks 00:00:00 - 00:00:59
           │
           └─ Genesis finality

Finality occurs at fixed UTC boundaries: every minute (XX:XX:00)
```

### 6.3 Security Properties

**Attack cost:** Requires advancing UTC. Time is universal.

```python
def get_finality_boundary(timestamp_ms: int) -> int:
    """
    Get the next finality boundary for a given timestamp.

    Boundaries are at 1-minute UTC intervals.
    """
    interval_ms = FINALITY_INTERVAL_SEC * 1000
    return ((timestamp_ms // interval_ms) + 1) * interval_ms

def get_finality_level(block_timestamp_ms: int, current_time_ms: int) -> str:
    """
    Determine finality level based on UTC boundaries passed.

    This is a PHYSICAL BOUND:
    - Hardware speed bounded by UTC
    - Time allocation is equal for all
    - Physics constraint applies universally
    """
    block_boundary = get_finality_boundary(block_timestamp_ms)
    boundaries_passed = (current_time_ms - block_boundary) // (FINALITY_INTERVAL_SEC * 1000)

    if boundaries_passed >= FINALITY_HARD_BOUNDARIES:
        return "hard"      # 3+ minutes
    elif boundaries_passed >= FINALITY_MEDIUM_BOUNDARIES:
        return "medium"    # 2+ minutes
    elif boundaries_passed >= FINALITY_SOFT_BOUNDARIES:
        return "soft"      # 1+ minute
    else:
        return "pending"

# ASIC Resistance:
# - Old model: ASIC computes VDF 40x faster → 40x advantage
# - UTC model: ASIC computes faster but waits for UTC → NO advantage
```

### 6.4 Time Consensus

```python
# Time source: system UTC on each node
# No external NTP servers required
# Tolerance: ±5 seconds between nodes

def is_timestamp_valid(timestamp_ms: int, local_time_ms: int) -> bool:
    """
    Validate timestamp against local UTC.

    Accepts timestamps within ±5 seconds of local time.
    """
    tolerance_ms = TIME_TOLERANCE_SEC * 1000
    return abs(timestamp_ms - local_time_ms) <= tolerance_ms
```

### 6.5 VDF Role in UTC Model

VDF proves participation in a finality window — not computation speed:

```python
def can_participate_in_finality(
    vdf_completion_time_ms: int,
    finality_boundary_ms: int
) -> bool:
    """
    Check if VDF completed before finality boundary.

    Fast hardware: completes early, waits for boundary
    Slow hardware: must complete before boundary or miss window
    """
    return vdf_completion_time_ms <= finality_boundary_ms

# Example:
# Finality boundary: 00:01:00 UTC
# Node A (ASIC):  VDF ready 00:00:12 → waits → participates
# Node B (fast):  VDF ready 00:00:25 → waits → participates
# Node C (slow):  VDF ready 00:00:55 → participates
# Node D (too slow): VDF ready 00:01:02 → MISSES window → next boundary
```

### 6.6 Finality Checkpoint Structure

```python
@dataclass
class FinalityCheckpoint:
    """Finality checkpoint at UTC boundary."""
    boundary_timestamp_ms: int      # u64 - UTC boundary (e.g., 00:10:00)
    blocks_merkle_root: bytes       # 32 bytes - Merkle root of blocks in window
    vdf_proofs_root: bytes          # 32 bytes - Merkle root of VDF proofs
    participants_count: int         # u32 - Number of participating nodes
    total_vdf_iterations: int       # u64 - Sum of all VDF iterations in window
    aggregate_score: int            # u64 - Sum of participant scores (√heartbeats)
    previous_checkpoint: bytes      # 32 bytes - Hash of previous checkpoint

    SIZE: int = 128  # bytes (112 + 8 + 8)

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u64(self.boundary_timestamp_ms)
        writer.write_raw(self.blocks_merkle_root)
        writer.write_raw(self.vdf_proofs_root)
        writer.write_u32(self.participants_count)
        writer.write_u64(self.total_vdf_iterations)
        writer.write_u64(self.aggregate_score)
        writer.write_raw(self.previous_checkpoint)
        return writer.to_bytes()

    def checkpoint_hash(self) -> bytes:
        return sha3_256(self.serialize())
```

### 6.7 Clock Security

**Each participant is responsible for their own time, just as they are responsible for their own private keys.**

Montana relies on system UTC. Each node uses its own clock.

| Responsibility | Owner | Montana's Role |
|----------------|-------|----------------|
| Private key | Node operator | Verify signatures |
| System clock | Node operator | Accept ±5 seconds |
| Network connection | Node operator | Relay messages |

**Self-Sovereign Time:**

| Property | Guarantee |
|----------|-----------|
| Time source | Each node's own UTC |
| Independence | Isolated from peer influence |
| Tolerance | ±5 seconds for propagation, drift, jitter |

```python
# ±5 second tolerance breakdown
TOLERANCE_BUDGET = {
    "network_propagation": 2.0,  # seconds
    "clock_drift": 1.0,          # seconds
    "ntp_jitter": 1.0,           # seconds
    "safety_margin": 1.0,        # seconds
    # Total: 5 seconds
}

def is_node_synchronized(local_utc_ms: int, reference_ms: int) -> bool:
    """
    Check if node is within acceptable time window.

    Nodes within ±5 seconds participate in current finality window.
    Nodes outside participate in subsequent windows.
    """
    return abs(local_utc_ms - reference_ms) <= TIME_TOLERANCE_SEC * 1000
```

**Recommendations for Full Node Operators:**

| Practice | Purpose |
|----------|---------|
| Multiple NTP sources (3+) | Resilience |
| NTS (NTP over TLS) | Authenticated synchronization |
| Hardware clock monitoring | Early drift detection |

**Principle:**

Clock security = private key security. Each operator controls their own system.

### 6.8 Fork Choice Rule

```python
def select_best_chain(chains: List[Chain]) -> Chain:
    """
    Fork choice: chain with more finality checkpoints.

    Cascade tiebreakers (each level has semantic meaning):
    1. More finality checkpoints (more UTC boundaries)
    2. More participants in latest checkpoint (larger active network)
    3. Higher total VDF iterations (more proven time)
    4. Higher aggregate participant score (more reliable participants)
    5. Lower checkpoint hash (deterministic last resort)
    """
    return max(chains, key=lambda c: (
        c.finality_checkpoint_count,
        c.latest_checkpoint.participants_count,
        c.latest_checkpoint.total_vdf_iterations,
        c.latest_checkpoint.aggregate_score,
        -int.from_bytes(c.latest_checkpoint.checkpoint_hash(), 'big')
    ))
```

### 6.9 Network Partition Handling

During network partition, both partitions continue creating checkpoints independently at the same UTC boundaries.

```
Partition A (60% nodes)     Partition B (40% nodes)
        │                           │
00:01   F1-A (60 heartbeats)       F1-B (40 heartbeats)
00:02   F2-A                        F2-B
00:03   F3-A                        F3-B
        │                           │
        └─────── reconnect ─────────┘
                    │
               Conflict resolution
```

**Checkpoint Conflict Resolution:**

```python
def resolve_checkpoint_conflict(
    checkpoint_a: FinalityCheckpoint,
    checkpoint_b: FinalityCheckpoint
) -> FinalityCheckpoint:
    """
    Resolve conflicting checkpoints at the same UTC boundary.

    Cascade tiebreakers (each level has semantic meaning):
    1. More participants (heartbeats) → larger active network
    2. Higher total VDF iterations → more proven time
    3. Higher aggregate score → more reliable participants
    4. Lower checkpoint hash → deterministic last resort

    Level 4 is reached only with perfect 50/50, identical participants,
    identical VDF. Probability → 0.

    Returns canonical checkpoint.
    """
    # Must be same UTC boundary
    assert checkpoint_a.boundary_timestamp_ms == checkpoint_b.boundary_timestamp_ms

    cp_a, cp_b = checkpoint_a, checkpoint_b

    # 1. More participants → larger active network
    if cp_a.participants_count != cp_b.participants_count:
        return max(cp_a, cp_b, key=lambda c: c.participants_count)

    # 2. More VDF iterations → more proven time
    if cp_a.total_vdf_iterations != cp_b.total_vdf_iterations:
        return max(cp_a, cp_b, key=lambda c: c.total_vdf_iterations)

    # 3. Higher aggregate score → more reliable participants
    if cp_a.aggregate_score != cp_b.aggregate_score:
        return max(cp_a, cp_b, key=lambda c: c.aggregate_score)

    # 4. Hash — only if ALL equal (astronomically rare)
    return min(cp_a, cp_b, key=lambda c: c.checkpoint_hash())


def merge_partition_chains(
    local_chain: List[FinalityCheckpoint],
    remote_chain: List[FinalityCheckpoint]
) -> List[FinalityCheckpoint]:
    """
    Merge two checkpoint chains after network partition.

    Preserves canonical checkpoint at each boundary.
    Transactions from all checkpoints are preserved in DAG
    and included in subsequent checkpoints.
    """
    merged = []

    # Find common ancestor
    common_ancestor = find_common_checkpoint(local_chain, remote_chain)

    # Resolve each conflicting boundary
    local_idx = local_chain.index(common_ancestor) + 1
    remote_idx = remote_chain.index(common_ancestor) + 1

    while local_idx < len(local_chain) or remote_idx < len(remote_chain):
        local_cp = local_chain[local_idx] if local_idx < len(local_chain) else None
        remote_cp = remote_chain[remote_idx] if remote_idx < len(remote_chain) else None

        if local_cp and remote_cp:
            if local_cp.boundary_timestamp_ms == remote_cp.boundary_timestamp_ms:
                # Same boundary - resolve conflict
                merged.append(resolve_checkpoint_conflict(local_cp, remote_cp))
                local_idx += 1
                remote_idx += 1
            elif local_cp.boundary_timestamp_ms < remote_cp.boundary_timestamp_ms:
                merged.append(local_cp)
                local_idx += 1
            else:
                merged.append(remote_cp)
                remote_idx += 1
        elif local_cp:
            merged.append(local_cp)
            local_idx += 1
        else:
            merged.append(remote_cp)
            remote_idx += 1

    return merged
```

**Partition Behavior:**

| Scenario | Outcome | Recovery |
|----------|---------|----------|
| 60/40 split | Majority partition's checkpoints canonical | Minority transactions preserved in DAG |
| 50/50 split | Lower hash wins (deterministic) | Both partitions' DAG blocks preserved |
| Brief partition | Few checkpoints affected | Fast convergence |
| Long partition | Multiple checkpoints roll back | DAG merge preserves all transactions |

**Guarantees:**
- **Safety:** No conflicting finalized transactions (fork choice is deterministic)
- **Liveness:** Network recovers after partition heals (DAG merge)
- **No transaction loss:** DAG blocks from minority partition are preserved

### 6.10 Minimum Viable Network

For UTC finality to provide meaningful security guarantees, the network must meet minimum participation thresholds.

#### 6.10.1 Minimum Thresholds

```python
# Minimum viable network constants
MIN_FINALITY_PARTICIPANTS = 7       # BFT threshold: n ≥ 3f+1, f=2 → n≥7
MIN_GEOGRAPHIC_REGIONS = 2          # Avoid single-region failure
MIN_AUTONOMOUS_SYSTEMS = 3          # Network path diversity
MIN_FULL_NODES = 3                  # Minimum for checkpoint creation

# Confidence levels based on participation
CONFIDENCE_FULL = "full"            # ≥21 participants, ≥3 regions
CONFIDENCE_HIGH = "high"            # ≥7 participants, ≥2 regions
CONFIDENCE_LOW = "low"              # <7 participants OR <2 regions
```

#### 6.10.2 Participation Requirements

| Confidence Level | Participants | Regions | Finality Meaning |
|------------------|--------------|---------|------------------|
| **FULL** | ≥21 | ≥3 | Production-grade BFT (f=6) |
| **HIGH** | ≥7 | ≥2 | Meaningful BFT (f=2) |
| **LOW** | <7 or <2 regions | Degraded | Finality works but trust limited |

**Byzantine Fault Tolerance:**

```python
def get_bft_tolerance(participants: int) -> int:
    """
    Calculate Byzantine fault tolerance.

    BFT threshold: n ≥ 3f + 1
    Solving for f: f ≤ (n - 1) / 3
    """
    return (participants - 1) // 3

# Examples:
# 7 participants  → tolerates 2 Byzantine (f=2)
# 21 participants → tolerates 6 Byzantine (f=6)
# 100 participants → tolerates 33 Byzantine (f=33)
```

#### 6.10.3 Finality Confidence Calculation

```python
@dataclass
class FinalityConfidence:
    """Confidence assessment for a finality checkpoint."""
    level: str                      # "full", "high", "low"
    participants: int
    regions: int
    byzantine_tolerance: int
    reason: str

def assess_finality_confidence(checkpoint: FinalityCheckpoint) -> FinalityConfidence:
    """
    Assess confidence level for a finality checkpoint.

    Confidence depends on:
    1. Number of unique participants
    2. Geographic distribution (inferred from node metadata)
    3. Byzantine fault tolerance
    """
    participants = checkpoint.participants_count
    regions = estimate_geographic_regions(checkpoint)  # From node metadata
    f = (participants - 1) // 3

    if participants >= 21 and regions >= 3:
        return FinalityConfidence(
            level="full",
            participants=participants,
            regions=regions,
            byzantine_tolerance=f,
            reason=f"Production BFT: tolerates {f} Byzantine nodes"
        )
    elif participants >= 7 and regions >= 2:
        return FinalityConfidence(
            level="high",
            participants=participants,
            regions=regions,
            byzantine_tolerance=f,
            reason=f"Meaningful BFT: tolerates {f} Byzantine nodes"
        )
    else:
        return FinalityConfidence(
            level="low",
            participants=participants,
            regions=regions,
            byzantine_tolerance=f,
            reason="Degraded: insufficient participation for strong BFT"
        )
```

#### 6.10.4 Bootstrap Requirements

```python
# Minimum bootstrap network
BOOTSTRAP_REQUIREMENTS = {
    "full_nodes": 3,                # Minimum Full Nodes for genesis
    "regions": 2,                   # Minimum geographic regions
    "autonomous_systems": 3,        # Minimum AS diversity
}

# Bootstrap progression
BOOTSTRAP_PHASES = [
    # Phase 1: Genesis (3 Full Nodes, 2 regions)
    {"full_nodes": 3, "confidence": "low", "label": "Genesis"},

    # Phase 2: Early Network (7+ participants)
    {"full_nodes": 7, "confidence": "high", "label": "Early"},

    # Phase 3: Production (21+ participants, 3+ regions)
    {"full_nodes": 21, "confidence": "full", "label": "Production"},
]
```

#### 6.10.5 Degraded Mode Behavior

When network falls below minimum thresholds:

```python
def handle_degraded_network(checkpoint: FinalityCheckpoint) -> None:
    """
    Handle finality checkpoint in degraded network conditions.

    Degraded mode:
    - Finality checkpoints still created (protocol continues)
    - Checkpoints labeled with confidence level
    - Clients warned about reduced security
    - No protocol changes — only labeling
    """
    confidence = assess_finality_confidence(checkpoint)

    if confidence.level == "low":
        logger.warning(
            f"Degraded finality: {confidence.participants} participants, "
            f"{confidence.regions} regions. "
            f"Byzantine tolerance: {confidence.byzantine_tolerance}"
        )

        # Checkpoint is still valid but marked
        checkpoint.metadata["confidence"] = "low"
        checkpoint.metadata["warning"] = (
            "Finality confidence reduced. "
            "Consider waiting for network recovery."
        )
```

**Degraded Mode Guarantees:**

| Property | Degraded Mode | Notes |
|----------|---------------|-------|
| Checkpoint creation | ✓ Continues | Protocol does not halt |
| Fork choice | ✓ Deterministic | Same algorithm applies |
| Transaction processing | ✓ Continues | DAG accepts blocks |
| Finality confidence | ⚠ Reduced | Labeled in checkpoint |
| Client warnings | ✓ Enabled | Applications notified |

#### 6.10.6 Network Health Metrics

```python
@dataclass
class NetworkHealth:
    """Real-time network health assessment."""
    total_participants: int
    full_nodes: int
    light_nodes: int
    geographic_regions: int
    autonomous_systems: int
    confidence_level: str
    byzantine_tolerance: int

    @property
    def is_healthy(self) -> bool:
        return self.confidence_level in ("full", "high")

    @property
    def is_production_ready(self) -> bool:
        return self.confidence_level == "full"

def get_network_health() -> NetworkHealth:
    """
    Calculate current network health metrics.

    Called every finality window to assess network state.
    """
    # Implementation aggregates data from all known peers
    ...
```

---

## 7. Heartbeat Structure

### 7.1 Definition

A heartbeat is proof of temporal presence across all three layers.

```python
@dataclass
class Heartbeat:
    # Identity
    pubkey: PublicKey               # 33 bytes

    # Layer 0-1: Temporal Proof
    vdf_proof: VDFProof             # Variable (proves elapsed time)

    # Layer 2: Finality Reference
    finality_ref: FinalityReference # 48 bytes

    # Metadata
    sequence: int                   # u64 - Heartbeat sequence
    version: int                    # u8 - Protocol version

    # Signature
    signature: Signature            # 17,088 bytes (SPHINCS+)

    def heartbeat_id(self) -> Hash:
        return sha3_256(self.serialize_for_signing())
```

### 7.2 Heartbeat Validation

```python
def validate_heartbeat(hb: Heartbeat, state: GlobalState) -> bool:
    """
    Validate heartbeat across all layers.
    """
    # 1. Verify signature
    if not verify_sphincs(hb.pubkey, hb.serialize_for_signing(), hb.signature):
        return False

    # 2. Verify VDF proof (Layer 0-1)
    if not verify_stark_proof(hb.vdf_proof):
        return False

    # 3. Verify finality reference
    if hb.finality_ref.depth < state.min_finality_depth:
        return False

    if hb.finality_ref.vdf_root != state.get_vdf_root_at_depth(hb.finality_ref.depth):
        return False

    # 5. Cross-layer consistency
    if not hb.is_cross_layer_consistent():
        return False

    # 6. Sequence must increment
    account = state.get_account(hb.pubkey)
    if account and hb.sequence <= account.last_heartbeat_sequence:
        return False

    return True
```

---

## 8. Score System

### 8.1 Score Formula

```python
SCORE_PRECISION: int = 1_000_000
SCORE_MIN_HEARTBEATS: int = 1
ACTIVITY_WINDOW_BLOCKS: int = 2016       # ~2 weeks at 10 min blocks
INACTIVITY_PENALTY_RATE: float = 0.001

def compute_score(epoch_heartbeats: int) -> float:
    """
    Score = √(epoch_heartbeats)

    Provides:
    - Diminishing returns for more heartbeats
    - Sybil resistance (N identities = 1/√N efficiency)
    """
    if epoch_heartbeats < SCORE_MIN_HEARTBEATS:
        return 0.0
    return math.sqrt(epoch_heartbeats)

def effective_score(pubkey: PublicKey, state: GlobalState) -> float:
    """
    Effective Score = base_score × activity_multiplier
    """
    account = state.get_account(pubkey)
    if not account:
        return 0.0

    base = compute_score(account.epoch_heartbeats)
    multiplier = compute_activity_multiplier(
        account.last_heartbeat_height,
        state.chain_height
    )
    return base * multiplier

def compute_activity_multiplier(last_height: int, current_height: int) -> float:
    """
    Full multiplier if active within window.
    Decay for inactivity.
    """
    if last_height <= 0:
        return 0.0

    blocks_inactive = current_height - last_height

    if blocks_inactive <= ACTIVITY_WINDOW_BLOCKS:
        return 1.0

    decay = (blocks_inactive - ACTIVITY_WINDOW_BLOCKS) * INACTIVITY_PENALTY_RATE
    return max(0.1, 1.0 - decay)
```

### 8.2 Sybil Resistance Analysis

| Identities (N) | Time Each | Total Score | Efficiency |
|----------------|-----------|-------------|------------|
| 1 | T | √T | 100% |
| 4 | T/4 | 2√(T/4) = √T | 50% |
| 100 | T/100 | 10√(T/100) = √T | 10% |
| 10,000 | T/10,000 | 100√(T/10,000) = √T | 1% |

---

## 9. Block Structure

### 9.1 Block Header

```python
@dataclass
class BlockHeader:
    version: int                    # u8
    height: int                     # u64
    parent_hash: Hash               # 32 bytes
    timestamp_ms: int               # u64
    heartbeats_root: Hash           # 32 bytes (Merkle root)
    transactions_root: Hash         # 32 bytes (Merkle root)
    state_root: Hash                # 32 bytes
    finality_ref: FinalityReference # 48 bytes

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u8(self.version)
        writer.write_u64(self.height)
        writer.write_raw(self.parent_hash.data)
        writer.write_u64(self.timestamp_ms)
        writer.write_raw(self.heartbeats_root.data)
        writer.write_raw(self.transactions_root.data)
        writer.write_raw(self.state_root.data)
        writer.write_raw(self.finality_ref.serialize())
        return writer.to_bytes()
```

### 9.2 Block

```python
@dataclass
class Block:
    header: BlockHeader
    heartbeats: List[Heartbeat]
    transactions: List[Transaction]
    signers: List[BlockSigner]

    MAX_HEARTBEATS: int = 1000
    MAX_TRANSACTIONS: int = 5000
    MAX_SIZE_BYTES: int = 4_194_304  # 4 MB

    def block_hash(self) -> Hash:
        return sha3_256(self.header.serialize())
```

### 9.3 Block Signer

```python
@dataclass
class BlockSigner:
    pubkey: PublicKey
    score_fixed: int        # Score × SCORE_PRECISION
    signature: Signature

    def score(self) -> float:
        return self.score_fixed / SCORE_PRECISION
```

---

## 10. Block Production

### 10.1 DAG-PHANTOM

Montana uses DAG structure with PHANTOM ordering:

```python
# No leader selection - eligibility only
def is_eligible_producer(pubkey: PublicKey, state: GlobalState) -> bool:
    account = state.get_account(pubkey)
    if not account:
        return False

    # Minimum heartbeats requirement
    if account.epoch_heartbeats < SCORE_MIN_HEARTBEATS:
        return False

    # Activity requirement
    blocks_since = state.chain_height - account.last_heartbeat_height
    if blocks_since > ACTIVITY_WINDOW_BLOCKS * 2:
        return False

    return True

def verify_eligibility_vrf(
    pubkey: PublicKey,
    vrf_proof: bytes,
    block_seed: bytes
) -> bool:
    """
    ECVRF proves eligibility without revealing identity until block creation.
    """
    vrf_output = ecvrf_verify(pubkey, block_seed, vrf_proof)
    if not vrf_output:
        return False

    # Threshold based on score
    threshold = compute_eligibility_threshold(pubkey)
    return int.from_bytes(vrf_output[:8], 'big') < threshold
```

### 10.2 Block Time

```python
BLOCK_TIME_TARGET_SEC: int = 600         # 10 minutes
BLOCK_INTERVAL_MS: int = 600_000         # 10 minutes in ms
VDF_TX_CHECKPOINT_SEC: int = 1           # Soft finality every second
```

### 10.3 Transaction Ordering

Montana separates transaction ordering from block rewards:

```python
# Two-layer timing
VDF_TX_CHECKPOINT_INTERVAL: int = 1      # 1 second - soft finality
BLOCK_REWARD_INTERVAL: int = 600         # 10 minutes - reward distribution

# UTC-aligned blocks from genesis
GENESIS_TIMESTAMP_MS: int = 1704067200000  # 2024-01-01 00:00:00 UTC

def get_block_number(timestamp_ms: int) -> int:
    """Get block number for given timestamp."""
    return (timestamp_ms - GENESIS_TIMESTAMP_MS) // BLOCK_INTERVAL_MS

def get_block_start_time(block_number: int) -> int:
    """Get UTC start time for block N."""
    return GENESIS_TIMESTAMP_MS + (block_number * BLOCK_INTERVAL_MS)
```

**Transaction Flow:**

1. User submits transaction with `timestamp_ms`
2. Transaction enters mempool, propagates to network
3. VDF checkpoint every 1 second provides ordering
4. DAG-PHANTOM determines deterministic order across nodes
5. Accumulated VDF depth provides progressive finality

**No TPS ceiling** — network processes transactions as they arrive.

---

## 11. Block Reward Distribution

### 11.1 Three-Tier Lottery

```python
# Tier weights (tiers numbered 1, 2, 3)
TIER_1_WEIGHT: float = 0.70  # Full Node operators
TIER_2_WEIGHT: float = 0.20  # Light Node / TG Bot owners
TIER_3_WEIGHT: float = 0.10  # TG Community participants

@dataclass
class RewardCandidate:
    pubkey: PublicKey
    tier: int               # 1, 2, or 3
    score: float

def select_block_winner(
    candidates: List[RewardCandidate],
    vrf_seed: bytes
) -> RewardCandidate:
    """
    Two-stage weighted lottery:
    1. Select tier based on tier weights
    2. Within tier, select by score-weighted random
    """
    # Stage 1: Select tier
    tier_rand = int.from_bytes(sha3_256(vrf_seed + b"tier")[:8], 'big')
    tier_value = (tier_rand % 100) / 100.0

    if tier_value < TIER_1_WEIGHT:
        selected_tier = 1  # Full Node (70%)
    elif tier_value < TIER_1_WEIGHT + TIER_2_WEIGHT:
        selected_tier = 2  # Light Node / TG Bot (20%)
    else:
        selected_tier = 3  # TG Users (10%)

    # Stage 2: Filter to selected tier
    tier_candidates = [c for c in candidates if c.tier == selected_tier]
    if not tier_candidates:
        # Fallback to any tier
        tier_candidates = candidates

    # Stage 3: Score-weighted selection within tier
    total_score = sum(c.score for c in tier_candidates)
    if total_score == 0:
        return random.choice(tier_candidates)

    pick_rand = int.from_bytes(sha3_256(vrf_seed + b"pick")[:8], 'big')
    pick_value = (pick_rand % 1_000_000) / 1_000_000 * total_score

    cumulative = 0.0
    for candidate in tier_candidates:
        cumulative += candidate.score
        if cumulative >= pick_value:
            return candidate

    return tier_candidates[-1]
```

### 11.2 Reward Calculation

```python
def calculate_block_reward(height: int, fees: int) -> int:
    """
    Winner receives: block_reward + accumulated_fees
    """
    base_reward = get_block_reward(height)
    return base_reward + fees
```

---

## 12. Transaction Structure

### 12.1 Transaction

```python
@dataclass
class Transaction:
    version: int                    # u8
    sender: PublicKey               # 33 bytes
    receiver: PublicKey             # 33 bytes
    amount: int                     # u64

    # Layer 0
    timestamp_ms: int               # u64
    source_bitmap: int              # u8 (reserved)

    # Layer 2
    finality_depth: int             # u64 - Reference finality depth
    finality_root: bytes            # 32 bytes - VDF root at that depth

    # Anti-spam PoW
    pow_difficulty: int             # u8
    pow_nonce: bytes                # 8 bytes
    pow_hash: Hash                  # 32 bytes

    # Metadata
    nonce: int                      # u64
    epoch: int                      # u32
    memo: bytes                     # 256 bytes (zero-padded)
    memo_length: int                # u8

    # Privacy
    privacy_tier: int               # u8 (0-3)
    privacy_data: bytes             # Variable (stealth/ring/commitment)

    # Signature
    signature: Signature            # 17,089 bytes

    def transaction_id(self) -> Hash:
        return sha3_256(self.serialize_for_signing())
```

### 12.2 Transaction Types

```python
class TxType(IntEnum):
    STANDARD = 0            # Regular transfer
    COINBASE = 1            # Block reward
    PRIVACY_T1 = 2          # Hidden receiver
    PRIVACY_T2 = 3          # Hidden receiver + amount
    PRIVACY_T3 = 4          # Fully private
```

---

## 13. Transaction Fees

### 13.1 Free Tier

```python
TX_FREE_PER_SECOND: int = 1
TX_FREE_PER_EPOCH: int = 10
TX_EPOCH_DURATION_SEC: int = 600  # 10 minutes
```

### 13.2 Anti-Spam PoW

```python
POW_BASE_DIFFICULTY_BITS: int = 16       # ~65ms
POW_EXCESS_PENALTY_BITS: int = 2         # Per excess tx
POW_BURST_PENALTY_BITS: int = 4          # Per same-second tx
POW_MAX_DIFFICULTY_BITS: int = 32        # ~18 hours max
POW_MEMORY_COST_KB: int = 65536          # 64 MB Argon2id
POW_TIME_COST: int = 1
POW_PARALLELISM: int = 1

def compute_required_pow(
    sender: PublicKey,
    state: GlobalState,
    current_second: int
) -> int:
    """
    Calculate required PoW difficulty.
    """
    account = state.get_account(sender)
    if not account:
        return POW_BASE_DIFFICULTY_BITS

    # Count transactions this epoch
    epoch_tx = account.epoch_tx_count

    # Count transactions this second
    second_tx = 0
    if account.last_tx_second == current_second:
        second_tx = account.second_tx_count

    # Free tier
    if epoch_tx < TX_FREE_PER_EPOCH and second_tx < TX_FREE_PER_SECOND:
        return 0

    # Calculate difficulty
    excess = max(0, epoch_tx - TX_FREE_PER_EPOCH)
    burst = max(0, second_tx - TX_FREE_PER_SECOND)

    difficulty = POW_BASE_DIFFICULTY_BITS
    difficulty += excess * POW_EXCESS_PENALTY_BITS
    difficulty += burst * POW_BURST_PENALTY_BITS

    return min(difficulty, POW_MAX_DIFFICULTY_BITS)
```

### 13.3 Privacy Fee Multipliers

```python
PRIVACY_FEE_MULTIPLIERS = {
    0: 1,   # T0: Transparent
    1: 2,   # T1: Hidden receiver
    2: 5,   # T2: + Hidden amount
    3: 10,  # T3: + Hidden sender
}
```

---

## 14. Privacy Tiers

### 14.1 T0: Transparent

All fields visible. No additional cryptography.

### 14.2 T1: Stealth Addresses (Hidden Receiver)

```python
@dataclass
class StealthKeys:
    view_secret: bytes      # a
    spend_secret: bytes     # b
    view_public: bytes      # A = a*G
    spend_public: bytes     # B = b*G

def create_stealth_output(
    recipient_view_public: bytes,
    recipient_spend_public: bytes
) -> Tuple[bytes, bytes]:
    """
    Create one-time stealth address.

    1. Generate random r
    2. R = r*G (ephemeral public key)
    3. s = H(r*A) (shared secret)
    4. P = s*G + B (one-time address)
    """
    r = os.urandom(32)
    R = scalarmult_base(r)

    shared = scalarmult(r, recipient_view_public)
    s = sha3_256(shared)

    sG = scalarmult_base(s)
    P = point_add(sG, recipient_spend_public)

    return P, R  # One-time address, ephemeral key
```

### 14.3 T2: Pedersen Commitments (Hidden Amount)

**Quantum Note:** Pedersen commitment binding relies on discrete log, which is quantum-vulnerable (ATC L-1.3.4). However:
- **Hiding** is information-theoretic (Type A) — quantum-resistant
- Binding only matters for transaction validity, not past privacy
- Attackers cannot extract hidden values, only potentially forge new commitments
- **Upgrade path:** Lattice-based commitments when standardized

```python
# C = v*H + r*G
# Where H is second generator (nothing-up-my-sleeve)

H_GENERATOR = sha3_256(b"MONTANA_PEDERSEN_H_V1")

def pedersen_commit(value: int, blinding: bytes = None) -> Tuple[bytes, bytes]:
    """
    Create Pedersen commitment.
    Returns (commitment, blinding_factor).
    """
    if blinding is None:
        blinding = os.urandom(32)

    vH = scalarmult(int_to_scalar(value), H_GENERATOR)
    rG = scalarmult_base(blinding)
    C = point_add(vH, rG)

    return C, blinding

def verify_pedersen_sum(
    inputs: List[bytes],
    outputs: List[bytes],
    fee: int
) -> bool:
    """
    Verify: Σ(input_commitments) = Σ(output_commitments) + fee*H
    """
    sum_in = POINT_ZERO
    for c in inputs:
        sum_in = point_add(sum_in, c)

    sum_out = POINT_ZERO
    for c in outputs:
        sum_out = point_add(sum_out, c)

    fee_commitment = scalarmult(int_to_scalar(fee), H_GENERATOR)
    sum_out = point_add(sum_out, fee_commitment)

    return sum_in == sum_out
```

### 14.4 T3: Ring Signatures (Hidden Sender)

```python
RING_SIZE: int = 11

@dataclass
class LSAGSignature:
    key_image: bytes            # I = x * Hp(P)
    c0: bytes                   # Initial challenge
    responses: List[bytes]      # Response scalars

def lsag_sign(
    message: bytes,
    ring: List[bytes],          # Public keys
    secret_index: int,
    secret_key: bytes
) -> LSAGSignature:
    """
    Linkable Spontaneous Anonymous Group signature.
    """
    n = len(ring)
    assert n >= 2

    # Key image (for linkability)
    P = ring[secret_index]
    Hp = hash_to_point(P)
    I = scalarmult(secret_key, Hp)

    # Generate random scalars
    alpha = os.urandom(32)
    responses = [os.urandom(32) for _ in range(n)]

    # Compute challenges in ring
    L = [None] * n
    R = [None] * n

    L[secret_index] = scalarmult_base(alpha)
    R[secret_index] = scalarmult(alpha, Hp)

    c = [None] * n
    c[(secret_index + 1) % n] = challenge_hash(message, L[secret_index], R[secret_index])

    for i in range(secret_index + 1, secret_index + n):
        idx = i % n
        next_idx = (i + 1) % n

        L[idx] = point_add(
            scalarmult_base(responses[idx]),
            scalarmult(c[idx], ring[idx])
        )
        R[idx] = point_add(
            scalarmult(responses[idx], Hp),
            scalarmult(c[idx], I)
        )

        if next_idx != secret_index:
            c[next_idx] = challenge_hash(message, L[idx], R[idx])

    # Close the ring
    responses[secret_index] = scalar_sub(
        alpha,
        scalar_mul(c[secret_index], secret_key)
    )

    return LSAGSignature(
        key_image=I,
        c0=c[0],
        responses=responses
    )
```

---

## 15. Light Client Protocol

Montana supports multiple light client platforms for mass adoption. The protocol has **no dependency** on any specific platform — all platforms are interchangeable interfaces to the same network.

### 15.0 Platform Independence

```python
# Supported light client platforms
LIGHT_CLIENT_PLATFORMS = [
    "telegram",      # Initial implementation
    "discord",       # Planned
    "wechat",        # Planned
    "ios_app",       # App Store — Planned
    "android_app",   # Google Play — Planned
    "web_app",       # Browser — Planned
]

# All platforms use the same protocol
# Time passes equally for all — no platform provides advantage
```

**Design Principles:**
1. Platform-agnostic protocol
2. Equal conditions for all participants
3. Time as the only arbiter
4. Safe scaling (Tier 2+3 = 30% combined)

### 15.1 Light Client Registration

```python
@dataclass
class LightClientValidator:
    client_id: str              # Platform-specific client ID
    platform: str               # Platform identifier (telegram, discord, etc.)
    owner_pubkey: PublicKey     # Owner's Montana pubkey
    registered_height: int      # Block height at registration
    user_count: int             # Active users
    validation_count: int       # Total validations

class LightClientUser:
    user_id: str                # Platform-specific user ID
    client_id: str              # Which light client they use
    platform: str               # Platform identifier
    pubkey: PublicKey           # Montana pubkey
    frequency_seconds: int      # Validation frequency (60 - 86400)
    correct_answers: int
    total_answers: int
```

### 15.2 Time Verification Protocol

```python
@dataclass
class TimeChallenge:
    challenge_id: bytes         # Unique ID
    timestamp_ms: int           # When challenge was issued
    correct_time: str           # Correct answer (HH:MM)
    options: List[str]          # 5 shuffled options
    expires_at: int             # Challenge expiry

CHALLENGE_TIMEOUT_SEC: int = 60
TIME_VARIANCE_MINUTES: int = 2

def generate_time_challenge(device_time_ms: int) -> TimeChallenge:
    """
    Generate "What time is it, Chico?" challenge.
    """
    # Convert to HH:MM
    dt = datetime.fromtimestamp(device_time_ms / 1000)
    correct = dt.strftime("%H:%M")

    # Generate options: correct ± 1-2 minutes
    options = [correct]
    for delta in [-2, -1, 1, 2]:
        variant = (dt + timedelta(minutes=delta)).strftime("%H:%M")
        if variant not in options:
            options.append(variant)

    # Shuffle
    random.shuffle(options)

    return TimeChallenge(
        challenge_id=os.urandom(16),
        timestamp_ms=device_time_ms,
        correct_time=correct,
        options=options[:5],  # Exactly 5 options
        expires_at=int(time.time()) + CHALLENGE_TIMEOUT_SEC
    )

def verify_challenge_response(
    challenge: TimeChallenge,
    response: str,
    response_time: int
) -> bool:
    """
    Verify user's answer.
    """
    # Check expiry
    if response_time > challenge.expires_at:
        return False

    # Check answer
    return response == challenge.correct_time
```

### 15.3 Bot Messages

```python
# Challenge message
CHALLENGE_MESSAGE = """
🎬 *¿Qué hora es en tu reloj, Chico?*

_"What time is it on your clock, Chico?"_
— Tony Montana

Choose the correct time:
"""

# Success message
SUCCESS_MESSAGE = """
✅ *Correcto!*

Your validation has been recorded.
Current score: {score}
Next challenge in: {next_time}
"""

# Failure message
FAILURE_MESSAGE = """
❌ *Incorrecto.*

The correct time was: {correct}
Your answer: {answer}

Score penalty applied.
"""
```

---

## 16. Cryptographic Primitives

### 16.1 Hash Functions

```python
HASH_FUNCTION: str = "SHA3-256"

def sha3_256(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()

def shake_256(data: bytes, length: int = 32) -> bytes:
    return hashlib.shake_256(data).digest(length)
```

### 16.2 Signatures (SPHINCS+)

```python
SIGNATURE_SCHEME: str = "SPHINCS+-SHAKE-128f"
SPHINCS_PUBLIC_KEY_SIZE: int = 32
SPHINCS_SECRET_KEY_SIZE: int = 64
SPHINCS_SIGNATURE_SIZE: int = 17088

def sphincs_keygen() -> Tuple[bytes, bytes]:
    """Generate SPHINCS+ keypair."""
    return liboqs.sign.generate_keypair("SPHINCS+-SHAKE-128f-simple")

def sphincs_sign(message: bytes, secret_key: bytes) -> bytes:
    """Sign message with SPHINCS+."""
    return liboqs.sign.sign(message, secret_key)

def sphincs_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify SPHINCS+ signature."""
    return liboqs.sign.verify(message, signature, public_key)
```

### 16.3 Key Encapsulation (ML-KEM)

```python
KEY_ENCAPSULATION: str = "ML-KEM-768"

def mlkem_keygen() -> Tuple[bytes, bytes]:
    return liboqs.kem.generate_keypair("ML-KEM-768")

def mlkem_encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
    return liboqs.kem.encapsulate(public_key)

def mlkem_decapsulate(ciphertext: bytes, secret_key: bytes) -> bytes:
    return liboqs.kem.decapsulate(ciphertext, secret_key)
```

### 16.4 VRF (ECVRF)

**Quantum Status:** ECVRF is based on elliptic curve discrete log (DDH), which is BROKEN by Shor's algorithm. Montana uses ECVRF for block eligibility determination, which has short-term security requirements (current epoch only).

**Upgrade Path:** When cryptographically relevant quantum computers emerge, migrate to Lattice-VRF (ATC L-1.B) or Hash-VRF (ATC L-1.C). Protocol version field enables seamless transition.

```python
def ecvrf_prove(secret_key: bytes, input_data: bytes) -> bytes:
    """Generate VRF proof."""
    pass

def ecvrf_verify(public_key: bytes, input_data: bytes, proof: bytes) -> Optional[bytes]:
    """Verify VRF proof and return output."""
    pass
```

---

## 17. Network Protocol

### 17.1 Network Constants

```python
NETWORK_ID_MAINNET: int = 0x4D4F4E5441   # "MONTA"
NETWORK_ID_TESTNET: int = 0x544553544E   # "TESTN"
PROTOCOL_VERSION: int = 8
DEFAULT_PORT: int = 19656
MESSAGE_MAGIC_MAINNET: bytes = b"MONT"
MESSAGE_MAGIC_TESTNET: bytes = b"TEST"
```

### 17.2 Peer Connections

```python
MIN_OUTBOUND_CONNECTIONS: int = 8
MAX_INBOUND_CONNECTIONS: int = 125
```

### 17.3 Message Types

```python
class MessageType(IntEnum):
    HELLO = 0x01
    PING = 0x02
    PONG = 0x03
    GET_BLOCKS = 0x10
    BLOCKS = 0x11
    GET_HEARTBEATS = 0x12
    HEARTBEATS = 0x13
    NEW_BLOCK = 0x20
    NEW_HEARTBEAT = 0x21
    NEW_TRANSACTION = 0x22
    GET_VDF_STATE = 0x30
    VDF_STATE = 0x31
    GET_ADDR = 0x40
    ADDR = 0x41
    NOT_FOUND = 0x42
```

### 17.4 Peer Discovery

Montana uses a multi-layer peer discovery system.

#### 17.4.1 Bootstrap Nodes

```python
# Primary bootstrap node (Genesis infrastructure)
BOOTSTRAP_NODES = [
    BootstrapNode(
        name="montana-genesis-1",
        ip="176.124.208.93",
        port=19656,
        pubkey="GENESIS_NODE_PUBKEY_PLACEHOLDER",  # Set at mainnet launch
        region="EU",
        services=SERVICE_FULL_NODE | SERVICE_VDF,
    ),
]

# Service flags
SERVICE_FULL_NODE: int = 0x01      # Full timechain history
SERVICE_LIGHT_NODE: int = 0x02     # Light node
SERVICE_VDF: int = 0x04            # Computes VDF proofs
SERVICE_RELAY: int = 0x10          # Relays transactions

@dataclass
class BootstrapNode:
    name: str
    ip: str
    port: int
    pubkey: str
    region: str
    services: int
```

#### 17.4.2 DNS Seeds

```python
# DNS seeds for decentralized discovery (post-launch)
DNS_SEEDS = [
    "seed1.montana.network",
    "seed2.montana.network",
    "seed3.montana.network",
]

DNS_SEED_QUERY_TIMEOUT_SEC: int = 10
DNS_SEED_MAX_RESULTS: int = 256

def query_dns_seeds() -> List[PeerAddress]:
    """
    Query DNS seeds for peer addresses.
    Returns A/AAAA records as potential peers.
    """
    peers = []
    for seed in DNS_SEEDS:
        try:
            records = dns_resolve(seed, timeout=DNS_SEED_QUERY_TIMEOUT_SEC)
            for ip in records:
                peers.append(PeerAddress(
                    ip=ip,
                    port=DEFAULT_PORT,
                    services=SERVICE_FULL_NODE,
                    last_seen=0,  # Unknown
                ))
        except DNSError:
            continue
    return peers[:DNS_SEED_MAX_RESULTS]
```

#### 17.4.3 Peer Address Storage

```python
# Peer database configuration
PEER_DB_MAX_ADDRESSES: int = 5000
PEER_DB_MAX_NEW: int = 1000            # Unverified addresses
PEER_DB_MAX_TRIED: int = 4000          # Verified addresses
PEER_HORIZON_DAYS: int = 30            # Ignore older addresses

@dataclass
class PeerAddress:
    ip: str                             # IPv4 or IPv6
    port: int                           # u16
    services: int                       # Service flags
    last_seen: int                      # Unix timestamp
    last_try: int                       # Last connection attempt
    last_success: int                   # Last successful connection
    attempts: int                       # Failed attempts since success

    def is_valid(self) -> bool:
        """Check if address is valid for connection."""
        if self.attempts > 10:
            return False
        if time.time() - self.last_seen > PEER_HORIZON_DAYS * 86400:
            return False
        return True

# Peer storage schema (extends §25)
PEER_SCHEMA = """
CREATE TABLE peers (
    ip TEXT PRIMARY KEY,
    port INTEGER NOT NULL,
    services INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    last_try INTEGER DEFAULT 0,
    last_success INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    source TEXT,  -- 'dns', 'bootstrap', 'addr', 'incoming'

    INDEX idx_peers_last_seen (last_seen DESC)
);
"""
```

#### 17.4.4 Discovery Flow

```python
def discover_peers(state: NodeState) -> List[PeerAddress]:
    """
    Multi-stage peer discovery.

    1. Load cached peers from database
    2. Query DNS seeds if insufficient
    3. Fall back to bootstrap nodes
    4. Request addresses from connected peers
    """
    peers = []

    # Stage 1: Cached peers
    cached = state.db.get_recent_peers(limit=100)
    peers.extend(cached)

    # Stage 2: DNS seeds (if < MIN_OUTBOUND_CONNECTIONS peers)
    if len(peers) < MIN_OUTBOUND_CONNECTIONS:
        dns_peers = query_dns_seeds()
        peers.extend(dns_peers)

    # Stage 3: Bootstrap nodes (always include for initial sync)
    if state.chain_height == 0:
        for node in BOOTSTRAP_NODES:
            peers.append(PeerAddress(
                ip=node.ip,
                port=node.port,
                services=node.services,
                last_seen=int(time.time()),
            ))

    # Stage 4: Address relay from connected peers
    for peer in state.connected_peers:
        if peer.connection_time > 60:  # Connected > 1 min
            peer.send(Message(type=MessageType.GET_ADDR))

    return deduplicate_peers(peers)
```

### 17.5 Connection Handshake

#### 17.5.1 Hello Message

```python
@dataclass
class HelloMessage:
    """
    Initial handshake message. Sent by both sides.
    Contains Montana protocol version and node capabilities.
    """
    # Protocol
    protocol_version: int           # u8 — PROTOCOL_VERSION = 8
    network_id: int                 # u32 — NETWORK_ID_MAINNET

    # Node identity
    node_type: int                  # u8 — NodeType.FULL or NodeType.LIGHT
    services: int                   # u64 — Service flags bitmap
    user_agent: str                 # Variable — "Montana/1.0.0"

    # Timing
    timestamp_ms: int               # u64 — Local time in milliseconds

    # Chain state
    best_height: int                # u64 — Current chain height
    best_hash: Hash                 # 32 bytes — Best block hash

    # Montana-specific
    vdf_depth: int                  # u64 — Accumulated VDF depth
    tier: int                       # u8 — Participation tier (1, 2, 3)

    # Connection preferences
    relay: bool                     # Accept transaction relay
    listen_port: int                # u16 — Port for incoming (0 if not listening)

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u8(self.protocol_version)
        writer.write_u32(self.network_id)
        writer.write_u8(self.node_type)
        writer.write_u64(self.services)
        writer.write_var_string(self.user_agent)
        writer.write_u64(self.timestamp_ms)
        writer.write_u64(self.best_height)
        writer.write_raw(self.best_hash.data)
        writer.write_u64(self.vdf_depth)
        writer.write_u8(self.tier)
        writer.write_bool(self.relay)
        writer.write_u16(self.listen_port)
        return writer.to_bytes()

# Validation constants
HELLO_MAX_USER_AGENT_LENGTH: int = 256
HELLO_MAX_TIME_DRIFT_SEC: int = 7200    # 2 hours max drift
HELLO_MIN_PROTOCOL_VERSION: int = 8
```

#### 17.5.2 Hello Acknowledgment

```python
@dataclass
class HelloAckMessage:
    """
    Handshake acknowledgment. Confirms or rejects connection.
    """
    accepted: bool                  # Connection accepted
    reject_code: int                # 0 if accepted, error code otherwise
    reject_reason: str              # Human-readable reason (if rejected)

class RejectCode(IntEnum):
    NONE = 0
    PROTOCOL_VERSION = 1            # Incompatible protocol
    NETWORK_MISMATCH = 2            # Wrong network (mainnet/testnet)
    TIME_DRIFT = 3                  # Clock too far off
    BANNED = 4                      # Peer is banned
    TOO_MANY_CONNECTIONS = 5        # Connection limit reached
    DUPLICATE = 6                   # Already connected
```

#### 17.5.3 Handshake Flow

```python
HANDSHAKE_TIMEOUT_SEC: int = 30

async def perform_handshake(
    conn: Connection,
    local_state: NodeState,
    is_outbound: bool
) -> Tuple[bool, Optional[PeerInfo]]:
    """
    Complete connection handshake.

    Flow (both directions):
    1. Initiator sends HELLO
    2. Responder sends HELLO
    3. Both validate received HELLO
    4. Initiator sends HELLO_ACK
    5. Responder sends HELLO_ACK
    6. If both accepted → connected

    Returns (success, peer_info)
    """
    # Build our HELLO
    our_hello = HelloMessage(
        protocol_version=PROTOCOL_VERSION,
        network_id=NETWORK_ID_MAINNET,
        node_type=local_state.node_type,
        services=local_state.services,
        user_agent=f"Montana/{VERSION_STRING}",
        timestamp_ms=get_current_time_ms(),
        best_height=local_state.chain_height,
        best_hash=local_state.chain_tip_hash,
        vdf_depth=local_state.accumulated_vdf_depth,
        tier=local_state.participation_tier,
        relay=True,
        listen_port=local_state.listen_port if local_state.accepting else 0,
    )

    # Send HELLO
    conn.send(Message(type=MessageType.HELLO, payload=our_hello.serialize()))

    # Receive their HELLO
    their_hello_msg = await conn.recv(timeout=HANDSHAKE_TIMEOUT_SEC)
    if their_hello_msg.type != MessageType.HELLO:
        return False, None

    their_hello = HelloMessage.deserialize(their_hello_msg.payload)

    # Validate their HELLO
    reject_code, reject_reason = validate_hello(their_hello, local_state)

    # Send HELLO_ACK
    our_ack = HelloAckMessage(
        accepted=(reject_code == RejectCode.NONE),
        reject_code=reject_code,
        reject_reason=reject_reason,
    )
    conn.send(Message(type=MessageType.HELLO_ACK, payload=our_ack.serialize()))

    # Receive their HELLO_ACK
    their_ack_msg = await conn.recv(timeout=HANDSHAKE_TIMEOUT_SEC)
    if their_ack_msg.type != MessageType.HELLO_ACK:
        return False, None

    their_ack = HelloAckMessage.deserialize(their_ack_msg.payload)

    # Both must accept
    if not our_ack.accepted or not their_ack.accepted:
        return False, None

    # Build peer info
    peer_info = PeerInfo(
        address=conn.remote_address,
        services=their_hello.services,
        node_type=their_hello.node_type,
        best_height=their_hello.best_height,
        vdf_depth=their_hello.vdf_depth,
        user_agent=their_hello.user_agent,
        connected_at=int(time.time()),
        is_outbound=is_outbound,
    )

    return True, peer_info

def validate_hello(hello: HelloMessage, state: NodeState) -> Tuple[int, str]:
    """Validate incoming HELLO message."""

    # Protocol version
    if hello.protocol_version < HELLO_MIN_PROTOCOL_VERSION:
        return RejectCode.PROTOCOL_VERSION, f"Protocol {hello.protocol_version} < {HELLO_MIN_PROTOCOL_VERSION}"

    # Network
    if hello.network_id != NETWORK_ID_MAINNET:
        return RejectCode.NETWORK_MISMATCH, "Wrong network"

    # Time drift
    local_time = get_current_time_ms()
    drift_sec = abs(hello.timestamp_ms - local_time) / 1000
    if drift_sec > HELLO_MAX_TIME_DRIFT_SEC:
        return RejectCode.TIME_DRIFT, f"Time drift {drift_sec}s > {HELLO_MAX_TIME_DRIFT_SEC}s"

    # User agent length
    if len(hello.user_agent) > HELLO_MAX_USER_AGENT_LENGTH:
        return RejectCode.PROTOCOL_VERSION, "User agent too long"

    return RejectCode.NONE, ""
```

### 17.6 Message Format

#### 17.6.1 Message Header

```python
MESSAGE_HEADER_SIZE: int = 13  # 4 + 1 + 4 + 4 bytes

@dataclass
class MessageHeader:
    """
    Network message header.
    All messages are prefixed with this header.
    """
    magic: bytes                    # 4 bytes — Network magic
    command: int                    # 1 byte — MessageType enum
    payload_size: int               # 4 bytes — Payload length
    checksum: bytes                 # 4 bytes — SHA3-256(payload)[:4]

    def serialize(self) -> bytes:
        return (
            self.magic +
            bytes([self.command]) +
            self.payload_size.to_bytes(4, 'little') +
            self.checksum
        )

    @classmethod
    def deserialize(cls, data: bytes) -> 'MessageHeader':
        return cls(
            magic=data[0:4],
            command=data[4],
            payload_size=int.from_bytes(data[5:9], 'little'),
            checksum=data[9:13],
        )

def compute_checksum(payload: bytes) -> bytes:
    """Compute message checksum using SHA3-256."""
    return sha3_256(payload)[:4]
```

#### 17.6.2 Message Limits

```python
# Size limits
MAX_MESSAGE_SIZE: int = 4_194_304       # 4 MB (= MAX_BLOCK_SIZE)
MAX_INV_COUNT: int = 50000              # Max items in INV message
MAX_ADDR_COUNT: int = 1000              # Max addresses per ADDR message
MAX_HEADERS_COUNT: int = 2000           # Max headers per response
MAX_GETDATA_COUNT: int = 50000          # Max items in GETDATA

# Rate limits
MESSAGE_RATE_LIMIT_PER_SEC: int = 100   # Max messages per second
MESSAGE_RATE_WINDOW_SEC: int = 10       # Rate limit window
```

#### 17.6.3 Message Serialization

```python
@dataclass
class Message:
    type: MessageType
    payload: bytes

    def serialize(self, network_magic: bytes) -> bytes:
        """Serialize complete message with header."""
        header = MessageHeader(
            magic=network_magic,
            command=self.type,
            payload_size=len(self.payload),
            checksum=compute_checksum(self.payload),
        )
        return header.serialize() + self.payload

    @classmethod
    def deserialize(cls, header: MessageHeader, payload: bytes) -> 'Message':
        """Deserialize message from header and payload."""
        # Verify checksum
        expected = compute_checksum(payload)
        if header.checksum != expected:
            raise ChecksumError(f"Checksum mismatch")

        return cls(
            type=MessageType(header.command),
            payload=payload,
        )
```

### 17.7 Address Relay

#### 17.7.1 Address Messages

```python
@dataclass
class AddrMessage:
    """
    List of known peer addresses.
    Sent in response to GET_ADDR or proactively.
    """
    addresses: List[PeerAddress]    # Max MAX_ADDR_COUNT

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_var_int(len(self.addresses))
        for addr in self.addresses:
            writer.write_var_string(addr.ip)
            writer.write_u16(addr.port)
            writer.write_u64(addr.services)
            writer.write_u64(addr.last_seen)
        return writer.to_bytes()

# Address relay configuration
ADDR_RELAY_INTERVAL_SEC: int = 30       # Min interval between relays
ADDR_RELAY_MAX_PER_PEER: int = 10       # Max addresses per relay
ADDR_RELAY_PROBABILITY: float = 0.25    # Probability to relay to each peer
```

#### 17.7.2 Address Handling

```python
def handle_addr_message(
    msg: AddrMessage,
    from_peer: Peer,
    state: NodeState
) -> None:
    """
    Process received addresses.

    1. Validate addresses
    2. Store new addresses
    3. Optionally relay to other peers
    """
    now = int(time.time())
    new_addresses = []

    for addr in msg.addresses[:MAX_ADDR_COUNT]:
        # Skip invalid
        if not is_valid_address(addr.ip, addr.port):
            continue

        # Skip old addresses
        if now - addr.last_seen > PEER_HORIZON_DAYS * 86400:
            continue

        # Skip self
        if addr.ip == state.external_ip:
            continue

        # Store or update
        existing = state.db.get_peer(addr.ip)
        if existing is None or addr.last_seen > existing.last_seen:
            state.db.upsert_peer(addr)
            new_addresses.append(addr)

    # Relay new addresses to some peers
    if new_addresses:
        relay_addresses(new_addresses, exclude=from_peer, state=state)

def relay_addresses(
    addresses: List[PeerAddress],
    exclude: Optional[Peer],
    state: NodeState
) -> None:
    """Relay addresses to connected peers."""
    for peer in state.connected_peers:
        if peer == exclude:
            continue
        if random.random() > ADDR_RELAY_PROBABILITY:
            continue

        # Select subset to relay
        to_relay = random.sample(
            addresses,
            min(len(addresses), ADDR_RELAY_MAX_PER_PEER)
        )

        peer.send(Message(
            type=MessageType.ADDR,
            payload=AddrMessage(addresses=to_relay).serialize()
        ))
```

### 17.8 Inventory Protocol

#### 17.8.1 Inventory Types

```python
class InvType(IntEnum):
    """Types of inventory objects."""
    ERROR = 0
    TX = 1                          # Transaction
    BLOCK = 2                       # Block
    HEARTBEAT = 3                   # Heartbeat (Montana-specific)
    VDF_CHECKPOINT = 4              # VDF checkpoint (Montana-specific)

@dataclass
class Inventory:
    """Single inventory item."""
    type: InvType                   # u8
    hash: Hash                      # 32 bytes

    def serialize(self) -> bytes:
        return bytes([self.type]) + self.hash.data
```

#### 17.8.2 Inventory Messages

```python
@dataclass
class InvMessage:
    """Announce available inventory."""
    items: List[Inventory]          # Max MAX_INV_COUNT

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_var_int(len(self.items))
        for inv in self.items:
            writer.write_raw(inv.serialize())
        return writer.to_bytes()

@dataclass
class GetDataMessage:
    """Request inventory data."""
    items: List[Inventory]          # Max MAX_GETDATA_COUNT

@dataclass
class NotFoundMessage:
    """Indicate requested items not found."""
    items: List[Inventory]
```

#### 17.8.3 Inventory Handling

```python
# Track what inventory each peer knows about
class PeerInventory:
    known_tx: Set[Hash]             # Transactions peer has
    known_blocks: Set[Hash]         # Blocks peer has
    known_heartbeats: Set[Hash]     # Heartbeats peer has

    # Pending requests
    requested: Dict[Hash, int]      # hash -> request_time

    REQUEST_TIMEOUT_SEC: int = 60

def handle_inv_message(
    msg: InvMessage,
    from_peer: Peer,
    state: NodeState
) -> None:
    """
    Process inventory announcement.
    Request items we don't have.
    """
    to_request = []

    for inv in msg.items:
        # Skip if we have it
        if state.has_inventory(inv):
            from_peer.inventory.add_known(inv)
            continue

        # Skip if already requested from another peer
        if state.is_requested(inv.hash):
            continue

        to_request.append(inv)

    if to_request:
        # Request data
        from_peer.send(Message(
            type=MessageType.GET_DATA,
            payload=GetDataMessage(items=to_request).serialize()
        ))

        # Mark as requested
        for inv in to_request:
            state.mark_requested(inv.hash, from_peer)
```

### 17.9 Block Relay

#### 17.9.1 Block Messages

```python
@dataclass
class GetBlocksMessage:
    """Request block hashes starting from locator."""
    locator_hashes: List[Hash]      # Block locator (exponential backoff)
    stop_hash: Hash                 # Stop at this hash (or zero for tip)

@dataclass
class BlocksMessage:
    """Response with block data."""
    blocks: List[Block]             # Max IBD_BATCH_SIZE

@dataclass
class GetHeadersMessage:
    """Request block headers."""
    locator_hashes: List[Hash]
    stop_hash: Hash

@dataclass
class HeadersMessage:
    """Response with block headers."""
    headers: List[BlockHeader]      # Max MAX_HEADERS_COUNT
```

#### 17.9.2 Block Locator

```python
def build_block_locator(tip: BlockHeader, state: NodeState) -> List[Hash]:
    """
    Build block locator with exponential backoff.

    Returns hashes at heights: tip, tip-1, tip-2, tip-3, tip-5, tip-9, ...
    Plus genesis block.
    """
    locator = []
    height = tip.height
    step = 1

    while height >= 0:
        block_hash = state.get_block_hash_at_height(height)
        if block_hash:
            locator.append(block_hash)

        if len(locator) >= 10:
            step *= 2

        height -= step

    # Always include genesis
    if locator[-1] != GENESIS_BLOCK_HASH:
        locator.append(GENESIS_BLOCK_HASH)

    return locator
```

#### 17.9.3 Orphan Block Management

```python
ORPHAN_MAX_COUNT: int = 100
ORPHAN_EXPIRY_SEC: int = 3600           # 1 hour

@dataclass
class OrphanBlock:
    block: Block
    received_at: int
    from_peer: PeerId

class OrphanManager:
    """Manage blocks whose parent we don't have yet."""

    orphans: Dict[Hash, OrphanBlock]            # block_hash -> orphan
    by_parent: Dict[Hash, Set[Hash]]            # parent_hash -> orphan hashes

    def add_orphan(self, block: Block, peer: PeerId) -> bool:
        """
        Add orphan block.
        Returns False if orphan limit reached.
        """
        block_hash = block.block_hash()
        parent_hash = block.header.parent_hash

        # Check limits
        if len(self.orphans) >= ORPHAN_MAX_COUNT:
            self.prune_oldest()

        if block_hash in self.orphans:
            return False  # Already have it

        # Store orphan
        self.orphans[block_hash] = OrphanBlock(
            block=block,
            received_at=int(time.time()),
            from_peer=peer,
        )

        # Index by parent
        if parent_hash not in self.by_parent:
            self.by_parent[parent_hash] = set()
        self.by_parent[parent_hash].add(block_hash)

        return True

    def get_children(self, parent_hash: Hash) -> List[Block]:
        """
        Get all orphans waiting for this parent.
        Called when parent block is received.
        """
        if parent_hash not in self.by_parent:
            return []

        children = []
        for block_hash in self.by_parent[parent_hash]:
            if block_hash in self.orphans:
                children.append(self.orphans[block_hash].block)
                del self.orphans[block_hash]

        del self.by_parent[parent_hash]
        return children

    def prune_expired(self) -> int:
        """Remove expired orphans."""
        cutoff = int(time.time()) - ORPHAN_EXPIRY_SEC
        expired = [h for h, o in self.orphans.items()
                   if o.received_at < cutoff]

        for block_hash in expired:
            orphan = self.orphans[block_hash]
            parent_hash = orphan.block.header.parent_hash

            del self.orphans[block_hash]
            if parent_hash in self.by_parent:
                self.by_parent[parent_hash].discard(block_hash)

        return len(expired)

    def prune_oldest(self) -> None:
        """Remove oldest orphan to make room."""
        if not self.orphans:
            return

        oldest_hash = min(self.orphans.keys(),
                         key=lambda h: self.orphans[h].received_at)

        orphan = self.orphans[oldest_hash]
        parent_hash = orphan.block.header.parent_hash

        del self.orphans[oldest_hash]
        if parent_hash in self.by_parent:
            self.by_parent[parent_hash].discard(oldest_hash)
```

### 17.10 Ban System

#### 17.10.1 Misbehavior Scoring

```python
MISBEHAVIOR_THRESHOLD: int = 100        # Ban at this score
BAN_DURATION_SEC: int = 86400           # 24 hours default
BAN_DURATION_PERMANENT: int = -1        # Permanent ban

# Penalty values for different violations
class Penalty(IntEnum):
    # Protocol violations
    INVALID_MESSAGE = 10
    UNKNOWN_MESSAGE = 1
    OVERSIZED_MESSAGE = 20

    # Block violations
    INVALID_BLOCK_HEADER = 20
    INVALID_BLOCK_FULL = 100            # Immediate ban
    INVALID_POW = 100                   # Immediate ban (N/A for VDF)
    INVALID_VDF = 100                   # Immediate ban

    # Transaction violations
    INVALID_TRANSACTION = 10
    DOUBLE_SPEND_ATTEMPT = 50

    # Heartbeat violations
    INVALID_HEARTBEAT = 20
    INVALID_TIMESTAMP = 30

    # DoS attempts
    ADDR_FLOOD = 20
    INV_FLOOD = 20
    GETDATA_FLOOD = 30
    CONNECTION_FLOOD = 50
```

#### 17.10.2 Ban Manager

```python
@dataclass
class BanEntry:
    address: str                        # IP address or CIDR
    banned_until: int                   # Unix timestamp (-1 = permanent)
    reason: str
    created_at: int

class BanManager:
    """Manage peer bans and misbehavior scores."""

    bans: Dict[str, BanEntry]           # address -> ban entry
    scores: Dict[str, int]              # peer_id -> misbehavior score

    def misbehaving(
        self,
        peer: Peer,
        penalty: int,
        reason: str
    ) -> bool:
        """
        Record misbehavior. Returns True if peer is now banned.
        """
        peer_id = peer.id
        current = self.scores.get(peer_id, 0)
        new_score = current + penalty
        self.scores[peer_id] = new_score

        log.warning(f"Peer {peer.address} misbehaving: {reason} "
                    f"(+{penalty}, total={new_score})")

        if new_score >= MISBEHAVIOR_THRESHOLD:
            self.ban(peer.address, BAN_DURATION_SEC, reason)
            return True

        return False

    def ban(
        self,
        address: str,
        duration: int,
        reason: str
    ) -> None:
        """Ban an address."""
        now = int(time.time())
        banned_until = -1 if duration == BAN_DURATION_PERMANENT else now + duration

        self.bans[address] = BanEntry(
            address=address,
            banned_until=banned_until,
            reason=reason,
            created_at=now,
        )

        log.info(f"Banned {address} until {banned_until}: {reason}")

    def is_banned(self, address: str) -> bool:
        """Check if address is banned."""
        if address not in self.bans:
            return False

        entry = self.bans[address]

        # Permanent ban
        if entry.banned_until == -1:
            return True

        # Check expiry
        if int(time.time()) >= entry.banned_until:
            del self.bans[address]
            return False

        return True

    def unban(self, address: str) -> bool:
        """Remove ban. Returns True if was banned."""
        if address in self.bans:
            del self.bans[address]
            return True
        return False

    def clear_score(self, peer_id: str) -> None:
        """Clear misbehavior score for peer."""
        if peer_id in self.scores:
            del self.scores[peer_id]

# Ban storage schema (extends §25)
BAN_SCHEMA = """
CREATE TABLE bans (
    address TEXT PRIMARY KEY,
    banned_until INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
"""
```

### 17.11 Connection Management

#### 17.11.1 Connection State

```python
class ConnectionState(IntEnum):
    CONNECTING = 1                      # TCP connecting
    HANDSHAKING = 2                     # Exchanging HELLO
    CONNECTED = 3                       # Fully connected
    DISCONNECTING = 4                   # Graceful disconnect

@dataclass
class PeerInfo:
    """Information about connected peer."""
    address: str
    port: int
    services: int
    node_type: int
    best_height: int
    vdf_depth: int
    user_agent: str
    connected_at: int
    is_outbound: bool

    # Runtime stats
    bytes_sent: int = 0
    bytes_recv: int = 0
    messages_sent: int = 0
    messages_recv: int = 0
    last_send: int = 0
    last_recv: int = 0
    ping_time_ms: int = 0
```

#### 17.11.2 Ping/Pong Keepalive

```python
PING_INTERVAL_SEC: int = 120            # Send ping every 2 minutes
PING_TIMEOUT_SEC: int = 20              # Disconnect if no pong

@dataclass
class PingMessage:
    nonce: int                          # u64 random nonce

@dataclass
class PongMessage:
    nonce: int                          # u64 echo back nonce

class PingManager:
    """Manage ping/pong for connection liveness."""

    pending_pings: Dict[str, Tuple[int, int]]  # peer_id -> (nonce, send_time)

    async def ping_loop(self, peer: Peer) -> None:
        """Background ping loop for a peer."""
        while peer.state == ConnectionState.CONNECTED:
            await asyncio.sleep(PING_INTERVAL_SEC)

            # Send ping
            nonce = random.getrandbits(64)
            send_time = int(time.time() * 1000)
            self.pending_pings[peer.id] = (nonce, send_time)

            peer.send(Message(
                type=MessageType.PING,
                payload=PingMessage(nonce=nonce).serialize()
            ))

            # Wait for pong
            await asyncio.sleep(PING_TIMEOUT_SEC)

            if peer.id in self.pending_pings:
                # No pong received
                log.warning(f"Peer {peer.address} ping timeout")
                peer.disconnect("ping timeout")

    def handle_pong(self, peer: Peer, msg: PongMessage) -> None:
        """Handle pong response."""
        if peer.id not in self.pending_pings:
            return

        expected_nonce, send_time = self.pending_pings[peer.id]

        if msg.nonce != expected_nonce:
            peer.misbehaving(Penalty.INVALID_MESSAGE, "wrong pong nonce")
            return

        # Calculate ping time
        ping_time = int(time.time() * 1000) - send_time
        peer.info.ping_time_ms = ping_time

        del self.pending_pings[peer.id]
```

#### 17.11.3 Outbound Peer Selection

```python
def select_outbound_peers(
    known: List[PeerAddress],
    connected: Set[str],
    banned: BanManager,
    target_count: int = MIN_OUTBOUND_CONNECTIONS
) -> List[PeerAddress]:
    """
    Select peers for outbound connections.

    Strategy:
    1. Prefer recently seen peers
    2. Diversify by /16 subnet (IPv4) or /32 (IPv6)
    3. Prefer peers with services we need
    4. Avoid already connected or banned
    """
    # Filter candidates
    candidates = []
    for addr in known:
        if addr.ip in connected:
            continue
        if banned.is_banned(addr.ip):
            continue
        if not addr.is_valid():
            continue
        candidates.append(addr)

    if not candidates:
        return []

    # Group by subnet
    by_subnet: Dict[str, List[PeerAddress]] = {}
    for addr in candidates:
        subnet = get_subnet(addr.ip)
        if subnet not in by_subnet:
            by_subnet[subnet] = []
        by_subnet[subnet].append(addr)

    # Select one from each subnet, preferring recent
    selected = []
    subnets = list(by_subnet.keys())
    random.shuffle(subnets)

    for subnet in subnets:
        if len(selected) >= target_count:
            break

        # Pick most recently seen from this subnet
        peers = sorted(by_subnet[subnet],
                      key=lambda p: p.last_seen, reverse=True)
        selected.append(peers[0])

    return selected

def get_subnet(ip: str) -> str:
    """Get /16 subnet for IPv4, /32 for IPv6."""
    if ':' in ip:  # IPv6
        parts = ip.split(':')
        return ':'.join(parts[:2])
    else:  # IPv4
        parts = ip.split('.')
        return '.'.join(parts[:2])
```

#### 17.11.4 Connection Limits

```python
# Connection limits
MIN_OUTBOUND_CONNECTIONS: int = 8
MAX_OUTBOUND_CONNECTIONS: int = 12
MAX_INBOUND_CONNECTIONS: int = 125
MAX_TOTAL_CONNECTIONS: int = MAX_OUTBOUND_CONNECTIONS + MAX_INBOUND_CONNECTIONS

# Per-subnet limits (prevent Sybil)
MAX_CONNECTIONS_PER_SUBNET: int = 2

# Feeler connections (for address discovery)
FEELER_INTERVAL_SEC: int = 120
FEELER_TIMEOUT_SEC: int = 5

class ConnectionManager:
    """Manage peer connections."""

    outbound: Dict[str, Peer]
    inbound: Dict[str, Peer]

    def can_accept_inbound(self, address: str) -> bool:
        """Check if we can accept new inbound connection."""
        if len(self.inbound) >= MAX_INBOUND_CONNECTIONS:
            return False

        # Check per-subnet limit
        subnet = get_subnet(address)
        subnet_count = sum(1 for p in self.inbound.values()
                         if get_subnet(p.address) == subnet)
        if subnet_count >= MAX_CONNECTIONS_PER_SUBNET:
            return False

        return True

    def need_outbound(self) -> int:
        """Return number of outbound connections needed."""
        return max(0, MIN_OUTBOUND_CONNECTIONS - len(self.outbound))
```

---

## 18. Governance

### 18.1 MIP Process

```python
class MIPStatus(IntEnum):
    DRAFT = 0
    PROPOSED = 1
    SIGNALING = 2
    LOCKED_IN = 3
    ACTIVE = 4
    REJECTED = 5
    WITHDRAWN = 6
```

### 18.2 Activation Parameters

```python
SOFT_FORK_THRESHOLD: float = 0.95
HARD_FORK_THRESHOLD: float = 0.95
ACTIVATION_WINDOW_BLOCKS: int = 2016     # ~2 weeks at 10 min blocks
TIMEOUT_EPOCHS: int = 2
```

### 18.3 Version Signaling

```python
# Heartbeat version field structure:
# Bits 0-7:   Protocol version
# Bits 8-15:  Reserved
# Bits 16-31: MIP signaling bits

def signal_mip_support(heartbeat: Heartbeat, mip_number: int) -> None:
    """Set MIP support bit in heartbeat version."""
    bit_position = 16 + (mip_number % 16)
    heartbeat.version |= (1 << bit_position)
```

---

## 19. Constants Reference

```python
# ==============================================================================
# Ɉ MONTANA — MECHANISM FOR ASYMPTOTIC TRUST IN TIME VALUE
# ==============================================================================
PROJECT = "Ɉ Montana"
SYMBOL = "Ɉ"
TICKER = "$MONT"
DEFINITION = "lim(evidence → ∞) 1 Ɉ → 1 second"
TYPE = "Temporal Time Unit"
TOTAL_SUPPLY = 1_260_000_000
INITIAL_DISTRIBUTION = 3000
HALVING_INTERVAL = 210_000
TOTAL_BLOCKS = 6_930_000
TOTAL_ERAS = 33

# ==============================================================================
# NODE TYPES (2 types only)
# ==============================================================================
NODE_TYPE_FULL = 1              # Full Node: Full history + VDF
NODE_TYPE_LIGHT = 2             # Light Node: History from connection only
NODE_TYPES_TOTAL = 2            # Exactly 2 node types in protocol

# ==============================================================================
# PARTICIPATION TIERS (3 tiers only, numbered 1-2-3)
# ==============================================================================
TIER_1 = 1                      # Full Node operators
TIER_2 = 2                      # Light Node operators OR TG Bot/Channel owners
TIER_3 = 3                      # TG Community participants
TIERS_TOTAL = 3                 # Exactly 3 tiers in protocol

# Lottery probability by tier
TIER_1_WEIGHT = 0.70            # 70% → Full Node
TIER_2_WEIGHT = 0.20            # 20% → Light Node / TG Bot owners
TIER_3_WEIGHT = 0.10            # 10% → TG Community users

# Summary:
# Tier 1 (Full Node):  70%
# Tier 2 (Light Node): 20%
# Tier 3 (TG Users):   10%

# ==============================================================================
# LAYER 0-1: VDF (CLASS GROUP, WESOLOWSKI 2019)
# ==============================================================================
VDF_TYPE = "class_group"              # Wesolowski construction
VDF_DISCRIMINANT_BITS = 2048          # Security parameter for Δ
VDF_BASE_ITERATIONS = 16777216        # 2^24 sequential squarings
VDF_CHALLENGE_BITS = 128              # Wesolowski challenge size

# ==============================================================================
# LAYER 2: ACCUMULATED FINALITY
# ==============================================================================
VDF_CHECKPOINT_TIME_SEC = 2.5
FINALITY_SOFT_CHECKPOINTS = 1
FINALITY_MEDIUM_CHECKPOINTS = 100
FINALITY_HARD_CHECKPOINTS = 1000

# ==============================================================================
# SCORE
# ==============================================================================
SCORE_PRECISION = 1_000_000
SCORE_MIN_HEARTBEATS = 1
ACTIVITY_WINDOW_BLOCKS = 2016
INACTIVITY_PENALTY_RATE = 0.001

# ==============================================================================
# BLOCK REWARDS
# ==============================================================================
TIER_0_WEIGHT = 0.70
TIER_1_WEIGHT = 0.20
TIER_2_WEIGHT = 0.10

# ==============================================================================
# TRANSACTIONS
# ==============================================================================
TX_FREE_PER_SECOND = 1
TX_FREE_PER_EPOCH = 10
TX_EPOCH_DURATION_SEC = 600
POW_BASE_DIFFICULTY_BITS = 16
POW_MEMORY_COST_KB = 65536

# ==============================================================================
# PRIVACY
# ==============================================================================
RING_SIZE = 11
PRIVACY_FEE_T0 = 1
PRIVACY_FEE_T1 = 2
PRIVACY_FEE_T2 = 5
PRIVACY_FEE_T3 = 10

# ==============================================================================
# NETWORK
# ==============================================================================
PROTOCOL_VERSION = 8
DEFAULT_PORT = 19656
MAX_BLOCK_SIZE = 4_194_304
BLOCK_TIME_TARGET_SEC = 600
VDF_TX_CHECKPOINT_SEC = 1

# ==============================================================================
# CRYPTOGRAPHY
# ==============================================================================
SPHINCS_SIGNATURE_SIZE = 17088
SHA3_256_OUTPUT_SIZE = 32

# ==============================================================================
# GOVERNANCE
# ==============================================================================
SOFT_FORK_THRESHOLD = 0.95
ACTIVATION_WINDOW_BLOCKS = 2016
```

---

## 20. API Reference

### 20.1 RPC Methods

```python
# Node information
getinfo() -> dict
gettimechaininfo() -> dict
getnetworkinfo() -> dict

# Blocks
getblock(hash: str) -> Block
getblockheader(hash: str) -> BlockHeader
getblockhash(height: int) -> str
getbestblockhash() -> str

# Heartbeats
getheartbeat(id: str) -> Heartbeat
submitheartbeat(heartbeat: Heartbeat) -> str

# Transactions
gettransaction(txid: str) -> Transaction
sendtransaction(tx: Transaction) -> str
getmempool() -> List[str]

# Accounts
getaccount(pubkey: str) -> AccountState
getbalance(pubkey: str) -> int
getscore(pubkey: str) -> float

# Finality
getfinalitydepth() -> int
getvdfstate() -> VDFState
getfinalityreference(depth: int) -> FinalityReference

# Bot
registerbot(bot_id: str, owner_pubkey: str) -> bool
submitvalidation(user_id: str, challenge_id: str, response: str) -> bool
```

### 20.2 WebSocket Events

```python
# Subscribe to events
subscribe("new_block")
subscribe("new_heartbeat")
subscribe("new_transaction")
subscribe("finality_update")

# Event payloads
NewBlockEvent {
    hash: str
    height: int
    timestamp: int
    finality_depth: int
}

NewHeartbeatEvent {
    id: str
    pubkey: str
    sequence: int
}

FinalityUpdateEvent {
    depth: int
    vdf_root: str
    timestamp: int
}
```

---

## 21. Account State

### 21.1 Account Structure

```python
@dataclass
class AccountState:
    """Per-account state tracking."""
    pubkey: PublicKey               # 33 bytes - Account identity
    balance: int                    # u64 - Current balance in Ɉ (seconds)
    nonce: int                      # u64 - Transaction nonce (anti-replay)

    # Heartbeat tracking
    epoch_heartbeats: int           # u32 - Heartbeats in current epoch
    total_heartbeats: int           # u64 - Lifetime heartbeats
    last_heartbeat_height: int      # u64 - Block height of last heartbeat
    last_heartbeat_sequence: int    # u64 - Sequence of last heartbeat
    first_seen_height: int          # u64 - When account was created

    # Participation tier
    tier: int                       # u8 - 0=node, 1=bot_validator, 2=bot_user

    # Transaction tracking
    epoch_tx_count: int             # u32 - Transactions this epoch
    last_tx_second: int             # u64 - Last transaction timestamp (seconds)
    second_tx_count: int            # u8 - Transactions in current second

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_raw(self.pubkey.serialize())
        writer.write_u64(self.balance)
        writer.write_u64(self.nonce)
        writer.write_u32(self.epoch_heartbeats)
        writer.write_u64(self.total_heartbeats)
        writer.write_u64(self.last_heartbeat_height)
        writer.write_u64(self.last_heartbeat_sequence)
        writer.write_u64(self.first_seen_height)
        writer.write_u8(self.tier)
        writer.write_u32(self.epoch_tx_count)
        writer.write_u64(self.last_tx_second)
        writer.write_u8(self.second_tx_count)
        return writer.to_bytes()
```

### 21.2 Global State

```python
@dataclass
class GlobalState:
    """Network-wide state."""
    chain_height: int               # Current block height
    chain_tip_hash: Hash            # Current chain tip

    # Finality state
    accumulated_vdf_depth: int      # Total VDF checkpoints
    vdf_root: Hash                  # Current VDF chain tip
    min_finality_depth: int         # Minimum required finality

    # Supply tracking
    total_supply: int               # Total minted supply
    circulating_supply: int         # Circulating (minus burned)

    # Network stats
    total_heartbeats: int           # Total heartbeats ever
    active_accounts: int            # Accounts with activity this epoch

    # Account index
    accounts: Dict[PublicKey, AccountState]

    def get_account(self, pubkey: PublicKey) -> Optional[AccountState]:
        return self.accounts.get(pubkey)

    def get_all_pubkeys(self) -> List[PublicKey]:
        return list(self.accounts.keys())

    def get_vdf_root_at_depth(self, depth: int) -> Optional[Hash]:
        """Get VDF root at specific depth for validation."""
        pass
```

---

## 22. Wallet (PLUTUS)

### 22.1 Key Derivation

```python
# HD-like key derivation from seed
def derive_master_keys(seed: bytes) -> Tuple[bytes, bytes]:
    """
    Derive master view and spend keys from 256-bit seed.

    Returns (view_secret, spend_secret)
    """
    view_data = hmac_sha3_256(b"montana_view_key", seed)
    spend_data = hmac_sha3_256(b"montana_spend_key", seed)

    view_secret = scalar_reduce(view_data)
    spend_secret = scalar_reduce(spend_data)

    return view_secret, spend_secret

def derive_subaddress(
    view_secret: bytes,
    spend_secret: bytes,
    major: int,      # Account index
    minor: int       # Address index
) -> Tuple[bytes, bytes]:
    """
    Derive subaddress keys for account hierarchy.

    Returns (subaddress_view_public, subaddress_spend_public)
    """
    data = b"SubAddr" + view_secret + struct.pack('<II', major, minor)
    m = scalar_reduce(sha3_256(data))

    spend_public = scalarmult_base(spend_secret)
    m_point = scalarmult_base(m)

    sub_spend = point_add(spend_public, m_point)
    sub_view = scalarmult(view_secret, sub_spend)

    return sub_view, sub_spend
```

### 22.2 Wallet Encryption

```python
# Wallet encryption parameters
ARGON2_TIME_COST: int = 3
ARGON2_MEMORY_COST: int = 65536      # 64 MB
ARGON2_PARALLELISM: int = 4
ARGON2_HASH_LEN: int = 32

AES_KEY_SIZE: int = 32               # AES-256
AES_NONCE_SIZE: int = 12             # GCM nonce
AES_TAG_SIZE: int = 16               # GCM auth tag

MIN_PASSWORD_LENGTH: int = 8

def derive_encryption_key(password: str, salt: bytes) -> bytes:
    """
    Derive encryption key using Argon2id.

    Argon2id provides:
    - Memory-hard: Resistant to GPU/ASIC attacks
    - Time-hard: Adjustable computation time
    - Hybrid: Combines Argon2i and Argon2d benefits
    """
    return argon2id(
        password=password.encode('utf-8'),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN
    )

def encrypt_wallet(plaintext: bytes, password: str) -> bytes:
    """
    Encrypt wallet data with AES-256-GCM.

    Format: version (1) || salt (32) || nonce (12) || ciphertext || tag (16)
    """
    salt = os.urandom(32)
    nonce = os.urandom(AES_NONCE_SIZE)
    key = derive_encryption_key(password, salt)

    ciphertext, tag = aes_gcm_encrypt(key, nonce, plaintext)

    return bytes([WALLET_VERSION]) + salt + nonce + ciphertext + tag

def decrypt_wallet(encrypted: bytes, password: str) -> bytes:
    """Decrypt wallet data."""
    version = encrypted[0]
    salt = encrypted[1:33]
    nonce = encrypted[33:45]
    ciphertext_and_tag = encrypted[45:]

    key = derive_encryption_key(password, salt)
    return aes_gcm_decrypt(key, nonce, ciphertext_and_tag)
```

### 22.3 Wallet Structure

```python
WALLET_VERSION: int = 1

@dataclass
class Wallet:
    """Montana wallet."""
    # Master keys
    seed: bytes                     # 32 bytes - BIP39-style seed
    view_secret: bytes              # 32 bytes
    view_public: bytes              # 33 bytes
    spend_secret: bytes             # 32 bytes
    spend_public: bytes             # 33 bytes

    # Subaddresses: (major, minor) -> (view_pub, spend_pub)
    subaddresses: Dict[Tuple[int, int], Tuple[bytes, bytes]]

    # Tracked outputs
    outputs: Dict[bytes, WalletOutput]
    key_images: Set[bytes]

    # State
    synced_height: int

    def get_balance(self) -> Tuple[int, int]:
        """Returns (confirmed, pending) balance."""
        confirmed = sum(o.amount for o in self.outputs.values()
                       if o.status == OutputStatus.UNSPENT)
        pending = sum(o.amount for o in self.outputs.values()
                     if o.status == OutputStatus.PENDING)
        return confirmed, pending

    def get_primary_address(self) -> bytes:
        """Get main address (account 0, index 0)."""
        return self.view_public + self.spend_public

@dataclass
class WalletOutput:
    """Tracked wallet output."""
    txid: bytes                     # 32 bytes
    output_index: int               # u32
    amount: int                     # u64
    stealth_address: bytes          # 33 bytes
    tx_public_key: bytes            # 33 bytes
    one_time_secret: bytes          # 32 bytes (derived)
    key_image: bytes                # 32 bytes (for spending)
    status: OutputStatus            # UNSPENT, PENDING, SPENT
    block_height: int               # u64
    timestamp: int                  # u64

class OutputStatus(IntEnum):
    UNSPENT = 0
    PENDING = 1      # In mempool
    SPENT = 2
    LOCKED = 3       # Coinbase maturity
```

### 22.4 Output Scanning

```python
def scan_transaction(
    tx: Transaction,
    view_secret: bytes,
    spend_public: bytes
) -> List[WalletOutput]:
    """
    Scan transaction for outputs belonging to wallet.

    For each output:
    1. Compute shared secret: s = Hs(view_secret * tx_public_key)
    2. Derive expected address: P' = s*G + spend_public
    3. Compare with output address
    """
    found = []

    for i, output in enumerate(tx.outputs):
        # Compute shared secret
        shared = scalarmult(view_secret, output.tx_public_key)
        s = sha3_256(shared)

        # Derive expected one-time address
        sG = scalarmult_base(s)
        expected_address = point_add(sG, spend_public)

        if expected_address == output.stealth_address:
            # This output is ours!
            one_time_secret = scalar_add(s, spend_secret)
            key_image = generate_key_image(one_time_secret, output.stealth_address)

            found.append(WalletOutput(
                txid=tx.transaction_id(),
                output_index=i,
                amount=decrypt_amount(output.encrypted_amount, shared),
                stealth_address=output.stealth_address,
                tx_public_key=output.tx_public_key,
                one_time_secret=one_time_secret,
                key_image=key_image,
                status=OutputStatus.UNSPENT
            ))

    return found
```

---

## 23. Mempool Management

### 23.1 Mempool Configuration

```python
MEMPOOL_MAX_SIZE_MB: int = 300
MEMPOOL_MAX_TX_COUNT: int = 50000
MEMPOOL_EXPIRY_HOURS: int = 336      # 2 weeks
MEMPOOL_MIN_FEE_RATE: int = 1        # Minimum fee per KB

# Replace-by-fee
RBF_ENABLED: bool = True
RBF_MIN_INCREMENT: float = 1.1       # 10% fee increase required
```

### 23.2 Mempool Structure

```python
@dataclass
class MempoolEntry:
    tx: Transaction
    received_at: int                 # Unix timestamp
    fee_rate: float                  # Fee per KB
    ancestors: Set[bytes]            # Parent tx IDs
    descendants: Set[bytes]          # Child tx IDs

class Mempool:
    entries: Dict[bytes, MempoolEntry]  # txid -> entry
    by_fee: SortedList[MempoolEntry]    # Sorted by fee_rate desc
    total_size: int                     # Current size in bytes

    def add_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Add transaction to mempool.

        Validation:
        1. Transaction is valid (signatures, amounts)
        2. Inputs exist and unspent
        3. No double-spend with existing mempool tx
        4. Fee meets minimum
        5. Mempool not full (or tx pays higher fee)
        """
        txid = tx.transaction_id()

        # Check duplicate
        if txid in self.entries:
            return False, "Already in mempool"

        # Validate transaction
        if not validate_transaction(tx):
            return False, "Invalid transaction"

        # Check inputs
        for inp in tx.inputs:
            if inp.key_image in self.spent_key_images:
                return False, "Double-spend detected"

        # Check fee
        fee_rate = tx.fee / (len(tx.serialize()) / 1024)
        if fee_rate < MEMPOOL_MIN_FEE_RATE:
            return False, "Fee too low"

        # Add to mempool
        entry = MempoolEntry(
            tx=tx,
            received_at=int(time.time()),
            fee_rate=fee_rate
        )
        self.entries[txid] = entry
        self.by_fee.add(entry)

        return True, "Added to mempool"

    def get_transactions_for_block(self, max_size: int) -> List[Transaction]:
        """Get highest-fee transactions that fit in block."""
        selected = []
        current_size = 0

        for entry in self.by_fee:
            tx_size = len(entry.tx.serialize())
            if current_size + tx_size <= max_size:
                selected.append(entry.tx)
                current_size += tx_size

        return selected

    def remove_expired(self):
        """Remove transactions older than MEMPOOL_EXPIRY_HOURS."""
        cutoff = int(time.time()) - (MEMPOOL_EXPIRY_HOURS * 3600)
        expired = [txid for txid, e in self.entries.items()
                   if e.received_at < cutoff]
        for txid in expired:
            self.remove_transaction(txid)
```

---

## 24. Sync Protocol

### 24.1 Initial Block Download (IBD)

```python
IBD_BATCH_SIZE: int = 500            # Blocks per request
IBD_PARALLEL_DOWNLOADS: int = 4      # Concurrent download streams
IBD_CHECKPOINT_INTERVAL: int = 10000 # Verify checkpoint every N blocks

class SyncManager:
    def initial_sync(self, peers: List[Peer]):
        """
        Perform initial block download.

        1. Get best chain from peers
        2. Download headers first
        3. Verify header chain
        4. Download blocks in parallel
        5. Validate and apply blocks
        6. Sync VDF state
        """
        # Get chain tips from peers
        tips = [peer.get_chain_tip() for peer in peers]
        best_height = max(tip.height for tip in tips)

        # Download headers
        headers = self.download_headers(peers, best_height)

        # Verify header chain
        if not self.verify_header_chain(headers):
            raise SyncError("Invalid header chain")

        # Download blocks in batches
        for start in range(0, best_height, IBD_BATCH_SIZE):
            end = min(start + IBD_BATCH_SIZE, best_height)
            blocks = self.download_blocks(peers, start, end)

            # Validate and apply
            for block in blocks:
                if not self.validate_and_apply(block):
                    raise SyncError(f"Invalid block at height {block.height}")

            # Checkpoint verification
            if end % IBD_CHECKPOINT_INTERVAL == 0:
                if not self.verify_checkpoint(end):
                    raise SyncError(f"Checkpoint mismatch at {end}")

        # Sync VDF state
        self.sync_vdf_state(peers)
```

### 24.2 Block Propagation

```python
BLOCK_PROPAGATION_TIMEOUT_MS: int = 5000
MAX_BLOCKS_IN_FLIGHT: int = 16

class BlockPropagation:
    def announce_block(self, block: Block):
        """Announce new block to peers."""
        inv = Inventory(type=INV_BLOCK, hash=block.block_hash())
        for peer in self.peers:
            peer.send(Message(type=MSG_INV, payload=inv))

    def handle_block(self, block: Block, from_peer: Peer):
        """Handle received block."""
        # Quick validation
        if not self.quick_validate(block):
            from_peer.misbehaving(10)
            return

        # Full validation
        if self.validate_block(block):
            # Apply to chain
            self.apply_block(block)
            # Relay to other peers
            self.announce_block(block)
        else:
            from_peer.misbehaving(100)
```

### 24.3 Chain Reorganization

```python
MAX_REORG_DEPTH: int = 100           # Maximum reorg depth

def reorganize_chain(
    current_tip: Block,
    new_tip: Block,
    state: GlobalState
) -> bool:
    """
    Reorganize chain to new tip.

    1. Find common ancestor
    2. Roll back to ancestor
    3. Apply new chain
    """
    # Find common ancestor
    old_chain = get_chain_to_ancestor(current_tip, MAX_REORG_DEPTH)
    new_chain = get_chain_to_ancestor(new_tip, MAX_REORG_DEPTH)

    ancestor = find_common_ancestor(old_chain, new_chain)
    if ancestor is None:
        return False  # Reorg too deep

    # Calculate chain scores (based on accumulated VDF)
    old_score = compute_chain_score(old_chain)
    new_score = compute_chain_score(new_chain)

    if new_score <= old_score:
        return False  # New chain not better

    # Roll back
    for block in reversed(old_chain):
        if block.height <= ancestor.height:
            break
        unapply_block(block, state)

    # Apply new chain
    for block in new_chain:
        if block.height <= ancestor.height:
            continue
        if not apply_block(block, state):
            return False

    return True
```

---

## 25. Storage Structure

### 25.1 Database Schema

```python
# SQLite schema for node storage

SCHEMA = """
-- Blocks
CREATE TABLE blocks (
    height INTEGER PRIMARY KEY,
    hash BLOB NOT NULL UNIQUE,
    parent_hash BLOB NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    finality_depth INTEGER NOT NULL,
    data BLOB NOT NULL,  -- Serialized block

    INDEX idx_blocks_hash (hash),
    INDEX idx_blocks_parent (parent_hash)
);

-- Transactions
CREATE TABLE transactions (
    txid BLOB PRIMARY KEY,
    block_height INTEGER,
    tx_index INTEGER,
    data BLOB NOT NULL,

    FOREIGN KEY (block_height) REFERENCES blocks(height)
);

-- UTXO Set
CREATE TABLE utxos (
    txid BLOB NOT NULL,
    output_index INTEGER NOT NULL,
    stealth_address BLOB NOT NULL,
    amount INTEGER NOT NULL,
    block_height INTEGER NOT NULL,

    PRIMARY KEY (txid, output_index),
    INDEX idx_utxos_address (stealth_address)
);

-- Key Images (spent outputs)
CREATE TABLE key_images (
    key_image BLOB PRIMARY KEY,
    txid BLOB NOT NULL,
    block_height INTEGER NOT NULL
);

-- Accounts
CREATE TABLE accounts (
    pubkey BLOB PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    nonce INTEGER NOT NULL DEFAULT 0,
    epoch_heartbeats INTEGER NOT NULL DEFAULT 0,
    total_heartbeats INTEGER NOT NULL DEFAULT 0,
    last_heartbeat_height INTEGER NOT NULL DEFAULT 0,
    first_seen_height INTEGER NOT NULL,
    tier INTEGER NOT NULL DEFAULT 0,
    data BLOB  -- Full serialized AccountState
);

-- Heartbeats
CREATE TABLE heartbeats (
    id BLOB PRIMARY KEY,
    pubkey BLOB NOT NULL,
    block_height INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    data BLOB NOT NULL,

    INDEX idx_heartbeats_pubkey (pubkey),
    INDEX idx_heartbeats_height (block_height)
);

-- VDF State
CREATE TABLE vdf_state (
    depth INTEGER PRIMARY KEY,
    vdf_root BLOB NOT NULL,
    timestamp_ms INTEGER NOT NULL,

    INDEX idx_vdf_depth (depth)
);
""";
```

### 25.2 Storage Configuration

```python
@dataclass
class StorageConfig:
    db_path: str = "montana.db"
    blocks_dir: str = "blocks"
    chainstate_dir: str = "chainstate"
    vdf_dir: str = "vdf"

    # Performance
    cache_size_mb: int = 512
    write_buffer_mb: int = 64
    max_open_files: int = 1000

    # Pruning (optional)
    prune_enabled: bool = False
    prune_keep_blocks: int = 10000   # Keep last N blocks
```

---

## 26. Node Configuration

### 26.1 Configuration Structure

```python
class NetworkType(IntEnum):
    MAINNET = 1
    TESTNET = 2
    REGTEST = 3

@dataclass
class NodeConfig:
    """Complete node configuration."""
    # Identity
    data_dir: str = "~/.montana"
    node_name: str = "Montana-Node"

    # Network
    network_type: NetworkType = NetworkType.MAINNET
    listen_port: int = 19656
    max_inbound: int = 125
    max_outbound: int = 8

    # RPC
    rpc_enabled: bool = True
    rpc_bind: str = "127.0.0.1"
    rpc_port: int = 19657
    rpc_user: Optional[str] = None
    rpc_password: Optional[str] = None

    # Wallet
    wallet_enabled: bool = True
    wallet_file: str = "wallet.dat"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Performance
    db_cache_mb: int = 512
    mempool_size_mb: int = 300

    # Features
    enable_heartbeat: bool = True
    enable_mining: bool = False

    @classmethod
    def from_file(cls, path: str) -> 'NodeConfig':
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)

    def validate(self) -> bool:
        if self.max_outbound < 4:
            raise ValueError("max_outbound must be >= 4")
        if self.rpc_enabled and not self.rpc_password:
            raise ValueError("RPC password required when RPC enabled")
        return True
```

### 26.2 Network Seeds

```python
# DNS seeds for peer discovery
MAINNET_SEEDS = [
    "seed1.montana.network",
    "seed2.montana.network",
    "seed3.montana.network",
]

TESTNET_SEEDS = [
    "testnet-seed1.montana.network",
    "testnet-seed2.montana.network",
]

# Hardcoded bootstrap nodes
BOOTSTRAP_NODES = [
    ("node1.montana.network", 19656),
    ("node2.montana.network", 19656),
]
```

---

## 27. Genesis Block

### 27.1 Genesis Parameters

```python
# Genesis block parameters (to be set at launch)
GENESIS_TIMESTAMP_MS: int = 0        # TBD: Launch timestamp (UTC)
GENESIS_VDF_ROOT: bytes = b''        # TBD: Initial VDF state

# Genesis block structure
def create_genesis_block() -> Block:
    """
    Create genesis block.

    FAIR LAUNCH:
    - No pre-mine
    - No founder allocation
    - All coins from block rewards only
    """
    finality_ref = FinalityReference(
        depth=0,
        vdf_root=Hash(GENESIS_VDF_ROOT),
        timestamp_ms=GENESIS_TIMESTAMP_MS,
    )

    header = BlockHeader(
        version=PROTOCOL_VERSION,
        height=0,
        parent_hash=Hash.zero(),
        timestamp_ms=GENESIS_TIMESTAMP_MS,
        heartbeats_root=Hash.zero(),
        transactions_root=Hash.zero(),
        state_root=Hash.zero(),
        finality_ref=finality_ref,
    )

    return Block(
        header=header,
        heartbeats=[],
        transactions=[],
        signers=[],
    )
```

### 27.2 Genesis State

```python
def create_genesis_state() -> GlobalState:
    """
    Create genesis state.

    FAIR LAUNCH: Zero initial supply.
    """
    genesis = create_genesis_block()

    return GlobalState(
        chain_height=0,
        chain_tip_hash=genesis.block_hash(),
        accumulated_vdf_depth=0,
        vdf_root=Hash(GENESIS_VDF_ROOT),
        min_finality_depth=0,
        total_supply=0,           # Fair launch - no pre-mine
        circulating_supply=0,
        total_heartbeats=0,
        active_accounts=0,
        accounts={},
    )
```

---

## 28. Constants Reference (Complete)

```python
# ==============================================================================
# Ɉ MONTANA — MECHANISM FOR ASYMPTOTIC TRUST IN TIME VALUE
# v3.1 — Explicit Tier System (1-2-3)
# ==============================================================================
PROJECT = "Ɉ Montana"
SYMBOL = "Ɉ"
TICKER = "$MONT"
DEFINITION = "lim(evidence → ∞) 1 Ɉ → 1 second"
TYPE = "Temporal Time Unit"
TOTAL_SUPPLY = 1_260_000_000
INITIAL_DISTRIBUTION = 3000
HALVING_INTERVAL = 210_000
TOTAL_BLOCKS = 6_930_000
TOTAL_ERAS = 33

# ==============================================================================
# NODE TYPES (2 types only)
# ==============================================================================
NODE_TYPE_FULL = 1              # Full Node: Full history + VDF
NODE_TYPE_LIGHT = 2             # Light Node: History from connection only
NODE_TYPES_TOTAL = 2            # Exactly 2 node types in protocol

# ==============================================================================
# PARTICIPATION TIERS (3 tiers only, numbered 1-2-3)
# ==============================================================================
TIER_1 = 1                      # Full Node operators
TIER_2 = 2                      # Light Node operators OR TG Bot/Channel owners
TIER_3 = 3                      # TG Community participants
TIERS_TOTAL = 3                 # Exactly 3 tiers in protocol

# Lottery probability by tier
TIER_1_WEIGHT = 0.70            # 70% → Full Node
TIER_2_WEIGHT = 0.20            # 20% → Light Node / TG Bot owners
TIER_3_WEIGHT = 0.10            # 10% → TG Community users

# Summary:
# Tier 1 (Full Node):  70%
# Tier 2 (Light Node): 20%
# Tier 3 (TG Users):   10%

# ==============================================================================
# LAYER 0-1: VDF (CLASS GROUP, WESOLOWSKI 2019)
# ==============================================================================
VDF_TYPE = "class_group"              # Wesolowski construction
VDF_DISCRIMINANT_BITS = 2048          # Security parameter for Δ
VDF_BASE_ITERATIONS = 16777216        # 2^24 sequential squarings
VDF_MAX_ITERATIONS = 268435456        # 2^28
VDF_CHALLENGE_BITS = 128              # Wesolowski challenge size

# Wesolowski proof parameters
WESOLOWSKI_HASH_TO_PRIME_ATTEMPTS = 1000
WESOLOWSKI_PROOF_SECURITY_BITS = 128
# Verification: O(log T), proof size: ~256 bytes

# ==============================================================================
# LAYER 2: ACCUMULATED FINALITY
# ==============================================================================
VDF_CHECKPOINT_TIME_SEC = 2.5
FINALITY_SOFT_CHECKPOINTS = 1
FINALITY_MEDIUM_CHECKPOINTS = 100
FINALITY_HARD_CHECKPOINTS = 1000

# ==============================================================================
# BLOCK TIMING
# ==============================================================================
BLOCK_TIME_TARGET_SEC = 600
BLOCK_INTERVAL_MS = 600_000
VDF_TX_CHECKPOINT_SEC = 1

# ==============================================================================
# SCORE
# ==============================================================================
SCORE_PRECISION = 1_000_000
SCORE_MIN_HEARTBEATS = 1
ACTIVITY_WINDOW_BLOCKS = 2016
INACTIVITY_PENALTY_RATE = 0.001

# ==============================================================================
# BLOCK REWARDS (tiers numbered 1-2-3)
# ==============================================================================
# See PARTICIPATION TIERS section for authoritative values
# TIER_1_WEIGHT = 0.70 (Full Node)
# TIER_2_WEIGHT = 0.20 (Light Node / TG Bot)
# TIER_3_WEIGHT = 0.10 (TG Users)

# ==============================================================================
# TRANSACTIONS
# ==============================================================================
TX_FREE_PER_SECOND = 1
TX_FREE_PER_EPOCH = 10
TX_EPOCH_DURATION_SEC = 600
POW_BASE_DIFFICULTY_BITS = 16
POW_EXCESS_PENALTY_BITS = 2
POW_BURST_PENALTY_BITS = 4
POW_MAX_DIFFICULTY_BITS = 32
POW_MEMORY_COST_KB = 65536

# ==============================================================================
# PRIVACY
# ==============================================================================
RING_SIZE = 11
PRIVACY_FEE_T0 = 1
PRIVACY_FEE_T1 = 2
PRIVACY_FEE_T2 = 5
PRIVACY_FEE_T3 = 10

# ==============================================================================
# NETWORK
# ==============================================================================
PROTOCOL_VERSION = 8
NETWORK_ID_MAINNET = 0x4D4F4E5441
NETWORK_ID_TESTNET = 0x544553544E
DEFAULT_PORT = 19656
DEFAULT_RPC_PORT = 19657
MIN_OUTBOUND_CONNECTIONS = 8
MAX_INBOUND_CONNECTIONS = 125
MAX_BLOCK_SIZE = 4_194_304
MAX_HEARTBEATS_PER_BLOCK = 1000
MAX_TRANSACTIONS_PER_BLOCK = 5000

# ==============================================================================
# MEMPOOL
# ==============================================================================
MEMPOOL_MAX_SIZE_MB = 300
MEMPOOL_MAX_TX_COUNT = 50000
MEMPOOL_EXPIRY_HOURS = 336
MEMPOOL_MIN_FEE_RATE = 1
RBF_ENABLED = True
RBF_MIN_INCREMENT = 1.1

# ==============================================================================
# SYNC
# ==============================================================================
IBD_BATCH_SIZE = 500
IBD_PARALLEL_DOWNLOADS = 4
MAX_REORG_DEPTH = 100

# ==============================================================================
# WALLET
# ==============================================================================
WALLET_VERSION = 1
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
MIN_PASSWORD_LENGTH = 8

# ==============================================================================
# CRYPTOGRAPHY
# ==============================================================================
HASH_FUNCTION = "SHA3-256"
SIGNATURE_SCHEME = "SPHINCS+-SHAKE-128f"
SPHINCS_PUBLIC_KEY_SIZE = 32
SPHINCS_SECRET_KEY_SIZE = 64
SPHINCS_SIGNATURE_SIZE = 17088
KEY_ENCAPSULATION = "ML-KEM-768"

# ==============================================================================
# GENESIS (TBD at launch)
# ==============================================================================
GENESIS_TIMESTAMP_MS = 0             # Set at launch
GENESIS_VDF_ROOT = bytes(32)         # Set at launch
```

---

<div align="center">

**Ɉ Montana**

Mechanism for asymptotic trust in the value of time

*lim(evidence → ∞) 1 Ɉ → 1 second*

**Self-sovereign. Physics-based.**

**$MONT**

Technical Specification v3.1 | January 2026

</div>
