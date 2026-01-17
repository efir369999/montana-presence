# Adversarial Review: Eclipse Attack на Montana

**Модель:** Claude Opus 4.5
**Компания:** Anthropic
**Дата:** 07.01.2026 17:00 UTC
**Роль:** Атакующий с неограниченными ресурсами

---

## Attack Surface

**External inputs:**
- P2P addr messages (адреса пиров)
- DNS seeds (hardcoded в бинарнике)
- Gossip от подключённых пиров
- AddrMan persistence file (peers.dat)

**Trust boundaries:**
- Сеть → AddrMan (NEW table)
- Успешное соединение → TRIED table
- AddrMan file → Memory

**Critical assets:**
- Outbound connections (8 слотов)
- Inbound connections (117 слотов)
- Chain tip consensus

---

## Attempted Attacks

### 1. NEW Table Poisoning

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 1.1 | Отправить 1M вредоносных адресов через addr message | NEW table | **PROTECTED** — MAX_ADDR_SIZE=1000 ограничивает одно сообщение |
| 1.2 | Отправить addr от множества connection | NEW table | **PROTECTED** — bucket assignment зависит от source IP |
| 1.3 | Заполнить все 1024 bucket одним netgroup | NEW table | **PROTECTED** — bucket = hash(key \|\| netgroup \|\| source_netgroup) |

**Анализ `addrman.rs:441-450`:**
```rust
fn get_new_bucket(&self, addr: &SocketAddr, source: Option<&SocketAddr>) -> usize {
    let mut hasher = SipHasher24::new_with_key(&self.key[..16]);
    hasher.write(&get_netgroup_bytes(addr));
    if let Some(src) = source {
        hasher.write(&get_netgroup_bytes(src)); // Source affects bucket!
    }
    (hasher.finish() as usize) % NEW_BUCKET_COUNT
}
```

**Verdict 1:** Атакующий с одного netgroup может заполнить только ограниченное количество bucket'ов. Для полного заполнения нужны адреса из многих /16 подсетей.

---

### 2. TRIED Table Manipulation

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 2.1 | Fake successful connections | TRIED table | **PROTECTED** — mark_good() требует реального TCP соединения |
| 2.2 | Collision в TRIED bucket | Вытеснение honest peers | **VULNERABLE** — см. анализ ниже |
| 2.3 | Массовые mark_good() | TRIED overflow | **PROTECTED** — TRIED_BUCKET_COUNT × BUCKET_SIZE = 16384 slots |

**Анализ `addrman.rs:196-208`:**
```rust
fn mark_good(&mut self, addr: &SocketAddr) {
    // ...
    let bucket = self.get_tried_bucket(addr);
    let pos = self.get_bucket_position(addr, bucket, false);
    let idx = bucket * BUCKET_SIZE + pos;

    // Handle collision
    if let Some(existing_idx) = self.tried_table[idx] {
        self.move_to_new(existing_idx);  // Existing moved to NEW!
    }
    self.tried_table[idx] = Some(addr_idx);
}
```

**FINDING [MEDIUM]:** При коллизии в TRIED table, существующий адрес перемещается обратно в NEW. Атакующий контролирующий множество IP может вытеснить honest peers из TRIED.

**Mitigation:** Bucket assignment использует cryptographic hash с secret key, что делает предсказание коллизий вычислительно сложным.

---

### 3. Restart Attack (Classic Eclipse)

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 3.1 | Заполнить tables, ждать restart | Все outbound | **PROTECTED** — full bootstrap always |
| 3.2 | Poisoned peers.dat | Все connections | **PROTECTED** — full bootstrap overrides |

**Анализ `startup.rs:79-95`:**
```rust
/// Montana always uses full_bootstrap regardless of chain age:
/// - 100 peers from 25+ subnets
/// - Hardcoded nodes must match network median
pub async fn verify(&self) -> Result<StartupResult, StartupError> {
    // Always use full bootstrap for decentralized verification
    self.full_bootstrap(chain_age, local_height).await
}
```

**PROTECTED:** Montana выполняет **полный bootstrap при КАЖДОМ рестарте**.

Требования:
- 100 peers (20 hardcoded + 80 P2P)
- 25+ unique /16 subnets
- Hardcoded must match median ±1%

Стоимость атаки: контроль 51+ peers из 25+ /16 подсетей И 15+ hardcoded nodes.

---

### 4. Netgroup Diversity Check

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 4.1 | Все outbound из одного /16 | Outbound diversity | **PROTECTED** |
| 4.2 | Контроль 4+ разных /16 | Bypass diversity | **PROTECTED** (частично) |

**Анализ `connection.rs:265-269`:**
```rust
pub async fn can_connect(&self, addr: &SocketAddr) -> bool {
    let netgroup = get_netgroup(addr);
    let counts = self.netgroup_counts.lock().await;
    let current = counts.get(&netgroup).copied().unwrap_or(0);
    current < MAX_PEERS_PER_NETGROUP  // MAX = 2
}
```

**Verdict:** MAX_PEERS_PER_NETGROUP=2 означает атакующему нужно контролировать минимум 4 различных /16 подсети для 8 outbound. Каждая /16 = 65536 IP, это дорого.

---

### 5. Eviction Gaming

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 5.1 | Low latency gaming | Eviction protection | **PROTECTED** — 8 lowest-ping protected |
| 5.2 | Fake tx/slice relay activity | Eviction protection | **PROTECTED** — 4 recent tx + 4 recent slice protected |
| 5.3 | Netgroup concentration | Eviction target | **PROTECTED** — evicts from most-concentrated netgroup |

**Анализ `eviction.rs:63-126`:**

