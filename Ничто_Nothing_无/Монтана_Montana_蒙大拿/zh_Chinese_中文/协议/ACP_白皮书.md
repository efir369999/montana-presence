# 非时间坐标存在协议 (ACP)

**版本:** 1.0
**日期:** 2026年1月
**语言:** 中文 (独家)

---

## 定义

**ACP** — Atemporal Coordinate Presence (非时间坐标存在)

```
ACP = 通过密码学证明时间存在
```

> *"时间是唯一平等分配给所有人的资源。"*

---

## 核心原理

### 时间坐标层级

| 单位 | 持续时间 | 用途 |
|------|----------|------|
| **τ₁** | 1分钟 | 存在签名 |
| **τ₂** | 10分钟 | 切片（块） |
| **τ₃** | 14天 | 检查点 |
| **τ₄** | 4年 | 纪元 |

```
τ₄ 包含 104 × τ₃
τ₃ 包含 2,016 × τ₂
τ₂ 包含 10 × τ₁
```

---

## 存在证明

```rust
// 存在证明结构（中文注释）
pub struct PresenceProof {
    /// 节点公钥 (ML-DSA-65)
    /// 后量子安全签名算法
    pub pubkey: [u8; 1952],

    /// 时间坐标 τ₁
    /// 精确到分钟的时间戳
    pub tau1: u64,

    /// 切片索引 τ₂
    /// 当前切片的序号
    pub tau2_index: u64,

    /// 存在签名
    /// 证明节点在此时刻存在
    pub signature: [u8; 3309],
}

impl PresenceProof {
    /// 创建存在证明
    /// 只能为当前时间创建，不能伪造过去
    pub fn create(keypair: &Keypair, tau2_index: u64) -> Self {
        let tau1 = current_tau1();  // 当前分钟
        let message = Self::format_message(tau1, tau2_index);
        let signature = keypair.sign(&message);

        Self {
            pubkey: keypair.public_key(),
            tau1,
            tau2_index,
            signature,
        }
    }

    /// 验证存在证明
    /// 检查签名有效性和时间正确性
    pub fn verify(&self, current_tau2: u64) -> bool {
        // 签名只接受当前 τ₂
        // 这是核心安全保证
        if self.tau2_index != current_tau2 {
            return false;
        }

        let message = Self::format_message(self.tau1, self.tau2_index);
        verify_signature(&self.pubkey, &message, &self.signature)
    }
}
```

---

## 确定性彩票

选择切片胜者的算法：

```rust
/// 确定性彩票
/// 所有节点计算相同结果
pub struct DeterministicLottery {
    /// 随机种子
    /// 来自前一个切片的哈希
    seed: [u8; 32],

    /// 参与者列表
    /// 按公钥排序（确定性顺序）
    participants: Vec<Participant>,
}

impl DeterministicLottery {
    /// 计算种子
    /// 种子在前一个切片关闭后才确定
    pub fn compute_seed(prev_slice_hash: &[u8; 32], tau2_index: u64) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(prev_slice_hash);      // 前一切片哈希
        hasher.update(&tau2_index.to_le_bytes()); // 当前索引
        hasher.finalize().into()
    }

    /// 选择胜者
    /// 两阶段选择确保公平
    pub fn select_winner(&self) -> Option<&Participant> {
        // 第一阶段：选择节点池
        let pool_selector = self.seed[0] % 100;
        let pool = match pool_selector {
            0..=69 => NodePool::Full,      // 70% 概率
            70..=89 => NodePool::Light,    // 20% 概率
            90..=99 => NodePool::Client,   // 10% 概率
            _ => unreachable!(),
        };

        // 第二阶段：池内加权选择
        let pool_participants: Vec<_> = self.participants
            .iter()
            .filter(|p| p.pool == pool)
            .collect();

        if pool_participants.is_empty() {
            return None;
        }

        // 计算累积权重
        let total_weight: u64 = pool_participants
            .iter()
            .map(|p| p.weight)
            .sum();

        // 选择目标
        let target_bytes = sha3_256(&[&self.seed[..], b"stage2"].concat());
        let target = u64::from_le_bytes(target_bytes[0..8].try_into().unwrap())
            % total_weight;

        // 找到胜者
        let mut cumulative = 0u64;
        for p in &pool_participants {
            cumulative += p.weight;
            if cumulative > target {
                return Some(p);
            }
        }

        pool_participants.last().copied()
    }
}
```

