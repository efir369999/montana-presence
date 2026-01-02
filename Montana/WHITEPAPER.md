# Ɉ Montana: Temporal Time Unit

**Version:** 4.0
**Protocol:** 11
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

**Montana v4.0** achieves self-sovereignty through physics. Finality is determined by UTC boundaries — time itself becomes the consensus mechanism. All cryptographic primitives are post-quantum secure.

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
├─ Aggregate signatures (ML-DSA)
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

### 4.5 Formal Fork Choice Specification

**Definition 1 (Finality Checkpoint).** A finality checkpoint C is a tuple:
```
C = (τ, M_blocks, M_vdf, n, v, s, h_prev)

where:
  τ       ∈ ℤ⁺         UTC boundary timestamp (ms), τ ≡ 0 (mod 60000)
  M_blocks ∈ {0,1}²⁵⁶   Merkle root of blocks in window [τ-60000, τ)
  M_vdf   ∈ {0,1}²⁵⁶   Merkle root of VDF proofs
  n       ∈ ℤ⁺         Participant count (heartbeats)
  v       ∈ ℤ⁺         Total VDF iterations Σᵢ vdf_iterations(hᵢ)
  s       ∈ ℝ⁺         Aggregate score Σᵢ √(history(hᵢ))
  h_prev  ∈ {0,1}²⁵⁶   Previous checkpoint hash
```

**Definition 2 (Checkpoint Ordering ≺).** For checkpoints C₁, C₂ with τ(C₁) = τ(C₂):
```
C₁ ≺ C₂ ⟺
  (n(C₁) > n(C₂)) ∨
  (n(C₁) = n(C₂) ∧ v(C₁) > v(C₂)) ∨
  (n(C₁) = n(C₂) ∧ v(C₁) = v(C₂) ∧ s(C₁) > s(C₂)) ∨
  (n(C₁) = n(C₂) ∧ v(C₁) = v(C₂) ∧ s(C₁) = s(C₂) ∧ H(C₁) < H(C₂))
```

**Theorem 1 (Total Order).** The relation ≺ is a strict total order on checkpoints with equal timestamps.

*Proof.*
- *Irreflexivity:* C ⊀ C since H(C) ≮ H(C).
- *Transitivity:* Follows from lexicographic ordering on (n, v, s, -H).
- *Totality:* For C₁ ≠ C₂, either some component differs (deterministic comparison) or all equal except hash (H(C₁) ≠ H(C₂) with probability 1 - 2⁻²⁵⁶). ∎

**Theorem 2 (Fork Resolution Determinism).** All honest nodes select the same canonical checkpoint.

*Proof.* Given checkpoints {C₁, ..., Cₖ} at timestamp τ, each honest node:
1. Computes (n, v, s, H) for each Cᵢ
2. Applies ≺ ordering
3. Selects max≺{C₁, ..., Cₖ}

Since ≺ is total and deterministic, all nodes select identical checkpoint. ∎

**Theorem 3 (Partition Recovery).** After network partition heals, consensus converges in O(1) checkpoint intervals.

*Proof sketch.*
- At reconnection time τᵣ, partitions exchange checkpoints
- For each τ < τᵣ with conflicting checkpoints, ≺ determines canonical
- New checkpoints at τ ≥ τᵣ include participants from both partitions
- Convergence requires single message round per conflicting timestamp. ∎

**Corollary 1 (Majority Wins).** In any partition, the side with more active participants produces canonical checkpoints.

*Proof.* Level 1 of ≺ compares n (participant count). Majority partition has n_majority > n_minority. ∎

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
    pubkey: PublicKey           # ML-DSA public key (user owns private key)
    timestamp_ms: int           # Within ±5 seconds of UTC
    signature: Signature        # ML-DSA signature (3,309 bytes)

# Verification:
def verify_heartbeat(hb: LightHeartbeat) -> bool:
    return mldsa_verify(hb.pubkey, hb.timestamp_ms, hb.signature)
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
Heartbeat authenticity = valid ML-DSA signature
```

**Security model:**

| Layer | Guarantee |
|-------|-----------|
| Tier weights (70/20/10) | Light Client influence capped at 30% |
| ML-DSA signatures | Cryptographic authenticity |
| One heartbeat per key per minute | Rate limiting |
| Private key ownership | Owner exclusivity |

Protocol is source-agnostic. Telegram, Discord, direct TCP — all equivalent. Valid signature = valid heartbeat.

### 6.5 Heartbeat

A **heartbeat** proves temporal presence within a finality window:

```
Full Heartbeat (Tier 1):       Light Heartbeat (Tier 2/3):
├─ VDF proof                   ├─ Timestamp (verified)
├─ Finality window reference   ├─ Source (LIGHT_NODE/TG_BOT/TG_USER)
└─ ML-DSA signature            ├─ Community ID
                               └─ ML-DSA signature
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

