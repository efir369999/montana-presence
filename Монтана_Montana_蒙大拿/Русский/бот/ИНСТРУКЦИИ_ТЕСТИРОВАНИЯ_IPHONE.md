# 📱 Инструкции: Тест Montana с iPhone

**Дата:** 19.01.2026
**Компоненты:** Agent Registry + FIDO2 + ML-DSA-65

---

## Что Тестируем

### 1. **Agent Registry**
- ML-DSA-65 подписи сообщений
- Верификация официальных агентов Montana
- Защита от Agent Impersonation

### 2. **FIDO2 Biometrics (Mock)**
- Touch ID / Face ID регистрация
- Proof of Presence верификация
- Защита от Sybil Attack

---

## Подготовка

### Шаг 1: Убедиться что Юнона зарегистрирована

```bash
cd "/Users/kh./Python/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿/Русский/бот"

# Проверить registry
cat data/agent_registry.json

# Если нет - зарегистрировать
python3 register_junona.py
```

### Шаг 2: Запустить тестовый веб-сервер

```bash
python3 test_iphone_web.py
```

Вывод:
```
🏔 Montana Test Server
============================================================
Agent Registry: ACTIVE (ML-DSA-65)
FIDO2: MOCK MODE (для production нужен WebAuthn)
============================================================

📱 Для доступа с iPhone:
1. Открой http://127.0.0.1:5001 в браузере
2. Или отсканируй QR: http://127.0.0.1:5001/qr

🔍 Или используй локальный IP в той же сети
============================================================

Запуск сервера на порту 5001...
```

---

## Вариант 1: Mac + iPhone в одной сети

### На Mac:

```bash
# Узнать локальный IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Пример вывода:
# inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255
```

### На iPhone:

1. Открыть Safari
2. Перейти на `http://192.168.1.100:5001` (твой локальный IP)
3. Сохранить на Home Screen (опционально)

---

## Вариант 2: QR код

### На Mac:

```bash
# В браузере открыть:
http://127.0.0.1:5001/qr
```

### На iPhone:

1. Открыть Камеру
2. Навести на QR код
3. Tap на уведомление
4. Откроется Safari с Montana Test

---

## Тесты

### Тест 1: Agent Registry

#### На iPhone:

1. Нажать **"Список агентов"**
2. Увидеть Юнону Montana:
   ```
   Юнона Montana [OFFICIAL]
   mtAGENT1eccbac3e5048039a2bf2105d211514d
   Официальный AI агент Montana Protocol...
   ```

3. Нажать **"Сообщение от Юноны"**
4. Увидеть подписанное сообщение:
   ```
   Подписанное сообщение Юноны:
   Агент: Юнона Montana
   Адрес: mtAGENT1eccbac3e5048039a2bf2105d211514d
   Сообщение: Привет с iPhone! Это тест Montana.
   Timestamp: 2026-01-19T14:10:23.456Z
   Подпись: 38190b7cfed2fa632469c59102628fa1...
   ✅ ML-DSA-65 подпись валидна
   ```

#### Что проверяется:
- ✅ ML-DSA-65 генерация подписи (4032 байта private key)
- ✅ Верификация подписи (1952 байта public key)
- ✅ Agent Registry lookup
- ✅ Official agent badge

---

### Тест 2: FIDO2 Biometrics (Mock)

#### На iPhone:

1. Нажать **"Зарегистрировать биометрию"**
2. Увидеть:
   ```
   Биометрия зарегистрирована:
   Credential ID: ff0f89307d3a2acb8f8d048c...
   ✅ Touch ID / Face ID registered
   В production это будет реальный Touch ID / Face ID
   ```

3. Нажать **"Верифицировать биометрию"**
4. Увидеть:
   ```
   Биометрия верифицирована:
   Устройство: iPhone
   Зарегистрировано: 2026-01-19T14:05:23.737555+00:00
   Последняя авторизация: 2026-01-19T14:10:45.123456+00:00
   ✅ Proof of Presence подтверждён
   ```

#### Что проверяется:
- ✅ FIDO2 credential registration
- ✅ Proof of Presence верификация
- ✅ Timestamp tracking
- ⚠️ MOCK MODE: В production будет реальный WebAuthn API

---

## Production FIDO2 (Реальный Touch ID / Face ID)

### Для реального Touch ID / Face ID нужно:

1. **HTTPS сертификат** (WebAuthn требует TLS)
   ```bash
   # Self-signed для теста:
   openssl req -x509 -newkey rsa:4096 -nodes \
     -keyout key.pem -out cert.pem -days 365
   ```

