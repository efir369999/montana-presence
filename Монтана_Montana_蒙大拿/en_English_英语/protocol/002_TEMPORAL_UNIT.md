# 金元Ɉ (Temporal Unit)

**Montana Temporal Unit**
**Montana Protocol v1.0**

---

## Abstract

金元Ɉ — the first cryptocurrency where the unit of measurement is tied to time. The symbol combines three concepts: 金 (gold/value), 元 (genesis/origin), Ɉ (time). Key property: 1 Ɉ asymptotically approaches 1 second.

**Key formula:**
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

**Source code:** [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs)

```rust
pub const GENESIS_TIMESTAMP: u64 = 1735862400;  // 2026-01-03 00:00:00 UTC

pub const TAU1_MINUTES: u64 = 1;        // τ₁ = 1 minute
pub const TAU2_MINUTES: u64 = 10;       // τ₂ = 10 minutes (slice)
pub const TAU3_MINUTES: u64 = 20_160;   // τ₃ = 14 days (epoch)
pub const TAU4_MINUTES: u64 = 2_102_400; // τ₄ = 4 years (halving)
```

### 2.2 Conversion Table

| Unit | Value | In Seconds | In Ɉ |
|------|-------|------------|------|
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

**Source code:** [types.rs#L40-L45](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs#L40-L45)

### 3.2 Fixed Rates

| Currency | Rate | Status |
|----------|------|--------|
| USD | $0.16 | Fixed forever |
| RUB | 12.09₽ | Fixed forever |
| AMD | 83.46 dram | Fixed forever |
| BTC | 0.00000278 | Fixed forever |

---

## 4. Emission

### 4.1 Slice Reward

**Source code:** [types.rs#L25-L36](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs#L25-L36)

```rust
pub const REWARD_PER_TAU2: u64 = 3000;      // 3000 Ɉ per τ₂
pub const TOTAL_SUPPLY: u64 = 1_260_000_000; // Maximum
pub const HALVING_INTERVAL: u64 = 210_000;   // ~4 years (τ₄)

pub fn calculate_reward(slice_index: u64) -> u64 {
    let halvings = slice_index / HALVING_INTERVAL;
    if halvings >= 64 {
        return 0;
    }
    REWARD_PER_TAU2 >> halvings
}
```

### 4.2 Halving Schedule

| Halving | Reward | Period |
|---------|--------|--------|
| 0 | 3000 Ɉ | Years 1-4 |
| 1 | 1500 Ɉ | Years 5-8 |
| 2 | 750 Ɉ | Years 9-12 |
| ... | ... | ... |
| 64 | 0 Ɉ | Final |

---

## 5. Scientific Novelty

1. **Temporal peg** — currency unit = time unit
2. **Objective genesis** — price determined by independent market event (Beeple)
3. **Fixed rates** — protection from fiat peg volatility
4. **Asymptotic convergence** — 1 Ɉ → 1 second with infinite evidence

---

## 6. References

| Document | Link |
|----------|------|
| Montana Protocol | [MONTANA.md](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/MONTANA.md) |
| Types and Constants | [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs) |
| ACP Consensus | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
