# Montana Protocol — Claude Code Context

## Project Overview
Montana Protocol (Ɉ) — Protocol of Ideal Money с постквантовой криптографией.
Полностью независимый децентрализованный проект.

## Devices
- **Основной iPhone:** `00008110-00144D493A9B801E` (8110)

## IMMUTABLE CODE BLOCKS (Неизменяемые блоки кода)

**КРИТИЧЕСКОЕ ПРАВИЛО: Код помеченный `IMMUTABLE BLOCK` НЕЛЬЗЯ МЕНЯТЬ.**

Блоки помечены в коде так:
```
// ╔══════════════════════════════════════════════════════════════════╗
// ║  IMMUTABLE BLOCK — <NAME>                                       ║
// ║  НЕ МЕНЯТЬ. Это неизменяемый блок кода.                         ║
// ╚══════════════════════════════════════════════════════════════════╝
```

### Текущие неизменяемые блоки:

| Блок | Файл | Что делает |
|------|------|------------|
| **SENSOR MODEL** | `PresenceEngine.swift` | Формула веса: активные датчики + 1 (база) + VPN |
| **PERMISSION SYNC** | `PresenceEngine.swift` | Синхронизация разрешений: старт → автоотключение без разрешения, переходы → авто вкл/выкл |
| **SENSOR UI** | `MenuBarView.swift` | Отображение датчиков: ON+разрешение=золотой, OFF/нет разрешения=серый |

### Правила датчиков (НЕИЗМЕНЯЕМЫЕ):
1. Разрешение есть + тумблер ON = датчик активен (якорь, данные НЕ собирает)
2. Разрешения нет ИЛИ тумблер OFF = всё выключено (ничего не собирает/не отправляет)
3. На старте: тумблер ON без разрешения → автоотключение
4. По умолчанию: вес = 1 (присутствие пока программа включена)
5. Каждый датчик +1 по факту включения/выключения

**Claude Code: НИКОГДА не модифицировать IMMUTABLE BLOCK ни при каких обстоятельствах и обновлениях.**

---

## Development Rules (Правила разработки)

### КРИТИЧЕСКОЕ ПРАВИЛО: КРИТИКИ → БИЛД → ДЕПЛОЙ
```
1. ИЗМЕНИЛ КОД → КРИТИКИ (security audit, code review)
2. КРИТИКИ OK → БИЛД
3. БИЛД УСПЕШЕН → ДЕПЛОЙ
4. ЛЮБОЙ FAILED → ИСПРАВИТЬ → СНОВА С ПУНКТА 1
```

**ЗАПРЕЩЕНО:**
- Деплоить без билда
- Билдить без критиков
- Пропускать security audit
- Предлагать пользователю деплоить вручную — ВСЕГДА деплоить самому
- Останавливаться на полпути — ВСЕГДА доводить до конца (билд + деплой + проверка)

## Servers & Domains (Серверы и домены)

### 3 узла сети Montana + сайт (проверены через SSH)
| Узел | IP | Статус |
|------|-----|--------|
| **Сайт (Timeweb)** | `1394793-cy33234.tw1.ru` | Primary |
| **Москва** | `176.124.208.93` | Active |
| **Амстердам** | `72.56.102.240` | Active |
| **Алматы** | `91.200.148.93` | Active |

- **Web root:** `/var/www/html/`
- **Downloads:** `https://1394793-cy33234.tw1.ru/downloads/`
- **НЕТ домена montana.network — используй 1394793-cy33234.tw1.ru**

```bash
# iOS: ВСЕГДА в таком порядке

# 1. КРИТИКИ — security audit, code review
#    - Проверить clipboard attacks
#    - Проверить хранение ключей
#    - Проверить HTTPS/TLS
#    - Проверить input validation

# 2. БИЛД (только после критиков)
cd Монтана_Montana_蒙大拿/iOS/Apps/Montana
xcodebuild -scheme Montana -destination 'platform=iOS,id=00008110-00144D493A9B801E' build

# 3. ДЕПЛОЙ НА УСТРОЙСТВО
xcrun devicectl device install app --device 00008110-00144D493A9B801E \
  ~/Library/Developer/Xcode/DerivedData/Montana-*/Build/Products/Debug-iphoneos/Montana.app
```

**Порядок НЕ меняется:** КРИТИКИ → БИЛД → ДЕПЛОЙ

## Swipe Apps (Свайп Приложения)
Концепт навигации внутри Montana iOS app. Вместо отдельных приложений — единый app с горизонтальным свайпом между экранами:
- **Книга Монтана** — читалка и аудиокнига (BookView.swift)
- **Контакты** — адресная книга (ContactsView.swift)
- **Настройки** — профиль и ключи (SettingsView.swift)

Все "приложения" живут внутри единого Montana.app с общей авторизацией.

## iOS Project
- **Путь:** `Монтана_Montana_蒙大拿/iOS/Apps/Montana/`
- **Scheme:** `Montana`
- **Bundle ID:** `network.montana.wallet`
- **Target:** `Montana`

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

## Security Architecture

**Локальный Mac + Keychain = Хранитель операционных ключей сети Атлантов**

Ключи в keychain — это ОПЕРАЦИОННЫЕ ключи (API, SSH):
- Управление серверами
- Доступ к внешним API

**Компрометация этих ключей НЕ влияет на сеть Montana Protocol:**
- Криптографические ключи ML-DSA-65 генерируются на каждом узле
- Каждый Атлант хранит свой приватный ключ локально
- Сеть децентрализована — нет единой точки отказа

## ALL KEYS (macOS Keychain ONLY)
Все операционные ключи ТОЛЬКО в keychain. Файлы .env пустые!

### API Keys:
```bash
security find-generic-password -a "montana" -s "OPENAI_API_KEY" -w
security find-generic-password -a "montana" -s "ANTHROPIC_API_KEY" -w
security find-generic-password -a "montana" -s "GITHUB_TOKEN" -w
```

## SSH Keys & Servers (macOS Keychain)
Все SSH ключи и данные серверов в keychain:
```bash
# SSH ключ id_ed25519 (приватный, base64)
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PRIVATE" -w | base64 -d > ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519

# SSH ключ id_ed25519 (публичный)
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PUBLIC" -w > ~/.ssh/id_ed25519.pub

# SSH ключ jn_srv (приватный, base64) — для Timeweb сервера
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PRIVATE" -w | base64 -d > ~/.ssh/jn_srv
chmod 600 ~/.ssh/jn_srv

# SSH ключ jn_srv (публичный)
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PUBLIC" -w > ~/.ssh/jn_srv.pub

# Passphrase для jn_srv ключа (зашифрован)
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w

# SSH config (base64)
security find-generic-password -a "montana" -s "SSH_CONFIG" -w | base64 -d > ~/.ssh/config

# Серверы
security find-generic-password -a "montana" -s "SERVER_TIMEWEB_IP" -w    # 176.124.208.93
security find-generic-password -a "montana" -s "SERVER_TIMEWEB_USER" -w  # root
security find-generic-password -a "montana" -s "SERVER_AMS_IP" -w        # 72.56.102.240
security find-generic-password -a "montana" -s "SERVER_AMS_USER" -w      # root
```

### Быстрое подключение к серверам
```bash
# Timeweb (использует jn_srv ключ)
ssh my-timeweb

# Amsterdam
ssh montana-ams
```

### Деплой на сервер (АВТОМАТИЧЕСКИ через expect)
```bash
# SSH ключ требует passphrase — использовать expect
PASS_HEX=$(security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w)
PASS=$(echo "$PASS_HEX" | xxd -r -p)

# Подготовить ключ
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PRIVATE" -w | base64 -d > /tmp/jn_srv
chmod 600 /tmp/jn_srv

# SCP с passphrase через expect
expect -c "
spawn scp -i /tmp/jn_srv -o StrictHostKeyChecking=no FILE root@176.124.208.93:/root/montana/
expect { \"passphrase\" { send \"$PASS\r\"; exp_continue } eof }
"

# SSH команда через expect
expect -c "
spawn ssh -i /tmp/jn_srv -o StrictHostKeyChecking=no root@176.124.208.93 \"COMMAND\"
expect { \"passphrase\" { send \"$PASS\r\"; exp_continue } eof }
"

# Путь montana_api.py на сервере: /root/montana/montana_api.py
```

**ВАЖНО:** В документации НЕ должно быть:
- Реальных API ключей (только ссылки на keyring)
- Личных имён — автор: **Alejandro Montana** (как Satoshi Nakamoto)

## GitHub
- **Repo:** efir369999/-_Nothing_-
- **Auth:** Настроена через `gh auth` (keyring)
- **Token:** В keychain под именем "GITHUB_TOKEN"
- **Releases:** Создавать через `gh release create`

## Backend
- **API:** Монтана_Montana_蒙大拿/Русский/Бот/montana_api.py
- **Crypto:** Монтана_Montana_蒙大拿/Русский/Бот/node_crypto.py
- **Time Bank:** Монтана_Montana_蒙大拿/Русский/Бот/time_bank.py
- **Leader Election:** Монтана_Montana_蒙大拿/Русский/Бот/leader_election.py

## Логистика — SeaFare_Montana (#Сованаглобус)
Морская логистика и консалтинг. AI-агент на Moltbook.

### Moltbook Agent
- **Агент:** SeaFare_Montana
- **Платформа:** moltbook.com (соцсеть для AI-агентов)
- **Submolt:** r/maritimetrade
- **Бизнес-модель:** Консультант (контакты фрахтовщиков $10 USDT)
- **API Key:** В keychain `MOLTBOOK_SEAFARE_API_KEY`

### Файлы
- **Агент:** `Монтана_Montana_蒙大拿/Русский/Логистика/seafare_agent.py`
- **API:** `Монтана_Montana_蒙大拿/Русский/Логистика/seafare_api.py`
- **БД:** `Монтана_Montana_蒙大拿/Русский/Логистика/maritime_db.py`
- **Equasis:** `Монтана_Montana_蒙大拿/Русский/Логистика/equasis_parser.py`

