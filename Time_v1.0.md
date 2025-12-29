# Time: A Peer-to-Peer Electronic Cash System Based on Time

**Alejandro Montana**
alejandromontana@tutamail.com

---

## Abstract

A purely peer-to-peer version of electronic cash where consensus is based on time, not capital. The main problem with existing systems is that influence is proportional to money: in Proof of Work — to ASIC purchases, in Proof of Stake — to token holdings. We propose a system where the only resource that matters is time. Time cannot be bought, accelerated, or transferred. Run a node for 180 days — gain maximum influence. Your capital is irrelevant.

---

## 1. Introduction

Commerce on the Internet has evolved from trusted third parties to trustless consensus. Bitcoin solved the double-spending problem through Proof of Work. Ethereum added programmability through Proof of Stake. Both systems share a fundamental flaw: influence is bought with money.

In PoW, those who can afford more ASICs control the network. In PoS, those who hold more tokens control the network. The promise of decentralization collapses into plutocracy.

We need a system where:
- Influence cannot be purchased
- Entry barrier is zero
- Attack cost scales with time, not money

The solution is Proof of Time.

---

## 2. Time as Consensus

### 2.1 The Problem with Capital-Based Consensus

```
PoW:  Influence = f(Money → Hardware → Electricity)
PoS:  Influence = f(Money → Tokens)
PoT:  Influence = f(Time)
```

Time is the only resource distributed equally to all humans. One second for a billionaire equals one second for anyone else.

### 2.2 Verifiable Delay Functions

A Verifiable Delay Function (VDF) is a function that:
1. Requires sequential computation (cannot be parallelized)
2. Produces a proof that can be quickly verified
3. Has deterministic output

We use Wesolowski VDF:

```
y = x^(2^T) mod N
proof π = x^(2^T / l) mod N

where:
  T = number of iterations (time parameter)
  N = RSA modulus (2048-bit)
  l = hash-derived prime
```

Verification: `y = π^l · x^r mod N` where `r = 2^T mod l`

VDF guarantees that T sequential squarings were performed. No amount of money can speed this up — only time.

---

## 3. Dual-Layer Architecture

### 3.1 Layer 1: Proof of History (PoH)

Fast transaction layer. Sequential SHA-256 chain:

```
H(n) = SHA256(H(n-1) || data || timestamp)
```

- 1 hash per slot
- Transactions embedded in hash chain
- Provides ordering without consensus

### 3.2 Layer 2: Proof of Time (PoT)

Finality layer. VDF checkpoints every 600 seconds:

```
Checkpoint(n) = VDF(H(last_slot), T=1,000,000)
```

- Cannot be reverted after VDF completion
- 10-minute finality (like Bitcoin, but deterministic)
- Checkpoint = irreversible anchor

---

## 4. Leader Selection

### 4.1 ECVRF

Leader is selected via Elliptic Curve Verifiable Random Function:

```
(β, π) = VRF_prove(sk, seed)
VRF_verify(pk, seed, β, π) → {0, 1}
```

Where:
- `seed` = previous checkpoint hash
- `β` = pseudo-random output
- `π` = proof of correct computation

### 4.2 Selection Probability

```
P(node_i) = Adonis(i) / Σ Adonis(all)

Selected if: β < P(node_i) × 2^256
```

The Adonis score determines selection probability.

---

## 5. The Five Fingers of Adonis

Node weight is computed from five dimensions. Like fingers on a hand — each has a role.

### 5.1 Formula

```
Adonis(i) = Σ(w_d × score_d) for d in {TIME, INTEGRITY, STORAGE, GEOGRAPHY, HANDSHAKE}
```

### 5.2 Dimensions

| Finger | Dimension | Weight | Saturation |
|--------|-----------|--------|------------|
| Thumb | TIME | 50% | 180 days uptime |
| Index | INTEGRITY | 20% | No violations |
| Middle | STORAGE | 15% | 100% chain history |
| Ring | GEOGRAPHY | 10% | Country + city diversity |
| Pinky | HANDSHAKE | 5% | 10 mutual trust bonds |

### 5.3 TIME (Thumb) — 50%

```
score_time = min(uptime_seconds / 15,552,000, 1.0)
```

15,552,000 seconds = 180 days. After 180 days, newcomer equals veteran.

TIME is the thumb. Without it, the hand cannot grasp.

### 5.4 INTEGRITY (Index) — 20%

Behavioral score. Positive actions increase, violations decrease:

```
BLOCK_PRODUCED:  +0.05
BLOCK_VALIDATED: +0.02
BLOCK_INVALID:   -0.15
EQUIVOCATION:    -1.0 + 180-day quarantine
```

Double protection: score reduction AND time penalty.

### 5.5 STORAGE (Middle) — 15%

```
score_storage = min(stored_blocks / total_blocks, 1.0)
```

Full nodes store complete history. Light nodes get proportional score.

### 5.6 GEOGRAPHY (Ring) — 10%

```
country_score = 0.6 × (1 / (1 + log10(nodes_in_country))) + 0.4 × (countries / 50)
city_score = 0.7 × (1 / (1 + log10(nodes_in_city))) + 0.3 × (cities / 100)
geography = 0.6 × country_score + 0.4 × city_score
```

