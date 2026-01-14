//! Montana Fork Choice Rule
//!
//! **Longest Chain + Highest Weight** правило:
//! 1. Выбрать цепь с наибольшим количеством слайсов
//! 2. При равенстве — цепь с наибольшим накопленным весом
//! 3. При равенстве — цепь с меньшим хешем головы

use std::collections::HashMap;
use crate::types::Hash;

/// Состояние цепи (head)
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainHead {
    pub hash: Hash,
    pub height: u64,
    pub tau2_index: u64,
    pub cumulative_weight: u64,
    pub finality_depth: u32,  // Сколько слайсов до финального checkpoint
}

impl ChainHead {
    /// Создать genesis head
    pub fn genesis(genesis_hash: Hash) -> Self {
        Self {
            hash: genesis_hash,
            height: 0,
            tau2_index: 0,
            cumulative_weight: 0,
            finality_depth: 0,
        }
    }

    /// Создать head из slice header
    pub fn from_slice_header(hash: Hash, height: u64, tau2_index: u64, weight: u64) -> Self {
        Self {
            hash,
            height,
            tau2_index,
            cumulative_weight: weight,
            finality_depth: 0, // TODO: compute from finality tracker
        }
    }
}

/// Fork choice state
#[derive(Debug)]
pub struct ForkChoice {
    /// Все известные heads
    heads: HashMap<Hash, ChainHead>,
    /// Текущий canonical head
    canonical: Hash,
    /// Последний finalized checkpoint
    finalized_checkpoint: Option<Hash>,
    /// Maximum reorg depth (защита)
    max_reorg_depth: u32,
}

/// Результат сравнения цепей
#[derive(Debug, PartialEq)]
pub enum ChainComparison {
    /// Первая цепь лучше
    First,
    /// Вторая цепь лучше
    Second,
    /// Цепи равны (используем hash tiebreaker)
    Equal,
}

/// Результат reorg
#[derive(Debug)]
pub struct ReorgResult {
    /// Слайсы, которые стали orphan
    pub orphaned: Vec<Hash>,
    /// Слайсы, которые стали canonical
    pub adopted: Vec<Hash>,
    /// Глубина reorg
    pub depth: u32,
}

/// Ошибки fork choice
#[derive(Debug, thiserror::Error)]
pub enum ForkChoiceError {
    #[error("Reorg слишком глубокий: attempted={attempted}, max={max}")]
    ReorgTooDeep { attempted: u32, max: u32 },
    #[error("Попытка реорганизовать finalized слайс")]
    ReorgBelowFinalized,
    #[error("Head не найден")]
    HeadNotFound,
    #[error("Циклическая ссылка (атака)")]
    CyclicReference,
}

// ============================================================================
// CONSTANTS
// ============================================================================

/// Максимальная глубина reorg (без checkpoint)
pub const MAX_REORG_DEPTH: u32 = 100;

/// Safe depth (после которого reorg маловероятен)
pub const SAFE_DEPTH: u32 = 6;

/// Finality depth (после которого reorg невозможен)
pub const FINALITY_DEPTH: u32 = 2016;  // τ₃

// ============================================================================
// IMPLEMENTATION
// ============================================================================

impl ForkChoice {
    /// Создать с genesis
    pub fn new(genesis_hash: Hash) -> Self {
        let genesis_head = ChainHead::genesis(genesis_hash);
        let mut heads = HashMap::new();
        heads.insert(genesis_hash, genesis_head);

        Self {
            heads,
            canonical: genesis_hash,
            finalized_checkpoint: None,
            max_reorg_depth: MAX_REORG_DEPTH,
        }
    }

    /// Добавить новый head (при получении слайса)
    pub fn add_head(&mut self, head: ChainHead) -> Result<(), ForkChoiceError> {
        // Проверяем что head не создаёт цикл (упрощённо)
        if self.heads.contains_key(&head.hash) {
            return Err(ForkChoiceError::CyclicReference);
        }

        self.heads.insert(head.hash, head);
        Ok(())
    }

    /// Получить canonical head
    pub fn canonical_head(&self) -> &ChainHead {
        self.heads.get(&self.canonical).expect("Canonical head must exist")
    }

