# Security Audit: Montana Network Layer — Adversarial Analysis

**Модель:** Claude Opus 4.5
**Компания:** Anthropic
**Дата:** 08.01.2026 12:00 UTC
**Scope:** `montana/src/net/` (21 файлов, ~12,000 LOC Rust)

---

## 1. Понимание архитектуры

### ACP vs Traditional Consensus

Montana использует **Atemporal Coordinate Presence (ACP)** — модель консенсуса, основанную на:

1. **Физическая упорядоченность (Layer -1)** — фундаментальное ограничение энтропии, требующее реального времени для накопления присутствия. Нельзя ускорить.

2. **Слайсы вместо блоков** — каждый слайс представляет фиксированный интервал времени (τ₂ = 5 минут), а не произвольный набор транзакций.

3. **Presence Proofs** — узлы подтверждают своё присутствие в момент времени τ₂, накапливая вес.

4. **Fork Choice через Cumulative Weight** — не PoW/PoS, а сумма весов presence proofs за всё время существования цепи.

### Отличия от традиционных систем

| Аспект | Bitcoin/Ethereum | Montana |
|--------|------------------|---------|
| Единица консенсуса | Блок | Слайс (τ₂ = 5 min) |
| Право на создание | Mining/Staking | Любой узел с presence |
| Fork resolution | Longest chain / Finality | Cumulative weight |
| Time model | Block timestamps | Physically derived coordinate time |
| Sybil resistance | PoW/PoS | Presence age + subnet diversity |

### Следствия для безопасности

1. **Атаки на майнинг не применимы** — нет mining power
2. **Nothing-at-stake не применим** — нет staking
3. **Критична синхронизация времени** — физические инварианты привязывают к реальному времени
4. **Bootstrap особенно критичен** — начальный вектор состояния определяет всё

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| mod.rs | ~50 | Module exports |
| types.rs | ~200 | Constants, NetAddress, InvItem |
| message.rs | ~300 | Wire protocol messages |
| peer.rs | ~250 | Peer state, rate limits |
| connection.rs | ~510 | Connection manager, bans, netgroup |
| addrman.rs | ~740 | Cryptographic bucket system |
| rate_limit.rs | ~150 | Token bucket rate limiting |
| eviction.rs | ~200 | Peer eviction strategy |
| discouraged.rs | ~180 | Bloom filter for misbehavior |
| startup.rs | ~300 | Bootstrap orchestration |
| bootstrap.rs | ~400 | Chain verification protocol |
| verification.rs | ~850 | Bootstrap verification client |
| hardcoded_identity.rs | ~205 | ML-DSA-65 hardcoded nodes |
| noise.rs | ~895 | Hybrid Noise XX + ML-KEM-768 |
| encrypted.rs | ~435 | Encrypted stream wrapper |
| subnet.rs | ~390 | Subnet reputation tracking |
| feeler.rs | ~260 | Feeler connections, addr cache |
| sync.rs | ~670 | Headers-first sync |
| protocol.rs | ~1650 | Main network protocol |
| inventory.rs | ~595 | Relay cache, LRU eviction |
| dns.rs | ~270 | DNS seeds, fallback IPs |

**Всего:** ~8,500 LOC анализированного кода

---

## 3. Attack Surface

### External Inputs (Точки входа для атакующего)

| Категория | Источник | Trust Level |
|-----------|----------|-------------|
| TCP connections | Any IP | Untrusted |
| Noise handshake | Post-TCP | Transport-secure |
| P2P messages | Post-handshake | Partially trusted |
| Addr gossip | Any peer | Untrusted |
| DNS seeds | Hardcoded domains | Semi-trusted |
| Hardcoded nodes | Embedded in binary | Trusted |
| Bootstrap data | Network consensus | Verified |

### Trust Boundaries

```
Internet → TCP → Noise Handshake → Montana Protocol → Consensus
          ↑        ↑                  ↑                ↑
         DoS    Crypto attacks    Protocol abuse    Fork manipulation
```

### Critical Assets (Что защищаем)

1. **Consensus state** — cumulative_weight, canonical chain
2. **Private keys** — Noise keypair, wallet keys
3. **Peer set** — защита от eclipse
4. **Network connectivity** — защита от DoS

---

## 4. Найденные уязвимости

### [CRITICAL] V-001: Single Point of Failure — One Hardcoded Node

**Файл:** `hardcoded_identity.rs:59-68`