Eviction защищает по слоям:
1. **NoBan** — trusted peers (4+)
2. **Netgroup diversity** — 4 из разных /16
3. **Lowest ping** — 8 peers
4. **Recent TX relay** — 4 peers
5. **Recent slice relay** — 4 peers
6. **Longevity** — 8 oldest connections

**Total protected:** 4+8+4+4+8 = **28 peers minimum**

С MAX_INBOUND=117 и 28 protected, атакующий может занять 89 slots, но не вытеснить protected diversity peers.

---

### 6. Bootstrap Attack

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 6.1 | Контроль DNS seeds | New node bootstrap | **PROTECTED** — требует 15/20 hardcoded |
| 6.2 | Sybil атака на P2P gossip | Bootstrap peers | **PROTECTED** — subnet diversity 25+ required |
| 6.3 | Clock manipulation | Time verification | **PROTECTED** — median from 100 peers |

**Анализ `bootstrap.rs:37-50`:**
```rust
pub const HARDCODED_NODE_COUNT: usize = 20;
pub const MIN_HARDCODED_RESPONSES: usize = 15;
pub const MIN_DIVERSE_SUBNETS: usize = 25;
pub const BOOTSTRAP_PEER_COUNT: usize = 100;
```

**Security model `bootstrap.rs:14-25`:**
- Требует 15/20 hardcoded nodes согласны
- 25+ уникальных /16 подсетей
- Max 5 peers per subnet
- Hardcoded must match median (1% tolerance)

**Verdict:** Двойная защита (hardcoded + diversity) требует компрометации И DNS seeds, И 51+ peers из 25+ подсетей.

---

### 7. AddrMan Persistence Attack

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 7.1 | Malformed peers.dat | Memory corruption | **PROTECTED** — 16MB size limit |
| 7.2 | Oversized file DoS | Disk/memory exhaustion | **PROTECTED** — MAX_ADDRMAN_FILE_SIZE check |

**Анализ `addrman.rs:107-121`:**
```rust
pub fn load<P: AsRef<Path>>(path: P) -> Result<Self, std::io::Error> {
    let data = std::fs::read(&path)?;
    if data.len() as u64 > MAX_ADDRMAN_FILE_SIZE {
        return Err(/* ... */);
    }
    bincode::deserialize(&data)  // Standard bincode
}
```

**FINDING [LOW]:** bincode deserialize без explicit limits на collections. При корректном MAX_ADDRMAN_FILE_SIZE это маловероятно, но теоретически возможна memory amplification при crafted data.

---

## Findings Summary

### CRITICAL: None

### HIGH: None

Montana выполняет полный bootstrap при каждом рестарте (`startup.rs:79-95`). Атака требует контроля 51+ peers из 25+ /16 подсетей И 15+ hardcoded nodes.

### MEDIUM

**M-1: TRIED Collision → Move to NEW**

| Поле | Значение |
|------|----------|
| Файл | `addrman.rs:196-208` |
| Описание | При коллизии в TRIED table, existing peer перемещается обратно в NEW вместо отклонения нового |
| Impact | Постепенное вытеснение honest peers из TRIED в менее надёжную NEW table |
| Mitigation | При коллизии сравнивать качество адресов (last_success, attempts) и сохранять лучший |

### LOW

**L-1: Bincode Deserialize без explicit collection limits**

| Поле | Значение |
|------|----------|
| Файл | `addrman.rs:119`, `connection.rs:76-77` |
| Описание | bincode::deserialize без serde(deserialize_with) limits на HashMap/Vec |
| Impact | При MAX_FILE_SIZE=16MB атака маловероятна, но возможна memory amplification |
| Mitigation | Добавить explicit size limits через bincode::options().with_limit() |

---

## Checklist Results

```
[x] Eclipse: full bootstrap on every restart — startup.rs
[x] Eclipse: netgroup diversity — MAX_PEERS_PER_NETGROUP=2
[x] Eclipse: subnet diversity — 25+ /16 subnets required
[x] Eclipse: hardcoded verification — must match median ±1%
[x] Memory: flow control до allocation — MAX_TX_SIZE early check
[x] Memory: все collections bounded — Vec<Option<usize>> fixed size
[x] Slots: eviction защищает diversity — 28 peers protected
[x] Rate: per-IP limiting — MAX_CONNECTIONS_PER_IP=2
```

---

## Verdict

**[x] SAFE — можно продолжать**
**[ ] NEEDS_FIX — исправить перед продолжением**

---

## Recommendations

### Priority 1: TRIED Collision Resolution

```rust
// Вместо безусловного move_to_new:
if let Some(existing_idx) = self.tried_table[idx] {
    if let Some(existing) = self.addrs.get(&existing_idx) {
        if let Some(new_info) = self.addrs.get(&addr_idx) {
            // Сохранить peer с лучшей историей
            if existing.last_success > new_info.last_success {
                return; // Keep existing, reject new
            }
        }
    }
    self.move_to_new(existing_idx);
}
```

---

## Attack Cost Analysis

**Eclipse attack на Montana требует:**

| Требование | Стоимость |
|------------|-----------|
| 51+ peers из 25+ /16 подсетей | Контроль IP в 25+ datacenter/ISP |
| 15+ hardcoded DNS seeds | Компрометация инфраструктуры |
| Subnet diversity bypass | Каждая /16 = 65536 IP адресов |

**Защита через:**
- Full bootstrap при каждом рестарте (100 peers, 25+ subnets)
- Hardcoded verification (must match median ±1%)
- Runtime netgroup diversity (MAX_PEERS_PER_NETGROUP=2)
- Eviction protection (28 peers protected)

---

*Ничто_Nothing_无_金元Ɉ*
