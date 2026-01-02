# Ɉ Montana: Temporal Time Unit

**Version:** 3.6
**Date:** January 2026
**Ticker:** $MONT
**Architecture:** Timechain

---

> *"Time is the only resource distributed equally to all humans."*

**Ɉ** (inverted t) is a Temporal Time Unit. **Montana** is the Timechain that produces it.

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

---

## Abstract

**Ɉ** (inverted t) is a Temporal Time Unit. **Montana** is the Timechain that produces it.

```
lim(evidence → ∞) 1 Ɉ → 1 second
∀t: 1 Ɉ(t) ≈ 1 second
```

Montana builds trust in time value through the **Asymptotic Trust Consensus** (ATC) architecture — physical constraints, computational hardness, protocol primitives, and consensus mechanisms.

**Montana is a Timechain.** Timechain chains time, bounded by physics. The fundamental unit is a second.

```
Timechain:   chain of time, bounded by physics
             "Time passed — this is fact"
```

**Montana v3.6** is fully self-sovereign. Finality is determined by UTC boundaries — time itself becomes the consensus mechanism.

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

**Time is physically verified.** Every second is confirmed by thermodynamics (irreversibility) and atomic physics (clock precision).

### 1.3 Purpose

Montana answers one question:

> **"Can we verify that one second has passed?"**

Yes — through:
1. **UTC boundaries** (universal time reference)
2. **VDF computation** (proof of participation in time window)
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

An adversary operating within known physics is **bound by**:
- Time flows forward (thermodynamics)
- Time is conserved (conservation)
- Information travels at light speed maximum (relativity)
- Computation requires energy (Landauer)
- **UTC is universal** (time passes equally for all)

TTU integrity rests on physics — the most precisely tested constraints in science.

### 2.3 Self-Sovereign Finality

Montana achieves finality through **UTC time boundaries** — deterministic points in time when blocks become final.

| Property | Guarantee |
|----------|-----------|
| Security basis | Physical (UTC is universal) |
| Attack cost | Requires advancing UTC (physically bound) |
| Dependencies | Physics only |
| Trust model | Physics |

**Time passes equally for all. Hardware advantage is bounded by UTC.**

---

## 3. UTC Finality Model

Montana uses UTC time boundaries for deterministic finality. No external time sources required — nodes use system UTC with ±5 second tolerance.

### 3.1 Finality Boundaries

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
```

Finality occurs every **1 minute** at UTC boundaries: 00:00, 00:01, 00:02, etc.

### 3.2 Time Consensus

```
Time source:        UTC on each node (system clock)
Tolerance:          ±5 seconds
External sources:   None required
```

Nodes accept blocks and heartbeats within ±5 seconds of their local UTC. This tolerance accommodates network propagation, minor drift, and NTP variance without requiring external synchronization.

### 3.3 VDF Role

VDF proves participation in a time window — not computation speed:

```
Node A (fast hardware):   VDF ready at 00:00:25 → waits → participates in F1
Node B (slow hardware):   VDF ready at 00:00:55 → participates in F1
Node C (too slow):        VDF ready at 00:01:02 → misses F1 → participates in F2
```

**Hardware advantage eliminated.** Fast hardware waits for UTC boundary like everyone else.

### 3.4 ASIC Resistance

| Scenario | Old Model (VDF depth) | UTC Model |
|----------|----------------------|-----------|
| ASIC vs CPU | 40× advantage | Equal (bounded by UTC) |
| Finality time | Variable (hardware-dependent) | Fixed (1 min UTC) |
| Attack vector | Faster VDF = more depth | Bounded by UTC (physical) |

### 3.5 Clock Security

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

Nodes within ±5 seconds participate in the current finality window. Nodes outside this window participate in subsequent windows.

**±5 Second Budget:**

| Factor | Allocation |
|--------|------------|
| Network propagation | ~2 seconds |
| Clock drift | ~1 second |
| NTP jitter | ~1 second |
| Safety margin | ~1 second |

**Recommendations for Full Node Operators:**

| Practice | Purpose |
|----------|---------|
| Multiple NTP sources (3+) | Resilience |
| NTS (NTP over TLS) | Authenticated synchronization |
| Hardware clock monitoring | Early drift detection |
| Isolated time source (HSM) | High-value nodes |

**Principle:**

Clock security = private key security. Each operator controls their own system.

---

## 4. Finality

```
┌─────────────────────────────────────────────────────────────────┐
│  HARD FINALITY (3 minutes)                                      │
│  3 UTC boundaries passed                                        │
│  Attack cost: Requires reversing UTC (physical)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  MEDIUM FINALITY (2 minutes)                                    │
│  2 UTC boundaries passed                                        │
│  High certainty                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  SOFT FINALITY (1 minute)                                       │
│  1 UTC boundary passed                                          │
│  Block included in finality checkpoint                          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 Transaction Speed

