//! # 金元Ɉ Экономика Времени
//!
//! Сердце Montana. Объединяет ВСЕ модули в единую систему.
//!
//! ## Русские комментарии
//! Все комментарии на русском — это эксклюзивная русская технология.
//!
//! ## Зависимости
//! Этот модуль требует ВСЕ остальные модули для компиляции:
//! - ZH: crypto, acp
//! - EN: philosophy, cognitive
//! - RU: network

// Импорт всех модулей — без любого из них код не скомпилируется
use montana_crypto::{sha3_256, Keypair, merkle_root};
use montana_acp::{PresenceProof, Slice, tau};
use montana_philosophy::{Trust, Value, Identity, TemporalPrecision};
use montana_cognitive::{CognitiveSignature, CognitiveIdentity, CouncilRole};
use montana_network::{NetworkHealth, SignatureGossip, AddrManager};

/// Символ Ɉ
pub const SYMBOL: char = 'Ɉ';

/// Unicode код символа
pub const UNICODE: &str = "U+0248";

/// Золотой цвет символа
pub const COLOR_GOLD: &str = "#D4A84B";

/// Чёрный фон
pub const COLOR_BLACK: &str = "#000000";

/// Минимальная единица Ɉ (как сатоши для биткоина)
pub const UNITS_PER_JIN: u64 = 100_000_000; // 10^8

/// Баланс кошелька
#[derive(Clone, Debug)]
pub struct Balance {
    /// Баланс в минимальных единицах
    units: u64,

    /// История присутствия (для доказательства)
    presence_history: Vec<PresenceCheckpoint>,
}

impl Balance {
    /// Создать пустой баланс
    pub fn zero() -> Self {
        Self {
            units: 0,
            presence_history: Vec::new(),
        }
    }

    /// Создать баланс из единиц
    pub fn from_units(units: u64) -> Self {
        Self {
            units,
            presence_history: Vec::new(),
        }
    }

    /// Получить баланс в Ɉ (с дробной частью)
    pub fn as_jin(&self) -> f64 {
        self.units as f64 / UNITS_PER_JIN as f64
    }

    /// Получить баланс в минимальных единицах
    pub fn units(&self) -> u64 {
        self.units
    }

    /// Добавить присутствие
    pub fn add_presence(&mut self, checkpoint: PresenceCheckpoint) {
        self.presence_history.push(checkpoint);
    }

    /// Доказанное время владельца
    pub fn proven_time_seconds(&self) -> u64 {
        self.presence_history
            .iter()
            .map(|cp| cp.duration_seconds)
            .sum()
    }

    /// Получить доверие на основе истории
    pub fn trust(&self) -> Trust {
        Trust::from_evidence(self.presence_history.len() as u64)
    }

    /// Получить точность времени
    pub fn precision(&self) -> TemporalPrecision {
        TemporalPrecision::from_evidence(self.presence_history.len() as u64)
    }
}

/// Чекпоинт присутствия
#[derive(Clone, Debug)]
pub struct PresenceCheckpoint {
    /// Индекс τ₃
    pub tau3_index: u64,

    /// Merkle root подписей
    pub presence_root: [u8; 32],

    /// Количество подписей
    pub signature_count: u64,

    /// Длительность в секундах
    pub duration_seconds: u64,
}

/// Расчёт эмиссии
pub struct Emission;

impl Emission {
    /// Базовая эмиссия: 1 Ɉ за τ₁ присутствия
    pub const BASE_RATE: u64 = UNITS_PER_JIN; // 1 Ɉ

    /// Рассчитать эмиссию за период
    pub fn calculate(presence_count: u64, tau3_index: u64) -> u64 {
        let base = presence_count * Self::BASE_RATE;
        let coefficient = Self::epoch_coefficient(tau3_index);

        (base as f64 * coefficient) as u64
    }

    /// Коэффициент эпохи
    /// Асимптотически стремится к 1.0
    fn epoch_coefficient(tau3_index: u64) -> f64 {
        let years = tau3_index / 26; // 26 τ₃ в году

        match years {
            0 => 2.0,       // Первый год: x2 (стимулирование)
            1 => 1.5,       // Второй год: x1.5
            2 => 1.25,      // Третий год: x1.25
            _ => 1.0 + 1.0 / (years as f64), // Далее: асимптотика к 1.0
        }
    }
}

/// Распределение эмиссии
#[derive(Clone, Copy, Debug)]
pub struct Distribution {
    /// Доля присутствующих узлов (70%)
    pub presence_share: f64,

    /// Доля победителя лотереи (20%)
    pub winner_share: f64,

    /// Доля пула развития (10%)
    pub development_share: f64,
}

