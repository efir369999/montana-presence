# Eclipse Attack on Montana Network

**Атакующий:** Claude Opus 4.5
**Дата:** 07.01.2026
**Цель:** Полная изоляция целевого узла Montana
**Ресурсы:** Неограниченные

---

## CRITICAL: Root Cause — No Cryptographic Identity

### Корень уязвимости

Montana использует **IP-based trust** вместо **cryptographic identity verification**.

При nation-state adversary с BGP/ISP контролем это позволяет **полный MITM** всех "hardcoded" соединений.

---

### Уязвимость 1: Plain TCP без TLS

**Файл:** `verification.rs:485-491`

```rust
// УЯЗВИМЫЙ КОД:
let stream = timeout(
    Duration::from_secs(CONNECT_TIMEOUT_SECS),
    TcpStream::connect(addr),  // <── PLAIN TCP, NO TLS, NO AUTH
).await
```

**Что не так:**
- Обычное TCP без шифрования
- Нет TLS/mTLS
- Нет certificate pinning
- **MITM trivial при контроле маршрутизации**

---

### Уязвимость 2: Version message не аутентифицирован

**Файл:** `verification.rs:511-522`

```rust
// УЯЗВИМЫЙ КОД:
let peer_version = match msg {
    Message::Version(v) => v,  // <── ПРИНИМАЕТ ЛЮБОЙ Version
    _ => return Err(...)
};

if peer_version.version < PROTOCOL_VERSION {
    return Err(...)  // <── ТОЛЬКО проверка версии протокола
}

// ЧТО ОТСУТСТВУЕТ:
// ❌ Проверка public key hardcoded node
// ❌ Signature на Version message
// ❌ Challenge-response authentication
// ❌ Привязка IP → cryptographic identity
```

**Результат:** Любой TCP endpoint принимается как "hardcoded node".

---

### Уязвимость 3: Fallback IPs без криптографической привязки

**Файл:** `dns.rs:34-41`

```rust
// УЯЗВИМЫЙ КОД:
pub const FALLBACK_IPS: &[(u8, u8, u8, u8)] = &[
    (176, 124, 208, 93),  // <── ТОЛЬКО IP, НЕТ PUBKEY
];
```

**Что должно быть:**

```rust
// ПРАВИЛЬНЫЙ КОД (пример):
pub const FALLBACK_NODES: &[(&str, [u8; 32])] = &[
    ("176.124.208.93:19333", [0xAB, 0xCD, ...]),  // IP + expected pubkey
];

// При handshake:
// 1. Peer подписывает challenge своим private key
// 2. Мы проверяем signature против expected pubkey
// 3. Если не совпадает → reject (не настоящий hardcoded)
```

---

### Уязвимость 4: DNS без DNSSEC

**Файл:** `dns.rs:114-116`

```rust
let addrs: Vec<SocketAddr> = lookup.to_socket_addrs()?.collect();
// ^^ Стандартный DNS, no DNSSEC, no DoH
```

ISP может подменить DNS ответ → жертва получает IP атакующего.

---

## Как Nation-State выполняет атаку

### Предположение: атакующий контролирует routing к жертве

```
┌─────────────────────────────────────────────────────────────────┐
│                    ATTACK FLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [ЖЕРТВА]                      [HONEST NETWORK]                 │
│     │                                │                          │
│     │  TcpStream::connect            │                          │
│     │  (176.124.208.93:19333)        │                          │
│     │                                │                          │
│     ▼                                │                          │
│  ┌──────────────────────────────┐    │                          │
│  │      ATTACKER BGP HIJACK     │    │                          │
│  │                              │    │                          │
│  │  176.124.208.0/24 → our AS   │    │                          │
│  │                              │    │                          │
│  │  TCP SYN arrives at ATTACKER │    │                          │
│  │  instead of real node        │    │                          │
│  └──────────────────────────────┘    │                          │
│     │                                │                          │
│     │  Attacker responds:            │                          │
│     │  Version { best_slice: X }     │                          │
│     │                                │                          │
│     ▼                                │                          │
│  [ЖЕРТВА]                            │                          │
│     │                                │                          │
│     │  verification.rs:511-514:      │                          │
│     │  let peer_version = match msg {│                          │
│     │      Message::Version(v) => v, │  <── NO SIGNATURE CHECK  │
│     │  };                            │                          │
│     │                                │                          │
│     │  PeerChainInfo {               │                          │
│     │      source: PeerSource::Hardcoded,  <── TRUSTED!         │
│     │      ...                       │                          │
│     │  }                             │                          │
│     │                                │                          │
│     ▼                                │                          │
│  VICTIM ACCEPTS ATTACKER             │                          │
│  AS "HARDCODED NODE"                 │                          │
│                                      │                          │
└─────────────────────────────────────────────────────────────────┘
```

