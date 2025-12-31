//! Transaction Structure for PoT Blockchain

use crate::crypto::hash::sha256;
use crate::structures::types::{Hash256, Amount, KeyImage, Commitment, StealthPubKey};
use serde::{Deserialize, Serialize};

/// Transaction type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum TransactionType {
    /// Coinbase (block reward)
    Coinbase = 0,
    /// Standard transfer
    Transfer = 1,
    /// Stake deposit
    Stake = 2,
    /// Stake withdrawal
    Unstake = 3,
    /// Governance vote
    Vote = 4,
}

impl Default for TransactionType {
    fn default() -> Self {
        Self::Transfer
    }
}

impl From<u8> for TransactionType {
    fn from(v: u8) -> Self {
        match v {
            0 => Self::Coinbase,
            1 => Self::Transfer,
            2 => Self::Stake,
            3 => Self::Unstake,
            4 => Self::Vote,
            _ => Self::Transfer,
        }
    }
}

/// Transaction input
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxInput {
    /// Reference to output being spent
    pub output_ref: OutputRef,

    /// Key image (for double-spend prevention)
    pub key_image: KeyImage,

    /// Ring signature (LSAG)
    pub ring_signature: Vec<u8>,

    /// Ring members (public keys of decoys + real output)
    pub ring_members: Vec<[u8; 32]>,
}

impl TxInput {
    /// Create new input
    pub fn new(output_ref: OutputRef, key_image: KeyImage) -> Self {
        Self {
            output_ref,
            key_image,
            ring_signature: Vec::new(),
            ring_members: Vec::new(),
        }
    }

    /// Get ring size
    pub fn ring_size(&self) -> usize {
        self.ring_members.len()
    }

    /// Estimated size in bytes
    pub fn size(&self) -> usize {
        32 + 32 + // output_ref + key_image
        self.ring_signature.len() +
        self.ring_members.len() * 32
    }
}

/// Reference to a transaction output
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct OutputRef {
    /// Transaction hash
    pub tx_hash: Hash256,
    /// Output index in transaction
    pub index: u32,
}

impl OutputRef {
    pub fn new(tx_hash: Hash256, index: u32) -> Self {
        Self { tx_hash, index }
    }

    pub fn to_bytes(&self) -> [u8; 36] {
        let mut result = [0u8; 36];
        result[..32].copy_from_slice(self.tx_hash.as_bytes());
        result[32..].copy_from_slice(&self.index.to_le_bytes());
        result
    }
}

/// Transaction output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxOutput {
    /// Stealth public key (recipient)
    pub stealth_key: StealthPubKey,

    /// Pedersen commitment to amount
    pub commitment: Commitment,

    /// Encrypted amount (for recipient)
    pub encrypted_amount: Vec<u8>,

    /// Range proof (Bulletproof)
    pub range_proof: Vec<u8>,

    /// Extra data (for coinbase, contains reward info)
    pub extra: Vec<u8>,
}

impl TxOutput {
    /// Create new output
    pub fn new(stealth_key: StealthPubKey, commitment: Commitment) -> Self {
        Self {
            stealth_key,
            commitment,
            encrypted_amount: Vec::new(),
            range_proof: Vec::new(),
            extra: Vec::new(),
        }
    }

    /// Create coinbase output
    pub fn coinbase(pubkey: [u8; 32], amount: Amount) -> Self {
        Self {
            stealth_key: StealthPubKey::new([0u8; 32], pubkey),
            commitment: Commitment([0u8; 32]),
            encrypted_amount: amount.to_le_bytes().to_vec(),
            range_proof: Vec::new(),
            extra: b"coinbase".to_vec(),
        }
    }

    /// Estimated size in bytes
    pub fn size(&self) -> usize {
        64 + 32 + // stealth_key + commitment
        self.encrypted_amount.len() +
        self.range_proof.len() +
        self.extra.len()
    }

    /// Check if this is a coinbase output
    pub fn is_coinbase(&self) -> bool {
        self.extra.starts_with(b"coinbase")
    }

    /// Get amount from coinbase output
    pub fn coinbase_amount(&self) -> Option<Amount> {
        if !self.is_coinbase() || self.encrypted_amount.len() < 8 {
            return None;
        }
        Some(u64::from_le_bytes(self.encrypted_amount[..8].try_into().ok()?))
    }
}

/// Full transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Transaction version
    pub version: u8,

    /// Transaction type
    pub tx_type: TransactionType,

    /// Inputs
    pub inputs: Vec<TxInput>,

    /// Outputs
    pub outputs: Vec<TxOutput>,

    /// Fee (in seconds)
    pub fee: Amount,

    /// Extra data
    pub extra: Vec<u8>,

    /// Transaction unlock time (0 for immediate)
    pub unlock_time: u64,
}

impl Transaction {
    /// Create new transaction
    pub fn new(tx_type: TransactionType) -> Self {
        Self {
            version: 1,
            tx_type,
            inputs: Vec::new(),
            outputs: Vec::new(),
            fee: 0,
            extra: Vec::new(),
            unlock_time: 0,
        }
    }

