#!/usr/bin/env python3
"""
cognitive_signature.py — Когнитивные подписи Montana

Montana Protocol
Подписание мыслей и сообщений с domain separation
"""

import hashlib
import hmac
import secrets
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
#                         DOMAIN SEPARATION
# ═══════════════════════════════════════════════════════════════════════════

class DomainType(Enum):
    """
    Типы доменов для domain separation

    Domain separation гарантирует что подпись для одного контекста
    не может быть переиспользована в другом
    """

    THOUGHT = "montana.thought"              # Сырая мысль
    MESSAGE = "montana.message"              # Обычное сообщение
    TRANSACTION = "montana.transaction"      # Транзакция
    PRESENCE = "montana.presence"            # Proof of Presence
    NODE_AUTH = "montana.node.auth"          # Аутентификация узла
    SYNC = "montana.sync"                    # Синхронизация данных


def get_domain_prefix(domain: DomainType) -> bytes:
    """
    Получить префикс домена для domain separation

    Args:
        domain: Тип домена

    Returns:
        Префикс в байтах

    Example:
        >>> get_domain_prefix(DomainType.THOUGHT)
        b'montana.thought'
    """
    return domain.value.encode('utf-8')


# ═══════════════════════════════════════════════════════════════════════════
#                         COGNITIVE SIGNATURE
# ═══════════════════════════════════════════════════════════════════════════

