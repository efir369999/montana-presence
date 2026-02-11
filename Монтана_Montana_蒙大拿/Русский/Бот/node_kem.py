#!/usr/bin/env python3
"""
node_kem.py
Montana Protocol — ML-KEM-768 Post-Quantum Key Exchange for Nodes

Постквантовый обмен ключами между узлами:
- ML-KEM-768 (FIPS 203) для инкапсуляции ключей
- AES-256-GCM для симметричного шифрования
- ML-DSA-65 для аутентификации

Защита от:
- Квантовых атак (Shor's algorithm, Grover's algorithm)
- Harvest now, decrypt later
- Man-in-the-middle (через ML-DSA-65 подписи)
"""

import hashlib
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ML-KEM-768 через kyber-py
try:
    from kyber_py.ml_kem import ML_KEM_768
    HAS_KYBER = True
except ImportError:
    HAS_KYBER = False
    logger.warning("kyber-py not installed: pip install kyber-py")

# AES-GCM
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography not installed: pip install cryptography")

# ML-DSA-65 для аутентификации
try:
    from dilithium_py.ml_dsa import ML_DSA_65
    HAS_DILITHIUM = True
except ImportError:
    HAS_DILITHIUM = False
    logger.warning("dilithium-py not installed: pip install dilithium-py")


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════════════════════

# ML-KEM-768 (FIPS 203)
PUBLIC_KEY_SIZE = 1184
SECRET_KEY_SIZE = 2400
CIPHERTEXT_SIZE = 1088
SHARED_SECRET_SIZE = 32
KEYPAIR_SEED_SIZE = 48

# Порт для постквантового обмена ключами
PQ_PORT = 19334

# Таймауты
HANDSHAKE_TIMEOUT = 30.0
MESSAGE_TIMEOUT = 60.0

# Версия протокола
PROTOCOL_VERSION = "PQ-1.0"


# ═══════════════════════════════════════════════════════════════════════════════
#                              ML-KEM-768 ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def check_dependencies() -> bool:
    """Проверка зависимостей"""
    if not HAS_KYBER:
        return False
    if not HAS_CRYPTO:
        return False
    if not HAS_DILITHIUM:
        return False
    return True


def derive_kem_seed(private_key_dsa: bytes) -> bytes:
    """
    Деривирует seed для ML-KEM-768 из ML-DSA-65 приватного ключа узла.

    Это позволяет детерминированно генерировать KEM ключи
    для каждого узла на основе его identity.
    """
    # HKDF-подобная деривация
    salt = b"MONTANA_KEM_NODE_V1"

    # SHA3-256 хэш для деривации (не SHA-256, для квантовой стойкости)
    h = hashlib.sha3_256()
    h.update(salt)
    h.update(private_key_dsa)
    derived = h.digest()

    # Расширяем до 48 байт
    h2 = hashlib.sha3_256()
    h2.update(derived)
    h2.update(b"\x01")
    extended = derived + h2.digest()[:16]

    return extended[:KEYPAIR_SEED_SIZE]


def generate_kem_keypair(seed: bytes) -> Optional[Tuple[bytes, bytes]]:
    """
    Генерирует ML-KEM-768 ключевую пару детерминированно из seed.

    Returns:
        (secret_key, public_key) или None при ошибке
    """
    if not HAS_KYBER:
        logger.error("kyber-py not available")
        return None

    if len(seed) != KEYPAIR_SEED_SIZE:
        logger.error(f"Invalid seed size: {len(seed)}, expected {KEYPAIR_SEED_SIZE}")
        return None

    try:
        ML_KEM_768.set_drbg_seed(seed)
        public_key, secret_key = ML_KEM_768.keygen()
        return (secret_key, public_key)
    except Exception as e:
        logger.error(f"KEM keypair generation failed: {e}")
        return None


def encapsulate(public_key: bytes) -> Optional[Tuple[bytes, bytes]]:
    """
    Инкапсуляция для получения shared secret.

    Returns:
        (ciphertext, shared_secret) или None
    """
    if not HAS_KYBER:
        return None

    if len(public_key) != PUBLIC_KEY_SIZE:
        logger.error(f"Invalid public key size: {len(public_key)}")
        return None

    try:
        shared_secret, ciphertext = ML_KEM_768.encaps(public_key)
        return (ciphertext, shared_secret)
    except Exception as e:
        logger.error(f"Encapsulation failed: {e}")
        return None