Montana is post-quantum secure from genesis. All cryptographic primitives use lattice-based constructions with Type B security — proven reductions to the Module-LWE problem.

| Function | Primitive | Standard | Security Type |
|----------|-----------|----------|---------------|
| Signatures | ML-DSA-65 | NIST FIPS 204 | Type B (MLWE) |
| Key Exchange | ML-KEM-768 | NIST FIPS 203 | Type B (MLWE) |
| VRF | Lattice-VRF | ATC L-1.B | Type B (MLWE) |
| Commitment | Lattice | ATC L-1.3 | Type B (MLWE + SIS) |
| VDF | Class Group | Wesolowski 2019 | Type B + P |
| Hash | SHA3-256 | NIST FIPS 202 | Type C |

**Security Types:**

| Type | Meaning | Confidence |
|------|---------|------------|
| A | Proven unconditionally | Mathematical certainty |
| B | Proven relative to assumption | Conditional certainty |
| C | Empirical hardness | High (10+ years) |
| P | Physical bound | As confident as physics |

**Hash Function Classification:**

| Category | Function | Security Type | Use Case |
|----------|----------|---------------|----------|
| Unkeyed | SHA3-256 | Type C | Block hashes, Merkle roots, VDF input |
| Keyed (MAC) | HMAC-SHA3-256 | Type B | Message authentication |
| Key Derivation | HKDF-SHA3-256 | Type B | Session keys, derived keys |

### 7.2 Post-Quantum Security

Montana assumes cryptographically relevant quantum computers will exist. The protocol is designed accordingly.

**Threat Model:**

Classical computers cannot break Montana cryptography. Quantum computers with Shor's algorithm can break RSA, ECDSA, and discrete log — but Montana uses none of these.

**Defense:**

| Component | Classical | Quantum | Montana |
|-----------|-----------|---------|---------|
| Signatures | ECDSA | Broken (Shor) | ML-DSA (MLWE) |
| Key Exchange | ECDH | Broken (Shor) | ML-KEM (MLWE) |
| VRF | ECVRF | Broken (Shor) | Lattice-VRF (MLWE) |
| Commitment | Pedersen | Broken (Shor) | Lattice (MLWE + SIS) |
| VDF | Class Group | Vulnerable | UTC neutralization |
| Hash | SHA-256 | Weakened (Grover) | SHA3-256 (128-bit PQ) |

**Module-LWE (MLWE):**

All Montana Type B primitives reduce to the Module Learning With Errors problem. MLWE is the foundation of NIST post-quantum standards (FIPS 203, 204).

```
Given: A (public matrix), b = A·s + e (mod q)
Find:  s (secret vector)

Where e is small error vector.

Best known attack: Exponential in lattice dimension.
Quantum speedup: None known beyond Grover (√).
```

**Confidence:**

| Primitive | Attack Complexity | NIST Level |
|-----------|-------------------|------------|
| ML-DSA-65 | 2¹²⁸ | Level 2 |
| ML-KEM-768 | 2¹²⁸ | Level 2 |
| Lattice-VRF | 2¹²⁸ | Level 2 |
| Lattice Commitment | 2¹²⁸ | Level 2 |

Montana does not predict when quantum computers will arrive. Montana is ready when they do.

### 7.3 Verifiable Delay Function

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

### 7.3 DAG Structure (Bullshark)

Montana uses **Bullshark** DAG ordering — Type B (proven) security with optimal latency.

```
    ┌─[B1]─┐
    │      │
[G]─┼─[B2]─┼─[B4]─...  → Bullshark commits (3 rounds)
    │      │
    └─[B3]─┘
```

| Property | Value | Type |
|----------|-------|------|
| Safety | Proven | B |
| Liveness | Proven (after GST) | B |
| Latency | 3 rounds (optimal) | — |
| Throughput | >100,000 TPS | — |
| Fault tolerance | f < n/3 Byzantine | — |