```
00:00:00.000 — Transaction created
00:00:00.050 — In mempool
00:00:00.500 — Propagated to network
00:00:01.000 — Included in DAG (visible to all)
              ↓
      TRANSACTION VISIBLE AND ACTIVE
              ↓
00:01:00.000 — FINALIZED (irreversible)
```

| Stage | Time |
|-------|------|
| Transaction visibility | **< 1 second** |
| Finalization | **1 minute** |

Transactions are near-instant. Finalization is deterministic.

### 4.2 Finality Properties

| Property | UTC Finality |
|----------|--------------|
| Security | Physical (UTC is universal) |
| Attack cost | Requires advancing time (physical) |
| Dependencies | Physics only |
| Latency | Deterministic (1/2/3 minutes) |

### 4.3 Finality Checkpoint Structure

Each finality checkpoint (every 1 minute) contains:

```
Finality Checkpoint:
├─ UTC timestamp (boundary time)
├─ Merkle root of all blocks in window
├─ VDF proofs from participating nodes
├─ Aggregate signatures (SPHINCS+)
└─ Previous checkpoint hash
```

### 4.4 Network Partition

During network partition, both sides continue creating finality checkpoints independently.

```
Partition A (60% nodes)     Partition B (40% nodes)
        │                           │
00:01   F1-A (60 heartbeats)       F1-B (40 heartbeats)
00:02   F2-A                        F2-B
00:03   F3-A                        F3-B
        │                           │
        └─────── reconnect ─────────┘
                    │
               Fork choice
```

**Fork Choice Rule:** Cascade tiebreakers — each level has semantic meaning.

```python
def resolve_checkpoint_conflict(cp_a, cp_b):
    assert cp_a.utc_timestamp == cp_b.utc_timestamp

    # 1. More participants → larger active network
    if len(cp_a.heartbeats) != len(cp_b.heartbeats):
        return max(cp_a, cp_b, key=lambda c: len(c.heartbeats))

    # 2. More VDF iterations → more proven time
    vdf_a = sum(h.vdf_iterations for h in cp_a.heartbeats)
    vdf_b = sum(h.vdf_iterations for h in cp_b.heartbeats)
    if vdf_a != vdf_b:
        return cp_a if vdf_a > vdf_b else cp_b

    # 3. Higher aggregate score → more reliable participants
    score_a = sum(h.participant_score for h in cp_a.heartbeats)
    score_b = sum(h.participant_score for h in cp_b.heartbeats)
    if score_a != score_b:
        return cp_a if score_a > score_b else cp_b

    # 4. Hash — only if ALL equal (astronomically rare)
    return min(cp_a, cp_b, key=lambda c: c.hash)
```

**Cascade Logic:**

| Level | Criterion | Semantic |
|-------|-----------|----------|
| 1 | Heartbeats count | Active network size |
| 2 | Σ VDF iterations | Total proven time |
| 3 | Σ participant scores | Participant reliability (√heartbeats history) |
| 4 | Hash | Deterministic last resort |

Level 4 is reached only with perfect 50/50, identical participants, identical VDF. Probability → 0.

**Consequences:**
- Transactions in smaller partition are preserved (DAG merge includes all blocks)
- Finality in smaller partition rolls back to reconnection point
- Heartbeats count after merge

| Scenario | Outcome |
|----------|---------|
| 60/40 split | Majority checkpoint canonical (Level 1) |
| 50/50 different VDF | Higher total VDF wins (Level 2) |
| 50/50 same VDF | Higher aggregate score wins (Level 3) |
| Perfect tie | Smaller hash wins (Level 4, astronomically rare) |
| Brief partition | Minimal impact (few checkpoints affected) |

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

All TTUs distributed through participation. Everyone starts equal.

---

## 6. Participation

### 6.1 Node Types (2 only)

