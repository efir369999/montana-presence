# 🏔 Юнона Montana Bot — Техническая Спецификация

**Дата:** 18.01.2026
**Версия:** Full Edition v2.0 (Multilingual)

---

## 📋 Основная информация

**Бот:** @junomontanaagibot
**Токен:** см. keyring: TELEGRAM_TOKEN_JUNONA
**Сервер:** Amsterdam (72.56.102.240)
**Директория:** `/root/junona_bot/`
**Процесс:** `junona_bot_full.py`

---

## 🚀 ПРАВИЛЬНЫЙ ЗАПУСК

```bash
# Полная процедура (одной командой)
ssh root@72.56.102.240 "pkill -f junona_bot_full.py && sleep 2 && cd /root/junona_bot && source venv/bin/activate && nohup python junona_bot_full.py > bot_full.log 2>&1 & sleep 5 && tail -20 bot_full.log"
```

### Пошагово:

```bash
# 1. Остановить старый процесс
pkill -f junona_bot_full.py

# 2. Подождать
sleep 2

# 3. Проверить остановку
ps aux | grep junona_bot_full | grep -v grep
# Должно быть пусто!

# 4. Запустить
cd /root/junona_bot
source venv/bin/activate
nohup python junona_bot_full.py > bot_full.log 2>&1 &

# 5. Проверить лог
sleep 5
tail -30 bot_full.log
```

---

## ✅ Проверка что бот запущен правильно

### 1. Лог должен показывать:

```
INFO - 🏔 Montana Evolution: агенты инициализированы
INFO - 📖 Channel Parser: инициализирован
INFO - 🏔 Юнона Montana Full Edition — запущена
INFO -    Параллельные агенты: ✓
INFO -    Channel Parser: ✓
INFO - Application started
```

### 2. Процесс должен быть:

```bash
ps aux | grep junona_bot_full | grep -v grep
```

**ВАЖНО:** Время запуска процесса ПОСЛЕ изменения файла!

### 3. Проверка файлов:

```bash
ls -la /root/junona_bot/*.py | grep -E 'junona_bot_full|language_detector'
```

Должны быть:
- junona_bot_full.py (19KB)
- language_detector.py (3.5KB)

---

## 🎯 Команды бота (v2.0)

```
/start    - Выбор языка (кнопки 🇷🇺🇬🇧🇨🇳)
/network  - Статус сети + токеномика
/book     - Части Благаявести
/sync     - Проверить канал
/help     - Помощь
```

---

## 🔧 Обновить меню команд

```bash
ssh root@72.56.102.240 "cd /root/junona_bot && python << 'PYEOF'
import asyncio
from telegram import Bot, BotCommand

async def update():
    bot = Bot(os.popen('security find-generic-password -a montana -s TELEGRAM_TOKEN_JUNONA -w').read().strip())
    await bot.set_my_commands([
        BotCommand('start', 'Montana Full Edition'),
        BotCommand('network', 'Network Status'),
        BotCommand('book', 'Blagayavest'),
        BotCommand('sync', 'Check Channel'),
        BotCommand('help', 'Help')
    ])
    print('✓ Updated')

asyncio.run(update())
PYEOF
"
```

---

## 🐛 Troubleshooting

### Кнопки языка не работают

**Причина:** Бот запущен ДО загрузки нового кода

**Решение:**
1. Проверить дату файла vs время процесса
2. Если процесс старее → перезапустить!

### Старое меню команд

**Причина:** Кэш Telegram

**Решение:**
1. Закрыть Telegram (force stop)
2. Открыть снова
3. ИЛИ обновить через API (команда выше)

---

**Время как proof.**

金元Ɉ Montana
18.01.2026
