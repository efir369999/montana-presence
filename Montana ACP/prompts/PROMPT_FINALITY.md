# PROMPT: Финальность Montana (finality.rs)

**Модель:** Claude Opus
**Задача:** Написать модуль финальности для Montana ACP
**Язык:** Rust
**Файл:** `finality.rs` (ТОЛЬКО ЭТОТ ФАЙЛ!)

---

## ⚠️ ПРАВИЛА ИЗОЛЯЦИИ

**ТЫ СОЗДАЁШЬ ТОЛЬКО ОДИН ФАЙЛ: `finality.rs`**

```
🔴 ЗАПРЕЩЕНО:
├── Редактировать consensus.rs, types.rs, crypto.rs
├── Редактировать fork_choice.rs, merkle.rs, engine.rs
├── Менять Cargo.toml
├── Создавать другие файлы

🟢 РАЗРЕШЕНО:
├── Создать finality.rs с нуля
├── Импортировать из types.rs, crypto.rs, consensus.rs
├── Добавить `pub mod finality;` в lib.rs
├── Добавить реэкспорты в lib.rs
```

**Зависимости (ТОЛЬКО ЭТИ):**
```rust
use crate::types::{Hash, PublicKey, Signature, Slice, SliceHeader, COOLDOWN_WINDOW_TAU2};
use crate::crypto::verify;  // Для проверки подписей
use sha3::{Digest, Sha3_256};
use std::collections::HashMap;
```

**НЕ зависи от:**
- fork_choice.rs (другая модель создаст)
- merkle.rs (другая модель создаст)
- engine.rs (создаётся в Фазе 2)

---

## Контекст

Montana — децентрализованный протокол, основанный на **присутствии** (Proof of Presence), не на работе (PoW) или стейке (PoS).

**Философия:**
> "Bitcoin спрашивает: Сколько работы ты сделал?
> Ethereum спрашивает: Сколько ты поставил?
> Montana спрашивает: ТЫ ЗДЕСЬ?"

**Архитектура 80/20:**
- 80% Full Node (серверы, автоматика)
- 20% Verified User (люди, биометрия FIDO2)

---

## Что уже есть

```
montana/src/
├── consensus.rs  — Lottery, Slice, SliceHeader, PresenceProof (ЕСТЬ)
├── types.rs      — NodeWeight, Slice, SliceHeader, PresenceProof (ЕСТЬ)
├── cooldown.rs   — AdaptiveCooldown (ЕСТЬ)
├── crypto.rs     — SHA3-256, ML-DSA-65 (ЕСТЬ)
├── db.rs         — Storage для слайсов (ЕСТЬ)
└── finality.rs   — НУЖНО НАПИСАТЬ
```

**Существующие структуры (из types.rs):**
```rust
pub struct SliceHeader {
    pub prev_hash: Hash,
    pub timestamp: u64,
    pub slice_index: u64,
    pub winner_pubkey: PublicKey,
    pub cooldown_medians: [u64; 3],
    pub registrations: [u64; 3],
    pub cumulative_weight: u64,  // ← уже есть!
    pub subnet_reputation_root: Hash,
}

pub struct Slice {
    pub header: SliceHeader,
    pub presence_root: Hash,
    pub tx_root: Hash,
    pub signature: Signature,
}
```

**Lottery (из consensus.rs):**
- seed = SHA3-256(prev_slice_hash || τ₂_index)
- 10 backup slots (SLOTS_PER_TAU2)
- 80% Full Node / 20% Verified User caps

---

## Что НУЖНО написать: finality.rs

### 1. Структуры

```rust
use crate::types::{Hash, PublicKey, Signature};

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
```

### 2. Правила финальности

```text
INSTANT (0 слайсов):
├── Слайс создан, но может быть реорганизован
├── finality_depth = 0

SAFE (6 слайсов = 60 минут):
├── finality_depth >= 6
├── Реорганизация требует 6x больше веса
├── Практически безопасно для обычных транзакций
├── is_safe = true

FINAL (τ₃ = 2016 слайсов = 14 дней):
├── finality_depth >= 2016 (COOLDOWN_WINDOW_TAU2)
├── Checkpoint создан
├── Реорганизация невозможна (нужен hard fork)
├── Можно удалить старые presence proofs
├── is_final = true
```

