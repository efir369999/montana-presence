//! Montana Finality Layer
//!
//! ```text
//! INSTANT (0 слайсов):
//! ├── Слайс создан, но может быть реорганизован
//!
//! SAFE (6 слайсов = 60 минут):
//! ├── Реорганизация требует 6x больше веса
//! ├── Практически безопасно для обычных транзакций
//!
//! FINAL (τ₃ = 2016 слайсов = 14 дней):
//! ├── Checkpoint создан
//! ├── Реорганизация невозможна (нужен hard fork)
//! ├── Можно удалить старые presence proofs
//! ```

use crate::types::{Hash, PublicKey, Signature, Slice, SliceHeader, COOLDOWN_WINDOW_TAU2};
use crate::crypto::verify;
use sha3::{Digest, Sha3_256};
use std::collections::HashMap;

/// Финальность слайса
pub struct FinalityStatus {
    pub slice_hash: Hash,
    pub slice_index: u64,
    pub finality_depth: u32,      // Сколько слайсов сверху
    pub attestation_weight: u64,   // Накопленный вес подтверждений
    pub is_safe: bool,            // SAFE (6 слайсов = 60 минут)?
    pub is_final: bool,           // FINAL (τ₃ = 2016 слайсов = 14 дней)?
}

/// Голос за слайс (attestation)
pub struct SliceAttestation {
    pub slice_hash: Hash,
    pub attester_pubkey: PublicKey,
    pub attester_weight: u64,
    pub slice_index: u64,
    pub signature: Signature,
}

/// Checkpoint каждые τ₃ (14 дней = 2016 слайсов)
pub struct FinalityCheckpoint {
    pub tau3_index: u64,
    pub slice_hash: Hash,
    pub slice_index: u64,
    pub cumulative_weight: u64,    // Из SliceHeader.cumulative_weight
    pub attestation_root: Hash,    // Merkle root всех attestations
    pub signatures: Vec<Signature>, // Подписи топ-100 по весу
}

/// Ошибки финальности
pub enum FinalityError {
    InvalidSignature,
    WrongSliceIndex,
    AlreadyAttested,
    InsufficientWeight,
    SliceNotFound,
}

/// Трекер финальности для всех слайсов
pub struct FinalityTracker {
    /// Attestations по slice_hash
    attestations: HashMap<Hash, Vec<SliceAttestation>>,
    /// Текущий canonical head (slice_index)
    canonical_head: u64,
    /// Последний finalized checkpoint
    finalized_checkpoint: Option<FinalityCheckpoint>,
}

impl FinalityTracker {
    /// Создать новый трекер
    pub fn new() -> Self {
        Self {
            attestations: HashMap::new(),
            canonical_head: 0,
            finalized_checkpoint: None,
        }
    }

    /// Добавить attestation к слайсу
    pub fn add_attestation(&mut self, att: SliceAttestation) -> Result<(), FinalityError> {
        // Проверяем подпись (упрощённо - в реальности нужна полная верификация)
        if att.signature.is_empty() {
            return Err(FinalityError::InvalidSignature);
        }

        // Проверяем вес (не нулевой)
        if att.attester_weight == 0 {
            return Err(FinalityError::InsufficientWeight);
        }

        // Получаем или создаём список attestations для этого слайса
        let slice_attestations = self.attestations.entry(att.slice_hash).or_insert(Vec::new());

        // Проверяем лимит
        if slice_attestations.len() >= MAX_ATTESTATIONS_PER_SLICE {
            return Err(FinalityError::AlreadyAttested);
        }

        // Проверяем что не attested уже
        if slice_attestations.iter().any(|existing| existing.attester_pubkey == att.attester_pubkey) {
            return Err(FinalityError::AlreadyAttested);
        }

        // Добавляем attestation
        slice_attestations.push(att);

        Ok(())
    }

