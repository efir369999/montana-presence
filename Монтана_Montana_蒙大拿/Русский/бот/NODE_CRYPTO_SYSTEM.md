# Криптографическая Система Узлов Montana

## POST-QUANTUM КРИПТОГРАФИЯ ML-DSA-65 (FIPS 204)

**MAINNET READY** — Post-quantum криптография активна с genesis.

## Обзор

Узлы Montana используют **криптографические адреса** вместо IP адресов для идентификации кошельков.
Все операции защищены **ML-DSA-65** (FIPS 204) — post-quantum алгоритмом.

### Защита от Атак

- ✅ **Квантовые компьютеры** — ML-DSA-65 устойчив к Shor's algorithm
- ✅ **Harvest now, decrypt later** — данные защищены от будущей дешифровки
- ✅ **IP hijacking** — адрес не зависит от IP
- ✅ **DNS spoofing** — alias только для удобства
- ✅ **Man-in-the-middle** — все операции подписаны ML-DSA-65
- ✅ **Подделка транзакций** — требуется private key (4032 байта)

---

## Архитектура Адресов

### Пользователи
```
Адрес = Telegram ID
Ключ = Telegram Session
Пример: 123456789
```

### Узлы
```
Адрес = mt + SHA256(public_key)[:20].hex()
Ключ = Private key ML-DSA-65 (4032 байта)
Public key = 1952 байта
Подпись = 3309 байт
Пример: mt1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0
```

---

## Формат Адреса Узла

### Структура
```
mt + SHA256(public_key)[:20].hex()
│   └─ Первые 20 байт (40 hex символов) SHA256 хеша
└─ Префикс Montana

Пример:
mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a
```

### Длина
- **Префикс:** 2 символа (`mt`)
- **Hash:** 40 hex символов (20 байт)
- **Всего:** 42 символа

---

## Криптографические Алгоритмы

### MAINNET: ML-DSA-65 (FIPS 204)

**Текущая реализация — POST-QUANTUM:**
- ✅ Post-quantum защита (lattice-based)
- ✅ NIST Level 3 security (128-bit post-quantum)
- ✅ Защита от Shor's algorithm
- ✅ FIPS 204 стандарт
- ✅ Защита от "harvest now, decrypt later"

**Параметры ML-DSA-65:**
```
Private key: 4032 байта
Public key:  1952 байта
Signature:   3309 байт
```

**Реализация:**
```python
# node_crypto.py
from dilithium_py.ml_dsa import ML_DSA_65

def generate_keypair():
    public_key, private_key = ML_DSA_65.keygen()
    return private_key.hex(), public_key.hex()

def sign_message(private_key_hex: str, message: str) -> str:
    private_bytes = bytes.fromhex(private_key_hex)
    message_bytes = message.encode('utf-8')
    signature = ML_DSA_65.sign(private_bytes, message_bytes)
    return signature.hex()

def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    public_bytes = bytes.fromhex(public_key_hex)
    message_bytes = message.encode('utf-8')
    signature = bytes.fromhex(signature_hex)
    return ML_DSA_65.verify(public_bytes, message_bytes, signature)
```

### Статус: MAINNET READY

**Миграция завершена:**
- ~~Q1 2026: Ed25519~~ → ML-DSA-65 MAINNET
- Q2-Q4 2026: Post-quantum защита с genesis

---

## Генерация Адреса

### Алгоритм

```python
def public_key_to_address(public_key_hex: str) -> str:
    """
    Преобразует public key в адрес кошелька Montana

    Формат: mt + SHA256(public_key)[:20].hex()
    """
    # 1. Конвертируем hex в bytes
    public_bytes = bytes.fromhex(public_key_hex)

    # 2. SHA256 хеш
    hash_bytes = hashlib.sha256(public_bytes).digest()

    # 3. Первые 20 байт
    address_bytes = hash_bytes[:20]

    # 4. Hex + префикс
    address = "mt" + address_bytes.hex()

    return address
```

### Пример

```python
public_key = "a3f8b2c1d4e5f6789..."  # 64 символа
              ↓
SHA256(public_key) = "72a4c3e8f9b1d5c7..."  # 64 символа
              ↓
[:20] = "72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a"  # 40 символов
              ↓
"mt" + "72a4c3e8..." = "mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a"
```

---

## Регистрация Узла

### API

```python
from node_crypto import get_node_crypto_system

ncs = get_node_crypto_system()

# Регистрация нового узла
result = ncs.register_node(
    owner_telegram_id=123456789,
    node_name="tokyo",
    location="🇯🇵 Tokyo",
    ip_address="1.2.3.4",
    node_type="light"
)

# Результат
{
    "success": True,
    "address": "mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a",
    "public_key": "a3f8b2c1d4e5...",
    "private_key": "f9d8c7b6a5e4...",  # ⚠️ СОХРАНИ В БЕЗОПАСНОМ МЕСТЕ!
    "alias": "tokyo.montana.network",
    "owner": 123456789
}
```

### Данные Узла

```python
{
    "address": "mt72a4c3e8...",          # Адрес кошелька
    "public_key": "a3f8b2c1...",         # Public key
    "owner": 123456789,                  # Telegram ID владельца
    "node_name": "tokyo",                # Короткое имя
    "alias": "tokyo.montana.network",    # Alias для удобства
    "location": "🇯🇵 Tokyo",             # Локация
    "ip": "1.2.3.4",                     # IP (только для networking!)
    "type": "light",                     # Тип узла
    "official": False,                   # Официальный или нет
    "priority": 10                       # Приоритет в сети
}
```

---

## Подпись и Верификация

### Подпись Транзакции

```python
from node_crypto import sign_message, verify_signature

# Владелец подписывает сообщение своим private key
message = "Transfer 500 seconds to mt9876543210"
signature = sign_message(private_key, message)

print(signature)
# → "a7f8b3c2d1e4f5678..."  # 128 hex символов
```

### Проверка Подписи

```python
# Любой может проверить подпись по public key
is_valid = verify_signature(public_key, message, signature)

print(is_valid)
# → True (валидная подпись)
```

### Проверка Владения Узлом

```python
# Проверить что у отправителя есть private key узла
is_owner = ncs.verify_node_ownership(
    address="mt72a4c3e8...",
    message="Transfer 500 seconds",
    signature_hex="a7f8b3c2d1..."
)

if is_owner:
    # Выполнить перевод
    bank.send("mt72a4c3e8...", "mt9876543210", 500)
else:
    # Отклонить (атака!)
    print("❌ Подпись невалидна")
```

---

## Защита от Атак

### 1. IP Hijacking

**Атака:**
```
Атакующий поднимает сервер с тем же IP 72.56.102.240
↓
Пытается получить доступ к кошельку узла
```

**Защита:**
```
IP адрес НЕ является ключом к кошельку
↓
Адрес кошелька = mt + SHA256(public_key)
↓
Без private key — доступ НЕВОЗМОЖЕН
```

### 2. DNS Spoofing

**Атака:**
```
Атакующий подменяет DNS:
amsterdam.montana.network → 6.6.6.6 (поддельный IP)
```

**Защита:**
```
Alias только для удобства
↓
Реальный адрес = mt72a4c3e8... (криптографический)
↓
DNS не влияет на адрес кошелька
```

### 3. Man-in-the-Middle

**Атака:**
```
Перехват и модификация сообщений между узлами
```

**Защита:**
```
Все операции подписаны ML-DSA-65
↓
Модифицированное сообщение → невалидная подпись
↓
Атака обнаружена и заблокирована
```

### 4. Подделка Транзакций

**Атака:**
```
Атакующий пытается отправить:
"Transfer 9999 seconds from mt72a4c3e8... to attacker"
```

**Защита:**
```
Для транзакции нужна подпись private key узла
↓
У атакующего нет private key
↓
verify_signature() → False
↓
Транзакция отклонена
```

---

## Команды Бота

### `/node <адрес>`
Показать узел по криптографическому адресу:
```bash
/node mt72a4c3e8f9b1d5c7e2a4f6d8b0e1c3a5f7d9e1a
```

### `/node <alias>`
Показать узел по alias:
```bash
/node amsterdam.montana.network
```

### `/node <ip>` (deprecated)
IP адрес больше НЕ является идентификатором:
```bash
/node 72.56.102.240
# → Показывает узел, но предупреждает:
# "⚠️ IP адрес не является ключом. Используй адрес mt..."
```

### `/register_node` (admin only)
Зарегистрировать новый узел:
```bash
/register_node tokyo "🇯🇵 Tokyo" 1.2.3.4 123456789 light
```

---

## Технические Спецификации

### ML-DSA-65 (MAINNET)
| Параметр | Значение |
|----------|----------|
| Алгоритм | ML-DSA-65 (Dilithium) |
| Стандарт | FIPS 204 |
| Security Level | NIST Level 3 (128-bit post-quantum) |
| Размер private key | 4032 байта |
| Размер public key | 1952 байта |
| Размер подписи | 3309 байт |
| Квантовая защита | ✅ С GENESIS |

---

## Ссылки

- **Протокол:** [007_POST_QUANTUM.md](/Users/kh./Python/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿/English/protocol/007_POST_QUANTUM.md)
- **Код:** [node_crypto.py](/Users/kh./Python/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿/Русский/бот/node_crypto.py)
- **Тест:** [test_node_crypto.py](/Users/kh./Python/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿/Русский/бот/test_node_crypto.py)
- **NIST ML-DSA:** [FIPS 204](https://csrc.nist.gov/publications/detail/fips/204/final)
- **NIST ML-KEM:** [FIPS 203](https://csrc.nist.gov/publications/detail/fips/203/final)

---

**Ɉ Montana — Протокол идеальных денег**

*Адрес = Криптографический хеш (не IP)*

*Post-quantum защита от genesis*
