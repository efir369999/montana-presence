//! Sled-based storage layer

use crate::types::{Hash, NodeWeight, PresenceProof, PublicKey, RegistrationEntry, Slice, SliceHeader, Transaction, Utxo};
use sled::{Db, Tree};
use std::path::Path;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum DbError {
    #[error("sled error: {0}")]
    Sled(#[from] sled::Error),
    #[error("serialization error: {0}")]
    Serialize(#[from] bincode::Error),
    #[error("not found")]
    NotFound,
}

pub struct Storage {
    db: Db,
    slices: Tree,
    utxo: Tree,
    weights: Tree,
    presence: Tree,
    registrations: Tree,
}

impl Storage {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self, DbError> {
        let db = sled::open(path)?;
        let slices = db.open_tree("slices")?;
        let utxo = db.open_tree("utxo")?;
        let weights = db.open_tree("weights")?;
        let presence = db.open_tree("presence")?;
        let registrations = db.open_tree("registrations")?;
        Ok(Self { db, slices, utxo, weights, presence, registrations })
    }

    // Slices
    pub fn put_slice(&self, slice: &Slice) -> Result<(), DbError> {
        let key = slice.header.slice_index.to_be_bytes();
        let value = bincode::serialize(slice)?;
        self.slices.insert(key, value)?;
        self.db.insert("head", &slice.header.slice_index.to_be_bytes())?;
        self.db.flush()?;
        Ok(())
    }

    pub fn get_slice(&self, index: u64) -> Result<Slice, DbError> {
        let key = index.to_be_bytes();
        let value = self.slices.get(key)?.ok_or(DbError::NotFound)?;
        Ok(bincode::deserialize(&value)?)
    }

    pub fn head(&self) -> Result<u64, DbError> {
        let value = self.db.get("head")?.ok_or(DbError::NotFound)?;
        Ok(u64::from_be_bytes(value.as_ref().try_into().unwrap()))
    }

    // UTXO
    pub fn put_utxo(&self, utxo: &Utxo) -> Result<(), DbError> {
        let mut key = utxo.tx_hash.to_vec();
        key.extend(&utxo.output_index.to_be_bytes());
        let value = bincode::serialize(utxo)?;
        self.utxo.insert(key, value)?;
        Ok(())
    }

    pub fn get_utxo(&self, tx_hash: &Hash, output_index: u32) -> Result<Utxo, DbError> {
        let mut key = tx_hash.to_vec();
        key.extend(&output_index.to_be_bytes());
        let value = self.utxo.get(key)?.ok_or(DbError::NotFound)?;
        Ok(bincode::deserialize(&value)?)
    }

    pub fn delete_utxo(&self, tx_hash: &Hash, output_index: u32) -> Result<(), DbError> {
        let mut key = tx_hash.to_vec();
        key.extend(&output_index.to_be_bytes());
        self.utxo.remove(key)?;
        Ok(())
    }

    pub fn apply_tx(&self, tx: &Transaction) -> Result<(), DbError> {
        for input in &tx.inputs {
            self.delete_utxo(&input.prev_tx, input.output_index)?;
        }
        let tx_hash = tx.hash();
        for (i, output) in tx.outputs.iter().enumerate() {
            let utxo = Utxo {
                tx_hash,
                output_index: i as u32,
                output: output.clone(),
            };
            self.put_utxo(&utxo)?;
        }
        Ok(())
    }

    pub fn get_balance(&self, pubkey: &PublicKey) -> Result<u64, DbError> {
        let mut balance = 0u64;
        for item in self.utxo.iter() {
            let (_, value) = item?;
            let utxo: Utxo = bincode::deserialize(&value)?;
            if &utxo.output.pubkey == pubkey {
                balance += utxo.output.amount;
            }
        }
        Ok(balance)
    }

    // Weights
    pub fn put_weight(&self, weight: &NodeWeight) -> Result<(), DbError> {
        let value = bincode::serialize(weight)?;
        self.weights.insert(&weight.pubkey, value)?;
        Ok(())
    }

    pub fn get_weight(&self, pubkey: &PublicKey) -> Result<NodeWeight, DbError> {
        let value = self.weights.get(pubkey)?.ok_or(DbError::NotFound)?;
        Ok(bincode::deserialize(&value)?)
    }

    pub fn get_all_weights(&self) -> Result<Vec<NodeWeight>, DbError> {
        let mut weights = Vec::new();
        for item in self.weights.iter() {
            let (_, value) = item?;
            weights.push(bincode::deserialize(&value)?);
        }
        Ok(weights)
    }

    pub fn get_eligible_weights(&self, current_tau2: u64) -> Result<Vec<NodeWeight>, DbError> {
        Ok(self.get_all_weights()?.into_iter().filter(|w| w.can_participate(current_tau2)).collect())
    }

    // Registrations
    pub fn put_registration(&self, entry: &RegistrationEntry) -> Result<(), DbError> {
        let mut key = entry.registered_tau2.to_be_bytes().to_vec();
        key.push(entry.node_type.tier_index());
        key.extend(&entry.pubkey);
        let value = bincode::serialize(entry)?;
        self.registrations.insert(key, value)?;
        Ok(())
    }

    // Presence
    pub fn put_presence(&self, proof: &PresenceProof) -> Result<(), DbError> {
        let mut key = proof.tau2_index.to_be_bytes().to_vec();
        key.extend(&proof.pubkey);
        let value = bincode::serialize(proof)?;
        self.presence.insert(key, value)?;
        Ok(())
    }

    pub fn get_presence_for_tau2(&self, tau2_index: u64) -> Result<Vec<PresenceProof>, DbError> {
        let prefix = tau2_index.to_be_bytes();
        let mut proofs = Vec::new();
        for item in self.presence.scan_prefix(prefix) {
            let (_, value) = item?;
            proofs.push(bincode::deserialize(&value)?);
        }
        Ok(proofs)
    }

    // Chain age (for startup decision: quick_verify vs full_bootstrap)

    /// Get chain age in seconds (time since last slice)
    /// Returns None if no slices exist
    pub fn chain_age_secs(&self) -> Option<u64> {
        let head_idx = self.head().ok()?;
        let head_slice = self.get_slice(head_idx).ok()?;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .ok()?
            .as_secs();
        Some(now.saturating_sub(head_slice.header.timestamp))
    }

    /// Check if chain is fresh (less than threshold seconds old)
    /// Used for startup: fresh chain = quick verify, stale chain = full bootstrap
    pub fn is_chain_fresh(&self, threshold_secs: u64) -> bool {
        self.chain_age_secs()
            .map(|age| age < threshold_secs)
            .unwrap_or(false) // No chain = not fresh = full bootstrap
    }

    /// Get last slice timestamp
    pub fn last_slice_timestamp(&self) -> Option<u64> {
        let head_idx = self.head().ok()?;
        let head_slice = self.get_slice(head_idx).ok()?;
        Some(head_slice.header.timestamp)
    }

    // Genesis
    /// Initialize genesis slice (slice_index = 0)
    /// 
    /// ПРАВИЛО: Один ключ, одна подпись, один раз.
    /// Genesis может быть создан только один раз.
    /// Если genesis уже существует, возвращает существующий.
    pub fn init_genesis(&self) -> Result<Slice, DbError> {
        // Проверить, существует ли уже genesis (slice_index = 0)
        if self.get_slice(0).is_ok() {
            // Genesis уже существует — возвращаем его
            return self.get_slice(0);
        }

        use crate::crypto::sha3;

        let genesis = Slice {
            header: SliceHeader {
                prev_hash: [0u8; 32],
                timestamp: 1735862400,  // 2026-01-03 00:00:00 UTC
                slice_index: 0,
                winner_pubkey: vec![],
                cooldown_medians: [0, 0, 0],
                registrations: [0, 0, 0],
                cumulative_weight: 0,
                subnet_reputation_root: [0u8; 32],  // Genesis has zero root
            },
            presence_root: sha3(b"montana genesis presence"),
            tx_root: sha3(b"montana genesis tx"),
            signature: vec![],  // ПРАВИЛО: Одна подпись генезиса
            presences: vec![],
            transactions: vec![],
        };

        self.put_slice(&genesis)?;
        Ok(genesis)
    }
}
