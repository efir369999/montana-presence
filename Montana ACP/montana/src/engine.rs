//! Montana Consensus Engine
//!
//! Интегрирует все слои:
//! - consensus.rs — Lottery, Slice, Presence
//! - types.rs — Structures
//! - cooldown.rs — Adaptive Cooldown
//! - crypto.rs — Cryptography
//! - finality.rs — Checkpoints
//! - fork_choice.rs — Chain selection
//! - merkle.rs — Merkle proofs

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{self, Duration, Instant};

use crate::consensus::{
    FullNodePresence, Lottery, Slice, SliceHeader, TAU1_SECS, TAU2_SECS, VerifiedUserPresence, NodeTier
};
use crate::cooldown::AdaptiveCooldown;
use crate::crypto::Keypair;
use crate::finality::FinalityTracker;
use crate::fork_choice::{ForkChoice, ChainHead, ReorgResult};
use crate::merkle::MerkleTree;
use crate::net::Network;
use crate::types::{Hash, NodeType, PublicKey, Signature, Transaction};
use crate::consensus::LotteryParticipant;

/// Конфигурация Montana node
#[derive(Debug, Clone)]
pub struct Config {
    pub node_type: NodeType,
    pub genesis_hash: Hash,
    pub tau1_interval: Duration,
    pub tau2_interval: Duration,
}

/// Main Montana node
pub struct MontanaNode {
    config: Config,
    state: RwLock<NodeState>,
    consensus: ConsensusEngine,
    network: Arc<Network>,
}

// ============================================================================
// TRAIT IMPLEMENTATIONS
// ============================================================================


impl MontanaNode {
    pub fn new(config: Config, network: Arc<Network>) -> Self {
        let consensus = ConsensusEngine::new(config.clone());
        let state = RwLock::new(NodeState::Syncing { progress: 0.0 });

        Self {
            config,
            state,
            consensus,
            network,
        }
    }

    pub async fn start(&mut self) -> Result<(), MontanaError> {
        self.consensus.start().await?;
        *self.state.write().await = NodeState::Active;
        Ok(())
    }

    pub async fn stop(&mut self) -> Result<(), MontanaError> {
        self.consensus.stop().await?;
        Ok(())
    }

    pub async fn state(&self) -> NodeState {
        *self.state.read().await
    }
}

/// Consensus Engine — Main Loop
pub struct ConsensusEngine {
    config: Config,
    keypair: Keypair,
    fork_choice: RwLock<ForkChoice>,
    finality: RwLock<FinalityTracker>,
    cooldown: RwLock<AdaptiveCooldown>,
    current_tau2: RwLock<u64>,
    running: RwLock<bool>,
    lottery: RwLock<Option<Lottery>>,
}

impl ConsensusEngine {
    pub fn new(config: Config) -> Self {
        let fork_choice = ForkChoice::new(config.genesis_hash);
        let finality = FinalityTracker::new();
        let cooldown = AdaptiveCooldown::new();

        Self {
            config,
            keypair: Keypair::generate(), // В реальности загружать из файла
            fork_choice: RwLock::new(fork_choice),
            finality: RwLock::new(finality),
            cooldown: RwLock::new(cooldown),
            current_tau2: RwLock::new(0),
            running: RwLock::new(false),
            lottery: RwLock::new(None),
        }
    }

    /// Запустить основной консенсусный цикл
    pub async fn start(&self) -> Result<(), MontanaError> {
        let mut running = self.running.write().await;
        if *running {
            return Err(MontanaError::AlreadyRunning);
        }
        *running = true;
        drop(running);

        // TODO: Запустить main loop в фоне
        // let engine = self as *const Self as *mut Self;
        // tokio::spawn(async move {
        //     (*engine).run().await;
        // });

        Ok(())
    }

    /// Остановить движок
    pub async fn stop(&self) -> Result<(), MontanaError> {
        *self.running.write().await = false;
        Ok(())
    }

    /// Main consensus loop (runs every τ₁)
    pub async fn run(&self) {
        let tau1_duration = Duration::from_secs(TAU1_SECS);

        while *self.running.read().await {
            let tau1_start = Instant::now();

            // 1. Wait for next τ₁ boundary
            self.wait_for_tau1().await;

            // 2. Sign presence (if Full Node)
            if matches!(self.config.node_type, NodeType::Full) {
                if let Err(e) = self.sign_presence().await {
                    eprintln!("Presence signing error: {:?}", e);
                }
            }

            // 3. Check if τ₂ ended
            if self.tau2_ended().await {
                if let Err(e) = self.finalize_tau2().await {
                    eprintln!("τ₂ finalization error: {:?}", e);
                }
            }

            // 4. Process incoming slices
            if let Err(e) = self.process_pending_slices().await {
                eprintln!("Slice processing error: {:?}", e);
            }

            // 5. Update finality
            if let Err(e) = self.update_finality().await {
                eprintln!("Finality update error: {:?}", e);
            }

            // Ждём до следующего τ₁
            let elapsed = tau1_start.elapsed();
            if elapsed < tau1_duration {
                time::sleep(tau1_duration - elapsed).await;
            }
        }
    }