def decapsulate(ciphertext: bytes, secret_key: bytes) -> Optional[bytes]:
    """
    Декапсуляция для восстановления shared secret.

    Returns:
        shared_secret (32 bytes) или None
    """
    if not HAS_KYBER:
        return None

    if len(ciphertext) != CIPHERTEXT_SIZE:
        logger.error(f"Invalid ciphertext size: {len(ciphertext)}")
        return None

    if len(secret_key) != SECRET_KEY_SIZE:
        logger.error(f"Invalid secret key size: {len(secret_key)}")
        return None

    try:
        shared_secret = ML_KEM_768.decaps(secret_key, ciphertext)
        return shared_secret
    except Exception as e:
        logger.error(f"Decapsulation failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#                              AES-256-GCM
# ═══════════════════════════════════════════════════════════════════════════════

def aes_encrypt(data: bytes, key: bytes) -> Optional[bytes]:
    """
    AES-256-GCM шифрование.

    Returns:
        nonce (12) + ciphertext + tag (16)
    """
    if not HAS_CRYPTO:
        return None

    if len(key) != 32:
        logger.error(f"Invalid key size: {len(key)}")
        return None

    try:
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    except Exception as e:
        logger.error(f"AES encryption failed: {e}")
        return None


def aes_decrypt(encrypted: bytes, key: bytes) -> Optional[bytes]:
    """
    AES-256-GCM расшифровка.

    Args:
        encrypted: nonce (12) + ciphertext + tag (16)
    """
    if not HAS_CRYPTO:
        return None

    if len(key) != 32:
        logger.error(f"Invalid key size: {len(key)}")
        return None

    if len(encrypted) < 28:  # 12 nonce + 16 tag минимум
        logger.error("Encrypted data too short")
        return None

    try:
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        logger.error(f"AES decryption failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#                              SECURE CHANNEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SecureChannel:
    """
    Защищённый канал между двумя узлами.

    Использует:
    - ML-KEM-768 для key exchange
    - AES-256-GCM для шифрования
    - ML-DSA-65 для аутентификации
    """

    local_address: str   # Наш адрес (mt...)
    peer_address: str    # Адрес партнёра (mt...)
    shared_secret: bytes  # 32 bytes from ML-KEM-768
    established_at: datetime

    # Счётчики для nonce (предотвращение replay)
    send_counter: int = 0
    recv_counter: int = 0

    def derive_key(self, sender_address: str, counter: int) -> bytes:
        """
        Деривирует ключ на основе отправителя.

        Ключ детерминирован: оба узла получат одинаковый ключ
        для сообщения от конкретного отправителя.
        """
        h = hashlib.sha3_256()
        h.update(self.shared_secret)
        h.update(sender_address.encode())
        h.update(counter.to_bytes(8, 'big'))
        return h.digest()

    def encrypt(self, data: bytes) -> Optional[bytes]:
        """Шифрует данные для отправки"""
        self.send_counter += 1
        key = self.derive_key(self.local_address, self.send_counter)

        encrypted = aes_encrypt(data, key)
        if encrypted:
            # Добавляем counter в начало
            return self.send_counter.to_bytes(8, 'big') + encrypted
        return None

    def decrypt(self, data: bytes) -> Optional[bytes]:
        """Расшифровывает полученные данные"""
        if len(data) < 8:
            return None

        counter = int.from_bytes(data[:8], 'big')

        # Защита от replay
        if counter <= self.recv_counter:
            logger.warning(f"Replay attack detected: {counter} <= {self.recv_counter}")
            return None

        # Ключ деривируется от адреса отправителя (peer)
        key = self.derive_key(self.peer_address, counter)
        decrypted = aes_decrypt(data[8:], key)

        if decrypted:
            self.recv_counter = counter

        return decrypted


# ═══════════════════════════════════════════════════════════════════════════════
#                              NODE KEM MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class NodeKEMManager:
    """
    Менеджер ML-KEM-768 для узла Montana.

    Управляет:
    - Генерацией KEM ключей из DSA identity
    - Установлением защищённых каналов
    - Хранением активных сессий
    """

    def __init__(self, node_address: str, dsa_private_key: bytes, dsa_public_key: bytes):
        """
        Args:
            node_address: Адрес узла (mt...)
            dsa_private_key: ML-DSA-65 приватный ключ (4032 bytes)
            dsa_public_key: ML-DSA-65 публичный ключ (1952 bytes)
        """
        self.node_address = node_address
        self.dsa_private_key = dsa_private_key
        self.dsa_public_key = dsa_public_key

        # Деривируем KEM ключи из DSA identity
        seed = derive_kem_seed(dsa_private_key)
        keys = generate_kem_keypair(seed)

        if keys:
            self.kem_secret_key, self.kem_public_key = keys
            logger.info(f"[NodeKEM] Initialized for {node_address[:16]}...")
        else:
            self.kem_secret_key = None
            self.kem_public_key = None
            logger.error("[NodeKEM] Failed to generate KEM keys")

        # Активные защищённые каналы
        self.channels: Dict[str, SecureChannel] = {}

    def get_handshake_request(self) -> Dict[str, Any]:
        """
        Создаёт запрос на установление защищённого канала.

        Returns:
            {
                "type": "kem_handshake",
                "version": "PQ-1.0",
                "node_address": "mt...",
                "kem_public_key": "hex...",  # 1184 bytes
                "dsa_public_key": "hex...",  # 1952 bytes
                "timestamp": "iso...",
                "signature": "hex..."        # ML-DSA-65 подпись
            }
        """
        if not self.kem_public_key:
            return {"error": "KEM not initialized"}

        timestamp = datetime.now(timezone.utc).isoformat()

        message = f"KEM_HANDSHAKE:{self.node_address}:{timestamp}"
        signature = ML_DSA_65.sign(self.dsa_private_key, message.encode())

        return {
            "type": "kem_handshake",
            "version": PROTOCOL_VERSION,
            "node_address": self.node_address,
            "kem_public_key": self.kem_public_key.hex(),
            "dsa_public_key": self.dsa_public_key.hex(),
            "timestamp": timestamp,
            "signature": signature.hex()
        }

    def process_handshake_request(
        self,
        request: Dict[str, Any]
    ) -> Optional[Tuple[Dict[str, Any], SecureChannel]]:
        """
        Обрабатывает запрос handshake от другого узла.

        Returns:
            (response, channel) или None при ошибке
        """
        try:
            # Извлекаем данные
            peer_address = request["node_address"]
            peer_kem_pk = bytes.fromhex(request["kem_public_key"])
            peer_dsa_pk = bytes.fromhex(request["dsa_public_key"])
            timestamp = request["timestamp"]
            signature = bytes.fromhex(request["signature"])

            # Проверяем подпись (аутентификация)
            message = f"KEM_HANDSHAKE:{peer_address}:{timestamp}"
            if not ML_DSA_65.verify(peer_dsa_pk, message.encode(), signature):
                logger.warning(f"[NodeKEM] Invalid signature from {peer_address[:16]}...")
                return None

            # Проверяем что адрес соответствует публичному ключу
            expected_address = "mt" + hashlib.sha256(peer_dsa_pk).hexdigest()[:40]
            if peer_address != expected_address:
                logger.warning(f"[NodeKEM] Address mismatch: {peer_address} != {expected_address}")
                return None

            # Инкапсуляция: создаём shared secret
            result = encapsulate(peer_kem_pk)
            if not result:
                return None

            ciphertext, shared_secret = result

            # Создаём канал
            channel = SecureChannel(
                local_address=self.node_address,
                peer_address=peer_address,
                shared_secret=shared_secret,
                established_at=datetime.now(timezone.utc)
            )

            # Сохраняем
            self.channels[peer_address] = channel

            # Подписываем ответ
            response_ts = datetime.now(timezone.utc).isoformat()
            response_msg = f"KEM_RESPONSE:{self.node_address}:{response_ts}"
            response_sig = ML_DSA_65.sign(self.dsa_private_key, response_msg.encode())

            response = {
                "type": "kem_response",
                "version": PROTOCOL_VERSION,
                "node_address": self.node_address,
                "ciphertext": ciphertext.hex(),  # 1088 bytes
                "dsa_public_key": self.dsa_public_key.hex(),
                "timestamp": response_ts,
                "signature": response_sig.hex()
            }

            logger.info(f"[NodeKEM] Channel established with {peer_address[:16]}...")
            return (response, channel)

        except Exception as e:
            logger.error(f"[NodeKEM] Handshake processing failed: {e}")
            return None

    def process_handshake_response(
        self,
        response: Dict[str, Any]
    ) -> Optional[SecureChannel]:
        """
        Обрабатывает ответ на наш handshake запрос.

        Returns:
            SecureChannel или None
        """
        try:
            # Извлекаем данные
            peer_address = response["node_address"]
            ciphertext = bytes.fromhex(response["ciphertext"])
            peer_dsa_pk = bytes.fromhex(response["dsa_public_key"])
            timestamp = response["timestamp"]
            signature = bytes.fromhex(response["signature"])

            # Проверяем подпись
            message = f"KEM_RESPONSE:{peer_address}:{timestamp}"
            if not ML_DSA_65.verify(peer_dsa_pk, message.encode(), signature):
                logger.warning(f"[NodeKEM] Invalid response signature from {peer_address[:16]}...")
                return None

            # Декапсуляция: восстанавливаем shared secret
            shared_secret = decapsulate(ciphertext, self.kem_secret_key)
            if not shared_secret:
                return None

            # Создаём канал
            channel = SecureChannel(
                local_address=self.node_address,
                peer_address=peer_address,
                shared_secret=shared_secret,
                established_at=datetime.now(timezone.utc)
            )

            # Сохраняем
            self.channels[peer_address] = channel

            logger.info(f"[NodeKEM] Channel established with {peer_address[:16]}...")
            return channel

        except Exception as e:
            logger.error(f"[NodeKEM] Response processing failed: {e}")
            return None

    def get_channel(self, peer_address: str) -> Optional[SecureChannel]:
        """Получить защищённый канал к узлу"""
        return self.channels.get(peer_address)

    def close_channel(self, peer_address: str):
        """Закрыть канал"""
        if peer_address in self.channels:
            del self.channels[peer_address]
            logger.info(f"[NodeKEM] Channel closed: {peer_address[:16]}...")


# ═══════════════════════════════════════════════════════════════════════════════
#                              ASYNC CLIENT/SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class PQSecureClient:
    """
    Асинхронный клиент для постквантового обмена ключами.
    """

    def __init__(self, kem_manager: NodeKEMManager):
        self.kem = kem_manager

    async def establish_channel(
        self,
        host: str,
        port: int = PQ_PORT,
        timeout: float = HANDSHAKE_TIMEOUT
    ) -> Optional[SecureChannel]:
        """
        Устанавливает защищённый канал с узлом.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )

            # Отправляем handshake request
            request = self.kem.get_handshake_request()
            data = json.dumps(request).encode()
            writer.write(len(data).to_bytes(4, 'big'))
            writer.write(data)
            await writer.drain()

            # Получаем response
            length_bytes = await asyncio.wait_for(
                reader.read(4),
                timeout=timeout
            )
            length = int.from_bytes(length_bytes, 'big')
            response_data = await asyncio.wait_for(
                reader.read(length),
                timeout=timeout
            )

            response = json.loads(response_data.decode())

            if response.get("type") == "kem_response":
                channel = self.kem.process_handshake_response(response)
                writer.close()
                await writer.wait_closed()
                return channel

            writer.close()
            await writer.wait_closed()
            return None

        except Exception as e:
            logger.error(f"[PQClient] Failed to establish channel with {host}: {e}")
            return None


class PQSecureServer:
    """
    Асинхронный сервер для постквантового обмена ключами.
    """

    def __init__(self, kem_manager: NodeKEMManager):
        self.kem = kem_manager
        self._server = None

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Обрабатывает handshake от клиента"""
        peer = writer.get_extra_info('peername')

        try:
            # Читаем request
            length_bytes = await asyncio.wait_for(
                reader.read(4),
                timeout=HANDSHAKE_TIMEOUT
            )
            length = int.from_bytes(length_bytes, 'big')
            request_data = await asyncio.wait_for(
                reader.read(length),
                timeout=HANDSHAKE_TIMEOUT
            )

            request = json.loads(request_data.decode())

            if request.get("type") == "kem_handshake":
                result = self.kem.process_handshake_request(request)

                if result:
                    response, channel = result
                    data = json.dumps(response).encode()
                    writer.write(len(data).to_bytes(4, 'big'))
                    writer.write(data)
                    await writer.drain()
                    logger.info(f"[PQServer] Handshake complete with {peer}")
                else:
                    error = {"type": "error", "message": "Handshake failed"}
                    data = json.dumps(error).encode()
                    writer.write(len(data).to_bytes(4, 'big'))
                    writer.write(data)
                    await writer.drain()

        except Exception as e:
            logger.error(f"[PQServer] Error handling {peer}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self, host: str = "0.0.0.0", port: int = PQ_PORT):
        """Запускает сервер"""
        self._server = await asyncio.start_server(
            self._handle_client,
            host, port
        )
        logger.info(f"[PQServer] Started on {host}:{port}")

        async with self._server:
            await self._server.serve_forever()

    def stop(self):
        """Останавливает сервер"""
        if self._server:
            self._server.close()


# ═══════════════════════════════════════════════════════════════════════════════
#                              ТЕСТИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════════

def test_node_kem():
    """Тест ML-KEM-768 для узлов"""
    print("=" * 60)
    print("Montana Protocol — ML-KEM-768 Node Test")
    print("=" * 60 + "\n")

    if not check_dependencies():
        print("Missing dependencies. Install:")
        print("  pip install kyber-py cryptography dilithium-py")
        return False

    # Создаём два узла
    print("Generating Node 1 (Amsterdam)...")
    pk1, sk1 = ML_DSA_65.keygen()
    addr1 = "mt" + hashlib.sha256(pk1).hexdigest()[:40]

    print("Generating Node 2 (Moscow)...")
    pk2, sk2 = ML_DSA_65.keygen()
    addr2 = "mt" + hashlib.sha256(pk2).hexdigest()[:40]

    print(f"\nNode 1: {addr1[:20]}...")
    print(f"Node 2: {addr2[:20]}...")

    # Инициализируем KEM менеджеры
    print("\nInitializing KEM managers...")
    kem1 = NodeKEMManager(addr1, sk1, pk1)
    kem2 = NodeKEMManager(addr2, sk2, pk2)

    if not kem1.kem_public_key or not kem2.kem_public_key:
        print("Failed to initialize KEM")
        return False

    # Handshake
    print("\nPerforming handshake...")

    # Node 1 создаёт запрос
    request = kem1.get_handshake_request()
    print(f"  Request size: {len(json.dumps(request))} bytes")

    # Node 2 обрабатывает и отвечает
    result = kem2.process_handshake_request(request)
    if not result:
        print("Handshake failed at Node 2")
        return False

    response, channel2 = result
    print(f"  Response size: {len(json.dumps(response))} bytes")

    # Node 1 обрабатывает ответ
    channel1 = kem1.process_handshake_response(response)
    if not channel1:
        print("Handshake failed at Node 1")
        return False

    print("\nHandshake complete!")
    print(f"  Shared secret match: {channel1.shared_secret == channel2.shared_secret}")

    # Тест шифрования
    print("\nTesting encrypted communication...")

    test_message = b"Hello from Node 1! This is a test message."

    # Node 1 шифрует
    encrypted = channel1.encrypt(test_message)
    print(f"  Original: {len(test_message)} bytes")
    print(f"  Encrypted: {len(encrypted)} bytes")

    # Node 2 расшифровывает
    decrypted = channel2.decrypt(encrypted)
    print(f"  Decrypted: {decrypted}")

    if decrypted == test_message:
        print("\nSUCCESS: Message decrypted correctly")
    else:
        print("\nFAIL: Message mismatch")
        return False

    # Тест replay protection
    print("\nTesting replay protection...")
    replay_result = channel2.decrypt(encrypted)
    if replay_result is None:
        print("  Replay attack blocked correctly")
    else:
        print("  FAIL: Replay attack not detected!")
        return False

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_node_kem()
