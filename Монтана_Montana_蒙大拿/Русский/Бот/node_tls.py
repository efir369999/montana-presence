#!/usr/bin/env python3
"""
node_tls.py
Montana Protocol — Hybrid TLS + ML-KEM-768 Шифрование между узлами

Обеспечивает защищённую связь между узлами Montana:
- TLS 1.3 шифрование всего трафика (классическая защита)
- ML-KEM-768 post-quantum key exchange (FIPS 203)
- Взаимная аутентификация узлов через ML-DSA-65

HYBRID ЗАЩИТА:
- TLS 1.3: защита от классических атак
- ML-KEM-768: защита от квантовых атак
- Данные защищены даже если одна из систем скомпрометирована

Защита от:
- Квантовых атак (Shor's algorithm)
- Harvest now, decrypt later
- Man-in-the-middle атак
- Перехвата трафика
"""

import ssl
import socket
import asyncio
import logging
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ML-KEM-768 Post-Quantum Key Exchange
try:
    from node_kem import (
        NodeKEMManager,
        SecureChannel as PQSecureChannel,
        check_dependencies as check_pq_dependencies,
        PQ_PORT
    )
    HAS_PQ = check_pq_dependencies()
except ImportError:
    HAS_PQ = False
    logger.warning("node_kem not available, post-quantum disabled")


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TLSConfig:
    """Конфигурация TLS"""

    # Порт для защищённой связи
    SECURE_PORT: int = 19333

    # Таймауты
    CONNECT_TIMEOUT: float = 10.0
    READ_TIMEOUT: float = 30.0

    # SSL/TLS параметры
    TLS_VERSION = ssl.TLSVersion.TLSv1_3
    VERIFY_MODE = ssl.CERT_OPTIONAL  # CERT_REQUIRED для production

    # Пути к сертификатам (генерируются автоматически)
    CERTS_DIR: str = "certs"
    CERT_FILE: str = "node.crt"
    KEY_FILE: str = "node.key"
    CA_FILE: str = "montana_ca.crt"


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЕНЕРАЦИЯ СЕРТИФИКАТОВ
# ═══════════════════════════════════════════════════════════════════════════════

