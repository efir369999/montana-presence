"""
MontanaSign — Сервис подписи iOS приложений
montana.network/install

Модель как LazyShop:
1. Пользователь регистрирует UDID
2. Мы выдаём сертификат (или подписываем своим)
3. .ipa скачивается и устанавливается
4. Apple не контролирует
"""

from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import os
import subprocess
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
CORS(app)

# Конфигурация
UPLOAD_FOLDER = '/var/montana/ipa'
SIGNED_FOLDER = '/var/montana/signed'
CERTS_FOLDER = '/var/montana/certs'
DATABASE = '/var/montana/montanasign.db'

# IPA файлы Montana (беззнаковые)
MONTANA_APPS = {
    'wallet': {
        'name': 'Montana Wallet',
        'bundle_id': 'network.montana.wallet',
        'version': '1.0.0',
        'ipa': 'MontanaWallet.ipa',
        'icon': 'wallet_icon.png',
        'description': 'Кошелёк Ɉ — баланс и переводы'
    },
    'junona': {
        'name': 'Junona AI',
        'bundle_id': 'network.montana.junona',
        'version': '1.0.0',
        'ipa': 'JunonaAI.ipa',
        'icon': 'junona_icon.png',
        'description': 'Чат с ИИ Montana Protocol'
    },
    'contracts': {
        'name': 'Montana Contracts',
        'bundle_id': 'network.montana.contracts',
        'version': '1.0.0',
        'ipa': 'MontanaContracts.ipa',
        'icon': 'contracts_icon.png',
        'description': 'Контракты Bitcoin Pizza Style'
    }
}


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            udid TEXT PRIMARY KEY,
            user_id TEXT,
            device_name TEXT,
            model TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            certificate_id TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS certificates (
            cert_id TEXT PRIMARY KEY,
            udid TEXT,
            cert_data BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            revoked BOOLEAN DEFAULT FALSE
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS installations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            udid TEXT,
            app_id TEXT,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            version TEXT
        )
    ''')

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════════════

LANDING_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Montana Install — Установка без App Store</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', sans-serif;
            background: #0F0F1A;
            color: white;
            min-height: 100vh;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header {
            text-align: center;
            padding: 40px 0;
        }
        .logo { font-size: 64px; margin-bottom: 16px; }
        h1 { font-size: 28px; margin-bottom: 8px; }
        .subtitle { color: #888; font-size: 16px; }

        .apps { margin-top: 32px; }
        .app-card {
            background: #1A1A2E;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .app-icon {
            width: 60px;
            height: 60px;
            background: #4A90D9;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
        }
        .app-info { flex: 1; }
        .app-name { font-weight: 600; font-size: 18px; }
        .app-desc { color: #888; font-size: 14px; margin-top: 4px; }
        .install-btn {
            background: #4A90D9;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            font-size: 16px;
        }
        .install-btn:disabled {
            background: #333;
            cursor: not-allowed;
        }

        .step {
            background: #1A1A2E;
            border-radius: 16px;
            padding: 24px;
            margin-top: 32px;
        }
        .step-number {
            background: #4A90D9;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 12px;
        }
        .step h3 { display: inline; font-size: 18px; }
        .step p { margin-top: 12px; color: #888; line-height: 1.6; }

        .udid-input {
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #333;
            background: #0F0F1A;
            color: white;
            font-size: 16px;
            margin-top: 16px;
            font-family: monospace;
        }
        .udid-input:focus { border-color: #4A90D9; outline: none; }

        .register-btn {
            width: 100%;
            background: #4A90D9;
            color: white;
            border: none;
            padding: 16px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            font-size: 16px;
            margin-top: 16px;
        }

        .footer {
            text-align: center;
            padding: 40px 0;
            color: #666;
            font-size: 14px;
        }

        .status { padding: 12px; border-radius: 8px; margin-top: 16px; }
        .status.success { background: rgba(16, 185, 129, 0.2); color: #10B981; }
        .status.error { background: rgba(239, 68, 68, 0.2); color: #EF4444; }

        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">Ɉ</div>
            <h1>Montana Install</h1>
            <p class="subtitle">Установка без App Store. Apple не контролирует.</p>
        </div>

        <div class="step">
            <span class="step-number">1</span>
            <h3>Зарегистрируй устройство</h3>
            <p>Открой Настройки → Основные → Об этом устройстве → UDID<br>
               Или используй <a href="udid://" style="color: #4A90D9">get.udid.io</a></p>
            <input type="text" class="udid-input" id="udid" placeholder="00000000-0000000000000000">
            <button class="register-btn" onclick="registerDevice()">Зарегистрировать</button>
            <div id="register-status" class="status hidden"></div>
        </div>

        <div class="apps" id="apps-section">
            <div class="app-card">
                <div class="app-icon">💰</div>
                <div class="app-info">
                    <div class="app-name">Montana Wallet</div>
                    <div class="app-desc">Кошелёк Ɉ — баланс и переводы</div>
                </div>
                <button class="install-btn" onclick="installApp('wallet')" id="btn-wallet" disabled>Установить</button>
            </div>

            <div class="app-card">
                <div class="app-icon">🤖</div>
                <div class="app-info">
                    <div class="app-name">Junona AI</div>
                    <div class="app-desc">Чат с ИИ Montana Protocol</div>
                </div>
                <button class="install-btn" onclick="installApp('junona')" id="btn-junona" disabled>Установить</button>
            </div>

            <div class="app-card">
                <div class="app-icon">📄</div>
                <div class="app-info">
                    <div class="app-name">Montana Contracts</div>
                    <div class="app-desc">Контракты Bitcoin Pizza Style</div>
                </div>
                <button class="install-btn" onclick="installApp('contracts')" id="btn-contracts" disabled>Установить</button>
            </div>
        </div>

        <div class="step">
            <span class="step-number">2</span>
            <h3>После установки</h3>
            <p>Настройки → Основные → VPN и управление устройством → Доверять сертификату Montana</p>
        </div>

        <div class="footer">
            <p>Время — единственная реальная валюта</p>
            <p style="margin-top: 8px;">Apple не может удалить время. Ɉ</p>
        </div>
    </div>

    <script>
        let registeredUDID = localStorage.getItem('montana_udid');

        if (registeredUDID) {
            document.getElementById('udid').value = registeredUDID;
            enableInstallButtons();
        }

        async function registerDevice() {
            const udid = document.getElementById('udid').value.trim();
            const status = document.getElementById('register-status');

            if (!udid || udid.length < 20) {
                status.className = 'status error';
                status.textContent = 'Неверный формат UDID';
                status.classList.remove('hidden');
                return;
            }

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ udid })
                });
                const data = await res.json();

                if (data.success) {
                    localStorage.setItem('montana_udid', udid);
                    registeredUDID = udid;
                    status.className = 'status success';
                    status.textContent = 'Устройство зарегистрировано! Можешь устанавливать.';
                    enableInstallButtons();
                } else {
                    status.className = 'status error';
                    status.textContent = data.error || 'Ошибка регистрации';
                }
            } catch (e) {
                status.className = 'status error';
                status.textContent = 'Ошибка соединения';
            }
            status.classList.remove('hidden');
        }

        function enableInstallButtons() {
            document.querySelectorAll('.install-btn').forEach(btn => {
                btn.disabled = false;
            });
        }

        async function installApp(appId) {
            if (!registeredUDID) {
                alert('Сначала зарегистрируй устройство');
                return;
            }

            // Открываем manifest для установки
            window.location.href = `itms-services://?action=download-manifest&url=${encodeURIComponent(
                window.location.origin + '/api/manifest/' + appId + '?udid=' + registeredUDID
            )}`;
        }
    </script>
</body>
</html>
'''