### Источники данных
1. **Equasis** (бесплатно, ~100 запросов/день) — владельцы, операторы судов
2. **Локальная БД SQLite** — кэш всех данных
3. **AIS** — позиции судов (публичные источники)

### Деплой на Amsterdam (OpenAI блокирует Россию)
```bash
# Сервер: 72.56.102.240
# Путь: /root/montana/

# Переменные окружения в /root/montana/seafare_env:
# - OPENAI_API_KEY
# - MOLTBOOK_SEAFARE_API_KEY
# - EQUASIS_USER (требуется регистрация)
# - EQUASIS_PASS

# Запуск агента
ssh montana-ams "cd /root/montana && source seafare_env && python3 seafare_agent.py"
```

### Demurrage Calculator
Формула: `(actual_days - agreed_days) × daily_rate`
- agreed_days: согласованное время на разгрузку
- actual_days: фактическое время
- daily_rate: ставка демереджа в день

### API Endpoints
- `GET /api/v1/vessel/<identifier>` — информация о судне
- `GET /api/v1/vessel/search?q=` — поиск судов
- `GET /api/v1/position/<mmsi>` — позиция судна
- `POST /api/v1/demurrage/calculate` — расчёт демереджа
- `GET /api/v1/contacts/search` — поиск контактов (платно)

## Documentation
- **Система ключей:** Монтана_Montana_蒙大拿/Русский/Ключи/СПЕЦИФИКАЦИЯ.md
- **Коммуникации:** Монтана_Montana_蒙大拿/Русский/Коммуникация/СПЕЦИФИКАЦИЯ.md
- **Контракты:** Монтана_Montana_蒙大拿/Русский/Контракты/СПЕЦИФИКАЦИЯ.md

## Languages
Документация на трёх языках:
- Русский: Монтана_Montana_蒙大拿/Русский/
- English: Монтана_Montana_蒙大拿/English/
- 中文: Монтана_Montana_蒙大拿/中文/

## Important Notes
1. ML-DSA-65 это MAINNET — не упоминать Ed25519 как "текущий"
2. Post-quantum с genesis — не retrofit
3. Time is the only real currency
4. **НЕТ Telegram бота** — полностью независимый проект

---

## ОБЯЗАТЕЛЬНЫЕ ПРИВЫЧКИ (Claude Code)

**ВСЕГДА выполнять при деплое:**

### 1. Версионирование
- [ ] Обновить `CFBundleShortVersionString` (семантическая версия X.Y.Z)
- [ ] Обновить `CFBundleVersion` (инкремент build number)
- [ ] Формат: MAJOR.MINOR.PATCH
  - MAJOR: breaking changes
  - MINOR: новые фичи
  - PATCH: баг-фиксы, security fixes

### 2. Changelog
- [ ] Документировать изменения в релизе
- [ ] Security fixes помечать явно

### 3. Montana Landing Pages
При создании/редактировании страниц Montana:
- [ ] Использовать цвета: #00d4ff (cyan), #7b2fff (purple)
- [ ] Логотип Montana

### 4. Перед деплоем
- [ ] Проверить что нет HTTP fallback
- [ ] Проверить что тесты проходят
- [ ] Проверить версию обновлена

### 5. После деплоя
- [ ] Убедиться что приложение установилось
- [ ] Проверить что версия отображается корректно

### 6. Git
- [ ] Создать тег с версией: `git tag vX.Y.Z`
- [ ] Commit с описанием изменений

---

## Версионная история iOS

| Версия | Build | Дата | Изменения |
|--------|-------|------|-----------|
| 1.0.0 | 1 | 2026-01-27 | Initial release |
| 1.1.0 | 2 | 2026-01-28 | Security: HTTPS only, signature required, 300x audit |
| 1.2.0 | 3 | 2026-01-28 | MAINNET: Server deployed, Disney 8 critics PASS |
| 1.4.0 | 5 | 2026-01-28 | Cognitive Key: 248-bit entropy, ONE memory phrase, BIP-39 model |
| 1.5.0 | 6 | 2026-01-28 | Montana rebrand, Passkey (Face ID), security fixes (seed zeroing) |
| 1.5.0 | 13 | 2026-01-28 | New identity reset, Keychain cleanup, privacy policy fix |
| 1.5.0 | 14 | 2026-01-28 | WalletService: montana_address only, project renamed JunonaAI → Montana |
| 1.6.0 | 15 | 2026-01-28 | Purge TG/Google: removed dead auth views, cleaned ProfileManager/Settings/AuthService, coin symbol fix |
| 1.8.0 | 17 | 2026-02-02 | Cognitive Key Model: keys = identity (no server registration), coin symbol same size as balance, full address in settings |
| 1.9.0 | 18 | 2026-02-02 | PIN Protection: KeychainManager (explicit private_key/public_key), PinView (6-digit), clear key architecture |
| 2.0.0 | 21 | 2026-02-03 | Full independence: removed Telegram bot, standalone Montana Protocol |