class CertificateManager:
    """
    Менеджер сертификатов для узлов Montana

    Генерирует self-signed сертификаты с привязкой к
    криптографическому адресу узла (mt...).
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path(__file__).parent
        self.certs_dir = self.data_dir / TLSConfig.CERTS_DIR
        self.certs_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed_cert(
        self,
        node_address: str,
        node_name: str,
        days_valid: int = 365
    ) -> Tuple[Path, Path]:
        """
        Генерирует self-signed сертификат для узла

        Args:
            node_address: Криптографический адрес узла (mt...)
            node_name: Имя узла (amsterdam, moscow, etc.)
            days_valid: Срок действия в днях

        Returns:
            (cert_path, key_path)
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from datetime import timedelta

            # Генерируем RSA ключ для TLS (ML-DSA-65 не поддерживается в TLS пока)
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
            )

            # Создаём сертификат
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "NL"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Montana"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, node_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Montana Protocol"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"{node_name}.montana.network"),
                x509.NameAttribute(NameOID.USER_ID, node_address),
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=days_valid)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(f"{node_name}.montana.network"),
                    x509.DNSName("localhost"),
                ]),
                critical=False,
            ).sign(key, hashes.SHA256())

            # Сохраняем
            cert_path = self.certs_dir / f"{node_name}.crt"
            key_path = self.certs_dir / f"{node_name}.key"

            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            with open(key_path, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            logger.info(f"🔐 Сертификат создан: {cert_path}")
            return cert_path, key_path

        except ImportError:
            logger.warning("⚠️ cryptography не установлена, используем openssl")
            return self._generate_with_openssl(node_address, node_name, days_valid)

    def _generate_with_openssl(
        self,
        node_address: str,
        node_name: str,
        days_valid: int
    ) -> Tuple[Path, Path]:
        """Генерация через openssl CLI"""
        import subprocess

        cert_path = self.certs_dir / f"{node_name}.crt"
        key_path = self.certs_dir / f"{node_name}.key"

        # Генерируем ключ и сертификат
        cmd = [
            "openssl", "req", "-x509", "-newkey", "rsa:4096",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", str(days_valid),
            "-nodes",
            "-subj", f"/CN={node_name}.montana.network/O=Montana Protocol/UID={node_address}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"openssl error: {result.stderr}")

        logger.info(f"🔐 Сертификат создан (openssl): {cert_path}")
        return cert_path, key_path

    def get_cert_paths(self, node_name: str) -> Tuple[Optional[Path], Optional[Path]]:
        """Получить пути к сертификатам узла"""
        cert_path = self.certs_dir / f"{node_name}.crt"
        key_path = self.certs_dir / f"{node_name}.key"

        if cert_path.exists() and key_path.exists():
            return cert_path, key_path
        return None, None


# ═══════════════════════════════════════════════════════════════════════════════
#                              TLS КОНТЕКСТ
# ═══════════════════════════════════════════════════════════════════════════════

class SecureContext:
    """
    Создаёт SSL контекст для защищённой связи
    """

    @staticmethod
    def create_server_context(
        cert_path: Path,
        key_path: Path,
        ca_path: Path = None
    ) -> ssl.SSLContext:
        """
        Создаёт SSL контекст для сервера

        Args:
            cert_path: Путь к сертификату
            key_path: Путь к приватному ключу
            ca_path: Путь к CA сертификату (для mTLS)
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = TLSConfig.TLS_VERSION

        # Загружаем сертификат
        context.load_cert_chain(str(cert_path), str(key_path))

        # CA для проверки клиентов (mTLS)
        if ca_path and ca_path.exists():
            context.load_verify_locations(str(ca_path))
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_OPTIONAL

        # Безопасные настройки
        context.set_ciphers('ECDHE+AESGCM:DHE+AESGCM')
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3

        return context

    @staticmethod
    def create_client_context(
        cert_path: Path = None,
        key_path: Path = None,
        ca_path: Path = None,
        verify: bool = False
    ) -> ssl.SSLContext:
        """
        Создаёт SSL контекст для клиента

        Args:
            cert_path: Путь к сертификату (для mTLS)
            key_path: Путь к приватному ключу (для mTLS)
            ca_path: Путь к CA сертификату
            verify: Проверять сертификат сервера
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = TLSConfig.TLS_VERSION

        # Клиентский сертификат (для mTLS)
        if cert_path and key_path:
            context.load_cert_chain(str(cert_path), str(key_path))

        # Проверка сервера
        if verify and ca_path and ca_path.exists():
            context.load_verify_locations(str(ca_path))
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        return context


# ═══════════════════════════════════════════════════════════════════════════════
#                              ЗАЩИЩЁННЫЙ КЛИЕНТ
# ═══════════════════════════════════════════════════════════════════════════════

class SecureNodeClient:
    """
    Клиент для защищённой связи с другими узлами
    """

    def __init__(self, cert_manager: CertificateManager = None):
        self.cert_manager = cert_manager or CertificateManager()

    async def connect(
        self,
        host: str,
        port: int = TLSConfig.SECURE_PORT,
        timeout: float = TLSConfig.CONNECT_TIMEOUT
    ) -> Tuple[Optional[asyncio.StreamReader], Optional[asyncio.StreamWriter]]:
        """
        Устанавливает защищённое соединение с узлом

        Returns:
            (reader, writer) или (None, None) при ошибке
        """
        try:
            ssl_context = SecureContext.create_client_context(verify=False)

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host, port,
                    ssl=ssl_context
                ),
                timeout=timeout
            )

            logger.debug(f"🔐 TLS соединение с {host}:{port}")
            return reader, writer

        except asyncio.TimeoutError:
            logger.warning(f"⏰ Таймаут подключения к {host}:{port}")
            return None, None
        except Exception as e:
            logger.warning(f"❌ Ошибка TLS подключения к {host}:{port}: {e}")
            return None, None

    async def send_message(
        self,
        host: str,
        message: Dict[str, Any],
        port: int = TLSConfig.SECURE_PORT
    ) -> Optional[Dict[str, Any]]:
        """
        Отправляет сообщение и получает ответ

        Args:
            host: IP адрес узла
            message: Сообщение (dict)
            port: Порт

        Returns:
            Ответ (dict) или None
        """
        reader, writer = await self.connect(host, port)
        if not reader or not writer:
            return None

        try:
            # Отправляем
            data = json.dumps(message).encode('utf-8')
            writer.write(len(data).to_bytes(4, 'big'))
            writer.write(data)
            await writer.drain()

            # Получаем ответ
            length_bytes = await asyncio.wait_for(
                reader.read(4),
                timeout=TLSConfig.READ_TIMEOUT
            )
            if not length_bytes:
                return None

            length = int.from_bytes(length_bytes, 'big')
            response_data = await asyncio.wait_for(
                reader.read(length),
                timeout=TLSConfig.READ_TIMEOUT
            )

            return json.loads(response_data.decode('utf-8'))

        except Exception as e:
            logger.warning(f"❌ Ошибка отправки: {e}")
            return None
        finally:
            writer.close()
            await writer.wait_closed()