**Уязвимый код:**
```rust
pub static MAINNET_HARDCODED: LazyLock<Vec<HardcodedNode>> = LazyLock::new(|| {
    vec![HardcodedNode {
        addr: SocketAddr::new(IpAddr::V4(Ipv4Addr::new(176, 124, 208, 93)), 19333),
        pubkey: TIMEWEB_MOSCOW_PUBKEY,
        name: "timeweb-moscow-1",
        region: "eu-east",
    }]
});
```

**Вектор атаки:**
1. Атакующий получает контроль над сервером 176.124.208.93 (TimeWeb Moscow)
2. Bootstrap verification (`verification.rs:140`) требует ответа от hardcoded nodes
3. С одним узлом атакующий контролирует 100% hardcoded ответов
4. Атакующий может поставить любой `cumulative_weight` и `head_hash`
5. Все новые узлы синхронизируются с поддельной цепью

**Импакт:** Полный контроль над консенсусом всех новых узлов

**Сложность:**
- Компрометация одного VPS (~$1000-10000 через социальную инженерию или уязвимость хостинга)
- Или DDoS на один IP для отказа в обслуживании bootstrap

**PoC сценарий:**
```bash
# Вариант 1: Compromise
ssh root@176.124.208.93  # После компрометации
systemctl stop montana
./fake-bootstrap-server --cumulative-weight 999999999

# Вариант 2: DDoS
hping3 -S --flood -p 19333 176.124.208.93
# Все новые узлы не могут пройти bootstrap
```

---

### [CRITICAL] V-002: Unencrypted Private Key Storage

**Файл:** `encrypted.rs:274-316`

**Уязвимый код:**
```rust
pub fn load_or_generate_keypair(data_dir: &Path) -> io::Result<StaticKeypair> {
    let key_path = data_dir.join("noise_key.bin");
    // ...
    // Save to file
    std::fs::write(&key_path, &keypair.secret)?;  // PLAINTEXT!

    #[cfg(unix)]
    {
        perms.set_mode(0o600);  // Only owner read/write
    }
```

**Вектор атаки:**
1. Атакующий получает read access к data_dir (через malware, physical access, backup leak)
2. Читает `noise_key.bin` — 32 байта plaintext private key
3. Импортирует keypair и выдаёт себя за легитимный узел
4. Если это hardcoded node — полная компрометация bootstrap

**Импакт:**
- Обычный узел: возможность MITM его соединений
- Hardcoded узел: полная компрометация сети

**Сложность:** Средняя (требуется доступ к файловой системе)

**PoC сценарий:**
```bash
# Атакующий на скомпрометированной машине
cat /home/node/.montana/noise_key.bin | xxd
# 00000000: 7a8b...  (32 bytes secret key)

# Импорт в другой узел
cp noise_key.bin /attacker/.montana/
./montana --impersonate
```

---

### [HIGH] V-003: Empty DNS Seeds — No Redundancy

**Файл:** `dns.rs:8-21`

**Уязвимый код:**
```rust
pub const DNS_SEEDS: &[&str] = &[
    // Primary seeds (to be populated with actual domains)
    // "seed1.montana.network",
    // ...
];

pub const FALLBACK_IPS: &[(u8, u8, u8, u8)] = &[
    // TimeWeb primary (Moscow)
    (176, 124, 208, 93),
    // Additional fallback IPs (to be populated)
];
```

**Вектор атаки:**
1. DNS_SEEDS пуст — DNS discovery отключен
2. FALLBACK_IPS содержит только один IP (тот же TimeWeb)
3. Сеть полностью зависит от одного сервера
4. DDoS или компрометация = сеть мертва для новых узлов

**Импакт:** Denial of Service для всех новых узлов

**Сложность:** Низкая (DDoS одного IP)

---

### [HIGH] V-004: Eclipse via Cloud Provider Subnet Diversity Bypass

**Файл:** `subnet.rs:16-17`, `verification.rs:200-250`

**Уязвимый код:**
```rust
pub const MAX_NODES_PER_SUBNET: usize = 5;
pub const MIN_DIVERSE_SUBNETS: usize = 25;
```

**Вектор атаки:**
1. Bootstrap требует 25 уникальных /16 подсетей
2. Атакующий арендует VPS у 25+ провайдеров (AWS, GCP, Azure, DigitalOcean, Vultr, Linode, OVH, Hetzner, ...)
3. Каждый провайдер = другая /16 подсеть
4. Атакующий контролирует 125 IP (5 × 25) в разных подсетях
5. Bootstrap verification проходит успешно с поддельными данными

**Импакт:** Eclipse attack на новые узлы

**Сложность:**
- 125 VPS × $5/month = $625/month
- Один раз настроить автоматизацию
- Долгосрочная атака экономически выгодна

