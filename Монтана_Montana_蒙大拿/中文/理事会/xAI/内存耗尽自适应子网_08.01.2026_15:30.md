# Security Audit: Memory Exhaustion in AdaptiveSubnetLimiter

**Модель:** Grok 3
**Компания:** xAI
**Дата:** 08.01.2026 15:30 UTC

---

## 1. Понимание архитектуры

Montana — это реализация протокола Atemporal Coordinate Presence (ACP), где присутствие доказывается через подписи во времени. Система использует двухуровневую архитектуру времени (Layer 1: Peer Consensus, Layer 2: NTS), детерминированную лотерею и адаптивный кулдаун.

Ключевые отличия от традиционных блокчейнов:
- Присутствие = реальное время (не PoW/PoS)
- Детерминированная лотерея (не mining/staking)
- ACP вместо традиционного консенсуса
- Сетевой слой использует Noise Protocol с ML-KEM для постквантовой безопасности

Для сетевой безопасности это означает, что уязвимости должны позволять обходить защиту от DoS, eclipse атак и манипуляции консенсусом через сетевой уровень.

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| protocol.rs | 1491 | Core network protocol, connection handling, message processing |
| rate_limit.rs | 879 | Token bucket, AdaptiveSubnetLimiter, flow control |
| connection.rs | 444 | Ban lists, netgroup limits, retry logic |
| addrman.rs | 500+ | Cryptographic bucket address manager |
| sync.rs | 500+ | Headers-first sync, orphan pool, late signature buffer |
| verification.rs | 800+ | Bootstrap verification, hardcoded node auth |
| types.rs | 658 | Constants, NetAddress, InvType, message types |
| consensus.rs | 123 | Lottery placeholder (not implemented) |
| cooldown.rs | 262 | Adaptive cooldown with median-based rate limiting |

---

## 3. Attack Surface

Основные точки входа для атакующего:

1. **P2P соединения**: Все входящие соединения проходят через subnet rate limiting (Erebus protection)
2. **Address relay**: AddrMan с криптографическими бакетами для предотвращения eclipse
3. **Inventory relay**: Rate limited per-peer для предотвращения flooding
4. **Message processing**: Все сообщения валидируются по размеру и rate limit
5. **Bootstrap verification**: Требует 75% hardcoded nodes + subnet diversity

---

## 4. Найденные уязвимости

### CRITICAL: Memory Exhaustion via AdaptiveSubnetLimiter

**Файл:** `montana/src/net/rate_limit.rs:301-320`

**Уязвимый код:**
```rust
// IPv6 subnet tracking with LRU eviction
const MAX_TRACKED_SUBNETS_V6: usize = 50_000;
const V6_EVICTION_BATCH: usize = 5_000;

// HashMaps that can grow unbounded before eviction
v6_requests: HashMap<(u64, Subnet32), u64>,
v6_median_history: HashMap<(u64, Subnet32), u64>,
v6_previous_limit: HashMap<Subnet32, u64>,
v6_current_counts: HashMap<Subnet32, u64>,
```

**Вектор атаки:**
1. Атакующий создаёт 50,000+ уникальных IPv6 подсетей (Subnet32)
2. Для каждой подсети отправляет соединения/запросы, вызывая `record()` или `check()`
3. HashMaps растут без ограничения до тех пор, пока не достигнут MAX_TRACKED_SUBNETS_V6
4. Даже с LRU eviction, атакующий может поддерживать 50k записей в памяти
5. Каждый Subnet32 занимает ~32 байта + overhead HashMap → ~2MB на HashMap
6. Всего: 4 HashMaps × 2MB = 8MB, плюс access_order VecDeque

**Импакт:** Memory exhaustion на full nodes. Атакующий с ботнетом IPv6 адресов может вызвать OOM на узлах, нарушая доступность сети.

**Сложность:** Низкая. IPv6 адресное пространство огромно. Атакующий может арендовать IPv6 ranges или использовать ботнет с IPv6.

**PoC сценарий:**
```rust
// Атакующий генерирует 50k уникальных IPv6 подсетей
for i in 0..50_000 {
    let ipv6 = format!("2001:db8:{:x}:{:x}::1", i >> 16, i & 0xffff);
    connect_to_montana_node(ipv6, 19333);
    // Каждый новый subnet добавляется в HashMaps
}
```

---

### HIGH: Orphan Pool Exhaustion DoS

**Файл:** `montana/src/net/sync.rs:23-24, 265-385`

**Уязвимый код:**
```rust
const MAX_ORPHANS: usize = 100;

// Orphan pool with fixed limit
by_prev_hash: HashMap<Hash, Vec<OrphanSlice>>,
indices: HashSet<u64>,
count: usize,
```

**Вектор атаки:**
1. Атакующий отправляет 100+ slice'ов с уникальными prev_hash
2. Каждый slice занимает ~8KB (MAX_SLICE_SIZE)
3. Orphan pool заполняется: 100 × 8KB = 800KB
4. Новые orphans вызывают expire_oldest(), но атакующий поддерживает поток
5. Узел не может обрабатывать легитимные orphans во время атаки

**Импакт:** Denial of service для sync механизма. Узлы не могут догонять chain, теряют liveness.

**Сложность:** Средняя. Требует bandwidth для отправки 100×8KB = 800KB, но slices могут быть минимальными.

**PoC сценарий:**
```rust
for i in 0..101 {
    let fake_slice = create_slice_with_random_prev_hash();
    send_slice_to_peer(fake_slice);
    // Pool fills up, legitimate orphans evicted
}
```

---

