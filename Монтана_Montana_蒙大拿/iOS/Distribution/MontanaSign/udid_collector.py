"""
UDID Collector через .mobileconfig профиль

Как работает:
1. Пользователь открывает montana.network/install
2. Нажимает "Зарегистрировать устройство"
3. iOS предлагает установить профиль
4. После установки профиля iOS отправляет данные на наш callback URL
5. Мы получаем UDID, модель, версию iOS
6. Редиректим пользователя на страницу с приложениями
"""

from flask import Flask, request, Response, redirect, render_template_string
import plistlib
import uuid
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

DATABASE = '/var/montana/montanasign.db'
CALLBACK_URL = 'https://install.montana.network/enroll/callback'


def generate_enrollment_profile(session_id: str) -> bytes:
    """
    Генерация .mobileconfig профиля для сбора UDID

    Профиль содержит:
    - PayloadType: Profile Service
    - URL: куда отправить данные устройства
    """

    profile = {
        'PayloadContent': {
            'URL': f'{CALLBACK_URL}?session={session_id}',
            'DeviceAttributes': [
                'UDID',
                'IMEI',
                'ICCID',
                'VERSION',
                'PRODUCT',
                'DEVICE_NAME',
                'SERIAL',
                'MAC_ADDRESS_EN0'
            ],
        },
        'PayloadOrganization': 'Montana Protocol',
        'PayloadDisplayName': 'Montana Device Registration',
        'PayloadDescription': 'Регистрация устройства для установки Montana apps',
        'PayloadVersion': 1,
        'PayloadUUID': str(uuid.uuid4()).upper(),
        'PayloadIdentifier': f'network.montana.enroll.{session_id}',
        'PayloadType': 'Profile Service',
    }

    return plistlib.dumps(profile)


# ═══════════════════════════════════════════════════════════════
# ENROLLMENT FLOW
# ═══════════════════════════════════════════════════════════════

