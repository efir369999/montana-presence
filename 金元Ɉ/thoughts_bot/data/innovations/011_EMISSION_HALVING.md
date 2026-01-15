# Emission and Halving Mechanics

**Supply Schedule and Distribution**
**Version:** 1.0
**Date:** January 2026

---

## Abstract

This paper specifies Montana's emission schedule and halving mechanics. Unlike proof-of-work systems where emission rewards miners for computation, Montana's emission rewards participants for temporal presence. We formalize the supply curve, halving intervals, and distribution mechanisms that ensure fair allocation while maintaining scarcity.

---

## 1. Introduction

### 1.1 Design Goals

Montana's emission must satisfy:

1. **Finite supply:** Total Ɉ mathematically bounded
2. **Fair distribution:** Rewards presence, not capital or hardware
3. **Predictable schedule:** Emission rate calculable for any future time
4. **Decreasing inflation:** Halving reduces emission over time

### 1.2 Key Parameters

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Total supply | 1,260,000,000 Ɉ | 金 (gold) = 126 strokes × 10M |
| Initial emission | 3,000 Ɉ/τ₂ | Practical distribution rate |
| Halving interval | 210,000 τ₂ | ~4 years |
| Genesis | 2026-01-13 | Protocol launch |

---

## 2. Supply Formula

### 2.1 Total Supply Derivation

```
Total_Supply = Initial_Emission × Halving_Interval × ∑(1/2^n)
             = 3,000 × 210,000 × 2
             = 1,260,000,000 Ɉ
```

### 2.2 Geometric Series

The infinite sum converges:

```
∑(n=0 to ∞) 1/2^n = 2

Therefore:
∑(all epochs) emission = 630,000,000 × 2 = 1,260,000,000 Ɉ
```

### 2.3 Supply at Time t

```python
def supply_at_slice(slice_number):
    supply = 0
    remaining = slice_number

    epoch = 0
    while remaining > 0:
        slices_in_epoch = min(remaining, 210_000)
        emission_per_slice = 3000 / (2 ** epoch)
        supply += slices_in_epoch * emission_per_slice
        remaining -= slices_in_epoch
        epoch += 1

    return supply
```

---

## 3. Emission Schedule

### 3.1 Per-Epoch Emission

| Epoch | Emission/τ₂ | Total in Epoch | Cumulative |
|-------|-------------|----------------|------------|
| 0 | 3,000 Ɉ | 630,000,000 Ɉ | 630,000,000 Ɉ |
| 1 | 1,500 Ɉ | 315,000,000 Ɉ | 945,000,000 Ɉ |
| 2 | 750 Ɉ | 157,500,000 Ɉ | 1,102,500,000 Ɉ |
| 3 | 375 Ɉ | 78,750,000 Ɉ | 1,181,250,000 Ɉ |
| 4 | 187.5 Ɉ | 39,375,000 Ɉ | 1,220,625,000 Ɉ |
| ... | ... | ... | ... |
| ∞ | 0 | 0 | 1,260,000,000 Ɉ |

### 3.2 Epoch Timing

```
Epoch 0: 2026-01-13 to ~2030-01-13 (4 years)
Epoch 1: ~2030-01-13 to ~2034-01-13 (4 years)
Epoch 2: ~2034-01-13 to ~2038-01-13 (4 years)
...
```

### 3.3 Halving Dates

```python
def halving_date(epoch):
    slices_to_halving = epoch * 210_000
    seconds = slices_to_halving * 600
    return GENESIS_UNIX + seconds

# Halving 1: 2030-01-11 (approximately)
# Halving 2: 2034-01-08 (approximately)
# Halving 3: 2038-01-06 (approximately)
```

---

## 4. Distribution Mechanism

### 4.1 Presence-Weighted Distribution

Each τ₂ slice, emission distributes proportionally to presence:

```python
def distribute_emission(slice_number, participants):
    emission = get_emission(slice_number)
    total_weight = sum(p.presence_weight for p in participants)

    rewards = {}
    for p in participants:
        share = p.presence_weight / total_weight
        rewards[p.address] = emission * share

    return rewards
```

### 4.2 Presence Weight

```python
def calculate_presence_weight(participant, window):
    base_weight = participant.message_count * CHARACTER_FACTOR
    time_weight = participant.active_seconds / window.duration
    attestation_bonus = len(participant.peer_attestations) * ATTESTATION_FACTOR

    return base_weight * time_weight + attestation_bonus
```

### 4.3 No Minimum Threshold

Even minimal presence receives proportional reward:

```
reward(1 message) = emission × (1 message weight / total weight)
```

This ensures inclusivity—everyone can participate.

---