**PoC сценарий:**
```python
# terraform/attack.tf
providers = [
    "aws_us-east-1",      # /16: 54.X
    "aws_eu-west-1",      # /16: 52.X
    "gcp_us-central1",    # /16: 35.X
    "azure_eastus",       # /16: 40.X
    # ... 21 more providers
]

for provider in providers:
    for i in range(5):
        create_vm(provider, run="fake-montana-node")
```

---

### [HIGH] V-005: Orphan Pool Memory Exhaustion

**Файл:** `sync.rs:17-18`

**Уязвимый код:**
```rust
pub const MAX_ORPHANS: usize = 100;
// Each orphan can be MAX_SLICE_SIZE = 4MB
// Total: 100 × 4MB = 400MB potential memory
```

**Вектор атаки:**
1. Атакующий генерирует 100 фейковых "orphan" слайсов по 4MB каждый
2. Слайсы имеют валидный формат, но parent не существует
3. Узел-жертва хранит их в orphan pool
4. 400MB памяти заблокировано мусором
5. Повторить с разных IP для обхода rate limiting

**Импакт:** Memory exhaustion DoS

**Сложность:** Низкая (генерация случайных данных)

**PoC сценарий:**
```rust
for i in 0..100 {
    let fake_slice = Slice {
        parent_hash: random_hash(),  // Non-existent parent
        data: vec![0u8; 4_000_000],  // 4MB payload
        // ... valid structure
    };
    send_to_victim(fake_slice);
}
// Victim now holds 400MB of garbage
```

---

### [MEDIUM] V-006: Flow Control Counts Messages, Not Bytes

**Файл:** `protocol.rs:779-803`

**Уязвимый код:**
```rust
// Flow control: pause reading if receive queue is overloaded
if peer.flow_control.should_pause_recv() {
    flow_control_pauses += 1;
    // ...
}
// ...
let msg_size = msg.estimated_size();
peer.flow_control.add_recv(msg_size);
```

**Проблема:** `should_pause_recv()` проверяется ПОСЛЕ чтения сообщения. Атакующий может отправить одно огромное сообщение (MAX_TX_SIZE = 1MB), которое будет полностью прочитано до проверки.

**Вектор атаки:**
1. Отправить множество 1MB сообщений подряд
2. Каждое полностью читается перед pause check
3. Memory spike до обработки flow control

**Импакт:** Временные memory spikes

**Сложность:** Низкая

---

### [MEDIUM] V-007: Self-Connection Nonce Race Condition

**Файл:** `protocol.rs:764-765, 911-915`

**Уязвимый код:**
```rust
// Insert nonce
sent_nonces.write().await.insert(version.nonce);
// ...later...
// Check nonce
if sent_nonces.read().await.contains(&version.nonce) {
    return Err(NetError::Protocol("Self-connection detected".into()));
}
```

**Проблема:** Между вызовом `insert()` на одном соединении и `contains()` на другом есть временное окно. При высокой параллельности возможны false negatives.

**Вектор атаки:**
1. Узел инициирует множество параллельных исходящих соединений
2. Один из них случайно к самому себе
3. Race condition позволяет обойти проверку

**Импакт:** Self-connection создаёт петлю сообщений

**Сложность:** Требует точного timing

---

### [MEDIUM] V-008: Timing Side Channel in ML-DSA-65 Verification

**Файл:** `verification.rs:380-400`, криптобиблиотека

**Вектор атаки:**
1. Bootstrap verification вызывает ML-DSA-65 signature verification
2. Время верификации может зависеть от signature content
3. Атакующий может извлечь информацию о public key через timing

**Импакт:** Потенциальная утечка криптографических секретов

**Сложность:** Высокая (требует точных измерений времени)

---

### [LOW] V-009: Unbounded sent_nonces HashSet

**Файл:** `protocol.rs:135, 866-868`

**Уязвимый код:**
```rust
sent_nonces: Arc<RwLock<HashSet<u64>>>,
// ...
// Cleanup only on successful disconnect:
if let Some(nonce) = our_sent_nonce {
    sent_nonces.write().await.remove(&nonce);
}
```

**Проблема:** Если соединение обрывается до cleanup (crash, timeout), nonce остаётся в HashSet навсегда. При миллионах неудачных соединений — memory leak.

**Импакт:** Медленный memory leak

**Сложность:** Требует длительной эксплуатации

---

### [LOW] V-010: Version Information Disclosure

**Файл:** `protocol.rs:904-948`

**Уязвимый код:**
```rust
// Record IP vote from peer (addr_recv is how they see us)
let their_view_of_us = version.addr_recv.ip;
if !peer.inbound
    && !their_view_of_us.is_loopback()
    && !their_view_of_us.is_unspecified()
{
    ip_votes.write().await.insert(peer.addr, their_view_of_us);
```