@app.route('/')
def landing():
    return render_template_string(LANDING_HTML)


# ═══════════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/register', methods=['POST'])
def register_device():
    """Регистрация устройства по UDID"""
    data = request.json
    udid = data.get('udid', '').strip()

    if not udid or len(udid) < 20:
        return jsonify({'success': False, 'error': 'Invalid UDID'})

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Проверяем существует ли
    c.execute('SELECT * FROM devices WHERE udid = ?', (udid,))
    existing = c.fetchone()

    if existing:
        conn.close()
        return jsonify({'success': True, 'message': 'Already registered'})

    # Регистрируем
    expires_at = datetime.now() + timedelta(days=365)
    cert_id = secrets.token_hex(16)

    c.execute('''
        INSERT INTO devices (udid, expires_at, certificate_id)
        VALUES (?, ?, ?)
    ''', (udid, expires_at, cert_id))

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': 'Device registered',
        'expires': expires_at.isoformat()
    })


@app.route('/api/manifest/<app_id>')
def get_manifest(app_id):
    """Генерация manifest.plist для установки"""
    udid = request.args.get('udid')

    if app_id not in MONTANA_APPS:
        return 'App not found', 404

    app = MONTANA_APPS[app_id]

    # Генерируем manifest
    manifest = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{request.host_url}api/download/{app_id}?udid={udid}</string>
                </dict>
                <dict>
                    <key>kind</key>
                    <string>display-image</string>
                    <key>url</key>
                    <string>{request.host_url}static/icons/{app['icon']}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{app['bundle_id']}</string>
                <key>bundle-version</key>
                <string>{app['version']}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{app['name']}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>'''

    return manifest, 200, {'Content-Type': 'application/xml'}


@app.route('/api/download/<app_id>')
def download_ipa(app_id):
    """Скачивание подписанного IPA"""
    udid = request.args.get('udid')

    if app_id not in MONTANA_APPS:
        return 'App not found', 404

    app = MONTANA_APPS[app_id]

    # Путь к подписанному IPA для этого UDID
    signed_path = os.path.join(SIGNED_FOLDER, udid, app['ipa'])

    # Если ещё не подписан — подписываем
    if not os.path.exists(signed_path):
        sign_ipa_for_udid(app_id, udid)

    if os.path.exists(signed_path):
        # Логируем установку
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO installations (udid, app_id, version)
            VALUES (?, ?, ?)
        ''', (udid, app_id, app['version']))
        conn.commit()
        conn.close()

        return send_file(signed_path, as_attachment=True, download_name=app['ipa'])

    return 'Signing failed', 500