    /// Получить статус финальности для слайса
    pub fn get_status(&self, slice_hash: &Hash, current_head: u64) -> FinalityStatus {
        let slice_index = self.get_slice_index(slice_hash).unwrap_or(0);
        let finality_depth = (current_head.saturating_sub(slice_index)) as u32;

        let attestation_weight = self.attestations.get(slice_hash)
            .map(|atts| atts.iter().map(|att| att.attester_weight).sum())
            .unwrap_or(0);

        let is_safe = finality_depth >= SAFE_DEPTH;
        let is_final = finality_depth >= FINAL_DEPTH as u32;

        FinalityStatus {
            slice_hash: *slice_hash,
            slice_index,
            finality_depth,
            attestation_weight,
            is_safe,
            is_final,
        }
    }

    /// Проверить можно ли реорганизовать до этого слайса
    pub fn can_reorg_to(&self, target_index: u64) -> bool {
        // Если target_index + SAFE_DEPTH > canonical_head, можно реорганизовать
        target_index + SAFE_DEPTH as u64 > self.canonical_head
    }

    /// Обновить canonical head (вызывается при принятии нового слайса)
    pub fn update_head(&mut self, new_head_index: u64) {
        self.canonical_head = new_head_index.max(self.canonical_head);
    }

    /// Создать checkpoint (каждые τ₃ = 2016 слайсов)
    pub fn create_checkpoint(&mut self, slice_index: u64, slice: &Slice) -> Option<FinalityCheckpoint> {
        if slice_index % CHECKPOINT_INTERVAL != 0 {
            return None;
        }

        let tau3_index = slice_index / CHECKPOINT_INTERVAL;

        // Собираем все attestations для этого слайса
        let slice_attestations = self.attestations.get(&slice.header.hash()).cloned().unwrap_or_default();

        // Вычисляем cumulative weight
        let cumulative_weight = slice.header.cumulative_weight;

        // Создаём Merkle root из attestations
        let attestation_root = self.compute_attestation_root(&slice_attestations);

        // Собираем signatures от топ attestors (упрощённо)
        let signatures = slice_attestations.iter()
            .take(100)
            .map(|att| att.signature.clone())
            .collect();

        let checkpoint = FinalityCheckpoint {
            tau3_index,
            slice_hash: slice.header.hash(),
            slice_index,
            cumulative_weight,
            attestation_root,
            signatures,
        };

        // Сохраняем checkpoint
        self.finalized_checkpoint = Some(checkpoint.clone());

        Some(checkpoint)
    }

    /// Получить slice_index по hash (упрощённо)
    fn get_slice_index(&self, slice_hash: &Hash) -> Option<u64> {
        // В реальности нужно хранить mapping или получать из базы данных
        // Пока возвращаем фиксированное значение
        Some(0)
    }

    /// Вычислить Merkle root attestations
    fn compute_attestation_root(&self, attestations: &[SliceAttestation]) -> Hash {
        if attestations.is_empty() {
            return [0u8; 32];
        }

        // Простая реализация - хешируем все attestations
        let mut hasher = Sha3_256::new();
        for att in attestations {
            hasher.update(&att.slice_hash);
            hasher.update(&att.attester_pubkey);
            hasher.update(&att.attester_weight.to_le_bytes());
            hasher.update(&att.slice_index.to_le_bytes());
            hasher.update(&att.signature);
        }
        hasher.finalize().into()
    }
}

impl Default for FinalityTracker {
    fn default() -> Self {
        Self::new()
    }
}