    async fn wait_for_tau1(&self) {
        // Синхронизируемся с τ₁ границей
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let tau1_boundary = (now / TAU1_SECS) * TAU1_SECS + TAU1_SECS;
        let wait_time = tau1_boundary - now;

        if wait_time > 0 {
            time::sleep(Duration::from_secs(wait_time)).await;
        }
    }

    async fn sign_presence(&self) -> Result<(), MontanaError> {
        let current_tau2 = *self.current_tau2.read().await;
        let pubkey_vec = self.keypair.public_key();
        let mut pubkey_array = [0u8; 32];
        pubkey_array.copy_from_slice(&pubkey_vec[..32]);

        let presence = FullNodePresence {
            pubkey: pubkey_array,
            tau2_index: current_tau2,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            prev_slice_hash: [0u8; 32], // TODO
            tier: 0, // FullNode
            signature: vec![], // TODO: Реальная подпись
        };

        // TODO: Отправить presence в сеть
        println!("Signed presence for τ₂ {}", current_tau2);

        Ok(())
    }

    async fn tau2_ended(&self) -> bool {
        // Проверяем окончание τ₂ периода
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let current_tau2 = *self.current_tau2.read().await;
        let tau2_end = (current_tau2 + 1) * TAU2_SECS;

        now >= tau2_end
    }

    fn presence_to_participant(&self, presence: &FullNodePresence) -> LotteryParticipant {
        // Конвертируем u8 tier в NodeTier
        let node_tier = match presence.tier {
            0 => NodeTier::FullNode,
            1 => NodeTier::VerifiedUser,
            _ => NodeTier::FullNode, // fallback
        };

        // TODO: Реальный расчёт веса на основе tier и истории
        let weight = match node_tier {
            NodeTier::FullNode => 1000,
            NodeTier::VerifiedUser => 20000,
        };

        LotteryParticipant {
            pubkey: presence.pubkey,
            tier: node_tier,
            weight,
            presence_hash: crate::crypto::sha3(&presence.pubkey), // TODO: Реальный presence hash
        }
    }

    async fn finalize_tau2(&self) -> Result<(), MontanaError> {
        let current_tau2 = *self.current_tau2.read().await;

        // 1. Collect all presences (упрощённо)
        let presences = self.collect_presences().await;

        // 2. Run lottery
        let prev_slice_hash = self.get_prev_slice_hash().await;
        let mut lottery = Lottery::new(prev_slice_hash, current_tau2);

        for presence in &presences {
            let participant = self.presence_to_participant(presence);
            lottery.add_participant(participant);
        }

        let result = lottery.run();

        // 3. If we won, produce slice
        let our_pubkey_vec = self.keypair.public_key();
        let mut our_pubkey_array = [0u8; 32];
        our_pubkey_array.copy_from_slice(&our_pubkey_vec[..32]);

        if result.winners[0].pubkey == our_pubkey_array {
            let slice = self.produce_slice(presences, result.clone()).await?;
            self.broadcast_slice(slice).await?;
        }

        // 4. Wait for slice from winner (упрощённо)
        let winner_pubkey = result.winners[0].pubkey.clone();
        let slice = self.wait_for_slice(winner_pubkey.to_vec()).await?;

        // 5. Verify and apply
        self.verify_and_apply_slice(slice).await?;

        // Обновляем τ₂
        *self.current_tau2.write().await += 1;

        Ok(())
    }

    async fn collect_presences(&self) -> Vec<FullNodePresence> {
        // TODO: Реальный сбор presence из сети
        vec![]
    }

    async fn get_prev_slice_hash(&self) -> Hash {
        // TODO: Получить хеш предыдущего слайса
        [0u8; 32]
    }

    async fn produce_slice(&self, presences: Vec<FullNodePresence>, lottery_result: crate::consensus::LotteryResult)
        -> Result<Slice, MontanaError>
    {
        let current_tau2 = *self.current_tau2.read().await;
        let prev_hash = self.get_prev_slice_hash().await;

        // Создаём Merkle tree для presence
        let presence_hashes: Vec<Hash> = presences.iter()
            .map(|p| self.hash_presence(p))
            .collect();
        let presence_tree = MerkleTree::new(presence_hashes);
        let presence_root = presence_tree.root();

        // Создаём header
        let header = SliceHeader {
            version: 1,
            height: current_tau2,
            tau2_index: current_tau2,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            prev_slice_hash: prev_hash,
            presence_root,
            tx_root: [0u8; 32], // TODO: transactions
            producer_pubkey: {
                let pubkey_vec = self.keypair.public_key();
                let mut pubkey_array = [0u8; 32];
                pubkey_array.copy_from_slice(&pubkey_vec[..32]);
                pubkey_array
            },
            lottery_ticket: [0u8; 32], // TODO: lottery ticket
            slot: 0,
            finality_checkpoint: None,
        };

        Ok(Slice {
            header,
            full_node_presences: presences,
            verified_user_presences: vec![], // TODO
            transactions: vec![], // TODO
            producer_signature: vec![], // TODO
            attestations: vec![],
        })
    }

