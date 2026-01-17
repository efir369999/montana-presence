# knowledge/connect.py
# Как подключить бота к сети

KNOWLEDGE_CONNECT = """ПОДКЛЮЧЕНИЕ К СЕТИ MONTANA:

ШАГ 1 — СОЗДАТЬ БОТА:
- Открой @BotFather в Telegram
- /newbot → придумай имя → получишь TELEGRAM_TOKEN
- Сохрани токен (не показывай никому!)

ШАГ 2 — СОЗДАТЬ СТРУКТУРУ:
```
твой_бот/
├── .env                 # TELEGRAM_TOKEN=твой_токен
├── bot.py               # Основной код
├── data/users.json      # База пользователей (создастся автоматом)
└── content/             # Контент (опционально)
```

ШАГ 3 — МИНИМАЛЬНЫЙ КОД:
```python
from telegram.ext import ApplicationBuilder, CommandHandler
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update, context):
    await update.message.reply_text("Привет! Я подключён к Montana.")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
```

ШАГ 4 — УСТАНОВИТЬ ЗАВИСИМОСТИ:
```bash
pip install python-telegram-bot python-dotenv
```

ШАГ 5 — ЗАПУСТИТЬ:
```bash
python bot.py
```

УЗЛЫ СЕТИ ДЛЯ СИНХРОНИЗАЦИИ:
- Амстердам: 72.56.102.240 (PRIMARY)
- Москва: 176.124.208.93
- Алматы: 91.200.148.93
- СПб: 188.225.58.98
- Новосибирск: 147.45.147.247

СИНХРОНИЗАЦИЯ USERS.JSON:
- Каждый бот = узел подсети
- Формат: {"user_id": {"lang": "ru", "chapter": 0, "state": "..."}}
- Синхронизация через rsync/git каждые 12 секунд

ЕСЛИ СКИНУЛИ ТОКЕН:
1. Сохрани в .env как TELEGRAM_TOKEN=токен
2. Скопируй код выше
3. Запусти python bot.py

ЕСЛИ СКИНУЛИ КОД:
- Разбери что делает
- Объясни какие handlers добавить
- Покажи как подключить к сети"""
