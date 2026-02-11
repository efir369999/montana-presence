# Montana iOS Distribution — Без App Store

## Модель LazyShop

```
┌─────────────────────────────────────────────────────────────┐
│                 install.montana.network                      │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  Wallet.ipa │    │ Junona.ipa  │    │Contracts.ipa│      │
│  │  (unsigned) │    │  (unsigned) │    │  (unsigned) │      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                    ┌───────▼───────┐                        │
│                    │   zsign       │                        │
│                    │ (server-side) │                        │
│                    └───────┬───────┘                        │
│                            │                                 │
│                    ┌───────▼───────┐                        │
│                    │ Signed .ipa   │                        │
│                    │ per UDID      │                        │
│                    └───────┬───────┘                        │
│                            │                                 │
└────────────────────────────┼────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   iPhone        │
                    │ (itms-services) │
                    └─────────────────┘
```

## Процесс установки

### 1. Пользователь заходит на install.montana.network

### 2. Получает свой UDID
- Настройки → Основные → Об этом устройстве
- Или через get.udid.io

### 3. Регистрирует устройство
```
POST /api/register
{ "udid": "00000000-0000000000000000" }
```

### 4. Выбирает приложение и нажимает "Установить"
```
itms-services://?action=download-manifest&url=.../manifest.plist
```

### 5. iOS скачивает подписанный IPA
```
GET /api/download/wallet?udid=00000000-...
```

### 6. Доверяет сертификату
Настройки → Основные → VPN и управление устройством → Доверять

---

## Типы сертификатов

| Тип | Лимит | Срок | Контроль Apple |
|-----|-------|------|----------------|
| **Ad-Hoc** | 100 UDID/год | 1 год | Да (dev portal) |
| **Enterprise** | Безлимит | 1 год | Да (могут отозвать) |
| **Sideload** | 1 устройство | 7 дней | Нет |

### Рекомендация для Montana:

**Уровень 1: Enterprise Certificate**
- Один сертификат для всех
- Не нужен UDID каждого
- Риск: Apple может отозвать

**Уровень 2: Ad-Hoc + Rotation**
- 100 устройств на сертификат
- Несколько dev accounts = больше слотов
- Ротация сертификатов

**Уровень 3: Self-sign Guide**
- Учим пользователей подписывать самим
- AltStore / Sideloadly
- Полная независимость

---

## Структура сервера

```
/var/montana/
├── ipa/                    # Оригинальные .ipa (без подписи)
│   ├── MontanaWallet.ipa
│   ├── JunonaAI.ipa
│   └── MontanaContracts.ipa
│
├── signed/                 # Подписанные (по UDID)
│   ├── 00000000-xxx/
│   │   ├── MontanaWallet.ipa
│   │   └── ...
│   └── 11111111-yyy/
│       └── ...
│
├── certs/                  # Сертификаты
│   ├── montana.p12         # Enterprise/Dev cert
│   └── *.mobileprovision   # Provisioning profiles
│
├── static/                 # Иконки
│   └── icons/
│
├── server.py               # Flask app
└── montanasign.db          # SQLite
```

---

## API Endpoints

```
GET  /                      # Landing page
POST /api/register          # Регистрация UDID
GET  /api/manifest/{app}    # manifest.plist для установки
GET  /api/download/{app}    # Скачать подписанный IPA
GET  /api/apps              # Список приложений
GET  /api/stats             # Статистика
```

---

## Fallback при блокировке

1. **Домен заблокирован** → Новый домен + DNS over HTTPS
2. **IP заблокирован** → Cloudflare / CDN
3. **Сертификат отозван** → Новый Enterprise account
4. **Всё заблокировано** → PWA + Android + Sideload guide

---

## Безопасность

- HTTPS обязателен (itms-services требует)
- Rate limiting на регистрацию
- UDID валидация
- Логирование всех установок
- Backup сертификатов

---

## Сравнение с LazyShop

| Функция | LazyShop | Montana |
|---------|----------|---------|
| Регистрация UDID | ✅ | ✅ |
| Онлайн подпись | ✅ | ✅ |
| Каталог приложений | Много | 3 (наши) |
| Монетизация | Платно | Бесплатно |
| Цель | Пиратство | Независимость |

---

*Apple не контролирует. Время — единственная реальная валюта. Ɉ*
