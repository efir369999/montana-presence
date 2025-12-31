# Ɉ Montana: Time-Proven Human Temporal Currency

<div style="text-align: center; margin: 0.5em 0;">

Alejandro Montana

alejandromontana@tutamail.com

December 31, 2025

</div>

---

<div style="text-align: justify;">

**Abstract.** A peer-to-peer quantum-resistant electronic cash system based on Proof of Time (PoT). Existing consensus mechanisms—Proof of Work and Proof of Stake—scale influence through purchasable resources, concentrating power in capital owners. Ɉ Montana ($MONT) replaces resource expenditure with temporal presence.

**PoT:ATC (Proof of Time: Atomic Time Consensus)** implements a three-layer temporal verification system anchored to Bitcoin's immutable timeline. Layer 0 queries 34 global atomic clocks using W-MSR Byzantine consensus. Layer 1 computes sequential VDF proofs with STARK verification. Layer 2 anchors to Bitcoin block hashes, using halving epochs as time oracle.

**Three-Layer Participation** democratizes access: Server nodes (50% weight) provide constant heartbeat streams; Telegram Bot (30% weight) enables frequency-based participation; Users (15% weight) play "Chico Time"—a gamified time verification challenge. Creating N fake identities costs N × 4 years.

**Post-quantum cryptography** (SPHINCS+, SHA3-256, ML-KEM-768) ensures long-term security. The **Five Fingers of Adonis** reputation system and **Twelve Apostles** trust bonds provide Sybil resistance without plutocratic capture.

Time cannot be bought—only spent. Humanity cannot be faked—only proven.

