# PROMPT: Merkle Proofs для Light Clients (merkle.rs)

**Модель:** Gemini 2.0
**Задача:** Написать модуль Merkle proofs для Montana ACP
**Язык:** Rust
**Файл:** `merkle.rs` (ТОЛЬКО ЭТОТ ФАЙЛ!)

---

## ⚠️ ПРАВИЛА ИЗОЛЯЦИИ

**ТЫ СОЗДАЁШЬ ТОЛЬКО ОДИН ФАЙЛ: `merkle.rs`**

```
🔴 ЗАПРЕЩЕНО:
├── Редактировать consensus.rs, types.rs, crypto.rs
├── Редактировать finality.rs, fork_choice.rs, engine.rs
├── Менять Cargo.toml
├── Создавать другие файлы

🟢 РАЗРЕШЕНО:
├── Создать merkle.rs с нуля
├── Импортировать из types.rs, crypto.rs
├── Добавить `pub mod merkle;` в lib.rs
├── Добавить реэкспорты в lib.rs
```

**Зависимости (ТОЛЬКО ЭТИ):**
```rust
use crate::types::{Hash, SliceHeader};
use sha3::{Digest, Sha3_256};
```

**НЕ зависи от:**
- finality.rs (другая модель создаёт)
- fork_choice.rs (другая модель создаёт)
- engine.rs (создаётся в Фазе 2)

---

## Контекст

Montana использует Merkle trees для двух целей:
1. `presence_root` — корень всех подписей присутствия за τ₂
2. `tx_root` — корень транзакций в слайсе

Light clients должны уметь проверить:
- "Моя подпись присутствия включена в слайс"
- "Моя транзакция включена в слайс"

---

## Что уже есть

```rust
// В consensus.rs (Slice::compute_presence_root):
fn compute_presence_root(&self) -> [u8; 32] {
    // Простое merkle дерево, но БЕЗ генерации proofs
    // Использует SHA3-256 для пар
}

// В types.rs:
pub struct Slice {
    pub header: SliceHeader,
    pub presence_root: Hash,
    pub tx_root: Hash,
    pub signature: Signature,
    // НЕТ: merkle_proofs
}

pub struct PresenceProof {
    pub pubkey: PublicKey,
    pub tau2_index: u64,
    pub tau1_bitmap: u16,
    pub prev_slice_hash: Hash,
    pub timestamp: u64,
    pub signature: Signature,
    pub cooldown_until: u64,
}
```

---

## Что НУЖНО написать: merkle.rs

### 1. Структуры

```rust
use crate::types::Hash;

/// Merkle proof для включения в дерево
pub struct MerkleProof {
    /// Индекс листа в дереве
    pub leaf_index: usize,
    /// Путь аутентификации (siblings)
    pub siblings: Vec<Hash>,
    /// Направления: true = right sibling, false = left sibling
    pub directions: Vec<bool>,
}

/// Merkle дерево с возможностью генерации proofs
pub struct MerkleTree {
    /// Все уровни дерева (leaves, then internal nodes)
    levels: Vec<Vec<[u8; 32]>>,
    /// Количество листьев
    leaf_count: usize,
}
```

### 2. Методы

```rust
impl MerkleTree {
    /// Построить дерево из листьев
    pub fn new(leaves: Vec<[u8; 32]>) -> Self;

    /// Получить корень
    pub fn root(&self) -> [u8; 32];

    /// Сгенерировать proof для листа по индексу
    pub fn proof(&self, leaf_index: usize) -> Option<MerkleProof>;

    /// Сгенерировать proof для листа по хешу
    pub fn proof_by_hash(&self, leaf_hash: &[u8; 32]) -> Option<MerkleProof>;
}

impl MerkleProof {
    /// Верифицировать proof против известного root
    pub fn verify(&self, leaf_hash: [u8; 32], root: [u8; 32]) -> bool;

    /// Размер proof в байтах (для network limits)
    pub fn size(&self) -> usize;
}
```

### 3. Хеширование (совместимо с consensus.rs)

```rust
use sha3::{Digest, Sha3_256};
use crate::types::Hash;

/// Hash двух узлов (canonical ordering)
/// Должен совпадать с логикой в Slice::compute_presence_root()
fn hash_pair(left: &Hash, right: &Hash) -> Hash {
    let mut hasher = Sha3_256::new();
    hasher.update(b"MONTANA_MERKLE_V1:");

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
```

**Важно:** Должен совпадать с `Slice::compute_presence_root()` из consensus.rs!

### 4. Light Client API

```rust
/// Запрос proof от full node
pub struct ProofRequest {
    pub slice_hash: [u8; 32],
    pub leaf_hash: [u8; 32],  // Hash presence или tx
    pub proof_type: ProofType,
}

pub enum ProofType {
    Presence,
    Transaction,
}

/// Ответ с proof
pub struct ProofResponse {
    pub proof: MerkleProof,
    pub slice_header: SliceHeader,  // Для проверки root
}
```

---

## Требования безопасности

1. **Domain separation:** Все хеши с префиксом MONTANA_MERKLE_V1
2. **Canonical ordering:** Меньший хеш слева (защита от second preimage)
3. **Bounded size:** MAX_PROOF_DEPTH = 32 (достаточно для 2³² листьев)
4. **No trusted setup:** Простой SHA3-256

---

## Интеграция

**НЕ изменяй существующие структуры!** Создай отдельный модуль:

```rust
use crate::types::{Slice, PresenceProof, Hash, Transaction};

// В merkle.rs:
impl MerkleTree {
    /// Построить дерево из presence proofs слайса
    pub fn from_slice_presences(slice: &Slice) -> Self;

    /// Построить дерево из транзакций слайса
    pub fn from_slice_transactions(slice: &Slice) -> Self;
}

// Вспомогательные функции:
pub fn generate_presence_proof(slice: &Slice, presence: &PresenceProof) -> Option<MerkleProof>;
pub fn generate_tx_proof(slice: &Slice, tx: &Transaction) -> Option<MerkleProof>;
```

**Добавь в lib.rs:**
```rust
pub mod merkle;
pub use merkle::{MerkleTree, MerkleProof};
```

---

## Тесты

```rust
#[test]
fn test_empty_tree() { }

#[test]
fn test_single_leaf() { }

#[test]
fn test_power_of_two_leaves() { }

#[test]
fn test_non_power_of_two_leaves() { }

#[test]
fn test_proof_verification() { }

#[test]
fn test_invalid_proof_rejected() { }

#[test]
fn test_canonical_ordering() { }
```

---

## Константы

```rust
pub const MAX_PROOF_DEPTH: usize = 32;
pub const MERKLE_PREFIX: &[u8] = b"MONTANA_MERKLE_V1:";
```

---

## Выход

Один файл: `merkle.rs` (~200-300 строк)

Включить:
- MerkleTree
- MerkleProof
- Light client API structures
- Тесты
- Документацию

**Стиль:** Чистый Rust, no_std compatible (для embedded), минимум аллокаций.