2. **WebAuthn API в браузере**
   ```javascript
   // Registration
   const credential = await navigator.credentials.create({
     publicKey: {
       challenge: Uint8Array.from(challenge, c => c.charCodeAt(0)),
       rp: { name: "Montana Network", id: "montana.network" },
       user: {
         id: Uint8Array.from(userId, c => c.charCodeAt(0)),
         name: "montana_user",
         displayName: "Montana User"
       },
       pubKeyCredParams: [{ alg: -7, type: "public-key" }],
       authenticatorSelection: {
         userVerification: "required"  // Touch ID / Face ID
       }
     }
   });

   // Authentication
   const assertion = await navigator.credentials.get({
     publicKey: {
       challenge: Uint8Array.from(challenge, c => c.charCodeAt(0)),
       allowCredentials: [{
         type: "public-key",
         id: credentialId
       }],
       userVerification: "required"
     }
   });
   ```

3. **Сервер FIDO2 верификация**
   ```python
   from fido2_node import MontanaFIDO2

   fido = MontanaFIDO2(rp_id="montana.network")

   # Верификация registration
   auth_data = fido.server.register_complete(
       state=state,
       client_data=client_data,
       attestation_object=attestation
   )
   ```

---

## Что Дальше

### Следующие шаги для production:

1. **Интеграция в junomontanaagibot.py**
   - Все сообщения Юноны подписываются ML-DSA-65
   - Пользователи видят `✅ Official Agent` badge
   - Команда `/verify_agent <address>` проверяет подписи

2. **WebAuthn для /register_node**
   - Регистрация узла требует Touch ID / Face ID
   - Private key защищён биометрией
   - Proof of Presence каждые 24 часа

3. **Agent Registry на Amsterdam сервере**
   - `data/agent_registry.json` синхронизирован на всех узлах
   - Watchdog обновляет registry через git
   - API endpoint `/api/agent/<address>` для верификации

4. **Rate Limiting**
   - Max 100 запросов в час с одного IP
   - Max 10 транзакций в минуту с одного Telegram ID
   - Redis для distributed rate limiting

---

## Архитектура

```
iPhone (Safari)
     ↓
WebAuthn API (Touch ID / Face ID)
     ↓
Montana Flask Server (localhost:5001)
     ↓
agent_crypto.py (ML-DSA-65 подписи)
     ↓
fido2_node.py (FIDO2 верификация)
     ↓
data/agent_registry.json (реестр агентов)
data/agent_keys.json (private keys)
data/mock_fido2.json (credentials)
```

---

## Безопасность

### ✅ Защищено:

| Атака | Защита |
|-------|--------|
| Agent Impersonation | ML-DSA-65 подписи + Registry |
| Sybil Attack | FIDO2 биометрия (1 человек = 1 Touch ID) |
| Quantum Computer | ML-DSA-65 (post-quantum) |
| MITM | TLS + ML-DSA-65 подписи |

### ⚠️ TODO для production:

- [ ] HTTPS / TLS сертификат
- [ ] Реальный WebAuthn (вместо mock)
- [ ] Синхронизация registry через git
- [ ] Rate limiting API
- [ ] Hardware Security Module (HSM) для ключей

---

## Отладка

### Проблема: "Connection refused" на iPhone

**Решение:**
```bash
# Проверить, что сервер слушает 0.0.0.0
netstat -an | grep 5001

# Должно быть:
# tcp4  0  0  *.5001  *.*  LISTEN
```

### Проблема: "Agent keys not found"

**Решение:**
```bash
# Зарегистрировать Юнону
python3 register_junona.py

# Проверить
ls -lh data/agent_keys.json
```

### Проблема: "No biometric registered"

**Решение:**
```bash
# Сначала нажать "Зарегистрировать биометрию"
# Потом "Верифицировать биометрию"
```

---

## Резюме

### Что работает прямо сейчас:

✅ **Agent Registry**
- ML-DSA-65 подписи
- Post-quantum защита
- Верификация официальных агентов

✅ **FIDO2 Mock**
- Симуляция Touch ID / Face ID
- Proof of Presence
- Credential management

### Для production нужно:

⚠️ **WebAuthn API** (реальный Touch ID / Face ID)
⚠️ **HTTPS** (TLS сертификат)
⚠️ **Синхронизация** (git watchdog для registry)

---

**Ɉ Montana — Протокол идеальных денег**

*ML-DSA-65 MAINNET — Post-quantum от genesis*

*FIDO2 Biometrics — 1 человек = 1 Touch ID*

*Agent Registry — Доверяй, но проверяй подписи*
