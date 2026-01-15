# τ (Tau) Temporal Units System

**Hierarchical Time Measurement**
**Version:** 1.0
**Date:** January 2026

---

## Abstract

This paper formalizes the τ (tau) temporal units system—Montana's hierarchical framework for measuring and organizing time within the protocol. Unlike arbitrary time divisions (seconds, hours, days), τ units derive from protocol requirements: signature intervals, emission slices, checkpoints, and economic cycles. We demonstrate that this structure creates natural synchronization points and enables predictable protocol behavior.

---

## 1. Introduction

Traditional timekeeping divides time into arbitrary units based on astronomical observations (days, years) or decimal convenience (seconds, milliseconds). Montana requires time units that align with protocol operations rather than historical convention.

The τ system provides four hierarchical levels, each serving specific protocol functions.

---

## 2. τ Unit Definitions

### 2.1 Hierarchy

| Unit | Duration | Seconds | Protocol Role |
|------|----------|---------|---------------|
| τ₁ | 1 minute | 60 | Signature interval |
| τ₂ | 10 minutes | 600 | Emission slice |
| τ₃ | 14 days | 1,209,600 | Checkpoint epoch |
| τ₄ | ~4 years | ~126,144,000 | Halving cycle |

### 2.2 Relationships

```
τ₂ = 10 × τ₁
τ₃ = 20,160 × τ₁ = 2,016 × τ₂
τ₄ = 210,000 × τ₂
```

### 2.3 Rationale

**τ₁ (1 minute):** Minimum meaningful presence interval. Below this, network latency dominates; above this, presence granularity decreases.

**τ₂ (10 minutes):** Emission slice duration. Balances reward frequency against verification overhead. Derived from Bitcoin's block time as proven practical interval.

**τ₃ (14 days):** Checkpoint epoch. Represents the minimum time to establish "deep" presence. Attacker with infinite resources still needs 14 days for 14 days of presence.

**τ₄ (~4 years):** Halving cycle. Long enough for ecosystem maturation, short enough for observable economic effects.

---

## 3. τ₁: Signature Interval

### 3.1 Definition

```
τ₁ = 60 seconds
```

### 3.2 Protocol Use

Each τ₁ interval, participants may submit one presence signature:

```
Sig_τ₁(participant, t) = Sign(sk, H(t || participant || nonce))
```

### 3.3 Properties

- **Minimum presence quantum:** Cannot prove presence smaller than τ₁
- **Rate limiting:** One signature per τ₁ prevents spam
- **Network sync:** τ₁ boundaries provide synchronization points

---

## 4. τ₂: Emission Slice

### 4.1 Definition

```
τ₂ = 600 seconds = 10 × τ₁
```

### 4.2 Protocol Use

Emission occurs at τ₂ boundaries:

```python
def emission_at_slice(slice_number):
    epoch = slice_number // 210_000
    base_emission = INITIAL_EMISSION / (2 ** epoch)
    return base_emission
```

### 4.3 Properties

- **Emission granularity:** Rewards distributed every τ₂
- **Presence accumulation:** Window for measuring participant activity
- **VDF alignment:** VDF difficulty targets τ₂ duration

---

## 5. τ₃: Checkpoint Epoch

### 5.1 Definition

```
τ₃ = 1,209,600 seconds = 14 days = 2,016 × τ₂
```

### 5.2 Protocol Use

Checkpoints finalize at τ₃ boundaries:

```python
def is_checkpoint(slice_number):
    return slice_number % 2016 == 0

def checkpoint_weight(checkpoint):
    return sum(presence_proofs in checkpoint.epoch)
```

### 5.3 The 14-Day Principle

```
"14 days require 14 days."

∀ attacker A with resources R (unlimited):
    time_to_produce(14_days_presence) ≥ 14 days
```

This is not a design choice but a physical constraint. No optimization can reduce the time required to accumulate τ₃ worth of presence.

### 5.4 Security Implications

- **Long-range attack resistance:** Rewriting τ₃ history requires τ₃ time
- **Finality guarantee:** After τ₃, transactions are practically irreversible
- **Difficulty adjustment:** Occurs every τ₃ (2,016 slices), matching Bitcoin

---

## 6. τ₄: Halving Cycle

### 6.1 Definition

```
τ₄ = 126,144,000 seconds ≈ 4 years = 210,000 × τ₂
```

### 6.2 Protocol Use

Emission halves every τ₄:

```
emission(epoch n) = 3000 Ɉ / (2^n)

Epoch 0: 3000 Ɉ per τ₂
Epoch 1: 1500 Ɉ per τ₂
Epoch 2: 750 Ɉ per τ₂
...
```

### 6.3 Supply Convergence

Total supply converges:

```
∑(all epochs) = 3000 × 210,000 × ∑(1/2^n)
              = 630,000,000 × 2
              = 1,260,000,000 Ɉ
```

---

## 7. Genesis Alignment

### 7.1 Genesis Timestamp

```
GENESIS_TIME = 2026-01-13 00:00:00 UTC
GENESIS_UNIX = 1736726400
```

All τ units align to genesis:

```python
def current_tau1():
    return (now() - GENESIS_UNIX) // 60

def current_tau2():
    return (now() - GENESIS_UNIX) // 600

def current_epoch():
    return current_tau2() // 210_000
```

### 7.2 Predictability

Any future τ boundary can be calculated:

```python
def tau2_boundary(n):
    return GENESIS_UNIX + (n * 600)

# Example: τ₂ slice #1,000,000
tau2_boundary(1_000_000) = 1736726400 + 600_000_000
                         = 2336726400
                         = 2044-01-15 00:00:00 UTC
```

---

## 8. Implementation

### 8.1 Time Conversion

```python
def to_tau1(unix_time):
    return (unix_time - GENESIS_UNIX) // TAU1_SECONDS

def to_tau2(unix_time):
    return (unix_time - GENESIS_UNIX) // TAU2_SECONDS

def to_unix(tau2_slice):
    return GENESIS_UNIX + (tau2_slice * TAU2_SECONDS)
```

### 8.2 Boundary Detection

```python
def is_tau2_boundary(unix_time):
    return (unix_time - GENESIS_UNIX) % TAU2_SECONDS == 0

def next_tau2_boundary(unix_time):
    current = to_tau2(unix_time)
    return to_unix(current + 1)
```

---

## 9. Conclusion

The τ system provides Montana with a time framework derived from protocol requirements rather than historical convention. Each level serves specific functions: τ₁ for signatures, τ₂ for emission, τ₃ for checkpoints, τ₄ for halvings. This hierarchy creates predictable, calculable protocol behavior while maintaining alignment with physical time constraints.

---

## References

1. Montana, A. (2026). ACP Protocol Specification.
2. Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.

---

```
Alejandro Montana
Montana Protocol
January 2026
```
