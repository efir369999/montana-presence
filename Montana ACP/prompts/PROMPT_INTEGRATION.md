# PROMPT: Интеграция всех слоёв (engine.rs)

**Модель:** Claude Opus
**Задача:** Создать ConsensusEngine для Montana ACP
**Язык:** Rust
**Файл:** `engine.rs` (ТОЛЬКО ЭТОТ ФАЙЛ!)
**Фаза:** 2 (ПОСЛЕ Фазы 1!)

---

## ⚠️ ПРАВИЛА ИЗОЛЯЦИИ

**ТЫ СОЗДАЁШЬ ТОЛЬКО ОДИН ФАЙЛ: `engine.rs`**

```
🔴 ЗАПРЕЩЕНО:
├── Редактировать consensus.rs, types.rs, crypto.rs
├── Редактировать finality.rs, fork_choice.rs, merkle.rs
├── Менять Cargo.toml
├── Создавать другие файлы (кроме engine.rs)

🟢 РАЗРЕШЕНО:
├── Создать engine.rs с нуля
├── Импортировать из ВСЕХ модулей
├── Добавить `pub mod engine;` в lib.rs
├── Добавить реэкспорты в lib.rs
```

## ⚠️ ЗАВИСИМОСТИ ОТ ФАЗЫ 1

**ВЫПОЛНЯТЬ ТОЛЬКО ПОСЛЕ завершения Фазы 1!**

Перед началом проверь что существуют:
- `finality.rs` — FinalityTracker, FinalityStatus
- `fork_choice.rs` — ForkChoice, ChainHead
- `merkle.rs` — MerkleTree, MerkleProof

**Если файлы не существуют — НЕ НАЧИНАЙ. Жди Фазу 1.**

---

## Контекст

Montana состоит из модулей:
- `consensus.rs` — Lottery, Slice, SliceHeader, PresenceProof
- `types.rs` — NodeWeight, Slice, SliceHeader, Transaction, Utxo
- `cooldown.rs` — AdaptiveCooldown
- `crypto.rs` — SHA3-256, ML-DSA-65
- `db.rs` — Storage (sled-based)
- `net/` — P2P networking (полная реализация)
- `nmi.rs` — Network time
- `nts.rs` — Time sync
- `finality.rs` — Finality (NEW - нужно написать)
- `fork_choice.rs` — Fork Choice (NEW - нужно написать)
- `merkle.rs` — Merkle Proofs (NEW - нужно написать)

**Нужно:** Связать всё в единый consensus engine (engine.rs).

---

## Что НУЖНО написать

### 1. lib.rs — Public API

```rust
//! Montana ACP — Atemporal Coordinate Presence
//!
//! lim(evidence → ∞) 1 Ɉ → 1 секунда

pub mod consensus;
pub mod types;
pub mod cooldown;
pub mod crypto;
pub mod finality;
pub mod fork_choice;
pub mod merkle;
pub mod nmi;
pub mod nts;

// Re-exports
pub use consensus::{Lottery, Slice, FullNodePresence, VerifiedUserPresence};
pub use types::{NodeWeight, Transaction, Hash, PublicKey};
pub use finality::{FinalityStatus, FinalityCheckpoint};
pub use fork_choice::ForkChoice;

/// Montana node configuration
pub struct Config {
    pub node_type: NodeType,
    pub data_dir: PathBuf,
    pub network_port: u16,
    pub rpc_port: u16,
    pub genesis_hash: Hash,
}

/// Main Montana node
pub struct MontanaNode {
    config: Config,
    state: NodeState,
    consensus: ConsensusEngine,
    network: NetworkManager,
}

impl MontanaNode {
    pub fn new(config: Config) -> Result<Self, MontanaError>;
    pub async fn start(&mut self) -> Result<(), MontanaError>;
    pub async fn stop(&mut self) -> Result<(), MontanaError>;
}
```

### 2. ConsensusEngine — Main Loop

