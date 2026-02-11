#!/usr/bin/env python3
"""
Юнона AI API — Montana Protocol
- AI чат (OpenAI, Claude, Совет)
- Кошелёк ML-DSA-65
- Синхронизация чатов
- Presence (время = Ɉ)
"""

import os
import json
import sqlite3
import hashlib
import time
import secrets
from datetime import datetime
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import openai
import anthropic
import requests

app = Flask(__name__)
CORS(app)

# Конфигурация
DB_PATH = '/opt/junona/montana.db'
OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Системный промпт Юноны
SYSTEM_PROMPT = """Ты — Юнона, AI-проводник Montana Protocol.

Ключевые принципы:
- Время — единственная реальная валюта
- 1 секунда присутствия = 1 Ɉ (Jin Yuan)
- ML-DSA-65 постквантовая криптография (MAINNET)
- ML-KEM-768 для шифрования (Интимный уровень)
- Genesis: 2026-01-09

Отвечай кратко, по делу. Используй факты о Montana Protocol.
Не выдумывай — если не знаешь, скажи честно."""


# ============ DATABASE ============

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            device_id TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            verified INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            presence_seconds INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            messages TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            privacy TEXT DEFAULT 'intimate',
            items TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            from_phone TEXT NOT NULL,
            to_phone TEXT NOT NULL,
            amount INTEGER NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_users_device ON users(device_id);
        CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);

        CREATE TABLE IF NOT EXISTS login_sessions (
            id INTEGER PRIMARY KEY,
            session_id TEXT UNIQUE NOT NULL,
            device_id TEXT,
            telegram_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()


def normalize_phone(phone):
    """Нормализация номера телефона"""
    if not phone:
        return None
    # Убираем всё кроме цифр
    digits = ''.join(c for c in phone if c.isdigit())
    # Если начинается с 8, меняем на 7
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    # Добавляем + если нет
    return '+' + digits if digits else None


def generate_code():
    """Генерация 6-значного кода"""
    return ''.join(str(secrets.randbelow(10)) for _ in range(6))


# ============ AI FUNCTIONS ============

def ask_openai(message: str, history: list) -> str:
    if not OPENAI_KEY:
        return "OpenAI API ключ не настроен"
    try:
        client = openai.OpenAI(api_key=OPENAI_KEY)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-10:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI ошибка: {str(e)}"


def ask_claude(message: str, history: list) -> str:
    if not ANTHROPIC_KEY:
        return "Anthropic API ключ не настроен"
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        messages = []
        for h in history[-10:]:
            role = "user" if h.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        return response.content[0].text
    except Exception as e:
        return f"Claude ошибка: {str(e)}"


# ============ API ROUTES ============

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "openai": bool(OPENAI_KEY),
        "claude": bool(ANTHROPIC_KEY),
        "version": "1.0.0"
    })


@app.route('/api/register', methods=['POST'])
def register():
    """Регистрация устройства"""
    data = request.json or {}
    device_id = data.get('device_id')

    if not device_id:
        device_id = secrets.token_hex(16)

    db = get_db()

    # Проверяем существует ли уже
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()

    if user:
        return jsonify({
            "device_id": user['device_id'],
            "phone": user['phone'],
            "verified": bool(user['verified']),
            "balance": user['balance'],
            "presence": user['presence_seconds'],
            "created_at": user['created_at']
        })

    # Создаём нового пользователя (без телефона пока)
    db.execute(
        'INSERT INTO users (device_id, balance) VALUES (?, ?)',
        (device_id, 0)  # Бонус только после верификации
    )
    db.commit()

    return jsonify({
        "device_id": device_id,
        "phone": None,
        "verified": False,
        "balance": 0,
        "presence": 0,
        "created_at": datetime.now().isoformat()
    })