---

## 切片结构

```rust
/// 切片（Montana的"块"）
/// 每10分钟产生一个
pub struct Slice {
    /// 切片索引
    /// 从创世切片开始递增
    pub index: u64,

    /// 前一切片哈希
    /// 链接到链上
    pub prev_hash: [u8; 32],

    /// 存在根
    /// 所有存在证明的默克尔根
    pub presence_root: [u8; 32],

    /// 交易根
    /// 所有交易的默克尔根
    pub tx_root: [u8; 32],

    /// 时间戳
    /// 切片创建时间
    pub timestamp: u64,

    /// 胜者签名
    /// 彩票胜者签署整个切片
    pub signature: [u8; 3309],

    /// 胜者公钥
    pub winner_pubkey: [u8; 1952],
}

impl Slice {
    /// 验证切片
    pub fn verify(&self, prev_slice: &Slice) -> bool {
        // 1. 检查索引连续性
        if self.index != prev_slice.index + 1 {
            return false;
        }

        // 2. 检查哈希链接
        if self.prev_hash != prev_slice.hash() {
            return false;
        }

        // 3. 验证胜者是否正确
        let lottery = DeterministicLottery::new(
            &self.prev_hash,
            self.index,
        );
        let expected_winner = lottery.select_winner();
        if expected_winner.map(|w| w.pubkey) != Some(self.winner_pubkey) {
            return false;
        }

        // 4. 验证签名
        let message = self.signing_message();
        verify_signature(&self.winner_pubkey, &message, &self.signature)
    }

    /// 计算切片哈希
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.index.to_le_bytes());
        hasher.update(&self.prev_hash);
        hasher.update(&self.presence_root);
        hasher.update(&self.tx_root);
        hasher.update(&self.timestamp.to_le_bytes());
        hasher.finalize().into()
    }
}
```

---

## 时间链

```
┌─────────────────────────────────────────────────────────────┐
│                      时间链结构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Slice₀ ──→ Slice₁ ──→ Slice₂ ──→ ... ──→ Sliceₙ          │
│     │          │          │                   │             │
│     ↓          ↓          ↓                   ↓             │
│  Genesis    10分钟后    20分钟后           n×10分钟后        │
│                                                             │
│   每个切片包含:                                              │
│   - 前一切片哈希 (链接)                                      │
│   - 存在证明根 (时间证明)                                    │
│   - 交易根 (价值转移)                                        │
│   - 胜者签名 (共识)                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 分叉选择规则

```rust
/// 分叉选择
/// 选择最重的链（最多存在证明）
pub fn fork_choice(chains: &[Chain]) -> &Chain {
    chains
        .iter()
        .max_by_key(|chain| chain.total_presence_weight())
        .expect("至少有一条链")
}

impl Chain {
    /// 计算链的总存在权重
    pub fn total_presence_weight(&self) -> u64 {
        self.slices
            .iter()
            .map(|slice| slice.presence_count)
            .sum()
    }
}
```

---

## 安全属性

### 不可伪造性

```
伪造存在 = 伪造时间 = 违反物理定律
```

### 不可逆转性

```
14天的存在需要14天
无论计算能力多强
时间是唯一的限制因素
```

### 确定性

```
所有节点计算相同结果
彩票是确定性的
切片选择是确定性的
```

---

## 节点类型

| 类型 | 功能 | 存储 | 彩票概率 |
|------|------|------|----------|
| **全节点** | 完整验证 | 完整时间链 | 70% |
| **轻节点** | 头部验证 | 头部+检查点 | 20% |
| **轻客户端** | 发送签名 | 仅自己数据 | 10% |

---

## 与其他共识的对比

| 属性 | PoW | PoS | ACP |
|------|-----|-----|-----|
| 资源 | 计算 | 资本 | 时间 |
| 可加速 | 是 | 否 | 否 |
| 公平性 | 低 | 中 | 高 |
| 能耗 | 高 | 低 | 极低 |
| 量子安全 | 否 | 否 | 是 |

---

## 结论

ACP协议实现了:
- **时间证明:** 不可伪造的存在
- **公平共识:** 时间平等分配
- **确定性选择:** 所有节点一致
- **量子安全:** ML-DSA签名

时间是新的工作证明。存在是新的共识。

---

*Alejandro Montana*
*github.com/afgrouptime*
*x.com/tojesatoshi*