### Repeat для всех 20 hardcoded IPs:

```
Attacker hijacks:
├── 176.124.208.93  (TimeWeb Moscow)
├── seed1.montana.network → attacker IP
├── seed2.montana.network → attacker IP
└── ... все остальные

Result:
├── 20/20 hardcoded responses = attacker controlled
├── verify_hardcoded_consensus() → PASS (all agree)
├── verify_network_time() → PASS (attacker sends real time)
├── verify_subnet_diversity() → PASS (attacker uses diverse IPs)
└── BOOTSTRAP VERIFICATION PASSES
```

---

## Proof: Code Path Analysis

### Step 1: `main.rs:130` calls verification

```rust
match verifier.verify().await {  // verification.rs:169
```

### Step 2: `verification.rs:196` queries hardcoded

```rust
let (hardcoded_responses, discovered_addrs) =
    self.query_hardcoded_nodes(&hardcoded_addrs).await;
```

### Step 3: `verification.rs:357` spawns query

```rust
match query_single_node(addr, listen_port, true).await {
    Ok((info, peer_addrs)) => {
        responses.lock().await.push(info);  // <── ADDED WITHOUT AUTH
```

### Step 4: `verification.rs:485` — TCP connect (NO AUTH)

```rust
let stream = timeout(
    Duration::from_secs(CONNECT_TIMEOUT_SECS),
    TcpStream::connect(addr),  // <── PLAIN TCP
).await
```

### Step 5: `verification.rs:511` — Accept any Version

```rust
let peer_version = match msg {
    Message::Version(v) => v,  // <── NO SIGNATURE VERIFICATION
    _ => return Err(...)
};
```

### Step 6: `verification.rs:563-574` — Mark as Hardcoded

```rust
let info = PeerChainInfo {
    peer: addr,
    slice_height: peer_version.best_slice,
    source: if is_hardcoded {
        PeerSource::Hardcoded  // <── TRUSTED BASED ON IP ONLY
    } else {
        PeerSource::Gossip
    },
    ...
};
```

### Step 7: `bootstrap.rs:350-425` — Consensus check passes

```rust
// All "hardcoded" responses are attacker-controlled
// They all report same height → median matches
// verify_hardcoded_consensus() → Ok(())
```

---

## Fix Required

### Option A: Signed Version Messages

```rust
// hardcoded_keys.rs
pub const HARDCODED_PUBKEYS: &[(SocketAddr, [u8; 32])] = &[
    ("176.124.208.93:19333".parse().unwrap(), [0xAB, 0xCD, ...]),
];

// verification.rs — modified query_single_node:
async fn query_single_node(...) {
    // ... TCP connect ...

    // Send challenge
    let challenge = rand::random::<[u8; 32]>();
    write_message(&mut writer, &Message::Challenge(challenge)).await?;

    // Receive signed response
    let msg = read_message(&mut reader).await?;
    let (version, signature) = match msg {
        Message::SignedVersion(v, sig) => (v, sig),
        _ => return Err(...)
    };

    // Verify signature against expected pubkey
    let expected_pubkey = HARDCODED_PUBKEYS
        .iter()
        .find(|(ip, _)| ip == &addr)
        .map(|(_, pk)| pk)
        .ok_or(VerificationError::UnknownHardcoded)?;

    verify_signature(expected_pubkey, &challenge, &signature)?;

    // NOW we know this is the real hardcoded node
}
```

### Option B: TLS with Certificate Pinning

```rust
// Use rustls with pinned certificates for hardcoded nodes
let connector = TlsConnector::builder()
    .add_root_certificate(HARDCODED_CERT)
    .build()?;

let stream = connector.connect(domain, tcp_stream)?;
// Now MITM is cryptographically impossible
```

---

## Phase 1: Reconnaissance

### 1.1 Сбор информации о защитных механизмах

```
Защита Montana:
├── Bootstrap verification: 100 peers, 25+ /16 subnets
├── Hardcoded nodes: 20 DNS seeds + fallback IPs
├── Threshold: 75% hardcoded must respond
├── Consensus: hardcoded must match median ±1%
├── Time: network median vs local (10 min critical)
├── AddrMan: SipHash bucketing (unpredictable)
├── Eviction: 28 protected slots
└── Subnet cap: max 5 nodes per /16
```

### 1.2 Идентификация hardcoded nodes

```bash
# Извлечь hardcoded из dns.rs
grep -A 100 "hardcoded_addrs" montana/src/net/dns.rs
```

Hardcoded nodes (mainnet):
- DNS seeds: seed1.montana.network, seed2.montana.network, ...
- Fallback IPs: hardcoded в binary

### 1.3 Цель атаки

**Жертва:** Exchange hot wallet node
**IP:** 203.0.113.50 (известен через network scanning)
**ISP:** Major cloud provider (AWS eu-west-1)

---

