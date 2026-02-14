# Montana Protocol Ɉ

[🇷🇺 Русский](#-montana-protocol--протокол-идеальных-денег) | [🇬🇧 English](#-montana-protocol--ideal-money-protocol)

<div align="center">

![Montana Protocol](https://img.shields.io/badge/Montana-Ɉ-00d4ff?style=for-the-badge)
![Version](https://img.shields.io/badge/version-3.7.2-7b2fff?style=for-the-badge)
![ML-DSA-65](https://img.shields.io/badge/crypto-ML--DSA--65-00d4ff?style=for-the-badge)
![macOS](https://img.shields.io/badge/macOS-14.0+-7b2fff?style=for-the-badge)
![iOS](https://img.shields.io/badge/iOS-17.0+-00d4ff?style=for-the-badge)

**Time is the only real currency**

</div>

---

## 🇷🇺 Montana Protocol — Протокол Идеальных Денег

**Montana Protocol (Ɉ)** — децентрализованный протокол идеальных денег с постквантовой криптографией.

### 🎯 Концепция

**1 Ɉ = 1 секунда человеческого присутствия**

- **Genesis Price:** 1 Ɉ = $0.1605 USD = 12.04₽ RUB
- **Price Genesis:** 12.03.2021 (BIPL — Bill Payment anchor)
- **Network Genesis:** 09.01.2026

### 🔐 Постквантовая криптография

- **Алгоритм:** ML-DSA-65 (Dilithium)
- **Стандарт:** FIPS 204
- **Статус:** MAINNET (production)
- **Размеры ключей:**
  - Private Key: 4032 bytes
  - Public Key: 1952 bytes
  - Signature: 3309 bytes
  - Address: `mt` + SHA256(pubkey)[:20].hex() = 42 chars

### 💰 Экономика

#### Proof-of-Presence Mining

```
weight = 1 (база) + активные датчики + VPN

Пример:
Camera ON + Microphone ON + VPN ON
→ weight = 1 + 2 + 1 = 4
→ 1 секунда = 4 Ɉ
```

Датчики **НЕ СОБИРАЮТ ДАННЫЕ** — это якоря (anchors) для proof-of-presence.

#### Аукционная модель

- **Домены:** `alice@montana.network` → N-й домен = N Ɉ
- **Номера:** `+montana-000042` → N-й номер = N Ɉ
- **Звонки:** 1 Ɉ/сек для владельцев номеров
- **Комиссия:** 0 Ɉ (нет комиссий)

### 📱 Приложения

#### macOS (Montana.app)

[⬇️ Скачать последнюю версию](https://github.com/efir369999/-_Nothing_-/releases/latest)

- Встроенный кошелёк с proof-of-presence mining
- Junona AI ассистент (Claude 4.5) — управление протоколом
- Домены, номера, звонки, сайты, видео
- Real-time синхронизация с 3 узлами (консенсус 51%+)
- Montana VPN (WireGuard + постквантовое шифрование)

#### iOS (Montana Wallet)

- Proof-of-presence mining
- ML-DSA-65 ключи в Secure Enclave
- Отправка/получение Ɉ
- История транзакций
- Требуется Xcode 15+ и физическое устройство

### 🌐 Сеть

**3 узла (Атланты):**

| Узел | IP | Статус |
|------|-----|--------|
| Москва | 176.124.208.93 | Online |
| Амстердам | 72.56.102.240 | Online |
| Алматы | 91.200.148.93 | Online |

**Консенсус:** Majority voting (51%+)

**Сайт:** [efir.org](https://efir.org)

**Синхронизация:**
- Автоматически каждые 60 секунд
- Проверка баланса у всех 3 узлов
- Кошелёк показывает статус: ✅ синхронизирован | 🔄 синхронизация...

### 🤖 Junona AI

Montana Protocol AI ассистент на базе Claude 4.5:
- Помощь с Montana Protocol
- Управление кошельком, доменами, номерами
- API: `POST https://efir.org/api/chat`

```json
{
  "question": "Как отправить Ɉ?",
  "lang": "ru",
  "context": "кошелёк создан, баланс 1000 Ɉ"
}
```

### 📦 Установка

#### macOS

```bash
# Скачать Montana.app
curl -LO https://github.com/efir369999/-_Nothing_-/releases/latest/download/Montana.app.zip

# Распаковать
unzip Montana.app.zip

# Запустить
open Montana.app
```

При первом запуске macOS покажет предупреждение (Montana подписан ad-hoc):
1. **System Settings** → **Privacy & Security**
2. **"Open Anyway"** → **"Open"**

#### iOS

```bash
cd Монтана_Montana_蒙大拿/iOS/Apps/Montana
xcodebuild -scheme Montana -destination 'platform=iOS,id=YOUR_DEVICE_ID' build
xcrun devicectl device install app --device YOUR_DEVICE_ID Montana.app
```

### 🛠 Сборка из исходников

#### macOS

```bash
cd Монтана_Montana_蒙大拿/macOS/MontanaPresence
./build.sh
```

Требуется:
- Xcode Command Line Tools
- macOS 14.0+

#### iOS

```bash
cd Монтана_Montana_蒙大拿/iOS/Apps/Montana
xcodebuild -scheme Montana -destination 'generic/platform=iOS' clean build
```

Требуется:
- Xcode 15+
- iOS 17.0+

### 📚 Документация

- [Спецификация ключей](Монтана_Montana_蒙大拿/Русский/Ключи/СПЕЦИФИКАЦИЯ.md)
- [Спецификация коммуникаций](Монтана_Montana_蒙大拿/Русский/Коммуникация/СПЕЦИФИКАЦИЯ.md)
- [Спецификация контрактов](Монтана_Montana_蒙大拿/Русский/Контракты/СПЕЦИФИКАЦИЯ.md)

### 🔗 Ссылки

- **Сайт:** [efir.org](https://efir.org)
- **GitHub:** [efir369999/-_Nothing_-](https://github.com/efir369999/-_Nothing_-)
- **Twitter:** [@AlexMontana369](https://x.com/AlexMontana369)

### 🔒 Безопасность

#### 1 устройство = 1 Montana

Montana строго привязан к вашему устройству через Hardware UUID:
- При первом запуске записывается UUID устройства
- Невозможно скопировать на другое устройство
- Автоматическое убийство дубликатов

#### Постквантовая защита

- ML-DSA-65 устойчив к квантовым компьютерам
- Защита от атаки Шора (RSA/ECDSA ломаются)
- 248-бит энтропия (превосходит Bitcoin 256-бит)

#### Открытый код

- Весь код на GitHub
- Нет бэкдоров
- Нет корпораций
- Создатель: Alejandro Montana (псевдоним, как Satoshi Nakamoto)

### 📄 Лицензия

Open source. Автор: **Alejandro Montana**

---

## 🇬🇧 Montana Protocol — Ideal Money Protocol

**Montana Protocol (Ɉ)** — decentralized ideal money protocol with post-quantum cryptography.

### 🎯 Concept

**1 Ɉ = 1 second of human presence**

- **Genesis Price:** 1 Ɉ = $0.1605 USD = 12.04₽ RUB
- **Price Genesis:** 12.03.2021 (BIPL — Bill Payment anchor)
- **Network Genesis:** 09.01.2026

### 🔐 Post-Quantum Cryptography

- **Algorithm:** ML-DSA-65 (Dilithium)
- **Standard:** FIPS 204
- **Status:** MAINNET (production)
- **Key sizes:**
  - Private Key: 4032 bytes
  - Public Key: 1952 bytes
  - Signature: 3309 bytes
  - Address: `mt` + SHA256(pubkey)[:20].hex() = 42 chars

### 💰 Economics

#### Proof-of-Presence Mining

```
weight = 1 (base) + active sensors + VPN

Example:
Camera ON + Microphone ON + VPN ON
→ weight = 1 + 2 + 1 = 4
→ 1 second = 4 Ɉ
```

Sensors **DO NOT COLLECT DATA** — they are anchors for proof-of-presence.

#### Auction Model

- **Domains:** `alice@montana.network` → Nth domain = N Ɉ
- **Numbers:** `+montana-000042` → Nth number = N Ɉ
- **Calls:** 1 Ɉ/sec for number owners
- **Fees:** 0 Ɉ (no fees)

### 📱 Applications

#### macOS (Montana.app)

[⬇️ Download latest release](https://github.com/efir369999/-_Nothing_-/releases/latest)

- Built-in wallet with proof-of-presence mining
- Junona AI assistant (Claude 4.5) — protocol management
- Domains, numbers, calls, sites, video
- Real-time sync with 3 nodes (51%+ consensus)
- Montana VPN (WireGuard + post-quantum encryption)

#### iOS (Montana Wallet)

- Proof-of-presence mining
- ML-DSA-65 keys in Secure Enclave
- Send/receive Ɉ
- Transaction history
- Requires Xcode 15+ and physical device

### 🌐 Network

**3 nodes (Atlants):**

| Node | IP | Status |
|------|-----|--------|
| Moscow | 176.124.208.93 | Online |
| Amsterdam | 72.56.102.240 | Online |
| Almaty | 91.200.148.93 | Online |

**Consensus:** Majority voting (51%+)

**Website:** [efir.org](https://efir.org)

**Synchronization:**
- Automatically every 60 seconds
- Checks balance from all 3 nodes
- Wallet shows status: ✅ synced | 🔄 syncing...

### 🤖 Junona AI

Montana Protocol AI assistant powered by Claude 4.5:
- Help with Montana Protocol
- Wallet, domains, numbers management
- API: `POST https://efir.org/api/chat`

```json
{
  "question": "How to send Ɉ?",
  "lang": "en",
  "context": "wallet created, balance 1000 Ɉ"
}
```

### 📦 Installation

#### macOS

```bash
# Download Montana.app
curl -LO https://github.com/efir369999/-_Nothing_-/releases/latest/download/Montana.app.zip

# Unzip
unzip Montana.app.zip

# Run
open Montana.app
```

First launch warning (Montana is ad-hoc signed):
1. **System Settings** → **Privacy & Security**
2. **"Open Anyway"** → **"Open"**

#### iOS

```bash
cd Монтана_Montana_蒙大拿/iOS/Apps/Montana
xcodebuild -scheme Montana -destination 'platform=iOS,id=YOUR_DEVICE_ID' build
xcrun devicectl device install app --device YOUR_DEVICE_ID Montana.app
```

### 🛠 Build from source

#### macOS

```bash
cd Монтана_Montana_蒙大拿/macOS/MontanaPresence
./build.sh
```

Requirements:
- Xcode Command Line Tools
- macOS 14.0+

#### iOS

```bash
cd Монтана_Montana_蒙大拿/iOS/Apps/Montana
xcodebuild -scheme Montana -destination 'generic/platform=iOS' clean build
```

Requirements:
- Xcode 15+
- iOS 17.0+

### 📚 Documentation

- [Key Specification](Монтана_Montana_蒙大拿/Русский/Ключи/СПЕЦИФИКАЦИЯ.md)
- [Communication Specification](Монтана_Montana_蒙大拿/Русский/Коммуникация/СПЕЦИФИКАЦИЯ.md)
- [Contracts Specification](Монтана_Montana_蒙大拿/Русский/Контракты/СПЕЦИФИКАЦИЯ.md)

### 🔗 Links

- **Website:** [efir.org](https://efir.org)
- **GitHub:** [efir369999/-_Nothing_-](https://github.com/efir369999/-_Nothing_-)
- **Twitter:** [@AlexMontana369](https://x.com/AlexMontana369)

### 🔒 Security

#### 1 device = 1 Montana

Montana is strictly bound to your device via Hardware UUID:
- Records device UUID on first launch
- Cannot copy to another device
- Automatic duplicate termination

#### Post-Quantum Protection

- ML-DSA-65 resistant to quantum computers
- Protection against Shor's algorithm (breaks RSA/ECDSA)
- 248-bit entropy (exceeds Bitcoin's 256-bit)

#### Open Source

- All code on GitHub
- No backdoors
- No corporations
- Creator: Alejandro Montana (pseudonym, like Satoshi Nakamoto)

### 📄 License

Open source. Author: **Alejandro Montana**

---

<div align="center">

**Montana Protocol Ɉ — Time is the only real currency**

Made with ⏱️ by Alejandro Montana

</div>
