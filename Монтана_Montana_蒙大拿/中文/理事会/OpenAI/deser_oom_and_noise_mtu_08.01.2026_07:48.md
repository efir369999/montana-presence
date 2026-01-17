# Security Audit: Montana Network Layer (`montana/src/net`)

**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 08.01.2026 07:48 UTC

---

## 1. Понимание архитектуры

Montana (ACP) строит консенсус не через майнинг/стейкинг, а через **координатное присутствие во времени**:

- Узлы **доказывают присутствие** подписанием координат (кванты τ₁/τ₂) и распространением подписей через P2P gossip. Ценность подписи задаётся **бинарностью слота** и ограничением «сеть принимает только в текущем τ₂/τ₁».
- Каждые τ₂ (10 минут) формируется **слайс** (не “блок” в PoW смысле): он содержит `prev_hash` (хеш-цепь таймчейна), `presence_root` и `tx_root` (Merkle), и подпись победителя.
- Победитель τ₂ выбирается **детерминированной лотереей** из `seed = SHA3(prev_slice_hash || τ₂_index)`; цель — избежать grinding и «выигрышей из будущего», при этом результат одинаков у всех при одинаковом view.
- Fork-choice: первично сравнение по **ChainWeight** (кол-во/вес подписей присутствия), затем длина, затем tie-break по хешу головы.
- Безопасность упирается в (а) криптостойкость SHA3/ML-DSA/ML-KEM и (б) реализацию сетевой доставки/валидации, потому что ACP сильно чувствителен к **liveness/partition/eclipse** и к DoS на обработке сообщений.

Ключевое следствие для безопасности: атаки “как на блокчейн” (51% hashrate/MEV в PoW, long-range через стейк и т.п.) здесь в основном нерелевантны; основная поверхность — **P2P протокол, (де)сериализация, лимиты, bootstrap и time/partition-handling**.

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| `montana/src/net/addrman.rs` | 739 | AddrMan (new/tried buckets), selection, persistence |
| `montana/src/net/bootstrap.rs` | 1253 | BootstrapVerifier, time median, hardcoded vs gossip, peer age |
| `montana/src/net/connection.rs` | 509 | ConnectionManager, bans, netgroup/per-IP limits, backoff |
| `montana/src/net/discouraged.rs` | 286 | Rolling bloom discouraged set |
| `montana/src/net/dns.rs` | 266 | DNS seeds + fallback IPs |
| `montana/src/net/encrypted.rs` | 434 | Noise handshake wrapper, keypair load/save |
| `montana/src/net/eviction.rs` | 347 | Inbound eviction policy |
| `montana/src/net/feeler.rs` | 256 | Feeler probes + addr response cache |
| `montana/src/net/hardcoded_identity.rs` | 203 | Hardcoded node pubkeys + ML-DSA verify |
| `montana/src/net/inventory.rs` | 591 | Inv tracking, relay cache, per-peer in-flight limits |
| `montana/src/net/message.rs` | 217 | Message enum, per-command size caps |
| `montana/src/net/mod.rs` | 68 | module wiring/re-exports |
| `montana/src/net/noise.rs` | 893 | Hybrid Noise XX + ML-KEM-768 + ChaChaPoly |
| `montana/src/net/peer.rs` | 438 | Peer state machine, misbehavior, flow control hooks |
| `montana/src/net/protocol.rs` | 1652 | Wire framing, encrypted read/write, main loops |
| `montana/src/net/rate_limit.rs` | 1183 | Token buckets, FlowControl bytes counters, subnet limiter |
| `montana/src/net/startup.rs` | 184 | Always full bootstrap verification |
| `montana/src/net/subnet.rs` | 387 | Subnet reputation tracker |
| `montana/src/net/sync.rs` | 665 | Header/slice sync, orphan pool, late signatures |
| `montana/src/net/types.rs` | 573 | Constants, NetAddress, message size caps |
| `montana/src/net/verification.rs` | 847 | VerificationClient, hardcoded queries, subnet diversity |

---

## 3. Attack Surface

- Входящие TCP соединения → Noise handshake → расшифровка → разбор фрейма → `bincode::deserialize(Message)`.
- Любые `Vec<>`/`String` поля в `Message` и вложенных типах (Addr/Inv/…/SignedAddr/AuthResponse) — особенно в условиях нестрогих лимитов десериализации.
- Bootstrap/verification: доверие к hardcoded узлам (их количество/распределение), обработка подписанных списков адресов.
- Ограничители: per-IP, per-netgroup, token buckets, FlowControl (байтовый учёт очереди), eviction.
- Персистентные файлы (`addresses.dat`, `banlist.dat`, `noise_key.bin`) как локальная поверхность (supply chain / локальная компрометация / повреждение данных).

---

## 4. Найденные уязвимости

### [CRITICAL] Remote OOM/DoS через `bincode::deserialize` (unbounded allocations при малом размере сообщения)

**Файл:** `montana/src/net/protocol.rs:1351-1395` (аналогично для encrypted path: `1432-1481`)