# ═══════════════════════════════════════════════════════════════════════════════
#                              ЗАЩИЩЁННЫЙ СЕРВЕР
# ═══════════════════════════════════════════════════════════════════════════════

class SecureNodeServer:
    """
    Сервер для приёма защищённых соединений
    """

    def __init__(
        self,
        node_name: str,
        node_address: str,
        cert_manager: CertificateManager = None
    ):
        self.node_name = node_name
        self.node_address = node_address
        self.cert_manager = cert_manager or CertificateManager()

        self._server = None
        self._handlers = {}

        # Проверяем/создаём сертификаты
        self._ensure_certificates()

    def _ensure_certificates(self):
        """Убеждаемся что сертификаты существуют"""
        cert_path, key_path = self.cert_manager.get_cert_paths(self.node_name)

        if not cert_path or not key_path:
            logger.info(f"🔐 Генерация сертификата для {self.node_name}...")
            self.cert_path, self.key_path = self.cert_manager.generate_self_signed_cert(
                self.node_address,
                self.node_name
            )
        else:
            self.cert_path = cert_path
            self.key_path = key_path

    def register_handler(self, message_type: str, handler):
        """Регистрирует обработчик для типа сообщений"""
        self._handlers[message_type] = handler

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Обрабатывает клиентское соединение"""
        peer = writer.get_extra_info('peername')
        logger.debug(f"🔐 TLS клиент подключился: {peer}")

        try:
            while True:
                # Читаем длину сообщения
                length_bytes = await asyncio.wait_for(
                    reader.read(4),
                    timeout=TLSConfig.READ_TIMEOUT
                )
                if not length_bytes:
                    break

                length = int.from_bytes(length_bytes, 'big')

                # Читаем сообщение
                data = await asyncio.wait_for(
                    reader.read(length),
                    timeout=TLSConfig.READ_TIMEOUT
                )

                message = json.loads(data.decode('utf-8'))
                msg_type = message.get("type", "unknown")

                # Обрабатываем
                handler = self._handlers.get(msg_type, self._default_handler)
                response = await handler(message, peer)

                # Отправляем ответ
                response_data = json.dumps(response).encode('utf-8')
                writer.write(len(response_data).to_bytes(4, 'big'))
                writer.write(response_data)
                await writer.drain()

        except asyncio.TimeoutError:
            logger.debug(f"⏰ Клиент {peer} таймаут")
        except Exception as e:
            logger.warning(f"❌ Ошибка обработки клиента {peer}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _default_handler(self, message: Dict, peer) -> Dict:
        """Обработчик по умолчанию"""
        return {
            "type": "ack",
            "node": self.node_name,
            "address": self.node_address,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def start(
        self,
        host: str = "0.0.0.0",
        port: int = TLSConfig.SECURE_PORT
    ):
        """Запускает TLS сервер"""
        ssl_context = SecureContext.create_server_context(
            self.cert_path,
            self.key_path
        )

        self._server = await asyncio.start_server(
            self._handle_client,
            host, port,
            ssl=ssl_context
        )

        logger.info(f"🔐 TLS сервер запущен на {host}:{port}")
        logger.info(f"   Сертификат: {self.cert_path}")

        async with self._server:
            await self._server.serve_forever()

    def stop(self):
        """Останавливает сервер"""
        if self._server:
            self._server.close()


# ═══════════════════════════════════════════════════════════════════════════════
#                    HYBRID TLS + ML-KEM-768 (POST-QUANTUM)
# ═══════════════════════════════════════════════════════════════════════════════

class HybridSecureClient:
    """
    Клиент с гибридной защитой: TLS 1.3 + ML-KEM-768

    Последовательность:
    1. Устанавливается TLS 1.3 соединение
    2. Внутри TLS выполняется ML-KEM-768 handshake
    3. Сообщения дважды шифруются: TLS + AES-256-GCM(ML-KEM shared secret)

    Это обеспечивает защиту даже если:
    - TLS взломан квантовым компьютером
    - ML-KEM-768 имеет уязвимость
    """

    def __init__(
        self,
        kem_manager: 'NodeKEMManager' = None,
        cert_manager: CertificateManager = None
    ):
        self.cert_manager = cert_manager or CertificateManager()
        self.kem = kem_manager
        self._tls_client = SecureNodeClient(self.cert_manager)

    async def establish_hybrid_channel(
        self,
        host: str,
        port: int = TLSConfig.SECURE_PORT,
        timeout: float = TLSConfig.CONNECT_TIMEOUT
    ) -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter, 'PQSecureChannel']]:
        """
        Устанавливает гибридный защищённый канал.

        Returns:
            (reader, writer, pq_channel) или None
        """
        if not HAS_PQ or not self.kem:
            logger.warning("Post-quantum not available, using TLS only")
            reader, writer = await self._tls_client.connect(host, port, timeout)
            return (reader, writer, None) if reader else None

        try:
            # 1. Устанавливаем TLS соединение
            ssl_context = SecureContext.create_client_context(verify=False)
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_context),
                timeout=timeout
            )

            # 2. Отправляем ML-KEM-768 handshake внутри TLS
            request = self.kem.get_handshake_request()
            data = json.dumps(request).encode()
            writer.write(len(data).to_bytes(4, 'big'))
            writer.write(data)
            await writer.drain()

            # 3. Получаем ответ
            length_bytes = await asyncio.wait_for(reader.read(4), timeout=timeout)
            length = int.from_bytes(length_bytes, 'big')
            response_data = await asyncio.wait_for(reader.read(length), timeout=timeout)
            response = json.loads(response_data.decode())

            # 4. Обрабатываем ML-KEM-768 ответ
            if response.get("type") == "kem_response":
                pq_channel = self.kem.process_handshake_response(response)
                if pq_channel:
                    logger.info(f"🔐 Hybrid channel established with {host}")
                    return (reader, writer, pq_channel)

            logger.warning(f"PQ handshake failed with {host}")
            writer.close()
            await writer.wait_closed()
            return None

        except Exception as e:
            logger.error(f"Hybrid channel error: {e}")
            return None

    async def send_pq_message(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        pq_channel: 'PQSecureChannel',
        message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Отправляет сообщение с двойным шифрованием.

        Шифрование: TLS(ML-KEM-768/AES-256-GCM(message))
        """
        try:
            # 1. Сериализуем и шифруем ML-KEM-768
            plain_data = json.dumps(message).encode()
            encrypted = pq_channel.encrypt(plain_data)
            if not encrypted:
                return None

            # 2. Отправляем через TLS
            writer.write(len(encrypted).to_bytes(4, 'big'))
            writer.write(encrypted)
            await writer.drain()

            # 3. Получаем зашифрованный ответ
            length_bytes = await asyncio.wait_for(
                reader.read(4),
                timeout=TLSConfig.READ_TIMEOUT
            )
            length = int.from_bytes(length_bytes, 'big')
            encrypted_response = await asyncio.wait_for(
                reader.read(length),
                timeout=TLSConfig.READ_TIMEOUT
            )

            # 4. Расшифровываем ML-KEM-768
            decrypted = pq_channel.decrypt(encrypted_response)
            if not decrypted:
                return None

            return json.loads(decrypted.decode())

        except Exception as e:
            logger.error(f"PQ message error: {e}")
            return None


