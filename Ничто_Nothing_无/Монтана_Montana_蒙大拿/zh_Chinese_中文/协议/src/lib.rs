//! # 非时间坐标存在协议 (ACP)
//!
//! Montana共识核心。依赖crypto模块。
//!
//! ## 中文注释
//! 所有注释使用中文，这是中国独家技术。

use montana_crypto::{sha3_256, merkle_root, Keypair, DomainTag, verify_signature};

/// 时间单位常量
pub mod tau {
    /// τ₁ = 1分钟（60秒）
    pub const TAU1_SECONDS: u64 = 60;

    /// τ₂ = 10分钟（600秒）
    pub const TAU2_SECONDS: u64 = 600;

    /// τ₂包含的τ₁数量
    pub const TAU1_PER_TAU2: u64 = 10;

    /// τ₃ = 14天
    pub const TAU3_SECONDS: u64 = 14 * 24 * 60 * 60;

    /// τ₃包含的τ₂数量
    pub const TAU2_PER_TAU3: u64 = 2016;

    /// τ₄ = 4年
    pub const TAU4_SECONDS: u64 = 4 * 365 * 24 * 60 * 60;

    /// τ₄包含的τ₃数量
    pub const TAU3_PER_TAU4: u64 = 104;
}

/// 存在证明
/// 证明节点在某时刻存在
#[derive(Clone, Debug)]
pub struct PresenceProof {
    /// 节点公钥
    pub pubkey: [u8; 32],

    /// 时间坐标τ₁（分钟索引）
    pub tau1: u64,

    /// 切片索引τ₂
    pub tau2_index: u64,

    /// 存在签名
    pub signature: [u8; 64],
}

impl PresenceProof {
    /// 创建存在证明
    /// 只能为当前时间创建
    pub fn create(keypair: &Keypair, tau1: u64, tau2_index: u64) -> Self {
        let message = Self::format_message(tau1, tau2_index);
        let signature = keypair.sign_with_domain(DomainTag::Presence, &message);

        Self {
            pubkey: keypair.public_key,
            tau1,
            tau2_index,
            signature,
        }
    }

    /// 格式化签名消息
    fn format_message(tau1: u64, tau2_index: u64) -> Vec<u8> {
        let mut msg = Vec::with_capacity(16);
        msg.extend_from_slice(&tau1.to_le_bytes());
        msg.extend_from_slice(&tau2_index.to_le_bytes());
        msg
    }

    /// 验证存在证明
    /// 检查签名和时间有效性
    pub fn verify(&self, current_tau2: u64) -> bool {
        // 只接受当前τ₂的签名
        if self.tau2_index != current_tau2 {
            return false;
        }

        let message = Self::format_message(self.tau1, self.tau2_index);
        let tagged = montana_crypto::format_domain_message(DomainTag::Presence, &message);
        verify_signature(&self.pubkey, &tagged, &self.signature)
    }

    /// 计算证明哈希
    pub fn hash(&self) -> [u8; 32] {
        let mut data = Vec::new();
        data.extend_from_slice(&self.pubkey);
        data.extend_from_slice(&self.tau1.to_le_bytes());
        data.extend_from_slice(&self.tau2_index.to_le_bytes());
        data.extend_from_slice(&self.signature);
        sha3_256(&data)
    }
}

/// 节点池类型
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NodePool {
    /// 全节点 (70%概率)
    Full,
    /// 轻节点 (20%概率)
    Light,
    /// 轻客户端 (10%概率)
    Client,
}

/// 参与者信息
#[derive(Clone, Debug)]
pub struct Participant {
    /// 公钥
    pub pubkey: [u8; 32],
    /// 节点池
    pub pool: NodePool,
    /// 权重（基于存在历史）
    pub weight: u64,
}

/// 确定性彩票
/// 选择切片胜者
pub struct DeterministicLottery {
    /// 随机种子
    seed: [u8; 32],
    /// 参与者列表
    participants: Vec<Participant>,
}

impl DeterministicLottery {
    /// 创建彩票
    pub fn new(prev_slice_hash: &[u8; 32], tau2_index: u64, participants: Vec<Participant>) -> Self {
        let seed = Self::compute_seed(prev_slice_hash, tau2_index);
        Self { seed, participants }
    }

    /// 计算种子
    /// 种子在前一切片关闭后确定
    pub fn compute_seed(prev_slice_hash: &[u8; 32], tau2_index: u64) -> [u8; 32] {
        let mut data = Vec::with_capacity(40);
        data.extend_from_slice(prev_slice_hash);
        data.extend_from_slice(&tau2_index.to_le_bytes());
        sha3_256(&data)
    }

