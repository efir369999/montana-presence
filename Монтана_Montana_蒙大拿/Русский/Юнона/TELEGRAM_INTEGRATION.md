# Telegram Integration — Юнона в Telegram

Два способа интегрировать веб-чат Юноны с Telegram.

---

## Вариант 1: Telegram Mini App (Web App)

**Что это:** Веб-чат efir.org открывается ВНУТРИ Telegram как нативное приложение.

### Плюсы:
- ✅ Полный контроль над UI (наш веб-интерфейс)
- ✅ Доступ к Telegram API (user info, payments, etc.)
- ✅ Работает на iOS/Android/Desktop
- ✅ Нативные кнопки/меню Telegram

### Как сделать:

#### 1. Создать Telegram Bot
```bash
# Написать @BotFather в Telegram
/newbot
# Название: Junona Montana
# Username: junona_montana_bot

# Получишь токен: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

#### 2. Настроить Web App
```bash
# В @BotFather
/newapp

# URL: https://efir.org
# Short name: junona
# Title: Юнона Монтана
# Description: AI-агент Montana Protocol
# Photo: загрузить ЮНОНА_МОНТАНА.JPG
```

#### 3. Добавить Telegram SDK в index.html
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
// Доступ к Telegram API
const tg = window.Telegram.WebApp;

// Получить данные пользователя
const user = tg.initDataUnsafe.user;
console.log('Telegram user:', user.first_name, user.username);

// Изменить цвет header
tg.setHeaderColor('#0a0a0a');

// Показать кнопку "Назад"
tg.BackButton.show();
tg.BackButton.onClick(() => tg.close());

// Растянуть на весь экран
tg.expand();
</script>
```

#### 4. Запустить бота
```bash
# В Telegram:
# /start @junona_montana_bot
# Или открыть Web App через кнопку
```

### Дополнительные возможности:
- **Payments:** Принимать платежи в Ɉ через Telegram
- **User Auth:** Автоматическая авторизация через Telegram ID
- **Notifications:** Push-уведомления от бота
- **Share:** Делиться результатами чата в Telegram

---

## Вариант 2: Telegram Bot с proxy к API

**Что это:** Классический бот который проксирует запросы к `/api/chat`.

### Плюсы:
- ✅ Нативный Telegram UI (пузырьки, кнопки)
- ✅ Работает везде где есть Telegram
- ✅ Проще для пользователей (просто напиши боту)

### Как сделать:

#### 1. Создать бота (см. выше)

#### 2. Написать Python бот (python-telegram-bot)
```python
#!/usr/bin/env python3
"""
Telegram Bot для Юноны Монтана
"""

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Токен от BotFather
TELEGRAM_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

# Montana API
JUNONA_API_URL = "https://efir.org/api/chat"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "Привет! Я Юнона Монтана, AI-агент Montana Protocol.\n\n"
        "Просто напиши мне любой вопрос!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user message"""
    question = update.message.text

    # Показать "typing..."
    await update.message.chat.send_action("typing")

    # Запрос к Montana API
    response = requests.post(
        JUNONA_API_URL,
        json={"question": question, "lang": "ru"},
        timeout=30
    )

    data = response.json()
    answer = data.get("answer", "Ошибка соединения")

    # Отправить ответ
    await update.message.reply_text(answer)


def main():
    """Start bot"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
```

#### 3. Установить зависимости
```bash
pip install python-telegram-bot requests
```

#### 4. Запустить бота
```bash
python junona_telegram_bot.py
```

#### 5. Deploy на Amsterdam сервер
```bash
# Скопировать на сервер
scp junona_telegram_bot.py montana-ams:/root/montana/

# Запустить в systemd
ssh montana-ams
sudo nano /etc/systemd/system/junona-telegram.service
```

**Содержимое junona-telegram.service:**
```ini
[Unit]
Description=Junona Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/montana
ExecStart=/usr/bin/python3 /root/montana/junona_telegram_bot.py
Restart=always
Environment="TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

[Install]
WantedBy=multi-user.target
```

```bash
# Запустить
sudo systemctl daemon-reload
sudo systemctl enable junona-telegram
sudo systemctl start junona-telegram
sudo systemctl status junona-telegram
```

---

## Вариант 3: Hybrid (лучшее из обоих миров)

**Идея:** Bot + Web App вместе

1. **Бот** - для быстрых вопросов в чате Telegram
2. **Web App** - для полноценного диалога с реакциями, reply, history

**Как:**
- Команда `/chat` → открывает Web App (efir.org)
- Обычные сообщения → отвечает бот напрямую

```python
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open web chat"""
    keyboard = [[InlineKeyboardButton(
        "Открыть чат с Юноной",
        web_app=WebAppInfo(url="https://efir.org")
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Открой полноценный чат с Юноной:",
        reply_markup=reply_markup
    )
```

---

## Рекомендация

**Начни с Варианта 1 (Mini App):**
- ✅ Используешь уже готовый веб-интерфейс
- ✅ Все функции мессенджера сразу работают
- ✅ Можно потом добавить бота для уведомлений

**Потом добавь Вариант 2 (Bot):**
- ✅ Для тех кто хочет быстро спросить
- ✅ Для push-уведомлений
- ✅ Для интеграции с другими Telegram фичами

---

## Готовые файлы

**Для деплоя:**
1. `junona_telegram_bot.py` - Python бот (создать)
2. `junona-telegram.service` - Systemd service (создать)
3. `efir.org/index.html` - уже готов с Telegram SDK support

**Токены хранить в keychain:**
```bash
# Telegram Bot Token
security add-generic-password -a "montana" -s "TELEGRAM_BOT_TOKEN" -w "123456:ABC-DEF..."
```

---

**Автор:** Alejandro Montana
**Дата:** 14.02.2026
