//! # P2P Сетевой модуль
//!
//! Распространение подписей присутствия между узлами.
//!
//! ## Русские комментарии
//! Все комментарии на русском — это эксклюзивная русская технология.

use montana_crypto::{sha3_256, secure_random_bytes};
use montana_acp::PresenceProof;
use std::collections::{HashMap, HashSet, VecDeque};
use std::net::IpAddr;

/// Лимиты соединений
/// Защита от перегрузки и Eclipse-атак
#[derive(Clone, Copy, Debug)]
pub struct ConnectionLimits {
    /// Максимум входящих соединений
    pub max_inbound: usize,

    /// Максимум исходящих соединений
    pub max_outbound: usize,

    /// Максимум соединений на подсеть /16
    pub max_per_netgroup: usize,

    /// Минимум различных подсетей
    pub min_netgroups: usize,
}

impl Default for ConnectionLimits {
    fn default() -> Self {
        Self {
            max_inbound: 117,      // Защита от перегрузки
            max_outbound: 11,      // Связность без избыточности
            max_per_netgroup: 2,   // Разнообразие подсетей
            min_netgroups: 4,      // Географическое распределение
        }
    }
}

/// Сетевой адрес узла
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct NetAddr {
    /// IP адрес
    pub ip: IpAddr,

    /// Порт
    pub port: u16,

    /// Временная метка последнего контакта
    pub timestamp: u64,

    /// Сервисы узла
    pub services: u64,
}

impl NetAddr {
    /// Создать новый адрес
    pub fn new(ip: IpAddr, port: u16) -> Self {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            ip,
            port,
            timestamp,
            services: 0,
        }
    }

    /// Проверить роутабельность адреса
    /// Отфильтровать локальные и зарезервированные адреса
    pub fn is_routable(&self) -> bool {
        match self.ip {
            IpAddr::V4(ip) => {
                !ip.is_private()
                    && !ip.is_loopback()
                    && !ip.is_link_local()
                    && !ip.is_broadcast()
                    && !ip.is_documentation()
                    && !ip.is_unspecified()
            }
            IpAddr::V6(ip) => {
                !ip.is_loopback() && !ip.is_unspecified()
            }
        }
    }

    /// Получить ключ группы (для бакетирования)
    /// IPv4: /16 подсеть, IPv6: /32 подсеть
    pub fn group_key(&self) -> [u8; 4] {
        match self.ip {
            IpAddr::V4(ip) => {
                let octets = ip.octets();
                [octets[0], octets[1], 0, 0] // /16
            }
            IpAddr::V6(ip) => {
                let segments = ip.segments();
                let bytes = segments[0].to_be_bytes();
                let bytes2 = segments[1].to_be_bytes();
                [bytes[0], bytes[1], bytes2[0], bytes2[1]] // /32
            }
        }
    }
}

/// Менеджер адресов
/// Защита от Eclipse через криптографическое бакетирование
pub struct AddrManager {
    /// Новые адреса (непроверенные)
    new_addrs: HashMap<usize, Vec<NetAddr>>,

    /// Проверенные адреса (успешно подключались)
    tried_addrs: HashMap<usize, Vec<NetAddr>>,

    /// Секретный ключ для бакетирования
    /// Уникален для каждого узла — атакующий не знает схему
    bucket_key: [u8; 32],

    /// Количество new бакетов
    new_buckets: usize,

    /// Количество tried бакетов
    tried_buckets: usize,

    /// Максимум адресов в бакете
    bucket_size: usize,
}

impl AddrManager {
    /// Создать новый менеджер адресов
    pub fn new() -> Self {
        Self {
            new_addrs: HashMap::new(),
            tried_addrs: HashMap::new(),
            bucket_key: secure_random_bytes(),
            new_buckets: 1024,
            tried_buckets: 256,
            bucket_size: 64,
        }
    }

    /// Вычислить бакет для адреса
    /// Криптографическое размещение — атакующий не может предсказать
    fn calculate_bucket(&self, addr: &NetAddr, source: &NetAddr, is_new: bool) -> usize {
        let mut data = Vec::new();
        data.extend_from_slice(&self.bucket_key);
        data.extend_from_slice(&addr.group_key());
        data.extend_from_slice(&source.group_key());

        let hash = sha3_256(&data);
        let bucket_count = if is_new { self.new_buckets } else { self.tried_buckets };

        (u64::from_le_bytes(hash[0..8].try_into().unwrap()) as usize) % bucket_count
    }

