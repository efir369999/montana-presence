//! Block Structure for PoT Blockchain

use crate::crypto::hash::{sha256, sha256_multi, merkle_root};
use crate::structures::types::{Hash256, Timestamp, Height, VrfProofData};
use crate::structures::transaction::Transaction;
use serde::{Deserialize, Serialize};

/// Block header (fixed size, ~200 bytes)
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BlockHeader {
    /// Protocol version
    pub version: u32,

    /// Block height
    pub height: Height,

    /// Previous block hash
    pub prev_hash: Hash256,

    /// Merkle root of transactions
    pub merkle_root: Hash256,

    /// Block timestamp (UTC)
    pub timestamp: Timestamp,

    /// VDF iterations (0 for non-checkpoint blocks)
    pub vdf_iterations: u64,

    /// VDF output (32 bytes, zero for non-checkpoint)
    pub vdf_output: [u8; 32],

    /// VDF proof (variable length, empty for non-checkpoint)
    pub vdf_proof: Vec<u8>,

    /// Block producer's public key
    pub producer_pubkey: [u8; 32],

    /// VRF proof for leader selection
    pub vrf_proof: Option<VrfProofData>,

    /// Block signature (Ed25519)
    pub signature: [u8; 64],
}

impl BlockHeader {
    /// Compute header hash
    pub fn hash(&self) -> Hash256 {
        let data = self.to_hash_bytes();
        Hash256(sha256(&data))
    }

    /// Serialize for hashing (excludes signature)
    fn to_hash_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(256);

        buf.extend_from_slice(&self.version.to_le_bytes());
        buf.extend_from_slice(&self.height.to_le_bytes());
        buf.extend_from_slice(self.prev_hash.as_bytes());
        buf.extend_from_slice(self.merkle_root.as_bytes());
        buf.extend_from_slice(&self.timestamp.to_le_bytes());
        buf.extend_from_slice(&self.vdf_iterations.to_le_bytes());
        buf.extend_from_slice(&self.vdf_output);
        buf.extend_from_slice(&(self.vdf_proof.len() as u32).to_le_bytes());
        buf.extend_from_slice(&self.vdf_proof);
        buf.extend_from_slice(&self.producer_pubkey);

        if let Some(ref vrf) = self.vrf_proof {
            buf.push(1);
            buf.extend_from_slice(&vrf.to_bytes());
        } else {
            buf.push(0);
        }

        buf
    }

    /// Check if this is a checkpoint block (every 600 blocks)
    pub fn is_checkpoint(&self) -> bool {
        self.height > 0 && self.height % 600 == 0
    }

    /// Validate basic structure
    pub fn validate_structure(&self) -> bool {
        // Version check
        if self.version > 1 {
            return false;
        }

        // Checkpoint blocks must have VDF
        if self.is_checkpoint() && self.vdf_iterations == 0 {
            return false;
        }

        // Non-checkpoint blocks must not have VDF
        if !self.is_checkpoint() && self.vdf_iterations > 0 {
            return false;
        }

        true
    }
}

impl Default for BlockHeader {
    fn default() -> Self {
        Self {
            version: 1,
            height: 0,
            prev_hash: Hash256::ZERO,
            merkle_root: Hash256::ZERO,
            timestamp: 0,
            vdf_iterations: 0,
            vdf_output: [0u8; 32],
            vdf_proof: Vec::new(),
            producer_pubkey: [0u8; 32],
            vrf_proof: None,
            signature: [0u8; 64],
        }
    }
}

/// Full block with transactions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    /// Block header
    pub header: BlockHeader,

    /// List of transactions
    pub transactions: Vec<Transaction>,
}

impl Block {
    /// Create new block
    pub fn new(header: BlockHeader, transactions: Vec<Transaction>) -> Self {
        Self { header, transactions }
    }

    /// Create genesis block
    pub fn genesis(genesis_timestamp: u64) -> Self {
        let header = BlockHeader {
            version: 1,
            height: 0,
            prev_hash: Hash256::ZERO,
            merkle_root: Hash256::ZERO,
            timestamp: genesis_timestamp,
            ..Default::default()
        };

        Self {
            header,
            transactions: Vec::new(),
        }
    }

    /// Get block hash
    pub fn hash(&self) -> Hash256 {
        self.header.hash()
    }

    /// Get block height
    pub fn height(&self) -> Height {
        self.header.height
    }

    /// Compute merkle root of transactions
    pub fn compute_merkle_root(&self) -> Hash256 {
        if self.transactions.is_empty() {
            return Hash256::ZERO;
        }

        let tx_hashes: Vec<[u8; 32]> = self.transactions
            .iter()
            .map(|tx| tx.hash().0)
            .collect();

        Hash256(merkle_root(&tx_hashes))
    }

