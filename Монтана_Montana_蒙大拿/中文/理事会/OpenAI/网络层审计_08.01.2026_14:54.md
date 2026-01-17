# Security Audit: Montana Network Layer (net/)

**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 08.01.2026 14:54 UTC

---

## 1. Понимание архитектуры

Montana — это ACP: сеть фиксирует «присутствие во времени» через регулярные подписи (τ₁/τ₂), которые распространяются в реальном времени по P2P. Безопасность консенсуса опирается на (a) криптографическую неподделываемость, (b) привязку к текущему τ₂ (prev_hash / сетевое окно), (c) eventual consistency через fork-choice.

Следствие для сетевого слоя: ключевая цель сети — обеспечить доставку и валидацию внешних данных (подписей/слайсов/tx) в bounded-режиме и не дать атакующему:
- изолировать узел на старте (bootstrap) или во время работы (eclipse/addrman poisoning)
- исчерпать ресурсы (mem/cpu/bandwidth) через сообщения, очереди, инвентори
- подменить доверенные источники на старте (hardcoded bootstrap anchors)

---

## 2. Изученные файлы

Сетевой слой `montana/src/net/` (12,330 LOC):
- `net/message.rs` (168)
- `net/encrypted.rs` (570)
- `net/types.rs` (658)
- `net/serde_safe.rs` (266)
- `net/protocol.rs` (1506)
- `net/verification.rs` (848)
- `net/dns.rs` (266)
- `net/feeler.rs` (256)
- `net/discouraged.rs` (286)
- `net/sync.rs` (665)
- `net/bootstrap.rs` (1413)
- `net/startup.rs` (184)
- `net/subnet.rs` (444)
- `net/eviction.rs` (347)
- `net/mod.rs` (82)
- `net/inventory.rs` (705)
- `net/hardcoded_identity.rs` (203)
- `net/noise.rs` (898)
- `net/rate_limit.rs` (879)
- `net/connection.rs` (509)
- `net/peer.rs` (438)
- `net/addrman.rs` (739)

Связанные файлы:
- `src/types.rs`, `src/crypto.rs`, `src/db.rs`, `src/nmi.rs`, `src/nts.rs`

Инструменты/утилиты:
- `src/bin/attacker.rs` (stress-тест)

---

## 3. Attack Surface

- **Bootstrap / Startup verification**: `net/startup.rs` → `net/verification.rs` → `net/bootstrap.rs`.
  - hardcoded challenge-response
  - сбор P2P адресов через GetAddr / Addr
  - принятие network time (median) и median height

- **Долгоживущая P2P-сеть**: `net/protocol.rs`.
  - inbound/outbound TCP
  - Noise XX + ML-KEM (шифрование/аутентификация транспорта)
  - обработка сообщений (Version/Verack/Addr/Inv/GetData/Slice/Tx/Presence)

- **Механизмы устойчивости**:
  - connection limits / netgroup / per-IP (`net/connection.rs`)
  - eviction защищённых слотов (`net/eviction.rs`)
  - AddrMan bucket system (`net/addrman.rs`) + feeler (`net/feeler.rs`)
  - rate limit per peer + subnet-level (fast/slow) (`net/rate_limit.rs`)
  - bounded collections (`net/serde_safe.rs`, `net/message.rs`)

---

## 4. Найденные уязвимости

### [CRITICAL] Bootstrap MITM: подпись hardcoded узла не привязана к `VersionPayload`

**Суть:** протокол `AuthChallenge`/`AuthResponse` предполагает, что hardcoded узел доказывает идентичность подписью, но в коде проверяется подпись только над `challenge`, а поля `version` (высота, timestamp, best_slice, etc.) не входят в подписанное сообщение.

**Уязвимый код (проверка подписи по одному challenge):**
- `montana/src/net/verification.rs:493-515` — подпись проверяется функцией `verify_hardcoded_response(&challenge, &signature)` и затем используется `version`.
- `montana/src/net/hardcoded_identity.rs:85-112` — `verify_hardcoded_response()` проверяет `verify_mldsa65(pubkey, challenge, signature)`.

