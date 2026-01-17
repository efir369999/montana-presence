# 金元Ɉ (时间单位)

**Montana时间单位**
**Montana协议 v1.0**

---

## 摘要

金元Ɉ — 第一个计量单位与时间挂钩的加密货币。符号结合三个概念：金（黄金/价值）、元（创世/起源）、Ɉ（时间）。关键属性：1 Ɉ 渐近趋向于1秒。

**关键公式:**
```
lim(evidence → ∞) 1 Ɉ → 1 秒
```

---

## 1. 引言

### 1.1 现有单位的问题

| 加密货币 | 单位 | 锚定 | 问题 |
|----------|------|------|------|
| 比特币 | BTC | 市场 | 波动性 |
| 以太坊 | ETH | 市场 | 波动性 |
| 稳定币 | USD | 法币 | 通货膨胀 |
| **Montana** | **Ɉ** | **时间** | **无** |

### 1.2 符号学

**金** — 黄金（价值）
**元** — 创世（起源）
**Ɉ** — 时间（单位）

---

## 2. 时间系统

### 2.1 τ单位

**源代码:** [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs)

```rust
pub const GENESIS_TIMESTAMP: u64 = 1735862400;  // 2026-01-03 00:00:00 UTC

pub const TAU1_MINUTES: u64 = 1;        // τ₁ = 1分钟
pub const TAU2_MINUTES: u64 = 10;       // τ₂ = 10分钟（切片）
pub const TAU3_MINUTES: u64 = 20_160;   // τ₃ = 14天（纪元）
pub const TAU4_MINUTES: u64 = 2_102_400; // τ₄ = 4年（减半）
```

### 2.2 转换表

| 单位 | 值 | 秒数 | Ɉ |
|------|-----|------|---|
| τ₁ | 1分钟 | 60 | 60 Ɉ |
| τ₂ | 10分钟 | 600 | 600 Ɉ |
| τ₃ | 14天 | 1,209,600 | 1,209,600 Ɉ |
| τ₄ | 4年 | 126,144,000 | 126,144,000 Ɉ |

---

## 3. 创世公式

### 3.1 Beeple锚点

2021年3月11日Beeple NFT "Everydays: The First 5000 Days"的销售确立了时间的创世价格：

```
$69,300,000 ÷ 5000天 ÷ 86400秒 = $0.1605/秒
```

**源代码:** [types.rs#L40-L45](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs#L40-L45)

### 3.2 固定汇率

| 货币 | 汇率 | 状态 |
|------|------|------|
| USD | $0.16 | 永久固定 |
| RUB | 12.09₽ | 永久固定 |
| AMD | 83.46德拉姆 | 永久固定 |
| BTC | 0.00000278 | 永久固定 |

---

## 4. 发行

### 4.1 切片奖励

**源代码:** [types.rs#L25-L36](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs#L25-L36)

```rust
pub const REWARD_PER_TAU2: u64 = 3000;      // 每τ₂ 3000 Ɉ
pub const TOTAL_SUPPLY: u64 = 1_260_000_000; // 最大供应量
pub const HALVING_INTERVAL: u64 = 210_000;   // ~4年（τ₄）

pub fn calculate_reward(slice_index: u64) -> u64 {
    let halvings = slice_index / HALVING_INTERVAL;
    if halvings >= 64 {
        return 0;
    }
    REWARD_PER_TAU2 >> halvings
}
```

### 4.2 减半时间表

| 减半 | 奖励 | 时期 |
|------|------|------|
| 0 | 3000 Ɉ | 第1-4年 |
| 1 | 1500 Ɉ | 第5-8年 |
| 2 | 750 Ɉ | 第9-12年 |
| ... | ... | ... |
| 64 | 0 Ɉ | 最终 |

---

## 5. 科学创新

1. **时间锚定** — 货币单位 = 时间单位
2. **客观创世** — 价格由独立市场事件（Beeple）确定
3. **固定汇率** — 防止法币锚定波动
4. **渐近收敛** — 1 Ɉ → 1秒（证据趋于无穷时）

---

## 6. 参考文献

| 文档 | 链接 |
|------|------|
| Montana协议 | [MONTANA.md](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/MONTANA.md) |
| 类型和常量 | [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs) |
| ACP共识 | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana协议 v1.0
2026年1月

github.com/efir369999/junomontanaagibot
```
