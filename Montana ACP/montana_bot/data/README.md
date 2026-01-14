# montana_bot data

Это локальная БД Telegram-бота Montana (genesis-ключи и записи присутствия).

## ПРАВИЛО: Один ключ, одна подпись, один раз

**Это касается всех без исключения.**

Каждый пользователь может создать только один genesis identity. Это фундаментальное правило системы Montana.

- **Основание БД = GENESIS**: первая запись для пользователя — это его `CognitiveKey`
  (genesis identity) в `cognitive_keys.json`. Все дальнейшие записи присутствия
  (`presence_records.json`) логически "висят" на этом genesis-ключе через `user_id`
  и `public_key` (публичный идентификатор).

- `cognitive_keys.json`: genesis-ключи пользователей (создаются ботом, **один раз**)
- `presence_records.json`: успешные записи присутствия
- `active_challenges.json`: активные "Ты здесь?" challenge

## Криптографическая подпись genesis (ML-DSA / Dilithium3)

С версии, где включена подпись genesis, бот создаёт **ML-DSA ключ** и делает **ровно одну подпись** по canonical genesis payload.

Чтобы это работало, собери один раз Rust-бинарник:

```bash
cd "Montana ACP/montana" && cargo build --bin genesis_sign
```

Если бинарник лежит не в стандартном месте, укажи путь через переменную окружения:

```bash
export MONTANA_GENESIS_SIGN_BIN="/abs/path/to/genesis_sign"
```

Источник "открытых" когнитивных подписей (маркер + промпт) находится в `Montana ACP/Council/doc/COGNITIVE_MARKERS.md`.
Реестр ключей подписи коммитов (CIK/Ed25519) находится в `Montana ACP/Council/IDENTITY_REGISTRY.md`.