```rust
use crate::types::{Slice, SliceHeader, PresenceProof, NodeWeight};
use crate::consensus::{Lottery, LotteryResult};
use crate::cooldown::AdaptiveCooldown;
use crate::crypto::Keypair;
use crate::db::Storage;
use crate::net::Network;

pub struct ConsensusEngine {
    storage: Arc<Storage>,
    network: Arc<Network>,
    fork_choice: ForkChoice,
    finality: FinalityTracker,
    cooldown: AdaptiveCooldown,
    current_tau2: u64,
    keypair: Keypair,
    node_weight: NodeWeight,
}

impl ConsensusEngine {
    /// Main consensus loop (runs every τ₁)
    pub async fn run(&mut self) -> ! {
        loop {
            // 1. Wait for next τ₁ boundary
            self.wait_for_tau1().await;

            // 2. Sign presence (if Full Node)
            if self.is_full_node() {
                self.sign_presence().await;
            }

            // 3. Check if τ₂ ended
            if self.tau2_ended() {
                self.finalize_tau2().await;
            }

            // 4. Process incoming slices
            self.process_pending_slices().await;

            // 5. Update finality
            self.update_finality().await;
        }
    }

    async fn finalize_tau2(&mut self) {
        // 1. Получить prev_slice_hash из storage
        let prev_slice = self.storage.get_slice(self.current_tau2 - 1)?;
        let prev_slice_hash = prev_slice.hash();

        // 2. Собрать все presence proofs за этот τ₂
        let presences = self.collect_presences(self.current_tau2).await;

        // 3. Запустить лотерею
        let mut lottery = Lottery::new(prev_slice_hash, self.current_tau2);
        for presence in &presences {
            // Преобразовать PresenceProof в LotteryParticipant
            let participant = self.presence_to_participant(presence)?;
            lottery.add_participant(participant);
        }
        let result = lottery.run();

        // 4. Если мы выиграли, создать слайс
        if result.winners[0].pubkey == self.keypair.public_key() {
            let slice = self.produce_slice(presences, &result, prev_slice_hash).await?;
            self.broadcast_slice(&slice).await;
            self.apply_slice(slice).await?;
        } else {
            // 5. Ждать слайс от победителя
            let slice = self.wait_for_slice(result.winners[0].pubkey).await?;
            self.verify_and_apply_slice(slice).await?;
        }

        self.current_tau2 += 1;
    }
}
```

### 3. State Machine

```rust
pub enum NodeState {
    /// Синхронизация с сетью
    Syncing { progress: f64 },
    /// Активное участие в консенсусе
    Active,
    /// В cooldown периоде
    Cooldown { until_tau2: u64 },
    /// Офлайн
    Offline,
}

impl ConsensusEngine {
    pub fn state(&self) -> NodeState {
        if self.is_syncing() {
            NodeState::Syncing { progress: self.sync_progress() }
        } else if self.in_cooldown() {
            NodeState::Cooldown { until_tau2: self.cooldown_until }
        } else {
            NodeState::Active
        }
    }
}
```

### 4. Event System

```rust
pub enum ConsensusEvent {
    /// Новый слайс принят
    SliceAccepted { hash: Hash, height: u64 },
    /// Произошла реорганизация
    Reorg { depth: u32, new_head: Hash },
    /// Checkpoint финализирован
    CheckpointFinalized { tau3_index: u64 },
    /// Мы выиграли лотерею
    LotteryWon { tau2_index: u64, slot: u32 },
    /// Cooldown начался
    CooldownStarted { until_tau2: u64 },
}

pub trait ConsensusListener {
    fn on_event(&mut self, event: ConsensusEvent);
}
```

### 5. Error Handling

```rust
#[derive(Debug, thiserror::Error)]
pub enum MontanaError {
    #[error("Consensus error: {0}")]
    Consensus(#[from] ConsensusError),

    #[error("Network error: {0}")]
    Network(#[from] NetworkError),

    #[error("Storage error: {0}")]
    Storage(#[from] StorageError),

    #[error("Crypto error: {0}")]
    Crypto(#[from] CryptoError),

    #[error("Invalid configuration: {0}")]
    Config(String),
}
```

---

## Тесты интеграции

```rust
#[tokio::test]
async fn test_full_tau2_cycle() {
    // 1. Create 3 nodes
    // 2. Run for 1 τ₂
    // 3. Verify all have same head
}

#[tokio::test]
async fn test_reorg_handling() {
    // 1. Create partition
    // 2. Both sides produce slices
    // 3. Heal partition
    // 4. Verify reorg to correct chain
}

#[tokio::test]
async fn test_finality_checkpoint() {
    // 1. Run for τ₃ (mock time)
    // 2. Verify checkpoint created
    // 3. Try to reorg below checkpoint
    // 4. Verify rejection
}
```

---

## Константы интеграции

```rust
// Timing
pub const TAU1_SECS: u64 = 60;
pub const TAU2_SECS: u64 = 600;
pub const TAU3_SECS: u64 = 1_209_600;  // 14 days

// Network
pub const MAX_PEERS: usize = 125;
pub const SLICE_PROPAGATION_TIMEOUT_MS: u64 = 5000;

// Consensus
pub const SLOTS_PER_TAU2: u32 = 10;
pub const GRACE_PERIOD_SECS: u64 = 30;
```

---

## Выход

Обновить:
1. `lib.rs` — Public API и re-exports
2. `main.rs` — CLI и node startup
3. Новый файл `engine.rs` — ConsensusEngine

**Стиль:** async/await, tokio runtime, structured logging (tracing).
