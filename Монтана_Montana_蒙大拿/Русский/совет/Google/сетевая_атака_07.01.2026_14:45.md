**Модель:** Gemini 3 Pro
**Компания:** Google
**Дата:** 07.01.2026 14:45 UTC

---

## TIER 0: КРИТИЧЕСКИЕ

### 1. Eclipse Attack: Poisoning TRIED & No Anchors

**Файлы:** `net/addrman.rs`, `net/connection.rs`

**Анализ:**
Код содержит критические уязвимости, позволяющие изолировать узел (Eclipse Attack):
1.  **Отсутствие Anchor Connections:** В `addrman.rs` и `connection.rs` нет механизма сохранения активных соединений ("anchors") для немедленного переподключения после перезапуска. Узел полагается только на `addresses.dat`. Если `TRIED` таблица отравлена, после рестарта узел подключится только к атакующему.
2.  **Слабая защита TRIED таблицы:** В методе `mark_good` (`addrman.rs`) при коллизии в `tried_table` используется стратегия `move_to_new`, которая вытесняет *существующий* (легитимный) адрес обратно в `new_table`. Атакующий может намеренно создавать коллизии (зная алгоритм SipHash ключа или просто флудом), вымывая честные узлы из доверенного списка.

**Эксплуатация:**
1.  Атакующий заполняет `NEW` таблицу своими IP.
2.  Атакующий устанавливает соединения, чтобы попасть в `TRIED`.
3.  Атакующий вызывает коллизии, вытесняя легитимные пиры в `NEW`, где они могут быть удалены.
4.  Жертва перезагружается -> подключается к адресам из `TRIED` (которые теперь принадлежат атакующему).

### 2. Memory Exhaustion: Unbounded Event Channel & Read Timeout

**Файлы:** `net/protocol.rs`

**Анализ:**
1.  **Event Channel Flooding:** Канал `mpsc::channel(10000)` в `Network::new` передает сообщения `NetEvent`. Событие `NetEvent::Slice` содержит `Box<Slice>`. Размер `Slice` до 4MB.
    *   Атакующий может отправить 10,000 сообщений `Slice` (нет rate limit, см. ниже).
    *   Потребление памяти: 10,000 * 4MB = **40 GB**. Это приведет к OOM (Out of Memory) падению.
2.  **No Read Timeout (Post-Handshake):** В `handle_connection` таймаут 30 сек действует только на handshake. После этого `read_message` вызывается без таймаута.
    *   Атакующий отправляет заголовок сообщения (Length = 4MB) и останавливает передачу.
    *   Узел выделяет 4MB буфер (`vec![0u8; len]`) и вечно ждет данные.
    *   При 117 слотах это ~470MB "мертвой" памяти, плюс блокировка потоков tokio.

**Эксплуатация:**
*   **Vector A:** Открыть соединение, handshake, отправить 10,000 сообщений `Slice` максимально быстро.
*   **Vector B:** Открыть 117 соединений, отправить заголовки 4MB сообщений и перестать слать байты.

---

## TIER 1: ВЫСОКИЕ

### 3. Connection Slot Exhaustion: Dead Eviction Logic

**Файлы:** `net/protocol.rs`, `net/eviction.rs`

**Анализ:**
В файле `net/eviction.rs` реализована сложная логика вытеснения (`select_peer_to_evict`), но она **НИГДЕ НЕ ИСПОЛЬЗУЕТСЯ**.
В `protocol.rs` в `listener_loop`:
```rust
if !connections.can_accept_inbound() {
    debug!("Max inbound reached, rejecting: {}", addr);
    continue; // Просто отклоняет, не пытаясь освободить место!
}
```

**Эксплуатация:**
1.  Атакующий открывает 117 соединений (max inbound).
2.  Узел перестает принимать любые новые входящие соединения.
3.  Легитимные пиры не могут подключиться.

### 4. Sync DoS: GetSlices Amplification

**Файлы:** `net/protocol.rs`, `net/sync.rs`

**Анализ:**
Обработчик `Message::GetSlices` в `protocol.rs` не имеет проверки Rate Limit (в отличие от `Inv` или `GetData`).
```rust
Message::GetSlices { start, count } => {
    let count = count.min(500); // Limit count per req, but NOT req rate
    let _ = event_tx.send(...).await;
}
```
Атакующий может слать тысячи запросов `GetSlices` в секунду. Каждый запрос заставляет узел (в другом потоке) читать с диска и сериализовать до 500 слайсов (до 2GB данных).

**Эксплуатация:**
Отправить поток сообщений `GetSlices`. Это вызовет перегрузку CPU, Disk I/O и пропускной способности (если узел начнет отвечать).

### 5. Rate Limit Bypass: Missing Checks

**Файлы:** `net/protocol.rs`, `net/rate_limit.rs`

**Анализ:**
Структура `PeerRateLimits` и проверки в `protocol.rs` покрывают только сообщения `Addr`, `Inv`, `GetData`.
Остальные сообщения **не имеют ограничений**:
*   `Slice` (4MB payload)
*   `Tx` (1MB payload)
*   `Presence`
*   `GetSlices`

**Эксплуатация:**
Атакующий может флудить сообщениями `Slice` (4MB каждый), что быстро заполнит канал событий (см. Memory Exhaustion) или забьет канал связи, так как проверка `process_message` происходит *после* вычитывания всего сообщения в память.

