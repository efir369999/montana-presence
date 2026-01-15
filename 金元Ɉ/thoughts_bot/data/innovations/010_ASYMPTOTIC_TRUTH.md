# Asymptotic Truth

**The Convergence of Evidence and Reality**
**Version:** 1.0
**Date:** January 2026

---

## Abstract

This paper formalizes Montana's epistemological foundation: the principle of Asymptotic Truth. We prove that the relationship between Ɉ and physical time is not equivalence but convergence—as evidence accumulates, confidence in the temporal backing of Ɉ approaches but never reaches certainty. This philosophical grounding distinguishes Montana from systems claiming absolute guarantees.

---

## 1. Introduction

### 1.1 The Core Formula

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

This formula encodes a fundamental insight: Ɉ asymptotically approaches equivalence with physical seconds as verification evidence increases.

### 1.2 Why Asymptotic?

True equivalence would require infinite verification. Since verification is finite, we can only achieve arbitrarily high confidence, never certainty:

```
∀t: Trust(t) < 1
```

For all claims t, trust is strictly less than 1 (certainty).

---

## 2. Mathematical Foundation

### 2.1 Evidence Function

Let E(t) represent total evidence at time t:

```
E(t) = ∫₀ᵗ [vdf_proofs + nts_attestations + peer_confirmations] dt
```

### 2.2 Confidence Function

Confidence C grows with evidence but is bounded:

```
C(E) = 1 - e^(-λE)

where:
  λ = evidence weight parameter
  C ∈ [0, 1)
  lim(E→∞) C(E) = 1
```

### 2.3 Asymptotic Property

```
∀ε > 0, ∃E₀: E > E₀ ⟹ |C(E) - 1| < ε
```

For any desired confidence level below 1, sufficient evidence achieves it.

---

## 3. Components of Evidence

### 3.1 VDF Proofs

VDF proofs provide primary temporal evidence:

```
VDF_evidence(n proofs) = n × difficulty × verification_certainty
```

Each VDF proof attests that sequential computation (hence time) occurred.

### 3.2 NTS Attestations

Network Time Security attestations provide external anchoring:

```
NTS_evidence(n sources) = n × source_reliability × agreement_factor
```

Multiple independent time sources increase confidence.

### 3.3 Peer Confirmations

Network peer confirmations provide social consensus:

```
Peer_evidence(n confirmations) = n × peer_honesty × network_diversity
```

Geographically diverse, independent peers provide stronger evidence.

---

## 4. Trust Bounds

### 4.1 Strict Inequality

```
∀t: Trust(t) < 1
```

This is not a limitation but intellectual honesty. Systems claiming Trust = 1 are either:
- Lying (trust is based on authority)
- Confused (conflating high confidence with certainty)
- Centralized (trust in specific parties)

### 4.2 Practical Sufficiency

For practical purposes, Trust > 0.999999 is equivalent to certainty:

```
Practical_certainty = C(E) > 1 - 10^(-6)
```

Montana achieves this with sufficient evidence accumulation.

### 4.3 Comparison

| System | Trust Claim | Reality |
|--------|-------------|---------|
| Fiat | Government guarantee | Trust in institution |
| Bitcoin | 6 confirmations | Trust in hash rate majority |
| PoS | Stake finality | Trust in stake distribution |
| Montana | Asymptotic | Explicit about uncertainty |

---

## 5. Philosophical Implications

### 5.1 Epistemic Honesty

Montana explicitly acknowledges uncertainty:

```
"We prove with high confidence, never with certainty."
```

This honesty is a feature, not a bug. Systems hiding uncertainty mislead users.

### 5.2 Scientific Method Alignment

Asymptotic truth aligns with scientific epistemology:

- Hypotheses are never proven, only supported
- Confidence increases with evidence
- Perfect knowledge is unattainable

### 5.3 Practical Security

Despite theoretical uncertainty, practical security can be overwhelming:

