# Montana Protocol — Claude Code Context

## Project Overview
Montana Protocol (Ɉ) — Protocol of Ideal Money с постквантовой криптографией.

## Cryptography — MAINNET PRODUCTION
- **Algorithm:** ML-DSA-65 (Dilithium)
- **Standard:** FIPS 204
- **Status:** MAINNET (НЕ migration, НЕ testnet)
- **Library:** `dilithium_py.ml_dsa.ML_DSA_65`

### Key Sizes
- Private Key: 4032 bytes
- Public Key: 1952 bytes
- Signature: 3309 bytes
- Address: `mt + SHA256(pubkey)[:20].hex()` = 42 chars

## API Keys (macOS Keychain)
Все ключи сохранены в системном keyring. Получить:
```bash
# Telegram Bot Token
security find-generic-password -a "montana" -s "TELEGRAM_TOKEN_JUNONA" -w

# OpenAI API Key
security find-generic-password -a "montana" -s "OPENAI_API_KEY" -w

# GitHub Token
security find-generic-password -a "montana" -s "GITHUB_TOKEN" -w

# Admin Telegram ID (владелец узлов)
security find-generic-password -a "montana" -s "ADMIN_TELEGRAM_ID" -w
```

**ВАЖНО:** В документации НЕ должно быть:
- Реальных API ключей (только ссылки на keyring)
- Реальных Telegram ID (использовать ADMIN_ID или keyring)
- Личных имён — автор: **Alejandro Montana** (как Satoshi Nakamoto)

## GitHub
- **Repo:** efir369999/-_Nothing_-
- **Auth:** Настроена через `gh auth` (keyring)
- **Token:** В keychain под именем "GITHUB_TOKEN"
- **Releases:** Создавать через `gh release create`

## Bot
- **Telegram:** @JunonaMontanaAGIBot
- **Token:** В keychain "TELEGRAM_TOKEN_JUNONA"
- **Main file:** Монтана_Montana_蒙大拿/Русский/бот/junomontanaagibot.py
- **Crypto:** Монтана_Montana_蒙大拿/Русский/бот/node_crypto.py
- **AI Provider:** OpenAI (ключ в keychain)

## Languages
Документация на трёх языках:
- Русский: Монтана_Montana_蒙大拿/Русский/
- English: Монтана_Montana_蒙大拿/English/
- 中文: Монтана_Montana_蒙大拿/中文/

## Important Notes
1. ML-DSA-65 это MAINNET — не упоминать Ed25519 как "текущий"
2. Post-quantum с genesis — не retrofit
3. Time is the only real currency