    /// Verify merkle root matches transactions
    pub fn verify_merkle_root(&self) -> bool {
        self.header.merkle_root == self.compute_merkle_root()
    }

    /// Get coinbase transaction (first tx)
    pub fn coinbase(&self) -> Option<&Transaction> {
        self.transactions.first().filter(|tx| tx.is_coinbase())
    }

    /// Get total transaction count
    pub fn tx_count(&self) -> usize {
        self.transactions.len()
    }

    /// Get block size in bytes (estimated)
    pub fn size(&self) -> usize {
        let header_size = 200 + self.header.vdf_proof.len();
        let tx_size: usize = self.transactions.iter().map(|tx| tx.size()).sum();
        header_size + tx_size
    }

    /// Check if this is a checkpoint block
    pub fn is_checkpoint(&self) -> bool {
        self.header.is_checkpoint()
    }

    /// Serialize to bytes
    pub fn to_bytes(&self) -> Vec<u8> {
        bincode::serialize(self).unwrap_or_default()
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8]) -> Option<Self> {
        bincode::deserialize(bytes).ok()
    }
}

/// Block builder
pub struct BlockBuilder {
    header: BlockHeader,
    transactions: Vec<Transaction>,
}

impl BlockBuilder {
    /// Start building a new block
    pub fn new(height: Height, prev_hash: Hash256, timestamp: Timestamp) -> Self {
        Self {
            header: BlockHeader {
                height,
                prev_hash,
                timestamp,
                ..Default::default()
            },
            transactions: Vec::new(),
        }
    }

    /// Set producer public key
    pub fn producer(mut self, pubkey: [u8; 32]) -> Self {
        self.header.producer_pubkey = pubkey;
        self
    }

    /// Set VDF proof (for checkpoint blocks)
    pub fn vdf(mut self, iterations: u64, output: [u8; 32], proof: Vec<u8>) -> Self {
        self.header.vdf_iterations = iterations;
        self.header.vdf_output = output;
        self.header.vdf_proof = proof;
        self
    }

    /// Set VRF proof
    pub fn vrf(mut self, proof: VrfProofData) -> Self {
        self.header.vrf_proof = Some(proof);
        self
    }

    /// Add transaction
    pub fn add_transaction(mut self, tx: Transaction) -> Self {
        self.transactions.push(tx);
        self
    }

    /// Add multiple transactions
    pub fn add_transactions(mut self, txs: Vec<Transaction>) -> Self {
        self.transactions.extend(txs);
        self
    }

    /// Build the block (computes merkle root)
    pub fn build(mut self) -> Block {
        let block = Block::new(self.header.clone(), self.transactions);
        let merkle = block.compute_merkle_root();
        self.header.merkle_root = merkle;

        Block::new(self.header, block.transactions)
    }

    /// Build and sign the block
    pub fn build_and_sign(self, secret_key: &[u8; 32]) -> Block {
        use crate::crypto::signatures::sign;
        use crate::crypto::signatures::SecretKey;

        let mut block = self.build();
        let hash_bytes = block.header.to_hash_bytes();
        let sk = SecretKey::from_bytes(secret_key);
        let sig = sign(&sk, &hash_bytes);
        block.header.signature = sig.0;

        block
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::constants::GENESIS_TIMESTAMP;

    #[test]
    fn test_genesis_block() {
        let genesis = Block::genesis(GENESIS_TIMESTAMP);
        assert_eq!(genesis.height(), 0);
        assert!(genesis.header.prev_hash.is_zero());
        assert!(genesis.transactions.is_empty());
    }

    #[test]
    fn test_block_hash_deterministic() {
        let block = Block::genesis(GENESIS_TIMESTAMP);
        let hash1 = block.hash();
        let hash2 = block.hash();
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_checkpoint_detection() {
        let mut block = Block::genesis(GENESIS_TIMESTAMP);

        block.header.height = 0;
        assert!(!block.is_checkpoint());

        block.header.height = 599;
        assert!(!block.is_checkpoint());

        block.header.height = 600;
        assert!(block.is_checkpoint());

        block.header.height = 1200;
        assert!(block.is_checkpoint());
    }

    #[test]
    fn test_merkle_root() {
        let block = Block::genesis(GENESIS_TIMESTAMP);
        assert!(block.verify_merkle_root());
    }

    #[test]
    fn test_block_builder() {
        let block = BlockBuilder::new(1, Hash256::ZERO, GENESIS_TIMESTAMP + 1)
            .producer([1u8; 32])
            .build();

        assert_eq!(block.height(), 1);
        assert_eq!(block.header.producer_pubkey, [1u8; 32]);
    }

    #[test]
    fn test_serialization() {
        let block = Block::genesis(GENESIS_TIMESTAMP);
        let bytes = block.to_bytes();
        let parsed = Block::from_bytes(&bytes).unwrap();

        assert_eq!(block.hash(), parsed.hash());
    }
}
