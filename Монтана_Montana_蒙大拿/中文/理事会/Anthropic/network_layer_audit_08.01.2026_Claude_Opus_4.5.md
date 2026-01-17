# Security Audit: Montana Network Layer

**Модель:** Claude Opus 4.5
**Компания:** Anthropic
**Дата:** 08.01.2026 UTC

---

## 1. Понимание архитектуры

Montana — это **Atemporal Coordinate Presence (ACP)**, принципиально отличная от традиционных блокчейнов модель:

- **Нет майнеров/валидаторов** — узлы подтверждают присутствие через VDF-based heartbeat
- **Слайсы вместо блоков** — временные срезы (τ₂ = 10 минут) группируют presence proofs
- **Fork choice через время** — кумулятивный вес определяется физическим временем (VDF), а не hash power или stake
- **Физические инварианты** — скорость света и VDF обеспечивают невозможность подделки времени

**Следствия для безопасности сетевого слоя:**
1. Нет экономической атаки на консенсус через сеть (нет mining/staking)
2. Eclipse атака даёт временную изоляцию, но не позволяет украсть средства
3. Hardcoded nodes с ML-DSA-65 обеспечивают криптографическую привязку к источнику истины

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| protocol.rs | ~1500 | Network struct, message handling, encryption |
| types.rs | ~660 | Constants, NetAddress, VersionPayload, limits |
| message.rs | ~400 | Message enum, validate_collection_sizes() |
| peer.rs | ~300 | Peer state, rate limits, flow control |
| addrman.rs | ~600 | Address manager, NEW/TRIED tables |
| connection.rs | ~400 | ConnectionManager, bans, netgroup limits |
| noise.rs | ~500 | Noise XX + ML-KEM-768 hybrid encryption |
| encrypted.rs | ~400 | EncryptedStream with chunking |
| hardcoded_identity.rs | ~200 | ML-DSA-65 authentication for bootstrap nodes |
| bootstrap.rs | ~700 | BootstrapVerifier, Trusted Core model |
| verification.rs | ~850 | VerificationClient, pre-network verification |
| subnet.rs | ~450 | SubnetTracker, reputation, diversity |
| rate_limit.rs | ~300 | TokenBucket, GlobalSubnetLimiter |
| sync.rs | ~670 | SliceDownloader, OrphanPool, HeaderSync |
| eviction.rs | ~200 | Peer eviction logic |
| discouraged.rs | ~290 | Rolling bloom filter |
| feeler.rs | ~260 | Feeler connections, AddrResponseCache |
| dns.rs | ~270 | DNS seeds, fallback IPs |
| serde_safe.rs | ~200 | Bounded deserialization |
| inventory.rs | ~200 | Inventory relay cache |
| startup.rs | ~100 | Network initialization |

**Всего:** ~8,400 LOC сетевого слоя

---

## 3. Attack Surface

### 3.1 External Inputs
- TCP connections (inbound/outbound)
- Protocol messages (Version, Addr, Inv, GetData, Slice, Tx, Presence, etc.)
- DNS resolution

### 3.2 Trust Boundaries
- **Hardcoded nodes** — trusted via ML-DSA-65 signatures
- **Outbound peers** — partial trust (we selected them, but data untrusted)
- **Inbound peers** — untrusted (may be Sybil attackers)
- **P2P messages** — always validate before use

### 3.3 Critical Assets
- Chain state (slices, transactions)
- Private keys (Noise keypair, presence signing key)
- External IP discovery
- Address manager state

---

## 4. Найденные уязвимости

### [MEDIUM] Single Point of Failure — только один hardcoded узел

**Файл:** `hardcoded_identity.rs:41-55`, `dns.rs:25-32`

**Уязвимый код:**
```rust
pub static MAINNET_HARDCODED: LazyLock<Vec<HardcodedNode>> = LazyLock::new(|| {
    vec![
        // TimeWeb Primary (Moscow)
        HardcodedNode {
            addr: SocketAddr::new(IpAddr::V4(Ipv4Addr::new(176, 124, 208, 93)), 19333),
            pubkey: TIMEWEB_MOSCOW_PUBKEY,
            name: "timeweb-moscow",
        },
    ]
});
```

