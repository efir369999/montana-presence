# Верификация: Network Layer DoS Claims

**Дата верификации:** 08.01.2026
**Источник:** Google Gemini 3 Pro, `inventory_lock_dos_08.01.2026_12:00.md`
**Верификатор:** Председатель Совета

---

## V-001: Asymmetric Resource Exhaustion (Kyber768 Handshake)

**Заявлено:** HIGH — ботнет обходит subnet limiter, CPU exhaustion на Kyber768

**Файл:** `protocol.rs:395-441`

**Код существует:** Да

**Защиты:**

| Порядок | Проверка | Константа | Файл |
|---------|----------|-----------|------|
| 1 | Ban check | — | protocol.rs:397 |
| 2 | Subnet limiter | Two-tier adaptive | protocol.rs:410 |
| 3 | Inbound limit | MAX_INBOUND = 117 | types.rs:72 |
| 4 | Netgroup limit | MAX_PEERS_PER_NETGROUP = 2 | types.rs:83 |
| 5 | Per-IP limit | MAX_CONNECTIONS_PER_IP = 2 | types.rs:77 |
| 6 | Handshake | Только после всех проверок | protocol.rs:458 |

**Вердикт:** ALREADY_PROTECTED

**Обоснование:** Handshake запускается после 5 проверок. MAX_INBOUND = 117 ограничивает общее количество. MAX_PEERS_PER_NETGROUP = 2 ограничивает каждую /16 подсеть.

---

## V-002: AddrMan Write Lock DoS

**Заявлено:** MEDIUM — 1000 адресов блокируют write lock

**Файл:** `protocol.rs:970-983`

**Код существует:** Да

**Защиты:**

| Защита | Значение | Файл |
|--------|----------|------|
| MAX_ADDR_SIZE | 1000 | types.rs:168 |
| AddrRateLimiter | capacity=1000, rate=0.1/sec | rate_limit.rs:63 |
| SipHash | ~100ns per call | addrman.rs |

**Вердикт:** LOW (не MEDIUM)

**Обоснование:** Rate limiter 0.1/sec после burst. 1000 × SipHash = ~100μs под lock.

---

## Итог

| Заявлено | Реальный статус |
|----------|-----------------|
| HIGH: Asymmetric Resource Exhaustion | ALREADY_PROTECTED |
| MEDIUM: AddrMan Write Lock DoS | LOW |
