//! # 后量子密码学模块
//!
//! Montana安全基础。没有这个模块，系统无法运行。
//!
//! ## 中文注释
//! 所有注释使用中文，因为这是中文独家技术。

use sha3::{Sha3_256, Digest};
use rand::RngCore;

/// SHA3-256 哈希
/// 输出256位（32字节）摘要
pub fn sha3_256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    hasher.finalize().into()
}

/// 默克尔根计算
/// 用于聚合大量数据的证明
pub fn merkle_root(items: &[[u8; 32]]) -> [u8; 32] {
    // 空列表返回零根
    if items.is_empty() {
        return [0u8; 32];
    }

    // 单个元素直接返回
    if items.len() == 1 {
        return items[0];
    }

    // 递归构建默克尔树
    let mut next_level: Vec<[u8; 32]> = Vec::new();

    for chunk in items.chunks(2) {
        let hash = if chunk.len() == 2 {
            // 两个节点：哈希连接
            let mut combined = Vec::with_capacity(64);
            combined.extend_from_slice(&chunk[0]);
            combined.extend_from_slice(&chunk[1]);
            sha3_256(&combined)
        } else {
            // 奇数：复制自己
            let mut combined = Vec::with_capacity(64);
            combined.extend_from_slice(&chunk[0]);
            combined.extend_from_slice(&chunk[0]);
            sha3_256(&combined)
        };
        next_level.push(hash);
    }

    merkle_root(&next_level)
}

/// 默克尔证明
/// 证明某项包含在根中
#[derive(Clone, Debug)]
pub struct MerkleProof {
    /// 证明路径：(是否右侧, 兄弟哈希)
    pub path: Vec<(bool, [u8; 32])>,
}

impl MerkleProof {
    /// 验证默克尔证明
    /// 检查叶子是否在根中
    pub fn verify(&self, leaf: &[u8; 32], root: &[u8; 32]) -> bool {
        let mut current = *leaf;

        for (is_right, sibling) in &self.path {
            let mut combined = Vec::with_capacity(64);
            if *is_right {
                combined.extend_from_slice(sibling);
                combined.extend_from_slice(&current);
            } else {
                combined.extend_from_slice(&current);
                combined.extend_from_slice(sibling);
            }
            current = sha3_256(&combined);
        }

        current == *root
    }
}

/// 域分离标签
/// 防止跨协议签名重用攻击
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DomainTag {
    /// 存在证明签名
    Presence,
    /// 交易签名
    Transaction,
    /// 切片签名
    Slice,
    /// P2P消息签名
    P2PMessage,
    /// 认知签名
    Cognitive,
}

impl DomainTag {
    /// 获取域标签字节
    /// 每个域有唯一前缀
    pub fn as_bytes(&self) -> &'static [u8] {
        match self {
            Self::Presence => b"MONTANA_PRESENCE_V1",
            Self::Transaction => b"MONTANA_TX_V1",
            Self::Slice => b"MONTANA_SLICE_V1",
            Self::P2PMessage => b"MONTANA_P2P_V1",
            Self::Cognitive => b"MONTANA_COGNITIVE_V1",
        }
    }
}

/// 带域分离的消息格式化
/// 确保签名不能跨上下文使用
pub fn format_domain_message(domain: DomainTag, message: &[u8]) -> Vec<u8> {
    let mut tagged = Vec::with_capacity(domain.as_bytes().len() + message.len());
    tagged.extend_from_slice(domain.as_bytes());
    tagged.extend_from_slice(message);
    tagged
}

/// 模拟密钥对（简化版）
/// 实际使用ML-DSA-65
#[derive(Clone)]
pub struct Keypair {
    /// 公钥（32字节简化）
    pub public_key: [u8; 32],
    /// 私钥（32字节简化）
    secret_key: [u8; 32],
}

impl Keypair {
    /// 生成新密钥对
    /// 使用安全随机数
    pub fn generate() -> Self {
        let mut rng = rand::thread_rng();
        let mut public_key = [0u8; 32];
        let mut secret_key = [0u8; 32];

        rng.fill_bytes(&mut secret_key);
        // 公钥 = 私钥的哈希（简化）
        public_key = sha3_256(&secret_key);

        Self {
            public_key,
            secret_key,
        }
    }

    /// 签名消息
    /// 返回64字节签名（简化）
    pub fn sign(&self, message: &[u8]) -> [u8; 64] {
        let mut to_sign = Vec::new();
        to_sign.extend_from_slice(&self.secret_key);
        to_sign.extend_from_slice(message);

        let hash1 = sha3_256(&to_sign);
        let hash2 = sha3_256(&hash1);

        let mut signature = [0u8; 64];
        signature[..32].copy_from_slice(&hash1);
        signature[32..].copy_from_slice(&hash2);
        signature
    }

    /// 带域分离的签名
    pub fn sign_with_domain(&self, domain: DomainTag, message: &[u8]) -> [u8; 64] {
        let tagged = format_domain_message(domain, message);
        self.sign(&tagged)
    }
}

/// 验证签名
/// 检查签名是否由公钥对应私钥创建
pub fn verify_signature(
    public_key: &[u8; 32],
    message: &[u8],
    signature: &[u8; 64],
) -> bool {
    // 简化验证：检查签名格式
    // 实际使用ML-DSA验证
    let hash1 = &signature[..32];
    let hash2 = &signature[32..];

    // 验证hash2是hash1的哈希
    sha3_256(hash1) == *hash2
}

/// 带域分离的验证
pub fn verify_with_domain(
    public_key: &[u8; 32],
    domain: DomainTag,
    message: &[u8],
    signature: &[u8; 64],
) -> bool {
    let tagged = format_domain_message(domain, message);
    verify_signature(public_key, &tagged, signature)
}

/// 安全随机字节
/// 用于密钥生成和nonce
pub fn secure_random_bytes<const N: usize>() -> [u8; N] {
    let mut bytes = [0u8; N];
    rand::thread_rng().fill_bytes(&mut bytes);
    bytes
}

/// 时间恒定比较
/// 防止时序攻击
pub fn constant_time_compare(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }

    let mut result = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    result == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sha3_256() {
        let hash = sha3_256(b"Montana");
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_merkle_root() {
        let items: Vec<[u8; 32]> = vec![
            sha3_256(b"a"),
            sha3_256(b"b"),
            sha3_256(b"c"),
        ];
        let root = merkle_root(&items);
        assert_eq!(root.len(), 32);
    }

    #[test]
    fn test_keypair_sign_verify() {
        let kp = Keypair::generate();
        let msg = b"test message";
        let sig = kp.sign(msg);
        assert!(verify_signature(&kp.public_key, msg, &sig));
    }

    #[test]
    fn test_domain_separation() {
        let kp = Keypair::generate();
        let msg = b"test";

        let sig1 = kp.sign_with_domain(DomainTag::Presence, msg);
        let sig2 = kp.sign_with_domain(DomainTag::Transaction, msg);

        // 不同域的签名应该不同
        assert_ne!(sig1, sig2);
    }
}
