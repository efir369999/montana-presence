# ✅ Бот с Mini Apps готов

**Дата:** 19.01.2026  
**Функция:** Telegram бот с Mini Apps для Montana Protocol

---

## Что работает

### 1. **Команды бота**

В Telegram боте [@JunonaMontanaAGIBot](https://t.me/JunonaMontanaAGIBot) доступны команды:

```
/start   - 🏠 Главная — баланс и команды
/menu    - 📱 Меню Montana (Mini App)
/verify  - 🔐 Верификация Face ID (Mini App)
/balance - 💰 Баланс кошелька
/transfer - 💸 Перевод времени
/tx      - 📊 История транзакций
/feed    - 📡 Публичная лента
/node    - 🌐 Узлы Montana
/stream  - 💬 Лента диалога
```

### 2. **Mini Apps**

#### `/menu` - Меню Montana
- Открывает Mini App с кнопками для всех функций
- Разделы:
  - **Безопасность**: Верификация Face ID, Регистрация узла
  - **Кошелек**: Баланс, Перевод, История
  - **Сеть**: Узлы, Публичная лента

#### `/verify` - Верификация
- Открывает Mini App для Face ID / Touch ID верификации
- WebAuthn биометрия (в production)
- ML-DSA-65 подписи
- Proof of Presence

---

## Как это работает

### Для пользователя:

1. **Открыть Telegram** → [@JunonaMontanaAGIBot](https://t.me/JunonaMontanaAGIBot)

2. **Написать команду** `/menu` или `/verify`

3. **Нажать кнопку** "Открыть меню" или "Верифицировать Face ID"

4. **Mini App откроется** прямо в Telegram (не нужен браузер!)

5. **Использовать функции** через удобный интерфейс

---

## Архитектура

```
Telegram Bot (@JunonaMontanaAGIBot)
     ↓
/menu или /verify команда
     ↓
InlineKeyboardButton с WebAppInfo
     ↓
Mini App открывается в Telegram
     ↓
HTML страница (menu.html / verify.html)
     ↓
Telegram WebApp API
     ↓
Пользователь взаимодействует
     ↓
tg.sendData() отправляет результат в бот
     ↓
Бот получает данные через webapp_data_handler
```

---

## Файлы

### Бот
- **junomontanaagibot.py** - Telegram бот с Mini App командами
  - `menu_cmd()` - Команда /menu
  - `verify_cmd()` - Команда /verify
  - `webapp_data_handler()` - Обработчик данных от Mini Apps

### Mini Apps
- **miniapp/menu.html** - Меню Montana с кнопками для всех функций
- **miniapp/verify.html** - Верификация Face ID / Touch ID

### Сервер
- **test_iphone_web.py** - Flask сервер для Mini Apps
  - Routes: `/miniapp/menu.html`, `/miniapp/verify.html`
  - API: `/api/agents`, `/api/fido2/register`, etc.

---

## Тестирование

### На Mac (локально):

1. Flask сервер запущен:
   ```
   http://192.168.0.127:5001
   ```

2. Mini Apps доступны:
   - http://192.168.0.127:5001/miniapp/menu.html
   - http://192.168.0.127:5001/miniapp/verify.html

### В Telegram:

1. Открой бота: [@JunonaMontanaAGIBot](https://t.me/JunonaMontanaAGIBot)

2. Напиши `/menu` → Нажми кнопку → Mini App откроется

3. Напиши `/verify` → Нажми кнопку → Верификация Face ID

---

## Production Deploy

### Что нужно для production:

1. **Домен с HTTPS**
   ```
   montana.network (или любой другой)
   ```

2. **SSL сертификат**
   ```bash
   certbot certonly --standalone -d montana.network
   ```

3. **Обновить URL в боте**
   ```python
   # В junomontanaagibot.py
   MINIAPP_BASE_URL = "https://montana.network/miniapp"
   ```

4. **Deploy Mini Apps на сервер**
   ```bash
   scp -r miniapp/ root@server:/var/www/montana/
   ```

5. **Nginx конфигурация**
   ```nginx
   location /miniapp/ {
       alias /var/www/montana/miniapp/;
       index menu.html;
   }
   ```

---

## Как добавить новый Mini App

### Шаг 1: Создать HTML страницу

```bash
# Создать miniapp/new_feature.html
```

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>
    <h1>New Feature</h1>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        // Твоя логика
        
        // Отправить результат в бот
        tg.sendData(JSON.stringify({
            action: 'feature_completed',
            data: {...}
        }));
    </script>
</body>
</html>
```

### Шаг 2: Добавить route в Flask

```python
# В test_iphone_web.py
@app.route('/miniapp/new_feature.html')
def serve_new_feature():
    return send_file('miniapp/new_feature.html')
```

### Шаг 3: Добавить команду в бота

```python
# В junomontanaagibot.py
async def new_feature_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = f"{MINIAPP_BASE_URL}/new_feature.html"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="📱 Open Feature",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])
    
    await update.message.reply_text(
        "New Feature Description",
        reply_markup=keyboard
    )

# В main()
application.add_handler(CommandHandler("new_feature", new_feature_cmd))
```

### Шаг 4: Добавить в меню

```python
# В setup_bot_commands()
commands = [
    # ...
    BotCommand("new_feature", "📱 New Feature"),
]
```

---

## Преимущества Mini Apps

| Функция | Обычный веб | Mini App |
|---------|-------------|----------|
| Открытие | Safari / Chrome | Внутри Telegram |
| User ID | Нужен login | Автоматически из Telegram |
| UX | Переход в браузер | Моментально в Telegram |
| Результат | Нужен callback | `tg.sendData()` прямо в бот |
| Themes | Свои стили | Telegram темы автоматически |

---

## Резюме

✅ **Готово:**
- Telegram бот с командами для Mini Apps
- Menu Mini App - меню всех функций
- Verify Mini App - верификация Face ID
- Flask сервер с routes для Mini Apps
- Интеграция через WebAppInfo кнопки

✅ **Работает:**
- Локально на Mac (192.168.0.127:5001)
- На Amsterdam сервере (бот)
- Команды /menu и /verify в боте

⚠️ **Для production нужно:**
- HTTPS домен (montana.network)
- Deploy Mini Apps на сервер
- Обновить MINIAPP_BASE_URL

---

**Ɉ Montana — Протокол идеальных денег**

*Mini Apps — Функции Montana прямо в Telegram*

*Как BotFather, но для Montana Protocol*