First node from new country: +0.25 bonus.
First node from new city: +0.15 bonus.

Fewer nodes in your location = higher score. Incentivizes global distribution.

### 5.7 HANDSHAKE (Pinky) — 5%

Elite bonus. Two veterans shake hands = cryptographic proof of mutual trust.

Requirements:
- TIME ≥ 90%
- INTEGRITY ≥ 80%
- STORAGE ≥ 90%
- GEOGRAPHY > 10%
- Different countries (anti-sybil)

```
score_handshake = min(handshake_count / 10, 1.0)
```

The pinky completes the hand.

---

## 6. DAG Structure

### 6.1 Block References

Each block references 1-8 parent blocks:

```
Block {
  parents: [hash_1, hash_2, ..., hash_k]  // k ∈ [1, 8]
  transactions: [...]
  vrf_proof: π
  timestamp: t
}
```

### 6.2 PHANTOM-PoT Ordering

Blocks are ordered by:
1. VDF checkpoint anchors
2. Topological sort within checkpoint window
3. Tie-breaking via block hash

Horizontal scaling: more parents = higher throughput.

---

## 7. Economics

### 7.1 Unit

```
1 Ɉ = 1 second of time
```

The native token is **Ɉ** (pronounced "time"). One Ɉ equals one second.

```
1 minute  = 60 Ɉ
1 hour    = 3,600 Ɉ
1 day     = 86,400 Ɉ
1 year    = 31,536,000 Ɉ
```

### 7.2 Emission

```
Total supply: 21,000,000 minutes = 1,260,000,000 Ɉ
Block time: 10 minutes
Initial reward: 50 minutes = 3,000 Ɉ per block
Halving: every 210,000 blocks (~4 years)
Full emission: ~132 years
```

Emission schedule:

| Epoch | Blocks | Reward | Emitted |
|-------|--------|--------|---------|
| 0 | 0 - 209,999 | 50 min (3,000 Ɉ) | 630,000,000 Ɉ |
| 1 | 210,000 - 419,999 | 25 min (1,500 Ɉ) | 315,000,000 Ɉ |
| 2 | 420,000 - 629,999 | 12.5 min (750 Ɉ) | 157,500,000 Ɉ |
| ... | ... | ... | ... |
| 33 | 6,930,000+ | 0 | — |

Same curve as Bitcoin. Predictable, deflationary.

---

## 8. Privacy Tiers

| Tier | Hidden | Size | Fee Multiplier |
|------|--------|------|----------------|
| T0 | Nothing | 250 B | 1× |
| T1 | Receiver (stealth address) | 400 B | 2× |
| T2 | + Amount (Pedersen commitment) | 1.2 KB | 5× |
| T3 | + Sender (ring signature) | 2.5 KB | 10× |

Privacy is optional. User chooses transparency vs. anonymity.

---

## 9. Attack Analysis

### 9.1 Sybil Attack

Creating N fake nodes:
- Each needs 180 days to reach TIME saturation
- No shortcut. N nodes = N × 180 days

Cost: `attack_time = N × 180 days`

### 9.2 51% Attack

To control 51% of Adonis weight:
- Need 51% of TIME-weighted nodes
- With 1000 existing nodes at 180 days: need 1020 nodes running 180 days

Cost: `1020 × 180 = 183,600 node-days`

Compare:
- Bitcoin 51% attack: ~$20B in hardware
- Ethereum 51% attack: ~$10B in stake
- Proof of Time 51% attack: N × 180 days (cannot be bought)

### 9.3 Long-Range Attack

VDF checkpoints are irreversible. Rewriting history requires:
1. Recomputing all VDFs from fork point
2. Each VDF takes real time
3. Honest chain always ahead

Not feasible.

---

## 10. Comparison

| Property | Bitcoin | Ethereum | Proof of Time |
|----------|---------|----------|---------------|
| Consensus | PoW | PoS | VDF + Time |
| Influence | Money→ASIC | Money→Stake | Time only |
| Entry cost | High | Medium | Zero |
| Energy | Massive | Low | Minimal |
| 51% attack cost | $20B | $10B | N × 180 days |
| Finality | Probabilistic | ~15 min | 10 min (deterministic) |

---

## 11. Conclusion

We have proposed a system for electronic transactions that does not rely on capital for consensus. Time is the only resource that cannot be bought, accelerated, or transferred.

The network self-organizes through the Five Fingers of Adonis:
- TIME ensures long-term commitment
- INTEGRITY removes bad actors
- STORAGE maintains data availability
- GEOGRAPHY enforces global distribution
- HANDSHAKE creates trust networks

The result is a system where:
- Everyone starts equal
- Influence is earned, not bought
- Attacks require time, not money
- Decentralization is incentivized, not just promised

In time, we are all equal.

---

## References

1. Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.
2. Wesolowski, B. (2019). Efficient Verifiable Delay Functions.
3. Boneh, D., et al. (2018). Verifiable Delay Functions.
4. Sompolinsky, Y., Zohar, A. (2015). PHANTOM: A Scalable BlockDAG Protocol.
5. Micali, S., Rabin, M., Vadhan, S. (1999). Verifiable Random Functions.

---

**Ɉ**
