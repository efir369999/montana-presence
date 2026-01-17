**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 07.01.2026 10:49 UTC

---

## Область анализа

Сетевой слой Montana (Rust): `Montana ACP/montana/src/net/*` + обработчики событий в `montana/src/main.rs`.

Фокус — векторы из `Council/PROMPT_COUNSIL_TEMPLATE.md`:
- Eclipse Attack
- Memory Exhaustion
- Connection Slot Exhaustion
- Sync DoS
- Rate Limit Bypass

---

## TIER 0

### 1) Eclipse Attack

#### Что важно в протоколе
- Outbound-пиры считаются «более доверенными» (например, голосование за внешний IP учитывает только outbound; `net/protocol.rs`, блок `MIN_IP_VOTES`).
- Адресная книга (`AddrMan`) персистентна (`addresses.dat`) и переживает рестарт.

#### Слабые места в коде
1) **Продвижение адреса в TRIED происходит до успешного handhsake**
- В `net/protocol.rs` после успешного TCP connect вызывается `addresses.mark_connected(&socket_addr)` **до** `handle_connection()`/завершения рукопожатия.
- Следствие: «фейковая успешность» = достаточно принимать TCP, даже если Version/Verack не завершены или дальше соединение будет разорвано.

2) **Нет "anchor connections" между рестартами**
- В коде присутствует только периодический `save(addresses.dat)` и `save(banlist.dat)` (например, `net/protocol.rs::maintenance_loop`), но нет отдельного механизма закрепления last-known-good outbound peers.
- Это усиливает сценарий «ждать рестарт жертвы» из шаблона: после рестарта выбор адресов снова пойдёт через `AddrMan::select()`.

3) **Feeler/кеш ответов адресов заявлены, но не интегрированы**
- `FeelerManager` и `AddrResponseCache` существуют в `net/feeler.rs`, но поиск по репозиторию показывает, что они нигде не используются (кроме re-export в `net/mod.rs`).
- Следствие: защита качества addr-таблицы/анти-фингерпринтинг по GetAddr выглядит «задекларированной», но фактически не работает.

4) **Пер-пирная лимитация Addr легко масштабируется Sybil’ом**
- `Addr` ограничен на обработку через token bucket *на peer* (`net/protocol.rs` + `net/rate_limit.rs`).
- Атакующий множит соединения → множит «первичный burst» (1000 адресов) и скорость пополнения.

#### Как эксплуатировать
- **Шаг A: Poison NEW**
  - Поднять N нод(ы) атакующего с IP в разных /16.
  - На каждой — установить TCP listener и отвечать так, чтобы жертва могла подключиться.
  - С каждого соединения (после handshake) слать `Addr` с ~1000 адресов атакующей инфраструктуры. Повторять через новые соединения для обнуления token-bucket.

- **Шаг B: Продвинуть в TRIED через fake connections**
  - Добиться, чтобы жертва делала outbound dial на адреса атакующего.
  - Достаточно, чтобы TCP connect прошёл: жертва вызывает `addresses.mark_connected()` до handshake → адрес быстро попадает в TRIED.
  - На стороне атакующего можно *не завершать* handshake (или завершать, но не обслуживать sync), при этом адресная книга у жертвы «поверит».

- **Шаг C: Рестарт/перехват outbound**
  - После рестарта жертва выбирает адреса через `AddrMan::select()` (50/50 new vs tried).
  - Если TRIED и NEW существенно заполнены адресами атакующего, вероятность outbound→attacker высокая.

#### Итоговый риск
- **Высокий**: ключевой баг — доверие к TCP connect как к «успешному соединению» для целей `mark_connected/mark_good`.

---

### 2) Memory Exhaustion

#### Наблюдения по защитам
- `read_message()` имеет ранний лимит размера кадра (≤ `MAX_SLICE_SIZE` = 4MB) и bincode `with_limit(len)` — это хорошо против «len-prefix alloc bomb».
- Есть recv flow control до `read_message()` (блокировка чтения при переполнении очереди) — это хорошо против некоторых классов memory DoS.

#### Слабые места в коде
1) **`Inventory::relay_cache` не ограничен по объёму/числу элементов**
- `net/inventory.rs`: `relay_cache: HashMap<Hash, RelayEntry>` растёт без cap, чистится только по TTL (`RELAY_CACHE_EXPIRY_SECS`).
- Атакующий может присылать много уникальных `Slice/Tx/Presence` → жертва будет кэшировать сериализованные данные (`Network::broadcast_*` кэширует через `cache_relay()`), потребление памяти растёт до O(rate × TTL).

2) **OrphanPool ограничен по количеству, но worst-case всё равно огромный**
- `net/sync.rs`: `MAX_ORPHANS = 100`, при `MAX_SLICE_SIZE=4MB` worst-case ≈ 400MB только на orphan’ах.
- Если атакующий может заставить ноду принимать «слайсы без родителей» (зависит от валидации выше по стеку), это — практичный memory spike.

3) **Потенциально огромная очередь исходящих сообщений на per-peer channel**
- В `net/protocol.rs` на соединение создаётся `mpsc::channel::<Message>(1000)`.
- В `main.rs::send_slices_to_peer()` при `NeedSlices` нода может отправить до `count` слайсов подряд.
- `count` ограничивается в `protocol.rs` до 500, но **нет send-side flow control**, а `Message::Slice` может быть большим. Если удалённый peer перестанет читать, очередь/буферизация могут привести к значительной памяти.

