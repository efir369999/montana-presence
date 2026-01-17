# Adaptive Cooldown

**Montana Adaptive Waiting Period**
**Montana Protocol v1.0**

---

## Abstract

Adaptive Cooldown — dynamic Sybil attack protection through variable waiting period for new nodes. Cooldown is calculated based on registration median over the last 14 days. At low load — 1 day. At spike — up to 180 days. Sybil attack cost = time × number of nodes.

**Key formula:**
```
Sybil cost = time × N nodes
Minimum: 1 day × N
Maximum: 180 days × N
```

---

## 1. Introduction

### 1.1 Sybil Attack Problem

| System | Defense | Attack Cost |
|--------|---------|-------------|
| Bitcoin | PoW | Electricity |
| Ethereum | PoS | Capital |
| Social networks | Captcha | Minimal |
| **Montana** | **Time** | **1-180 days/node** |

### 1.2 Montana Solution

Time — the only resource that cannot be accelerated. Adaptive Cooldown converts time into attack cost.

---

## 2. Constants

### 2.1 Parameters from Code

**Source code:** [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs)

```rust
pub const COOLDOWN_MIN_TAU2: u64 = 144;          // 1 day
pub const COOLDOWN_MAX_TAU2: u64 = 25_920;       // 180 days
pub const COOLDOWN_WINDOW_TAU2: u64 = 2_016;     // 14 days (τ₃)
pub const COOLDOWN_DEFAULT_TAU2: u64 = 144;      // Genesis: 1 day
pub const COOLDOWN_SMOOTH_WINDOWS: u64 = 4;      // 56 days
pub const COOLDOWN_MAX_CHANGE_PERCENT: u64 = 20; // ±20% per τ₃
```

### 2.2 Cooldown Range

| Load | Cooldown | Period |
|------|----------|--------|
| Below median | 1-7 days | Linear |
| At median | 7 days | τ₃ / 2 |
| Above median | 7-180 days | Linear |

---

## 3. Calculation Algorithm

### 3.1 Core Formula

**Source code:** [cooldown.rs#L97-L135](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L97-L135)

```rust
let ratio = current_count as f64 / median as f64;

if ratio <= 1.0 {
    // MIN → MID (1 → 7 days)
    COOLDOWN_MIN + ratio * (MID - MIN)
} else {
    // MID → MAX (7 → 180 days)
    MID + (ratio - 1.0) * (MAX - MID)
}
```

### 3.2 Smoothing (56 days)

**Source code:** [cooldown.rs#L50-L74](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L50-L74)

```rust
// 4 τ₃ (56 days) sliding average
fn smoothed_median(&self, current_tau2: u64, tier: u8) -> u64 {
    let mut medians = Vec::new();
    for i in 0..COOLDOWN_SMOOTH_WINDOWS {
        let tau3_idx = current_tau3.saturating_sub(i);
        if let Some(&median) = self.median_history.get(&(tau3_idx, tier)) {
            medians.push(median);
        }
    }
    sum / medians.len()
}
```

### 3.3 Rate Limiting (±20%)

**Source code:** [cooldown.rs#L77-L91](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L77-L91)

```rust
fn rate_limited_cooldown(&self, raw_cooldown: u64, tier: usize) -> u64 {
    let max_change = (previous * COOLDOWN_MAX_CHANGE_PERCENT) / 100;

    if raw_cooldown > previous {
        raw_cooldown.min(previous + max_change)
    } else {
        raw_cooldown.max(previous - max_change)
    }
}
```

---

## 4. Attack Protection

| Attack | Defense Mechanism | Effect |
|--------|-------------------|--------|
| Spike manipulation | 56-day smoothing | Cannot rapidly change cooldown |
| Fast pump | ±20% rate limit | Max 20% change per 14 days |
| Sybil at low load | Minimum 1 day | Guaranteed delay |
| Sybil at spike | Up to 180 days | Exponential cost |

---

## 5. Scientific Novelty

1. **Temporal cost** — time as protective resource instead of capital
2. **Load adaptivity** — cooldown responds to network activity
3. **Manipulation smoothing** — 56-day window prevents spike attacks
4. **Rate limiting** — gradual changes prevent sharp jumps

---

## 6. References

| Document | Link |
|----------|------|
| Cooldown code | [cooldown.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs) |
| Constants | [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs) |
| ACP Consensus | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