    /// Create coinbase transaction
    pub fn coinbase(height: u64, pubkey: [u8; 32], reward: Amount) -> Self {
        let output = TxOutput::coinbase(pubkey, reward);

        let mut extra = Vec::new();
        extra.extend_from_slice(&height.to_le_bytes());

        Self {
            version: 1,
            tx_type: TransactionType::Coinbase,
            inputs: Vec::new(),
            outputs: vec![output],
            fee: 0,
            extra,
            unlock_time: 0,
        }
    }

    /// Compute transaction hash
    pub fn hash(&self) -> Hash256 {
        let data = self.to_hash_bytes();
        Hash256(sha256(&data))
    }

    /// Serialize for hashing
    fn to_hash_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(self.size());

        buf.push(self.version);
        buf.push(self.tx_type as u8);
        buf.extend_from_slice(&(self.inputs.len() as u32).to_le_bytes());

        for input in &self.inputs {
            buf.extend_from_slice(input.key_image.as_bytes());
            buf.extend_from_slice(&input.output_ref.to_bytes());
        }

        buf.extend_from_slice(&(self.outputs.len() as u32).to_le_bytes());
        for output in &self.outputs {
            buf.extend_from_slice(&output.stealth_key.to_bytes());
            buf.extend_from_slice(output.commitment.as_bytes());
            buf.extend_from_slice(&output.encrypted_amount);
        }

        buf.extend_from_slice(&self.fee.to_le_bytes());
        buf.extend_from_slice(&self.unlock_time.to_le_bytes());
        buf.extend_from_slice(&self.extra);

        buf
    }

    /// Check if this is a coinbase transaction
    pub fn is_coinbase(&self) -> bool {
        self.tx_type == TransactionType::Coinbase
    }

    /// Get all key images
    pub fn key_images(&self) -> Vec<KeyImage> {
        self.inputs.iter().map(|i| i.key_image).collect()
    }

    /// Estimated size in bytes
    pub fn size(&self) -> usize {
        let inputs_size: usize = self.inputs.iter().map(|i| i.size()).sum();
        let outputs_size: usize = self.outputs.iter().map(|o| o.size()).sum();
        1 + 1 + 8 + 8 + // version, type, fee, unlock_time
        inputs_size + outputs_size + self.extra.len()
    }

    /// Validate basic structure
    pub fn validate_structure(&self) -> Result<(), &'static str> {
        // Coinbase must have no inputs
        if self.is_coinbase() && !self.inputs.is_empty() {
            return Err("Coinbase must have no inputs");
        }

        // Non-coinbase must have inputs
        if !self.is_coinbase() && self.inputs.is_empty() {
            return Err("Transaction must have inputs");
        }

        // Must have outputs
        if self.outputs.is_empty() {
            return Err("Transaction must have outputs");
        }

        // Version check
        if self.version > 1 {
            return Err("Unknown transaction version");
        }

        Ok(())
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

/// Transaction builder
pub struct TransactionBuilder {
    tx: Transaction,
}

impl TransactionBuilder {
    /// Start building a transfer transaction
    pub fn transfer() -> Self {
        Self {
            tx: Transaction::new(TransactionType::Transfer),
        }
    }

    /// Start building a stake transaction
    pub fn stake() -> Self {
        Self {
            tx: Transaction::new(TransactionType::Stake),
        }
    }

    /// Add input
    pub fn add_input(mut self, input: TxInput) -> Self {
        self.tx.inputs.push(input);
        self
    }

    /// Add output
    pub fn add_output(mut self, output: TxOutput) -> Self {
        self.tx.outputs.push(output);
        self
    }

    /// Set fee
    pub fn fee(mut self, fee: Amount) -> Self {
        self.tx.fee = fee;
        self
    }

    /// Set unlock time
    pub fn unlock_time(mut self, unlock_time: u64) -> Self {
        self.tx.unlock_time = unlock_time;
        self
    }

    /// Build transaction
    pub fn build(self) -> Transaction {
        self.tx
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_coinbase_transaction() {
        let tx = Transaction::coinbase(100, [1u8; 32], 3000);

        assert!(tx.is_coinbase());
        assert!(tx.inputs.is_empty());
        assert_eq!(tx.outputs.len(), 1);
        assert_eq!(tx.outputs[0].coinbase_amount(), Some(3000));
    }

    #[test]
    fn test_transaction_hash() {
        let tx = Transaction::coinbase(100, [1u8; 32], 3000);
        let hash1 = tx.hash();
        let hash2 = tx.hash();
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_transaction_builder() {
        let tx = TransactionBuilder::transfer()
            .fee(100)
            .build();

        assert_eq!(tx.tx_type, TransactionType::Transfer);
        assert_eq!(tx.fee, 100);
    }

    #[test]
    fn test_validate_coinbase() {
        let tx = Transaction::coinbase(0, [0u8; 32], 3000);
        assert!(tx.validate_structure().is_ok());
    }

    #[test]
    fn test_serialization() {
        let tx = Transaction::coinbase(100, [1u8; 32], 3000);
        let bytes = tx.to_bytes();
        let parsed = Transaction::from_bytes(&bytes).unwrap();
        assert_eq!(tx.hash(), parsed.hash());
    }

    #[test]
    fn test_output_ref() {
        let oref = OutputRef::new(Hash256([1u8; 32]), 5);
        let bytes = oref.to_bytes();
        assert_eq!(bytes.len(), 36);
    }
}