    /// Сравнить две цепи
    pub fn compare(&self, a: &ChainHead, b: &ChainHead) -> ChainComparison {
        // 1. Сначала по высоте (количество слайсов)
        match a.height.cmp(&b.height) {
            std::cmp::Ordering::Greater => return ChainComparison::First,
            std::cmp::Ordering::Less => return ChainComparison::Second,
            std::cmp::Ordering::Equal => {}
        }

        // 2. При равной высоте — по весу
        match a.cumulative_weight.cmp(&b.cumulative_weight) {
            std::cmp::Ordering::Greater => return ChainComparison::First,
            std::cmp::Ordering::Less => return ChainComparison::Second,
            std::cmp::Ordering::Equal => {}
        }

        // 3. При равном весе — меньший hash wins
        match a.hash.cmp(&b.hash) {
            std::cmp::Ordering::Less => ChainComparison::First,
            std::cmp::Ordering::Greater => ChainComparison::Second,
            std::cmp::Ordering::Equal => ChainComparison::Equal,
        }
    }

    /// Проверить нужен ли reorg
    pub fn should_reorg(&self, new_head: &ChainHead) -> bool {
        let current = self.canonical_head();
        matches!(self.compare(current, new_head), ChainComparison::Second)
    }

    /// Выполнить reorg (если allowed)
    pub fn reorg_to(&mut self, new_head: ChainHead) -> Result<ReorgResult, ForkChoiceError> {
        let current = self.canonical_head().clone();

        // Добавляем новый head если его нет
        if !self.heads.contains_key(&new_head.hash) {
            self.heads.insert(new_head.hash, new_head.clone());
        }

        // Находим общего предка (упрощённо - в реальности нужен полноценный поиск)
        let common_ancestor = self.find_common_ancestor(&current.hash, &new_head.hash)?;

        let reorg_depth = current.height.saturating_sub(common_ancestor.height);

        // Проверяем глубину
        if reorg_depth > self.max_reorg_depth as u64 {
            return Err(ForkChoiceError::ReorgTooDeep {
                attempted: reorg_depth as u32,
                max: self.max_reorg_depth,
            });
        }

        // Проверяем не ниже finalized
        if let Some(finalized) = &self.finalized_checkpoint {
            if let Some(finalized_head) = self.heads.get(finalized) {
                if common_ancestor.height < finalized_head.height {
                    return Err(ForkChoiceError::ReorgBelowFinalized);
                }
            }
        }

        // Выполнить reorg
        let orphaned = self.compute_orphaned(&current.hash, &new_head.hash);
        let adopted = self.compute_adopted(&new_head.hash, &current.hash);

        // Обновляем canonical head
        self.canonical = new_head.hash;

        Ok(ReorgResult {
            orphaned,
            adopted,
            depth: reorg_depth as u32,
        })
    }

    /// Установить finalized checkpoint (блокирует reorg ниже)
    pub fn set_finalized(&mut self, checkpoint_hash: Hash) {
        self.finalized_checkpoint = Some(checkpoint_hash);
    }

    /// Проверить можно ли реорганизовать до target
    pub fn can_reorg_to(&self, target_hash: &Hash) -> bool {
        let Some(target) = self.heads.get(target_hash) else {
            return false;
        };

        // Нельзя реорганизовать finalized
        if let Some(finalized) = &self.finalized_checkpoint {
            if target.hash == *finalized {
                return false;
            }
        }

        // Проверяем глубину reorg
        let current = self.canonical_head();
        let common_ancestor = self.find_common_ancestor(&current.hash, &target.hash)
            .unwrap_or(current.clone()); // fallback

        let reorg_depth = current.height.saturating_sub(common_ancestor.height);
        reorg_depth <= self.max_reorg_depth as u64
    }

    /// Найти общего предка двух хешей (упрощённая версия)
    fn find_common_ancestor(&self, _a: &Hash, _b: &Hash) -> Result<ChainHead, ForkChoiceError> {
        // В реальности нужна база данных с parent связями
        // Пока возвращаем genesis для упрощения
        let genesis = self.heads.values()
            .find(|head| head.height == 0)
            .cloned()
            .ok_or(ForkChoiceError::HeadNotFound)?;

        Ok(genesis)
    }

    /// Вычислить orphaned слайсы при reorg
    fn compute_orphaned(&self, from: &Hash, _to: &Hash) -> Vec<Hash> {
        // Упрощённо: в реальности нужно пройти по цепи от from до общего предка
        vec![*from]
    }

    /// Вычислить adopted слайсы при reorg
    fn compute_adopted(&self, from: &Hash, _to: &Hash) -> Vec<Hash> {
        // Упрощённо: в реальности нужно пройти по цепи от to до общего предка
        vec![*from]
    }