| Node Type | Storage | Tier |
|-----------|---------|------|
| **Full Node** | Full timechain history (downloads all) | Tier 1 |
| **Light Node** | From connection moment only (mandatory) | Tier 2 |

### 6.2 Participation Tiers (3 only)

| Tier | Participants | Node Type | Lottery Weight |
|------|--------------|-----------|----------------|
| **1** | Full Node operators | Full Node | **70%** |
| **2** | Light Node operators OR Light Client owners | Light Node | **20%** |
| **3** | Light Client users | — | **10%** |

**Summary:**
- Tier 1 (Full Node): **70%** — network security
- Tier 2 (Light Node / Light Client): **20%** — infrastructure scaling
- Tier 3 (Light Client users): **10%** — mass adoption

### 6.3 Light Clients and Mass Adoption

Tier 2 and Tier 3 provide **barrier-free access** to time unit distribution through lightweight clients. Montana uses any platform — existing messaging and app platforms serve as distribution channels.

**Supported Light Client Platforms:**

| Platform | Type | Status |
|----------|------|--------|
| Telegram Bot | Messaging | Initial implementation |
| Discord Bot | Messaging | Planned |
| WeChat Mini Program | Messaging | Planned |
| iOS App (App Store) | Mobile | Planned |
| Android App (Google Play) | Mobile | Planned |
| Web Application | Browser | Planned |

**Design Principles:**

1. **Platform Independence:** Montana protocol has no dependency on Telegram or any platform. Light clients are interchangeable interfaces to the same network.

2. **Equal Conditions:** All participants compete on equal terms. The only arbiter is time — and time passes equally for everyone.

3. **Safe Scaling:** Tier 2+3 receive only 30% of lottery weight combined. This allows millions of participants without risk of network influence.

4. **Sybil Resistance:** Multiple identities share the same time allocation. Each participant receives equal seconds per day regardless of account count.

```
Why 70/20/10 distribution?

Full Nodes (70%):    Provide security, store history, compute VDF
Light Nodes (20%):   Extend network reach, validate from connection
Light Clients (10%): Mass adoption, zero barrier entry

Security comes from Tier 1.
Scale comes from Tier 2+3.
```

**Time as the Universal Equalizer:**

```
Billionaire with 1000 accounts:  24 hours/day
Student with 1 account:          24 hours/day
Server farm with 10000 bots:     24 hours/day

Time is equal for all.
Time flows at one speed.
Competition is fair — the arbiter is physics.
```

### 6.4 Light Client Security

**Authenticity verification:** Protocol verifies cryptography. Source is irrelevant.

```python
# Every heartbeat contains:
@dataclass
class LightHeartbeat:
    pubkey: PublicKey           # SPHINCS+ public key (user owns private key)
    timestamp_ms: int           # Within ±5 seconds of UTC
    signature: Signature        # SPHINCS+ signature (17,088 bytes)

# Verification:
def verify_heartbeat(hb: LightHeartbeat) -> bool:
    return sphincs_verify(hb.pubkey, hb.timestamp_ms, hb.signature)
```

**Sybil resistance through tier weights:**

| Scenario | Lottery allocation |
|----------|-------------------|
| 1,000,000 Telegram accounts | Share 10% total weight |
| Each account | 0.00001% chance |
| 1 Full Node | 7% chance (700,000× more) |

**Private key ownership guarantees authenticity:**

```
User owns private key → user signs heartbeat
Bot operator receives signed messages only
Heartbeat authenticity = valid SPHINCS+ signature
```

**Security model:**

| Layer | Guarantee |
|-------|-----------|
| Tier weights (70/20/10) | Light Client influence capped at 30% |
| SPHINCS+ signatures | Cryptographic authenticity |
| One heartbeat per key per minute | Rate limiting |
| Private key ownership | Owner exclusivity |

Protocol is source-agnostic. Telegram, Discord, direct TCP — all equivalent. Valid signature = valid heartbeat.

### 6.5 Heartbeat

A **heartbeat** proves temporal presence within a finality window:

```
Full Heartbeat (Tier 1):       Light Heartbeat (Tier 2/3):
├─ VDF proof                   ├─ Timestamp (verified)
├─ Finality window reference   ├─ Source (LIGHT_NODE/TG_BOT/TG_USER)
└─ SPHINCS+ signature          ├─ Community ID
                               └─ SPHINCS+ signature
```

Heartbeats must arrive before UTC boundary to be included in finality checkpoint.

### 6.6 Score

