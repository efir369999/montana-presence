# Ɉ Montana: A Peer-to-Peer Quantum-Resistant Temporal Currency

**Version 3.1**
**Alejandro Montana**
alejandromontana@tutamail.com
**December 2025**

---

## Abstract

A purely peer-to-peer electronic cash system would allow online payments without relying on financial institutions. Existing cryptocurrency solutions—Proof of Work and Proof of Stake—scale influence through purchasable resources, inevitably concentrating power in the hands of capital owners. We propose Ɉ Montana ($MONT), a currency built on Proof of Time consensus where influence accumulates through time presence rather than resource expenditure. The network timestamps blocks through sequential computation that cannot be parallelized or accelerated. Nodes compete for 21 million minutes of temporal asset distributed over 131 years.

**Version 3.0 additions:** Post-quantum cryptographic primitives following NIST standards:
- SPHINCS+ signatures (NIST FIPS 205) — hash-based, quantum-resistant
- SHA3-256 hashing (NIST FIPS 202) — Keccak, quantum-safe
- SHAKE256 VDF with STARK proofs — O(log T) verification, no trusted setup
- ML-KEM key encapsulation (NIST FIPS 203) — lattice-based key exchange
- Crypto-agility layer — runtime switching between legacy/PQ/hybrid backends

The protocol now provides long-term security against quantum computing threats.

**Version 3.1 additions:** Network security hardening for production readiness:
- Static IP validation — dynamic residential and CGNAT addresses blocked
- VPN/Proxy detection — ASN-based identification of anonymizing services
- Sybil protection — node registration only after validated block production
- Eclipse defense — minimum 8 outbound connections enforced
- Rate limiting — per-IP and per-subnet connection throttling
- Wallet encryption — minimum 8-character password requirement

