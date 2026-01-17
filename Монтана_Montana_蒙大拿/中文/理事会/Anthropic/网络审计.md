# Network Layer Security Audit

**Модель:** Claude Opus 4.5 (Anthropic)
**Дата:** 2025-01-07
**Scope:** `montana/src/net/` (~3500 строк Rust)

## Вердикт

**SAFE** с предупреждениями

## Критические проблемы

| Файл | Строка | Severity | Описание |
|------|--------|----------|----------|
| — | — | — | Критических проблем не обнаружено |

## Предупреждения

| Файл | Строка | Severity | Описание |
|------|--------|----------|----------|
| peer.rs | 184-188 | MED | `known_inv.clear()` при overflow удаляет ВСЕ записи вместо LRU eviction. Атакующий может заставить peer "забыть" известный inventory. |
| protocol.rs | 499-501 | LOW | Ping отправляется в maintenance loop без синхронной записи nonce в peer state. Теоретический race condition. |
| protocol.rs | 100 | LOW | `MIN_IP_VOTES = 2` для external IP discovery. Два злонамеренных пира могут навязать ложный external IP. |
| sync.rs | 17 | LOW | `MAX_ORPHANS = 100` может быть недостаточно при глубоком reorg (>100 слайсов). |
| types.rs | 16 | LOW | `MESSAGE_SIZE_LIMIT = 32MB` не используется для early check, но остаётся как fallback. Потенциальная путаница. |
| protocol.rs | — | LOW | Отсутствует проверка self-connection через nonce comparison (как в Bitcoin). Узел может подключиться сам к себе. |
| discouraged.rs | 107-127 | LOW | При bloom filter roll старые discouraged peers забываются. Атакующий может переждать и повторить атаку. |

## Сильные стороны

### DoS Protection
- Per-message size limits (`MAX_SLICE_SIZE = 4MB`, `MAX_TX_SIZE = 1MB`, etc.)
- Early size check в `read_message` ДО аллокации буфера (protocol.rs:1000-1005)
- SHA3-256 checksum (4 bytes) для целостности
- Token bucket rate limiting для addr/inv/getdata сообщений
- Flow control с pause_recv/pause_send при переполнении буферов

### Eclipse Resistance
- `/16 netgroup diversity` — max 2 peers per subnet (types.rs:48)
- Multi-layer eviction protection — 28+ protected slots:
  - 4 by netgroup diversity
  - 8 by lowest ping
  - 4 by recent tx relay
  - 4 by recent slice relay
  - 8 by connection longevity
- Outbound connections (8) инициируются нами — атакующий не контролирует

### Sybil Resistance
- AddrMan bucket system (1024 new + 256 tried buckets)
- Cryptographic bucket assignment через SipHash с random key
- Source-based bucketing — адреса от одного источника попадают в один bucket
- Feeler connections для валидации адресов

### Bootstrap Security
- Hardcoded nodes (20) ДОЛЖНЫ совпадать с P2P консенсусом (1% tolerance)
- 100 peers требуется, 51+ должны согласиться
- Subnet diversity: 25+ unique /16 subnets
- Peer history verification: 10+ peers с >14 дней истории
- Download peers: 5 из 8 должны иметь историю
- Network time verification против local clock manipulation

### Subnet Reputation
- Долгосрочная репутация накапливается годами
- Merkle root в каждом slice header
- Snapshot каждые τ₃ (2016 слайсов / ~14 дней)
- Max 5 nodes per subnet при bootstrap selection

## Рекомендации

1. **known_inv overflow** — заменить `HashSet::clear()` на LRU cache с bounded size
2. **Self-connection** — добавить nonce comparison для отклонения подключений к себе
3. **Discouraged expiry** — рассмотреть persistent storage для discouraged list
4. **MIN_IP_VOTES** — увеличить до 3-5 для большей устойчивости external IP discovery

## Общая оценка

Сетевой слой демонстрирует production-ready уровень безопасности. Реализованы все основные защиты из Bitcoin Core (AddrMan, eviction, rate limiting) плюс специфичные для Montana (subnet reputation, bootstrap verification, network time check). Найденные предупреждения не представляют критической угрозы и являются улучшениями, а не уязвимостями.

Код хорошо структурирован, содержит unit тесты для критических компонентов. Комментарии документируют security-critical решения.
