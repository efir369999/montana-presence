**Модель:** GPT-5.2
**Компания:** OpenAI
**Дата:** 07.01.2026 17:39 UTC

---

## Eclipse Attack — оценка возможности в Montana

Источник требований: `Montana ACP/Council/PROMPT_COUNSIL_TEMPLATE.md` (вектор «Eclipse Attack»).
Код: `Montana ACP/montana/src/net/{protocol.rs,addrman.rs,connection.rs,eviction.rs}`.

---

## 1) Что требуется для eclipse по архитектуре

В Montana outbound-пиры выбираются из `AddrMan::select()` (50/50 NEW/TRIED). Это означает: если злоумышленник может сильно исказить содержимое `AddrMan` так, что большинство «доступных» кандидатов — его адреса, он повышает шанс, что после рестарта жертва поднимет outbound в основном к нему.

Факт выбора через AddrMan:

```500:555:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/protocol.rs
// Peer selection from AddrMan
let net_addr = {
    let mut addrman = addresses.write().await;
    match addrman.select() {
        Some(addr) => addr,
        None => continue,
    }
};
...
// Check netgroup diversity
if !connections.can_connect(&socket_addr).await { continue; }
// Check per-IP limit
if !connections.can_accept_from_ip(&socket_addr).await { continue; }
```

---

## 2) Что защищает от классического «TRIED poisoning через fake TCP connect»

Критически важно: адрес переводится в TRIED только после завершения рукопожатия (`Version + Verack`), а не при одном TCP connect.

```944:953:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/protocol.rs
Message::Verack => {
    peer.handshake_complete();
    just_connected = true;
    // Mark address as successfully connected (moves to TRIED table in AddrMan).
    addresses.write().await.mark_connected(&peer.addr);
}
```

А `mark_connected()` двигает адрес в TRIED:

```342:346:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/addrman.rs
pub fn mark_connected(&mut self, addr: &SocketAddr) {
    self.connected.insert(*addr);
    self.mark_good(addr);
}
```

**Вывод:** самый простой вариант eclipse, когда достаточно «принять TCP» для продвижения в TRIED — в текущем коде закрыт.

---

## 3) Где остаётся возможность eclipse (при сильном противнике)

### 3.1 Poisoning NEW (ограниченно, но возможно)
`AddrMan::add()` кладёт адрес в NEW по бакету/позиции. При коллизии сохраняется «нетеррибл» запись.

```131:175:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/addrman.rs
if let Some(existing_idx) = self.new_table[idx] {
    if let Some(existing) = self.addrs.get(&existing_idx)
        && !existing.is_terrible()
    {
        return false; // Keep existing good address
    }
    self.remove_from_new(existing_idx);
}
```

Это означает: если противник (1) способен сделать так, чтобы жертва приняла много routable/свежих адресов и (2) эти адреса не быстро становятся "terrible", то он может увеличивать долю своих адресов в NEW.

### 3.2 Barrier: netgroup diversity + per-IP limits
Outbound-кандидат проходит:
- `/16` netgroup limit (`MAX_PEERS_PER_NETGROUP=2`)
- per-IP limit (`MAX_CONNECTIONS_PER_IP=2`)

```48:53:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/types.rs
pub const MAX_CONNECTIONS_PER_IP: usize = 2;
```

```202:210:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/types.rs
pub const MAX_PEERS_PER_NETGROUP: usize = 2;
```

**Следствие:** eclipse становится практичным только для противника, который может предоставить много адресов в разных /16 (и не упереться в per-IP cap).

### 3.3 Отсутствие явных «anchor peers» на рестарт
Код явно сохраняет `addresses.dat` и затем снова делает выбор через `AddrMan::select()`; отдельного механизма закрепления (anchor) списка проверенных outbound-пиров в явном виде в `net/*` не видно.
Это делает «рестартный» аспект eclipse (из шаблона) релевантным: после рестарта жертва снова полагается на качество `AddrMan`.

---

## 4) Применимость eviction к eclipse
На inbound включена eviction-логика при достижении лимита.

```354:376:/Users/kh./Python/ACP_1/Montana ACP/montana/src/net/protocol.rs
if !connections.can_accept_inbound() {
    let peer_infos: Vec<_> = peers.read().await.values()
        .map(super::peer::PeerInfo::from)
        .collect();

    if let Some(evict_addr) = super::eviction::select_peer_to_evict(&peer_infos) {
        ...
        connections.remove_peer(&evict_addr, true).await;
    } else {
        continue;
    }
}
```

Это помогает против DoS/slot-grabbing, но eclipse по outbound всё равно определяется составом `AddrMan` и фильтрами отбора.

---

## 5) Итоговая оценка

- **«TRIED poisoning через fake TCP connect»**: в текущем коде **закрыто** (TRIED только после handshake).
- **Eclipse через «смещение AddrMan → перехват outbound после рестартов»**: **возможен при сильном противнике**, способном обеспечить широкую /16 диверсификацию и выдерживать per-IP ограничения.

---

## 6) Рекомендации (защитные)

- **Усилить критерий “good” для TRIED**: считать “good” не только handshake, а минимальный период корректного поведения/обслуживания запросов (anti-TRIED inflation).
- **Добавить явные “anchor peers”**: хранить небольшой набор проверенных outbound peers, которые переживают рестарт и подключаются приоритетно.
- **Интегрировать feeler**: `FeelerManager` существует, но в `net/*` не видно его использования в runtime; подключение feeler-валидации повышает качество NEW.
- **Перенести/добавить ограничения на приём Addr**: сейчас это per-peer; для анти-Sybil усилить per-IP/per-subnet учёт именно для addr-relay.