**Уязвимый код (hardcoded узел подписывает только challenge):**
- `montana/src/net/protocol.rs:1175-1204` — `sign_mldsa65(secret_key, &challenge)` и отправка `AuthResponse { version, signature }`.

**Почему это важно:** на старте именно bootstrap-верификация определяет, чему узел доверяет как «правде» о сети (высота/время/seed peers). Если подпись не связывает `version` с `challenge`, атакующий «на проводе» может сохранить валидную подпись на challenge, но подменить `VersionPayload` (с высотой/временем/параметрами) в транзите.

**Импакт:** высокий риск некорректного bootstrap (неверная высота/время/peer-discovery), что может привести к:
- изоляции узла (eclipse-like) на этапе запуска
- выбору неправильного chain-tip/сегмента сети
- отказу в запуске из‑за «clock divergence» или «height divergence» (liveness)

**Сложность:** средняя для сетевого противника на пути (ISP/BGP/локальная сеть) или при наличии вредоносного прокси; не требует компрометации приватного ключа hardcoded узла.

**Проверка председателя:** ПОДТВЕРЖДЕНО по коду: подпись проверяется только над `challenge` и никак не включает `version`.

**Рекомендация исправления:**
- Подписывать и проверять **контекст + challenge + сериализованный VersionPayload** (и/или transcript):
  - `sig_msg = "Montana.HardcodedAuth.v1" || challenge || postcard(version)`
  - проверять `verify_mldsa65(pubkey, sig_msg, signature)`
- Дополнительно: рассмотреть перенос bootstrap-канала поверх `EncryptedStream` (Noise), чтобы исключить MITM в принципе.

---

### [HIGH] Централизация bootstrap: фактически 1 hardcoded IP и пустые DNS seeds

**Суть:** документы декларируют набор seed/hardcoded узлов и их разнообразие. В текущем коде:
- DNS seeds пусты (комментарии-заглушки)
- fallback IP содержит 1 адрес
- hardcoded идентичности mainnet содержат 1 узел

**Доказательства:**
- `montana/src/net/dns.rs:8-32` — `DNS_SEEDS` пустой, `FALLBACK_IPS` содержит один адрес.
- `montana/src/net/hardcoded_identity.rs:40-66` — `MAINNET_HARDCODED` содержит один узел.

**Импакт:** при таком наборе «trusted core» становится фактически единственной точкой отказа:
- DoS/недоступность узла → bootstrap деградирует/ломается
- регуляторные/инфраструктурные события вокруг одного провайдера/географии → системный риск

**Сложность:** низкая (противнику достаточно бить в доступность одного узла).

**Проверка председателя:** ПОДТВЕРЖДЕНО по коду.

**Рекомендация:** расширить список hardcoded узлов (минимум 5–10), реально включить DNS seeds, обеспечить юрисдикционное/AS/гео разнообразие.

---

### [MEDIUM] Несогласованность лимитов размера сообщений: в `protocol.rs` глобальный лимит = `MAX_TX_SIZE` (1MB), а в `net/types.rs` заявлен 2MB и `inv` до ~1.8MB

**Суть:** `net/types.rs` декларирует `MESSAGE_SIZE_LIMIT = 2MB` и `MAX_INV_MSG_SIZE ≈ 1.8MB`, но `protocol.rs` делает ранний reject любых payload > `MAX_TX_SIZE` (1MB) независимо от команды.

**Доказательства:**
- `montana/src/net/types.rs:111-140` — 2MB лимит и `MAX_INV_MSG_SIZE`.
- `montana/src/net/protocol.rs:1249-1263` и `1329-1334` — ранняя проверка `if len > MAX_TX_SIZE`.

**Импакт:** функциональная несовместимость со «спецификацией» внутри самого репо:
- крупные `inv` сообщения по верхней границе фактически не проходят
- возможна деградация синхронизации/relay при больших батчах