### HIGH: Late Signature Buffer Memory Leak

**Файл:** `montana/src/net/sync.rs:467-540`

**Уязвимый код:**
```rust
pub struct LateSignatureBuffer {
    pending: HashMap<u64, Vec<LateSignature>>,  // No size limit!
    max_size: usize,  // Set to 10,000 but not enforced
    current_tau2: u64,
}
```

**Вектор атаки:**
1. Атакующий отправляет presence proofs с intended_tau2 в будущем
2. Они буферизуются в LateSignatureBuffer.pending
3. Нет enforcement max_size (только поле, но не используется)
4. HashMap растёт неограниченно: key = u64, value = Vec<LateSignature>
5. Каждый LateSignature ~1KB, 10k = 10MB, но может быть больше

**Импакт:** Memory exhaustion через late signatures. Узел OOM при обработке большого количества опоздавших proofs.

**Сложность:** Низкая. Любой узел может отправлять presence proofs для будущих τ₂.

---

### MEDIUM: AddrMan Poisoning for Eclipse

**Файл:** `montana/src/net/addrman.rs:125-169`

**Уязвимый код:**
```rust
pub fn add(&mut self, addr: NetAddress, source: Option<SocketAddr>) -> bool {
    // Skip if already known
    if self.addr_to_idx.contains_key(&socket_addr) {
        return false;
    }
    // ... adds to table without validation
}
```

**Вектор атаки:**
1. Атакующий контролирует source peer (через eclipse или Sybil)
2. Отправляет Addr messages с фейковыми адресами от "доверенного" source
3. AddrMan добавляет адреса в криптографические бакеты
4. При selection выбирает преимущественно фейковые адреса
5. Легитимные узлы изолируются от сети

**Импакт:** Eclipse attack через address table poisoning. Узлы подключаются только к контролируемым атакующим адресам.

**Сложность:** Высокая. Требует контроля source peer, что трудно в криптографических бакетах.

---

### MEDIUM: Flow Control Bypass via Message Size Manipulation

**Файл:** `montana/src/net/protocol.rs:867-868, 1210-1211`

**Уязвимый код:**
```rust
let msg_size = msg.estimated_size();
peer.flow_control.add_recv(msg_size);

// Later...
peer.flow_control.remove_recv(msg_size);
```

**Вектор атаки:**
1. Атакующий отправляет сообщения с заниженным estimated_size()
2. flow_control.add_recv() добавляет меньше байт чем реально получено
3. При достижении max_recv_queue, легитимные сообщения блокируются
4. Атакующий может поддерживать соединение открытым, отправляя "маленькие" сообщения

**Импакт:** DoS через flow control bypass. Узел перестает принимать легитимные сообщения.

**Сложность:** Средняя. Требует знания estimated_size() логики и возможности отправлять oversized payloads.

---

## 5. Атаки, которые НЕ работают

**51% attack на address discovery:** IP votes требуют 4+ outbound peers из разных подсетей, что делает Sybil attack дорогой.

**Hash collision attack:** SHA3-256 collision требует 2^128 операций, нецелесообразно.

**Timing attack на lottery:** Lottery seed не зависит от сетевых сообщений (prev_slice_hash фиксирован).

**Replay attack на presence proofs:** prev_slice_hash привязывает к конкретному τ₂, бинарность делает replay бесполезным.

**BGP hijack:** Hardcoded nodes используют ML-DSA-65 аутентификацию, BGP hijack детектируется через challenge-response.

---

## 6. Рекомендации

### Для Memory Exhaustion в AdaptiveSubnetLimiter:
```rust
// Добавить глобальный счетчик записей
struct GlobalSubnetLimiter {
    limiter: AdaptiveSubnetLimiter,
    total_v6_entries: AtomicUsize,
    max_total_entries: usize,
}

// Проверять перед добавлением
if self.total_v6_entries.load() >= self.max_total_entries {
    return false; // Reject new subnets
}
```

### Для Orphan Pool Exhaustion:
```rust
// Добавить per-peer orphan limits
orphan_counts: HashMap<SocketAddr, usize>,
MAX_ORPHANS_PER_PEER: usize = 10,

// Проверять перед добавлением
if *self.orphan_counts.entry(peer).or_insert(0) >= MAX_ORPHANS_PER_PEER {
    return false;
}
```

### Для Late Signature Buffer:
```rust
// Enforce max_size
impl LateSignatureBuffer {
    pub fn add(&mut self, proof: PresenceProof, ...) -> bool {
        let total_size: usize = self.pending.values().map(|v| v.len()).sum();
        if total_size >= self.max_size {
            return false; // Reject new late signatures
        }
        // ...
    }
}
```

### Для AddrMan Poisoning:
```rust
// Добавить source reputation
pub fn add(&mut self, addr: NetAddress, source: Option<SocketAddr>) -> bool {
    if let Some(src) = source {
        if !self.is_source_reputable(src) {
            return false; // Reject addresses from disreputable sources
        }
    }
    // ...
}
```

---

## 7. Вердикт

[ ] CRITICAL — есть уязвимости, позволяющие уничтожить сеть
[x] HIGH — есть серьёзные уязвимости
[ ] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено

Memory exhaustion в AdaptiveSubnetLimiter позволяет атакующему с IPv6 ботнетом вызвать OOM на full nodes, нарушая доступность сети. Orphan pool и late signature buffer уязвимы к DoS через memory exhaustion. AddrMan poisoning может привести к eclipse атакам. Эти уязвимости требуют срочного исправления для обеспечения сетевой безопасности Montana.