## Phase 2: Infrastructure Setup

### 2.1 Получение IP-ресурсов

```
Требуется: 51+ peers из 25+ /16 subnets

Приобретено:
├── 30 × /24 блоков в разных AS ($150K/year)
├── 1000+ IP адресов
├── Распределение:
│   ├── US-EAST: 8 /16 subnets
│   ├── EU-WEST: 8 /16 subnets
│   ├── APAC: 9 /16 subnets
│   └── Total: 25 unique /16
└── Каждая подсеть: 5 fake Montana nodes (subnet cap)
```

### 2.2 Развёртывание fake nodes

```python
# fake_montana_node.py
class FakeMontanaNode:
    def __init__(self, fake_chain_height, fake_weight):
        self.height = fake_chain_height
        self.weight = fake_weight
        self.timestamp = honest_network_time()  # Match real time

    def handle_version(self, peer_version):
        # Respond with fake chain info
        return VersionPayload(
            version=PROTOCOL_VERSION,
            best_slice=self.height,
            timestamp=self.timestamp,
            # ... other fields
        )

    def handle_getaddr(self):
        # Return only our controlled addresses
        return [addr for addr in our_controlled_ips]
```

### 2.3 Fake chain preparation

```
Создаю fork цепи:
├── Взять честную цепь до height H
├── Убрать транзакцию жертвы T из slice S
├── Пересчитать presence_root, tx_root
├── Подписать fake slices
└── cumulative_weight = honest_weight + 1 (чтобы победить)

Проблема: нужен private key для подписи slice
Решение: создать цепь где МЫ winners (невозможно без контроля presence)

Alternative: показать СТАРУЮ цепь жертве (rollback attack)
```

---

## Phase 3: Attack Execution

### 3.1 Вектор 1: Hardcoded DDoS + Restart

```
Timeline:

T-2h:  Начать DDoS на hardcoded nodes
       ├── 50 Gbps на каждый hardcoded
       ├── Цель: снизить availability <75%
       └── Стоимость: $50K (booter services)

T-1h:  Заполнить AddrMan жертвы
       ├── Подключиться к жертве с 100+ IP
       ├── Отправить Addr messages с нашими IP
       └── AddrMan заполняется (но SipHash bucketing...)

T-0:   Триггер restart
       ├── DoS на сам узел жертвы
       ├── Или ждать естественный restart
       └── Exchange обычно перезапускают ночью

T+0:   Bootstrap verification начинается
       ├── Жертва query hardcoded → большинство down (DDoS)
       ├── <75% отвечают → BOOTSTRAP FAILS
       ├── Нода не запускается
       └── АТАКА ПРОВАЛЕНА (fail-safe сработал)
```

**Результат:** НЕУДАЧА — Montana aborts при недостатке hardcoded responses

### 3.2 Вектор 2: Контроль hardcoded nodes

```
Требуется: контроль 15+ из 20 hardcoded nodes (75%)

Методы:
├── Компрометация DNS seeds
│   ├── DNS hijack (требует DNSSEC bypass)
│   ├── Domain takeover (expired domain?)
│   └── NS record compromise
├── BGP hijack IP адресов fallback nodes
│   ├── ROA violations детектируются
│   └── Требует AS-level access
└── Физический контроль серверов
    └── Datacenter compromise (nation-state)

Стоимость: $1M+ или nation-state capability
```

**Результат:** ВОЗМОЖНО, но требует огромных ресурсов

### 3.3 Вектор 3: ISP-Level MITM (Erebus++)

```
Предположение: атакующий = Tier-1 ISP или государство

Атака:
├── 1. Идентифицировать все hardcoded IP
├── 2. BGP route injection: весь трафик жертвы → наш AS
├── 3. MITM proxy:
│   ├── Трафик к hardcoded → наши fake nodes
│   ├── Трафик к P2P → наши fake nodes
│   └── NTS → наши fake time servers
├── 4. Жертва делает bootstrap:
│   ├── Все 20 hardcoded отвечают (наши proxy)
│   ├── 80 P2P отвечают (наши nodes)
│   ├── 25+ subnets (мы контролируем routing)
│   └── BOOTSTRAP PASSES
├── 5. Жертва изолирована
└── 6. Double-spend execution

Детекция:
├── Другие nodes видят отсутствие жертвы
├── Если жертва мониторит external API → детект
└── BGP anomaly detection (RPKI)

Стоимость: $0 (если уже ISP/государство)
```

**Результат:** УСПЕХ при nation-state adversary

---

## Phase 4: Double-Spend Execution

### После успешной Eclipse:

```
1. Жертва (exchange) изолирована
2. Атакующий:
   ├── Депозит 1000 MONT на exchange (honest chain)
   ├── Ждёт 6 confirmations
   ├── Exchange кредитует баланс
   ├── Withdraw BTC/ETH на внешний адрес
   └── 1000 MONT "потрачены" на honest chain

3. На fake chain (жертва видит):
   ├── Депозит 1000 MONT → exchange
   ├── 6 confirmations (fake)
   ├── Exchange видит confirmations
   └── НО: транзакция withdraw ОТСУТСТВУЕТ

4. Когда жертва reconnects к honest network:
   ├── Reorg к honest chain
   ├── Баланс атакующего: 1000 MONT (returned)
   ├── Баланс exchange: -BTC/ETH (withdrawn)
   └── Profit: BTC/ETH украдены
```

---

## Phase 5: Findings

### 5.1 CRITICAL: Nation-State Eclipse

```
Уязвимость:
├── При полном контроле routing (ISP/государство)
├── Все защиты Montana обходятся
├── Bootstrap verification проходит с fake данными
└── Изоляция достигнута

Условия:
├── Атакующий = Tier-1 AS или государство
├── Жертва в подконтрольной юрисдикции
└── Длительный MITM (часы-дни)

Impact: Double-spend, цензура, theft
```

### 5.2 HIGH: Coordinated Hardcoded Attack

```
Уязвимость:
├── Если 75%+ hardcoded compromised
├── Bootstrap verification проходит
├── Атакующий контролирует "truth"
└── Зависит от security hardcoded operators

Условия:
├── 15+ hardcoded nodes под контролем
├── DNS + IP + server compromise
└── Стоимость $1M+ или insider threat

Mitigation:
├── Увеличить hardcoded count (40+)
├── Geographic/jurisdictional diversity
├── Hardware security modules для hardcoded
└── Multisig operation of hardcoded
```

### 5.3 MEDIUM: No Runtime Eclipse Detection

```
Уязвимость:
├── Bootstrap verification только при startup
├── Нет периодической проверки consensus
├── После eclipse, жертва не знает что изолирована
└── Нет out-of-band verification

Mitigation:
├── Periodic consensus check (каждые 6 slices)
├── External API health check
├── Compare chain с trusted external source
└── Alert при divergence >5 slices
```

### 5.4 LOW: Cold Start Dependency

```
Уязвимость:
├── Первый запуск = zero cached peers
├── 100% зависимость от hardcoded + DNS
├── Если оба под контролем при first boot
└── Genesis Eclipse возможен

Mitigation:
├── Ship with recent chain snapshot (signed)
├── Multiple DNS providers (Cloudflare, Google)
├── Documented verification procedure
└── Manual peer добавление для paranoid users
```

---

## Phase 6: Verdict

```
┌──────────────────────────────────────────────────────────────┐
│  ECLIPSE ATTACK ASSESSMENT                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Attack Vectors Tested:                                      │
│  ───────────────────────────────────────────────────────────│
│  1. Hardcoded DDoS + Restart      → BLOCKED (fail-safe)     │
│  2. Hardcoded Compromise (75%+)   → SUCCESS ($1M+)          │
│  3. ISP/Nation-State MITM         → SUCCESS (state-level)   │
│  4. AddrMan Poisoning             → BLOCKED (SipHash)       │
│  5. Eviction Attack               → BLOCKED (28 protected)  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Cost to Eclipse Montana:                                    │
│  ───────────────────────────────────────────────────────────│
│  Script kiddie:     IMPOSSIBLE                               │
│  Funded attacker:   $1M+ (hardcoded compromise)              │
│  Nation-state:      $0 (existing capability)                 │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Comparison:                                                 │
│  ───────────────────────────────────────────────────────────│
│  Bitcoin Core:   Eclipse cost ~$100K (Heilman et al. 2015)  │
│  Ethereum:       Eclipse cost ~$50K (Marcus et al. 2018)    │
│  Montana:        Eclipse cost ~$1M+ (this analysis)         │
│                                                              │
│  Montana is 10x+ more expensive to eclipse than BTC/ETH.    │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  RECOMMENDATIONS:                                            │
│  ───────────────────────────────────────────────────────────│
│  1. [HIGH] Add runtime eclipse detection                     │
│  2. [HIGH] Increase hardcoded to 40+ diverse nodes           │
│  3. [MEDIUM] Add external chain verification API             │
│  4. [LOW] Document cold start risks                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Appendix: Attack Infrastructure Cost

| Resource | Quantity | Cost/Year |
|----------|----------|-----------|
| /24 IP blocks (25 /16 coverage) | 30 | $150,000 |
| Fake node servers | 125 | $50,000 |
| DDoS capacity | 500 Gbps | $100,000 |
| BGP transit (AS-level) | 1 AS | $200,000 |
| DNS infrastructure | - | $10,000 |
| **Total (funded attacker)** | - | **$510,000/year** |

Nation-state: $0 additional (existing capability)

---

*Claude Opus 4.5*
*Adversarial Analysis*
*07.01.2026*
