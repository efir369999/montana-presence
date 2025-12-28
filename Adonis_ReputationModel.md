# Adonis: Multi-Dimensional Reputation Model for Proof of Time

**Version 1.0**
**December 2025**

---

## Abstract

This document specifies Adonis, a multi-dimensional reputation system designed for the Proof of Time (PoT) consensus protocol. Adonis extends the basic reputation component (f_rep) with behavioral analysis, trust graph propagation, and dynamic penalty mechanisms. The model provides a quantifiable trust metric that integrates into the consensus probability calculation.

---

## 1. Introduction

### 1.1 Motivation

The original Proof of Time consensus uses a single-dimensional reputation metric based on signed blocks:

```
f_rep(r) = min(r / K_REP, 1)
```

Where `r` is the number of successfully signed blocks and `K_REP = 2016` blocks (~2 weeks).

This approach has limitations:
- Does not capture behavioral patterns
- No social trust component
- Recovery after penalties is binary
- No differentiation between contribution types

Adonis addresses these limitations by introducing a five-dimensional reputation model with event-driven updates and trust graph integration.

### 1.2 Design Goals

1. **Multi-dimensionality**: Capture different aspects of node behavior
2. **Temporal decay**: Recent behavior weighted more heavily
3. **Social trust**: Peer vouching affects reputation
4. **Graceful recovery**: Gradual rehabilitation after penalties
5. **Backward compatibility**: Integrates with existing f_rep calculation

---

## 2. Reputation Dimensions

### 2.1 Dimension Definitions

Adonis defines five orthogonal reputation dimensions:

| Dimension | Symbol | Description | Weight |
|-----------|--------|-------------|--------|
| Reliability | D_rel | Block production consistency, uptime | 0.25 |
| Integrity | D_int | Absence of violations, valid proofs | 0.30 |
| Contribution | D_con | Storage, relay, validation work | 0.15 |
| Longevity | D_lon | Time in network with good standing | 0.20 |
| Community | D_com | Peer trust and vouching | 0.10 |

### 2.2 Dimension Score Structure

Each dimension `D_i` maintains:

```
DimensionScore = {
    value: float      // Current score in [0, 1]
    confidence: float // Confidence level in [0, 1]
    samples: int      // Number of observations
    last_update: int  // Unix timestamp
}
```

### 2.3 Score Update Algorithm

For dimension `D_i` with new observation `o` and weight `w`:

```
decay = exp(-(t_now - t_last) / (168 * 3600))  // 1-week half-life
alpha = w / (samples + w)
value_new = (1 - alpha) * value_old * decay + alpha * o
confidence = 1 - exp(-samples / 100)
```

The exponential decay ensures recent behavior has greater influence while maintaining historical context.

---

## 3. Reputation Events

### 3.1 Event Classification

Events are classified as positive or negative with defined impact values:

**Positive Events:**

| Event | Impact | Target Dimension |
|-------|--------|------------------|
| BLOCK_PRODUCED | +0.05 | Reliability |
| BLOCK_VALIDATED | +0.02 | Contribution |
| TX_RELAYED | +0.01 | Contribution |
| UPTIME_CHECKPOINT | +0.03 | Reliability |
| PEER_VOUCH | +0.10 | Community |

**Negative Events:**

| Event | Impact | Target Dimension | Penalty Duration |
|-------|--------|------------------|------------------|
| BLOCK_INVALID | -0.15 | Integrity | - |
| VRF_INVALID | -0.20 | Integrity | 14 days |
| VDF_INVALID | -0.25 | Integrity | 30 days |
| EQUIVOCATION | -1.00 | Integrity | 180 days |
| DOWNTIME | -0.10 | Reliability | - |
| SPAM_DETECTED | -0.20 | Integrity | 7 days |
| PEER_COMPLAINT | -0.05 | Community | - |

### 3.2 Event Recording

Each event creates an immutable record:

```
ReputationRecord = {
    event_type: ReputationEvent
    timestamp: uint64
    impact: float32
    height: uint64
    source: bytes32    // Optional: source node for peer events
    evidence: bytes32  // Optional: hash of evidence
}
```

---

## 4. Aggregate Score Computation

### 4.1 Weighted Aggregation

The aggregate reputation score `R` is computed as:

```
R = Σ(w_i * D_i.value * D_i.confidence) / Σ(w_i * D_i.confidence)
```

Where `w_i` are the dimension weights defined in Section 2.1.

### 4.2 Penalty Modifier

If a node is under penalty:

```
R_effective = 0.1 * R  // 90% reduction during penalty
```

### 4.3 Consensus Integration

The Adonis score integrates with consensus probability:

```
f_rep_adonis(pubkey, signed_blocks) = 0.3 * f_rep_basic + 0.7 * R(pubkey)

Where:
    f_rep_basic = min(signed_blocks / K_REP, 1)
    R(pubkey) = Adonis aggregate score
```

---

## 5. Trust Graph

### 5.1 Vouch Mechanism

Nodes can vouch for other nodes, creating a directed trust graph:

```
G = (V, E)
Where:
    V = set of node public keys
    E = set of (voucher, vouchee) pairs
```

### 5.2 Trust Score

The trust score from vouches uses logarithmic scaling:

```
T(node) = min(1.0, 0.2 * log10(1 + 4 * |trusted_by(node)|))
```

This provides:
- 1 vouch: T = 0.20
- 10 vouches: T = 0.60
- 100 vouches: T = 0.90

### 5.3 PageRank Extension

For advanced trust computation, Adonis supports PageRank-style propagation:

```
PR_i = (1 - d) / N + d * Σ(PR_j / |out(j)|)
        for all j in trusted_by(i)

Where:
    d = 0.85 (damping factor)
    N = total nodes
    out(j) = nodes vouched by j
```

