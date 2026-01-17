# 创世即后量子

**从第一天起的量子抗性密码学**
**Montana协议 v1.0**

---

## 摘要

Montana从创世开始使用后量子密码学（ML-DSA-65、ML-KEM-768），而非事后改装。当量子计算机成为威胁时，Montana已经受到保护。其他网络将被迫进行硬分叉。

**关键区别:**
```
比特币/以太坊: 现在ECDSA → 以后硬分叉
Montana: 创世即ML-DSA-65 → 已受保护
```

---

## 1. 引言

### 1.1 量子威胁

| 算法 | 易受攻击 | 量子攻击 |
|------|----------|----------|
| ECDSA（比特币）| 是 | Shor算法 |
| Ed25519（Solana）| 是 | Shor算法 |
| RSA | 是 | Shor算法 |
| **ML-DSA-65** | **否** | **基于格** |

### 1.2 改装问题

```
步骤1: 量子计算机出现
步骤2: 所有ECDSA签名易受攻击
步骤3: 硬分叉进行密钥迁移
步骤4: 未迁移者 — 损失资金
```

Montana通过从后量子密码学开始来避免这个问题。

---

## 2. 密码学原语

### 2.1 签名: ML-DSA-65

**源代码:** [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs)

```rust
// FIPS 204 — 基于模格的数字签名
// 安全级别: NIST Level 3（128位后量子）
// 签名大小: 3293字节
// 公钥大小: 1952字节
```

### 2.2 加密: ML-KEM-768

```rust
// FIPS 203 — 基于模格的密钥封装
// 安全级别: NIST Level 3
// 在Noise XX中用于密钥交换
```

### 2.3 混合加密

**源代码:** [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs)

```rust
// Noise XX + ML-KEM-768
// 经典X25519 + 后量子ML-KEM
// 即使其中一个被破解也受保护
```

---

## 3. 为什么从创世开始？

### 3.1 策略比较

| 策略 | 复杂性 | 风险 |
|------|--------|------|
| 威胁后改装 | 硬分叉、迁移 | 资金损失 |
| 提前改装 | 硬分叉、迁移 | 协调困难 |
| **从创世开始** | **无需迁移** | **无风险** |

### 3.2 先收获后解密

```
今天的攻击者:
1. 拦截加密流量
2. 存储在磁盘上
3. 等待量子计算机
4. 解密一切

Montana从第一天起就受到保护免受此攻击。
```

---

## 4. 科学创新

1. **创世即后量子** — 非改装，而是原始设计
2. **混合加密** — X25519 + ML-KEM（防护两类攻击）
3. **NIST标准** — 非实验算法，而是最终确定的FIPS
4. **域分离** — 不同目的使用不同密钥

---

## 5. 参考文献

| 文档 | 链接 |
|------|------|
| 密码学代码 | [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs) |
| Noise代码 | [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs) |
| FIPS 204 (ML-DSA) | [NIST](https://csrc.nist.gov/publications/detail/fips/204/final) |
| FIPS 203 (ML-KEM) | [NIST](https://csrc.nist.gov/publications/detail/fips/203/final) |

---

```
Alejandro Montana
Montana协议 v1.0
2026年1月

github.com/efir369999/junomontanaagibot
```