**Вектор атаки:**
1. Атакующий получает контроль над 176.124.208.93 (DDoS, BGP hijack, компрометация хостинга)
2. Новые узлы не могут пройти bootstrap verification
3. Сеть теряет способность к росту

**Импакт:** Denial of Service для новых узлов. Существующие узлы продолжают работать.

**Сложность:** Средняя. Требует либо DDoS мощностью >10 Gbps, либо BGP hijack, либо компрометацию TimeWeb.

**Рекомендация:** Добавить минимум 5-10 hardcoded узлов в разных регионах и у разных провайдеров. Рекомендуемое распределение:
- 2-3 узла в Европе (разные страны)
- 2-3 узла в Азии
- 2-3 узла в Северной Америке
- 1-2 узла в Южной Америке

---

### [LOW] DNS Seeds пусты

**Файл:** `dns.rs:9-21`

**Код:**
```rust
pub const DNS_SEEDS: &[&str] = &[
    // Primary seeds (to be populated with actual domains)
    // "seed1.montana.network",
    // ...
];
```

**Импакт:** DNS seeding не работает. Всё bootstrap зависит от hardcoded IPs.

**Рекомендация:** Настроить DNS seeds до mainnet launch.

---

## 5. Атаки, которые НЕ работают

### 5.1 Memory Exhaustion (OOM)

**Попытка:** Отправить сообщение с огромным length prefix.

**Защита:** protocol.rs:1261-1263 проверяет размер ДО чтения:
```rust
if len > MAX_TX_SIZE {
    return Err(NetError::MessageTooLarge(len, MAX_TX_SIZE));
}
```
**Результат:** ✗ PROTECTED

### 5.2 Collection Size DoS

**Попытка:** Отправить Addr с миллионом адресов.

**Защита:** message.rs:validate_collection_sizes() + rate limiting:
```rust
pub fn validate_collection_sizes(&self) -> bool {
    match self {
        Message::Addr(addrs) => addrs.len() <= MAX_ADDR_COUNT,
        Message::Inv(items) => items.len() <= MAX_INV_COUNT,
        // ...
    }
}
```
**Результат:** ✗ PROTECTED

### 5.3 Self-Connection Attack

**Попытка:** Заставить узел подключиться к себе через NAT.

**Защита:** protocol.rs:877-882 детектирует через nonce:
```rust
if sent_nonces.read().await.contains(&version.nonce) {
    warn!("Self-connection detected (nonce match), disconnecting {}", peer.addr);
    return Err(NetError::Protocol("Self-connection detected".into()));
}
```
**Результат:** ✗ PROTECTED

### 5.4 Slowloris DoS

**Попытка:** Держать множество connections в handshake состоянии.

**Защита:**
- HANDSHAKE_TIMEOUT_SECS = 60
- MAX_INBOUND = 117
- Flow control с MAX_FLOW_CONTROL_PAUSES = 50

**Результат:** ✗ PROTECTED

### 5.5 External IP Spoofing

**Попытка:** Inbound Sybil peers голосуют за фейковый external IP.

**Защита:** protocol.rs:884-915 — только outbound peers голосуют:
```rust
if !peer.inbound && !their_view_of_us.is_loopback() ...
```
MIN_IP_VOTES = 4 (увеличено после предыдущего аудита).

**Результат:** ✗ PROTECTED

### 5.6 Erebus Attack (Subnet Takeover)

**Попытка:** Постепенно заполнить connections peers из одной /16 подсети.

**Защита:**
- MAX_PEERS_PER_NETGROUP = 2
- GlobalSubnetLimiter с двухуровневым rate limiting
- MIN_DIVERSE_SUBNETS = 25 при bootstrap

