//! Montana Merkle Proofs для Light Clients
//!
//! Montana использует Merkle trees для двух целей:
//! 1. `presence_root` — корень всех подписей присутствия за τ₂
//! 2. `tx_root` — корень транзакций в слайсе
//!
//! Light clients проверяют:
//! - "Моя подпись присутствия включена в слайс"
//! - "Моя транзакция включена в слайс"

use sha3::{Digest, Sha3_256};
use crate::types::Hash;

/// Merkle proof для включения в дерево
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MerkleProof {
    /// Индекс листа в дереве
    pub leaf_index: u64,
    /// Путь аутентификации (siblings)
    pub siblings: Vec<Hash>,
    /// Направления: true = right sibling, false = left sibling
    pub directions: Vec<bool>,
}

/// Merkle дерево с возможностью генерации proofs
#[derive(Debug, Clone)]
pub struct MerkleTree {
    /// Все уровни дерева (leaves, then internal nodes)
    levels: Vec<Vec<Hash>>,
    /// Количество листьев
    leaf_count: usize,
}

/// Запрос proof от full node
#[derive(Debug, Clone)]
pub struct ProofRequest {
    pub slice_hash: Hash,
    pub leaf_hash: Hash,  // Hash presence или tx
    pub proof_type: ProofType,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProofType {
    Presence,
    Transaction,
}

/// Ответ с proof
#[derive(Debug, Clone)]
pub struct ProofResponse {
    pub proof: MerkleProof,
    pub slice_header: crate::types::SliceHeader,  // Для проверки root
}

// ============================================================================
// CONSTANTS
// ============================================================================

/// Максимальная глубина proof
pub const MAX_PROOF_DEPTH: usize = 32;

/// Domain separation для Merkle
pub const MERKLE_PREFIX: &[u8] = b"MONTANA_MERKLE_V1:";

// ============================================================================
// IMPLEMENTATION
// ============================================================================

impl MerkleTree {
    /// Построить дерево из листьев
    pub fn new(leaves: Vec<Hash>) -> Self {
        if leaves.is_empty() {
            return Self {
                levels: vec![vec![]],
                leaf_count: 0,
            };
        }

        let leaf_count = leaves.len();
        let mut levels = vec![leaves];
        let mut current_level = 0;

        // Строим уровни до корня
        while levels[current_level].len() > 1 {
            let next_level = Self::build_next_level(&levels[current_level]);
            levels.push(next_level);
            current_level += 1;
        }

        Self {
            levels,
            leaf_count,
        }
    }

    /// Получить корень
    pub fn root(&self) -> Hash {
        if self.leaf_count == 0 {
            return [0u8; 32];
        }
        self.levels.last().unwrap()[0]
    }

    /// Сгенерировать proof для листа по индексу
    pub fn proof(&self, leaf_index: usize) -> Option<MerkleProof> {
        if leaf_index >= self.leaf_count {
            return None;
        }

        let mut siblings = Vec::new();
        let mut directions = Vec::new();
        let mut current_index = leaf_index;

        // Проходим от листьев к корню
        for level in 0..self.levels.len() - 1 {
            let level_nodes = &self.levels[level];
            let sibling_index = if current_index % 2 == 0 {
                // Левый узел - sibling справа
                current_index + 1
            } else {
                // Правый узел - sibling слева
                current_index - 1
            };

            if sibling_index < level_nodes.len() {
                siblings.push(level_nodes[sibling_index]);
                directions.push(current_index % 2 == 0); // true = right sibling
            }

            current_index /= 2;
        }

        Some(MerkleProof {
            leaf_index: leaf_index as u64,
            siblings,
            directions,
        })
    }

    /// Сгенерировать proof для листа по хешу
    pub fn proof_by_hash(&self, leaf_hash: &Hash) -> Option<MerkleProof> {
        // Находим индекс листа по хешу
        if let Some(index) = self.levels[0].iter().position(|h| h == leaf_hash) {
            self.proof(index)
        } else {
            None
        }
    }

    /// Построить следующий уровень дерева
    fn build_next_level(level: &[Hash]) -> Vec<Hash> {
        let mut next_level = Vec::new();
        let mut i = 0;

        while i < level.len() {
            if i + 1 < level.len() {
                // Есть пара - хешируем вместе
                let hash = hash_pair(&level[i], &level[i + 1]);
                next_level.push(hash);
                i += 2;
            } else {
                // Одинокий узел - копируем наверх
                next_level.push(level[i]);
                i += 1;
            }
        }

        next_level
    }

    /// Получить лист по индексу
    pub fn get_leaf(&self, index: usize) -> Option<&Hash> {
        self.levels.first()?.get(index)
    }
}

impl MerkleProof {
    /// Верифицировать proof против известного root
    pub fn verify(&self, leaf_hash: Hash, root: Hash) -> bool {
        if self.siblings.len() != self.directions.len() {
            return false;
        }

        let mut current_hash = leaf_hash;

        // Проходим по пути proof
        for (i, &sibling) in self.siblings.iter().enumerate() {
            current_hash = if self.directions[i] {
                // sibling справа
                hash_pair(&current_hash, &sibling)
            } else {
                // sibling слева
                hash_pair(&sibling, &current_hash)
            };
        }

        current_hash == root
    }

