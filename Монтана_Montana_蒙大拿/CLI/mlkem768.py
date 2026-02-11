"""
ML-KEM-768 Post-Quantum Key Encapsulation for Montana Protocol
FIPS 203 Standard

Шифрование приватного ключа ML-DSA-65 с помощью когнитивного ключа.
Совместимо с iOS реализацией.

Dependencies:
    pip install kyber-py cryptography
"""

import hashlib
import os
from typing import Optional, Tuple

# ML-KEM-768 через kyber-py (чистый Python, детерминированная генерация)
try:
    from kyber_py.ml_kem import ML_KEM_768
    HAS_KYBER = True
except ImportError:
    HAS_KYBER = False

# AES-GCM через cryptography
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# Константы ML-KEM-768 (FIPS 203)
PUBLIC_KEY_SIZE = 1184
SECRET_KEY_SIZE = 2400
CIPHERTEXT_SIZE = 1088
SHARED_SECRET_SIZE = 32
KEYPAIR_SEED_SIZE = 48  # kyber-py требует 48 байт

# ML-DSA-65 размеры
MLDSA65_PRIVATE_KEY_SIZE = 4032
MLDSA65_PUBLIC_KEY_SIZE = 1952

# Salt для PBKDF2 (должен совпадать с iOS)
KEM_KEY_SALT = b"MONTANA_KEM_KEY_V1"


def check_dependencies() -> bool:
    """Проверка зависимостей"""
    if not HAS_KYBER:
        print("ОШИБКА: Установи kyber-py:")
        print("  pip install kyber-py")
        return False
    if not HAS_CRYPTO:
        print("ОШИБКА: Установи cryptography:")
        print("  pip install cryptography")
        return False
    return True


def pbkdf2_derive(password: str, salt: bytes, iterations: int, key_length: int) -> bytes:
    """PBKDF2-HMAC-SHA256 деривация"""
    normalized = " ".join(password.lower().split())
    return hashlib.pbkdf2_hmac(
        "sha256",
        normalized.encode("utf-8"),
        salt,
        iterations,
        dklen=key_length
    )


def keypair_from_seed(seed: bytes) -> Optional[Tuple[bytes, bytes]]:
    """
    Детерминированная генерация ML-KEM-768 ключевой пары из seed.

    Args:
        seed: 64-byte seed

    Returns:
        (secret_key, public_key) или None при ошибке
    """
    if len(seed) != KEYPAIR_SEED_SIZE:
        print(f"[MLKEM768] Invalid seed size: {len(seed)}, expected {KEYPAIR_SEED_SIZE}")
        return None

    try:
        # ML_KEM_768 — singleton, устанавливаем seed и генерируем
        ML_KEM_768.set_drbg_seed(seed)

        # Генерируем ключевую пару детерминированно
        public_key, secret_key = ML_KEM_768.keygen()

        print(f"[MLKEM768] Generated keypair: pk={len(public_key)}, sk={len(secret_key)}")
        return (secret_key, public_key)

    except Exception as e:
        print(f"[MLKEM768] Keypair generation failed: {e}")
        return None


def encapsulate(public_key: bytes, seed: Optional[bytes] = None) -> Optional[Tuple[bytes, bytes]]:
    """
    Инкапсуляция для получения shared secret.

    Args:
        public_key: ML-KEM-768 публичный ключ
        seed: Опциональный seed для детерминированной инкапсуляции

    Returns:
        (ciphertext, shared_secret) или None
    """
    if len(public_key) != PUBLIC_KEY_SIZE:
        print(f"[MLKEM768] Invalid public key size: {len(public_key)}")
        return None

    try:
        if seed:
            ML_KEM_768.set_drbg_seed(seed)

        shared_secret, ciphertext = ML_KEM_768.encaps(public_key)

        print(f"[MLKEM768] Encapsulated: ct={len(ciphertext)}, ss={len(shared_secret)}")
        return (ciphertext, shared_secret)

    except Exception as e:
        print(f"[MLKEM768] Encapsulation failed: {e}")
        return None


