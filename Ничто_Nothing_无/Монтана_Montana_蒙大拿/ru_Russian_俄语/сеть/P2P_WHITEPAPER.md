# P2P Сеть Montana — Присутствие через связь

**Версия:** 1.0
**Дата:** Январь 2026
**Язык:** Русский (эксклюзивный)

---

## Определение

P2P-сеть Montana — слой связи между узлами, обеспечивающий:
1. Распространение подписей присутствия
2. Аттестацию временных координат
3. Защиту от изоляции (Eclipse)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     P2P СЕТЬ MONTANA                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐              │
│   │Full Node│────▶│Full Node│────▶│Full Node│              │
│   └────┬────┘     └────┬────┘     └────┬────┘              │
│        │               │               │                    │
│        ▼               ▼               ▼                    │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐              │
│   │Light    │     │Light    │     │Light    │              │
│   │Node     │     │Node     │     │Client   │              │
│   └─────────┘     └─────────┘     └─────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Типы узлов

| Тип | Функции | Хранение |
|-----|---------|----------|
| **Full Node** | Полная валидация, хранение истории | Полный таймчейн |
| **Light Node** | Валидация заголовков, ретрансляция | Заголовки + чекпоинты |
| **Light Client** | Отправка подписей, получение результатов | Только свои данные |

---

## Ограничения соединений

```rust
/// Лимиты соединений (комментарии на русском)
pub struct ConnectionLimits {
    /// Максимум входящих соединений
    /// Защита от перегрузки ресурсов
    pub max_inbound: usize,      // 117

    /// Максимум исходящих соединений
    /// Обеспечивает связность без избыточности
    pub max_outbound: usize,     // 11

    /// Максимум соединений на подсеть /16
    /// Защита от Eclipse через разнообразие
    pub max_per_netgroup: usize, // 2

    /// Минимум различных подсетей
    /// Гарантия географического распределения
    pub min_netgroups: usize,    // 4
}

impl Default for ConnectionLimits {
    fn default() -> Self {
        Self {
            max_inbound: 117,
            max_outbound: 11,
            max_per_netgroup: 2,
            min_netgroups: 4,
        }
    }
}
```

---

## Защита от Eclipse

Eclipse-атака — изоляция узла от честной сети.

### Стратегия защиты

```rust
/// Менеджер адресов с защитой от Eclipse
pub struct AddrManager {
    /// Новые адреса (непроверенные)
    /// 1024 бакета × 64 адреса = 65,536 макс
    new_table: BucketTable<1024, 64>,

    /// Проверенные адреса (успешно подключались)
    /// 256 бакетов × 64 адреса = 16,384 макс
    tried_table: BucketTable<256, 64>,

    /// Криптографический ключ для бакетирования
    /// Уникален для каждого узла — атакующий не знает схему
    bucket_key: [u8; 32],
}

impl AddrManager {
    /// Выбор адреса для подключения
    /// Приоритет: разнообразие подсетей > количество
    pub fn select_for_connection(&self) -> Option<NetAddr> {
        // 1. Проверить текущее разнообразие подсетей
        let current_netgroups = self.count_connected_netgroups();

        // 2. Если мало подсетей — приоритет новым подсетям
        if current_netgroups < MIN_NETGROUPS {
            return self.select_from_new_netgroup();
        }

        // 3. Иначе — баланс tried/new (50/50)
        if random() < 0.5 {
            self.select_from_tried()
        } else {
            self.select_from_new()
        }
    }
}
```

### Криптографическое бакетирование

```rust
/// Вычисление бакета для адреса
/// Атакующий не может предсказать размещение
fn calculate_bucket(
    addr: &NetAddr,
    bucket_key: &[u8; 32],
    source: &NetAddr,
) -> usize {
    // Входные данные для хеша
    let mut hasher = Sha3_256::new();
    hasher.update(bucket_key);           // Секретный ключ узла
    hasher.update(&addr.group_key());    // Группа адреса (/16)
    hasher.update(&source.group_key());  // Источник информации

    // Результат: номер бакета
    let hash = hasher.finalize();
    u64::from_le_bytes(hash[0..8].try_into().unwrap()) as usize
}
```

---

## Протокол обмена адресами

### Защита от AddrMan Poisoning

```rust
/// Обработка полученных адресов
pub fn process_addr_message(
    &mut self,
    addrs: Vec<NetAddr>,
    source: PeerId,
) -> Result<(), AddrError> {
    // 1. Лимит адресов в сообщении
    if addrs.len() > MAX_ADDR_PER_MSG {
        return Err(AddrError::TooManyAddresses);
    }

    // 2. Rate limiting: 0.1 адреса в секунду после burst
    if !self.rate_limiter.check(source) {
        return Err(AddrError::RateLimited);
    }

    for addr in addrs {
        // 3. Фильтрация нероутабельных
        if !addr.is_routable() {
            continue;
        }

        // 4. Проверка временной метки
        let now = current_time();
        if addr.timestamp > now + 600 {
            // Отклонить будущие метки (Time-Travel Poisoning)
            continue;
        }
        if addr.timestamp < now - 10 * 24 * 3600 {
            // Игнорировать старые адреса
            continue;
        }

        // 5. Добавить в new_table
        self.add_to_new(addr, source)?;
    }

    Ok(())
}
```

---

## Распространение подписей

```rust
/// Протокол распространения подписей присутствия
pub struct SignatureGossip {
    /// Очередь подписей для отправки
    outbound_queue: VecDeque<PresenceProof>,

    /// Фильтр дубликатов (Bloom filter)
    seen_filter: BloomFilter,

    /// Статистика по пирам
    peer_stats: HashMap<PeerId, PeerStats>,
}

impl SignatureGossip {
    /// Обработка входящей подписи
    pub fn on_signature(&mut self, sig: PresenceProof, from: PeerId) {
        // 1. Проверка на дубликат
        let sig_hash = sig.hash();
        if self.seen_filter.contains(&sig_hash) {
            return;
        }
        self.seen_filter.insert(&sig_hash);

        // 2. Валидация подписи
        if !sig.verify(current_tau2()) {
            self.peer_stats.get_mut(&from).map(|s| s.invalid_count += 1);
            return;
        }

        // 3. Добавить в локальный пул
        self.local_pool.add(sig.clone());

        // 4. Переслать пирам (кроме источника)
        for peer in self.connected_peers() {
            if peer != from {
                self.send_to(peer, sig.clone());
            }
        }
    }
}
```

---

## Типы сообщений

| Сообщение | Размер | Назначение |
|-----------|--------|------------|
| `VERSION` | ~100 B | Рукопожатие |
| `PRESENCE` | 3309 B | Подпись присутствия |
| `ADDR` | var | Адреса узлов |
| `GETADDR` | 1 B | Запрос адресов |
| `SLICE` | ~50 KB | Заголовок слайса |
| `GETSLICE` | 8 B | Запрос слайса |
| `TX` | var | Транзакция |
| `PING/PONG` | 8 B | Проверка связи |

---

## Сериализация

```rust
/// Безопасная сериализация с лимитами
/// Защита от OOM через ограничение размера
pub trait SafeSerialize {
    /// Максимальный размер сериализованных данных
    const MAX_SIZE: usize;

    /// Сериализация с проверкой размера
    fn serialize(&self, buf: &mut Vec<u8>) -> Result<(), SerError>;

    /// Десериализация с лимитом
    fn deserialize(buf: &[u8]) -> Result<Self, DeserError>
    where
        Self: Sized;
}

/// Пример: адрес узла
impl SafeSerialize for NetAddr {
    const MAX_SIZE: usize = 30; // IP + port + timestamp + services

    fn deserialize(buf: &[u8]) -> Result<Self, DeserError> {
        if buf.len() > Self::MAX_SIZE {
            return Err(DeserError::TooLarge);
        }
        // ... десериализация
    }
}
```

---

## Метрики здоровья сети

```rust
/// Мониторинг состояния P2P слоя
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
        let conn_score = (self.connections as f64 / 10.0).min(1.0);
        let ng_score = (self.netgroups as f64 / MIN_NETGROUPS as f64).min(1.0);
        let latency_score = (500.0 / self.avg_latency_ms as f64).min(1.0);

        (conn_score + ng_score + latency_score) / 3.0
    }
}
```

---

## Заключение

P2P-сеть Montana обеспечивает:
- **Связность:** Каждый узел достижим
- **Разнообразие:** Защита от изоляции
- **Эффективность:** Минимальный трафик
- **Безопасность:** Криптографическое бакетирование

Сеть — не просто транспорт. Сеть — часть доказательства присутствия.

---

*Alejandro Montana*
*github.com/afgrouptime*
*x.com/tojesatoshi*