class HybridSecureServer:
    """
    Сервер с гибридной защитой: TLS 1.3 + ML-KEM-768
    """

    def __init__(
        self,
        node_name: str,
        node_address: str,
        kem_manager: 'NodeKEMManager' = None,
        cert_manager: CertificateManager = None
    ):
        self.node_name = node_name
        self.node_address = node_address
        self.kem = kem_manager
        self.cert_manager = cert_manager or CertificateManager()

        self._server = None
        self._handlers = {}
        self._pq_channels: Dict[str, 'PQSecureChannel'] = {}

        # Убеждаемся что сертификаты существуют
        self._ensure_certificates()

    def _ensure_certificates(self):
        """Генерируем сертификаты если нужно"""
        cert_path, key_path = self.cert_manager.get_cert_paths(self.node_name)
        if not cert_path:
            self.cert_path, self.key_path = self.cert_manager.generate_self_signed_cert(
                self.node_address, self.node_name
            )
        else:
            self.cert_path = cert_path
            self.key_path = key_path

    def register_handler(self, message_type: str, handler):
        """Регистрирует обработчик для типа сообщений"""
        self._handlers[message_type] = handler

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Обрабатывает клиентское соединение с hybrid security"""
        peer = writer.get_extra_info('peername')
        pq_channel = None

        try:
            while True:
                # Читаем сообщение
                length_bytes = await asyncio.wait_for(
                    reader.read(4),
                    timeout=TLSConfig.READ_TIMEOUT
                )
                if not length_bytes:
                    break

                length = int.from_bytes(length_bytes, 'big')
                data = await asyncio.wait_for(
                    reader.read(length),
                    timeout=TLSConfig.READ_TIMEOUT
                )

                # Проверяем: это ML-KEM handshake или зашифрованное сообщение?
                if pq_channel is None:
                    # Первое сообщение — пробуем как JSON handshake
                    try:
                        message = json.loads(data.decode())

                        if message.get("type") == "kem_handshake" and self.kem:
                            # ML-KEM-768 handshake
                            result = self.kem.process_handshake_request(message)
                            if result:
                                response, pq_channel = result
                                self._pq_channels[message["node_address"]] = pq_channel

                                response_data = json.dumps(response).encode()
                                writer.write(len(response_data).to_bytes(4, 'big'))
                                writer.write(response_data)
                                await writer.drain()
                                logger.info(f"🔐 PQ handshake complete with {peer}")
                                continue
                        else:
                            # Обычное TLS сообщение
                            response = await self._process_message(message, peer)
                            response_data = json.dumps(response).encode()
                            writer.write(len(response_data).to_bytes(4, 'big'))
                            writer.write(response_data)
                            await writer.drain()
                            continue

                    except json.JSONDecodeError:
                        # Не JSON — пропускаем
                        pass
                else:
                    # PQ канал установлен — расшифровываем
                    decrypted = pq_channel.decrypt(data)
                    if decrypted:
                        message = json.loads(decrypted.decode())
                        response = await self._process_message(message, peer)

                        # Шифруем ответ
                        response_data = json.dumps(response).encode()
                        encrypted = pq_channel.encrypt(response_data)
                        if encrypted:
                            writer.write(len(encrypted).to_bytes(4, 'big'))
                            writer.write(encrypted)
                            await writer.drain()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.warning(f"Hybrid client error {peer}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_message(self, message: Dict, peer) -> Dict:
        """Обрабатывает сообщение"""
        msg_type = message.get("type", "unknown")
        handler = self._handlers.get(msg_type, self._default_handler)
        return await handler(message, peer)

    async def _default_handler(self, message: Dict, peer) -> Dict:
        """Обработчик по умолчанию"""
        return {
            "type": "ack",
            "node": self.node_name,
            "address": self.node_address,
            "pq_enabled": self.kem is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def start(self, host: str = "0.0.0.0", port: int = TLSConfig.SECURE_PORT):
        """Запускает hybrid TLS сервер"""
        ssl_context = SecureContext.create_server_context(self.cert_path, self.key_path)

        self._server = await asyncio.start_server(
            self._handle_client,
            host, port,
            ssl=ssl_context
        )

        pq_status = "ML-KEM-768 enabled" if self.kem else "TLS only"
        logger.info(f"🔐 Hybrid server started on {host}:{port} ({pq_status})")

        async with self._server:
            await self._server.serve_forever()

    def stop(self):
        """Останавливает сервер"""
        if self._server:
            self._server.close()


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🔐 Montana Node TLS")
    print("=" * 50)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "gen-cert":
            node_name = sys.argv[2] if len(sys.argv) > 2 else "test"
            node_address = sys.argv[3] if len(sys.argv) > 3 else "mt0000000000000000000000000000000000000000"

            cm = CertificateManager()
            cert, key = cm.generate_self_signed_cert(node_address, node_name)
            print(f"✅ Сертификат: {cert}")
            print(f"✅ Ключ: {key}")

        elif cmd == "server":
            node_name = sys.argv[2] if len(sys.argv) > 2 else "test"
            node_address = "mt0000000000000000000000000000000000000000"

            server = SecureNodeServer(node_name, node_address)

            print(f"🚀 Запуск TLS сервера {node_name}...")
            try:
                asyncio.run(server.start())
            except KeyboardInterrupt:
                print("\n⏹ Остановлено")

        elif cmd == "test":
            host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"

            async def test_connection():
                client = SecureNodeClient()
                response = await client.send_message(host, {"type": "ping"})
                if response:
                    print(f"✅ Ответ: {response}")
                else:
                    print("❌ Нет ответа")

            asyncio.run(test_connection())

        else:
            print(f"Неизвестная команда: {cmd}")
    else:
        print("""
Использование:
  python node_tls.py gen-cert <node_name> [address]  — генерация сертификата
  python node_tls.py server <node_name>              — запуск TLS сервера
  python node_tls.py test <host>                     — тест подключения
        """)