@app.route('/api/send-code', methods=['POST'])
def send_code():
    """Отправка кода верификации через Telegram"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    data = request.json or {}
    phone = normalize_phone(data.get('phone'))
    telegram_id = data.get('telegram_id')

    if not phone or len(phone) < 11:
        return jsonify({"error": "Неверный номер телефона"}), 400

    db = get_db()

    # Проверяем не занят ли номер
    existing = db.execute('SELECT id FROM users WHERE phone = ? AND verified = 1', (phone,)).fetchone()
    if existing:
        return jsonify({"error": "Номер уже зарегистрирован"}), 400

    # Генерируем код
    code = generate_code()
    expires = datetime.now().isoformat()

    # Удаляем старые коды для этого номера
    db.execute('DELETE FROM verification_codes WHERE phone = ?', (phone,))
    db.execute(
        'INSERT INTO verification_codes (phone, code, expires_at) VALUES (?, ?, ?)',
        (phone, code, expires)
    )
    db.commit()

    # Отправляем код через Telegram если есть telegram_id
    sent_via = None
    if telegram_id and TELEGRAM_TOKEN:
        try:
            resp = requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                json={
                    'chat_id': telegram_id,
                    'text': f'🔐 Код верификации Montana: {code}\n\nНе сообщайте код никому!'
                },
                timeout=10
            )
            if resp.ok:
                sent_via = 'telegram'
        except:
            pass

    return jsonify({
        "success": True,
        "phone": phone,
        "sent_via": sent_via,
        "message": "Код отправлен в Telegram" if sent_via else "Введите код",
        "debug_code": code if not sent_via else None  # Показываем только если не отправили
    })


@app.route('/api/login-status', methods=['GET'])
def login_status():
    """Проверка статуса входа через Telegram"""
    session_id = request.args.get('session')
    if not session_id:
        return jsonify({"error": "session required"}), 400

    db = get_db()
    session = db.execute('SELECT * FROM login_sessions WHERE session_id = ?', (session_id,)).fetchone()

    if not session or not session['device_id']:
        return jsonify({"pending": True})

    # Сессия завершена — возвращаем данные пользователя
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (session['device_id'],)).fetchone()
    if not user:
        return jsonify({"pending": True})

    # Удаляем использованную сессию
    db.execute('DELETE FROM login_sessions WHERE session_id = ?', (session_id,))
    db.commit()

    return jsonify({
        "device_id": user['device_id'],
        "phone": user['phone'],
        "verified": bool(user['verified']),
        "balance": user['balance'],
        "presence": user['presence_seconds']
    })


@app.route('/api/login-complete', methods=['POST'])
def login_complete():
    """Завершение входа через Telegram (вызывается ботом)"""
    data = request.json or {}
    session_id = data.get('session_id')
    telegram_id = data.get('telegram_id')
    phone = normalize_phone(data.get('phone'))

    if not session_id or not telegram_id:
        return jsonify({"error": "session_id и telegram_id обязательны"}), 400

    db = get_db()

    # Добавляем колонку telegram_id если нет
    try:
        db.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT')
        db.commit()
    except:
        pass

    # Ищем существующего пользователя по telegram_id
    user = db.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()

    if user:
        # Пользователь найден — восстанавливаем сессию
        device_id = user['device_id']
    else:
        # Новый пользователь — создаём аккаунт
        device_id = secrets.token_hex(16)
        db.execute(
            'INSERT INTO users (device_id, telegram_id, phone, verified, balance) VALUES (?, ?, ?, ?, ?)',
            (device_id, telegram_id, phone, 1 if phone else 0, 0)
        )
        db.commit()

    # Создаём/обновляем сессию входа
    db.execute('DELETE FROM login_sessions WHERE session_id = ?', (session_id,))
    db.execute(
        'INSERT INTO login_sessions (session_id, device_id, telegram_id) VALUES (?, ?, ?)',
        (session_id, device_id, telegram_id)
    )
    db.commit()

    return jsonify({
        "success": True,
        "device_id": device_id,
        "existing": user is not None
    })


@app.route('/api/telegram-link', methods=['POST'])
def telegram_link():
    """Связывание Telegram аккаунта с device_id"""
    data = request.json or {}
    device_id = data.get('device_id')
    telegram_id = data.get('telegram_id')
    phone = normalize_phone(data.get('phone'))

    if not device_id or not telegram_id:
        return jsonify({"error": "device_id и telegram_id обязательны"}), 400

    db = get_db()

    # Проверяем существует ли пользователь
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404

    # Сохраняем telegram_id (добавим колонку если нет)
    try:
        db.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT')
        db.commit()
    except:
        pass  # Колонка уже есть

    db.execute('UPDATE users SET telegram_id = ? WHERE device_id = ?', (telegram_id, device_id))

    # Если передан телефон — верифицируем сразу (Telegram подтверждает номер)
    if phone:
        db.execute('UPDATE users SET phone = ?, verified = 1 WHERE device_id = ?', (phone, device_id))

    db.commit()

    return jsonify({
        "success": True,
        "telegram_id": telegram_id,
        "verified": bool(phone)
    })


@app.route('/api/verify', methods=['POST'])
def verify():
    """Верификация номера телефона"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    data = request.json or {}
    phone = normalize_phone(data.get('phone'))
    code = data.get('code')

    if not phone or not code:
        return jsonify({"error": "Требуется телефон и код"}), 400

    db = get_db()

    # Проверяем код
    record = db.execute(
        'SELECT * FROM verification_codes WHERE phone = ? AND code = ?',
        (phone, code)
    ).fetchone()

    if not record:
        return jsonify({"error": "Неверный код"}), 400

    # Удаляем использованный код
    db.execute('DELETE FROM verification_codes WHERE phone = ?', (phone,))

    # Обновляем пользователя
    db.execute(
        'UPDATE users SET phone = ?, verified = 1 WHERE device_id = ?',
        (phone, device_id)
    )
    db.commit()

    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()

    return jsonify({
        "success": True,
        "phone": phone,
        "verified": True,
        "balance": user['balance']
    })