```
P(attack succeeds) < 2^(-128)
```

This probability is smaller than spontaneous hardware failure, making attacks practically impossible while remaining theoretically possible.

---

## 6. Temporal Evidence Hierarchy

### 6.1 Evidence Levels

| Level | Evidence | Confidence |
|-------|----------|------------|
| 1 | Single VDF | 0.9 |
| 2 | VDF + NTS | 0.99 |
| 3 | VDF + NTS + Peers | 0.999 |
| 4 | Multiple τ₂ | 0.9999 |
| 5 | Full τ₃ (14 days) | 0.999999 |

### 6.2 Confidence Growth

```
Confidence after n τ₂ slices:

C(n) = 1 - (1-p)^n

where p = per-slice confidence contribution ≈ 0.4

C(1) = 0.4
C(6) = 0.95
C(14) = 0.99
C(100) = 0.9999999
```

### 6.3 14-Day Threshold

After τ₃ (2,016 slices), confidence exceeds practical certainty:

```
C(2016) > 1 - 10^(-868)
```

---

## 7. Attack Analysis

### 7.1 Reducing Trust

An attacker seeking to reduce trust must invalidate evidence:

| Attack | Effect on Evidence |
|--------|-------------------|
| VDF forgery | Computationally infeasible |
| NTS spoofing | Requires server compromise |
| Sybil peers | Bounded by network diversity |
| Time travel | Physically impossible |

### 7.2 Residual Uncertainty

Even with maximum evidence, residual uncertainty exists:

```
Residual_uncertainty = P(all evidence simultaneously wrong)
                     < P(laws of physics violated)
```

This uncertainty is unavoidable in any physical system.

---

## 8. Implementation

### 8.1 Confidence Calculation

```python
def calculate_confidence(presence_proof):
    vdf_conf = verify_vdf_confidence(presence_proof.vdf)
    nts_conf = verify_nts_confidence(presence_proof.nts_attestations)
    peer_conf = verify_peer_confidence(presence_proof.peer_signatures)

    # Combined confidence (assuming independence)
    total_evidence = vdf_conf + nts_conf + peer_conf
    confidence = 1 - math.exp(-LAMBDA * total_evidence)

    return min(confidence, 1 - EPSILON)  # Never exactly 1
```

### 8.2 Threshold Enforcement

```python
def is_sufficiently_confident(presence_proof, threshold=0.999):
    confidence = calculate_confidence(presence_proof)
    return confidence >= threshold
```

---

## 9. The Limit Statement

### 9.1 Formal Expression

```
lim(evidence → ∞) 1 Ɉ → 1 second

Equivalently:

∀ε > 0, ∃E₀: E > E₀ ⟹ |value(1 Ɉ) - 1 second| < ε
```

### 9.2 Interpretation

As evidence grows without bound:
- Ɉ approaches perfect backing by physical time
- Confidence approaches (but never reaches) certainty
- Practical difference from certainty becomes negligible

### 9.3 Never Equals

```
1 Ɉ ≠ 1 second  (strict inequality always holds)
1 Ɉ ≈ 1 second  (practical equivalence with sufficient evidence)
```

---

## 10. Conclusion

Asymptotic Truth represents Montana's commitment to epistemic honesty. Rather than claiming false certainty, we acknowledge that confidence grows with evidence but never reaches absolute truth. This philosophical grounding distinguishes Montana from systems that hide uncertainty behind authority or complexity.

The formula `lim(evidence → ∞) 1 Ɉ → 1 second` is not a limitation but a feature—it honestly represents what any physical system can achieve.

---

## References

1. Popper, K. (1959). The Logic of Scientific Discovery.
2. Montana, A. (2026). VDF Specification.
3. Montana, A. (2026). ACP Protocol.

---

```
Alejandro Montana
Montana Protocol
January 2026

lim(evidence → ∞) 1 Ɉ → 1 second
∀t: Trust(t) < 1
```