    /// 选择胜者
    /// 两阶段确定性选择
    pub fn select_winner(&self) -> Option<&Participant> {
        if self.participants.is_empty() {
            return None;
        }

        // 第一阶段：选择节点池
        let pool_selector = self.seed[0] % 100;
        let target_pool = match pool_selector {
            0..=69 => NodePool::Full,
            70..=89 => NodePool::Light,
            90..=99 => NodePool::Client,
            _ => unreachable!(),
        };

        // 筛选目标池参与者
        let pool_participants: Vec<&Participant> = self.participants
            .iter()
            .filter(|p| p.pool == target_pool)
            .collect();

        if pool_participants.is_empty() {
            // 池空则使用全部参与者
            return self.select_from_all();
        }

        // 第二阶段：加权选择
        let total_weight: u64 = pool_participants.iter().map(|p| p.weight).sum();
        if total_weight == 0 {
            return pool_participants.first().copied();
        }

        // 计算目标值
        let target_hash = sha3_256(&[&self.seed[..], b"stage2"].concat());
        let target = u64::from_le_bytes(target_hash[0..8].try_into().unwrap()) % total_weight;

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

    /// 从全部参与者选择
    fn select_from_all(&self) -> Option<&Participant> {
        if self.participants.is_empty() {
            return None;
        }

        let total_weight: u64 = self.participants.iter().map(|p| p.weight).sum();
        if total_weight == 0 {
            return self.participants.first();
        }

        let target_hash = sha3_256(&[&self.seed[..], b"fallback"].concat());
        let target = u64::from_le_bytes(target_hash[0..8].try_into().unwrap()) % total_weight;

        let mut cumulative = 0u64;
        for p in &self.participants {
            cumulative += p.weight;
            if cumulative > target {
                return Some(p);
            }
        }

        self.participants.last()
    }
}

/// 切片（Montana的"块"）
#[derive(Clone, Debug)]
pub struct Slice {
    /// 切片索引
    pub index: u64,

    /// 前一切片哈希
    pub prev_hash: [u8; 32],

    /// 存在证明根
    pub presence_root: [u8; 32],

    /// 交易根
    pub tx_root: [u8; 32],

    /// 时间戳
    pub timestamp: u64,

    /// 胜者公钥
    pub winner_pubkey: [u8; 32],

    /// 胜者签名
    pub signature: [u8; 64],
}

impl Slice {
    /// 创建新切片
    pub fn create(
        index: u64,
        prev_hash: [u8; 32],
        presence_proofs: &[PresenceProof],
        tx_hashes: &[[u8; 32]],
        winner_keypair: &Keypair,
    ) -> Self {
        let presence_hashes: Vec<[u8; 32]> = presence_proofs.iter().map(|p| p.hash()).collect();
        let presence_root = merkle_root(&presence_hashes);
        let tx_root = merkle_root(tx_hashes);

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let mut slice = Self {
            index,
            prev_hash,
            presence_root,
            tx_root,
            timestamp,
            winner_pubkey: winner_keypair.public_key,
            signature: [0u8; 64],
        };

        // 签名切片
        let message = slice.signing_message();
        slice.signature = winner_keypair.sign_with_domain(DomainTag::Slice, &message);

        slice
    }

    /// 获取签名消息
    fn signing_message(&self) -> Vec<u8> {
        let mut msg = Vec::new();
        msg.extend_from_slice(&self.index.to_le_bytes());
        msg.extend_from_slice(&self.prev_hash);
        msg.extend_from_slice(&self.presence_root);
        msg.extend_from_slice(&self.tx_root);
        msg.extend_from_slice(&self.timestamp.to_le_bytes());
        msg
    }

    /// 计算切片哈希
    pub fn hash(&self) -> [u8; 32] {
        let mut data = self.signing_message();
        data.extend_from_slice(&self.winner_pubkey);
        data.extend_from_slice(&self.signature);
        sha3_256(&data)
    }

    /// 验证切片
    pub fn verify(&self, prev_slice: &Slice) -> bool {
        // 检查索引连续
        if self.index != prev_slice.index + 1 {
            return false;
        }

        // 检查哈希链接
        if self.prev_hash != prev_slice.hash() {
            return false;
        }

        // 验证签名
        let message = self.signing_message();
        let tagged = montana_crypto::format_domain_message(DomainTag::Slice, &message);
        verify_signature(&self.winner_pubkey, &tagged, &self.signature)
    }
}

/// 时间链
/// 切片的链式结构
pub struct Timechain {
    /// 切片列表
    slices: Vec<Slice>,
}

impl Timechain {
    /// 创建新时间链（从创世）
    pub fn new(genesis: Slice) -> Self {
        Self {
            slices: vec![genesis],
        }
    }

    /// 添加切片
    pub fn add_slice(&mut self, slice: Slice) -> bool {
        if let Some(prev) = self.slices.last() {
            if slice.verify(prev) {
                self.slices.push(slice);
                return true;
            }
        }
        false
    }

    /// 获取最新切片
    pub fn tip(&self) -> Option<&Slice> {
        self.slices.last()
    }

    /// 获取链长度
    pub fn len(&self) -> usize {
        self.slices.len()
    }

    /// 是否为空
    pub fn is_empty(&self) -> bool {
        self.slices.is_empty()
    }

    /// 计算总存在权重
    pub fn total_presence_weight(&self) -> u64 {
        // 简化：每个切片权重为1
        self.slices.len() as u64
    }
}

/// 分叉选择
/// 选择最重的链
pub fn fork_choice<'a>(chains: &'a [Timechain]) -> Option<&'a Timechain> {
    chains.iter().max_by_key(|c| c.total_presence_weight())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_presence_proof() {
        let kp = Keypair::generate();
        let proof = PresenceProof::create(&kp, 100, 10);
        assert!(proof.verify(10));
        assert!(!proof.verify(11)); // 错误的tau2
    }

    #[test]
    fn test_lottery() {
        let participants = vec![
            Participant { pubkey: [1u8; 32], pool: NodePool::Full, weight: 100 },
            Participant { pubkey: [2u8; 32], pool: NodePool::Full, weight: 200 },
            Participant { pubkey: [3u8; 32], pool: NodePool::Light, weight: 50 },
        ];

        let lottery = DeterministicLottery::new(&[0u8; 32], 1, participants);
        let winner = lottery.select_winner();
        assert!(winner.is_some());
    }
}