def sign_ipa_for_udid(app_id: str, udid: str):
    """Подписать IPA для конкретного UDID"""
    app = MONTANA_APPS[app_id]

    unsigned_path = os.path.join(UPLOAD_FOLDER, app['ipa'])
    output_dir = os.path.join(SIGNED_FOLDER, udid)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, app['ipa'])

    # Используем zsign или ldid для подписи
    # zsign -k cert.p12 -m profile.mobileprovision -o output.ipa input.ipa

    cert_path = os.path.join(CERTS_FOLDER, 'montana.p12')
    profile_path = os.path.join(CERTS_FOLDER, f'{udid}.mobileprovision')

    try:
        subprocess.run([
            'zsign',
            '-k', cert_path,
            '-m', profile_path,
            '-o', output_path,
            unsigned_path
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Signing failed: {e}")
        return False


@app.route('/api/apps')
def list_apps():
    """Список приложений"""
    return jsonify(MONTANA_APPS)


@app.route('/api/stats')
def stats():
    """Статистика"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM devices')
    devices = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM installations')
    installs = c.fetchone()[0]

    conn.close()

    return jsonify({
        'registered_devices': devices,
        'total_installations': installs
    })


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(SIGNED_FOLDER, exist_ok=True)
    os.makedirs(CERTS_FOLDER, exist_ok=True)

    init_db()

    print("🏔 MontanaSign — iOS Distribution Service")
    print("   montana.network/install")
    print("")
    print("   Модель: LazyShop-style")
    print("   1. Пользователь регистрирует UDID")
    print("   2. Мы подписываем IPA")
    print("   3. Apple не контролирует")
    print("")

    app.run(host='0.0.0.0', port=8080, debug=True)