### 3. Накопление attestations

```rust
use std::collections::HashMap;
use crate::types::{Slice, SliceHeader};

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
    pub fn new() -> Self;

    /// Добавить attestation к слайсу
    pub fn add_attestation(&mut self, att: SliceAttestation) -> Result<(), FinalityError>;

    /// Получить статус финальности для слайса
    pub fn get_status(&self, slice_hash: &Hash, current_head: u64) -> FinalityStatus;

    /// Проверить можно ли реорганизовать до этого слайса
    pub fn can_reorg_to(&self, target_index: u64) -> bool;

    /// Обновить canonical head (вызывается при принятии нового слайса)
    pub fn update_head(&mut self, new_head_index: u64);

    /// Создать checkpoint (каждые τ₃ = 2016 слайсов)
    pub fn create_checkpoint(&mut self, slice_index: u64, slice: &Slice) -> Option<FinalityCheckpoint>;
}
```

### 4. Требования безопасности

**Защита от атак:**
1. **Nothing-at-stake:** Attestation требует накопленного веса (нельзя голосовать без истории)
2. **Long-range attack:** Checkpoints необратимы
3. **Finality reversion:** После FINAL нет механизма отката

**НЕ использовать:**
- Slashing (Montana не использует stake)
- Депозиты/залоги
- Экономические наказания

---

## Формула финальности

```
finality_depth = current_head_index - slice_index

Где:
- current_head_index = индекс текущего canonical head
- slice_index = индекс проверяемого слайса

attestation_weight = Σ(attester_weight) для всех attestations слайса

is_safe = finality_depth >= 6 AND attestation_weight >= threshold
is_final = finality_depth >= 2016 (τ₃ = COOLDOWN_WINDOW_TAU2)
```

**Примечание:** Используй `SliceHeader.cumulative_weight` для проверки веса сети.

---

## Интеграция с существующим кодом

**НЕ изменяй существующие структуры!** Используй их как есть:

```rust
// types.rs уже имеет:
pub struct SliceHeader {
    pub cumulative_weight: u64,  // ← используй для веса сети
    // ...
}

// finality.rs должен работать с существующими типами:
use crate::types::{Slice, SliceHeader, Hash, PublicKey, Signature};
```

**Добавь в lib.rs:**
```rust
pub mod finality;
pub use finality::{FinalityTracker, FinalityStatus, FinalityCheckpoint};
```

---

## Тесты

Написать тесты:
1. `test_attestation_accumulation` — накопление голосов
2. `test_safe_threshold` — достижение SAFE (6 слайсов)
3. `test_final_threshold` — достижение FINAL (τ₃)
4. `test_reorg_protection` — защита от реорганизации
5. `test_checkpoint_creation` — создание checkpoint

---

## Константы

```rust
use crate::types::COOLDOWN_WINDOW_TAU2;  // 2016

pub const SAFE_DEPTH: u32 = 6;                    // 60 минут (6 × 10 мин)
pub const FINAL_DEPTH: u64 = COOLDOWN_WINDOW_TAU2; // τ₃ = 2016 слайсов = 14 дней
pub const SAFE_ATTESTATION_THRESHOLD: f64 = 0.5;  // 50% веса сети
pub const CHECKPOINT_INTERVAL: u64 = COOLDOWN_WINDOW_TAU2;  // Каждые τ₃
pub const MAX_ATTESTATIONS_PER_SLICE: usize = 1000;
```

---

## Выход

Один файл: `finality.rs` (~400-600 строк)

Включить:
- Структуры данных
- FinalityTracker
- Тесты (mod tests)
- Документацию (///comments)

**Стиль:** Минимум комментариев, самодокументируемый код, Rust идиомы.
