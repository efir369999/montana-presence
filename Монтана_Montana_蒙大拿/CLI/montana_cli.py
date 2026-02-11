#!/usr/bin/env python3
"""
MONTANA CLI
Время — единственная реальная валюта

Post-Quantum Security: ML-DSA-65 + ML-KEM-768

Usage:
    montana init          # Создать кошелёк
    montana restore       # Восстановить из когнитивного ключа
    montana balance       # Показать баланс
    montana send <addr> <amount>  # Перевод
    montana status        # Статус сервиса
    montana presence      # Запустить сервис присутствия
"""

import click
import os
import sys
import json
import hashlib
import getpass
import time
from pathlib import Path

# ML-DSA-65
try:
    from dilithium_py.ml_dsa import ML_DSA_65
except ImportError:
    print("Установи dilithium-py: pip install dilithium-py")
    sys.exit(1)

# ML-KEM-768 (постквантовое шифрование ключей)
try:
    from mlkem768 import encrypt_private_key, decrypt_private_key, check_dependencies as check_mlkem
    HAS_MLKEM = check_mlkem()
except ImportError:
    HAS_MLKEM = False
    print("Предупреждение: ML-KEM-768 недоступен. Ключи будут храниться без шифрования.")
    print("Установи: pip install kyber-py cryptography")

try:
    import requests
except ImportError:
    print("Установи requests: pip install requests")
    sys.exit(1)

# Конфигурация
MONTANA_DIR = Path.home() / ".montana"
KEYS_DIR = MONTANA_DIR / "keys"
CONFIG_FILE = MONTANA_DIR / "config.json"
API_URL = "https://1394793-cy33234.tw1.ru"

VERSION = "1.5.0"  # ML-KEM-768 integration


@click.group()
@click.version_option(version=VERSION, prog_name="montana")
def cli():
    """Montana Protocol — Время это деньги"""
    pass


@cli.command()
def init():
    """Создать новый кошелёк"""
    click.echo("Montana Protocol")
    click.echo("   Время — единственная реальная валюта\n")

    # Проверяем существующий кошелёк
    if (KEYS_DIR / "private.key.enc").exists() or (KEYS_DIR / "private.key").exists():
        click.echo("Кошелёк уже существует!")
        config = load_config()
        if config:
            click.echo(f"   Адрес: {config['address']}")
        click.echo("\n   Используй 'montana restore' для восстановления на другом устройстве")
        return

    click.echo("Придумай когнитивный ключ — уникальную фразу минимум из 24 слов.")
    click.echo("Это твоя история. Только ты её знаешь.\n")

    # Ввод когнитивного ключа (скрытый)
    cognitive_key = getpass.getpass("Когнитивный ключ: ")
    cognitive_key_confirm = getpass.getpass("Подтверди ключ: ")

    if cognitive_key != cognitive_key_confirm:
        click.echo("Ключи не совпадают")
        return

    # Валидация
    words = cognitive_key.split()
    if len(words) < 24 and len(cognitive_key) < 150:
        click.echo(f"Минимум 24 слова или 150 символов (сейчас: {len(words)} слов, {len(cognitive_key)} символов)")
        return

    click.echo("\nГенерирую ключи ML-DSA-65...")

    # Генерация ключей из когнитивного ключа
    address = generate_keys_from_cognitive(cognitive_key)

    # Регистрируем на сервере
    try:
        register_on_server(address, cognitive_key)
    except Exception as e:
        click.echo(f"Предупреждение: не удалось зарегистрировать на сервере: {e}")

    click.echo(f"\nКошелёк создан!")
    click.echo(f"   Адрес: {address}")
    if HAS_MLKEM:
        click.echo(f"   Защита: ML-KEM-768 + AES-256-GCM")
    click.echo(f"\nВАЖНО: Запомни свой когнитивный ключ!")
    click.echo("   Это единственный способ восстановить доступ.")