def decapsulate(ciphertext: bytes, secret_key: bytes) -> Optional[bytes]:
    """
    Декапсуляция для восстановления shared secret.

    Args:
        ciphertext: ML-KEM-768 ciphertext
        secret_key: ML-KEM-768 секретный ключ

    Returns:
        shared_secret (32 bytes) или None
    """
    if len(ciphertext) != CIPHERTEXT_SIZE:
        print(f"[MLKEM768] Invalid ciphertext size: {len(ciphertext)}")
        return None
    if len(secret_key) != SECRET_KEY_SIZE:
        print(f"[MLKEM768] Invalid secret key size: {len(secret_key)}")
        return None

    try:
        shared_secret = ML_KEM_768.decaps(secret_key, ciphertext)

        print(f"[MLKEM768] Decapsulated: ss={len(shared_secret)}")
        return shared_secret

    except Exception as e:
        print(f"[MLKEM768] Decapsulation failed: {e}")
        return None


def aes_gcm_encrypt(data: bytes, key: bytes, nonce: bytes) -> Optional[bytes]:
    """AES-256-GCM шифрование"""
    if len(key) != 32:
        print(f"[AES] Invalid key size: {len(key)}")
        return None
    if len(nonce) != 12:
        print(f"[AES] Invalid nonce size: {len(nonce)}")
        return None

    try:
        aesgcm = AESGCM(key)
        return aesgcm.encrypt(nonce, data, None)
    except Exception as e:
        print(f"[AES] Encryption failed: {e}")
        return None


def aes_gcm_decrypt(data: bytes, key: bytes, nonce: bytes) -> Optional[bytes]:
    """AES-256-GCM расшифровка"""
    if len(key) != 32:
        print(f"[AES] Invalid key size: {len(key)}")
        return None
    if len(nonce) != 12:
        print(f"[AES] Invalid nonce size: {len(nonce)}")
        return None

    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, data, None)
    except Exception as e:
        print(f"[AES] Decryption failed: {e}")
        return None


def encrypt_private_key(private_key: bytes, cognitive_key: str) -> Optional[bytes]:
    """
    Зашифровать ML-DSA-65 приватный ключ с помощью когнитивного ключа.

    Схема: ML-KEM-768 + AES-256-GCM

    Args:
        private_key: ML-DSA-65 приватный ключ (4032 bytes)
        cognitive_key: Когнитивный ключ пользователя

    Returns:
        Зашифрованные данные или None
    """
    if not check_dependencies():
        return None

    if len(private_key) != MLDSA65_PRIVATE_KEY_SIZE:
        print(f"[MLKEM768] Invalid private key size: {len(private_key)}")
        return None

    # 1. Деривация seed из когнитивного ключа (600K итераций)
    seed = pbkdf2_derive(cognitive_key, KEM_KEY_SALT, 600_000, KEYPAIR_SEED_SIZE)

    # 2. Генерация ML-KEM-768 keypair детерминированно
    keys = keypair_from_seed(seed)
    if not keys:
        return None
    secret_key, public_key = keys

    # 3. Инкапсуляция для получения shared secret
    encaps_result = encapsulate(public_key)
    if not encaps_result:
        return None
    ciphertext, shared_secret = encaps_result

    # 4. AES-GCM шифрование приватного ключа
    nonce = os.urandom(12)
    encrypted = aes_gcm_encrypt(private_key, shared_secret, nonce)
    if not encrypted:
        return None

    # 5. Упаковка: ciphertext (1088) + nonce (12) + encrypted (4032 + 16 tag)
    result = ciphertext + nonce + encrypted

    print(f"[MLKEM768] Encrypted private key: {len(result)} bytes")
    return result


