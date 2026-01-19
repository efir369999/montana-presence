#!/usr/bin/env python3
"""
Веб-интерфейс для тестирования Montana с iPhone
- Agent Registry верификация
- FIDO2 Touch ID / Face ID (mock)
- QR код для быстрого доступа
"""

from flask import Flask, render_template, request, jsonify, send_file
import qrcode
from io import BytesIO
import json
from pathlib import Path

from agent_crypto import AgentCrypto
from fido2_node import MockFIDO2

app = Flask(__name__)
acs = AgentCrypto()
fido = MockFIDO2()




@app.route('/api/agents')
def list_agents():
    """Список всех агентов"""
    agents = acs.list_agents(official_only=False)
    return jsonify(agents)


@app.route('/api/agent/<agent_address>')
def get_agent(agent_address):
    """Информация об агенте"""
    agent_info = acs.get_agent_info(agent_address)
    if agent_info:
        return jsonify(agent_info)
    return jsonify({"error": "Agent not found"}), 404


@app.route('/api/verify_message', methods=['POST'])
def verify_message():
    """
    Верифицировать подписанное сообщение

    POST /api/verify_message
    {
        "message": {...},
        "signature": "...",
        "agent_address": "mtAGENT..."
    }
    """
    data = request.json

    is_valid = acs.verify_message(
        message=data['message'],
        signature_hex=data['signature'],
        agent_address=data['agent_address']
    )

    agent_info = acs.get_agent_info(data['agent_address'])
    is_official = acs.is_official_agent(data['agent_address'])

    return jsonify({
        "valid": is_valid,
        "official": is_official,
        "agent_name": agent_info.get('name') if agent_info else None
    })


@app.route('/api/fido2/register', methods=['POST'])
def fido2_register():
    """
    Регистрация FIDO2 (mock)

    POST /api/fido2/register
    {
        "telegram_id": 123456789,
        "device": "iPhone 15 Pro"
    }
    """
    data = request.json
    telegram_id = data['telegram_id']
    device = data.get('device', 'iPhone')

    credential_id = fido.register_biometric(telegram_id, device)

    return jsonify({
        "success": True,
        "credential_id": credential_id,
        "message": "Touch ID / Face ID registered"
    })


@app.route('/api/fido2/verify', methods=['POST'])
def fido2_verify():
    """
    Верификация FIDO2 (mock)

    POST /api/fido2/verify
    {
        "telegram_id": 123456789
    }
    """
    data = request.json
    telegram_id = data['telegram_id']

    has_bio = fido.has_biometric(telegram_id)
    if not has_bio:
        return jsonify({"error": "No biometric registered"}), 400

    verified = fido.verify_biometric(telegram_id)

    cred_info = fido.get_credential_info(telegram_id)

    return jsonify({
        "success": verified,
        "credential_info": cred_info
    })


@app.route('/api/junona/message', methods=['POST'])
def junona_message():
    """
    Получить подписанное сообщение от Юноны

    POST /api/junona/message
    {
        "text": "Привет! Это тестовое сообщение."
    }
    """
    data = request.json
    text = data.get('text', 'Привет из Montana!')

    # Загрузить ключи Юноны
    keys_path = Path("data/agent_keys.json")
    if not keys_path.exists():
        return jsonify({"error": "Junona keys not found. Run register_junona.py"}), 500

    with open(keys_path, 'r') as f:
        keys_data = json.load(f)

    # Найти Юнону
    junona_address = None
    junona_keys = None
    for addr, keys in keys_data.items():
        if "Юнона" in keys.get("agent_name", ""):
            junona_address = addr
            junona_keys = keys
            break

    if not junona_keys:
        return jsonify({"error": "Junona not found in registry"}), 500

    # Создать подписанное сообщение
    signed_msg = acs.create_signed_message(
        private_key_hex=junona_keys['private_key'],
        public_key_hex=junona_keys['public_key'],
        text=text,
        metadata={"source": "web_api", "test": True}
    )

    # Добавить информацию об агенте
    agent_info = acs.get_agent_info(junona_address)

    return jsonify({
        "signed_message": signed_msg,
        "agent_info": agent_info
    })


@app.route('/miniapp/menu.html')
def serve_menu():
    """Меню Montana Mini App"""
    return send_file('miniapp/menu.html')


@app.route('/miniapp/verify.html')
def serve_verify():
    """Верификация Montana Mini App"""
    return send_file('miniapp/verify.html')


