# 金元Ɉ (Temporal Unit)

**Montana Temporal Unit**
**Montana Protocol v1.0**

**Status:** ✅ Implemented in Python

---

## Abstract

金元Ɉ — the first cryptocurrency where the unit of measurement is tied to time. The symbol combines three concepts: 金 (gold/value), 元 (genesis/origin), Ɉ (time). Key property: 1 Ɉ asymptotically approaches 1 second.

**Key Formula:**
```
lim(evidence → ∞) 1 Ɉ → 1 second
```

---

## 1. Introduction

### 1.1 Problem with Existing Units

| Cryptocurrency | Unit | Peg | Problem |
|----------------|------|-----|---------|
| Bitcoin | BTC | Market | Volatility |
| Ethereum | ETH | Market | Volatility |
| Stablecoins | USD | Fiat | Inflation |
| **Montana** | **Ɉ** | **Time** | **None** |

### 1.2 Symbolism

**金** — gold (value)
**元** — genesis (origin)
**Ɉ** — time (unit)

---

## 2. Temporal System

### 2.1 τ Units

**Source Code:** [time_bank.py:55-64](../бот/time_bank.py#L55-L64)

```python
# Temporal Coordinates
TAU1_INTERVAL_SEC = 60                 # τ₁ = 1 minute
T2_DURATION_SEC = 10 * 60              # τ₂ = 10 minutes = 600 seconds
TAU3_DURATION_SEC = 14 * 24 * 60 * 60  # τ₃ = 14 days = 1,209,600 sec
TAU4_DURATION_SEC = 4 * 365 * 24 * 60 * 60  # τ₄ = 4 years

# Hierarchy
T2_PER_TAU3 = 2016                     # 2016 × τ₂ in τ₃
TAU3_PER_YEAR = 26                     # 26 × τ₃ per year
TAU3_PER_TAU4 = 104                    # 104 × τ₃ in τ₄
```

### 2.2 Conversion Table

| Unit | Value | In Seconds | In Ɉ (base) |
|------|-------|------------|-------------|
| τ₁ | 1 minute | 60 | 60 Ɉ |
| τ₂ | 10 minutes | 600 | 600 Ɉ |
| τ₃ | 14 days | 1,209,600 | 1,209,600 Ɉ |
| τ₄ | 4 years | 126,144,000 | 126,144,000 Ɉ |

---

## 3. Genesis Formula

### 3.1 Beeple Anchor

The sale of Beeple's NFT "Everydays: The First 5000 Days" on March 11, 2021 established the genesis price of time:

```
$69,300,000 ÷ 5000 days ÷ 86400 sec = $0.1605/sec
```

### 3.2 Fixed Rates

| Currency | Rate | Status |
|----------|------|--------|
| USD | $0.16 | Fixed forever |
| RUB | 12.09₽ | Fixed forever |
| AMD | 83.46 dram | Fixed forever |
| BTC | 0.00000278 | Fixed forever |

---

## 4. Emission with Halving

### 4.1 Halving Every τ₄

**Source Code:** [time_bank.py:82-107](../бот/time_bank.py#L82-L107)

```python
def halving_coefficient(tau4_count: int) -> float:
    """
    Halving coefficient — division by 2 every τ₄ (4 years)

    Formula:
        emission_per_second = 1.0 / (2 ** tau4_count)
    """
    return 1.0 / (2 ** tau4_count)
```

### 4.2 Halving Schedule

| Halving | Period | Reward per 1 sec |
|---------|--------|------------------|
| τ₄ #0 | Years 1-4 | 1.0 Ɉ |
| τ₄ #1 | Years 5-8 | 0.5 Ɉ |
| τ₄ #2 | Years 9-12 | 0.25 Ɉ |
| τ₄ #3 | Years 13-16 | 0.125 Ɉ |
| ... | ... | ... |
| τ₄ #64 | ~260 years | ~0 Ɉ |

### 4.3 Mathematical Formulation

Let `n` be the τ₄ epoch number. Reward for 1 second of presence:

```
R(n) = 1 / 2ⁿ Ɉ

Total emission sum (geometric series):
∑(n=0 to ∞) R(n) = 2 × base_emission
```

---

## 5. Presence and Crediting

### 5.1 Crediting Mechanism

**Source Code:** [time_bank.py:560-567](../бот/time_bank.py#L560-L567)

```python
# Distribute: each user gets their seconds × halving
for address, entry in self.presence.all().items():
    if entry["t2_seconds"] > 0:
        coins = int(entry["t2_seconds"] * self.current_halving_coefficient)
        self.db.credit(address, coins, entry.get("addr_type", "unknown"))
        entry["t2_seconds"] = 0
```

### 5.2 Example

```
User was present for 450 seconds in τ₂
Current epoch: τ₄ #0 (halving_coefficient = 1.0)

Crediting: 450 × 1.0 = 450 Ɉ

---

Same user in τ₄ #1 (halving_coefficient = 0.5)

Crediting: 450 × 0.5 = 225 Ɉ
```

---

## 6. Protocol Constants

### 6.1 Coins

**Source Code:** [time_bank.py:67-71](../бот/time_bank.py#L67-L71)

```python
COINS_PER_SECOND = 1                   # 1 second = 1 Ɉ (base)
INACTIVITY_LIMIT_SEC = 3 * 60          # 3 minutes without activity = pause
```

### 6.2 Presence Proof

**Source Code:** [time_bank.py:74-75](../бот/time_bank.py#L74-L75)

```python
PRESENCE_PROOF_VERSION = "MONTANA_PRESENCE_V1"
GENESIS_HASH = "0" * 64                # Genesis prev_hash
```

---

## 7. Scientific Novelty

1. **Temporal binding** — currency unit = time unit
2. **Objective genesis** — price determined by independent market event (Beeple)
3. **Fixed rates** — protection from fiat peg volatility
4. **Asymptotic convergence** — 1 Ɉ → 1 second with infinite proofs
5. **Halving** — classic diminishing emission model (like Bitcoin)

---

## 8. Implementation

| Component | File | Status |
|-----------|------|--------|
| τ Constants | [time_bank.py:55-64](../бот/time_bank.py#L55-L64) | ✅ Working |
| halving_coefficient | [time_bank.py:82-107](../бот/time_bank.py#L82-L107) | ✅ Working |
| Coin crediting | [time_bank.py:560-567](../бот/time_bank.py#L560-L567) | ✅ Working |
| τ₃/τ₄ checkpoints | [time_bank.py:572-593](../бот/time_bank.py#L572-L593) | ✅ Working |

---

## 9. References

| Document | Link |
|----------|------|
| ACP Consensus | [001_ACP.md](001_ACP.md) |
| 3-Mirror | [003_THREE_MIRROR.md](003_THREE_MIRROR.md) |
| Adaptive Cooldown | [004_ADAPTIVE_COOLDOWN.md](004_ADAPTIVE_COOLDOWN.md) |
| Post-Quantum | [007_POST_QUANTUM.md](007_POST_QUANTUM.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026
```