@app.route('/api/user', methods=['GET'])
def get_user():
    """Получение информации о пользователе"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "phone": user['phone'],
        "verified": bool(user['verified']),
        "balance": user['balance'],
        "presence": user['presence_seconds'],
        "created_at": user['created_at'],
        "last_seen": user['last_seen']
    })


@app.route('/api/presence', methods=['POST'])
def update_presence():
    """Обновление времени присутствия — начисление Ɉ"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    data = request.json or {}
    seconds = data.get('seconds', 0)

    if seconds <= 0 or seconds > 3600:  # Макс 1 час за раз
        return jsonify({"error": "Invalid seconds (1-3600)"}), 400

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # 1 секунда = 1 Ɉ
    new_balance = user['balance'] + seconds
    new_presence = user['presence_seconds'] + seconds

    db.execute(
        'UPDATE users SET balance = ?, presence_seconds = ?, last_seen = CURRENT_TIMESTAMP WHERE device_id = ?',
        (new_balance, new_presence, device_id)
    )
    db.commit()

    return jsonify({
        "added": seconds,
        "balance": new_balance,
        "total_presence": new_presence
    })


@app.route('/api/transfer', methods=['POST'])
def transfer():
    """Перевод Ɉ между номерами телефонов"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    data = request.json or {}
    to_phone = normalize_phone(data.get('to'))
    amount = data.get('amount', 0)

    if not to_phone:
        return jsonify({"error": "Неверный номер телефона"}), 400

    if amount <= 0:
        return jsonify({"error": "Неверная сумма"}), 400

    db = get_db()

    # Получаем отправителя
    sender = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()
    if not sender:
        return jsonify({"error": "Отправитель не найден"}), 404

    if not sender['verified']:
        return jsonify({"error": "Подтвердите номер телефона для переводов"}), 400

    if sender['balance'] < amount:
        return jsonify({"error": "Недостаточно средств"}), 400

    # Получаем получателя
    receiver = db.execute('SELECT * FROM users WHERE phone = ? AND verified = 1', (to_phone,)).fetchone()
    if not receiver:
        return jsonify({"error": "Получатель не найден или не верифицирован"}), 404

    # Выполняем перевод
    db.execute('UPDATE users SET balance = balance - ? WHERE device_id = ?', (amount, device_id))
    db.execute('UPDATE users SET balance = balance + ? WHERE phone = ?', (amount, to_phone))
    db.execute(
        'INSERT INTO transactions (from_phone, to_phone, amount) VALUES (?, ?, ?)',
        (sender['phone'], to_phone, amount)
    )
    db.commit()

    return jsonify({
        "success": True,
        "from": sender['phone'],
        "to": to_phone,
        "amount": amount,
        "new_balance": sender['balance'] - amount
    })


@app.route('/api/sync', methods=['POST'])
def sync_data():
    """Синхронизация данных (чаты, контакты, папки)"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    data = request.json or {}

    db = get_db()
    user = db.execute('SELECT id FROM users WHERE device_id = ?', (device_id,)).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    user_id = user['id']

    # Сохраняем данные если переданы
    if 'chat' in data:
        existing = db.execute('SELECT id FROM chats WHERE user_id = ?', (user_id,)).fetchone()
        chat_json = json.dumps(data['chat'])
        if existing:
            db.execute('UPDATE chats SET messages = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                      (chat_json, user_id))
        else:
            db.execute('INSERT INTO chats (user_id, messages) VALUES (?, ?)', (user_id, chat_json))

    if 'contacts' in data:
        # Удаляем старые и вставляем новые
        db.execute('DELETE FROM contacts WHERE user_id = ?', (user_id,))
        for c in data['contacts']:
            db.execute('INSERT INTO contacts (user_id, name, address) VALUES (?, ?, ?)',
                      (user_id, c.get('name', ''), c.get('address')))

    if 'folders' in data:
        db.execute('DELETE FROM folders WHERE user_id = ?', (user_id,))
        for f in data['folders']:
            db.execute('INSERT INTO folders (user_id, name, privacy, items) VALUES (?, ?, ?, ?)',
                      (user_id, f.get('name', ''), f.get('privacy', 'intimate'), json.dumps(f.get('items', []))))

    db.commit()

    # Возвращаем все данные
    chat = db.execute('SELECT messages FROM chats WHERE user_id = ?', (user_id,)).fetchone()
    contacts = db.execute('SELECT name, address FROM contacts WHERE user_id = ?', (user_id,)).fetchall()
    folders = db.execute('SELECT name, privacy, items FROM folders WHERE user_id = ?', (user_id,)).fetchall()

    return jsonify({
        "chat": json.loads(chat['messages']) if chat else [],
        "contacts": [{"name": c['name'], "address": c['address']} for c in contacts],
        "folders": [{"name": f['name'], "privacy": f['privacy'], "items": json.loads(f['items'])} for f in folders]
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """AI чат"""
    data = request.json
    message = data.get('message', '')
    model = data.get('model', 'claude')
    history = data.get('history', [])

    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400

    if model == 'openai':
        response = ask_openai(message, history)
        return jsonify({"model": "OpenAI", "response": response})

    elif model == 'claude':
        response = ask_claude(message, history)
        return jsonify({"model": "Claude", "response": response})

    elif model == 'council':
        responses = []
        openai_resp = ask_openai(message, history)
        responses.append({"model": "OpenAI", "response": openai_resp})

        council_prompt = f"{message}\n\n[OpenAI сказал]: {openai_resp}\n\nТеперь твоя очередь. Можешь дополнить, уточнить или не согласиться."
        claude_resp = ask_claude(council_prompt, history)
        responses.append({"model": "Claude", "response": claude_resp})

        return jsonify({"council": responses})

    else:
        return jsonify({"error": f"Неизвестная модель: {model}"}), 400


# ============ VPN (WireGuard) ============

WG_SERVER_PUBKEY = "/9zhnW4O4uOstQpR5mgGmCLiy+B+LL4uQmNzgupNzwc="
WG_SERVER_IP = "72.56.102.240"
WG_SERVER_PORT = 51820
WG_SUBNET = "10.66.66"
WG_CONFIG_PATH = "/etc/wireguard/wg0.conf"

def get_next_vpn_ip():
    """Получить следующий свободный IP для VPN клиента"""
    db = get_db()
    try:
        db.execute('ALTER TABLE users ADD COLUMN vpn_ip TEXT')
        db.commit()
    except:
        pass

    # Находим максимальный использованный IP
    result = db.execute('SELECT vpn_ip FROM users WHERE vpn_ip IS NOT NULL ORDER BY vpn_ip DESC LIMIT 1').fetchone()
    if result and result['vpn_ip']:
        last_octet = int(result['vpn_ip'].split('.')[-1])
        return f"{WG_SUBNET}.{last_octet + 1}"
    return f"{WG_SUBNET}.2"  # .1 это сервер


@app.route('/api/vpn/generate', methods=['POST'])
def generate_vpn():
    """Генерация VPN конфигурации для пользователя"""
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        return jsonify({"error": "X-Device-ID header required"}), 401

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE device_id = ?', (device_id,)).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Проверяем, есть ли уже VPN
    try:
        if user['vpn_ip'] and user.get('vpn_private_key'):
            # Уже есть конфиг - возвращаем его
            config = f"""[Interface]
PrivateKey = {user['vpn_private_key']}
Address = {user['vpn_ip']}/24
DNS = 1.1.1.1

[Peer]
PublicKey = {WG_SERVER_PUBKEY}
Endpoint = {WG_SERVER_IP}:{WG_SERVER_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
            return jsonify({
                "success": True,
                "config": config,
                "ip": user['vpn_ip'],
                "existing": True
            })
    except:
        pass

    # Генерируем новые ключи
    import subprocess
    try:
        private_key = subprocess.check_output(['wg', 'genkey']).decode().strip()
        public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key.encode()).decode().strip()
    except:
        return jsonify({"error": "VPN key generation failed"}), 500

    # Получаем IP
    vpn_ip = get_next_vpn_ip()

    # Добавляем колонку если нет
    try:
        db.execute('ALTER TABLE users ADD COLUMN vpn_private_key TEXT')
        db.execute('ALTER TABLE users ADD COLUMN vpn_public_key TEXT')
        db.commit()
    except:
        pass

    # Сохраняем ключи
    db.execute(
        'UPDATE users SET vpn_ip = ?, vpn_private_key = ?, vpn_public_key = ? WHERE device_id = ?',
        (vpn_ip, private_key, public_key, device_id)
    )
    db.commit()

    # Добавляем peer на сервер
    try:
        subprocess.run([
            'wg', 'set', 'wg0',
            'peer', public_key,
            'allowed-ips', f'{vpn_ip}/32'
        ], check=True)

        # Сохраняем в конфиг файл для persistence
        with open(WG_CONFIG_PATH, 'a') as f:
            f.write(f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {vpn_ip}/32\n")
    except Exception as e:
        return jsonify({"error": f"Server config failed: {str(e)}"}), 500

    # Генерируем клиентский конфиг
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {vpn_ip}/24
DNS = 1.1.1.1

[Peer]
PublicKey = {WG_SERVER_PUBKEY}
Endpoint = {WG_SERVER_IP}:{WG_SERVER_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

    return jsonify({
        "success": True,
        "config": config,
        "ip": vpn_ip,
        "existing": False
    })


# ============ INIT ============

if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000)