Time cannot be bought, manufactured, or transferred—only spent.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [The Plutocracy Problem](#2-the-plutocracy-problem)
3. [Verifiable Delay Functions](#3-verifiable-delay-functions)
4. [Network Architecture](#4-network-architecture)
5. [The Five Fingers of Adonis](#5-the-five-fingers-of-adonis)
6. [Anti-Cluster Protection](#6-anti-cluster-protection)
7. [Post-Quantum Cryptography](#7-post-quantum-cryptography)
8. [Attack Resistance Analysis](#8-attack-resistance-analysis)
9. [Known Limitations](#9-known-limitations)
10. [Network Protocol](#10-network-protocol)
11. [Privacy](#11-privacy)
12. [Emission Schedule](#12-emission-schedule)
13. [Implementation](#13-implementation)
14. [Conclusion](#14-conclusion)

---

## 1. Introduction

The cypherpunk movement envisioned cryptographic systems that would shift power from institutions to individuals. Bitcoin delivered on part of that promise—a monetary system without central authority. But Bitcoin's consensus mechanism, while elegant, contains a flaw that becomes more apparent with time: influence scales with capital.

Proof of Work requires specialized hardware. A participant with capital purchases ASICs and controls hashrate proportional to investment. Proof of Stake makes this explicit—stake coins, receive influence. Both systems work. Both systems concentrate power.

What the cypherpunks sought was not merely decentralized currency, but decentralized power. True decentralization requires a resource that cannot be accumulated, purchased, or transferred.

**Time is that resource.**

A node operating for 180 days accumulates the same influence whether owned by a billionaire or a student. This time is irreversible. It cannot be bought on an exchange. It cannot be rented from a cloud provider. It can only be spent—by existing.

### 1.1 The Quantum Threat

Current cryptographic systems face an existential threat: quantum computers. Shor's algorithm, when executed on a sufficiently powerful quantum computer, breaks:

- **ECDSA/Ed25519:** Digital signatures used in Bitcoin, Ethereum, and most cryptocurrencies
- **RSA:** Public key encryption and VDF constructions
- **X25519:** Key exchange protocols

Conservative estimates place cryptographically-relevant quantum computers 10-15 years away. The "harvest now, decrypt later" attack model means adversaries may already be collecting encrypted data for future decryption.

**Ɉ Montana v3.0 implements quantum-resistant cryptography to ensure long-term security.**

---

## 2. The Plutocracy Problem

All existing consensus mechanisms suffer from the same fundamental weakness: resource dependence creates plutocratic capture.

In Proof of Work, hash rate is purchasable. The 2014 GHash.io incident demonstrated that a single mining pool could approach 51% of Bitcoin's hash rate. Today, mining is dominated by industrial operations in regions with cheap electricity. The barrier to meaningful participation exceeds the resources of ordinary individuals.

In Proof of Stake, the problem is structural. Stake requirements create minimum wealth thresholds for validation. Staking rewards compound existing holdings. The rich get richer—by design.

Delegated systems (DPoS) merely add intermediaries. Liquid staking creates derivatives that reconcentrate power. Every variation preserves the core issue: those with capital control consensus.

**The solution is not to redistribute resources more fairly within these systems. The solution is to build consensus on a resource that cannot be unequally distributed.**

Time passes for everyone at the same rate. One second for a nation-state equals one second for an individual. This is not policy. It is physics.

---

## 3. Verifiable Delay Functions

A Verifiable Delay Function (VDF) is a function that requires a specified number of sequential operations to compute, but whose output can be efficiently verified. The key property: **computation cannot be parallelized**.

### 3.1 Properties

For a VDF with difficulty parameter T:
- Computation requires O(T) sequential steps
- Verification requires O(log T) steps
- No amount of parallel processors reduces computation time

This creates cryptographic proof that time has passed.

### 3.2 Legacy Construction: Wesolowski VDF

The original network uses Wesolowski's VDF construction over RSA groups:

```
Parameters:
  N = 2048-bit RSA modulus (product of safe primes p, q)
  T = iteration count (calibrated to ~9 minutes on reference hardware)
  H = SHA-256 hash function

Compute(x, T):
  y = x^(2^T) mod N          # Sequential squaring
  l = H(x || y) mod N        # Challenge
  π = x^(⌊2^T / l⌋) mod N    # Proof
  return (y, π)

Verify(x, y, π, T):
  l = H(x || y) mod N
  r = 2^T mod l
  return y == π^l × x^r mod N
```

**Quantum Vulnerability:** Shor's algorithm factors N in polynomial time, breaking the underlying RSA assumption.

### 3.3 Post-Quantum Construction: SHAKE256 VDF

Version 3.0 introduces a hash-based VDF construction:

```
Parameters:
  H = SHAKE256 (extendable-output function)
  T = iteration count

Compute(x, T):
  state₀ = x
  for i = 1 to T:
    stateᵢ = H(stateᵢ₋₁)
  return stateₜ

Verify(x, y, proof, T):
  return STARK_verify(x, y, proof, T)
```

**Quantum Resistance:** SHAKE256 security relies only on hash function properties. Grover's algorithm provides at most √N speedup, reducing 256-bit security to 128-bit—still computationally infeasible.

### 3.4 STARK Proofs for VDF Verification

STARK (Scalable Transparent ARguments of Knowledge) enables O(log T) verification:

```
AIR Constraints:
  Transition: state[i+1] = SHAKE256(state[i])
  Boundary: state[0] = input, state[T] = output

Properties:
  - Proof size: ~50-200 KB
  - Verification: O(log T) operations
  - Transparent: No trusted setup
  - Quantum-safe: Hash-based
```

### 3.5 VDF Synchronization

Each VDF proof depends on the hash of the previous block:

```
VDF_input = SHA3-256(prev_block_hash || height)
VDF_output = Compute(VDF_input, T)
```

Pre-computation is impossible because `prev_block_hash` is unknown until the previous block is finalized. This creates a cryptographic chain of time proofs.

### 3.6 Iteration Calibration

```python
# Reference hardware: Intel i7-10700K
BASE_IPS = 15_000_000  # Iterations per second

# Target VDF compute time: 9 minutes (540 seconds)
TARGET_SECONDS = 540

# Iterations = IPS × target_time / 2 (two phases: compute + prove)
T = BASE_IPS * TARGET_SECONDS / 2  # ≈ 4 billion iterations
```

**Bounds:**
- Minimum: 1,000 iterations (testing)
- Maximum: 10^11 iterations (safety limit)

---

## 4. Network Architecture

### 4.1 Dual-Layer Consensus

**Layer 1 — Proof of History (PoH)**

Sequential SHA3-256 chain for transaction ordering:

```
PoH_n = SHA3-256(PoH_{n-1} || tx_hash || timestamp)
```

Provides sub-second transaction ordering without consensus overhead.

**Layer 2 — Proof of Time (PoT)**

VDF checkpoints every 10 minutes provide finality:

```
Block_n = {
  poh_chain: [PoH entries since last block],
  vdf_proof: Compute(prev_block_hash, T),
  leader_vrf: VRF_prove(sk, prev_block_hash),
  transactions: [...],
  signature: Sign(sk, block_hash)
}
```

### 4.2 Leader Selection

Every 10 minutes, one node is selected to produce a block using ECVRF (legacy) or hash-based VRF (post-quantum):

```
VRF_input = SHA3-256(prev_block_hash || height)
(π, β) = VRF_prove(secret_key, VRF_input)

# β is uniformly distributed in [0, 2^256)
# Node is leader if: β < threshold × 2^256
# where threshold = P_i (node's probability)
```

### 4.3 Node Probability Formula

```
P_i = (w_time × f_time + w_integrity × f_integrity + w_storage × f_storage
     + w_geography × f_geography + w_handshake × f_handshake) / Z
```

Where Z normalizes probabilities to sum to 1.

**Version 3.0 Weights (Five Fingers of Adonis):**

| Dimension | Weight | Description |
|-----------|--------|-------------|
| TIME | 50% | Continuous uptime |
| INTEGRITY | 20% | No protocol violations |
| STORAGE | 15% | Chain history stored |
| GEOGRAPHY | 10% | Location diversity |
| HANDSHAKE | 5% | Veteran trust bonds |

### 4.4 Minimum Network Requirements

- **Minimum nodes:** 3 (theoretical), 50+ (recommended)
- **Block time:** 10 minutes (VDF checkpoint interval)
- **Leader timeout:** 12 minutes (fallback to next candidate)
- **Finality:** 1 confirmation (VDF proof is deterministic)

---

## 5. The Five Fingers of Adonis

The Adonis reputation system replaces the simple three-factor model with a comprehensive five-dimensional assessment.

### 5.1 THUMB: TIME (50%)

The dominant factor. Saturates at 180 days of continuous uptime.

```python
f_time(t) = min(t / K_TIME, 1.0)
# where K_TIME = 180 days = 15,552,000 seconds
```

**Rationale:** Time is the core innovation. It cannot be purchased, accelerated, or transferred. 180 days provides sufficient barrier against flash attacks while remaining achievable for new participants.

### 5.2 INDEX: INTEGRITY (20%)

No protocol violations. Decreases with misbehavior.

```python
f_integrity = 1.0 - penalty_accumulation

# Penalties:
# - Block invalid: -0.15
# - VRF invalid: -0.20
# - VDF invalid: -0.25
# - Equivocation: -1.0 (catastrophic)
# - Spam detected: -0.20
```

**Recovery:** Penalties decay over time. Equivocation results in 180-day quarantine.

### 5.3 MIDDLE: STORAGE (15%)

Percentage of chain history stored. Full nodes preferred.

```python
f_storage(s) = min(s / K_STORAGE, 1.0)
# where K_STORAGE = 1.0 (100% of chain)
# Effective threshold: 80% for full participation
```

### 5.4 RING: GEOGRAPHY (10%)

Location diversity bonus. First node from a country/city receives bonus.

```python
f_geography = 0.6 × country_rarity + 0.4 × country_diversity

country_rarity = 1.0 / (1.0 + log10(nodes_in_country))
country_diversity = min(1.0, total_countries / 50)
```

**Privacy:** Only country code and city hash stored. Raw IP never persisted.

**Important Limitation:** Geographic verification relies on IP geolocation, which can be spoofed with VPNs. This is acknowledged as the weakest dimension. See [Section 9](#9-known-limitations).

### 5.5 PINKY: HANDSHAKE (5%)

Mutual trust bonds between veteran nodes.

```python
f_handshake = min(handshake_count / K_HANDSHAKE, 1.0)
# where K_HANDSHAKE = 10
```

**Handshake Requirements:**
1. Both nodes have TIME ≥ 90% (162+ days)
2. Both nodes have INTEGRITY ≥ 80%
3. Both nodes have STORAGE ≥ 90%
4. Both nodes have registered geography
5. Nodes are in DIFFERENT countries
6. Nodes have correlation < 50% (v2.0)
7. Nodes are not in same detected cluster (v2.0)

### 5.6 Aggregate Score Computation

```python
def compute_adonis_score(node):
    # Base scores
    scores = {
        TIME: min(uptime / K_TIME, 1.0),
        INTEGRITY: get_integrity_score(node),
        STORAGE: min(stored / total, 1.0),
        GEOGRAPHY: get_geography_score(node),
        HANDSHAKE: min(handshakes / 10, 1.0)
    }

    # Weighted aggregate
    weights = {TIME: 0.50, INTEGRITY: 0.20, STORAGE: 0.15,
               GEOGRAPHY: 0.10, HANDSHAKE: 0.05}

    score = sum(w * scores[d] for d, w in weights.items())

    # Apply penalties
    if node.is_penalized:
        score *= 0.1  # 90% reduction

    # Apply cluster penalty (v2.0)
    score *= get_cluster_penalty(node)

    # Apply entropy decay (v2.0)
    score *= get_entropy_decay_factor()

    return score
```

---

## 6. Anti-Cluster Protection

Defense against the "Slow Takeover Attack."

### 6.1 The Slow Takeover Attack

**Threat Model:**

An attacker deploys N nodes across VPN endpoints. Each node operates honestly for 180 days, accumulating maximum TIME score. At T+180, the attacker controls N saturated nodes with combined influence potentially exceeding 51%.

**Attack Timeline:**
```
Day 0:   Deploy 100 nodes across VPNs
Day 90:  Each node at 50% TIME
Day 180: All nodes at 100% TIME
Result:  Attacker controls significant influence
```

This attack is patient, distributed, and cannot be prevented by TIME saturation alone.

### 6.2 Behavioral Correlation Detection

The ClusterDetector analyzes node behavior to identify coordination:

```python
class ClusterDetector:
    def compute_correlation(self, node_a, node_b):
        # 1. Timing correlation (50% weight)
        # Actions within 100ms = suspicious
        timing_corr = count_simultaneous() / total_actions

        # 2. Action distribution (30% weight)
        # Same block/vote/relay ratios
        dist_corr = cosine_similarity(actions_a, actions_b)

        # 3. Block height patterns (20% weight)
        # Acting at identical heights
        height_corr = jaccard_similarity(heights_a, heights_b)

        return 0.5*timing + 0.3*dist + 0.2*height
```

**Detection Thresholds:**
```python
MAX_CORRELATION_THRESHOLD = 0.7   # 70% = suspicious
TIMING_VARIANCE_THRESHOLD = 100   # 100ms = synchronized
CORRELATION_WINDOW = 86400        # 24-hour analysis window
```

### 6.3 Correlation Penalty

Nodes with high correlation receive score reduction:

```python
CORRELATION_PENALTY_FACTOR = 0.5  # 50% maximum reduction

def get_cluster_penalty(node):
    correlation = get_max_correlation(node)

    if correlation < 0.7:
        return 1.0  # No penalty

    # Linear penalty from 0.7 to 1.0 correlation
    penalty = 1.0 - (correlation - 0.7) * 0.5 / 0.3
    return max(0.5, penalty)
```

### 6.4 Global Cluster Cap

**No cluster can exceed 33% of network influence.**

```python
MAX_CLUSTER_INFLUENCE = 0.33

def apply_cluster_cap(probabilities, clusters):
    for cluster in clusters:
        cluster_share = sum(prob[n] for n in cluster.members)

        if cluster_share > MAX_CLUSTER_INFLUENCE:
            reduction = MAX_CLUSTER_INFLUENCE / cluster_share
            for node in cluster.members:
                probabilities[node] *= reduction

    return probabilities
```

**Rationale:** Even if attackers evade correlation detection through random delays, their combined influence is hard-capped at 33%. Byzantine fault tolerance requires >2/3 honest participation; this cap ensures attackers cannot reach 1/3.

### 6.5 Entropy Monitoring

Network diversity health tracking:

```python
def compute_entropy():
    # Geographic diversity (40%)
    geo = gini_entropy(country_distribution)

    # City diversity (25%)
    city = gini_entropy(city_distribution)

    # TIME variance (20%)
    time = variance_entropy(time_scores)

    # Handshake span (15%)
    handshake = country_span(trust_network)

    return 0.4*geo + 0.25*city + 0.2*time + 0.15*handshake
```

**When entropy < 0.5:**
- TIME accumulation slows (decay applied)
- Warning logged for operators
- Network considered "unhealthy"

```python
MIN_NETWORK_ENTROPY = 0.5
ENTROPY_DECAY_RATE = 0.001  # 0.1% per hour

def get_entropy_decay():
    if entropy >= MIN_NETWORK_ENTROPY:
        return 1.0

    hours_unhealthy = (now - decay_start) / 3600
    return max(0.1, exp(-ENTROPY_DECAY_RATE * hours_unhealthy))
```

### 6.6 Independence Verification

Handshakes require provable independence:

```python
def request_handshake(requester, target):
    # Geographic independence
    if same_country(requester, target):
        return False, "Same country"

    # Behavioral independence
    correlation = compute_correlation(requester, target)
    if correlation > 0.5:
        return False, f"Too correlated ({correlation:.0%})"

    # Cluster independence
    if in_same_cluster(requester, target):
        return False, "Same cluster"

    return True, "Independence verified"
```

---

## 7. Post-Quantum Cryptography

**New in v3.0:** Complete quantum-resistant cryptographic stack following NIST post-quantum standards.

### 7.1 Quantum Threat Timeline

| Algorithm | Classical Security | Quantum Status | Threat Timeline |
|-----------|-------------------|----------------|-----------------|
| Ed25519 | 128-bit | BROKEN by Shor | 10-15 years |
| RSA-2048 | 112-bit | BROKEN by Shor | 10-15 years |
| SHA-256 | 256-bit | 128-bit (Grover) | Secure |
| SPHINCS+-128f | 128-bit | SECURE | N/A |
| SHA3-256 | 256-bit | 128-bit (Grover) | Secure |

### 7.2 Crypto-Agility Architecture

```
                    ┌─────────────────────────────┐
                    │      CryptoProvider         │
                    │    (Abstract Interface)     │
                    └─────────────────────────────┘
                          │         │         │
           ┌──────────────┘         │         └──────────────┐
           ▼                        ▼                        ▼
    ┌───────────┐           ┌───────────┐           ┌───────────┐
    │  Legacy   │           │Post-Quantum│           │  Hybrid   │
    │           │           │           │           │           │
    │ Ed25519   │           │ SPHINCS+  │           │ Ed25519 + │
    │ SHA-256   │           │ SHA3-256  │           │ SPHINCS+  │
    │ Wesolowski│           │ SHAKE256  │           │           │
    └───────────┘           └───────────┘           └───────────┘
```

Runtime switching enables:
- Gradual migration from legacy to post-quantum
- Backward compatibility during transition
- Testing without network disruption

### 7.3 SPHINCS+ Signatures (NIST FIPS 205)

Hash-based signature scheme with conservative security assumptions.

```
Algorithm: SPHINCS+-SHAKE-128f

Properties:
  - Public key: 32 bytes
  - Secret key: 64 bytes
  - Signature: 17,088 bytes (~17 KB)
  - Security: 128-bit post-quantum

Signing:
  signature = SPHINCS_sign(secret_key, message)

Verification:
  valid = SPHINCS_verify(public_key, message, signature)
```

**Security Basis:** Security relies only on hash function properties (SHA3/SHAKE). No number-theoretic assumptions that quantum computers break.

**Trade-off:** Larger signatures (~17 KB vs 64 bytes for Ed25519) increase block size but provide quantum resistance.

### 7.4 SHA3-256 Hashing (NIST FIPS 202)

Keccak-based hash function replacing SHA-256:

```
Properties:
  - Output: 256 bits
  - Rate: 1088 bits
  - Capacity: 512 bits
  - Rounds: 24

Usage:
  block_hash = SHA3-256(block_header)
  merkle_root = SHA3-256(left || right)
  address = SHA3-256(public_key)
```

**Quantum Security:** Grover's algorithm reduces security from 256-bit to 128-bit—still computationally infeasible (2^128 operations).

### 7.5 SHAKE256 VDF

Quantum-resistant VDF construction:

```python
class SHAKE256VDF:
    STATE_SIZE = 32  # bytes
    CHECKPOINT_INTERVAL = 1000

    def compute(self, input, iterations):
        state = SHA3-256(input)
        checkpoints = [state]

        for i in range(iterations):
            if i % CHECKPOINT_INTERVAL == 0:
                checkpoints.append(state)
            state = SHAKE256(state)

        return state, checkpoints

    def verify_stark(self, input, output, proof, iterations):
        return STARK_verify(input, output, proof, iterations)
```

**Properties:**
- Sequential: Each iteration depends on previous
- Quantum-safe: SHAKE256 resistant to Grover
- Verifiable: O(log T) via STARK proofs

### 7.6 STARK Proofs

Scalable Transparent ARguments of Knowledge for VDF verification:

```
AIR (Algebraic Intermediate Representation):
  Constraint: next_state = SHAKE256(current_state)
  Boundary: state[0] = input, state[T] = output

Proof Generation:
  proof = STARK_prove(input, output, checkpoints, iterations)
  # Proof size: ~50-200 KB

Verification:
  valid = STARK_verify(input, output, proof, iterations)
  # Complexity: O(log T)
```

**Implementation:** Winterfell library (Rust) via PyO3 bindings.

### 7.7 ML-KEM Key Encapsulation (NIST FIPS 203)

Lattice-based key exchange replacing X25519:

```
Algorithm: ML-KEM-768 (Kyber)

Key Generation:
  (secret_key, public_key) = ML-KEM.keygen()

Encapsulation:
  (ciphertext, shared_secret) = ML-KEM.encapsulate(public_key)

Decapsulation:
  shared_secret = ML-KEM.decapsulate(secret_key, ciphertext)
```

Used for:
- P2P connection encryption
- Wallet key exchange
- Secure channel establishment

### 7.8 Post-Quantum VRF

Hash-based VRF construction for leader selection:

```python
def vrf_prove(secret_key, alpha):
    # Compute deterministic output
    beta = SHA3-256(secret_key || alpha || "vrf_output")

    # Generate proof (SPHINCS+ signature)
    proof = SPHINCS_sign(secret_key, alpha || beta)

    return beta, proof

def vrf_verify(public_key, alpha, beta, proof):
    return SPHINCS_verify(public_key, alpha || beta, proof)
```

**Properties:**
- Uniqueness: One output per input
- Pseudorandomness: Output indistinguishable from random
- Verifiability: Anyone can verify with public key

### 7.9 Hybrid Mode

Transition period supporting both signature types:

```python
class HybridSignature:
    def sign(self, message):
        ed25519_sig = Ed25519.sign(self.legacy_sk, message)
        sphincs_sig = SPHINCS.sign(self.pq_sk, message)
        return (ed25519_sig, sphincs_sig)

    def verify(self, message, signature):
        ed25519_valid = Ed25519.verify(self.legacy_pk, message, sig[0])
        sphincs_valid = SPHINCS.verify(self.pq_pk, message, sig[1])

        if self.require_both:
            return ed25519_valid and sphincs_valid
        return ed25519_valid or sphincs_valid
```

**Migration Strategy:**
1. Phase 1: Enable hybrid mode (both signatures)
2. Phase 2: Deprecation warnings for legacy-only
3. Phase 3: Require post-quantum signatures

### 7.10 Performance Impact

| Operation | Ed25519 | SPHINCS+-128f | Factor |
|-----------|---------|---------------|--------|
| Key Gen | <1 ms | ~50 ms | 50× |
| Sign | <1 ms | ~100 ms | 100× |
| Verify | <1 ms | ~10 ms | 10× |
| Signature | 64 B | 17,088 B | 267× |

**Block Size Impact:**

For 1000 transactions per block:
- Legacy: ~64 KB signatures
- Post-quantum: ~17 MB signatures

**Mitigations:**
- Signature aggregation (future work)
- Pruning old signatures
- Compression

---

## 8. Attack Resistance Analysis

### 8.1 Attack Vector Matrix

| Attack | Difficulty | Mitigation | Quantum-Safe |
|--------|------------|------------|--------------|
| Flash Takeover | IMPOSSIBLE | 180-day saturation | Yes |
| Slow Takeover | VERY HARD | Correlation + 33% cap | Yes |
| Geographic Sybil | HARD | Country + correlation | Yes |
| Handshake Infiltration | HARD | Independence check | Yes |
| Eclipse Attack | HARD | Subnet limits | Yes |
| Nothing-at-Stake | MODERATE | TIME investment | Yes |
| Timing Attack | MODERATE | Correlation detection | Yes |
| VPN Spoofing | EASY | Limited (10% weight) | Yes |
| Quantum Attack | IMPOSSIBLE | SPHINCS+, SHA3, SHAKE256 | Yes |
| Signature Forgery | IMPOSSIBLE | Hash-based signatures | Yes |

### 8.2 Flash Takeover Attack

**Attack:** Acquire resources, immediately gain 51% influence.

**Defense:** TIME dimension requires 180 days to saturate.

```
Day 0:   Attacker deploys nodes
         TIME score = 0%
         Cannot achieve majority influence

Day 180: TIME score reaches 100%
         But correlation detection active for 180 days
         Behavioral patterns analyzed
```

**Effectiveness:** 100% — Mathematically impossible to bypass time requirement.

### 8.3 Slow Takeover Attack

**Attack:** Deploy N nodes, wait 180 days, coordinate for majority.

**Defense:** Multi-layered:

1. **Correlation detection:** Synchronized actions flagged
2. **Cluster cap:** Combined influence ≤ 33%
3. **Entropy decay:** Homogeneous networks penalized
4. **Independence verification:** Cannot form handshakes within cluster

**Analysis:**

Even with 100 coordinated nodes:
- Behavioral correlation flags synchronized actions
- Cluster detection groups correlated nodes
- 33% cap applies regardless of cluster size
- Cannot form trust bonds with each other

**Effectiveness:** 95% — Sophisticated attackers with random delays may evade timing detection, but cap still applies.

### 8.4 Quantum Attack Resistance

**Signature Forgery:**
- Legacy: Shor's algorithm breaks Ed25519 in polynomial time
- Post-quantum: SPHINCS+ security based on hash functions; no known quantum speedup beyond Grover

**VDF Bypass:**
- Legacy: Shor's algorithm could factor RSA modulus
- Post-quantum: SHAKE256 iterations cannot be parallelized; no quantum speedup for sequential hashing

**Key Recovery:**
- Legacy: Quantum computer recovers private key from public key
- Post-quantum: ML-KEM lattice problem resistant to known quantum algorithms

### 8.5 Sybil Resistance

**Traditional Sybil:** Create many identities to gain influence.

**In Ɉ Montana:**

Creating N Sybil nodes provides no advantage because:
- Each node starts with zero TIME (requires 180 days)
- Probability is normalized across all nodes
- Splitting identity splits influence proportionally
- Correlation detection identifies coordinated behavior

```python
# Sybil detection via connection rate
if new_connections > 2 * median_historical_rate:
    new_nodes.enter_probation(
        duration=180_days,
        probability_reduction=0.9  # 90% reduction
    )
```

### 8.6 51% Attack Cost

To control majority weighted influence, an attacker must:

| Requirement | Cost |
|-------------|------|
| N nodes × 180 days | Time (irreversible) |
| N × 80% chain storage | Storage |
| N × 2,016 blocks signed | Reputation |
| Evade correlation detection | Operational complexity |
| Overcome 33% cap | Requires multiple independent clusters |

**Key insight:** Unlike PoW/PoS attacks which can execute instantly with sufficient capital, time-based attacks require... time. An attack planned today cannot execute for 6 months.

### 8.7 Equivocation Penalty

Signing conflicting blocks triggers immediate slashing:

```python
EQUIVOCATION_PENALTY = {
    'reputation_reset': True,      # Reset to zero
    'quarantine_days': 180,        # No selection
    'time_forfeited': True,        # Lose accumulated time
}
```

The attacker's only path forward is to restart the 180-day accumulation.

### 8.8 Gambler's Ruin Analysis

For an attacker with probability q trying to catch up from z blocks behind an honest chain with probability p > q:

```
P(catch up) = (q/p)^z when p > q
```

For a single attacking node among N honest nodes at maximum saturation: q = 1/N.

Attack probability drops exponentially with chain depth.

---

## 9. Known Limitations

### 9.1 VPN Spoofing (Geography)

**Limitation:** Geographic verification relies on IP geolocation, which can be spoofed with VPNs.

**Mitigation:** Geography is weighted at only 10%. Maximum benefit from spoofing is 0.1 score points.

**Future:** Latency triangulation, TEE attestation, or proof of physical presence may provide stronger guarantees.

### 9.2 Correlation Detection Evasion

**Limitation:** Sophisticated attackers can add random delays to avoid timing correlation detection.

**Mitigation:** Even if timing detection is evaded:
- Cluster cap (33%) still applies
- Statistical anomaly detection (v2.6)
- Long-term behavioral analysis

### 9.3 Small Network Vulnerability

**Limitation:** With fewer than 50 nodes, statistical models for cluster detection become unreliable.

**Mitigation:** Network should not be considered production-ready until achieving 50+ diverse nodes.

### 9.4 Off-Chain Coordination

**Limitation:** Attackers coordinating via external channels (encrypted messaging) cannot be detected on-chain.

**Mitigation:** Cluster cap limits damage regardless of coordination method.

### 9.5 Post-Quantum Signature Size

**Limitation:** SPHINCS+ signatures (~17 KB) are 267× larger than Ed25519 (64 bytes).

**Mitigation:**
- Signature aggregation (future work)
- Pruning historical signatures
- Block compression

---

## 10. Network Protocol

### 10.1 Message Types

```
Type 0:   VERSION         Initial handshake
Type 1:   VERACK          Handshake acknowledgment
Type 2:   GETADDR         Request peer addresses
Type 3:   ADDR            Peer address list
Type 4:   INV             Inventory announcement
Type 5:   GETDATA         Request full objects
Type 6:   NOTFOUND        Object not available
Type 7:   GETBLOCKS       Request block range
Type 8:   GETHEADERS      Request headers only
Type 9:   HEADERS         Block headers
Type 10:  BLOCK           Full block
Type 11:  TX              Transaction
Type 12:  MEMPOOL         Request mempool contents
Type 13:  PING            Keepalive
Type 14:  PONG            Keepalive response
Type 15:  REJECT          Error/rejection

Type 100: NOISE_INIT      Noise handshake initiate
Type 101: NOISE_RESP      Noise handshake respond
Type 102: NOISE_FINAL     Noise handshake complete
```

### 10.2 Encryption: Noise Protocol

All peer connections use Noise Protocol Framework, XX pattern:

```
Initiator (I)                    Responder (R)
    |                                  |
    |-- e, es ----------------------->|  # I sends ephemeral, DH
    |                                  |
    |<-- e, ee, s, es ----------------|  # R sends ephemeral, static
    |                                  |
    |-- s, se ----------------------->|  # I sends static
    |                                  |
    |<========= Encrypted ==========>|  # All further messages encrypted
```

**Cipher Suite:**
- Key exchange: X25519 (legacy) / ML-KEM (post-quantum)
- Encryption: ChaCha20-Poly1305 (AEAD)
- Hash: SHA3-256

### 10.3 Peer Management

```python
# Eclipse attack protection
MAX_CONNECTIONS_PER_IP = 1
MAX_CONNECTIONS_PER_SUBNET = 3    # /24 for IPv4
MIN_OUTBOUND_CONNECTIONS = 8      # Always maintain 8 outbound
MAX_INBOUND_RATIO = 0.7           # Max 70% inbound

# Rate limiting
MAX_MESSAGES_PER_SECOND = 100
BAN_SCORE_THRESHOLD = 100
BAN_DURATION = 86400              # 24 hours

# Misbehavior scoring
SCORE_INV_SPAM = 20
SCORE_INVALID_BLOCK = 50
SCORE_DOS_ATTEMPT = 100
```

### 10.4 Peer Discovery

```python
# DNS seeds (initial discovery)
DNS_SEEDS = [
    "seed1.montana.network",
    "seed2.montana.network",
    "seed3.montana.network",
]

# Gossip protocol (ongoing discovery)
# Every 30 seconds, request ADDR from random peer
# Share own address if public
# Maintain address database with last-seen timestamps
```

### 10.5 Block Propagation

```
1. Leader produces block
2. Leader broadcasts INV to all peers
3. Peers request GETDATA
4. Leader sends full BLOCK
5. Peers validate:
   - VDF proof correct
   - VRF proof correct
   - Transactions valid
   - Signature valid
6. Peers relay INV to their peers
```

**Compact Blocks:** For bandwidth efficiency, relay block headers + short transaction IDs. Peers reconstruct from mempool.

### 10.6 Network Security Hardening (v3.1)

Production-grade security measures for mainnet readiness.

**Static IP Validation:**

```python
# IP types blocked by default
BLOCKED_IP_TYPES = [
    "CGNAT",           # 100.64.0.0/10 - Carrier-Grade NAT
    "DYNAMIC",         # Residential dynamic IPs
    "RESERVED",        # RFC 5737, documentation
    "LOOPBACK",        # 127.0.0.0/8
    "LINK_LOCAL",      # 169.254.0.0/16
]

# Validation flow
def validate_peer_ip(ip):
    if is_reserved(ip): return False
    if is_cgnat(ip): return False
    if not has_valid_rdns(ip): return WARN
    if is_known_vpn_asn(ip): return False
    return True
```

**VPN/Proxy Detection:**

```python
# ASN-based detection
KNOWN_VPN_ASNS = [
    "AS9009",   # M247 (NordVPN, Surfshark)
    "AS20473",  # Choopa/Vultr (various VPNs)
    "AS16276",  # OVH (hosting, VPNs)
    # ... 50+ known VPN/hosting ASNs
]

def detect_vpn(ip):
    asn = lookup_asn(ip)
    rdns = lookup_rdns(ip)

    # ASN check
    if asn in KNOWN_VPN_ASNS:
        return True, "Known VPN ASN"

    # rDNS pattern check
    vpn_patterns = ["vpn", "proxy", "tor", "exit", "relay"]
    if any(p in rdns.lower() for p in vpn_patterns):
        return True, "VPN pattern in rDNS"

    return False, None
```

**Sybil Protection:**

```python
# Node registration ONLY after block validation
def register_block_producer(block):
    # Called ONLY from block validation code
    # NEVER from network message handlers

    producer = block.header.producer_key

    # Rate limiting: max 1 new node per 10 minutes
    if time_since_last_registration < 600:
        return False

    # Must have valid VDF proof
    if not verify_vdf(block):
        return False

    # Must have valid VRF (leader selection)
    if not verify_vrf(block):
        return False

    # Only then register
    consensus.register_node(producer)
    return True
```

**Eclipse Attack Defense:**

```python
# Connection requirements
MIN_OUTBOUND_CONNECTIONS = 8    # Always maintain
MAX_INBOUND_RATIO = 0.7         # Max 70% inbound
PROTECTED_PEERS_COUNT = 8       # Never evict

def get_eviction_candidates():
    candidates = []
    for peer in peers:
        # Never evict outbound peers
        if peer.is_outbound:
            continue
        # Never evict protected peers
        if peer in protected_peers:
            continue
        candidates.append(peer)
    return candidates

def maintain_connections():
    outbound = count_outbound()
    if outbound < MIN_OUTBOUND_CONNECTIONS:
        # Force new outbound connections
        connect_to_random_peers(MIN_OUTBOUND - outbound)
```

**Rate Limiting:**

```python
# Per-IP limits
MAX_CONNECTIONS_PER_IP = 1
MAX_MESSAGES_PER_MINUTE = 600

# Per-subnet limits
MAX_CONNECTIONS_PER_SUBNET_24 = 3   # /24 IPv4
MAX_CONNECTIONS_PER_SUBNET_48 = 5   # /48 IPv6

# Reputation decay
REPUTATION_DECAY_PER_HOUR = 0.01
REPUTATION_RECOVERY_RATE = 0.05
```

**Wallet Security:**

```python
MIN_PASSWORD_LENGTH = 8

def derive_wallet_key(password, salt):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Password must be at least 8 characters")

    return argon2id(
        password=password,
        salt=salt,
        time_cost=4,
        memory_cost=65536,
        parallelism=4
    )
```

---

## 11. Privacy

All transactions use ring signatures and stealth addresses. Privacy is not optional—it is structural.

### 11.1 Privacy Tiers

| Tier | Hidden | Fee Multiplier | Status |
|------|--------|----------------|--------|
| T0 | Nothing | 1× | Production |
| T1 | Receiver | 2× | Production |
| T2 | + Amount | 5× | Experimental |
| T3 | + Sender | 10× | Experimental |

### 11.2 Stealth Addresses

Each transaction generates a unique one-time address:

```python
# Receiver has (a, A) where A = aG (spend key)
# and (b, B) where B = bG (view key)

def create_stealth_address(A, B):
    r = random_scalar()
    R = rG                          # Ephemeral public key
    shared = H(rB)                  # Shared secret (only receiver can compute with b)
    P = shared*G + A                # One-time address
    return (P, R)

def scan_for_payments(b, a, R, P):
    shared = H(bR)                  # Compute shared secret with view key
    P_expected = shared*G + aG
    return P == P_expected
```

### 11.3 Ring Signatures (LSAG)

Linkable Spontaneous Anonymous Group signatures:

```python
def sign_lsag(secret_key, ring, message):
    """
    Sign message with secret_key, hiding among ring members.
    Key image I ensures one-time spending (double-spend detection).
    """
    I = secret_key * H(public_key)  # Key image (linkable)

    # Ring signature construction
    # ... (standard LSAG algorithm)

    return (c_0, s_0, s_1, ..., s_n, I)

def verify_lsag(ring, message, signature):
    """
    Verify signature. Cannot determine which ring member signed.
    """
    # Verify ring equation closes
    # Check key image not in spent set
    return valid
```

### 11.4 Pedersen Commitments

Transaction amounts hidden through commitments:

```
C = amount × G + blinding × H

Properties:
- Hiding: Cannot determine amount from C
- Binding: Cannot change amount after commitment
- Additive: C1 + C2 = (a1+a2)×G + (b1+b2)×H
```

Balance verification without revealing amounts:

```
sum(input_commitments) == sum(output_commitments) + fee×H
```

---

## 12. Emission Schedule

### 12.1 Supply Parameters

```
Name: Ɉ Montana
Symbol: Ɉ
Ticker: $MONT
Base unit: 1 Ɉ = 1 second
Total supply: 1,260,000,000 Ɉ (21 million minutes)
Smallest unit: 10^-8 Ɉ (10 nanoseconds)
```

### 12.2 Block Rewards

| Epoch | Blocks | Reward | Total Emitted |
|-------|--------|--------|---------------|
| 0 | 1 - 210,000 | 50 min | 630M Ɉ |
| 1 | 210,001 - 420,000 | 25 min | 945M Ɉ |
| 2 | 420,001 - 630,000 | 12.5 min | 1,102.5M Ɉ |
| 3 | 630,001 - 840,000 | 6.25 min | 1,181.25M Ɉ |
| ... | ... | ... | ... |
| ∞ | - | → 0 | 1,260M Ɉ |

**Halving interval:** 210,000 blocks (~4 years at 10 min/block)
**Full emission:** ~132 years

### 12.3 Temporal Compression

The ratio of time-to-earn vs time-represented converges:

| Era | Block Time | Reward | Ratio |
|-----|------------|--------|-------|
| Genesis | 10 min | 50 min | 1:5 |
| Halving 1 | 10 min | 25 min | 1:2.5 |
| Halving 5 | 10 min | 1.5625 min | 1:0.156 |
| Asymptote | 10 min | → 0 | 1:0 |

**Nash's Ideal Money:** Inflation asymptotically approaches zero as the reward ratio approaches 1:1 then 1:0.

### 12.4 Transaction Fees

```
Minimum fee: 1 Ɉ (1 second)
Fee calculation: max(1, size_bytes / 1000)
Priority: Higher fee = earlier in block
```

After emission completes (~132 years), fees sustain the network.

---

## 13. Implementation

### 13.1 System Requirements

**Minimum:**
- 3 active nodes (theoretical minimum)
- Standard consumer hardware (no ASICs)
- Persistent internet connection
- 10 GB storage (initial), ~52 MB/year growth

**Recommended:**
- 50+ network nodes
- 4+ CPU cores (for VDF computation)
- 16 GB RAM
- SSD storage

### 13.2 Repository Structure

```
montana/
├── pantheon/
│   ├── prometheus/              # Cryptography
│   │   ├── crypto.py            # Legacy primitives
│   │   ├── crypto_provider.py   # Abstraction layer
│   │   ├── pq_crypto.py         # Post-quantum
│   │   └── winterfell_ffi.py    # STARK FFI
│   ├── athena/                  # Consensus
│   ├── hermes/                  # Networking
│   ├── hades/                   # Storage
│   ├── plutus/                  # Wallet
│   └── nyx/                     # Privacy
├── winterfell_stark/            # Rust STARK prover
│   ├── Cargo.toml
│   ├── src/lib.rs
│   └── build.sh
└── tests/
    ├── test_integration.py
    ├── test_security_proofs.py
    └── test_pq_crypto.py        # 56 PQ tests
```

### 13.3 Leader Selection Protocol

```
1. Compute VRF input:
   input = SHA3-256(prev_block_hash || height)

2. Prove leadership:
   (π, β) = VRF_prove(secret_key, input)

3. Check threshold:
   if β < P_i × 2^256:
       node is leader candidate

4. Lowest valid VRF becomes leader

5. Leader computes VDF:
   vdf_proof = VDF_compute(prev_block_hash, T)

6. Leader broadcasts block

7. If no block after 12 minutes:
   Next VRF candidate assumes leadership
```

### 13.4 Block Validation

```python
def validate_block(block, prev_block):
    # 1. VDF proof
    assert VDF_verify(prev_block.hash, block.vdf_proof)

    # 2. VRF proof (leader selection)
    vrf_input = SHA3-256(prev_block.hash || block.height)
    assert VRF_verify(block.leader_pubkey, vrf_input, block.vrf_proof)

    # 3. Leader threshold
    beta = block.vrf_proof.beta
    prob = get_node_probability(block.leader_pubkey)
    assert beta < prob * 2**256

    # 4. Transactions valid
    for tx in block.transactions:
        assert validate_transaction(tx)

    # 5. Merkle root
    assert block.merkle_root == compute_merkle(block.transactions)

    # 6. Signature
    assert verify_signature(block.leader_pubkey, block.hash, block.signature)

    # 7. Timestamp reasonable
    assert prev_block.timestamp < block.timestamp < now + 600

    return True
```

### 13.5 Node Lifecycle

```python
def run_node():
    # 1. Bootstrap
    peers = discover_peers(DNS_SEEDS)
    sync_headers(peers)
    sync_blocks(peers)

    # 2. Main loop
    while True:
        # Process incoming messages
        handle_messages()

        # Check if we're leader
        if is_leader_slot():
            if check_leadership():
                block = produce_block()
                broadcast(block)

        # Maintain connections
        maintain_peers()

        # Update Adonis scores
        update_reputation()

        sleep(1)
```

### 13.6 Configuration

```python
from config import NodeConfig, CryptoConfig

config = NodeConfig()
config.crypto = CryptoConfig(
    backend="post_quantum",      # legacy | post_quantum | hybrid
    sphincs_variant="fast",      # fast | secure
    vdf_backend="shake256",      # wesolowski | shake256
    stark_proofs_enabled=True
)

provider = config.crypto.initialize_provider()
```

### 13.7 Environment Variables

```bash
MONT_CRYPTO_BACKEND=post_quantum
MONT_SPHINCS_VARIANT=fast
MONT_VDF_BACKEND=shake256
MONT_NETWORK=mainnet
MONT_DATA_DIR=~/.montana
```

### 13.8 Running a Node

```bash
pip install pynacl
python node.py --run
```

---

## 14. Conclusion

### 14.1 Summary

Ɉ Montana removes capital as the basis of influence. The system uses time—the only truly scarce and equally distributed resource—as the foundation for distributed agreement.

**Core Properties:**
- Flash attacks impossible (180-day saturation)
- Slow attacks mitigated (correlation detection + 33% cap)
- Quantum attacks prevented (SPHINCS+, SHA3, SHAKE256)
- Sybil resistance through multi-dimensional scoring
- Privacy by default (ring signatures, stealth addresses)

### 14.2 What We Guarantee

1. **No instant takeover:** Minimum 180 days to reach maximum influence
2. **Cluster cap:** No coordinated group exceeds 33% influence
3. **Quantum resistance:** Signatures and VDF secure against quantum computers
4. **Equivocation penalty:** Double-signing forfeits all progress
5. **VDF finality:** Each checkpoint proves real time elapsed

### 14.3 What We Cannot Guarantee

1. **Physical location:** VPN spoofing possible (but limited to 10% weight)
2. **Perfect correlation detection:** Random delays can evade (but cap applies)
3. **Small network security:** Need 50+ nodes for full model
4. **Bulletproof verification:** T2/T3 privacy experimental

### 14.4 Comparison

| Property | PoW | PoS | Ɉ Montana |
|----------|-----|-----|-----------|
| Attack resource | Energy | Capital | Time |
| Flash attack | Hardware cost | Borrow capital | **Impossible** |
| Resource recovery | Sell hardware | Unstake | **Never** |
| Plutocracy | Mining pools | Whale dominance | **Saturation caps** |
| Quantum-safe | No | No | **Yes** |
| 51% attack cost | ~$20B | ~$10B | **N×180 days** |

### 14.5 Future Work

1. **Signature aggregation:** Reduce block size impact
2. **ML-DSA (Dilithium):** Alternative PQ signature scheme
3. **Post-quantum ring signatures:** Quantum-safe anonymity
4. **VDF alternatives:** Class groups for additional quantum resistance
5. **Geographic proofs:** Latency triangulation, TEE attestation
6. **Dynamic thresholds:** Adapt parameters to network size
7. **Hardware wallet:** Ledger/Trezor integration
8. **Mobile clients:** Light client protocol

### 14.6 Final Statement

Ɉ Montana does not require trust in institutions, corporations, or wealthy individuals. It requires only that honest participants collectively invest more time than attackers. Since time cannot be purchased, manufactured, or concentrated, the system resists the plutocratic capture that afflicts all resource-based consensus mechanisms.

With quantum-resistant cryptography, this guarantee extends indefinitely into the future—even as quantum computers become reality.

The network is robust in its simplicity. Nodes require no identification. Messages need only best-effort delivery. Participants can leave and rejoin freely, accepting the longest valid chain as canonical history.

---

*"Time is priceless. Now it has a price—and a future."*

**Ɉ**

---

## References

[1] S. Nakamoto, "Bitcoin: A Peer-to-Peer Electronic Cash System," 2008.

[2] D. Boneh, J. Bonneau, B. Bünz, B. Fisch, "Verifiable Delay Functions," CRYPTO 2018.

[3] B. Wesolowski, "Efficient Verifiable Delay Functions," EUROCRYPT 2019.

[4] NIST, "FIPS 202: SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions," 2015.

[5] NIST, "FIPS 205: Stateless Hash-Based Digital Signature Standard (SLH-DSA)," 2024.

[6] NIST, "FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)," 2024.

[7] D. J. Bernstein et al., "SPHINCS+: Submission to the NIST Post-Quantum Cryptography Standardization," 2022.

[8] E. Ben-Sasson et al., "Scalable, transparent, and post-quantum secure computational integrity," 2018.

[9] A. Yakovenko, "Solana: A new architecture for a high performance blockchain," 2018.

[10] S. Noether, "Ring Signature Confidential Transactions for Monero," Ledger, 2016.

[11] N. van Saberhagen, "CryptoNote v2.0," 2013.

[12] E. Hughes, "A Cypherpunk's Manifesto," 1993.

[13] H. Finney, "RPOW - Reusable Proofs of Work," 2004.

[14] T. Perrin, "The Noise Protocol Framework," 2018.

[15] D. J. Bernstein et al., "Ed25519: High-speed high-security signatures," 2012.

---

## Appendix A: Constants Reference

```python
# ============================================================
# ADONIS WEIGHTS (Five Fingers)
# ============================================================
WEIGHT_TIME = 0.50       # THUMB
WEIGHT_INTEGRITY = 0.20  # INDEX
WEIGHT_STORAGE = 0.15    # MIDDLE
WEIGHT_GEOGRAPHY = 0.10  # RING
WEIGHT_HANDSHAKE = 0.05  # PINKY

# ============================================================
# SATURATION THRESHOLDS
# ============================================================
K_TIME = 15_552_000      # 180 days in seconds
K_STORAGE = 1.00         # 100% of chain
K_HANDSHAKE = 10         # 10 handshakes

# ============================================================
# ANTI-CLUSTER PROTECTION
# ============================================================
MAX_CORRELATION_THRESHOLD = 0.7   # 70% = suspicious
CORRELATION_PENALTY_FACTOR = 0.5  # 50% max penalty
MAX_CLUSTER_INFLUENCE = 0.33      # 33% cap
MIN_NETWORK_ENTROPY = 0.5         # Health threshold
ENTROPY_DECAY_RATE = 0.001        # 0.1% per hour
TIMING_VARIANCE_THRESHOLD = 100   # 100ms = synchronized
CORRELATION_WINDOW = 86400        # 24-hour analysis

# ============================================================
# NETWORK
# ============================================================
MAX_CONNECTIONS_PER_IP = 1
MAX_CONNECTIONS_PER_SUBNET = 3
MIN_OUTBOUND_CONNECTIONS = 8
MAX_MESSAGES_PER_SECOND = 100
BAN_DURATION = 86400              # 24 hours

# ============================================================
# CRYPTOGRAPHY
# ============================================================
HASH_ALGORITHM = "SHA3-256"       # Post-quantum
SIGNATURE_ALGORITHM = "SPHINCS+"  # Post-quantum
VDF_ALGORITHM = "SHAKE256"        # Post-quantum
KEM_ALGORITHM = "ML-KEM-768"      # Post-quantum

# ============================================================
# VDF
# ============================================================
VDF_MODULUS_BITS = 2048           # Legacy
VDF_CHECKPOINT_INTERVAL = 1000    # STARK checkpoints
VDF_MIN_ITERATIONS = 1000
VDF_MAX_ITERATIONS = 10**11
VDF_TARGET_SECONDS = 540          # 9 minutes

# ============================================================
# EMISSION
# ============================================================
TOTAL_SUPPLY = 1_260_000_000      # 21M minutes in seconds
INITIAL_REWARD = 3000             # 50 minutes in seconds
HALVING_INTERVAL = 210_000        # blocks
BLOCK_TIME = 600                  # 10 minutes in seconds
```

---

## Appendix B: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial specification |
| 2.0 | Dec 2025 | Five Fingers of Adonis, anti-cluster protection, known limitations |
| 2.6 | Dec 2025 | All security properties proven via executable tests |
| 3.0 | Dec 2025 | Post-quantum cryptography: SPHINCS+, SHA3-256, SHAKE256 VDF, STARK proofs, ML-KEM, crypto-agility layer |
| **3.1** | Dec 2025 | **Network security hardening: static IP validation, VPN/proxy detection, Sybil protection, Eclipse defense, rate limiting, wallet encryption** |

---

*Ɉ Montana Technical Specification v3.1*
*December 2025*