    /// Добавить адрес в new таблицу
    pub fn add_new(&mut self, addr: NetAddr, source: &NetAddr) -> bool {
        // Фильтрация нероутабельных
        if !addr.is_routable() {
            return false;
        }

        let bucket = self.calculate_bucket(&addr, source, true);

        let bucket_addrs = self.new_addrs.entry(bucket).or_insert_with(Vec::new);

        // Проверить лимит бакета
        if bucket_addrs.len() >= self.bucket_size {
            // Удалить самый старый
            if let Some(oldest_idx) = bucket_addrs
                .iter()
                .enumerate()
                .min_by_key(|(_, a)| a.timestamp)
                .map(|(i, _)| i)
            {
                bucket_addrs.remove(oldest_idx);
            }
        }

        // Проверить дубликаты
        if !bucket_addrs.contains(&addr) {
            bucket_addrs.push(addr);
            true
        } else {
            false
        }
    }

    /// Перевести адрес в tried (после успешного подключения)
    pub fn mark_good(&mut self, addr: &NetAddr) {
        // Найти и удалить из new
        for bucket_addrs in self.new_addrs.values_mut() {
            if let Some(pos) = bucket_addrs.iter().position(|a| a == addr) {
                bucket_addrs.remove(pos);
                break;
            }
        }

        // Добавить в tried
        let dummy_source = NetAddr::new(addr.ip, 0);
        let bucket = self.calculate_bucket(addr, &dummy_source, false);

        let bucket_addrs = self.tried_addrs.entry(bucket).or_insert_with(Vec::new);

        if bucket_addrs.len() < self.bucket_size && !bucket_addrs.contains(addr) {
            bucket_addrs.push(addr.clone());
        }
    }

    /// Выбрать адрес для подключения
    /// Баланс между tried и new (50/50)
    pub fn select_for_connection(&self) -> Option<NetAddr> {
        let use_tried = rand::random::<bool>();

        if use_tried {
            self.select_from_tried().or_else(|| self.select_from_new())
        } else {
            self.select_from_new().or_else(|| self.select_from_tried())
        }
    }

    /// Выбрать из tried
    fn select_from_tried(&self) -> Option<NetAddr> {
        if self.tried_addrs.is_empty() {
            return None;
        }

        let bucket_idx = rand::random::<usize>() % self.tried_buckets;
        self.tried_addrs.get(&bucket_idx).and_then(|addrs| {
            if addrs.is_empty() {
                None
            } else {
                let idx = rand::random::<usize>() % addrs.len();
                Some(addrs[idx].clone())
            }
        })
    }

    /// Выбрать из new
    fn select_from_new(&self) -> Option<NetAddr> {
        if self.new_addrs.is_empty() {
            return None;
        }

        let bucket_idx = rand::random::<usize>() % self.new_buckets;
        self.new_addrs.get(&bucket_idx).and_then(|addrs| {
            if addrs.is_empty() {
                None
            } else {
                let idx = rand::random::<usize>() % addrs.len();
                Some(addrs[idx].clone())
            }
        })
    }

    /// Получить количество адресов
    pub fn count(&self) -> (usize, usize) {
        let new_count: usize = self.new_addrs.values().map(|v| v.len()).sum();
        let tried_count: usize = self.tried_addrs.values().map(|v| v.len()).sum();
        (new_count, tried_count)
    }
}

impl Default for AddrManager {
    fn default() -> Self {
        Self::new()
    }
}

/// Идентификатор пира
pub type PeerId = [u8; 32];

/// Статистика пира
#[derive(Clone, Debug, Default)]
pub struct PeerStats {
    /// Количество валидных сообщений
    pub valid_count: u64,

    /// Количество невалидных сообщений
    pub invalid_count: u64,

    /// Время последнего сообщения
    pub last_message: u64,

    /// Средняя задержка (мс)
    pub avg_latency_ms: u64,
}

/// Протокол распространения подписей
pub struct SignatureGossip {
    /// Очередь подписей для отправки
    outbound_queue: VecDeque<PresenceProof>,

    /// Фильтр виденных подписей (хеши)
    seen_filter: HashSet<[u8; 32]>,

    /// Статистика по пирам
    peer_stats: HashMap<PeerId, PeerStats>,

    /// Локальный пул подписей
    local_pool: Vec<PresenceProof>,

    /// Максимум подписей в пуле
    max_pool_size: usize,
}

impl SignatureGossip {
    /// Создать новый протокол gossip
    pub fn new() -> Self {
        Self {
            outbound_queue: VecDeque::new(),
            seen_filter: HashSet::new(),
            peer_stats: HashMap::new(),
            local_pool: Vec::new(),
            max_pool_size: 10_000,
        }
    }

    /// Обработать входящую подпись
    pub fn on_signature(&mut self, sig: PresenceProof, from: PeerId, current_tau2: u64) -> bool {
        let sig_hash = sig.hash();

        // Проверка на дубликат
        if self.seen_filter.contains(&sig_hash) {
            return false;
        }
        self.seen_filter.insert(sig_hash);

        // Валидация подписи
        if !sig.verify(current_tau2) {
            if let Some(stats) = self.peer_stats.get_mut(&from) {
                stats.invalid_count += 1;
            }
            return false;
        }

        // Обновить статистику пира
        if let Some(stats) = self.peer_stats.get_mut(&from) {
            stats.valid_count += 1;
            stats.last_message = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs();
        }

        // Добавить в локальный пул
        if self.local_pool.len() < self.max_pool_size {
            self.local_pool.push(sig.clone());
        }

        // Добавить в очередь на рассылку
        self.outbound_queue.push_back(sig);

        true
    }