    /// Размер proof в байтах (для network limits)
    pub fn size(&self) -> usize {
        // leaf_index: 8 bytes
        // directions: 1 byte per bool (but packed)
        // siblings: 32 bytes per hash
        8 + self.directions.len() + self.siblings.len() * 32
    }
}

/// Hash двух узлов (canonical ordering)
fn hash_pair(left: &Hash, right: &Hash) -> Hash {
    let mut hasher = Sha3_256::new();
    hasher.update(MERKLE_PREFIX);

    // Canonical ordering: меньший хеш всегда слева
    if left <= right {
        hasher.update(left);
        hasher.update(right);
    } else {
        hasher.update(right);
        hasher.update(left);
    }

    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hash_data(data: &[u8]) -> Hash {
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        hasher.finalize().into()
    }

    #[test]
    fn test_empty_tree() {
        let tree = MerkleTree::new(vec![]);
        assert_eq!(tree.root(), [0u8; 32]);
        assert_eq!(tree.leaf_count, 0);
    }

    #[test]
    fn test_single_leaf() {
        let leaf = hash_data(b"single");
        let tree = MerkleTree::new(vec![leaf]);

        assert_eq!(tree.root(), leaf);
        assert_eq!(tree.leaf_count, 1);

        let proof = tree.proof(0).unwrap();
        assert!(proof.verify(leaf, tree.root()));
        assert_eq!(proof.siblings.len(), 0); // Корень = лист
    }

    #[test]
    fn test_two_leaves() {
        let leaf1 = hash_data(b"left");
        let leaf2 = hash_data(b"right");
        let tree = MerkleTree::new(vec![leaf1, leaf2]);

        assert_eq!(tree.leaf_count, 2);

        // Проверяем оба proof
        let proof1 = tree.proof(0).unwrap();
        assert!(proof1.verify(leaf1, tree.root()));

        let proof2 = tree.proof(1).unwrap();
        assert!(proof2.verify(leaf2, tree.root()));

        // Проверяем что siblings правильные
        assert_eq!(proof1.siblings[0], leaf2);
        assert_eq!(proof2.siblings[0], leaf1);

        // Проверяем направления
        assert!(proof1.directions[0]); // sibling справа
        assert!(!proof2.directions[0]); // sibling слева
    }

    #[test]
    fn test_power_of_two_leaves() {
        let leaves = vec![
            hash_data(b"a"),
            hash_data(b"b"),
            hash_data(b"c"),
            hash_data(b"d"),
        ];
        let tree = MerkleTree::new(leaves.clone());

        assert_eq!(tree.leaf_count, 4);

        // Проверяем все proof
        for (i, leaf) in leaves.iter().enumerate() {
            let proof = tree.proof(i).unwrap();
            assert!(proof.verify(*leaf, tree.root()));
        }
    }

    #[test]
    fn test_non_power_of_two_leaves() {
        let leaves = vec![
            hash_data(b"a"),
            hash_data(b"b"),
            hash_data(b"c"),
        ];
        let tree = MerkleTree::new(leaves.clone());

        assert_eq!(tree.leaf_count, 3);

        // Проверяем все proof
        for (i, leaf) in leaves.iter().enumerate() {
            let proof = tree.proof(i).unwrap();
            assert!(proof.verify(*leaf, tree.root()));
        }
    }

    #[test]
    fn test_proof_verification() {
        let leaves = vec![
            hash_data(b"leaf1"),
            hash_data(b"leaf2"),
            hash_data(b"leaf3"),
            hash_data(b"leaf4"),
        ];
        let tree = MerkleTree::new(leaves.clone());

        let proof = tree.proof(2).unwrap(); // leaf3
        assert!(proof.verify(leaves[2], tree.root()));

        // Проверяем неверный лист
        let wrong_leaf = hash_data(b"wrong");
        assert!(!proof.verify(wrong_leaf, tree.root()));

        // Проверяем неверный root
        let wrong_root = hash_data(b"wrong root");
        assert!(!proof.verify(leaves[2], wrong_root));
    }

    #[test]
    fn test_invalid_proof_rejected() {
        let leaves = vec![hash_data(b"a"), hash_data(b"b")];
        let leaf0 = leaves[0];  // Сохраняем до перемещения
        let tree = MerkleTree::new(leaves);

        // Создаём неправильный proof
        let mut invalid_proof = tree.proof(0).unwrap();
        invalid_proof.siblings[0] = hash_data(b"wrong");

        assert!(!invalid_proof.verify(leaf0, tree.root()));
    }

    #[test]
    fn test_canonical_ordering() {
        let hash1 = [1u8; 32];
        let hash2 = [2u8; 32];

        // hash1 < hash2, так что hash1 должен быть слева
        let pair1 = hash_pair(&hash1, &hash2);
        let pair2 = hash_pair(&hash2, &hash1);

        assert_eq!(pair1, pair2); // Должны быть одинаковыми

        // Проверяем что порядок действительно canonical
        let mut hasher = Sha3_256::new();
        hasher.update(MERKLE_PREFIX);
        hasher.update(&hash1);
        hasher.update(&hash2);
        let expected: [u8; 32] = hasher.finalize().into();

        assert_eq!(pair1, expected);
    }

    #[test]
    fn test_proof_by_hash() {
        let leaves = vec![
            hash_data(b"unique1"),
            hash_data(b"unique2"),
            hash_data(b"unique3"),
        ];
        let tree = MerkleTree::new(leaves.clone());

        let proof = tree.proof_by_hash(&leaves[1]).unwrap();
        assert!(proof.verify(leaves[1], tree.root()));
        assert_eq!(proof.leaf_index, 1);
    }

    #[test]
    fn test_proof_size() {
        let leaves = vec![hash_data(b"a"), hash_data(b"b")];
        let tree = MerkleTree::new(leaves);
        let proof = tree.proof(0).unwrap();

        // 8 (index) + 1 (direction) + 32 (sibling) = 41 байт
        assert_eq!(proof.size(), 41);
    }

    #[test]
    fn test_out_of_bounds() {
        let leaves = vec![hash_data(b"a"), hash_data(b"b")];
        let tree = MerkleTree::new(leaves);

        assert!(tree.proof(2).is_none()); // Индекс вне диапазона
    }
}