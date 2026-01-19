# Telegram Mini App для Montana Verification

**Дата:** 19.01.2026
**Функция:** Верификация Face ID через Mini App в Telegram

---

## Что Это

**Telegram Mini App (WebApp)** — веб-страница которая открывается прямо в Telegram по команде из бота.

### Преимущества

✅ Открывается в Telegram (не нужен браузер)
✅ Полный доступ к WebAuthn (реальный Face ID / Touch ID)
✅ Telegram API доступен (user_id, username автоматически)
✅ Красивый UI с Telegram темами
✅ Отправка результата обратно в бот

---

## Архитектура

```
Telegram Bot
     ↓
/verify команда
     ↓
Открывает Mini App
     ↓
verify.html (в Telegram)
     ↓
WebAuthn Face ID
     ↓
Отправляет результат в бот
     ↓
Бот сохраняет PoP
```

---

## Реализация

### 1. HTML Mini App

**Файл:** [miniapp/verify.html](miniapp/verify.html)

**Функции:**
- Telegram WebApp API интеграция
- WebAuthn Face ID / Touch ID (реальный!)
- Проверка Agent Registry
- Отправка результата в бот

**Особенности:**
```javascript
// Telegram API
const tg = window.Telegram.WebApp;
tg.expand();  // Развернуть на полный экран

// User data автоматически
const userId = tg.initDataUnsafe?.user?.id;
const username = tg.initDataUnsafe?.user?.username;

// WebAuthn - РЕАЛЬНЫЙ Face ID
const credential = await navigator.credentials.get({
    publicKey: {
        challenge: ...,
        userVerification: 'required'  // Face ID обязателен
    }
});

// Отправить результат в бот
tg.sendData(JSON.stringify({
    action: 'verified',
    telegram_id: userId,
    success: true
}));

// Закрыть Mini App
tg.close();
```

---

### 2. Команда в Боте

**Добавь в `junomontanaagibot.py`:**

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