    /// Получить head по хешу (для тестов)
    #[cfg(test)]
    pub fn get_head(&self, hash: &Hash) -> Option<&ChainHead> {
        self.heads.get(hash)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_head(hash: Hash, height: u64, weight: u64) -> ChainHead {
        ChainHead::from_slice_header(hash, height, height, weight)
    }

    #[test]
    fn test_longer_chain_wins() {
        let fork_choice = ForkChoice::new([0u8; 32]);

        let short_chain = create_test_head([1u8; 32], 5, 100);
        let long_chain = create_test_head([2u8; 32], 10, 100);

        assert_eq!(fork_choice.compare(&short_chain, &long_chain), ChainComparison::Second);
        assert_eq!(fork_choice.compare(&long_chain, &short_chain), ChainComparison::First);
    }

    #[test]
    fn test_heavier_chain_wins_at_equal_height() {
        let fork_choice = ForkChoice::new([0u8; 32]);

        let light_chain = create_test_head([1u8; 32], 10, 50);
        let heavy_chain = create_test_head([2u8; 32], 10, 100);

        assert_eq!(fork_choice.compare(&light_chain, &heavy_chain), ChainComparison::Second);
        assert_eq!(fork_choice.compare(&heavy_chain, &light_chain), ChainComparison::First);
    }

    #[test]
    fn test_smaller_hash_wins_at_equal_weight() {
        let fork_choice = ForkChoice::new([0u8; 32]);

        let big_hash = create_test_head([2u8; 32], 10, 100);
        let small_hash = create_test_head([1u8; 32], 10, 100);

        assert_eq!(fork_choice.compare(&big_hash, &small_hash), ChainComparison::Second);
        assert_eq!(fork_choice.compare(&small_hash, &big_hash), ChainComparison::First);
    }

    #[test]
    fn test_equal_chains() {
        let fork_choice = ForkChoice::new([0u8; 32]);

        let chain1 = create_test_head([1u8; 32], 10, 100);
        let chain2 = create_test_head([1u8; 32], 10, 100);

        assert_eq!(fork_choice.compare(&chain1, &chain2), ChainComparison::Equal);
    }

    #[test]
    fn test_reorg_depth_limit() {
        let mut fork_choice = ForkChoice::new([0u8; 32]);
        fork_choice.max_reorg_depth = 5;

        let current = create_test_head([1u8; 32], 10, 100);
        let new_head = create_test_head([2u8; 32], 20, 100); // depth difference = 10

        fork_choice.heads.insert(current.hash, current);
        fork_choice.heads.insert(new_head.hash, new_head.clone());
        // Make `current` the canonical head so reorg depth is measured from it.
        fork_choice.canonical = [1u8; 32];

        assert!(matches!(fork_choice.reorg_to(new_head), Err(ForkChoiceError::ReorgTooDeep { .. })));
    }

    #[test]
    fn test_cannot_reorg_below_finalized() {
        let mut fork_choice = ForkChoice::new([0u8; 32]);
        let finalized_hash = [1u8; 32];
        fork_choice.set_finalized(finalized_hash);

        let finalized_head = create_test_head(finalized_hash, 100, 100);
        let new_head = create_test_head([2u8; 32], 200, 100);

        fork_choice.heads.insert(finalized_head.hash, finalized_head);
        fork_choice.heads.insert(new_head.hash, new_head.clone());

        assert!(matches!(fork_choice.reorg_to(new_head), Err(ForkChoiceError::ReorgBelowFinalized)));
    }

    #[test]
    fn test_successful_reorg() {
        let mut fork_choice = ForkChoice::new([0u8; 32]);

        let old_head = create_test_head([1u8; 32], 10, 50);
        let new_head = create_test_head([2u8; 32], 15, 100);

        fork_choice.heads.insert(old_head.hash, old_head);
        fork_choice.canonical = new_head.hash;
        fork_choice.heads.insert(new_head.hash, new_head.clone());

        // Should be able to reorg since new head is better
        let old_head_hash = [1u8; 32];
        let old_head = create_test_head(old_head_hash, 10, 50);
        fork_choice.canonical = old_head_hash;
        fork_choice.heads.insert(old_head_hash, old_head);

        assert!(fork_choice.should_reorg(&new_head));

        let result = fork_choice.reorg_to(new_head).unwrap();
        assert_eq!(fork_choice.canonical, [2u8; 32]);
        assert_eq!(result.depth, 10);
    }

    #[test]
    fn test_canonical_head() {
        let mut fork_choice = ForkChoice::new([0u8; 32]);
        let genesis = fork_choice.canonical_head();
        assert_eq!(genesis.hash, [0u8; 32]);
        assert_eq!(genesis.height, 0);
    }
}
