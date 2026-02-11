# Montana iOS — Юнона везде

## Архитектура: Юнона = Диалог управления

```
┌─────────────────────────────────────────────────────────────┐
│                         ЮНОНА                                │
│              AI-диалог управления всей системой              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                                                         ││
│  │   "Покажи баланс"      → Wallet функции                ││
│  │   "Создай контракт"    → Contracts функции             ││
│  │   "Подключи VPN"       → VPN функции                   ││
│  │   "Переведи 100 Ɉ"     → Транзакции                    ││
│  │                                                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   APP STORE      │ │   СЕРТИФИКАТЫ    │ │   СЕРТИФИКАТЫ    │
│                  │ │                  │ │                  │
│  Junona VPN      │ │  Junona Wallet   │ │ Junona Contracts │
│                  │ │                  │ │                  │
│  • VPN ML-KEM    │ │  • Баланс Ɉ      │ │  • Bitcoin Pizza │
│  • Диалог Юнона  │ │  • Переводы      │ │  • Голосование   │
│  • Присутствие   │ │  • Диалог Юнона  │ │  • Диалог Юнона  │
│                  │ │  • ML-DSA-65     │ │  • Escrow        │
│  .junona         │ │  .wallet         │ │  .contracts      │
└──────────────────┘ └──────────────────┘ └──────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                 ┌────────────┴────────────┐
                 │      MontanaCore        │
                 │    (SPM Package)        │
                 │                         │
                 │  • JunonaDialog         │
                 │  • Shared Keychain      │
                 │  • AppStoreGuard        │
                 │  • Theme                │
                 └─────────────────────────┘
```

## Присутствие = Время VPN

```
НЕ трафик!

1 секунда VPN включён = 1 Ɉ

Пример:
├── VPN подключён 1 час = 3600 Ɉ
├── VPN подключён 24 часа = 86400 Ɉ
└── Трафик НЕ считается, только время
```

## Почему гибридная модель?

| Канал | Плюсы | Минусы |
|-------|-------|--------|
| **App Store (VPN)** | Доверие, легко найти | Ревью Apple |
| **Сертификаты (Wallet/Contracts)** | Нет контроля Apple | Нужен UDID |

**Ключевые преимущества:**
1. VPN легален в App Store — точка входа для новых пользователей
2. Crypto/Finance Apple блокирует — обходим через сертификаты
3. Mutual monitoring — если Junona удалят, показываем предупреждение

## AppStoreGuard Mechanism

```swift
// Each app runs this on startup
AppStoreGuard.shared.startMonitoring()

// Checks iTunes Lookup API every hour
GET https://itunes.apple.com/lookup?bundleId=network.montana.wallet

// If resultCount = 0 → App removed from store
// Shows warning banner in remaining apps
```

## Warning Message When App Removed

```
⚠️ ВНИМАНИЕ

Apple удалила из App Store: Montana Wallet

Это ограничивает функциональность Montana Protocol.
Apple не поддерживает свободу финансовых транзакций.

Причина удаления: Apple Inc.

Альтернативы:
• TestFlight: testflight.apple.com/join/montana
• Web: app.montana.network
• Android: play.google.com/store/apps/montana

Время — единственная реальная валюта.
Apple не может удалить время.
```

## Cross-App Communication

### URL Schemes
- `montana-wallet://` — Open wallet
- `montana-junona://` — Open Junona chat
- `montana-contracts://` — Open contracts

### Shared Keychain
All 3 apps share the same keychain group (`group.network.montana`):
- Wallet address
- Private/Public keys (ML-DSA-65)
- User preferences

```swift
// Any app can access wallet
let address = MontanaKeychain.shared.walletAddress

// Open another app
MontanaLinks.openJunona(message: "Создай контракт")
```

## Все приложения = Юнона

| App | Канал | Юнона помогает |
|-----|-------|----------------|
| **Junona VPN** | App Store | Подключить VPN, показать присутствие |
| **Junona Wallet** | Сертификаты | Баланс, переводы, управление ключами |
| **Junona Contracts** | Сертификаты | Создать контракт, голосовать, escrow |

**Юнона — единый интерфейс.** Пользователь общается с ней, она выполняет.

## Bundle IDs

```
network.montana.junona          — App Store (VPN + AI)
network.montana.junona.vpn      — VPN Extension
network.montana.wallet          — Сертификаты (Wallet)
network.montana.contracts       — Сертификаты (Contracts)
```

## Поток пользователя

```
1. Находит Junona VPN в App Store
2. Устанавливает, подключает VPN (защита + начисление Ɉ)
3. Видит "Установить Wallet" в приложении
4. Переходит на install.montana.network
5. Регистрирует UDID, устанавливает Wallet/Contracts
6. Все приложения связаны через общий Keychain
```

## Fallback

```
Если App Store удаляет Junona:
├── Wallet/Contracts продолжают работать
├── VPN доступен через install.montana.network
└── Пользователи получают уведомление

Если сертификаты отзывают:
├── Junona VPN остаётся в App Store
├── Функции интегрируются в Junona
└── Или новый Enterprise-аккаунт

Если всё блокируют:
├── PWA: app.montana.network
├── Android: Play Store + APK
└── Desktop: macOS/Windows
```

## VPN Узлы

| Узел | IP | Регион |
|------|-----|--------|
| Amsterdam | 72.56.102.240 | Европа |
| Almaty | 91.200.148.93 | Азия |

---

*Apple не может удалить время. Ɉ*