This gives higher weight to vouches from high-reputation nodes.

---

## 6. Reputation Multiplier

### 6.1 Probability Modifier

Adonis provides a multiplier for consensus probability:

```
M(pubkey) = 0.1 + 1.9 * R(pubkey)

Range: [0.1, 2.0]
    R = 0.0 -> M = 0.1 (maximum penalty)
    R = 0.5 -> M = 1.0 (neutral)
    R = 1.0 -> M = 2.0 (maximum bonus)
```

### 6.2 Application to Consensus

The final probability:

```
P_i_final = P_i_base * M(pubkey_i) / Z

Where Z is the normalization constant.
```

---

## 7. Penalty and Recovery

### 7.1 Penalty Conditions

Severe violations trigger time-based penalties:

| Violation | Duration | Effect |
|-----------|----------|--------|
| EQUIVOCATION | 180 days | 90% probability reduction |
| VDF_INVALID | 30 days | 90% probability reduction |
| VRF_INVALID | 14 days | 90% probability reduction |
| SPAM_DETECTED | 7 days | 90% probability reduction |

### 7.2 Recovery Mechanism

After penalty expiration:
1. `is_penalized` flag cleared
2. All dimension scores preserved
3. Node must rebuild reputation through positive events
4. No automatic score restoration

### 7.3 Longevity Impact

The longevity dimension naturally increases over time:

```
D_lon = min(1.0, age_days / 180)
```

This provides passive reputation recovery for nodes maintaining uptime.

---

## 8. Implementation

### 8.1 Data Structures

**AdonisProfile:**
```
struct AdonisProfile {
    pubkey: bytes32
    dimensions: map[ReputationDimension -> DimensionScore]
    aggregate_score: float32
    history: array[ReputationRecord]  // max 1000 entries
    trusted_by: set[bytes32]
    trusts: set[bytes32]
    is_penalized: bool
    penalty_until: uint64
    created_at: uint64
    last_updated: uint64
    total_events: uint32
}
```

### 8.2 Storage Requirements

Per-node storage:
- Fixed fields: ~150 bytes
- Dimension scores: 5 * 20 = 100 bytes
- History (max): 1000 * 85 = 85 KB
- Trust sets (typical): 2 * 100 * 32 = 6.4 KB

Total typical: ~90 KB per node

### 8.3 Computational Complexity

| Operation | Complexity |
|-----------|------------|
| Record event | O(1) |
| Compute aggregate | O(D) where D = dimensions |
| Get multiplier | O(1) |
| PageRank | O(N * E * I) where I = iterations |

---

## 9. Security Considerations

### 9.1 Sybil Resistance

The trust graph is resistant to Sybil attacks:
- PageRank concentration requires vouches from established nodes
- New nodes start with zero trust score
- Self-vouching has no effect

### 9.2 Collusion Resistance

Vouch farming is mitigated by:
- Logarithmic scaling of vouch count
- PageRank distribution dilutes low-quality vouches
- Community dimension weight limited to 10%

### 9.3 History Manipulation

Event records include:
- Cryptographic evidence hashes
- Block height for ordering
- Source node identification

Records are append-only and verifiable.

---

## 10. Protocol Constants

| Constant | Value | Description |
|----------|-------|-------------|
| MAX_HISTORY | 1000 | Maximum event records per node |
| DECAY_HALFLIFE | 168 hours | Score decay half-life |
| CONFIDENCE_SATURATION | 100 | Samples for 63% confidence |
| PENALTY_REDUCTION | 0.1 | Multiplier during penalty |
| VOUCH_LOG_BASE | 4 | Logarithmic vouch scaling |
| PAGERANK_DAMPING | 0.85 | PageRank damping factor |
| PAGERANK_ITERATIONS | 20 | PageRank convergence iterations |

---

## 11. Conclusion

Adonis provides a comprehensive reputation framework that enhances the Proof of Time consensus mechanism. By combining multi-dimensional scoring, trust graph analysis, and dynamic penalty mechanisms, it creates a robust and fair system for evaluating node behavior. The model maintains backward compatibility while significantly improving the expressiveness and accuracy of reputation assessment.

---

## References

1. Proof of Time Technical Specification v1.1
2. Page, L., et al. "The PageRank Citation Ranking: Bringing Order to the Web." (1999)
3. Kamvar, S. D., et al. "The EigenTrust Algorithm for Reputation Management in P2P Networks." (2003)

---

## Appendix A: Dimension Weight Rationale

The dimension weights were determined through analysis of consensus security requirements:

- **Integrity (0.30)**: Highest weight due to critical nature of valid proofs
- **Reliability (0.25)**: Essential for network liveness and block production
- **Longevity (0.20)**: Sybil resistance through time commitment
- **Contribution (0.15)**: Encourages network participation
- **Community (0.10)**: Social layer adds defense-in-depth

## Appendix B: Event Impact Calibration

Impact values calibrated to achieve:
- 100 blocks produced: ~50% reliability score
- 1 equivocation: Complete integrity destruction
- 10 vouches: ~60% community trust score

## Appendix C: Serialization Format

Binary serialization for network transmission:

```
AdonisProfile (serialized):
    pubkey:          32 bytes
    aggregate_score: 4 bytes (float32)
    created_at:      8 bytes (uint64)
    last_updated:    8 bytes (uint64)
    total_events:    4 bytes (uint32)
    is_penalized:    1 byte (bool)
    penalty_until:   8 bytes (uint64)
    dimensions:      5 * 20 bytes
    trusted_by_len:  2 bytes (uint16)
    trusted_by:      N * 32 bytes
    trusts_len:      2 bytes (uint16)
    trusts:          M * 32 bytes
```
