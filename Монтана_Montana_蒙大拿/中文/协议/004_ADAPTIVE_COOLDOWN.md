# 自适应冷却

**Montana自适应等待期**
**Montana协议 v1.0**

---

## 摘要

自适应冷却 — 通过新节点可变等待期进行动态女巫攻击防护。冷却期根据过去14天的注册中位数计算。低负载时 — 1天。峰值时 — 最多180天。女巫攻击成本 = 时间 × 节点数量。

**关键公式:**
```
女巫成本 = 时间 × N节点
最小: 1天 × N
最大: 180天 × N
```

---

## 1. 引言

### 1.1 女巫攻击问题

| 系统 | 防御 | 攻击成本 |
|------|------|----------|
| 比特币 | PoW | 电力 |
| 以太坊 | PoS | 资本 |
| 社交网络 | 验证码 | 最小 |
| **Montana** | **时间** | **1-180天/节点** |

### 1.2 Montana解决方案

时间 — 唯一无法加速的资源。自适应冷却将时间转化为攻击成本。

---

## 2. 常量

### 2.1 代码中的参数

**源代码:** [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs)

```rust
pub const COOLDOWN_MIN_TAU2: u64 = 144;          // 1天
pub const COOLDOWN_MAX_TAU2: u64 = 25_920;       // 180天
pub const COOLDOWN_WINDOW_TAU2: u64 = 2_016;     // 14天 (τ₃)
pub const COOLDOWN_DEFAULT_TAU2: u64 = 144;      // 创世: 1天
pub const COOLDOWN_SMOOTH_WINDOWS: u64 = 4;      // 56天
pub const COOLDOWN_MAX_CHANGE_PERCENT: u64 = 20; // 每τ₃ ±20%
```

### 2.2 冷却范围

| 负载 | 冷却期 | 期间 |
|------|--------|------|
| 低于中位数 | 1-7天 | 线性 |
| 在中位数 | 7天 | τ₃ / 2 |
| 高于中位数 | 7-180天 | 线性 |

---

## 3. 计算算法

### 3.1 核心公式

**源代码:** [cooldown.rs#L97-L135](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L97-L135)

```rust
let ratio = current_count as f64 / median as f64;

if ratio <= 1.0 {
    // MIN → MID (1 → 7天)
    COOLDOWN_MIN + ratio * (MID - MIN)
} else {
    // MID → MAX (7 → 180天)
    MID + (ratio - 1.0) * (MAX - MID)
}
```

### 3.2 平滑 (56天)

**源代码:** [cooldown.rs#L50-L74](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L50-L74)

```rust
// 4 τ₃ (56天) 滑动平均
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

### 3.3 速率限制 (±20%)

**源代码:** [cooldown.rs#L77-L91](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L77-L91)

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

## 4. 攻击防护

| 攻击 | 防御机制 | 效果 |
|------|----------|------|
| 峰值操纵 | 56天平滑 | 无法快速改变冷却期 |
| 快速拉升 | ±20%速率限制 | 每14天最多20%变化 |
| 低负载时女巫攻击 | 最少1天 | 保证延迟 |
| 峰值时女巫攻击 | 最多180天 | 指数级成本 |

---

## 5. 科学创新

1. **时间成本** — 时间作为保护资源而非资本
2. **负载自适应** — 冷却期响应网络活动
3. **操纵平滑** — 56天窗口防止峰值攻击
4. **速率限制** — 渐进变化防止急剧跳跃

---

## 6. 参考文献

| 文档 | 链接 |
|------|------|
| 冷却代码 | [cooldown.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs) |
| 常量 | [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs) |
| ACP共识 | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana协议 v1.0
2026年1月

github.com/efir369999/junomontanaagibot
```
