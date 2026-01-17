**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 07.01.2026 18:11 UTC

## Задача
Найти практический вектор **Eclipse Attack** на сеть Montana (P2P), опираясь на код в `/Montana ACP/montana/src/net/`.

## TL;DR (главная уязвимость)
Заявленная защита “full bootstrap verification (100 peers, 25+ /16 subnets, hardcoded median check)” **фактически не исполняется** в текущей реализации:
- `main.rs` только **логирует** «Startup verification … Full bootstrap…», но **не вызывает** `StartupVerifier` / `BootstrapVerifier`.
- `Network::start()` запускает listener/connector/maintenance и сразу добавляет user-supplied `seeds` в `AddrMan`, после чего `connection_loop` начинает диалить адреса **без какого-либо гейта “verification passed”**.
- `net/startup.rs` содержит заглушку `query_hardcoded_tips()` → `Vec::new()`, то есть даже если verifier вызывать, он **не сможет** набрать `MIN_HARDCODED_RESPONSES`.

Следствие: Eclipse сводится к классике — **poisoning AddrMan + перехват outbound**.

## Доказательства по коду (ключевые места)
### 1) Startup verification не выполняется
`montana/src/main.rs`:
- Есть лог о “Startup verification … Full bootstrap…”, но дальше код сразу делает `Network::new()` и `network.start()` (без вызова verifier).

`montana/src/net/protocol.rs`:
- `Network::start()` спаунит `listener_loop`, `connection_loop`, `maintenance_loop`, затем добавляет `seeds` через `add_seed()` и возвращает `Ok(())`.
- Никакой проверки, что “startup verification passed”, нет.

### 2) StartupVerifier — заглушка
`montana/src/net/startup.rs`:
- `query_hardcoded_tips()` возвращает `Vec::new()` (placeholder), а `total_peers` в результате = `responses.len()` с комментарием “Would be 100 in full implementation”.

### 3) Addr poisoning реально влияет на выбор outbound
`montana/src/net/protocol.rs`:
- `connection_loop` выбирает адрес через `addrman.select()` (50/50 NEW vs TRIED) и затем коннектится.

### 4) TRIED заполняется после handshake (это хорошо), но это делает eclipse ещё проще при отсутствии bootstrapping
`montana/src/net/protocol.rs`:
- На `Message::Verack` вызывается `addresses.write().await.mark_connected(&peer.addr);` — перевод адреса в TRIED происходит после успешного handshake.

### 5) Addr rate-limit легко обходится Sybil’ом (лимит per-connection)
`montana/src/net/rate_limit.rs`:
- `AddrRateLimiter`: **burst 1000**, sustained **0.1 addr/sec**.
- Лимитер хранится в `Peer` → лимит **на соединение**, а не глобальный.
- Значит атакующий открывает много соединений (входящих/исходящих) и с каждого отправляет по 1000 адресов → быстро забивает NEW таблицу.

## Практическая схема Eclipse Attack (эксплуатация)
### Предпосылки
- Жертва запускает узел и имеет хотя бы 1–2 канала к атакующему (например, через `--seeds` или просто подключившись к атакующему узлу).
- Атакующий контролирует набор IP’ов, желательно распределённых по разным /16 (или IPv6-префиксам так, как считает `get_netgroup`).

### Шаг 1 — “засорить NEW” адресной книгой атакующего
1) Атакующий устанавливает соединение с жертвой и доводит handshake до `Verack` (иначе нельзя слать `Addr`).
2) Сразу после handshake отправляет `Addr` с максимумом адресов (до 1000 в сообщении).
3) Повторяет через множество Sybil-соединений: каждый `Peer` имеет свой `AddrRateLimiter` → снова 1000 burst.

Результат: `AddrMan::new_table` (1024 buckets × 64) — до ~65k слотов — может быть существенно заполнена адресами атакующего.

### Шаг 2 — перевести атакующие адреса в TRIED
1) Т.к. `connection_loop` выбирает адреса из AddrMan (50/50 NEW/TRIED) и **нет гейта на bootstrap-verification**, жертва начнёт диалить адреса из отравленного AddrMan.
2) Атакующие узлы принимают соединение и корректно отвечают handshake.
3) На `Verack` адрес переводится в `TRIED` (`mark_connected`).

Результат: со временем TRIED (256×64 = 16384 слота) тоже становится “атакующий-доминант”.

### Шаг 3 — рестарт жертвы и «полный eclipse»
После рестарта жертва снова будет выбирать peers из AddrMan (частично TRIED) и практически все outbound уйдут на атакующего.

### Ограничения и как атакующий их обходит
- **MAX_OUTBOUND = 8**, **MAX_PEERS_PER_NETGROUP = 2** (т.е. максимум 2 исходящих на один /16).
  - Для полного перехвата 8 outbound нужно иметь ≥4 разных netgroup (/16) и по 2 адреса в каждом.
- **MAX_CONNECTIONS_PER_IP = 2** — не даёт одному IP занять много слотов.
  - Но атакующий использует несколько IP.
- Факт отсутствия “100 peers / 25+ subnets / hardcoded median check” делает стоимость атаки **на порядки ниже**, чем заявлено в комментариях.

## Почему это именно Eclipse (а не просто Sybil)
Потому что цель — **монополизировать видимость сети жертвы** за счёт контроля всех/почти всех outbound + доминирования адресной книги, а не просто “иметь много узлов”. Здесь это достигается через AddrMan poisoning и отсутствие обязательной startup-верификации.

## Рекомендации (high level)
1) **Сделать startup verification реальным гейтом**:
   - до запуска `connection_loop` собрать 100 ответов, проверить 25+ /16, проверить hardcoded-median, и только затем разрешать outbound.
2) **Убрать/жёстко ограничить доверие к `--seeds`**:
   - сейчас `add_seed()` bypass’ит часть проверок и фактически даёт атакующему якорь.
3) **Глобальный и per-IP/per-netgroup лимит на Addr ingestion**:
   - текущий лимит per-peer легко обходится множеством соединений.
4) (Если включать feelers) **Feeler должен проходить protocol handshake**, иначе “TCP-only reachability” снова откроет прямой путь к TRIED poisoning.

---

## Приложение: ключевые файлы
- `montana/src/net/protocol.rs` — выбор outbound (`AddrMan::select`), обработка `Addr`, перевод в `TRIED` на `Verack`.
- `montana/src/net/addrman.rs` — NEW/TRIED таблицы, bucket logic.
- `montana/src/net/startup.rs` и `montana/src/net/bootstrap.rs` — заявленная модель защиты, но сейчас не интегрирована/частично заглушена.
- `montana/src/net/rate_limit.rs` — per-peer токенбакеты.