**Результат:** ✗ PROTECTED

### 5.7 AddrMan Poisoning

**Попытка:** Заполнить address manager фейковыми адресами.

**Защита:**
- Bounded buckets: MAX_NEW_BUCKETS × MAX_NEW_BUCKET_SIZE = 65,536
- Rate limiting: ADDR_RATE = 0.1/sec
- Cryptographic bucketing prevents targeted bucket filling

**Результат:** ✗ PROTECTED

### 5.8 MITM on Hardcoded Nodes

**Попытка:** BGP hijack для перехвата трафика к hardcoded node.

**Защита:**
- Noise XX encryption prevents reading traffic
- ML-DSA-65 challenge-response authentication prevents impersonation
- Атакующий может только DoS, не может подделать identity

**Результат:** ✗ PROTECTED (downgraded to DoS only)

### 5.9 Postcard Deserialization OOM

**Попытка:** VarInt указывает на огромный Vec внутри payload.

**Защита:**
- Payload size checked before read (MAX_TX_SIZE = 1MB)
- postcard VarInt encoding: large values require many bytes
- validate_collection_sizes() after deserialization

**Результат:** ✗ PROTECTED

### 5.10 Cloud Provider Eclipse (25+ subnets)

**Попытка:** Развернуть 100+ узлов в 25+ уникальных /16 подсетях через AWS/GCP/Azure.

**Защита:**
- Hardcoded nodes с ML-DSA-65 определяют истину
- P2P peers только дают warnings, не могут override hardcoded consensus
- Trusted Core model: `verify_hardcoded_consensus()` требует agreement между hardcoded nodes

**Результат:** ✗ PROTECTED (requires compromising hardcoded nodes)

---

## 6. Рекомендации

### Критически важно (до mainnet):
1. **Добавить 5-10 hardcoded узлов** в разных регионах и у разных провайдеров

### Желательно:
2. Настроить DNS seeds (seed1.montana.network, etc.)
3. Рассмотреть Tor/I2P support для цензуроустойчивости

---

## 7. Вердикт

| Критичность | Количество |
|-------------|------------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |
| INFO | 0 |

**[x] MEDIUM — есть уязвимости среднего риска**

Сетевой слой Montana демонстрирует высокое качество security engineering:

1. **Explicit memory budgets** — все коллекции ограничены, документация содержит worst-case расчёты
2. **Defense in depth** — multiple layers of protection (size checks, rate limits, collection validation)
3. **Trusted Core model** — hardcoded nodes с криптографической аутентификацией
4. **Good practices** — saturating arithmetic, nonce-based self-detection, outbound-only IP votes

Единственная существенная проблема — **single point of failure** с единственным hardcoded узлом. Это легко исправляется добавлением дополнительных узлов.

---

## Приложение: Checklist Verification

| Категория | Статус | Доказательство |
|-----------|--------|----------------|
| Memory DoS | ✓ Protected | MAX_TX_SIZE, bounded collections |
| CPU DoS | ✓ Protected | Rate limiting (TokenBucket) |
| Disk DoS | ✓ Protected | MAX_ORPHANS = 100 |
| Network DoS | ✓ Protected | Connection limits, flow control |
| Unbounded collections | ✓ Protected | Explicit limits everywhere |
| Deserialize OOM | ✓ Protected | Size check before read |
| Integer overflow | ✓ Protected | saturating_add/sub |
| Trust boundary | ✓ Protected | Trusted Core model |
| Self-reference | ✓ Protected | Nonce detection |
| Replay | ✓ Protected | Challenge-response, nonces |
| Race condition | ✓ Protected | Arc<RwLock<>> usage |
| Crypto misuse | ✓ Protected | Standard Noise XX, ML-KEM-768, ML-DSA-65 |
| Key leakage | ✓ Protected | Keys not logged |
| Eclipse/Sybil | ✓ Protected | Netgroup diversity, Trusted Core |
| Economic attack | N/A | No mining/staking in network layer |