#### Как эксплуатировать
- **Relay-cache blowup**: отправлять поток уникальных `Slice` (или `Tx`) так, чтобы они попадали в `cache_relay()`; поддерживать rate выше, чем `expire()` успевает чистить, в течение TTL.
- **Outbound send queue pressure**: инициировать `GetSlices` (см. Sync DoS) и затем не читать ответы/читать медленно, провоцируя накопление очереди и удержание больших объектов.

#### Итоговый риск
- **Средний→Высокий** (в зависимости от реального пути попадания больших объектов в relay_cache и от поведения sender при backpressure).

---

## TIER 1

### 3) Connection Slot Exhaustion

#### Слабые места в коде
1) **Inbound слот учитывается сразу при accept, до handshake**
- `net/protocol.rs::listener_loop`: после `accept()` вызывается `connections.add_inbound(&addr)` и только потом запускается `handle_connection()`.
- Handshake может длиться до 60 секунд (`HANDSHAKE_TIMEOUT_SECS=60`, `net/types.rs`).

2) **Нет активной eviction-логики в runtime**
- `net/eviction.rs` реализует `select_peer_to_evict()`, но поиск показал отсутствие вызовов из `protocol.rs`/`connection.rs`.
- Когда inbound достигнут, нода просто «rejecting» новые соединения, но не освобождает старые.

3) **Нет rate limit на создание TCP соединений (per-IP/per-subnet) на входе**
- `can_accept_inbound()` проверяет только численные лимиты.

#### Как эксплуатировать
- **Slow/No handshake (slot pinning)**:
  - Открыть много inbound TCP соединений и не отправлять `Version` (или отправлять неполный фрейм).
  - В `handle_connection()` чтение pre-handshake обёрнуто в `timeout(30s, read_message())`, но атакующему достаточно держать 117 слотов занятыми, переподключаясь по мере таймаута.
- **Если есть много /16**: из-за `MAX_PEERS_PER_NETGROUP=2` для заполнения 117 inbound слотов потребуются адреса из множества /16 (IPv6 упрощает, если attacker контролирует префиксы).

#### Итоговый риск
- **Высокий** для доступности inbound-подключений (особенно против узлов, которым важны inbound).

---

### 4) Sync DoS

#### Слабые места в коде
1) **`GetSlices` не rate limited**
- В `net/protocol.rs` для `Message::GetSlices { start, count }` есть только `count.min(500)`.
- Нет token bucket/пер-IP ограничений для этого типа запросов.

2) **Обработчик `NeedSlices` в `main.rs` отвечает без доп. ограничений**
- `main.rs::send_slices_to_peer()` читает слайсы из хранилища и шлёт их подряд.
- В результате один небольшой запрос может спровоцировать длительную отправку больших данных.

#### Как эксплуатировать
- **Bandwidth + IO exhaustion**:
  - После handshake слать `GetSlices` на диапазоны, которые у жертвы точно есть (например, начиная с genesis).
  - Повторять с разных соединений.
  - На стороне атакующего можно не читать или читать медленно, усиливая нагрузку на буферы/очереди.

- **Амплификация**:
  - Даже с лимитом `count<=500`, если средний слайс ~1–4MB, один запрос может требовать от жертвы до сотен МБ/ГБ исходящего трафика.

#### Итоговый риск
- **Высокий** (простая эксплуатация, высокая стоимость для жертвы).

---

### 5) Rate Limit Bypass

#### Слабые места в коде
1) **Rate limiting — per-connection/per-peer, а не per-IP/subnet**
- `PeerRateLimits` хранится в `Peer` и создаётся на соединение (`net/peer.rs`, `net/rate_limit.rs`).
- Атакующий масштабирует пропускную способность линейно числом соединений.

2) **Не все message types покрыты rate limiting’ом**
- Лимитированы только `Addr/Inv/GetData`.
- `GetSlices/GetSlice/Ping/Pong/GetHeaders/SliceHeaders/...` не имеют token bucket.

3) **Burst reset через переподключение**
- Token buckets инициализируются с полной ёмкостью при создании `Peer`.
- Быстрое переподключение даёт снова полный burst (например, 1000 адресов для Addr).

#### Как эксплуатировать
- **Addr poisoning в обход лимита**: много коротких соединений → каждый раз отправлять `Addr` на 1000 адресов.
- **Request flooding без лимитов**: после handshake слать `GetSlices`/`Ping` на высокой частоте.

#### Итоговый риск
- **Высокий** (мультипликативный эффект Sybil’а).

---

## Короткие рекомендации (минимум для закрытия самых критичных дыр)

1) **Eclipse**: перенос `addresses.mark_connected()/mark_good()` на момент *после* успешного handshake (Version+Verack) и/или после минимального периода корректного поведения.
2) **Sync DoS**: добавить token bucket на `GetSlices/GetSlice/GetHeaders/SliceHeaders` (как минимум per-peer, лучше per-IP/subnet) + лимитировать общий объём отправляемых данных на peer/время.
3) **Slot exhaustion**: учитывать inbound слот после handshake или держать отдельный лимит на "pre-handshake" соединения; добавить rate limit на accept/handshake по IP/subnet.
4) **Memory**: ввести cap (по количеству и по суммарным байтам) на `relay_cache`, а также send-side flow control/ограничение очереди на большие сообщения.

