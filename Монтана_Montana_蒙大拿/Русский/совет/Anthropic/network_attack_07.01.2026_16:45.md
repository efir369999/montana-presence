# Adversarial Review: Montana Network Layer

**Модель:** Claude Opus 4.5
**Компания:** Anthropic
**Дата:** 07.01.2026 16:45 UTC

---

## Executive Summary

Проведён анализ сетевого слоя Montana (`/Montana ACP/montana/src/net/`) на устойчивость к атакам. Проверены 5 критических векторов из шаблона Council.

**Общий вердикт:** NEEDS_FIX — обнаружено 2 уязвимости среднего уровня.

---

## Роль

**Атакующий** с неограниченными ресурсами: ботнеты, множество IP-адресов из разных /16 подсетей, неограниченное время.

**Цель:** Eclipse жертвы, исчерпание ресурсов, нарушение консенсуса.

---

## Attack Surface

- **External inputs:** TCP соединения, P2P сообщения, адреса от peers
- **Trust boundaries:** inbound peers (недоверенные), outbound peers (частично доверенные)
- **Critical assets:** consensus view, address manager state, connection slots

---

## TIER 0: КРИТИЧЕСКИЕ ВЕКТОРЫ

### 1. Eclipse Attack

**Файлы:** `addrman.rs`, `eviction.rs`, `connection.rs`

#### Проверенные защиты

| Механизм | Статус | Код |
|----------|--------|-----|
| Netgroup diversity (/16) | PROTECTED | `connection.rs:253-257` |
| Cryptographic bucketing | PROTECTED | `addrman.rs:445-475` |
| Self-connection detection | PROTECTED | `protocol.rs:768-772` |
| Eviction multi-layer | PROTECTED | `eviction.rs:65-126` |
| Anchor connections | NOT IMPLEMENTED | — |

#### Attempted Attacks

| # | Attack | Result |
|---|--------|--------|
| 1 | Заполнить NEW table вредоносными адресами | MITIGATED — cryptographic bucketing распределяет по source |
| 2 | Продвинуть в TRIED через fake connections | MITIGATED — требует реальное TCP соединение |
| 3 | Occupy all outbound slots from same /16 | PROTECTED — MAX_PEERS_PER_NETGROUP = 2 |
| 4 | Gaming eviction (fake low latency) | PROTECTED — 6-layer protection (28 slots) |
| 5 | **Post-restart eclipse** | **VULNERABLE** — нет anchor connections |

#### Finding: Anchor Connections Missing

**Severity:** MEDIUM

**Описание:**
После рестарта узла все outbound соединения выбираются заново из AddrMan. Если атакующий заранее заполнил NEW/TRIED таблицы вредоносными адресами (даже распределёнными по разным /16), после рестарта жертва может подключиться к 8 узлам атакующего.

**Эксплуатация:**
```
1. Атакующий получает IPs в 8+ разных /16 подсетях
2. Заполняет AddrMan жертвы через Addr сообщения (1000 addr/msg)
3. Ждёт рестарт жертвы (обновление, сбой)
4. Жертва выбирает 8 outbound из отравленного AddrMan
5. Все 8 outbound → атакующий, eclipse достигнут
```

**Mitigating factors:**
- Требует 8+ IPs в разных /16 (дорого, но достижимо)
- Rate limiting на Addr (0.1/sec sustained) замедляет отравление
- Жертва должна перезапуститься

**Рекомендация:**
Реализовать anchor connections — сохранять 2 последних успешных outbound peers и подключаться к ним первыми после рестарта. Bitcoin Core: `net.cpp:2098-2150`.

---

### 2. Memory Exhaustion

**Файлы:** `protocol.rs`, `sync.rs`, `rate_limit.rs`

#### Проверенные защиты

| Механизм | Статус | Код |
|----------|--------|-----|
| Flow control BEFORE read | PROTECTED | `protocol.rs:647-658` |
| Early size check (4MB) | PROTECTED | `protocol.rs:1114-1119` |
| Bounded deserialize | PROTECTED | `protocol.rs:1138-1141` |
| OrphanPool bounded | PROTECTED | `sync.rs:38` (100 orphans) |
| BoundedInvSet | PROTECTED | `peer.rs:35-87` (100k items) |
| AddrMan file limit | PROTECTED | `addrman.rs:29` (16MB) |

#### Attempted Attacks

| # | Attack | Result |
|---|--------|--------|
| 1 | Send msg with length=2^32 | PROTECTED — early check vs MAX_SLICE_SIZE (4MB) |
| 2 | Flow control bypass | PROTECTED — check BEFORE read_message() |
| 3 | Orphan slice flooding | PROTECTED — MAX_ORPHANS=100, FIFO eviction |
| 4 | Known inventory exhaustion | PROTECTED — BoundedInvSet, FIFO eviction |
| 5 | Malicious bincode length prefix | PROTECTED — bounded deserialize with_limit() |

#### Verdict: SAFE

Память защищена на всех уровнях. Flow control исправлен после Gemini audit (комментарий в `protocol.rs:635`).

---

## TIER 1: ВЫСОКИЕ ВЕКТОРЫ

### 3. Connection Slot Exhaustion

**Файлы:** `connection.rs`, `eviction.rs`

#### Attempted Attacks

