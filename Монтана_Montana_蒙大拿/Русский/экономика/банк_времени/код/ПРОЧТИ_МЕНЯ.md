# TIME_BANK — Код Банка Времени

**Версия:** 3.0
**Дата:** Январь 2026

---

## Философия

```
Montana = Организм
TIME_BANK = Орган верификации эмиссии монет времени
```

**TIME_BANK верифицирует:**
- Прошло ровно 10 минут (600 секунд)
- Участники присутствовали N секунд
- Применяет халвинг
- Подтверждает эмиссию

**TIME_BANK НЕ печатает** монеты из воздуха — он **подтверждает время**.

---

## Структура модулей

```
код/
├── protocol.py              # Константы протокола
├── halving.py               # Логика халвинга
├── temporal_coordinates.py  # τ₁, τ₂, τ₃, τ₄
├── presence_cache.py        # Кэш присутствия
├── presence_proof.py        # ML-DSA-65 подписи
├── time_bank.py             # Основной класс
└── README.md                # Этот файл
```

---

## Использование

### Базовое использование

```python
from time_bank import get_time_bank

# Получить singleton TIME_BANK
bank = get_time_bank()

# Начать присутствие
bank.start(address="user_123", addr_type="telegram")

# Регистрировать активность
bank.activity(address="user_123")

# Завершить присутствие
bank.end(address="user_123")

# Проверить баланс
balance = bank.balance(address="user_123")
```

### Статистика

```python
stats = bank.stats()

print(f"τ₂ count: {stats['t2_count']}")
print(f"τ₃ count: {stats['tau3_count']}")
print(f"τ₄ count: {stats['tau4_count']}")
print(f"Халвинг: {stats['halving_coefficient']:.4f}x")
print(f"Год: {stats['current_year']}")
```

### Presence Proofs

```python
# Получить последние 10 proofs
proofs = bank.get_presence_proofs(limit=10)

for proof in proofs:
    print(f"T2 #{proof['t2_index']}")
    print(f"Hash: {proof['proof_hash'][:32]}...")
    print(f"Active: {proof['active_addresses']} addresses")
```

---

## Интеграция с Montana

TIME_BANK работает как **отдельный орган**, но интегрирован с:

- **ML-DSA-65** — пост-квантовые подписи
- **MontanaDB** — хранилище балансов
- **3-Mirror** — синхронизация узлов
- **Юнона (бот)** — интерфейс пользователя

### Пример интеграции с ботом

```python
from time_bank import get_time_bank

bank = get_time_bank()

@bot.message_handler(commands=['start'])
async def start_presence(message):
    user_id = str(message.from_user.id)
    bank.start(user_id, "telegram")
    await bot.reply("⏱️ Присутствие начато!")

@bot.message_handler(commands=['balance'])
async def show_balance(message):
    user_id = str(message.from_user.id)
    balance = bank.balance(user_id)
    await bot.reply(f"💰 Баланс: {balance} Ɉ")
```

---

## Важные особенности

### 1. Динамическая эмиссия

```python
# Эмиссия зависит от участников
total_seconds = sum(user.seconds for user in users)
emission = total_seconds × halving_coefficient
```

### 2. Банк вычитает себя

```python
# Банк подтверждает 600 секунд
bank_seconds = 600

# Вычитает свои секунды
emission = (total + bank - bank) × halving
         = total × halving
```

### 3. Халвинг каждые τ₄

```python
# τ₄ = 0: 1.0x
# τ₄ = 1: 0.5x (÷2)
# τ₄ = 2: 0.25x (÷2)
# τ₄ = 3: 0.125x (÷2)
```

---

## Лицензия

Montana Protocol v1.0
Copyright © 2026 Alejandro Montana