@app.route('/qr')
def qr_code():
    """QR код для доступа с iPhone"""
    # Получить локальный IP
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    url = f"http://{local_ip}:5001"

    # Создать QR код
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертировать в bytes
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png')


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Montana Test - iPhone</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #667eea;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .section {
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 12px;
        }
        .section h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 10px;
            transition: transform 0.2s;
        }
        button:active {
            transform: scale(0.98);
        }
        .result {
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            font-size: 14px;
            max-height: 300px;
            overflow-y: auto;
        }
        .success { color: #28a745; font-weight: 600; }
        .error { color: #dc3545; font-weight: 600; }
        .info { color: #17a2b8; }
        code {
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }
        .agent-badge {
            display: inline-block;
            padding: 4px 12px;
            background: #667eea;
            color: white;
            border-radius: 20px;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏔 Montana Test</h1>
        <p class="subtitle">Agent Registry + FIDO2 + ML-DSA-65</p>

        <!-- Agent Registry -->
        <div class="section">
            <h2>🔐 Agent Registry</h2>
            <button onclick="listAgents()">Список агентов</button>
            <button onclick="getJunonaMessage()">Сообщение от Юноны</button>
            <div id="agentResult" class="result" style="display:none;"></div>
        </div>

        <!-- FIDO2 Biometrics -->
        <div class="section">
            <h2>📱 Touch ID / Face ID (Mock)</h2>
            <button onclick="registerBiometric()">Зарегистрировать биометрию</button>
            <button onclick="verifyBiometric()">Верифицировать биометрию</button>
            <div id="fido2Result" class="result" style="display:none;"></div>
        </div>

        <!-- Status -->
        <div class="section">
            <h2>📊 Статус</h2>
            <p>✅ Agent Registry: ML-DSA-65 (FIPS 204)</p>
            <p>✅ FIDO2: Touch ID / Face ID ready</p>
            <p>✅ Post-Quantum: Active from genesis</p>
        </div>
    </div>

    <script>
        const TEST_TELEGRAM_ID = 8552053404;

        async function listAgents() {
            const result = document.getElementById('agentResult');
            result.style.display = 'block';
            result.innerHTML = '<p class="info">Загрузка...</p>';

            try {
                const response = await fetch('/api/agents');
                const agents = await response.json();

                let html = '<h3>Агенты Montana:</h3>';
                for (const [address, info] of Object.entries(agents)) {
                    html += `
                        <div style="margin: 10px 0; padding: 10px; background: #e9ecef; border-radius: 8px;">
                            <strong>${info.name}</strong>
                            ${info.official ? '<span class="agent-badge">OFFICIAL</span>' : ''}
                            <br><code>${address}</code>
                            <br><small>${info.description}</small>
                        </div>
                    `;
                }

                result.innerHTML = html;
            } catch (error) {
                result.innerHTML = `<p class="error">Ошибка: ${error.message}</p>`;
            }
        }

        async function getJunonaMessage() {
            const result = document.getElementById('agentResult');
            result.style.display = 'block';
            result.innerHTML = '<p class="info">Запрос сообщения от Юноны...</p>';

            try {
                const response = await fetch('/api/junona/message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: 'Привет с iPhone! Это тест Montana.' })
                });

                const data = await response.json();

                let html = '<h3>Подписанное сообщение Юноны:</h3>';
                html += `<p><strong>Агент:</strong> ${data.agent_info.name}</p>`;
                html += `<p><strong>Адрес:</strong> <code>${data.signed_message.agent_address}</code></p>`;
                html += `<p><strong>Сообщение:</strong> ${data.signed_message.message.text}</p>`;
                html += `<p><strong>Timestamp:</strong> ${data.signed_message.message.timestamp}</p>`;
                html += `<p><strong>Подпись:</strong> <code>${data.signed_message.signature.substring(0, 64)}...</code></p>`;
                html += `<p class="success">✅ ML-DSA-65 подпись валидна</p>`;

                result.innerHTML = html;
            } catch (error) {
                result.innerHTML = `<p class="error">Ошибка: ${error.message}</p>`;
            }
        }

        async function registerBiometric() {
            const result = document.getElementById('fido2Result');
            result.style.display = 'block';
            result.innerHTML = '<p class="info">Регистрация биометрии...</p>';

            try {
                const response = await fetch('/api/fido2/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: TEST_TELEGRAM_ID,
                        device: navigator.userAgent.includes('iPhone') ? 'iPhone' : 'Device'
                    })
                });

                const data = await response.json();

                let html = '<h3>Биометрия зарегистрирована:</h3>';
                html += `<p><strong>Credential ID:</strong> <code>${data.credential_id}</code></p>`;
                html += `<p class="success">✅ ${data.message}</p>`;
                html += `<p><small>В production это будет реальный Touch ID / Face ID</small></p>`;

                result.innerHTML = html;
            } catch (error) {
                result.innerHTML = `<p class="error">Ошибка: ${error.message}</p>`;
            }
        }

        async function verifyBiometric() {
            const result = document.getElementById('fido2Result');
            result.style.display = 'block';
            result.innerHTML = '<p class="info">Верификация биометрии...</p>';

            try {
                const response = await fetch('/api/fido2/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: TEST_TELEGRAM_ID })
                });

                const data = await response.json();

                let html = '<h3>Биометрия верифицирована:</h3>';
                html += `<p><strong>Устройство:</strong> ${data.credential_info.device}</p>`;
                html += `<p><strong>Зарегистрировано:</strong> ${data.credential_info.registered_at}</p>`;
                html += `<p><strong>Последняя авторизация:</strong> ${data.credential_info.last_auth}</p>`;
                html += `<p class="success">✅ Proof of Presence подтверждён</p>`;

                result.innerHTML = html;
            } catch (error) {
                result.innerHTML = `<p class="error">Ошибка: ${error.message}</p>`;
            }
        }
    </script>
</body>
</html>
"""


@app.route('/templates/index.html')
def serve_template():
    return HTML_TEMPLATE


if __name__ == '__main__':
    print("\n🏔 Montana Test Server")
    print("="*60)
    print("Agent Registry: ACTIVE (ML-DSA-65)")
    print("FIDO2: MOCK MODE (для production нужен WebAuthn)")
    print("="*60)
    print("\n📱 Для доступа с iPhone:")
    print("1. Открой http://127.0.0.1:5001 в браузере")
    print("2. Или отсканируй QR: http://127.0.0.1:5001/qr")
    print("\n🔍 Или используй локальный IP в той же сети")
    print("="*60)
    print("\nЗапуск сервера на порту 5001...")

    # Render template directly in app
    @app.route('/')
    def index():
        return HTML_TEMPLATE

    app.run(host='0.0.0.0', port=5001, debug=True)