@cli.command()
def restore():
    """Восстановить кошелёк из когнитивного ключа"""
    click.echo("Восстановление кошелька Montana\n")

    cognitive_key = getpass.getpass("Введи когнитивный ключ: ")

    click.echo("\nВосстанавливаю ключи...")
    address = generate_keys_from_cognitive(cognitive_key)

    # Проверяем на сервере
    try:
        resp = requests.get(f"{API_URL}/api/balance/{address}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            click.echo(f"\nКошелёк восстановлен!")
            click.echo(f"   Адрес: {address}")
            click.echo(f"   Баланс: {data.get('balance', 0)}")
        else:
            click.echo(f"\nПрофиль не найден на сервере. Создан новый кошелёк.")
            click.echo(f"   Адрес: {address}")
    except Exception as e:
        click.echo(f"\nКошелёк создан локально (сервер недоступен: {e})")
        click.echo(f"   Адрес: {address}")


@cli.command()
def balance():
    """Показать баланс"""
    config = load_config()
    if not config:
        click.echo("Сначала выполни: montana init")
        return

    address = config["address"]

    try:
        resp = requests.get(f"{API_URL}/api/balance/{address}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bal = data.get('balance', 0)
            click.echo(f"{bal}")
            click.echo(f"Адрес: {address}")
        else:
            click.echo(f"Ошибка: {resp.status_code}")
    except Exception as e:
        click.echo(f"Ошибка подключения: {e}")


@cli.command()
def address():
    """Показать адрес кошелька"""
    config = load_config()
    if not config:
        click.echo("Сначала выполни: montana init")
        return

    click.echo(config["address"])


@cli.command()
@click.argument("to_address")
@click.argument("amount", type=int)
def send(to_address, amount):
    """Отправить на адрес"""
    config = load_config()
    if not config:
        click.echo("Сначала выполни: montana init")
        return

    from_address = config["address"]

    click.echo(f"Отправить {amount} на {to_address}?")
    if not click.confirm("Подтвердить?"):
        return

    # Загружаем приватный ключ (требует когнитивный ключ если зашифрован)
    private_key = load_private_key()
    if not private_key:
        click.echo("Не удалось загрузить приватный ключ")
        return

    timestamp = int(time.time())
    message = f"TRANSFER:{from_address}:{to_address}:{amount}:{timestamp}"
    signature = ML_DSA_65.sign(private_key, message.encode())

    try:
        resp = requests.post(f"{API_URL}/api/transfer", json={
            "from": from_address,
            "to": to_address,
            "amount": amount,
            "timestamp": timestamp,
            "signature": signature.hex()
        }, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                click.echo(f"Отправлено {amount}")
                if "new_balance" in data:
                    click.echo(f"Новый баланс: {data['new_balance']}")
            else:
                click.echo(f"Ошибка: {data.get('error', 'Unknown')}")
        else:
            click.echo(f"Ошибка сервера: {resp.status_code}")
    except Exception as e:
        click.echo(f"Ошибка: {e}")


@cli.command()
def status():
    """Статус сервиса присутствия"""
    import subprocess

    config = load_config()
    if config:
        click.echo(f"Адрес: {config['address']}")
        if config.get("encrypted"):
            click.echo("Защита: ML-KEM-768 + AES-256-GCM")

    if sys.platform == "darwin":
        result = subprocess.run(
            ["launchctl", "list", "network.montana.presence"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            click.echo("Сервис присутствия: активен")
        else:
            click.echo("Сервис присутствия: остановлен")
    else:
        result = subprocess.run(
            ["systemctl", "is-active", "montana-presence"],
            capture_output=True, text=True
        )
        if "active" in result.stdout:
            click.echo("Сервис присутствия: активен")
        else:
            click.echo("Сервис присутствия: остановлен")


@cli.command()
@click.option("--daemon", is_flag=True, help="Запуск как daemon (без вывода)")
def presence(daemon):
    """Сервис присутствия (Proof of Presence)"""
    config = load_config()
    if not config:
        click.echo("Сначала выполни: montana init")
        return

    address = config["address"]

    if not daemon:
        click.echo(f"Сервис присутствия запущен")
        click.echo(f"   Адрес: {address}")
        click.echo("   Ctrl+C для остановки\n")

    last_sync = 0
    presence_seconds = 0

    while True:
        try:
            time.sleep(1)
            presence_seconds += 1

            # Синхронизация каждые 30 секунд
            if time.time() - last_sync >= 30:
                try:
                    resp = requests.post(
                        f"{API_URL}/api/presence",
                        headers={"X-Device-ID": address},
                        json={"seconds": presence_seconds},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        presence_seconds = 0
                        last_sync = time.time()
                        if not daemon:
                            bal = data.get("balance", "?")
                            click.echo(f"  Синхронизировано | Баланс: {bal}")
                except Exception as e:
                    if not daemon:
                        click.echo(f"  Ошибка синхронизации: {e}")

        except KeyboardInterrupt:
            if not daemon:
                click.echo("\nОстановлено")
            break


@cli.command()
def stop():
    """Остановить сервис присутствия"""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["sudo", "launchctl", "unload",
                       "/Library/LaunchDaemons/network.montana.presence.plist"],
                      capture_output=True)
        click.echo("Сервис остановлен")
    else:
        subprocess.run(["sudo", "systemctl", "stop", "montana-presence"],
                      capture_output=True)
        click.echo("Сервис остановлен")


@cli.command()
def start():
    """Запустить сервис присутствия"""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["sudo", "launchctl", "load",
                       "/Library/LaunchDaemons/network.montana.presence.plist"],
                      capture_output=True)
        click.echo("Сервис запущен")
    else:
        subprocess.run(["sudo", "systemctl", "start", "montana-presence"],
                      capture_output=True)
        click.echo("Сервис запущен")


# === Вспомогательные функции ===

def generate_keys_from_cognitive(cognitive_key: str) -> str:
    """Генерация ML-DSA-65 ключей из когнитивного ключа"""

    # Нормализация
    normalized = " ".join(cognitive_key.lower().split())

    # PBKDF2 (600K итераций) — защита от brute-force
    salt = b"MONTANA_COGNITIVE_KEY_V1"
    seed = hashlib.pbkdf2_hmac("sha256", normalized.encode(), salt, 600_000, dklen=32)

    # Детерминированная генерация ML-DSA-65
    import random
    random.seed(int.from_bytes(seed, 'big'))

    public_key, private_key = ML_DSA_65.keygen()

    # Адрес = mt + SHA256(pubkey)[:20].hex()
    address = "mt" + hashlib.sha256(public_key).hexdigest()[:40]

    # Создаём директории
    MONTANA_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # Сохраняем ключи
    if HAS_MLKEM:
        # Шифруем приватный ключ с ML-KEM-768
        encrypted = encrypt_private_key(private_key, cognitive_key)
        if encrypted:
            (KEYS_DIR / "private.key.enc").write_bytes(encrypted)
            os.chmod(KEYS_DIR / "private.key.enc", 0o600)
            # Удаляем незашифрованный если был
            if (KEYS_DIR / "private.key").exists():
                (KEYS_DIR / "private.key").unlink()
        else:
            # Fallback на незашифрованное хранение
            (KEYS_DIR / "private.key").write_bytes(private_key)
            os.chmod(KEYS_DIR / "private.key", 0o600)
    else:
        # Без ML-KEM — сохраняем открыто
        (KEYS_DIR / "private.key").write_bytes(private_key)
        os.chmod(KEYS_DIR / "private.key", 0o600)

    (KEYS_DIR / "public.key").write_bytes(public_key)

    # Сохраняем конфиг
    config = {
        "address": address,
        "public_key": public_key.hex(),
        "version": VERSION,
        "encrypted": HAS_MLKEM and (KEYS_DIR / "private.key.enc").exists()
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

    return address


def register_on_server(address: str, cognitive_key: str):
    """Регистрация адреса на сервере"""
    public_key = (KEYS_DIR / "public.key").read_bytes()
    private_key = load_private_key_internal(cognitive_key)
    if not private_key:
        raise Exception("Не удалось загрузить приватный ключ")

    # Подписываем регистрацию
    message = f"MONTANA_REGISTER:{address}"
    signature = ML_DSA_65.sign(private_key, message.encode())

    resp = requests.post(f"{API_URL}/api/auth/register", json={
        "address": address,
        "public_key": public_key.hex(),
        "signature": signature.hex()
    }, timeout=30)

    return resp.status_code == 200


def load_config():
    """Загрузить конфигурацию"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return None


def load_private_key_internal(cognitive_key: str) -> bytes:
    """Загрузить приватный ключ с когнитивным ключом"""
    # Сначала пробуем зашифрованный
    enc_path = KEYS_DIR / "private.key.enc"
    if enc_path.exists() and HAS_MLKEM:
        encrypted = enc_path.read_bytes()
        decrypted = decrypt_private_key(encrypted, cognitive_key)
        if decrypted:
            return decrypted
        return None

    # Fallback на незашифрованный
    plain_path = KEYS_DIR / "private.key"
    if plain_path.exists():
        return plain_path.read_bytes()

    return None


def load_private_key():
    """Загрузить приватный ключ (запрашивает когнитивный ключ если нужно)"""
    config = load_config()

    # Если ключ зашифрован — запрашиваем когнитивный ключ
    if config and config.get("encrypted"):
        cognitive_key = getpass.getpass("Когнитивный ключ: ")
        return load_private_key_internal(cognitive_key)

    # Незашифрованный
    plain_path = KEYS_DIR / "private.key"
    if plain_path.exists():
        return plain_path.read_bytes()

    return None


if __name__ == "__main__":
    cli()
