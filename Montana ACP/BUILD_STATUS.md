# Статус сборки Montana ACP

## Порядок сборки и текущий статус

### ✅ 1. Сеть: соединения, gossip, распространение сообщений
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `net/mod.rs` — основной модуль сети
- `net/protocol.rs` — протокол P2P
- `net/connection.rs` — управление соединениями
- `net/message.rs` — типы сообщений
- `net/gossip.rs` — распространение сообщений
- `net/encrypted.rs` — шифрование (Noise XX + ML-KEM-768)
- `net/addrman.rs` — управление адресами
- `net/peer_selector.rs` — выбор пиров
- `net/rate_limit.rs` — ограничение скорости
- `net/subnet.rs` — защита от Sybil по подсетям
- `net/sync.rs` — синхронизация блокчейна
- `net/bootstrap.rs` — начальная загрузка
- `net/verification.rs` — верификация пиров
- `net/hardcoded_identity.rs` — hardcoded nodes

**Файлы:** `montana/src/net/*.rs`

---

### ✅ 2. Структуры данных: слайс, микроблок, подпись присутствия, транзакция
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `Slice` — основной блок (слайс)
- `SliceHeader` — заголовок слайса
- `PresenceProof` — доказательство присутствия
- `Transaction` — транзакция
- `TxInput` / `TxOutput` — входы и выходы транзакций
- `NodeWeight` — вес узла
- `Utxo` — непотраченный выход

**Файлы:** `montana/src/types.rs`

**Ключевые структуры:**
```rust
pub struct Slice {
    pub header: SliceHeader,
    pub presence_root: Hash,
    pub tx_root: Hash,
    pub signature: Signature,
    pub presences: Vec<PresenceProof>,
    pub transactions: Vec<Transaction>,
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

### ✅ 3. Присутствие: подписание координат, сбор в presence_root
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `FullNodePresence` — автоматическое присутствие Full Node каждые τ₁ (1 минута)
- `VerifiedUserPresence` — присутствие Verified User с биометрией FIDO2
- `PresenceProof` — унифицированное доказательство присутствия
- `Slice::compute_presence_root()` — вычисление Merkle root присутствий
- Верификация подписей присутствия
- Проверка временных меток и cooldown

**Файлы:** 
- `montana/src/consensus.rs` (FullNodePresence, VerifiedUserPresence)
- `montana/src/types.rs` (PresenceProof)

**Особенности:**
- Full Node: автоматическое подписание каждые 60 секунд
- Verified User: случайный интервал 10-40 минут, требует биометрию
- Сбор в `presence_root` через Merkle tree

---

### ✅ 4. Консенсус: комитет, голосование, финальность
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `FinalityTracker` — трекинг финальности слайсов
- `FinalityStatus` — статус финальности (INSTANT/SAFE/FINAL)
- `SliceAttestation` — голосование за слайс
- `FinalityCheckpoint` — чекпоинты каждые τ₃
- `ForkChoice` — выбор канонической цепи
- Защита от long-range attacks
- Защита от nothing-at-stake

**Файлы:**
- `montana/src/finality.rs` — финальность
- `montana/src/fork_choice.rs` — выбор форка
- `montana/src/consensus.rs` — основной консенсус

**Уровни финальности:**
- INSTANT (0 слайсов) — может быть реорганизован
- SAFE (6 слайсов = 60 минут) — реорганизация требует 6x веса
- FINAL (2016 слайсов = 14 дней) — реорганизация невозможна

---

### ✅ 5. Лотерея: выбор победителя τ₂, награды
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `Lottery` — детерминированная лотерея
- `LotteryParticipant` — участник лотереи
- `LotteryResult` — результат лотереи
- `LotteryWinner` — победитель лотереи
- Двухэтапный отбор (tier-based, затем weighted)
- Защита от grinding (seed = SHA3-256(prev_hash || τ₂_index))
- 80% Full Node / 20% Verified User caps
- 10 backup slots (SLOTS_PER_TAU2)

**Файлы:** `montana/src/consensus.rs`

**Механика:**
```rust
seed = SHA3-256(prev_slice_hash || τ₂_index)
Stage 1: Выбор tier (80% Full Node / 20% Verified User)
Stage 2: Weighted selection внутри tier
```

**Награды:**
- `calculate_reward(slice_index)` — расчет награды с halving
- `REWARD_PER_TAU2 = 3000`
- `HALVING_INTERVAL = 210_000` слайсов (~4 года)

---

### ✅ 6. Экономика: тиры, кулдаун, халвинг
**Статус:** ЗАВЕРШЕНО

**Реализовано:**
- `AdaptiveCooldown` — адаптивный кулдаун на основе медианы
- Тиры веса: TIER1_WEIGHT, TIER2_WEIGHT, TIER3_WEIGHT, TIER4_WEIGHT
- Медианный расчет кулдауна по окну τ₃ (14 дней)
- Сглаживание по 4 τ₃ (56 дней)
- Ограничение изменения кулдауна (20% за τ₃)
- Халвинг награды каждые 210,000 слайсов

**Файлы:**
- `montana/src/cooldown.rs` — адаптивный кулдаун
- `montana/src/types.rs` — константы экономики

**Параметры кулдауна:**
- Минимум: 144 τ₂ (1 день)
- Максимум: 25,920 τ₂ (180 дней)
- Окно медианы: 2,016 τ₂ (14 дней)
- Сглаживание: 4 окна (56 дней)

**Халвинг:**
- Начальная награда: 3000 за τ₂
- Интервал: 210,000 слайсов (~4 года)
- Максимум 64 халвинга (после этого награда = 0)

---

## Итоговый статус

### ✅ Все компоненты реализованы

**Модули:**
- ✅ `net/` — сеть (полная реализация)
- ✅ `types.rs` — структуры данных
- ✅ `consensus.rs` — присутствие и лотерея
- ✅ `finality.rs` — финальность
- ✅ `fork_choice.rs` — выбор форка
- ✅ `cooldown.rs` — адаптивный кулдаун
- ✅ `crypto.rs` — криптография (SHA3-256, ML-DSA-65)
- ✅ `db.rs` — хранилище (sled)
- ✅ `merkle.rs` — Merkle proofs для light clients

**Следующие шаги:**
1. Интеграция всех модулей в `engine.rs` (Фаза 2)
2. Тестирование end-to-end
3. Оптимизация производительности
4. Аудит безопасности

---

## Статистика кодовой базы

- **Rust файлов:** 40
- **Строк кода:** 18,814
- **Тестов:** 112+
- **Модулей:** 10+
- **Документация:** Полная

**Распределение по модулям:**
- `net/` — ~8,000 строк (сеть)
- `consensus.rs` — ~1,000 строк (консенсус, присутствие, лотерея)
- `types.rs` — ~500 строк (структуры данных)
- `finality.rs` — ~550 строк (финальность)
- `fork_choice.rs` — ~400 строк (выбор форка)
- `cooldown.rs` — ~250 строк (кулдаун)
- `merkle.rs` — ~400 строк (Merkle proofs)
- `crypto.rs` — ~150 строк (криптография)
- `db.rs` — ~220 строк (хранилище)
- Остальные модули — ~7,000 строк

---

*Последнее обновление: 2026-01-09*