**Уязвимый код:**

```rust
// ...
let mut data = vec![0u8; len];
reader.read_exact(&mut data).await?;

// ...
let msg: Message = bincode::deserialize(&data)?;
// ...
```

(см. `protocol.rs` строки 1376–1395 и 1474–1481).

**Суть:** размер payload ограничен (≤1MB), но `bincode` при десериализации может попытаться выделить память по внутренним length-prefix (например, для `Vec<>`/`String`) **гораздо больше**, чем фактический размер входного буфера. Это классическая проблема «малый буфер → огромная аллокация → OOM/kill процесса».

**Импакт:** удалённый отказ в обслуживании узла (crash/OOM), потенциально массовый DoS по сети.

**Сложность:** низкая (атакующему достаточно установить соединение и отправить корректно оформленный по фрейму пакет с “вредными” length-prefix внутри bincode-полей).

**PoC сценарий (безопасно, локально):**
- В изолированной среде (unit-test/фаззинг) прогонять `bincode::deserialize::<Message>` на синтетических байтах, содержащих завышенные длины для векторов/строк, и проверять, что до отказа происходит попытка большой аллокации.

**Рекомендации:**
- Использовать bincode с жёсткими лимитами/защитой от аллокаций (например, `Options::with_limit` и/или переход на декодер, который ограничивает container allocations).
- Дополнительно валидировать ожидаемые максимумы для `Vec`/`String` на уровне типов (например, фиксированная длина подписи, cap на количество элементов и т.п.) до выделения больших структур.

---

### [HIGH] Несовместимость MTU Noise (≈64KB) с протокольными лимитами (до 1MB): liveness/DoS

**Файл:**
- `montana/src/net/noise.rs:681-697`
- `montana/src/net/protocol.rs:1403-1425`

**Уязвимый код:**

```rust
// noise.rs
if plaintext.len() > MAX_NOISE_MESSAGE_SIZE - CHACHA_TAG_SIZE - 2 {
    return Err(NoiseError::MessageTooLarge { ... });
}
```

(см. `noise.rs` 681–688) и отправка единого фрейма:

```rust
// protocol.rs
let mut frame = Vec::with_capacity(12 + data.len());
frame.extend_from_slice(&PROTOCOL_MAGIC);
frame.extend_from_slice(&(data.len() as u32).to_le_bytes());
frame.extend_from_slice(&checksum);
frame.extend_from_slice(&data);
writer.write(&frame).await?;
```

(см. `protocol.rs` 1416–1425).

**Суть:** транспорт Noise запрещает plaintext > ~65KB, а протокол на уровне `Message` допускает большие payloads (Tx 1MB, Headers ~512KB и т.д.). Код не реализует фрагментацию/стриминг больших сообщений поверх Noise, но при этом пытается отправлять “одним куском”.

**Импакт:**
- Потеря живучести для больших сообщений: узлы не смогут корректно ретранслировать/синхронизировать части протокола при достижении больших размеров.
- В худшем случае — легковесный DoS на конкретных соединениях (провоцирование ошибок `MessageTooLarge`/`NoiseError` и разрывы соединений).

**Сложность:** низкая/средняя.

**Рекомендации:**
- Либо уменьшить протокольные лимиты до MTU Noise (и убрать недостижимые размеры), либо реализовать фрагментацию/сборку (chunking) поверх Noise transport.
- Сделать консистентную единую константу «max cleartext payload per encrypted frame» и проверять её ещё до сериализации/отправки.

---

### [HIGH] Отклонение от Noise spec: AAD игнорируется в AEAD (handshake transcript binding ослаблен)

**Файл:** `montana/src/net/noise.rs:105-134` и `noise.rs:193-205`

**Уязвимый код (признак):**

```rust
// CipherState::encrypt
cipher.encrypt(&nonce, plaintext)

// CipherState::decrypt
cipher.decrypt(&nonce, ciphertext)
```

При этом параметры `ad` передаются, но фактически не используются.

**Суть:** реализация декларирует “encrypt with handshake hash as AD”, но AEAD вызывается без AAD. Это потенциально ломает ожидаемые свойства привязки сообщений к транскрипту (а значит — часть аргументов безопасности “как у Noise”).

**Импакт:** от “деградации модели безопасности” до потенциальных протокольных атак на рукопожатие (зависит от деталей state machine и того, какие поля шифруются/когда).

**Сложность:** средняя (требует криптоаналитического/протокольного разбирательства, но сам факт несоответствия спецификации — серьёзный).

**Рекомендации:**
- Включить AAD корректно (`Payload { msg, aad }` в chacha20poly1305).
- Добавить тест-векторы/interop-тесты с эталонной реализацией Noise XX.

---

### [HIGH] FlowControl можно обойти из-за использования `estimated_size()` вместо реального размера

**Файл:** `montana/src/net/protocol.rs:897-902` + `montana/src/net/rate_limit.rs:304-380`

**Уязвимый код:**

```rust
let msg_size = msg.estimated_size();
peer.flow_control.add_recv(msg_size);
```

(см. `protocol.rs` 897–902).

**Суть:** байтовый учёт очереди/буфера зависит от приблизительной оценки, которую можно сильно занизить для реально больших сериализованных сообщений. Это снижает эффективность лимита `max_recv_queue` (5MB) и может приводить к переполнению памяти под нагрузкой.

**Импакт:** DoS по памяти/латентности на узле при высокой входящей нагрузке.

**Сложность:** средняя.

**Рекомендации:**
- В FlowControl добавлять **реальный `len`** из фрейма (до десериализации) и снимать его после обработки.
- Либо считать фактический `data.len()` после чтения (но до `deserialize`) и использовать его.

---

### [MEDIUM] Фактическая централизация bootstrap: 1 hardcoded node + пустые DNS seeds

**Файлы:**
- `montana/src/net/hardcoded_identity.rs:40-66` (вектор hardcoded узлов содержит 1 запись)
- `montana/src/net/dns.rs:8-32` (DNS seeds пусты; fallback IP фактически 1)
- `montana/src/net/verification.rs:144-188` (75% от hardcoded_count)

**Суть:** многие проверки и “стоимость атак” в документации и комментариях подразумевают десятки hardcoded/seed источников и разнообразие. В текущем состоянии кода:
- hardcoded узлов — 1,
- DNS seeds — пусто,
- fallback IP — 1.

Порог 75% становится “1 из 1”, что превращает hardcoded bootstrap в single point of failure.

**Импакт:** деградация eclipse/bootstrapping безопасности (в частности, при компрометации оператора hardcoded-узла или его инфраструктуры).

**Сложность:** средняя (зависит от компрометации/сетевой инфраструктуры), но стратегический риск высокий.

**Рекомендации:**
- Добавить независимых hardcoded операторов (разные AS/юрисдикции), заполнить DNS seeds.
- Перейти к порогам, которые “не деградируют” при малом N (например, минимум 3 независимых hardcoded для mainnet).

---

### [MEDIUM] Приватный Noise static key хранится в открытом виде (несоответствие комментарию)

**Файл:** `montana/src/net/encrypted.rs:270-315`

**Уязвимый код:**

```rust
// комментарий: "encrypted with a derived key"
std::fs::write(&key_path, &keypair.secret)?;
```

(см. `encrypted.rs` 270–299).

**Импакт:** при локальной компрометации диска/бэкапов злоумышленник получает static key и может имитировать идентичность узла в P2P.

**Сложность:** зависит от модели угроз (локальный доступ).

**Рекомендации:**
- Реально шифровать `noise_key.bin` (OS keychain/TPM/HSM/пароль+KDF), либо чётко зафиксировать, что это **не секрет** и не используется как “identity anchor” (что сейчас не похоже на правду).

---

### [LOW] Bincode deserialization без лимитов при загрузке `addresses.dat` / `banlist.dat`

**Файлы:**
- `montana/src/net/addrman.rs:100-115`
- `montana/src/net/connection.rs:56-71`

**Суть:** есть лимит на размер файла (1MB), но `bincode::deserialize(&data)` по-прежнему потенциально может попытаться выделить чрезмерную память по length-prefix. Это локальный DoS при повреждении/подмене файлов состояния.

**Рекомендации:** использовать “safe deserialize” с лимитами аллокаций/контейнеров.

---

## 5. Атаки, которые НЕ работают

- Классические “51%” PoW/PoS атаки (майнинг/стейк-гриндинг) неприменимы в лоб, потому что в Montana нет майнеров/валидаторов в стандартном смысле, а “вес” привязан к присутствию и к таймчейну.
- “MEV через порядок транзакций” частично ограничен детерминированным `tx_root` (порядок по хешу), хотя остаются сетевые/мемпул-аспекты.
- “Long-range переписывание истории” не выглядит тривиальным: таймчейн фиксируется хеш-цепью и подписью победителя, а присутствие привязано к реальному времени/окну τ₂.

---

## 6. Рекомендации

1. **Срочно закрыть CRITICAL DoS**: заменить `bincode::deserialize` на безопасный декодер/опции с ограничением аллокаций и размером контейнеров.
2. **Согласовать лимиты протокола и транспорта**: либо chunking поверх Noise, либо снижение `MAX_TX_SIZE/MAX_HEADERS_SIZE/...` до допустимого размера кадра.
3. **Привести Noise-реализацию к спецификации**: AAD, корректный nonce-handling (инкремент после успеха), тест-векторы.
4. **Исправить FlowControl**: учитывать реальные байты фрейма.
5. **Bootstrap hardening**: увеличить число hardcoded/seed источников и сделать пороги устойчивыми при малом N.
6. **Локальная безопасность ключей**: зашифровать `noise_key.bin` или явно изменить модель идентичности.

---

## 7. Вердикт

[x] CRITICAL — есть уязвимости, позволяющие уничтожить сеть (по крайней мере через массовый DoS узлов)
[ ] HIGH — есть серьёзные уязвимости
[ ] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено
