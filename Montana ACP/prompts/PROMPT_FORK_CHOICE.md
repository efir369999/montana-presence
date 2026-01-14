# PROMPT: Fork Choice Rule (fork_choice.rs)

**Модель:** GPT-4o
**Задача:** Написать модуль fork choice для Montana ACP
**Язык:** Rust
**Файл:** `fork_choice.rs` (ТОЛЬКО ЭТОТ ФАЙЛ!)

---

## ⚠️ ПРАВИЛА ИЗОЛЯЦИИ

**ТЫ СОЗДАЁШЬ ТОЛЬКО ОДИН ФАЙЛ: `fork_choice.rs`**

```
🔴 ЗАПРЕЩЕНО:
├── Редактировать consensus.rs, types.rs, crypto.rs
├── Редактировать finality.rs, merkle.rs, engine.rs
├── Менять Cargo.toml
├── Создавать другие файлы

🟢 РАЗРЕШЕНО:
├── Создать fork_choice.rs с нуля
├── Импортировать из types.rs, crypto.rs
├── Добавить `pub mod fork_choice;` в lib.rs
├── Добавить реэкспорты в lib.rs
```

**Зависимости (ТОЛЬКО ЭТИ):**
```rust
use crate::types::{Hash, Slice, SliceHeader};
use std::collections::HashMap;
```

**НЕ зависи от:**
- finality.rs (другая модель создаёт)
- merkle.rs (другая модель создаёт)
- engine.rs (создаётся в Фазе 2)

---

## Контекст

Montana использует **Longest Chain + Highest Weight** правило:
1. Выбрать цепь с наибольшим количеством слайсов
2. При равенстве — цепь с наибольшим накопленным весом
3. При равенстве — цепь с меньшим хешем головы

---

## Текущая проблема

Fork choice rule описан в документации, но **НЕ реализован в коде**.

Нужен модуль, который:
- Отслеживает все известные цепи (heads)
- Вычисляет канонический head
- Обрабатывает reorg
- Защищает от глубоких реорганизаций

---

## Что НУЖНО написать: fork_choice.rs

### 1. Структуры

```rust
use crate::types::{Hash, Slice, SliceHeader};

/// Состояние цепи (head)
pub struct ChainHead {
    pub hash: Hash,
    pub slice_index: u64,  // Используй SliceHeader.slice_index
    pub cumulative_weight: u64,  // Из SliceHeader.cumulative_weight
    pub finality_depth: u32,  // Сколько слайсов до финального checkpoint
}

use std::collections::HashMap;

/// Fork choice state
pub struct ForkChoice {
    /// Все известные heads по slice_index
    heads: HashMap<u64, ChainHead>,
    /// Текущий canonical head (slice_index)
    canonical: u64,
    /// Последний finalized checkpoint (slice_index)
    finalized_checkpoint: Option<u64>,
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
```

### 2. Методы

```rust
impl ForkChoice {
    /// Создать с genesis (slice_index = 0)
    pub fn new() -> Self;

    /// Добавить новый head (при получении слайса)
    pub fn add_head(&mut self, slice: &Slice) -> Result<(), ForkChoiceError>;

    /// Получить canonical head
    pub fn canonical_head(&self) -> Option<&ChainHead>;

    /// Сравнить две цепи по правилу Montana
    pub fn compare(&self, a: &ChainHead, b: &ChainHead) -> ChainComparison;

    /// Проверить нужен ли reorg к новому слайсу
    pub fn should_reorg(&self, new_slice: &Slice) -> bool;

    /// Выполнить reorg (если allowed)
    pub fn reorg_to(&mut self, new_slice: &Slice) -> Result<ReorgResult, ForkChoiceError>;

    /// Установить finalized checkpoint (блокирует reorg ниже)
    pub fn set_finalized(&mut self, checkpoint_index: u64);

    /// Проверить можно ли реорганизовать до target
    pub fn can_reorg_to(&self, target_index: u64) -> bool;
}

/// Результат reorg
pub struct ReorgResult {
    /// Индексы слайсов, которые стали orphan
    pub orphaned: Vec<u64>,
    /// Индексы слайсов, которые стали canonical
    pub adopted: Vec<u64>,
    /// Глубина reorg (количество слайсов)
    pub depth: u32,
}
```

### 3. Алгоритм сравнения (Montana fork-choice rule)

```rust
use std::cmp::Ordering;

impl ForkChoice {
    pub fn compare(&self, a: &ChainHead, b: &ChainHead) -> ChainComparison {
        // 1. Сначала по высоте (количество слайсов = slice_index)
        match a.slice_index.cmp(&b.slice_index) {
            Ordering::Greater => return ChainComparison::First,
            Ordering::Less => return ChainComparison::Second,
            Ordering::Equal => {}
        }

        // 2. При равной высоте — по cumulative_weight (из SliceHeader)
        match a.cumulative_weight.cmp(&b.cumulative_weight) {
            Ordering::Greater => return ChainComparison::First,
            Ordering::Less => return ChainComparison::Second,
            Ordering::Equal => {}
        }

        // 3. При равном весе — меньший hash wins
        match a.hash.cmp(&b.hash) {
            Ordering::Less => ChainComparison::First,
            Ordering::Greater => ChainComparison::Second,
            Ordering::Equal => ChainComparison::Equal,
        }
    }
}
```

**Важно:** Используй `SliceHeader.cumulative_weight` для сравнения веса цепей.

### 4. Защита от глубоких реорганизаций

```rust
/// Ошибки fork choice
pub enum ForkChoiceError {
    /// Reorg слишком глубокий
    ReorgTooDeep { attempted: u32, max: u32 },
    /// Попытка реорганизовать finalized слайс
    ReorgBelowFinalized,
    /// Head не найден
    HeadNotFound,
    /// Циклическая ссылка (атака)
    CyclicReference,
}

impl ForkChoice {
    pub fn reorg_to(&mut self, new_head: ChainHead) -> Result<ReorgResult, ForkChoiceError> {
        let current = self.canonical_head();

        // Найти общего предка
        let common_ancestor = self.find_common_ancestor(&current.hash, &new_head.hash)?;

        let reorg_depth = current.height - common_ancestor.height;

        // Проверить глубину
        if reorg_depth > self.max_reorg_depth {
            return Err(ForkChoiceError::ReorgTooDeep {
                attempted: reorg_depth as u32,
                max: self.max_reorg_depth,
            });
        }

        // Проверить не ниже finalized
        if let Some(finalized) = &self.finalized_checkpoint {
            if common_ancestor.height < self.get_head(finalized)?.height {
                return Err(ForkChoiceError::ReorgBelowFinalized);
            }
        }

        // Выполнить reorg
        // ...
    }
}
```

---

## Константы

```rust
use crate::types::COOLDOWN_WINDOW_TAU2;  // 2016

/// Максимальная глубина reorg (без checkpoint)
pub const MAX_REORG_DEPTH: u32 = 100;

/// Safe depth (после которого reorg маловероятен)
pub const SAFE_DEPTH: u32 = 6;

/// Finality depth (после которого reorg невозможен)
pub const FINALITY_DEPTH: u64 = COOLDOWN_WINDOW_TAU2;  // τ₃ = 2016 слайсов
```

---

## Интеграция с существующим кодом

**НЕ изменяй существующие структуры!** Используй их как есть:

```rust
use crate::types::{Slice, SliceHeader, Hash};
use crate::db::Storage;  // Для хранения слайсов
```

**Добавь в lib.rs:**
```rust
pub mod fork_choice;
pub use fork_choice::{ForkChoice, ChainHead, ChainComparison};
```

**Использование:**
```rust
// При получении нового слайса:
if fork_choice.should_reorg(&new_slice) {
    let result = fork_choice.reorg_to(&new_slice)?;
    // Обработать orphaned слайсы
    for orphan_index in result.orphaned {
        // Вернуть транзакции в mempool если нужно
    }
}
```

---

## Тесты

```rust
#[test]
fn test_longer_chain_wins() { }

#[test]
fn test_heavier_chain_wins_at_equal_height() { }

#[test]
fn test_smaller_hash_wins_at_equal_weight() { }

#[test]
fn test_reorg_depth_limit() { }

#[test]
fn test_cannot_reorg_below_finalized() { }

#[test]
fn test_orphan_detection() { }
```

---

## Выход

Один файл: `fork_choice.rs` (~300-400 строк)

Включить:
- ForkChoice state machine
- ChainComparison algorithm
- Reorg protection
- Тесты
- Документацию

**Стиль:** Deterministic (одинаковый результат на всех узлах), минимум состояния.
