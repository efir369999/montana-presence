# Security Audit: Network Layer (net/)

**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 08.01.2026 00:00 UTC

---

## 1. Понимание архитектуры

Montana — это ACP (Atemporal Coordinate Presence), где «вес» и консенсус привязаны не к вычислительным ресурсам, а к **реальному времени присутствия** (подписи принимаются только в текущем τ₂/τ₁). Сетевой слой в этой модели — критичен для **liveness** (доставка подписей/tx в окно τ₂ и grace period) и для корректного bootstrap (чтобы новый узел не принял ложное представление о сети).

Ключевые следствия для безопасности сети:
- **Атаки на liveness** (eclipse, деградация gossip, перегрузка) важнее «переписывания истории».
- Консенсусная безопасность в основном держится на криптографии и «время = ресурс», но **сетевой слой** должен обеспечивать ограничение ресурсов (CPU/RAM/FD) и разнообразие соединений.
- Bootstrap и time-consensus должны быть устойчивы к изоляции и к «poisoning» адресной базы.

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| `Montana ACP/montana/src/net/mod.rs` | - | ре-экспорты компонентов net/ |
| `Montana ACP/montana/src/net/types.rs` | - | константы лимитов, типы сообщений/состояний |
| `Montana ACP/montana/src/net/message.rs` | - | wire message enum, max_size per command |
| `Montana ACP/montana/src/net/protocol.rs` | - | main P2P loop, handshake, relay/inv, size checks |
| `Montana ACP/montana/src/net/connection.rs` | - | лимиты соединений, per-ip/netgroup, bans, retry |
| `Montana ACP/montana/src/net/peer.rs` | - | состояние peer, bounded known_inv, rate limits, flow control |
| `Montana ACP/montana/src/net/addrman.rs` | - | addrman с бакетами, anti-poisoning, persistence size cap |
| `Montana ACP/montana/src/net/inventory.rs` | - | relay cache, bounded sets, per-peer request cap |
| `Montana ACP/montana/src/net/rate_limit.rs` | - | token buckets + global adaptive subnet limiter |
| `Montana ACP/montana/src/net/eviction.rs` | - | многоуровневая защита слотов + eviction |
| `Montana ACP/montana/src/net/feeler.rs` | - | feeler соединения + addr response cache |
| `Montana ACP/montana/src/net/discouraged.rs` | - | rolling bloom discouraged set |
| `Montana ACP/montana/src/net/noise.rs` | - | Noise XX + ML-KEM-768 гибрид |
| `Montana ACP/montana/src/net/encrypted.rs` | - | EncryptedStream поверх Noise |
| `Montana ACP/montana/src/net/dns.rs` | - | DNS seeds + fallback IPs |
| `Montana ACP/montana/src/net/hardcoded_identity.rs` | - | hardcoded nodes: IP→ML-DSA-65 pubkey |
| `Montana ACP/montana/src/net/bootstrap.rs` | - | bootstrap verification model |
| `Montana ACP/montana/src/net/verification.rs` | - | pre-network verification client |
| `Montana ACP/montana/src/net/subnet.rs` | - | subnet reputation tracking |
| `Montana ACP/montana/src/net/sync.rs` | - | headers-first sync, orphan pool, late signatures |

---

## 3. Attack Surface

- **Inbound TCP connections**: `protocol.rs` listener_loop, handshake (Noise) и дальнейший приём сообщений.
- **Wire message parsing**: magic/length/checksum + bincode decode.
- **Inventory/gossip**: `Inv/GetData` и relay.
- **Addr/AddrMan**: приём адресов, адресная база, DNS seeds/fallback.
- **Bootstrap verification** (до старта сети): `verification.rs` + `bootstrap.rs` + hardcoded identity.
- **Global subnet limiter**: контроль на входе/выходе (Erebus).

---

## 4. Найденные уязвимости

### [HIGH] Несогласованные лимиты размера сообщений (DoS/функциональная деградация, расхождение спецификации)

**Файл:** `Montana ACP/montana/src/net/types.rs:108-115` + `Montana ACP/montana/src/net/protocol.rs:1243-1276` + `Montana ACP/montana/src/net/verification.rs:696-737`

**Уязвимый код:**
- В `types.rs` явно указано: общий лимит сообщения `MESSAGE_SIZE_LIMIT = 2MB`, `inv` до ~1.8MB.
- В `protocol.rs` ранняя проверка читает `len` и сравнивает **с `MAX_TX_SIZE` (1MB)** до того, как определён тип сообщения:
  - `if len > MAX_TX_SIZE { ... }`