ENROLL_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Montana — Регистрация устройства</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0F0F1A;
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: #1A1A2E;
            border-radius: 24px;
            padding: 40px;
            max-width: 400px;
            text-align: center;
        }
        .logo { font-size: 64px; margin-bottom: 24px; }
        h1 { font-size: 24px; margin-bottom: 12px; }
        p { color: #888; margin-bottom: 24px; line-height: 1.6; }
        .btn {
            display: block;
            width: 100%;
            background: #4A90D9;
            color: white;
            border: none;
            padding: 16px;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
        }
        .steps {
            text-align: left;
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid #333;
        }
        .step {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }
        .step-num {
            background: #4A90D9;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            flex-shrink: 0;
        }
        .step-text { color: #888; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">Ɉ</div>
        <h1>Регистрация устройства</h1>
        <p>Для установки приложений Montana нужно зарегистрировать твой iPhone</p>

        <a href="/enroll/profile" class="btn">Зарегистрировать</a>

        <div class="steps">
            <div class="step">
                <span class="step-num">1</span>
                <span class="step-text">Нажми кнопку выше</span>
            </div>
            <div class="step">
                <span class="step-num">2</span>
                <span class="step-text">Разреши установку профиля в Настройках</span>
            </div>
            <div class="step">
                <span class="step-num">3</span>
                <span class="step-text">Вернись сюда и выбери приложения</span>
            </div>
        </div>
    </div>
</body>
</html>
'''


SUCCESS_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="2;url=/apps?udid={{ udid }}">
    <title>Montana — Готово!</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0F0F1A;
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card {
            background: #1A1A2E;
            border-radius: 24px;
            padding: 40px;
            text-align: center;
        }
        .check { font-size: 64px; margin-bottom: 24px; }
        h1 { color: #10B981; margin-bottom: 12px; }
        p { color: #888; }
    </style>
</head>
<body>
    <div class="card">
        <div class="check">✓</div>
        <h1>Устройство зарегистрировано!</h1>
        <p>Перенаправляю к приложениям...</p>
    </div>
</body>
</html>
'''


@app.route('/enroll')
def enroll_page():
    """Страница регистрации"""
    return render_template_string(ENROLL_PAGE)


@app.route('/enroll/profile')
def enroll_profile():
    """
    Отдаёт .mobileconfig профиль
    iOS откроет диалог установки профиля
    """
    # Создаём уникальную сессию
    session_id = str(uuid.uuid4())

    # Сохраняем сессию
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS enrollment_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed BOOLEAN DEFAULT FALSE,
            udid TEXT
        )
    ''')
    c.execute('INSERT INTO enrollment_sessions (session_id) VALUES (?)', (session_id,))
    conn.commit()
    conn.close()

    # Генерируем профиль
    profile_data = generate_enrollment_profile(session_id)

    return Response(
        profile_data,
        mimetype='application/x-apple-aspen-config',
        headers={
            'Content-Disposition': f'attachment; filename="montana-enroll.mobileconfig"'
        }
    )


@app.route('/enroll/callback', methods=['POST'])
def enroll_callback():
    """
    Callback от iOS после установки профиля
    iOS отправляет signed plist с данными устройства
    """
    session_id = request.args.get('session')

    if not session_id:
        return 'Missing session', 400

    # Парсим данные устройства из plist
    try:
        device_data = plistlib.loads(request.data)
    except Exception as e:
        print(f"Failed to parse device data: {e}")
        return 'Invalid data', 400

    # Извлекаем UDID и другие данные
    udid = device_data.get('UDID', '')
    product = device_data.get('PRODUCT', '')
    version = device_data.get('VERSION', '')
    device_name = device_data.get('DEVICE_NAME', '')

    if not udid:
        return 'Missing UDID', 400

    # Сохраняем устройство
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Обновляем сессию
    c.execute('''
        UPDATE enrollment_sessions
        SET completed = TRUE, udid = ?
        WHERE session_id = ?
    ''', (udid, session_id))

    # Добавляем устройство
    c.execute('''
        INSERT OR REPLACE INTO devices (udid, device_name, model, registered_at)
        VALUES (?, ?, ?, ?)
    ''', (udid, device_name, product, datetime.now()))

    conn.commit()
    conn.close()

    print(f"✅ Device enrolled: {udid} ({product}, iOS {version})")

    # Отправляем конфигурацию для завершения
    # Это удалит временный профиль и перенаправит пользователя
    response_profile = {
        'PayloadOrganization': 'Montana Protocol',
        'PayloadDisplayName': 'Registration Complete',
        'PayloadDescription': 'Устройство зарегистрировано',
        'PayloadVersion': 1,
        'PayloadUUID': str(uuid.uuid4()).upper(),
        'PayloadIdentifier': 'network.montana.enrolled',
        'PayloadType': 'Configuration',
        'PayloadContent': [],
        # Редирект после установки
        'PayloadRemovalDisallowed': False,
    }

    return Response(
        plistlib.dumps(response_profile),
        mimetype='application/x-apple-aspen-config'
    )


@app.route('/enroll/check/<session_id>')
def check_enrollment(session_id):
    """Проверка статуса регистрации (для polling)"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT completed, udid FROM enrollment_sessions WHERE session_id = ?', (session_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return {'enrolled': False, 'error': 'Session not found'}

    completed, udid = result
    return {'enrolled': bool(completed), 'udid': udid}


@app.route('/enroll/success')
def enroll_success():
    """Страница успешной регистрации"""
    udid = request.args.get('udid', '')
    return render_template_string(SUCCESS_PAGE, udid=udid)


# ═══════════════════════════════════════════════════════════════
# ALTERNATIVE: OTA Profile for UDID
# ═══════════════════════════════════════════════════════════════

def generate_ota_profile() -> bytes:
    """
    Альтернативный способ через OTA enrollment
    Работает как MDM lite
    """
    profile = {
        'PayloadContent': [
            {
                'PayloadType': 'com.apple.webClip.managed',
                'PayloadVersion': 1,
                'PayloadIdentifier': 'network.montana.webclip',
                'PayloadUUID': str(uuid.uuid4()).upper(),
                'PayloadDisplayName': 'Montana Apps',
                'URL': 'https://install.montana.network/apps',
                'Label': 'Montana',
                'Icon': None,  # Можно добавить base64 иконку
                'IsRemovable': True,
                'FullScreen': False,
            }
        ],
        'PayloadOrganization': 'Montana Protocol',
        'PayloadDisplayName': 'Montana Protocol',
        'PayloadDescription': 'Доступ к приложениям Montana без App Store',
        'PayloadVersion': 1,
        'PayloadUUID': str(uuid.uuid4()).upper(),
        'PayloadIdentifier': 'network.montana.profile',
        'PayloadType': 'Configuration',
        'PayloadRemovalDisallowed': False,
    }

    return plistlib.dumps(profile)


if __name__ == '__main__':
    os.makedirs('/var/montana', exist_ok=True)
    app.run(host='0.0.0.0', port=8081, debug=True)