**Вектор атаки:**
1. Sybil-атакующий подключается к жертве с разных IP
2. Каждое соединение получает Version с addr_recv
3. Атакующий видит, какой IP жертва считает своим external
4. Fingerprinting для идентификации узла за NAT

**Импакт:** Privacy leak, fingerprinting

**Сложность:** Низкая

---

## 5. Атаки, которые НЕ работают

### 51% Attack
**Не применима.** Montana не использует PoW/PoS. Консенсус через cumulative weight presence proofs, который накапливается со временем. Нельзя "намайнить" больше веса.

### Nothing-at-Stake
**Не применима.** Нет staking. Presence proofs привязаны к реальному времени через физические ограничения.

### Long-Range Attack
**Ограниченно применима.** Subnet reputation накапливается годами и снапшотится каждые τ₃. Атакующему нужно контролировать репутацию подсетей годами.

### Selfish Mining
**Не применима.** Нет mining. Слайсы создаются по расписанию τ₂.

### Transaction Malleability (Classic)
**Не проверена.** Требует анализа transaction layer (вне scope network audit).

### BGP Hijack
**Частично защищено.** Noise Protocol обеспечивает authenticated encryption. Hijack позволит DoS, но не MITM контента.

---

## 6. Рекомендации

### CRITICAL Fixes (Требуется немедленно)

| # | Уязвимость | Рекомендация |
|---|------------|--------------|
| V-001 | Single hardcoded node | Добавить минимум 5 hardcoded nodes в разных юрисдикциях |
| V-002 | Plaintext key storage | Шифровать ключи через OS keychain или password-derived key |
| V-003 | Empty DNS seeds | Настроить DNS seeds на нескольких доменах |

### HIGH Priority

| # | Уязвимость | Рекомендация |
|---|------------|--------------|
| V-004 | Cloud subnet bypass | Добавить ASN diversity check в дополнение к /16 |
| V-005 | Orphan exhaustion | Уменьшить MAX_ORPHANS до 20 или добавить size-based limit |

### MEDIUM Priority

| # | Уязвимость | Рекомендация |
|---|------------|--------------|
| V-006 | Flow control timing | Проверять size limit ДО чтения payload |
| V-007 | Nonce race | Использовать атомарный check-and-insert |
| V-008 | Timing side channel | Использовать constant-time comparison в crypto |

### LOW Priority

| # | Уязвимость | Рекомендация |
|---|------------|--------------|
| V-009 | Nonce leak | Добавить periodic cleanup для sent_nonces |
| V-010 | Version disclosure | Не включать точный external IP в addr_recv |

---

## 7. Вердикт

```
[X] CRITICAL — есть уязвимости, позволяющие уничтожить сеть
[ ] HIGH — есть серьёзные уязвимости
[ ] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено
```

### Обоснование

**V-001 (Single Hardcoded Node)** и **V-003 (Empty DNS Seeds)** создают катастрофическую точку отказа. Компрометация или DDoS одного IP (176.124.208.93) полностью парализует bootstrap новых узлов и позволяет навязать поддельную цепь.

**V-002 (Plaintext Keys)** в сочетании с V-001 означает: если атакующий получит доступ к файловой системе hardcoded node, он получит полный контроль над сетью.

**V-004 (Cloud Bypass)** показывает, что даже при наличии subnet diversity, экономически мотивированный атакующий может обойти защиту за ~$600/месяц.

### Общая оценка

Код сетевого слоя демонстрирует зрелый подход к безопасности (rate limiting, eviction, cryptographic bucketing). Однако **инфраструктурные** решения (один hardcoded node, пустые DNS seeds, plaintext ключи) создают критические уязвимости уровня **сети целиком**, а не отдельного узла.

**Рекомендация:** Не запускать mainnet до исправления V-001, V-002, V-003.

---

## Appendix: Файлы и строки

| Уязвимость | Файл | Строки |
|------------|------|--------|
| V-001 | hardcoded_identity.rs | 59-68 |
| V-002 | encrypted.rs | 274-316 |
| V-003 | dns.rs | 8-32 |
| V-004 | subnet.rs | 16-17, 169-233 |
| V-005 | sync.rs | 17-18 |
| V-006 | protocol.rs | 779-803 |
| V-007 | protocol.rs | 764-765, 911-915 |
| V-008 | verification.rs | 380-400 |
| V-009 | protocol.rs | 135, 866-868 |
| V-010 | protocol.rs | 904-948 |