- В `verification.rs` (pre-network bootstrap client) та же логика: `if length > MAX_TX_SIZE { ... }`.

**Вектор атаки:**
1. Атакующий (или просто честный peer) отправляет легитимный `inv` близкий к `MAX_INV_MSG_SIZE` (~1.8MB).
2. Узел отвергает кадр на раннем этапе, т.к. 1.8MB > 1MB.
3. Результат — систематический отказ от части протокола (и потенциальная деградация синхронизации/relay) при нормальном использовании.

**Импакт:**
- **Protocol mismatch / self-DoS:** узел не способен принимать сообщения, которые сам протокол допускает.
- **Повышенная вероятность деградации gossip/sync:** при большом инвентаре, особенно на старте/в bursts.

**Сложность:** низкая (любой peer может послать большой `inv`, без обхода криптографии).

**PoC сценарий:**
- Не привожу эксплуатационные шаги. Достаточно сконструировать `Inv` на ~50k items в рамках `MAX_INV_SIZE`.

**Рекомендации:**
- В ранней проверке использовать `MESSAGE_SIZE_LIMIT`, а не `MAX_TX_SIZE`.
- После десериализации дополнительно проверять per-command лимит через `Message::max_size_for_command()` (это уже делается). Аналогично — в `verification.rs`.

---

### [MEDIUM] Неконсистентные комментарии/оценки памяти в `sync.rs` (риск неверного hardening-а)

**Файл:** `Montana ACP/montana/src/net/sync.rs:13-23` и `Montana ACP/montana/src/net/types.rs:133-136`

**Описание:**
- `sync.rs` утверждает: «Each orphan is up to 4MB», что даёт 400MB worst case.
- `types.rs` фиксирует `MAX_SLICE_SIZE = 8KB` и рассчитывает orphan pool как 800KB.

**Импакт:**
- Это не прямая эксплуатационная уязвимость, но **опасный сигнал**: либо лимит реально где-то выше, либо документация/комментарии неверны. В обоих случаях можно ошибиться в настройках и пропустить DoS риск.

**Рекомендации:**
- Синхронизировать комментарии и реальные лимиты.
- Добавить unit test/assert, что wire decoder + `Message::max_size_for_command("slice")` реально ограничивает slice до `MAX_SLICE_SIZE`.

---

### [HIGH] Bootstrap hardcoded trust превращается в SPOF (availability)

**Файл:** `Montana ACP/montana/src/net/hardcoded_identity.rs:40-66`

**Уязвимость:**
- В mainnet/testnet определён фактически **1 hardcoded node**.
- Модель bootstrap/verification требует 75% ответов hardcoded. При 1 узле это означает: если он недоступен, bootstrap **всегда падает**.

**Импакт:**
- Целенаправленный DoS (или просто outage) одного адреса блокирует новые подключения/рестарты узлов.

**Сложность:** низкая для DoS по доступности.

**Рекомендации:**
- Увеличить набор hardcoded узлов (5+ минимум, 10+ лучше) и гео/ASN diversity.
- Подумать о fallback режиме (например: если hardcoded недоступны, но сеть уже синхронизирована локально — позволять стартовать с повышенными warning’ами, либо использовать pinned checkpoints).

---

## 5. Атаки, которые НЕ работают

- **«Подделать presence» через сеть**: не работает без подделки ML-DSA-65 или без возможности ретроактивно вставить подпись в закрытый τ₂ (привязка prev_slice_hash и окно времени).
- **MITM чтение/подмена трафика**: при корректной реализации Noise XX + hybrid ключей пассивная прослушка/подмена контента должна быть затруднена; остаётся DoS по доступности.

---

## 6. Рекомендации

- Привести ранние size-checks в `protocol.rs` и `verification.rs` к единому правилу:
  - первичный лимит: `MESSAGE_SIZE_LIMIT`.
  - вторичный лимит: per-command `Message::max_size_for_command()`.
- Согласовать лимиты и комментарии в `sync.rs`/`types.rs`, добавить тесты на реальные лимиты.
- Срочно расширить пул hardcoded узлов и обеспечить разнообразие.

---

## 7. Вердикт

[X] HIGH — есть серьёзные уязвимости