## 5. Halving Mechanics

### 5.1 Discrete Halving

Emission halves exactly at epoch boundaries:

```python
def get_emission(slice_number):
    epoch = slice_number // HALVING_INTERVAL
    return INITIAL_EMISSION / (2 ** epoch)
```

### 5.2 No Smooth Curve

Unlike continuous decay, Montana uses discrete halvings:

```
Emission:
3000 ─────────┐
              │
1500 ─────────┼─────────┐
              │         │
 750 ─────────┼─────────┼─────────┐
              │         │         │
     ─────────┴─────────┴─────────┴────→ time
           Epoch 0   Epoch 1   Epoch 2
```

### 5.3 Rationale

Discrete halvings provide:
- Clear, predictable events
- Natural economic attention points
- Simpler implementation
- Proven model (Bitcoin precedent)

---

## 6. Inflation Rate

### 6.1 Annual Inflation

```python
def annual_inflation(year):
    slices_per_year = 365.25 * 24 * 6  # ~52,596
    total_emission = 0

    for slice in year_slices(year):
        total_emission += get_emission(slice)

    current_supply = supply_at_year_start(year)
    return total_emission / current_supply
```

### 6.2 Inflation by Year

| Year | Approx. Inflation |
|------|-------------------|
| 2026 | 25% |
| 2027 | 20% |
| 2028 | 15% |
| 2029 | 12% |
| 2030 | 5% (post-halving) |
| 2034 | 2% (post-halving) |
| 2038 | 1% (post-halving) |
| 2050 | < 0.1% |

### 6.3 Asymptotic Zero

```
lim(t → ∞) inflation_rate(t) = 0
```

Inflation approaches but never reaches zero (always some emission until supply exhausted).

---

## 7. Supply Milestones

### 7.1 Key Thresholds

| Milestone | Supply | Approx. Date |
|-----------|--------|--------------|
| 10% | 126,000,000 Ɉ | 2026-05 |
| 25% | 315,000,000 Ɉ | 2027-06 |
| 50% | 630,000,000 Ɉ | 2030-01 |
| 75% | 945,000,000 Ɉ | 2034-01 |
| 90% | 1,134,000,000 Ɉ | 2042-01 |
| 99% | 1,247,400,000 Ɉ | 2066-01 |

### 7.2 Never Complete

Mathematically, supply never exactly reaches maximum:

```
∀t: supply(t) < 1,260,000,000 Ɉ
```

Final supply approaches maximum asymptotically.

---

## 8. Comparison with Bitcoin

| Property | Bitcoin | Montana |
|----------|---------|---------|
| Total supply | 21,000,000 | 1,260,000,000 |
| Initial reward | 50 BTC/block | 3,000 Ɉ/τ₂ |
| Halving interval | 210,000 blocks | 210,000 τ₂ |
| Interval duration | ~4 years | ~4 years |
| Distribution basis | Hash power | Presence |
| Smallest unit | 1 satoshi | 1 Ɉ |

---

## 9. Implementation

### 9.1 Emission Calculation

```python
INITIAL_EMISSION = 3000
HALVING_INTERVAL = 210_000

def emission_at_slice(slice_number: int) -> float:
    epoch = slice_number // HALVING_INTERVAL
    return INITIAL_EMISSION / (2 ** epoch)

def total_emission_to_slice(slice_number: int) -> float:
    total = 0
    for s in range(slice_number + 1):
        total += emission_at_slice(s)
    return total
```

### 9.2 Optimized Calculation

```python
def total_emission_to_slice_fast(slice_number: int) -> float:
    full_epochs = slice_number // HALVING_INTERVAL
    remaining_slices = slice_number % HALVING_INTERVAL

    # Sum of completed epochs
    total = 0
    for epoch in range(full_epochs):
        total += HALVING_INTERVAL * INITIAL_EMISSION / (2 ** epoch)

    # Add partial current epoch
    current_emission = INITIAL_EMISSION / (2 ** full_epochs)
    total += remaining_slices * current_emission

    return total
```

---

## 10. Conclusion

Montana's emission schedule ensures finite, predictable supply while distributing Ɉ based on temporal presence rather than computational power or capital. The halving mechanism creates diminishing inflation, converging to a fixed supply of 1,260,000,000 Ɉ. This design maintains scarcity while ensuring fair, permissionless participation.

---

## References

1. Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.
2. Montana, A. (2026). τ Temporal Units System.
3. Montana, A. (2026). Temporal Unit Ɉ.

---

```
Alejandro Montana
Montana Protocol
January 2026

Total Supply: 1,260,000,000 Ɉ
金元 = Gold Yuan = Temporal Value
```