    /// Получить следующую подпись для отправки
    pub fn next_outbound(&mut self) -> Option<PresenceProof> {
        self.outbound_queue.pop_front()
    }

    /// Зарегистрировать пира
    pub fn register_peer(&mut self, peer_id: PeerId) {
        self.peer_stats.insert(peer_id, PeerStats::default());
    }

    /// Удалить пира
    pub fn remove_peer(&mut self, peer_id: &PeerId) {
        self.peer_stats.remove(peer_id);
    }

    /// Получить подписи из пула
    pub fn get_pool(&self) -> &[PresenceProof] {
        &self.local_pool
    }

    /// Очистить пул (после закрытия τ₂)
    pub fn clear_pool(&mut self) {
        self.local_pool.clear();
        self.seen_filter.clear();
    }

    /// Получить статистику пира
    pub fn get_peer_stats(&self, peer_id: &PeerId) -> Option<&PeerStats> {
        self.peer_stats.get(peer_id)
    }
}

impl Default for SignatureGossip {
    fn default() -> Self {
        Self::new()
    }
}

/// Метрики здоровья сети
#[derive(Clone, Debug)]
pub struct NetworkHealth {
    /// Количество активных соединений
    pub connections: usize,

    /// Количество различных подсетей
    pub netgroups: usize,

    /// Среднее время отклика (мс)
    pub avg_latency_ms: u64,

    /// Количество подписей за последний τ₂
    pub signatures_per_tau2: usize,
}

impl NetworkHealth {
    /// Оценка здоровья сети (0.0 - 1.0)
    pub fn score(&self) -> f64 {
        let limits = ConnectionLimits::default();

        // Оценка соединений (0-10 → 0-1)
        let conn_score = (self.connections as f64 / 10.0).min(1.0);

        // Оценка разнообразия подсетей
        let ng_score = (self.netgroups as f64 / limits.min_netgroups as f64).min(1.0);

        // Оценка задержки (500мс = плохо, 50мс = хорошо)
        let latency_score = if self.avg_latency_ms == 0 {
            0.5
        } else {
            (500.0 / self.avg_latency_ms as f64).min(1.0)
        };

        // Средняя оценка
        (conn_score + ng_score + latency_score) / 3.0
    }

    /// Сеть здорова?
    pub fn is_healthy(&self) -> bool {
        self.score() > 0.6
    }
}

/// Типы P2P сообщений
#[derive(Clone, Debug)]
pub enum P2PMessage {
    /// Рукопожатие
    Version {
        version: u32,
        services: u64,
        timestamp: u64,
        nonce: u64,
    },

    /// Подпись присутствия
    Presence(PresenceProof),

    /// Адреса узлов
    Addr(Vec<NetAddr>),

    /// Запрос адресов
    GetAddr,

    /// Ping
    Ping(u64),

    /// Pong
    Pong(u64),
}

impl P2PMessage {
    /// Получить тип сообщения
    pub fn message_type(&self) -> &'static str {
        match self {
            Self::Version { .. } => "VERSION",
            Self::Presence(_) => "PRESENCE",
            Self::Addr(_) => "ADDR",
            Self::GetAddr => "GETADDR",
            Self::Ping(_) => "PING",
            Self::Pong(_) => "PONG",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::Ipv4Addr;

    #[test]
    fn test_netaddr_routable() {
        let public = NetAddr::new(IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8)), 8333);
        let private = NetAddr::new(IpAddr::V4(Ipv4Addr::new(192, 168, 1, 1)), 8333);
        let localhost = NetAddr::new(IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1)), 8333);

        assert!(public.is_routable());
        assert!(!private.is_routable());
        assert!(!localhost.is_routable());
    }

    #[test]
    fn test_addr_manager() {
        let mut mgr = AddrManager::new();
        let source = NetAddr::new(IpAddr::V4(Ipv4Addr::new(1, 1, 1, 1)), 8333);
        let addr = NetAddr::new(IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8)), 8333);

        assert!(mgr.add_new(addr.clone(), &source));

        let (new_count, _) = mgr.count();
        assert_eq!(new_count, 1);
    }

    #[test]
    fn test_network_health() {
        let health = NetworkHealth {
            connections: 10,
            netgroups: 5,
            avg_latency_ms: 100,
            signatures_per_tau2: 1000,
        };

        assert!(health.is_healthy());
        assert!(health.score() > 0.6);
    }
}
