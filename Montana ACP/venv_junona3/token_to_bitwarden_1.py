
#token_to_bitwarden_1

import subprocess
import base64
import json
import os
import getpass
from datetime import datetime

# Шаг 1: Запрос токена бота Telegram
print("=== Шаг 1: Запрос токена бота Telegram ===")
print("Введите токен бота Telegram ниже.")
bot_token = getpass.getpass("Bot token: ").strip()
print("Токен успешно получен.")

# Шаг 2: Запрос session key
print("\n=== Шаг 2: Запрос session key ===")
print("Пожалуйста, выполните команду `bw login --raw` в другом терминале.")
print("Введите email, пароль и код 2FA, затем вставьте полученный session key ниже.")
session_key = getpass.getpass("Session key: ").strip()
print(f"Получен session key.")

# Шаг 3: Установка session key как переменной окружения
print("\n=== Шаг 3: Установка session key в переменную окружения ===")
os.environ["BW_SESSION"] = session_key
print("Session key установлен в BW_SESSION.")

# Шаг 4: Подготовка JSON для безопасной заметки с уникальным именем
print("\n=== Шаг 4: Подготовка JSON для Bitwarden ===")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
note_name = f"telegram_token_stat_{timestamp}"

print("Подготовка JSON для токена бота...")
note = {
    "organizationId": None,
    "collectionIds": None,
    "folderId": None,
    "type": 2,  # Безопасная заметка
    "name": note_name,
    "notes": bot_token,
    "favorite": False,
    "fields": [],
    "secureNote": {"type": 0}
}
print("JSON для токена бота подготовлен.")

# Шаг 5: Создание записи в Bitwarden
print("\n=== Шаг 5: Создание записи в Bitwarden ===")
print(f"Создание записи '{note['name']}'...")

try:
    # Преобразование JSON в строку
    json_data = json.dumps(note)
    
    # Кодирование JSON в base64
    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
    
    cmd = ["bw", "create", "item"]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Передача закодированных данных через stdin
    stdout, stderr = process.communicate(input=encoded_data)
    
    if process.returncode != 0:
        print(f"Ошибка при создании записи '{note['name']}':")
        print(f"STDERR: {stderr}")
        exit(1)
    else:
        print(f"Запись '{note['name']}' успешно создана.")
except Exception as e:
    print(f"Ошибка при создании записи '{note['name']}': {e}")
    exit(1)

# Очистка чувствительных данных из памяти
print("\n=== Очистка памяти ===")
bot_token = None
note = None
print("Чувствительные данные (токен и заметка) очищены из памяти.")

# Очистка переменной окружения
del os.environ["BW_SESSION"]
print("\n=== Завершение ===")
print("Токен успешно сохранен в Bitwarden.")
print("Переменная окружения BW_SESSION очищена.")

# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 