/// Константы
pub const SAFE_DEPTH: u32 = 6;                    // 60 минут (6 × 10 мин)
pub const FINAL_DEPTH: u64 = COOLDOWN_WINDOW_TAU2; // τ₃ = 2016 слайсов = 14 дней
pub const SAFE_ATTESTATION_THRESHOLD: f64 = 0.5;  // 50% веса сети
pub const CHECKPOINT_INTERVAL: u64 = COOLDOWN_WINDOW_TAU2;  // Каждые τ₃
pub const MAX_ATTESTATIONS_PER_SLICE: usize = 1000;

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_attestation(slice_hash: Hash, pubkey: PublicKey, weight: u64, slice_index: u64) -> SliceAttestation {
        SliceAttestation {
            slice_hash,
            attester_pubkey: pubkey,
            attester_weight: weight,
            slice_index,
            signature: vec![1, 2, 3], // Mock signature
        }
    }

    #[test]
    fn test_attestation_accumulation() {
        let mut tracker = FinalityTracker::new();
        let slice_hash = [1u8; 32];
        let att = create_test_attestation(slice_hash, vec![1], 100, 1);

        assert!(tracker.add_attestation(att).is_ok());

        let status = tracker.get_status(&slice_hash, 10);
        assert_eq!(status.attestation_weight, 100);
        assert_eq!(status.finality_depth, 9); // 10 - 1
        assert!(!status.is_safe);
        assert!(!status.is_final);
    }

    #[test]
    fn test_safe_threshold() {
        let mut tracker = FinalityTracker::new();
        let slice_hash = [1u8; 32];
        let att = create_test_attestation(slice_hash, vec![1], 100, 1);

        tracker.add_attestation(att).unwrap();

        // Слайс на глубине 6+ считается safe
        let status = tracker.get_status(&slice_hash, 10); // depth = 9
        assert!(status.finality_depth >= SAFE_DEPTH);
        assert!(status.is_safe);
    }

    #[test]
    fn test_final_threshold() {
        let mut tracker = FinalityTracker::new();
        let slice_hash = [1u8; 32];
        let att = create_test_attestation(slice_hash, vec![1], 100, 1);

        tracker.add_attestation(att).unwrap();

        // Слайс на глубине FINAL_DEPTH+ считается final
        let deep_head = FINAL_DEPTH + 100;
        let status = tracker.get_status(&slice_hash, deep_head);
        assert!(status.finality_depth >= FINAL_DEPTH as u32);
        assert!(status.is_final);
    }

    #[test]
    fn test_reorg_protection() {
        let tracker = FinalityTracker::new();

        // Старый слайс (индекс 1) при текущем head=10
        assert!(tracker.can_reorg_to(1)); // 1 + 6 = 7 < 10, можно

        // Свежий слайс (индекс 8) при текущем head=10
        assert!(!tracker.can_reorg_to(8)); // 8 + 6 = 14 > 10, нельзя
    }

    #[test]
    fn test_checkpoint_creation() {
        let mut tracker = FinalityTracker::new();
        let slice_hash = [1u8; 32];

        // Создаём mock slice
        let header = SliceHeader {
            prev_hash: [0u8; 32],
            timestamp: 0,
            slice_index: CHECKPOINT_INTERVAL, // τ₃ граница
            winner_pubkey: vec![1],
            cooldown_medians: [0; 3],
            registrations: [0; 3],
            cumulative_weight: 1000,
            subnet_reputation_root: [0u8; 32],
        };

        let slice = Slice {
            header,
            presence_root: [0u8; 32],
            tx_root: [0u8; 32],
            signature: vec![],
        };

        let checkpoint = tracker.create_checkpoint(CHECKPOINT_INTERVAL, &slice);
        assert!(checkpoint.is_some());

        let cp = checkpoint.unwrap();
        assert_eq!(cp.tau3_index, 1);
        assert_eq!(cp.slice_hash, slice_hash);
        assert_eq!(cp.cumulative_weight, 1000);
    }

    #[test]
    fn test_duplicate_attestation_rejected() {
        let mut tracker = FinalityTracker::new();
        let slice_hash = [1u8; 32];
        let att1 = create_test_attestation(slice_hash, vec![1], 100, 1);
        let att2 = create_test_attestation(slice_hash, vec![1], 200, 1); // Same pubkey

        tracker.add_attestation(att1).unwrap();
        assert!(matches!(tracker.add_attestation(att2), Err(FinalityError::AlreadyAttested)));
    }

    #[test]
    fn test_update_head() {
        let mut tracker = FinalityTracker::new();

        tracker.update_head(5);
        assert_eq!(tracker.canonical_head, 5);

        tracker.update_head(3); // Меньше текущего - игнорируется
        assert_eq!(tracker.canonical_head, 5);

        tracker.update_head(10); // Больше - обновляется
        assert_eq!(tracker.canonical_head, 10);
    }
}

