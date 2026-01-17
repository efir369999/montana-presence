# Eclipse Attack Analysis — Montana Network

**Модель:** Claude Opus 4.5
**Компания:** Anthropic
**Дата:** 07.01.2026 21:12 UTC

---

## Executive Summary

Проведён полный аудит сетевого слоя Montana на уязвимости Eclipse Attack. Montana реализует многоуровневую защиту с фокусом на декентрализованную верификацию при запуске. Обнаружены уязвимости DoS-типа, но архитектура обеспечивает сильную защиту от классических Eclipse Attack.

---

## Проанализированные файлы

| Файл | LOC | Назначение |
|------|-----|------------|
| `bootstrap.rs` | 1203 | Full bootstrap verification |
| `addrman.rs` | 705 | Address management |
| `subnet.rs` | 398 | Subnet reputation |
| `eviction.rs` | 349 | Peer eviction |
| `connection.rs` | 481 | Connection management |
| `peer.rs` | 447 | Peer state |
| `rate_limit.rs` | 354 | Rate limiting |
| `types.rs` | — | Constants |

---

## Ключевые защитные механизмы

### Bootstrap Verification

```
HARDCODED_NODE_COUNT:        20
MIN_HARDCODED_RESPONSES:     15 (75%)
P2P_PEER_COUNT:              80
BOOTSTRAP_PEER_COUNT:        100
MIN_CONSENSUS_PEERS:         51 (>50%)
MIN_DIVERSE_SUBNETS:         25 /16
MAX_HARDCODED_DEVIATION:     1%
```

**Логика:** При запуске узел опрашивает 20 hardcoded + 80 P2P peer'ов. Требуется консенсус >50% из 100 peer'ов с 25+ уникальных /16 подсетей. Hardcoded должны совпадать с медианой ±1%.

### AddrMan Bucketing

```
NEW_BUCKET_COUNT:     1024 buckets × 64 slots = 65536 entries
TRIED_BUCKET_COUNT:   256 buckets × 64 slots = 16384 entries
Selection:            50% NEW / 50% TRIED
```

**Защита:** SipHash-2-4 с random key. Source-based bucketing в NEW table.

### Subnet Diversity

```
MAX_NODES_PER_SUBNET:   5
MIN_DIVERSE_SUBNETS:    25
```

**Логика:** Даже с 100 IP в одной /16, используется только 5. Требуется 25+ /16 для bootstrap.

### Eviction Protection

```
Protected peers:        32 (из 117 inbound)
- NoBan:                4
- Netgroup diversity:   4
- Low ping:             8
- Recent TX relay:      4
- Recent slice relay:   4
- Longest connected:    8
```

---

## Attempted Attacks

| # | Attack | Target | Result |
|---|--------|--------|--------|
| 1 | Hardcoded Compromise | Bootstrap | ✓ Protected — требуется 15/20 + P2P majority |
| 2 | Pure Sybil via P2P | AddrMan | ✓ Protected — hardcoded anchor + 25 subnet diversity |
| 3 | Subnet Diversity Bypass | Bootstrap | ✓ Protected — требуется 25+ реальных /16 |
| 4 | Address Table Poisoning | AddrMan | ✓ Protected — bootstrap verification |
| 5 | Eviction Domination | Runtime | ⚠ Partial — 85/117 могут быть вытеснены |
| 6 | Reputation Faking | SubnetTracker | ⚠ Partial — зависит от PQ signature |
| 7 | Ban List Exhaustion | Connection | ✗ VULNERABLE — unbounded HashMap |
| 8 | Requests Queue Buildup | Peer | ✗ VULNERABLE — unbounded HashMap |
| 9 | Clock Divergence | Bootstrap | ✓ Protected — median + hardcoded match |

---

## Findings

### CRITICAL: None

Eclipse Attack на bootstrap практически невозможен при текущей архитектуре.

### HIGH

**H1: BanList unbounded growth**

```rust
// connection.rs
pub fn ban(&mut self, entry: BanEntry) {
    self.bans.insert(entry.addr, entry);  // No size limit
}
```

**Attack:** Protocol violations от 1000+ IP → memory exhaustion.
**Fix:** `const MAX_BANS: usize = 100_000;` + FIFO eviction.

**H2: requests_in_flight unbounded**

```rust
// peer.rs
pub requests_in_flight: HashMap<Hash, Instant>,  // No limit
```

**Attack:** GetData без ответа → per-peer memory growth.
**Fix:** `const MAX_INFLIGHT: usize = 10_000;` + drop oldest.

**H3: Incomplete eviction protection**

```
Protected: 32 peers
Vulnerable: 117 - 32 = 85 peers
```

**Attack:** 85+ malicious inbound → runtime Eclipse.
**Fix:** Увеличить protected categories до 50+.

### MEDIUM

**M1: SubnetTracker unbounded HashMaps**

```rust
// subnet.rs
reputations: HashMap<Subnet16, SubnetReputation>,     // ~65535 max
signer_subnets: HashMap<Hash, Subnet16>,              // Unbounded
```

**Fix:** Periodic pruning + memory limits.

**M2: P2P Gossip Age Bypass**

```rust
// PeerHistory
pub fn age_score(&self) -> u64 {
    self.duration_tau2()  // Only duration
}
```

**Attack:** Botnet 60+ days → high age_score для Sybil.
**Mitigation:** Presence signature verification.

### LOW

None significant.

---

## Чеклист верификации

```
[✓] Eclipse: full bootstrap on every restart (startup.rs)
[✓] Eclipse: 100 peers, 25+ /16 subnets required
[✓] Eclipse: hardcoded nodes must match median ±1%
[✓] Eclipse: netgroup diversity for runtime (eviction.rs)
[✗] Memory: BanList unbounded
[✗] Memory: requests_in_flight unbounded
[✓] Memory: known_inv bounded (100k per peer)
[⚠] Slots: eviction защищает только 32/117
[✓] Rate: все message types covered
[✓] Rate: per-peer limiting
```

---

## Verdict

**Eclipse Attack Risk: LOW**

Montana обеспечивает сильную защиту от классических Eclipse атак через:
1. 100-peer bootstrap verification
2. 25+ subnet diversity requirement
3. Hardcoded anchor nodes
4. Cryptographic bucketing

**DoS Risk: MEDIUM-HIGH**

Unbounded collections (BanList, requests_in_flight) создают vectors для memory exhaustion.

---

## Recommendations

| Priority | Action | File | Effort |
|----------|--------|------|--------|
| P0 | Add MAX_BANS limit | connection.rs | Low |
| P0 | Add MAX_INFLIGHT limit | peer.rs | Low |
| P1 | Increase eviction protection to 50+ | eviction.rs | Medium |
| P1 | Add per-subnet connection limits | connection.rs | Medium |
| P2 | SubnetTracker memory pruning | subnet.rs | Low |

---

## Conclusion

Архитектура Montana устойчива к Eclipse Attack на уровне bootstrap. Основные уязвимости — DoS через unbounded collections. Рекомендуется hardening перед production deployment.

```
[ ] SAFE — можно продолжать
[✓] NEEDS_FIX — исправить DoS vectors перед production
```
