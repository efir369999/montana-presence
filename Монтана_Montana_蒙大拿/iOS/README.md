# Montana iOS — Юнона везде

100% Native Swift/SwiftUI • iOS 17+

**Юнона — единый диалог управления всей системой.**
Все приложения = интерфейсы к Юноне.

## Архитектура

```
iOS/
├── MontanaCore/                    # SPM пакет — общее ядро
│   ├── Package.swift
│   └── Sources/MontanaCore/
│       ├── MontanaCore.swift       # Типы, тема, Keychain, ссылки
│       └── AppStoreGuard.swift     # Мониторинг удаления из App Store
│
├── Apps/
│   ├── JunonaAI/                   # APP STORE — VPN + Диалог
│   │   ├── JunonaAI/
│   │   │   ├── JunonaAIApp.swift
│   │   │   ├── VPN/
│   │   │   │   └── MontanaVPN.swift
│   │   │   └── Views/
│   │   │       ├── VPNView.swift
│   │   │       └── InstallOtherAppsView.swift
│   │   └── JunonaVPNExtension/     # Network Extension
│   │       ├── PacketTunnelProvider.swift
│   │       └── PostQuantumTunnel.swift
│   │
│   ├── MontanaWallet/              # СЕРТИФИКАТЫ — Диалог + Кошелёк
│   │   └── MontanaWallet/
│   │       └── MontanaWalletApp.swift
│   │
│   └── MontanaContracts/           # СЕРТИФИКАТЫ — Диалог + Контракты
│       └── MontanaContracts/
│           └── MontanaContractsApp.swift
│
└── Distribution/
    └── MontanaSign/                # LazyShop-style сервис
        └── server.py               # Flask API + Landing
```

## Юнона везде

| App | Канал | Юнона управляет |
|-----|-------|-----------------|
| Junona VPN | **App Store** | VPN, присутствие |
| Junona Wallet | Сертификаты | Баланс, переводы Ɉ |
| Junona Contracts | Сертификаты | Контракты, голосование |

**Почему так:**
- VPN легален в App Store (NordVPN, ExpressVPN)
- Крипто/финансы Apple блокирует → сертификаты
- Юнона — диалог управления во всех apps

## VPN + Присутствие

| Параметр | Значение |
|----------|----------|
| Ключевой обмен | ML-KEM-768 (Kyber, FIPS 203) |
| Шифрование | ChaCha20-Poly1305 |
| Узлы | Amsterdam (72.56.102.240), Almaty (91.200.148.93) |
| **Присутствие** | **1 секунда VPN = 1 Ɉ** (время, не трафик!) |

## Сборка

```bash
cd iOS/Apps/JunonaAI
open JunonaAI.xcodeproj

# File → Add Package → ../../MontanaCore
```

## Shared Resources

- **App Group:** `group.network.montana`
- **Keychain:** Shared между 3 apps
- **URL Schemes:** `montana-wallet://`, `montana-junona://`, `montana-contracts://`

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) — общая архитектура
- [DISTRIBUTION_STRATEGY.md](DISTRIBUTION_STRATEGY.md) — стратегия распространения
- [VPN_ARCHITECTURE.md](VPN_ARCHITECTURE.md) — постквантовый VPN

## VPN Server

Серверная часть: `Русский/Бот/vpn_server.py`
- ML-KEM-768 + ChaCha20-Poly1305
- Деплой на Amsterdam/Almaty