def decrypt_private_key(encrypted_data: bytes, cognitive_key: str) -> Optional[bytes]:
    """
    Расшифровать ML-DSA-65 приватный ключ с помощью когнитивного ключа.

    Args:
        encrypted_data: Зашифрованные данные
        cognitive_key: Когнитивный ключ пользователя

    Returns:
        ML-DSA-65 приватный ключ или None
    """
    if not check_dependencies():
        return None

    # Минимальный размер: ciphertext (1088) + nonce (12) + priv (4032) + tag (16)
    min_size = CIPHERTEXT_SIZE + 12 + MLDSA65_PRIVATE_KEY_SIZE + 16
    if len(encrypted_data) < min_size:
        print(f"[MLKEM768] Encrypted data too small: {len(encrypted_data)}, expected >= {min_size}")
        return None

    # 1. Деривация seed из когнитивного ключа (600K итераций)
    seed = pbkdf2_derive(cognitive_key, KEM_KEY_SALT, 600_000, KEYPAIR_SEED_SIZE)

    # 2. Генерация ML-KEM-768 keypair детерминированно
    keys = keypair_from_seed(seed)
    if not keys:
        return None
    secret_key, public_key = keys

    # 3. Распаковка
    kem_ciphertext = encrypted_data[:CIPHERTEXT_SIZE]
    nonce = encrypted_data[CIPHERTEXT_SIZE:CIPHERTEXT_SIZE + 12]
    aes_ciphertext = encrypted_data[CIPHERTEXT_SIZE + 12:]

    # 4. Декапсуляция для восстановления shared secret
    shared_secret = decapsulate(kem_ciphertext, secret_key)
    if not shared_secret:
        print("[MLKEM768] Decapsulation failed - wrong cognitive key?")
        return None

    # 5. AES-GCM расшифровка
    decrypted = aes_gcm_decrypt(aes_ciphertext, shared_secret, nonce)
    if not decrypted:
        print("[MLKEM768] AES decryption failed")
        return None

    # 6. Проверка размера
    if len(decrypted) != MLDSA65_PRIVATE_KEY_SIZE:
        print(f"[MLKEM768] Decrypted key wrong size: {len(decrypted)}")
        return None

    print(f"[MLKEM768] Decrypted private key: {len(decrypted)} bytes")
    return decrypted


# === Тестирование ===

def test_mlkem768():
    """Тест ML-KEM-768 шифрования"""
    print("=" * 50)
    print("ML-KEM-768 + AES-256-GCM Test")
    print("=" * 50 + "\n")

    if not check_dependencies():
        return False

    # Тестовые данные
    test_private_key = os.urandom(MLDSA65_PRIVATE_KEY_SIZE)
    cognitive_key = "это мой уникальный когнитивный ключ для проверки постквантового шифрования приватного ключа"

    print(f"Private key size: {len(test_private_key)} bytes")
    print(f"Cognitive key: {cognitive_key[:40]}...")
    print()

    # Шифруем
    print("Encrypting...")
    encrypted = encrypt_private_key(test_private_key, cognitive_key)
    if not encrypted:
        print("❌ FAIL: Encryption failed")
        return False

    print(f"Encrypted size: {len(encrypted)} bytes")
    print(f"  - KEM ciphertext: {CIPHERTEXT_SIZE} bytes")
    print(f"  - Nonce: 12 bytes")
    print(f"  - AES ciphertext: {len(encrypted) - CIPHERTEXT_SIZE - 12} bytes")
    print()

    # Расшифровываем с правильным ключом
    print("Decrypting with correct key...")
    decrypted = decrypt_private_key(encrypted, cognitive_key)
    if not decrypted:
        print("❌ FAIL: Decryption failed")
        return False

    # Проверяем
    if decrypted == test_private_key:
        print("\n✅ SUCCESS: Decrypted key matches original")
    else:
        print("\n❌ FAIL: Keys don't match")
        return False

    # Тест с неправильным ключом
    print("\nDecrypting with wrong key...")
    wrong_decrypted = decrypt_private_key(encrypted, "wrong cognitive key")
    if wrong_decrypted is None:
        print("✅ Correctly rejected wrong key")
    else:
        print("❌ FAIL: Should have rejected wrong key")
        return False

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
    return True


if __name__ == "__main__":
    test_mlkem768()