**Сложность:** низкая (это детерминированное поведение кода).

**Проверка председателя:** ПОДТВЕРЖДЕНО по коду.

**Рекомендация:**
- заменить ранний лимит на `MESSAGE_SIZE_LIMIT`, либо
- привести `MAX_*` константы к тому, что реально разрешено ранней проверкой.

---

### [MEDIUM] `ip_votes` заявлен как bounded, но не очищается на disconnect → потенциальный рост памяти

**Суть:** комментарий говорит «max size = MAX_OUTBOUND», но ключи `SocketAddr` добавляются при каждом (outbound) Version и нигде не удаляются при разрыве соединения.

**Доказательства:**
- Определение + заявление bounded: `montana/src/net/protocol.rs:210-216`.
- Вставка голоса: `montana/src/net/protocol.rs:884-914`.
- Cleanup на disconnect удаляет только `sent_nonces`, но не `ip_votes`: `montana/src/net/protocol.rs:837-844`.

**Импакт:** потенциальный медленный рост HashMap при длительной работе и смене outbound адресов.

**Сложность:** низкая (естественная динамика сети + перезапросы).

**Проверка председателя:** ПОДТВЕРЖДЕНО по коду.

**Рекомендация:**
- удалять `ip_votes[peer.addr]` при `PeerDisconnected`/disconnect,
- либо хранить bounded LRU на `MAX_OUTBOUND` последних адресов.

---

### [LOW] Хранение Noise static secret key не соответствует комментарию («encrypted»), хранится как raw 32 bytes

**Суть:** в комментарии указано «encrypted with a derived key», но фактически ключ пишется как `std::fs::write(noise_key.bin, keypair.secret)`.

**Доказательства:**
- `montana/src/net/encrypted.rs:406-435`.

**Импакт:** риск при локальной компрометации/backup leaks; смягчается правами `0600`.

**Сложность:** зависит от локального противника.

**Проверка председателя:** ПОДТВЕРЖДЕНО по коду.

**Рекомендация:** либо зашифровать ключ на диске (например, OS keychain), либо поправить комментарий, чтобы не вводил в заблуждение.

---

## 5. Атаки, которые НЕ работают (или работают хуже ожидаемого)

- **«Просто спамить большие inv до 1.8MB»**: верхняя граница `MAX_INV_MSG_SIZE` теоретически есть, но `protocol.rs` режет всё >1MB ранней проверкой (`MAX_TX_SIZE`).

- **`src/bin/attacker.rs` как готовый эксплойт**: этот бинарь сериализует сообщения через `bincode` и работает без Noise, тогда как текущая сеть в `protocol.rs` использует `postcard` поверх `EncryptedStream` (Noise). В текущем виде это скорее исторический stress-тест/заготовка и не отражает реальный on-wire протокол.

---

## 6. Рекомендации

- **Закрыть CRITICAL bootstrap MITM**:
  - изменить `AuthResponse` так, чтобы подпись покрывала `challenge || VersionPayload` с domain separation.
  - (опционально, сильнее) проводить `VerificationClient` поверх `EncryptedStream`.

- **Убрать single point of failure в bootstrap**:
  - заполнить `DNS_SEEDS`, расширить `FALLBACK_IPS`, добавить 5–10+ hardcoded identities.

- **Согласовать лимиты сообщений**:
  - использовать `MESSAGE_SIZE_LIMIT` как ранний лимит в `protocol.rs`/`verification.rs` или уменьшить max-команды.

- **Сделать `ip_votes` реально bounded**:
  - удаление на disconnect или bounded LRU.

- **Уточнить/исправить хранение Noise secret**:
  - либо реализовать шифрование на диске, либо исправить комментарий.

---

## 7. Вердикт

[x] **CRITICAL — есть уязвимость, позволяющая сломать доверие bootstrap (MITM при старте)**
[ ] HIGH — есть серьёзные уязвимости
[ ] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено
