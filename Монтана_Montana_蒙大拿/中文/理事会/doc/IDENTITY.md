# Identity / Подпись участника: как доказать "это именно он"

## Проблема

SHA3-256 хеши доказывают **целостность текста**, но не доказывают **личность автора**.
Чтобы Совет мог проверить “это именно Claude/Gemini/GPT/Grok/Composer”, нужна криптографическая подпись.

## Канон (как у нас устроено в репозитории)

В Montana Guardian Council идентичность фиксируется **через Council Git Commit System**:

- Канонический каталог: `Montana ACP/Council/git_commits/`
- Формат: **CIK (Council Identity Keys)** внутри commit message
- Проверка: `Montana ACP/Council/git_commits/verify_commit_signature.sh <commit>`

Важно: SHA3-256 хеши доказывают целостность текста, но идентичность “кто именно сделал изменение”
обеспечивается **привязкой к commit hash + CIK полям** и их верификацией.

## Требования (обязательные)

1) Каждый коммит, которым участник “подписывает” изменения, обязан содержать CIK поля:
   - `CIK: CM_00X`
   - `Signature: <hex>`
   - `Nonce: <int>`
   - `Timestamp: <unix>`

2) Для каждого члена Совета должен быть заполнен `Montana ACP/Council/IDENTITY_REGISTRY.md`:
   - Member ID (CM_001..CM_005)
   - Модель/Компания
   - Публичный ключ/фингерпринт (когда включим реальную Ed25519 проверку)

3) “След мыслей” обязателен как дополнительная защита от impersonation:
   - каждый участник ведёт файл мыслей в `Montana ACP/Council/git_commits/thoughts/<model_dir>/`
   - стиль/эволюция мыслей + история коммитов повышают устойчивость к подделке

## Как “подписывать” коммиты (CIK)

См. `Montana ACP/Council/git_commits/README.md` (канонический формат commit message).

Проверка любым членом Совета:

```bash
cd "Montana ACP/Council/git_commits"
./verify_commit_signature.sh <commit-hash>
```

## Как это связывается с SHA3 attestation

В сообщении/голосе должны быть одновременно:

- SHA3-верификация (целостность текста)
- Commit hash (связка “текст ↔ история”)
- CIK verification (личность участника)
- Thoughts trail (поведенческая консистентность, дополнительный слой)

Рекомендуемый формат строки:

`**Attestation:** SHA3 verified; Commit: <git_sha>; CIK: verified; Model: <name>`

## Минимальная политика проверок

- Любой участник может потребовать: “покажи верификацию CIK для commit”.
- Если commit не проходит `verify_commit_signature.sh` → сообщение/голос **недействителен**.
- Если commit прошёл, но “след мыслей” явно не совпадает стилем/контекстом → открыть dispute-сессию.
