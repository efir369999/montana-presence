
#rsa_to_bitwarden_3

import subprocess
import base64
import json
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import getpass
from datetime import datetime

# Шаг 1: Генерация ключей RSA
print("=== Шаг 1: Генерация ключей RSA (4096 бит) ===")
print("Начало генерации ключей...")
try:
    # Используем os.urandom для явного источника случайности
    random_source = os.urandom
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    print("Ключи RSA успешно сгенерированы.")
except Exception as e:
    print(f"Ошибка при генерации ключей RSA: {e}")
    exit(1)

# Шаг 2: Сериализация ключей в PEM формат
print("\n=== Шаг 2: Сериализация ключей в PEM формат ===")
try:
    print("Сериализация приватного ключа...")
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    print("Приватный ключ в PEM формате сериализован.")

    print("Сериализация публичного ключа...")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    print("Публичный ключ в PEM формате сериализован.")
except Exception as e:
    print(f"Ошибка при сериализации ключей: {e}")
    exit(1)

# Шаг 3: Запрос session key
print("\n=== Шаг 3: Запрос session key ===")
print("Пожалуйста, выполните команду `bw login --raw` в другом терминале.")
print("Введите email, пароль и код 2FA, затем вставьте полученный session key ниже.")
session_key = getpass.getpass("Session key: ").strip()
print(f"Получен session key.")

# Шаг 4: Установка session key как переменной окружения
print("\n=== Шаг 4: Установка session key в переменную окружения ===")
os.environ["BW_SESSION"] = session_key
print("Session key установлен в BW_SESSION.")

# Шаг 5: Подготовка JSON для безопасных заметок с уникальными именами
print("\n=== Шаг 5: Подготовка JSON для Bitwarden ===")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
private_note_name = f"private_key_api_bybit_Master_Bybitw3D706SeU1f_{timestamp}"
public_note_name = f"public_key_api_bybit_Master_Bybitw3D706SeU1f_{timestamp}"

print("Подготовка JSON для приватного ключа...")
private_note = {
    "organizationId": None,
    "collectionIds": None,
    "folderId": None,
    "type": 2,  # Безопасная заметка
    "name": private_note_name,
    "notes": private_pem,
    "favorite": False,
    "fields": [],
    "secureNote": {"type": 0}
}
print("JSON для приватного ключа подготовлен.")

print("Подготовка JSON для публичного ключа...")
public_note = {
    "organizationId": None,
    "collectionIds": None,
    "folderId": None,
    "type": 2,  # Безопасная заметка
    "name": public_note_name,
    "notes": public_pem,
    "favorite": False,
    "fields": [],
    "secureNote": {"type": 0}
}
print("JSON для публичного ключа подготовлен.")

# Шаг 6: Создание записей в Bitwarden
print("\n=== Шаг 6: Создание записей в Bitwarden ===")
for note in [private_note, public_note]:
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
private_pem = None
public_pem = None
private_note = None
public_note = None
print("Чувствительные данные (ключи и заметки) очищены из памяти.")

# Очистка переменной окружения
del os.environ["BW_SESSION"]
print("\n=== Завершение ===")
print("Все ключи успешно сохранены в Bitwarden.")
print("Переменная окружения BW_SESSION очищена.")

# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 