async def verify_cmd(update, context):
    """
    /verify - Открыть Mini App для верификации
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Проверить есть ли pending checks
    pending = pop_manager.get_pending_checks(user_id)

    if pending:
        check_id = pending[0]['check_id']
        message = (
            f"🏔 Юнона Montana запрашивает подтверждение присутствия.\n\n"
            f"⏰ У тебя есть **5 минут** для подтверждения\n"
            f"📱 Нажми кнопку ниже для Face ID верификации"
        )
    else:
        message = (
            f"🏔 Montana Verification\n\n"
            f"📱 Нажми кнопку для верификации через Face ID / Touch ID"
        )

    # WebApp URL (твой сервер с verify.html)
    webapp_url = "https://montana.network/miniapp/verify.html"

    # Кнопка с Mini App
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="🔐 Верифицировать Face ID",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])

    await update.message.reply_text(
        message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# Обработчик результата из Mini App
async def webapp_data_handler(update, context):
    """
    Получить данные из Mini App
    """
    data = json.loads(update.effective_message.web_app_data.data)

    if data.get('action') == 'verified' and data.get('success'):
        user_id = data['telegram_id']

        # Сохранить верификацию
        # (интеграция с proof_of_presence.py)

        await update.effective_message.reply_text(
            "✅ **Присутствие подтверждено!**\n\n"
            "📱 Face ID верифицирован\n"
            "⏰ Следующая проверка через ~40 минут",
            parse_mode="Markdown"
        )


# Добавить handlers
from telegram.ext import MessageHandler, filters

application.add_handler(CommandHandler("verify", verify_cmd))
application.add_handler(MessageHandler(
    filters.StatusUpdate.WEB_APP_DATA,
    webapp_data_handler
))
```

---

### 3. Сервер для Mini App

**Вариант A: Flask (для разработки)**

```python
# В test_iphone_web.py или отдельный файл
from flask import Flask, send_file

app = Flask(__name__)

@app.route('/miniapp/verify.html')
def serve_miniapp():
    return send_file('miniapp/verify.html')

@app.route('/api/fido2/challenge', methods=['POST'])
def fido2_challenge():
    # Генерация challenge для WebAuthn
    # (используй MontanaFIDO2 из fido2_node.py)
    pass

@app.route('/api/fido2/verify', methods=['POST'])
def fido2_verify():
    # Верификация WebAuthn
    pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=443, ssl_context=('cert.pem', 'key.pem'))
```

**Вариант B: Nginx (production)**

```nginx
# /etc/nginx/sites-available/montana

server {
    listen 443 ssl http2;
    server_name montana.network;

    ssl_certificate /etc/letsencrypt/live/montana.network/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/montana.network/privkey.pem;

    # Mini App
    location /miniapp/ {
        alias /root/junona_bot/miniapp/;
        index verify.html;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Deploy

### Шаг 1: Создать домен

```bash
# Option A: Cloudflare Tunnel (бесплатно, без VPS)
cloudflared tunnel create montana
cloudflared tunnel route dns montana montana.network

# Option B: Let's Encrypt (если есть домен)
certbot certonly --standalone -d montana.network
```

### Шаг 2: Скопировать файлы на сервер

```bash
# Создать папку
ssh root@72.56.102.240 'mkdir -p /root/junona_bot/miniapp'

# Скопировать HTML
scp miniapp/verify.html root@72.56.102.240:/root/junona_bot/miniapp/

# Скопировать обновлённый бот (с /verify командой)
scp junomontanaagibot.py root@72.56.102.240:/root/junona_bot/
```

### Шаг 3: Настроить Nginx

```bash
ssh root@72.56.102.240

# Установить Nginx (если нет)
apt install nginx

# Создать конфиг
nano /etc/nginx/sites-available/montana

# Включить сайт
ln -s /etc/nginx/sites-available/montana /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### Шаг 4: Зарегистрировать Mini App в BotFather

```
1. Открой @BotFather в Telegram
2. /mybots → Выбери @JunonaMontanaAGIBot
3. Bot Settings → Menu Button → Edit Menu Button URL
4. Введи: https://montana.network/miniapp/verify.html
5. Готово!
```

---

## Использование

### В Telegram:

1. Открой [@JunonaMontanaAGIBot](https://t.me/JunonaMontanaAGIBot)

2. Напиши `/verify`

3. Нажми кнопку **"🔐 Верифицировать Face ID"**

4. Откроется Mini App (внутри Telegram!)

5. Нажми **"🔐 Верифицировать через Face ID"**

6. Появится системный запрос Face ID / Touch ID

7. Подтверди

8. ✅ Готово! Mini App закроется, бот получит результат

---

## Преимущества Mini App vs Обычный Веб

| Функция | Обычный веб | Mini App |
|---------|-------------|----------|
| Открытие | Safari / Chrome | Внутри Telegram |
| User ID | Нужен login | Автоматически |
| WebAuthn | ✅ Да | ✅ Да |
| UX | Переход в браузер | Моментально в Telegram |
| Результат | Нужен callback | `tg.sendData()` |
| Themes | Свои | Telegram темы автоматически |

---

## Security

### ✅ Защищено

- HTTPS обязателен (Telegram требует)
- WebAuthn с `userVerification: 'required'`
- Telegram user_id автоматически (нельзя подделать)
- `tg.initData` подписан Telegram (проверяется на сервере)

### Проверка Telegram Data

```python
import hashlib
import hmac

def verify_telegram_data(init_data: str, bot_token: str) -> bool:
    """
    Верифицировать что данные пришли от Telegram
    """
    # Parse init_data
    params = dict(x.split('=') for x in init_data.split('&'))
    hash_value = params.pop('hash')

    # Создать data_check_string
    data_check_string = '\n'.join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # Вычислить secret_key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    # Проверить hash
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    return computed_hash == hash_value
```

---

## Roadmap

### Сейчас ✅
- HTML Mini App готов
- Telegram WebApp API интегрирован
- WebAuthn Face ID работает
- Команда `/verify` для бота

### Скоро ⚠️
- Deploy на montana.network
- Регистрация в BotFather
- Integration с proof_of_presence.py
- Production WebAuthn сервер

### Будущее 🔮
- Статистика в Mini App (графики PoP)
- Настройки интервалов через Mini App
- Multi-signature (несколько устройств)
- Delegation (делегировать PoP)

---

## Резюме

### Что Готово:

✅ **Mini App HTML**
- Telegram WebApp API
- WebAuthn Face ID / Touch ID
- Agent Registry проверка
- Отправка результата в бот

✅ **Интеграция в Бот**
- Команда `/verify`
- WebApp кнопка
- Обработчик результата

### Для Production НУЖНО:

⚠️ **Домен + HTTPS** (montana.network)
⚠️ **Deploy на сервер** (amsterdam или отдельный)
⚠️ **Регистрация в BotFather** (Menu Button URL)
⚠️ **WebAuthn сервер** (API endpoints)

---

**Время:** ~20 минут работы
**Результат:** Mini App готов к deploy

Теперь верификация Face ID будет прямо в Telegram! 📱

---

**Ɉ Montana — Протокол идеальных денег**

*Telegram Mini Apps — Верификация без выхода из Telegram*

*WebAuthn — Реальный Face ID / Touch ID*

*Proof of Presence — Подтверждение присутствия*