```
Score = √(heartbeats)
```

Square root provides diminishing returns and Sybil resistance.

---

## 7. Technical

### 7.1 Cryptography

| Function | Primitive | Standard | Security Type |
|----------|-----------|----------|---------------|
| Signatures | SPHINCS+-SHAKE-128f | NIST FIPS 205 | Post-quantum |
| Key Exchange | ML-KEM-768 | NIST FIPS 203 | Post-quantum |
| Hashing | SHA3-256 | NIST FIPS 202 | Post-quantum |
| VDF | Class Group | Wesolowski 2019 | Type B |

### 7.2 Verifiable Delay Function

Montana uses **Class Group VDF** for temporal proof — Type B security with mathematical guarantees.

```
VDF: G × T → G × π

Input:  g ∈ Class Group of imaginary quadratic field
Output: g^(2^T), proof π
T = 2²⁴ sequential squarings

Verification: O(log T) using Wesolowski proof
```

**Class Group VDF Properties:**

| Property | Guarantee |
|----------|-----------|
| Sequentiality | Mathematical (group structure requires sequential computation) |
| Security | Type B (reduction to class group order problem) |
| Trusted setup | None required (class groups are parameter-free) |
| Verification | O(log T) — efficient for any verifier |

**UTC Model and Quantum Computers:**

Class Group VDF is vulnerable to Shor's algorithm on quantum computers. Montana's UTC finality model makes this irrelevant:

```
┌─────────────────────────────────────────────────────────────────┐
│                UTC BOUNDARY = PHYSICAL EQUALIZER                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Classical node:     VDF in 30 sec → wait 30 sec → 1 heartbeat  │
│  Quantum attacker:   VDF in 0.001 sec → wait 59.999 sec → 1 heartbeat
│                                                                  │
│  Result: Both receive exactly ONE heartbeat per finality window │
│                                                                  │
│  Quantum speedup on VDF = longer waiting time                   │
│  UTC boundary is the rate limiter, VDF speed is irrelevant      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Security Analysis:**

| Attacker | VDF Computation | Heartbeats per Minute | Advantage |
|----------|-----------------|----------------------|-----------|
| Classical CPU | 30 seconds | 1 | Baseline |
| ASIC | 5 seconds | 1 | None (waits for UTC) |
| Quantum computer | 0.001 seconds | 1 | None (waits for UTC) |

VDF proves participation eligibility within a finality window. The physical constraint is time itself — UTC boundaries pass at the same rate for all computers.

**Type B Security:**

```
Security reduction:
  "VDF shortcut exists" → "Class group order can be computed efficiently"

Class group order problem:
  Given discriminant Δ, compute |Cl(Δ)|

Status: Hard problem for 40+ years
  - Related to factoring
  - Best algorithms: subexponential
  - Quantum: Shor applies, but UTC neutralizes
```

VDF computation must complete before UTC boundary. Faster hardware simply waits longer.

### 7.3 DAG Structure

```
    ┌─[B1]─┐
    │      │
[G]─┼─[B2]─┼─[B4]─...
    │      │
    └─[B3]─┘
```

No wasted work. All valid blocks included.

### 7.4 Privacy (Optional)

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
│  Layer 2: Consensus (Safety, Liveness, UTC Finality)            │
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
│  Layer -1: Physics (Thermodynamics, Sequentiality, Light Speed) │
└─────────────────────────────────────────────────────────────────┘
```

**Montana v3.6 — Timechain:** Fully self-sovereign. No external dependencies.

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
- Boneh et al. (2018) — Verifiable Delay Functions
- Wesolowski (2019) — Efficient VDF from Class Groups
- Buchmann, Williams (1988) — Class Group Computation
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

# Time Consensus
TIME_TOLERANCE_SEC = 5       # ±5 seconds UTC tolerance
FINALITY_INTERVAL_SEC = 60   # 1 minute

# VDF (Class Group, Type B security)
VDF_TYPE = "class_group"     # Wesolowski 2019
VDF_ITERATIONS = 16_777_216  # 2^24 sequential squarings
VDF_DISCRIMINANT_BITS = 2048 # Security parameter

# Finality (UTC boundaries)
FINALITY_SOFT = 1            # 1 boundary (1 minute)
FINALITY_MEDIUM = 2          # 2 boundaries (2 minutes)
FINALITY_HARD = 3            # 3 boundaries (3 minutes)

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