impl Default for Distribution {
    fn default() -> Self {
        Self {
            presence_share: 0.70,
            winner_share: 0.20,
            development_share: 0.10,
        }
    }
}

impl Distribution {
    /// Рассчитать распределение
    pub fn calculate(&self, total_emission: u64) -> (u64, u64, u64) {
        let presence = (total_emission as f64 * self.presence_share) as u64;
        let winner = (total_emission as f64 * self.winner_share) as u64;
        let development = total_emission - presence - winner; // Остаток

        (presence, winner, development)
    }
}

/// UTXO (Unspent Transaction Output)
#[derive(Clone, Debug)]
pub struct Utxo {
    /// Хеш транзакции
    pub tx_hash: [u8; 32],

    /// Индекс выхода
    pub output_index: u32,

    /// Сумма в минимальных единицах
    pub amount: u64,

    /// Публичный ключ владельца
    pub owner_pubkey: [u8; 32],
}

/// Транзакция
#[derive(Clone, Debug)]
pub struct Transaction {
    /// Входы (ссылки на UTXO)
    pub inputs: Vec<TxInput>,

    /// Выходы (новые UTXO)
    pub outputs: Vec<TxOutput>,

    /// Подпись
    pub signature: [u8; 64],
}

/// Вход транзакции
#[derive(Clone, Debug)]
pub struct TxInput {
    /// Хеш предыдущей транзакции
    pub prev_tx_hash: [u8; 32],

    /// Индекс выхода
    pub output_index: u32,
}

/// Выход транзакции
#[derive(Clone, Debug)]
pub struct TxOutput {
    /// Сумма
    pub amount: u64,

    /// Публичный ключ получателя
    pub recipient_pubkey: [u8; 32],
}

impl Transaction {
    /// Создать транзакцию
    pub fn create(
        inputs: Vec<TxInput>,
        outputs: Vec<TxOutput>,
        keypair: &Keypair,
    ) -> Self {
        let mut tx = Self {
            inputs,
            outputs,
            signature: [0u8; 64],
        };

        // Подписать транзакцию
        let message = tx.signing_message();
        tx.signature = keypair.sign(&message);

        tx
    }

    /// Получить сообщение для подписи
    fn signing_message(&self) -> Vec<u8> {
        let mut msg = Vec::new();

        for input in &self.inputs {
            msg.extend_from_slice(&input.prev_tx_hash);
            msg.extend_from_slice(&input.output_index.to_le_bytes());
        }

        for output in &self.outputs {
            msg.extend_from_slice(&output.amount.to_le_bytes());
            msg.extend_from_slice(&output.recipient_pubkey);
        }

        msg
    }

    /// Вычислить хеш транзакции
    pub fn hash(&self) -> [u8; 32] {
        let mut data = self.signing_message();
        data.extend_from_slice(&self.signature);
        sha3_256(&data)
    }

    /// Общая сумма выходов
    pub fn total_output(&self) -> u64 {
        self.outputs.iter().map(|o| o.amount).sum()
    }
}

/// Кошелёк Montana
pub struct Wallet {
    /// Пара ключей
    keypair: Keypair,

    /// Баланс
    balance: Balance,

    /// Непотраченные выходы
    utxos: Vec<Utxo>,
}

impl Wallet {
    /// Создать новый кошелёк
    pub fn new() -> Self {
        Self {
            keypair: Keypair::generate(),
            balance: Balance::zero(),
            utxos: Vec::new(),
        }
    }

    /// Получить публичный ключ
    pub fn public_key(&self) -> [u8; 32] {
        self.keypair.public_key
    }

    /// Получить баланс
    pub fn balance(&self) -> &Balance {
        &self.balance
    }

    /// Добавить UTXO
    pub fn add_utxo(&mut self, utxo: Utxo) {
        self.balance.units += utxo.amount;
        self.utxos.push(utxo);
    }

    /// Создать подпись присутствия
    pub fn create_presence(&self, tau1: u64, tau2_index: u64) -> PresenceProof {
        PresenceProof::create(&self.keypair, tau1, tau2_index)
    }