</div>

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [The Plutocracy Problem](#2-the-plutocracy-problem)
3. [Proof of Time Consensus](#3-proof-of-time-consensus)
4. [Three-Layer Participation](#4-three-layer-participation)
5. [The Five Fingers of Adonis](#5-the-five-fingers-of-adonis)
6. [The Twelve Apostles](#6-the-twelve-apostles)
7. [HAL: Human Analyse Language](#7-hal-human-analyse-language)
8. [Tokenomics](#8-tokenomics)
9. [Post-Quantum Security](#9-post-quantum-security)
10. [Attack Resistance](#10-attack-resistance)
11. [Implementation](#11-implementation)
12. [Conclusion](#12-conclusion)

---

## 1. Introduction

The cypherpunk movement envisioned cryptographic systems that shift power from institutions to individuals. Bitcoin delivered a monetary system without central authority. But Bitcoin's consensus mechanism contains a flaw that becomes more apparent with time: influence scales with capital.

Proof of Work requires specialized hardware. A participant with capital purchases ASICs and controls hashrate proportional to investment. Proof of Stake makes this explicit—stake coins, receive influence. Both systems work. Both systems concentrate power.

True decentralization requires a resource that cannot be accumulated, purchased, or transferred.

**Time is that resource.**

A node operating through a full Bitcoin halving cycle (210,000 blocks, ~4 years) accumulates the same influence whether owned by a billionaire or a student. This time is measured in Bitcoin blocks, resets at each halving, and is irreversible.

### 1.1 The Quantum Threat

Current cryptographic systems face an existential threat: quantum computers. Shor's algorithm breaks ECDSA, RSA, and X25519.

Ɉ Montana implements quantum-resistant cryptography: SPHINCS+ (NIST FIPS 205), SHA3-256, SHAKE256.

### 1.2 The Humanity Problem

TIME proves existence, not uniqueness. An attacker can create 100 keypairs, wait 4 years, and control a coordinated network.

HAL (Human Analyse Language) solves this: proving humanity, not just cryptographic identity.

Named after Hal Finney (1956-2014), who received the first Bitcoin transaction and understood Sybil resistance before anyone else. "Running bitcoin" — his first tweet, January 2009.

---

## 2. The Plutocracy Problem

All existing consensus mechanisms suffer from the same fundamental weakness: resource dependence creates plutocratic capture.

| Mechanism | Resource | Problem |
|-----------|----------|---------|
| PoW | Hashrate (ASICs) | Capital → Hardware → Power |
| PoS | Staked coins | Capital → Stake → Power |
| DPoS | Votes | Capital → Votes → Power |
| **PoT** | **Time** | **Time → Equal opportunity** |

**The solution is to build consensus on resources that cannot be unequally distributed.**

- **Time** passes for everyone at the same rate. This is physics.
- **Humanity** cannot be multiplied. One person = one human.

---

## 3. Proof of Time Consensus

PoT:ATC (Proof of Time: Atomic Time Consensus) implements three temporal layers:

### 3.1 Layer 0: Global Atomic Time

Physical time from 34 NTP sources across 8 geographic regions:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 0: GLOBAL ATOMIC TIME                                │
├─────────────────────────────────────────────────────────────┤
│  34 NTP sources across 8 regions                            │
│  W-MSR Byzantine consensus (f=5 fault tolerance)            │
│  Requirement: n ≥ 3f+1 = 16 sources minimum                 │
│  Actual requirement: ≥18 sources, ≥5 regions                │
└─────────────────────────────────────────────────────────────┘
```

**W-MSR Algorithm (Weighted-Mean Subsequence Reduced):**
1. Sort all n timestamps
2. Remove f smallest and f largest (trimming)
3. Compute weighted mean of remaining n-2f values
4. Weights: stratum × RTT × region_diversity

No cryptographic proof required—atomic time is physical reality from cesium-133 transitions.

### 3.2 Layer 1: VDF (Verifiable Delay Function)

Sequential computation that cannot be parallelized:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: VDF + STARK                                       │
├─────────────────────────────────────────────────────────────┤
│  SHAKE256 sequential hashing                                │
│  16,777,216 iterations (~2.5 seconds)                       │
│  STARK proof for O(log n) verification                      │
│  Checkpoints every 1000 iterations                          │
└─────────────────────────────────────────────────────────────┘
```

**VDF proves time passage**—the only way to compute the output is to perform sequential operations that take wall-clock time.

### 3.3 Layer 2: Bitcoin Anchor

Bitcoin block hashes provide global time consensus:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: BITCOIN ANCHOR                                    │
├─────────────────────────────────────────────────────────────┤
│  Multi-API consensus (4 endpoints)                          │
│  Halving epochs as time oracle                              │
│  Epoch 0: blocks 0-209,999                                  │
│  Epoch 1: blocks 210,000-419,999                            │
│  Current epoch: 4 (block ~850,000)                          │
└─────────────────────────────────────────────────────────────┘
```

Bitcoin's proof-of-work provides the most secure global timestamp in existence.

---

## 4. Three-Layer Participation

Montana introduces gamified participation to maximize accessibility:

```
┌─────────────────────────────────────────────────────────────┐
│  MONTANA PARTICIPATION LAYERS                               │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: SERVER    │ Weight 0.50 │ Constant stream        │
│  Layer 1: BOT       │ Weight 0.30 │ Depends on frequency   │
│  Layer 2: USER      │ Weight 0.15 │ Manual time choice     │
│  Layer 3: RESERVED  │ Weight 0.05 │ Future extension       │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Layer 0: Server (50%)

Full node operators provide constant heartbeat streams. They run the consensus protocol, validate blocks, and maintain the network. Highest responsibility, highest weight.

### 4.2 Layer 1: Bot (30%)

Telegram bot integration enables lightweight participation. Users interact with the bot at chosen frequencies (1 minute to 1 day intervals). More frequent interaction = higher participation score.

### 4.3 Layer 2: User (15%)

**"Сколько на твоих часах, Чико?"** (What time is it on your watch, Chico?)

The Chico Time game presents 5 time options:

```
[12:34]  [12:36]  [12:38]  [12:40]  [12:42]

Correct answer: ±2 minutes from actual atomic time
Reward: Participation points for the layer
```

This gamified approach:
- Proves human presence (bots struggle with time verification)
- Engages users in the time consensus
- Creates viral Telegram mechanics similar to Hamster Kombat

---

## 5. The Five Fingers of Adonis

Reputation system using five-dimensional assessment:

```
┌─────────────────────────────────────────────────────────────┐
│  THE FIVE FINGERS OF ADONIS                                 │
├─────────────────────────────────────────────────────────────┤
│  THUMB:  TIME       │ 50% │ Blocks in network             │
│  INDEX:  INTEGRITY  │ 20% │ No protocol violations        │
│  MIDDLE: STORAGE    │ 15% │ Chain history stored          │
│  RING:   EPOCHS     │ 10% │ Bitcoin halvings survived     │
│  PINKY:  HANDSHAKE  │  5% │ 12 Apostles trust bonds       │
└─────────────────────────────────────────────────────────────┘
```

### 5.1 THUMB: TIME (50%)

The dominant factor. Saturates at 210,000 Bitcoin blocks (~4 years). **Resets at each halving.**

```python
def compute_time_score(btc_height: int, first_seen_height: int) -> float:
    blocks_in_epoch = btc_height % HALVING_INTERVAL
    return min(blocks_in_epoch / HALVING_INTERVAL, 1.0)
```

### 5.2 INDEX: INTEGRITY (20%)

No protocol violations. Decreases with misbehavior.

```python
def compute_integrity_score(violations: int) -> float:
    return max(0.0, 1.0 - violations * 0.1)
```

### 5.3 MIDDLE: STORAGE (15%)

Percentage of chain history stored.

### 5.4 RING: EPOCHS (10%)

Bitcoin halvings survived. Maximum score at 4 halvings (16 years).

### 5.5 PINKY: HANDSHAKE (5%)

Mutual trust bonds via the 12 Apostles system.

---

## 6. The Twelve Apostles

Each node chooses exactly 12 trust partners.

```
Trust Manifesto:
Before forming a handshake, ask yourself:

  Do I know this person?
  Not an avatar — a human.

  Do I trust them with my time?
  Willing to lose if they fail?

  Do I wish them longevity?
  Want them here for years?

  If any answer is NO — do not shake.
```

### 6.1 Seniority Bonus

Older nodes vouching for newer nodes carries more weight:

```python
def compute_handshake_value(my_number: int, partner_number: int) -> float:
    # Node #1000 shakes #50:  value = 1 + log10(1000/50) = 2.30
    # Node #1000 shakes #999: value = 1 + log10(1000/999) = 1.00
    if partner_number < my_number and partner_number > 0:
        return 1.0 + math.log10(my_number / partner_number)
    return 1.0
```

### 6.2 Collective Slashing

Attack the network, lose your friends:

```python
ATTACKER_QUARANTINE_BLOCKS = 180_000  # ~3 years
VOUCHER_INTEGRITY_PENALTY = 0.25      # -25% for those who vouched
ASSOCIATE_INTEGRITY_PENALTY = 0.10    # -10% for those vouched by attacker
```

---

## 7. HAL: Human Analyse Language

HAL = Human Analyse Language. Named after Hal Finney (1956-2014).

Proof of Human, not just Proof of Time.

### 7.1 Graduated Trust Model

```
┌─────────────────────────────────────────────────────────────┐
│  HAL HUMANITY TIERS                                         │
├─────────────────────────────────────────────────────────────┤
│  Tier 1: HARDWARE    │ 3 apostles  │ TPM/FIDO2 attestation │
│  Tier 2: SOCIAL      │ 6 apostles  │ Social graph bonds    │
│  Tier 3: TIME-LOCKED │ 12 apostles │ Bitcoin halving proof │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Sybil Economics

| Tier | Sybil Cost per Identity |
|------|------------------------|
| HARDWARE | $50-500 (physical device) |
| SOCIAL | Months/years (real connections) |
| TIME-LOCKED | 4+ years (Bitcoin halving) |

**At Tier 3: 100 fake identities = 400 years of waiting.**

---

## 8. Tokenomics

### 8.1 Supply Parameters

```python
# Identity
NAME = "Montana"
SYMBOL = "Ɉ"
TICKER = "$MONT"

# Supply
TOTAL_SUPPLY = 1_260_000_000      # 21 million minutes in seconds
# 1 Ɉ = 1 second
# 60 Ɉ = 1 minute
# 3600 Ɉ = 1 hour
# 86400 Ɉ = 1 day

# Emission
INITIAL_REWARD = 3000             # 50 minutes per block
HALVING_INTERVAL = 210_000        # Blocks per epoch (~4 years)
BLOCK_TIME = 600                  # 10 minutes
```

### 8.2 Emission Schedule

| Era | Block Reward | Cumulative Supply |
|-----|--------------|-------------------|
| 1 | 50 minutes (3000 Ɉ) | 630,000,000 Ɉ |
| 2 | 25 minutes (1500 Ɉ) | 945,000,000 Ɉ |
| 3 | 12.5 minutes (750 Ɉ) | 1,102,500,000 Ɉ |
| 4 | 6.25 minutes (375 Ɉ) | 1,181,250,000 Ɉ |

**Full emission: ~132 years (33 halvings)**

### 8.3 Time as Value

```
"Time is the only true currency.
 Everyone receives 86,400 seconds per day.
 No one can buy more. No one can save it.
 You can only spend it."

                    — Alejandro Montana
```

---

## 9. Post-Quantum Security

Complete quantum-resistant cryptographic stack following NIST standards:

| Function | Algorithm | Standard | Security |
|----------|-----------|----------|----------|
| Signatures | SPHINCS+-SHAKE-128f | NIST FIPS 205 | 128-bit PQ |
| Hashing | SHA3-256 | NIST FIPS 202 | 128-bit PQ |
| VDF | SHAKE256 | NIST FIPS 202 | 128-bit PQ |
| Key Exchange | ML-KEM-768 | NIST FIPS 203 | 128-bit PQ |

**SPHINCS+ signature size: 17,088 bytes** (vs 64 bytes for Ed25519)

This is a trade-off: larger signatures for quantum resistance.

---

## 10. Attack Resistance

### 10.1 Attack Vector Matrix

| Attack | Difficulty | Mitigation |
|--------|------------|------------|
| Flash Takeover | IMPOSSIBLE | 210,000 BTC blocks (~4 years) saturation |
| Slow Takeover | VERY HARD | Behavioral correlation + 33% cluster cap |
| Sybil via Keypairs | VERY HARD | HAL Humanity System (N × 4 years) |
| Fake Apostle Network | HARD | Humanity tier limits (3/6/12) |
| Hardware Spoofing | HARD | Multiple attestation sources |
| Quantum Attack | IMPOSSIBLE | SPHINCS+, SHA3, SHAKE256 |
| Eclipse Attack | BLOCKED | Minimum 8 outbound connections |

### 10.2 Anti-Cluster Protection

**No cluster can exceed 33% of network influence.**

```python
MAX_CLUSTER_INFLUENCE = 0.33
MAX_CORRELATION_THRESHOLD = 0.7
MIN_NETWORK_ENTROPY = 0.5
```

---

## 11. Implementation

### 11.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ɉ MONTANA                                │
├─────────────────────────────────────────────────────────────┤
│  Telegram Bot  │  Node  │  API  │  Storage                 │
├─────────────────────────────────────────────────────────────┤
│                    PoT v6 Library                           │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐       │
│  │ Layer 0 │ Layer 1 │ Layer 2 │ Crypto  │ State   │       │
│  │ Atomic  │ VDF     │ Bitcoin │ SPHINCS+│ Machine │       │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 Telegram Bot Commands

```
/start     - Register account, generate keypair
/time      - Play "Chico Time" game
/balance   - Check Ɉ balance
/send      - Send Ɉ to another user
/apostles  - Manage 12 Apostles trust bonds
/stats     - View Five Fingers reputation
```

### 11.3 Running a Node

```bash
pip install montana
montana-node --run
```

---

## 12. Conclusion

### 12.1 Security Guarantees

1. **No instant takeover:** TIME resets at each halving
2. **Cluster cap:** No coordinated group exceeds 33% influence
3. **Quantum resistance:** SPHINCS+, SHA3, SHAKE256
4. **Sybil resistance:** N fake identities = N × 4 years
5. **Time-locked identity:** Bitcoin halving anchors cannot be faked
6. **Collective accountability:** 12 Apostles + slashing
7. **Bitcoin-anchored time:** 3 layers with VDF fallback
8. **Gamified access:** Telegram bot democratizes participation

### 12.2 Final Statement

Ɉ Montana removes capital as the basis of influence. The system uses:
- **Time** — cannot be purchased, accelerated, or concentrated
- **Humanity** — cannot be multiplied across Bitcoin halvings

With quantum-resistant cryptography and the HAL Humanity System, these guarantees extend indefinitely into the future.

---

*"Running bitcoin" — Hal Finney, January 2009*

*"Time is priceless. Humanity is sacred. Now both have cryptographic proof."*

**Ɉ**

---

## References

[1] S. Nakamoto, "Bitcoin: A Peer-to-Peer Electronic Cash System," 2008.

[2] D. Boneh et al., "Verifiable Delay Functions," CRYPTO 2018.

[3] NIST FIPS 202, 203, 205 — Post-Quantum Standards, 2024.

[4] H. Finney, "RPOW - Reusable Proofs of Work," 2004.

[5] R. Dunbar, "How Many Friends Does One Person Need?" 2010.

[6] D. Dolev, "Authenticated algorithms for Byzantine agreement," 1981.

---

*Ɉ Montana Whitepaper v1.0*
*December 2025*
