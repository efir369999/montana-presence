# Montana iOS — Юнона везде

**Все приложения = диалог с Юноной**

## Навигация (4 вкладки)

```
[ Контакты ] [ Папки ] [ Юнона ] [ Настройки ]
```

## Уровни приватности

| Уровень | Шифрование | По умолчанию |
|---------|------------|--------------|
| **Интимное** | ML-KEM-768 + ChaCha20 (постквантовое) | ✅ ДА |
| Приватное | E2E шифрование | |
| Публичное | Без шифрования | |

## Приложения

### Junona VPN (App Store)
| Файл | Описание |
|------|----------|
| [JunonaAIApp.swift](Apps/JunonaAI/JunonaAI/JunonaAIApp.swift) | MainTabView + 4 вкладки |
| [FoldersView.swift](Apps/JunonaAI/JunonaAI/Views/FoldersView.swift) | Папки с уровнями приватности |
| [ContactsView.swift](Apps/JunonaAI/JunonaAI/Views/ContactsView.swift) | Контакты Montana |
| [SettingsView.swift](Apps/JunonaAI/JunonaAI/Views/SettingsView.swift) | Настройки + VPN |
| [VPNView.swift](Apps/JunonaAI/JunonaAI/Views/VPNView.swift) | UI для VPN |
| [MontanaVPN.swift](Apps/JunonaAI/JunonaAI/VPN/MontanaVPN.swift) | VPN Manager, присутствие по времени |
| [InstallOtherAppsView.swift](Apps/JunonaAI/JunonaAI/Views/InstallOtherAppsView.swift) | Ссылки на Wallet/Contracts |
| [PacketTunnelProvider.swift](Apps/JunonaAI/JunonaVPNExtension/PacketTunnelProvider.swift) | Network Extension |
| [PostQuantumTunnel.swift](Apps/JunonaAI/JunonaVPNExtension/PostQuantumTunnel.swift) | ML-KEM-768 + ChaCha20 |

### Junona Wallet (Сертификаты)
| Файл | Описание |
|------|----------|
| [MontanaWalletApp.swift](Apps/MontanaWallet/MontanaWallet/MontanaWalletApp.swift) | Диалог Юнона + Кошелёк Ɉ |

### Junona Contracts (Сертификаты)
| Файл | Описание |
|------|----------|
| [MontanaContractsApp.swift](Apps/MontanaContracts/MontanaContracts/MontanaContractsApp.swift) | Диалог Юнона + Контракты |

## MontanaCore (SPM)

| Файл | Описание |
|------|----------|
| [Package.swift](MontanaCore/Package.swift) | SPM manifest |
| [MontanaCore.swift](MontanaCore/Sources/MontanaCore/MontanaCore.swift) | Theme, Keychain, Links, Address, **PrivacyLevel**, **Folder**, **Contact** |
| [AppStoreGuard.swift](MontanaCore/Sources/MontanaCore/AppStoreGuard.swift) | Мониторинг удаления из App Store |

### Модели данных (MontanaCore.swift)

| Модель | Описание |
|--------|----------|
| `PrivacyLevel` | Интимное (default), Приватное, Публичное |
| `MontanaFolder` | Папка с уровнем приватности |
| `MontanaFolderItem` | Элемент в папке (note, photo, video, audio, file) |
| `MontanaContact` | Контакт с адресом mt... |
| `MontanaFolderStorage` | Менеджер хранения папок |
| `MontanaContactStorage` | Менеджер контактов |

## Distribution

| Файл | Описание |
|------|----------|
| [server.py](Distribution/MontanaSign/server.py) | LazyShop-style Flask API |

## Документация

| Файл | Описание |
|------|----------|
| [README.md](README.md) | Обзор iOS проекта |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура 3 приложений |
| [DISTRIBUTION_STRATEGY.md](DISTRIBUTION_STRATEGY.md) | App Store + Сертификаты |
| [VPN_ARCHITECTURE.md](VPN_ARCHITECTURE.md) | Постквантовый VPN |

## Криптография

| Алгоритм | Назначение | Стандарт |
|----------|------------|----------|
| ML-KEM-768 | Ключевой обмен VPN | FIPS 203 |
| ML-DSA-65 | Подписи кошелька | FIPS 204 |
| ChaCha20-Poly1305 | Симметричное шифрование | RFC 8439 |
| HKDF-SHA256 | Деривация ключей | RFC 5869 |

## Bundle IDs

```
network.montana.junona          # App Store
network.montana.junona.vpn      # VPN Extension
network.montana.wallet          # Сертификаты
network.montana.contracts       # Сертификаты
```

## URL Schemes

```
montana-wallet://               # Открыть кошелёк
montana-junona://               # Открыть Юнону
montana-contracts://            # Открыть контракты
```

## VPN Узлы

| Узел | IP | Регион | Ping |
|------|-----|--------|------|
| Amsterdam | 72.56.102.240 | Европа | ~40ms |
| Almaty | 91.200.148.93 | Азия | ~80ms |

## Присутствие = Время VPN

```
1 секунда VPN = 1 Ɉ

НЕ трафик! Только время подключения.
VPN включён 1 час = 3600 Ɉ
```

---

*11 Swift файлов • 3 приложения Юноны • Постквантовая криптография*