    async fn broadcast_slice(&self, slice: Slice) -> Result<(), MontanaError> {
        // TODO: Отправить слайс в сеть
        println!("Broadcasting slice {}", slice.header.height);
        Ok(())
    }

    async fn wait_for_slice(&self, winner_pubkey: PublicKey) -> Result<Slice, MontanaError> {
        // TODO: Реальное ожидание слайса
        // Пока возвращаем mock
        Err(MontanaError::SliceTimeout)
    }

    async fn verify_and_apply_slice(&self, slice: Slice) -> Result<(), MontanaError> {
        // Верифицируем слайс
        self.verify_slice(&slice).await?;

        // Добавляем в fork choice
        let head = ChainHead::from_slice_header(
            slice.header.hash(),
            slice.header.height,
            slice.header.tau2_index,
            self.calculate_slice_weight(&slice),
        );

        self.fork_choice.write().await.add_head(head.clone())?;

        // Проверяем reorg
        if self.fork_choice.write().await.should_reorg(&head) {
            let result = self.fork_choice.write().await.reorg_to(head)?;
            self.handle_reorg(result).await?;
        }

        Ok(())
    }

    async fn verify_slice(&self, slice: &Slice) -> Result<(), MontanaError> {
        // TODO: Полная верификация слайса
        // - Проверка lottery winner
        // - Проверка presence root
        // - Проверка подписей
        Ok(())
    }

    fn calculate_slice_weight(&self, slice: &Slice) -> u64 {
        // Вес слайса = сумма весов presence
        slice.full_node_presences.iter()
            .map(|p| 1000) // TODO: Реальный расчёт веса
            .sum()
    }

    async fn handle_reorg(&self, result: ReorgResult) -> Result<(), MontanaError> {
        // TODO: Обработка reorg - обновление mempool, etc.
        println!("Reorg: {} orphaned, {} adopted, depth {}",
                result.orphaned.len(), result.adopted.len(), result.depth);
        Ok(())
    }

    async fn process_pending_slices(&self) -> Result<(), MontanaError> {
        // TODO: Обработка входящих слайсов из сети
        Ok(())
    }

    async fn update_finality(&self) -> Result<(), MontanaError> {
        // TODO: Обновление финальности для новых слайсов
        Ok(())
    }

    fn hash_presence(&self, presence: &FullNodePresence) -> Hash {
        // TODO: Реальный хеш presence
        [0u8; 32]
    }
}

/// Состояние ноды
#[derive(Debug, Clone, Copy, PartialEq)]
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

/// События консенсуса
#[derive(Debug)]
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

/// Listener для событий консенсуса
pub trait ConsensusListener: Send + Sync {
    fn on_event(&mut self, event: ConsensusEvent);
}

/// Ошибки Montana
#[derive(Debug, thiserror::Error)]
pub enum MontanaError {
    #[error("Consensus error: {0}")]
    Consensus(String),

    #[error("Network error: {0}")]
    Network(String),

    #[error("Storage error: {0}")]
    Storage(String),

    #[error("Crypto error: {0}")]
    Crypto(String),

    #[error("Invalid configuration: {0}")]
    Config(String),

    #[error("Fork choice error: {0}")]
    ForkChoice(#[from] crate::fork_choice::ForkChoiceError),

    #[error("Finality error: {0}")]
    Finality(#[from] crate::finality::FinalityError),

    #[error("Already running")]
    AlreadyRunning,

    #[error("Slice timeout")]
    SliceTimeout,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    #[tokio::test]
    async fn test_node_creation() {
        let config = Config {
            node_type: NodeType::Full,
            genesis_hash: [0u8; 32],
            tau1_interval: Duration::from_secs(60),
            tau2_interval: Duration::from_secs(600),
        };

        let network = Arc::new(Network::new(crate::net::NetConfig::default()));
        let node = MontanaNode::new(config, network);

        assert!(matches!(node.state().await, NodeState::Syncing { .. }));
    }

    #[tokio::test]
    async fn test_engine_creation() {
        let config = Config {
            node_type: NodeType::Full,
            genesis_hash: [0u8; 32],
            tau1_interval: Duration::from_secs(60),
            tau2_interval: Duration::from_secs(600),
        };

        let engine = ConsensusEngine::new(config);
        assert_eq!(engine.config.node_type, NodeType::Full);
    }

    #[tokio::test]
    async fn test_tau2_boundary_detection() {
        let config = Config {
            node_type: NodeType::Full,
            genesis_hash: [0u8; 32],
            tau1_interval: Duration::from_secs(60),
            tau2_interval: Duration::from_secs(600),
        };

        let engine = ConsensusEngine::new(config);

        // Начало τ₂ = 0, конец = 600
        assert!(!engine.tau2_ended().await);

        // Имитируем время после конца τ₂
        *engine.current_tau2.write().await = 0;
        // TODO: Mock time source для тестирования
    }
}