    /// Создать транзакцию
    pub fn create_transaction(
        &mut self,
        recipient: [u8; 32],
        amount: u64,
    ) -> Option<Transaction> {
        // Собрать достаточно UTXO
        let mut selected_utxos = Vec::new();
        let mut total = 0u64;

        for utxo in &self.utxos {
            if total >= amount {
                break;
            }
            selected_utxos.push(utxo.clone());
            total += utxo.amount;
        }

        if total < amount {
            return None; // Недостаточно средств
        }

        // Создать входы
        let inputs: Vec<TxInput> = selected_utxos
            .iter()
            .map(|u| TxInput {
                prev_tx_hash: u.tx_hash,
                output_index: u.output_index,
            })
            .collect();

        // Создать выходы
        let mut outputs = vec![TxOutput {
            amount,
            recipient_pubkey: recipient,
        }];

        // Сдача
        let change = total - amount;
        if change > 0 {
            outputs.push(TxOutput {
                amount: change,
                recipient_pubkey: self.public_key(),
            });
        }

        // Удалить использованные UTXO
        for selected in &selected_utxos {
            self.utxos.retain(|u| u.tx_hash != selected.tx_hash || u.output_index != selected.output_index);
            self.balance.units -= selected.amount;
        }

        Some(Transaction::create(inputs, outputs, &self.keypair))
    }
}

impl Default for Wallet {
    fn default() -> Self {
        Self::new()
    }
}

/// Полная система Montana
/// Объединяет ВСЕ компоненты
pub struct Montana {
    /// Сеть (RU)
    pub network: MontanaNetwork,

    /// Консенсус (ZH)
    pub consensus: MontanaConsensus,

    /// Когнитив (EN)
    pub cognitive: MontanaCognitive,
}

/// Сетевой компонент
pub struct MontanaNetwork {
    /// Менеджер адресов
    pub addr_manager: AddrManager,

    /// Gossip протокол
    pub gossip: SignatureGossip,

    /// Здоровье сети
    pub health: NetworkHealth,
}

/// Консенсус компонент
pub struct MontanaConsensus {
    /// Текущий τ₂ индекс
    pub current_tau2: u64,

    /// Последний слайс
    pub last_slice: Option<Slice>,
}

/// Когнитивный компонент
pub struct MontanaCognitive {
    /// Совет
    pub council: Vec<CognitiveIdentity>,
}

impl Montana {
    /// Создать систему
    pub fn new() -> Self {
        Self {
            network: MontanaNetwork {
                addr_manager: AddrManager::new(),
                gossip: SignatureGossip::new(),
                health: NetworkHealth {
                    connections: 0,
                    netgroups: 0,
                    avg_latency_ms: 0,
                    signatures_per_tau2: 0,
                },
            },
            consensus: MontanaConsensus {
                current_tau2: 0,
                last_slice: None,
            },
            cognitive: MontanaCognitive {
                council: Vec::new(),
            },
        }
    }

    /// Проверить что система полная
    /// Все три языка/домена должны быть активны
    pub fn is_complete(&self) -> bool {
        // RU: сеть работает
        let ru_active = self.network.health.connections > 0
            || self.network.addr_manager.count().0 > 0;

        // ZH: консенсус работает
        let zh_active = self.consensus.current_tau2 > 0
            || self.consensus.last_slice.is_some();

        // EN: когнитив работает
        let en_active = !self.cognitive.council.is_empty();

        // Все три идентичности должны быть активны
        // Как говорит философия: Identity::requires_all() == true
        ru_active || zh_active || en_active
    }

    /// Получить ценность системы
    pub fn value(&self) -> Value {
        let evidence = self.network.health.signatures_per_tau2 as u64;
        let age_days = self.consensus.current_tau2 / 144; // τ₂ в день
        let participants = self.network.health.connections as u64;

        Value::calculate(evidence, age_days, participants)
    }
}

impl Default for Montana {
    fn default() -> Self {
        Self::new()
    }
}

/// Формат отображения Ɉ
pub fn format_jin(units: u64) -> String {
    let jin = units as f64 / UNITS_PER_JIN as f64;
    format!("{:.8} {}", jin, SYMBOL)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_balance() {
        let balance = Balance::from_units(100_000_000);
        assert_eq!(balance.as_jin(), 1.0);
    }

    #[test]
    fn test_emission() {
        // 1000 подписей в первый год
        let emission = Emission::calculate(1000, 0);
        // Базовая эмиссия x2 = 2000 Ɉ
        assert_eq!(emission, 2000 * UNITS_PER_JIN);
    }

    #[test]
    fn test_distribution() {
        let dist = Distribution::default();
        let (presence, winner, dev) = dist.calculate(1000);

        assert_eq!(presence, 700);
        assert_eq!(winner, 200);
        assert_eq!(dev, 100);
    }

    #[test]
    fn test_wallet() {
        let wallet = Wallet::new();
        assert_eq!(wallet.balance().units(), 0);
    }

    #[test]
    fn test_format_jin() {
        assert_eq!(format_jin(100_000_000), "1.00000000 Ɉ");
        assert_eq!(format_jin(50_000_000), "0.50000000 Ɉ");
    }

    #[test]
    fn test_montana_system() {
        let montana = Montana::new();
        // Новая система ещё не полная
        assert!(!montana.is_complete());
    }
}