class CognitiveSignature:
    """
    Когнитивная подпись Montana

    Использует HMAC-SHA256 с domain separation для подписания
    мыслей, сообщений и других данных
    """

    def __init__(self, secret_key: Optional[bytes] = None):
        """
        Args:
            secret_key: Секретный ключ (32 байта).
                       Если не указан, генерируется случайно.
        """
        if secret_key is None:
            self.secret_key = secrets.token_bytes(32)
        else:
            if len(secret_key) != 32:
                raise ValueError("Secret key must be exactly 32 bytes")
            self.secret_key = secret_key

    def sign(
        self,
        message: str,
        domain: DomainType,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Подписать сообщение

        Args:
            message: Текст сообщения
            domain: Домен для domain separation
            timestamp: Timestamp в ISO format (UTC)
            metadata: Дополнительные метаданные

        Returns:
            {
                "message": "текст",
                "domain": "montana.thought",
                "timestamp": "2026-01-20T12:00:00+00:00",
                "signature": "hex...",
                "metadata": {}
            }
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        # Собираем данные для подписи
        domain_prefix = get_domain_prefix(domain)
        message_bytes = message.encode('utf-8')
        timestamp_bytes = timestamp.encode('utf-8')

        # Формат: domain || timestamp || message
        data_to_sign = domain_prefix + b'||' + timestamp_bytes + b'||' + message_bytes

        # Подписываем с HMAC-SHA256
        signature = hmac.new(
            self.secret_key,
            data_to_sign,
            hashlib.sha256
        ).hexdigest()

        return {
            "message": message,
            "domain": domain.value,
            "timestamp": timestamp,
            "signature": signature,
            "metadata": metadata or {}
        }

    def verify(
        self,
        signed_data: Dict,
        domain: Optional[DomainType] = None
    ) -> bool:
        """
        Верифицировать подпись

        Args:
            signed_data: Подписанные данные (результат sign())
            domain: Ожидаемый домен (опционально)

        Returns:
            True если подпись валидна
        """
        try:
            message = signed_data["message"]
            domain_str = signed_data["domain"]
            timestamp = signed_data["timestamp"]
            signature = signed_data["signature"]

            # Проверяем домен если указан
            if domain:
                if domain_str != domain.value:
                    return False

            # Восстанавливаем domain enum
            domain_enum = DomainType(domain_str)

            # Пересобираем данные
            domain_prefix = get_domain_prefix(domain_enum)
            message_bytes = message.encode('utf-8')
            timestamp_bytes = timestamp.encode('utf-8')

            data_to_sign = domain_prefix + b'||' + timestamp_bytes + b'||' + message_bytes

            # Вычисляем ожидаемую подпись
            expected_signature = hmac.new(
                self.secret_key,
                data_to_sign,
                hashlib.sha256
            ).hexdigest()

            # Сравниваем
            return hmac.compare_digest(signature, expected_signature)

        except (KeyError, ValueError):
            return False

    def sign_thought(self, thought: str, user_id: Optional[int] = None) -> Dict:
        """
        Подписать сырую мысль

        Args:
            thought: Текст мысли
            user_id: ID пользователя

        Returns:
            Подписанная мысль
        """
        metadata = {}
        if user_id:
            metadata["user_id"] = user_id

        return self.sign(
            message=thought,
            domain=DomainType.THOUGHT,
            metadata=metadata
        )

    def sign_message(self, message: str, sender_id: Optional[int] = None) -> Dict:
        """
        Подписать обычное сообщение

        Args:
            message: Текст сообщения
            sender_id: ID отправителя

        Returns:
            Подписанное сообщение
        """
        metadata = {}
        if sender_id:
            metadata["sender_id"] = sender_id

        return self.sign(
            message=message,
            domain=DomainType.MESSAGE,
            metadata=metadata
        )

    def sign_transaction(
        self,
        transaction_data: str,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        amount: Optional[float] = None
    ) -> Dict:
        """
        Подписать транзакцию

        Args:
            transaction_data: Данные транзакции
            from_address: Адрес отправителя
            to_address: Адрес получателя
            amount: Сумма

        Returns:
            Подписанная транзакция
        """
        metadata = {}
        if from_address:
            metadata["from"] = from_address
        if to_address:
            metadata["to"] = to_address
        if amount:
            metadata["amount"] = amount

        return self.sign(
            message=transaction_data,
            domain=DomainType.TRANSACTION,
            metadata=metadata
        )

    def sign_presence(self, presence_data: str, user_id: Optional[int] = None) -> Dict:
        """
        Подписать proof of presence

        Args:
            presence_data: Данные присутствия
            user_id: ID пользователя

        Returns:
            Подписанное proof of presence
        """
        metadata = {}
        if user_id:
            metadata["user_id"] = user_id

        return self.sign(
            message=presence_data,
            domain=DomainType.PRESENCE,
            metadata=metadata
        )


# ═══════════════════════════════════════════════════════════════════════════
#                         KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def generate_keypair() -> Tuple[bytes, bytes]:
    """
    Сгенерировать пару ключей (secret, public)

    В текущей реализации используется симметричный ключ (HMAC),
    поэтому "публичный" ключ — это хеш секретного ключа

    Returns:
        (secret_key, public_key_hash)
    """
    secret_key = secrets.token_bytes(32)

    # "Публичный" ключ — хеш секретного
    public_key_hash = hashlib.sha256(secret_key).digest()

    return (secret_key, public_key_hash)


def derive_key_from_passphrase(passphrase: str, salt: Optional[bytes] = None) -> bytes:
    """
    Получить ключ из парольной фразы

    Args:
        passphrase: Парольная фраза
        salt: Соль (16 байт, если не указана — генерируется)

    Returns:
        32-байтовый ключ
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    # PBKDF2 с SHA256
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        100_000  # итераций
    )

    return key


# ═══════════════════════════════════════════════════════════════════════════
#                         EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'DomainType',
    'get_domain_prefix',
    'CognitiveSignature',
    'generate_keypair',
    'derive_key_from_passphrase'
]


# ═══════════════════════════════════════════════════════════════════════════
#                         CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧠 Montana Cognitive Signature")
    print("=" * 60)

    # Генерируем ключ
    print("\n🔑 Генерация ключей:")
    secret_key, public_key_hash = generate_keypair()
    print(f"   Secret key (hex): {secret_key.hex()[:32]}...")
    print(f"   Public key hash (hex): {public_key_hash.hex()[:32]}...")

    # Создаём signer
    signer = CognitiveSignature(secret_key)

    # Подписываем мысль
    print("\n💭 Подписание мысли:")
    thought = "Маска тяжелее лица"
    signed_thought = signer.sign_thought(thought, user_id=123)
    print(f"   Мысль: {signed_thought['message']}")
    print(f"   Домен: {signed_thought['domain']}")
    print(f"   Timestamp: {signed_thought['timestamp']}")
    print(f"   Подпись: {signed_thought['signature'][:32]}...")

    # Верификация
    print("\n✅ Верификация:")
    is_valid = signer.verify(signed_thought, domain=DomainType.THOUGHT)
    print(f"   Подпись валидна: {is_valid}")

    # Подделка подписи
    print("\n❌ Попытка подделки:")
    forged = signed_thought.copy()
    forged["message"] = "Поддельная мысль"
    is_valid_forged = signer.verify(forged, domain=DomainType.THOUGHT)
    print(f"   Поддельная подпись валидна: {is_valid_forged}")

    # Domain separation
    print("\n🔒 Domain separation:")
    print("   Пытаемся верифицировать мысль как сообщение...")
    is_valid_wrong_domain = signer.verify(signed_thought, domain=DomainType.MESSAGE)
    print(f"   Подпись валидна в другом домене: {is_valid_wrong_domain}")

    print("\n🎯 Когнитивные подписи готовы!")
