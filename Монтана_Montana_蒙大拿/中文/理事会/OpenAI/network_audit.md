# Network Layer Security Audit

**Модель:** GPT-5.2 (OpenAI)
**Дата:** 2026-01-07

## Вердикт

NEEDS_REVIEW

## Критические проблемы

| Файл | Строка | Severity | Описание |
|------|--------|----------|----------|
| `montana/src/net/protocol.rs` | 982–1030 | HIGH | **Десериализация сетевых сообщений через `bincode::deserialize(&data)` без `with_limit()`**. Даже при ограничении размера кадра (len ≤ 4MB), bincode может попытаться выделять большие буферы из поддельных length-prefix внутри `Vec`/`String`, что даёт DoS по памяти/CPU. |
| `montana/src/net/protocol.rs` | 799–838 | HIGH | **Повторная десериализация из relay-cache в обработке `GetData` без лимита** (`bincode::deserialize::<Slice/Transaction/PresenceProof>(data)`), тот же класс риска (DoS/alloc). |

## Предупреждения

- **Eclipse/манипуляция внешним IP через 2 голоса**: `MIN_IP_VOTES = 2`, обновление `local_addr` при совпадении 2 голосов (`ip_votes`) в обработке `Version` (`montana/src/net/protocol.rs` 672–697). В условиях Sybil/частичного eclipse атакер может навязать внешний IP, влияя на рекламу адреса/доступность.
- **Flow control выглядит как «логика для лога»**: при `should_pause_recv()` только логируется сообщение и идёт продолжение обработки (`montana/src/net/protocol.rs` 654–663). Комментарий про backpressure через `mpsc` не выглядит применимым к фактическому чтению из сокета (сообщение уже прочитано/аллокация уже произошла в `read_message`). Это снижает ценность защиты от memory/CPU DoS.
- **IPv6 routable-check недостаточен**: `NetAddress::is_routable()` для IPv6 исключает только loopback/unspecified (`montana/src/net/types.rs` 93–106). Не исключаются `fc00::/7` (ULA), `fe80::/10` (link-local) и др., что может ухудшать качество AddrMan/связность и облегчать мусорные addr-инъекции.
- **Sybil resistance: потенциальный разнобой AddrMan vs AddressManager**: в модуле есть полноценный `AddrMan` с криптобакетизацией (`montana/src/net/addrman.rs`), но в сетевом контуре используется `AddressManager` (`montana/src/net/protocol.rs` использует `AddressManager`), где бакетизация проще (по /16 префиксу), что хуже против целевой атакующей инъекции адресов.
- **Рекурсивный `select()` в AddressManager** может стать DoS по стеку при неблагоприятном распределении адресов (много connected/terrible): `return self.select();` (`montana/src/net/address.rs` 227–262).
- **Eviction netgroup protection предсказуем**: защита «случайных» netgroup на деле детерминирована сортировкой по `connected_at` (`montana/src/net/eviction.rs` 141–170), что может позволять атакеру влиять на выбор защищённых слотов по таймингу подключений.

## Сильные стороны

- **Чёткий wire framing + checksum**: MAGIC/LENGTH/CHECKSUM + SHA3-256(4 байта) и ранний лимит размера кадра до 4MB (`montana/src/net/protocol.rs` 982–1028).
- **Pre-handshake фильтрация**: до завершения рукопожатия разрешены только `Version/Verack/Reject` (`montana/src/net/protocol.rs` 649–652; `montana/src/net/message.rs` 106–109).
- **Rate limiting по классам сообщений** (`addr`/`inv`/`getdata`) через token bucket (`montana/src/net/protocol.rs` 747–808; `montana/src/net/rate_limit.rs`).
- **Netgroup diversity (/16)** на уровне ConnectionManager (`montana/src/net/connection.rs`) + многоуровневый eviction для inbound (`montana/src/net/eviction.rs`).
- **Bootstrap-верификация** с hardcoded-consensus и проверкой медианы времени/диверсификации подсетей (`montana/src/net/bootstrap.rs`).

## Рекомендации

- **Ввести bounded-deserialization**: использовать `bincode::options().with_limit(...)`/`deserialize_from` с лимитом, согласованным с `Message::max_size_for_command()`. Это нужно как минимум для `read_message` и десериализации relay-cache.
- **Усилить `is_routable()` для IPv6**: отфильтровать ULA, link-local, multicast и пр. (аналогично Bitcoin Core policy), чтобы адресная книга не загрязнялась.
- **Сделать flow control реальным**: при превышении лимитов — прекращать чтение/обработку (закрывать соединение или замедлять), а не только логировать.
- **Пересмотреть внешний IP discovery**: повысить порог голосов, учитывать разнообразие netgroup/только outbound, либо отключать по умолчанию.
- **Убрать рекурсию в `AddressManager::select()`** в пользу цикла с лимитом попыток.
- **Проверить интеграцию AddrMan**: если целевой механизм sybil-resistance — `AddrMan`, стоит убедиться, что именно он используется в основном контуре (или чётко объяснить, почему используется `AddressManager`).

## Общая оценка

В слое сети много правильных идей (лимиты, rate limiting, netgroup, bootstrap-hardcoded консенсус), но сейчас есть **классический риск DoS через неограниченную десериализацию bincode** на пути входящих данных. До исправления bounded-deserialization и сопутствующих защит вердикт: **NEEDS_REVIEW**.