| # | Attack | Result |
|---|--------|--------|
| 1 | Occupy all 117 inbound slots | PARTIAL — eviction может освободить |
| 2 | Gaming eviction via fake metrics | PROTECTED — 6-layer, 28 protected slots |
| 3 | Rapid connect/disconnect flooding | **POTENTIAL** — нет per-IP rate limit |

#### Finding: Connection Rate Limiting Per-IP

**Severity:** LOW

**Описание:**
Нет явного rate limiting на новые TCP соединения от одного IP. Атакующий может быстро открывать и закрывать соединения, создавая нагрузку на listener loop.

**Mitigating factors:**
- Exponential backoff в `connection.rs:139-173` работает только для outbound
- TCP handshake сам по себе ограничивает скорость
- OS-level connection limits

**Рекомендация:**
Добавить per-IP connection rate limit в listener_loop: max 5 connections per IP per minute.

---

### 4. Sync DoS

**Файлы:** `sync.rs`, `bootstrap.rs`, `protocol.rs`

#### Attempted Attacks

| # | Attack | Result |
|---|--------|--------|
| 1 | GetSlices amplification | PROTECTED — `count.min(500)` в `protocol.rs:1036` |
| 2 | GetData abuse | PROTECTED — rate_limits.getdata (1000 burst, 5/sec) |
| 3 | **Headers flooding** | **POTENTIAL** — нет rate limit на SliceHeaders |

#### Finding: Headers Rate Limiting

**Severity:** MEDIUM

**Описание:**
Нет явного rate limit на получение SliceHeaders сообщений. Атакующий может слать большие headers responses, вызывая CPU exhaustion на валидации.

**Проверка в коде:**
- `Message::SliceHeaders` не имеет rate limiter в `PeerRateLimits`
- MAX_HEADERS_SIZE = 512KB (2000 headers × 256 bytes)
- Обработка headers требует валидации каждого

**Эксплуатация:**
```
1. Подключиться к жертве
2. Слать GetHeaders запросы
3. Отвечать 2000 headers каждый раз
4. Жертва тратит CPU на валидацию
5. Повторить с множества соединений
```

**Рекомендация:**
Добавить HeadersRateLimiter в PeerRateLimits: 5000 headers burst, 10/sec sustained.

---

### 5. Rate Limit Bypass

**Файл:** `rate_limit.rs`

#### Attempted Attacks

| # | Attack | Result |
|---|--------|--------|
| 1 | Multiple connections bypass | CONFIRMED — rate limits per-connection |
| 2 | Token bucket timing | SAFE — refill() calls Instant::now() |
| 3 | Message type gaps | PARTIAL — Headers/Presence not rate limited |

#### Finding: Per-Connection vs Per-IP

**Severity:** LOW

**Описание:**
Rate limits в `PeerRateLimits` применяются per-connection. Атакующий с 10 соединениями получает 10× burst capacity.

**Пример:**
- Addr: 1000 burst per connection
- 10 connections = 10,000 addr burst
- Это ускоряет AddrMan poisoning

**Mitigating factors:**
- MAX_INBOUND = 117 ограничивает масштаб
- Netgroup diversity (/16) ограничивает connections per attacker

**Рекомендация:**
Рассмотреть глобальный per-IP rate tracker для критических message types.

---

## Checklist Results

```
[x] Eclipse: netgroup diversity работает
[ ] Eclipse: anchor connections есть           ← MISSING
[x] Memory: flow control до allocation
[x] Memory: orphan pool bounded
[x] Memory: все collections bounded
[x] Slots: eviction защищает diversity
[ ] Sync: headers rate limited                 ← MISSING
[x] Sync: GetSlices rate limited
[ ] Rate: все messages covered                 ← PARTIAL
[x] Rate: per-IP limiting (partial via netgroup)
```

---

## Summary of Findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Missing anchor connections | MEDIUM | NEEDS_FIX |
| 2 | Headers not rate limited | MEDIUM | NEEDS_FIX |
| 3 | Connection rate per IP | LOW | CONSIDER |
| 4 | Per-connection vs per-IP rate | LOW | CONSIDER |

---

## Positive Observations

1. **Flow control**: Исправлен после Gemini audit, теперь блокирует read ПЕРЕД allocation
2. **Bounded collections**: Все структуры данных имеют лимиты с FIFO eviction
3. **Eviction system**: 6-layer protection делает gaming очень сложным
4. **Cryptographic bucketing**: SipHash24 с секретным ключом предотвращает bucket prediction
5. **Self-connection detection**: Nonce-based detection работает корректно
6. **Bounded deserialize**: bincode with_limit() везде где нужно

---

## Verdict

```
[ ] SAFE — можно продолжать
[x] NEEDS_FIX — исправить перед продолжением

Critical:  0
High:      0
Medium:    2 (anchor connections, headers rate limit)
Low:       2 (connection rate, per-IP rate)
```

---

## References

- Bitcoin Core anchor connections: `net.cpp:2098-2150`
- Bitcoin Core headers rate limit: `net_processing.cpp:HEADERS_DOWNLOAD_TIMEOUT_BASE`
- Erebus attack paper: https://erebus-attack.comp.nus.edu.sg/

---

*Report generated by Claude Opus 4.5 (Anthropic)*
*Security Council Review — Montana ACP*