No wasted work. All valid blocks included. Ordering proven correct.

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
│  Layer 3+: Ɉ Montana: Temporal Time Unit                        │
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
│  Layer 0: Computation (SHA-3, ML-KEM, ML-DSA)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer -1: Physics (Thermodynamics, Sequentiality, Light Speed) │
└─────────────────────────────────────────────────────────────────┘
```

**Montana v3.7 — Timechain:** Fully self-sovereign. No external dependencies.

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

## 11. Security Analysis

### 11.1 Threat Model

**Adversary capabilities:**
- Controls up to f < n/3 nodes (Byzantine threshold)
- Has arbitrary but finite computational resources
- Operates within known physics (cannot reverse time, exceed light speed)
- May attempt to manipulate time sources

**Adversary goals:**
- Double-spend attacks
- Finality reversal
- Denial of service
- Sybil attacks

### 11.2 Security Properties

**Property 1 (Safety).** No two honest nodes finalize conflicting checkpoints at the same UTC boundary.

*Argument.* All honest nodes apply identical ordering ≺ to received checkpoints. By Theorem 2, deterministic selection ensures agreement. Conflicting finalization requires >2/3 Byzantine nodes (violates threshold). ∎

**Property 2 (Liveness).** Under partial synchrony, honest transactions achieve finality within bounded time.

*Argument.* After GST (Global Stabilization Time):
- Messages propagate within ±5 seconds
- Honest nodes produce heartbeats each minute
- Checkpoints form at UTC boundaries
- Finality: 1 minute (soft), 3 minutes (hard)

Liveness holds after GST with O(minutes) latency. ∎

**Property 3 (Finality).** After k UTC boundaries, checkpoint reversal requires violating physical constraints.

*Argument.* Reverting checkpoint at time τ requires:
1. Producing alternative checkpoint C' with C' ≺ C at same τ
2. This requires more participants, VDF iterations, or score
3. After τ passes, no new heartbeats can reference window [τ-60s, τ)
4. Reversal requires "going back in time" — physically impossible

Finality is physics-based, not economic. ∎

### 11.3 Attack Analysis

| Attack | Mitigation | Cost |
|--------|------------|------|
| **51% Sybil** | Tier weights (70/20/10) | Must control 51% of Full Nodes |
| **VDF speedup** | UTC boundary rate-limits | Zero advantage (wait for boundary) |
| **Quantum VDF** | UTC neutralization | Zero advantage (same rate limit) |
| **Clock manipulation** | Self-sovereign time | Excludes attacker from consensus |
| **Network partition** | Fork choice ≺ | Deterministic resolution |
| **Long-range attack** | Accumulated VDF | Requires recomputing all VDF sequentially |

### 11.4 NTP Threat Model

**Threat:** Adversary manipulates NTP infrastructure to desynchronize honest nodes.

**Attack vectors:**

| Vector | Description | Mitigation |
|--------|-------------|------------|
| **Single NTP compromise** | Attacker controls one NTP server | Multiple sources (3+) required |
| **Regional NTP attack** | All servers in region compromised | Geographic diversity |
| **BGP hijack of NTP** | Route NTP traffic through attacker | NTS (authenticated NTP) |
| **GPS spoofing** | False GPS time to NTP servers | Multiple independent sources |

**Analysis by drift magnitude:**

| Drift | % Network Affected | Impact |
|-------|-------------------|--------|
| ≤5 seconds | Any | None (within tolerance) |
| 5-60 seconds | <33% | Affected nodes miss 1 window, rejoin next |
| 5-60 seconds | >33% | Network partitions, fork choice resolves |
| >60 seconds | Any | Affected nodes excluded, rejoin after resync |

**Theorem 4 (NTP Attack Bound).** An adversary controlling k% of NTP infrastructure can affect at most k% of Montana nodes.

*Proof sketch.* Each node uses independent NTP sources. Compromise of source S affects only nodes using S exclusively. Recommendation of 3+ diverse sources limits single-source dependency. ∎

**Recovery procedure:**
1. Node detects drift via peer timestamp variance
2. Node pauses heartbeat submission
3. Node resynchronizes to verified NTP sources
4. Node resumes participation in next finality window

**Design principle:** Clock compromise affects only the compromised node. No mechanism exists for peers to influence a node's clock — isolation is absolute.

### 11.5 Minimum Viable Network

**Definition 3 (Minimum Viable Network).** Montana achieves meaningful BFT with:
```
n ≥ 7 participants     (tolerates f = 2 Byzantine)
k ≥ 2 geographic regions
m ≥ 3 autonomous systems
```

**Confidence levels:**

| Level | Participants | Regions | Byzantine Tolerance |
|-------|--------------|---------|---------------------|
| **Full** | ≥21 | ≥3 | f = 6 |
| **High** | ≥7 | ≥2 | f = 2 |
| **Low** | <7 | <2 | Limited |

**Theorem 5 (BFT Threshold).** Montana tolerates f < n/3 Byzantine participants while maintaining safety and liveness.

*Proof.* Standard BFT argument: honest majority (>2n/3) agrees on checkpoint via ≺ ordering. Byzantine minority cannot produce checkpoint with higher (n, v, s) tuple. ∎

---

## References

### Physics

[1] Einstein, A. (1905). "On the Electrodynamics of Moving Bodies." *Annalen der Physik* 17: 891-921.

[2] Einstein, A. (1915). "The Field Equations of Gravitation." *Sitzungsberichte der Preussischen Akademie der Wissenschaften*.

[3] Landauer, R. (1961). "Irreversibility and Heat Generation in the Computing Process." *IBM Journal of Research and Development* 5(3): 183-191.

[4] Bekenstein, J.D. (1981). "Universal upper bound on the entropy-to-energy ratio for bounded systems." *Physical Review D* 23(2): 287.

[5] Marshall, M. et al. (2025). "Optical atomic clock comparison at the 10⁻¹⁹ level." *Nature Physics*.

### Cryptography

[6] Dwork, C., Naor, M. (1992). "Pricing via Processing or Combatting Junk Mail." *CRYPTO '92*. Springer, pp. 139-147.

[7] Lamport, L., Shostak, R., Pease, M. (1982). "The Byzantine Generals Problem." *ACM Transactions on Programming Languages and Systems* 4(3): 382-401.

[8] Fischer, M., Lynch, N., Paterson, M. (1985). "Impossibility of Distributed Consensus with One Faulty Process." *Journal of the ACM* 32(2): 374-382.

[9] Castro, M., Liskov, B. (1999). "Practical Byzantine Fault Tolerance." *OSDI '99*, pp. 173-186.

[10] Boneh, D., Bonneau, J., Bünz, B., Fisch, B. (2018). "Verifiable Delay Functions." *CRYPTO 2018*. Springer, pp. 757-788.

[11] Wesolowski, B. (2019). "Efficient Verifiable Delay Functions." *EUROCRYPT 2019*. Springer, pp. 379-407.

[12] Buchmann, J., Williams, H.C. (1988). "A key-exchange system based on imaginary quadratic fields." *Journal of Cryptology* 1: 107-118.

### Consensus

[13] Sompolinsky, Y., Zohar, A. (2015). "Secure High-Rate Transaction Processing in Bitcoin." *Financial Cryptography 2015*.

[14] Spiegelman, A., Giridharan, N., Sonnino, A., Kokoris-Kogias, L. (2022). "Bullshark: DAG BFT Protocols Made Practical." *ACM CCS 2022*.

[15] Danezis, G., Kokoris-Kogias, L., Sonnino, A., Spiegelman, A. (2022). "Narwhal and Tusk: A DAG-based Mempool and Efficient BFT Consensus." *EuroSys 2022*.

[16] Keidar, I., Kokoris-Kogias, L., Naor, O., Spiegelman, A. (2021). "All You Need is DAG." *PODC 2021*.

[17] Sompolinsky, Y., Zohar, A. (2018). "PHANTOM: A Scalable BlockDAG Protocol." *IACR Cryptology ePrint Archive* 2018/104.

[15] Yin, M., Malkhi, D., Reiter, M.K., Gueta, G.G., Abraham, I. (2019). "HotStuff: BFT Consensus with Linearity and Responsiveness." *PODC '19*, pp. 347-356.

### Standards

[16] NIST FIPS 202 (2015). "SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions."

[17] NIST FIPS 203 (2024). "Module-Lattice-Based Key-Encapsulation Mechanism Standard."

[18] NIST FIPS 204 (2024). "Module-Lattice-Based Digital Signature Standard."

[19] BIPM (2019). "The International System of Units (SI)." 9th edition.

### Time Synchronization

[20] Mills, D.L. (1991). "Internet Time Synchronization: The Network Time Protocol." *IEEE Transactions on Communications* 39(10): 1482-1493.

[21] Malhotra, A., Goldberg, S. (2016). "Attacking NTP's Authenticated Broadcast Mode." *ACM SIGCOMM Computer Communication Review* 46(2): 12-17.

### Montana

[22] Montana Technical Specification v3.7 (2026).

[23] Asymptotic Trust Consensus (ATC) v10 — Layers -1, 0, 1, 2 (2026).

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
