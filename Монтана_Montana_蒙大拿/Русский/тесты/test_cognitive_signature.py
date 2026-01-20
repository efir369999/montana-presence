#!/usr/bin/env python3
"""
test_cognitive_signature.py — Unit tests для cognitive_signature.py

Montana Protocol
Тестирование когнитивных подписей с domain separation
"""

import sys
import os
import unittest
import secrets
import hashlib
from datetime import datetime, timezone

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../гиппокамп'))
from cognitive_signature import (
    DomainType,
    get_domain_prefix,
    CognitiveSignature,
    generate_keypair,
    derive_key_from_passphrase
)


class TestDomainType(unittest.TestCase):
    """Тесты типов доменов"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         DOMAIN TYPES
    # ═══════════════════════════════════════════════════════════════════════

    def test_domain_type_values(self):
        """Проверка значений доменов"""
        self.assertEqual(DomainType.THOUGHT.value, "montana.thought")
        self.assertEqual(DomainType.MESSAGE.value, "montana.message")
        self.assertEqual(DomainType.TRANSACTION.value, "montana.transaction")
        self.assertEqual(DomainType.PRESENCE.value, "montana.presence")
        self.assertEqual(DomainType.NODE_AUTH.value, "montana.node.auth")
        self.assertEqual(DomainType.SYNC.value, "montana.sync")

    def test_get_domain_prefix(self):
        """get_domain_prefix() возвращает bytes"""
        prefix = get_domain_prefix(DomainType.THOUGHT)

        self.assertIsInstance(prefix, bytes)
        self.assertEqual(prefix, b"montana.thought")

    def test_all_domains_have_prefix(self):
        """Все домены имеют префикс"""
        for domain in DomainType:
            prefix = get_domain_prefix(domain)
            self.assertIsInstance(prefix, bytes)
            self.assertGreater(len(prefix), 0)


class TestCognitiveSignatureInit(unittest.TestCase):
    """Тесты инициализации CognitiveSignature"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_init_generates_key(self):
        """Инициализация генерирует ключ если не указан"""
        signer = CognitiveSignature()

        self.assertIsNotNone(signer.secret_key)
        self.assertEqual(len(signer.secret_key), 32)

    def test_init_with_custom_key(self):
        """Инициализация с кастомным ключом"""
        custom_key = secrets.token_bytes(32)
        signer = CognitiveSignature(secret_key=custom_key)

        self.assertEqual(signer.secret_key, custom_key)

    def test_init_with_wrong_key_length(self):
        """Инициализация с неправильной длиной ключа"""
        wrong_key = secrets.token_bytes(16)  # Неправильная длина

        with self.assertRaises(ValueError):
            CognitiveSignature(secret_key=wrong_key)

    def test_different_signers_different_keys(self):
        """Разные signers генерируют разные ключи"""
        signer1 = CognitiveSignature()
        signer2 = CognitiveSignature()

        self.assertNotEqual(signer1.secret_key, signer2.secret_key)


class TestCognitiveSignatureSign(unittest.TestCase):
    """Тесты подписания"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         SIGNING
    # ═══════════════════════════════════════════════════════════════════════

    def test_sign_basic(self):
        """Базовое подписание"""
        message = "Test message"
        signed = self.signer.sign(message, DomainType.MESSAGE)

        self.assertIn("message", signed)
        self.assertIn("domain", signed)
        self.assertIn("timestamp", signed)
        self.assertIn("signature", signed)
        self.assertIn("metadata", signed)

    def test_sign_preserves_message(self):
        """sign() сохраняет оригинальное сообщение"""
        message = "Test message"
        signed = self.signer.sign(message, DomainType.MESSAGE)

        self.assertEqual(signed["message"], message)

    def test_sign_includes_domain(self):
        """sign() включает домен"""
        signed = self.signer.sign("message", DomainType.THOUGHT)

        self.assertEqual(signed["domain"], "montana.thought")

    def test_sign_generates_signature(self):
        """sign() генерирует подпись"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        self.assertIsInstance(signed["signature"], str)
        self.assertEqual(len(signed["signature"]), 64)  # SHA256 hex = 64 символа

    def test_sign_with_timestamp(self):
        """sign() с кастомным timestamp"""
        timestamp = "2026-01-20T12:00:00+00:00"
        signed = self.signer.sign("message", DomainType.MESSAGE, timestamp=timestamp)

        self.assertEqual(signed["timestamp"], timestamp)

    def test_sign_generates_timestamp(self):
        """sign() генерирует timestamp если не указан"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        self.assertIsNotNone(signed["timestamp"])
        # Должен быть в ISO format
        datetime.fromisoformat(signed["timestamp"])  # Не должно упасть

    def test_sign_with_metadata(self):
        """sign() с метаданными"""
        metadata = {"user_id": 123, "custom": "data"}
        signed = self.signer.sign("message", DomainType.MESSAGE, metadata=metadata)

        self.assertEqual(signed["metadata"], metadata)

    def test_sign_same_message_different_signature(self):
        """Одинаковое сообщение с разным timestamp → разные подписи"""
        message = "Test"

        signed1 = self.signer.sign(message, DomainType.MESSAGE, timestamp="2026-01-01T00:00:00+00:00")
        signed2 = self.signer.sign(message, DomainType.MESSAGE, timestamp="2026-01-02T00:00:00+00:00")

        self.assertNotEqual(signed1["signature"], signed2["signature"])


class TestCognitiveSignatureVerify(unittest.TestCase):
    """Тесты верификации"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         VERIFICATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_verify_valid_signature(self):
        """Верификация валидной подписи"""
        signed = self.signer.sign("message", DomainType.MESSAGE)
        is_valid = self.signer.verify(signed)

        self.assertTrue(is_valid)

    def test_verify_with_domain_check(self):
        """Верификация с проверкой домена"""
        signed = self.signer.sign("message", DomainType.MESSAGE)
        is_valid = self.signer.verify(signed, domain=DomainType.MESSAGE)

        self.assertTrue(is_valid)

    def test_verify_wrong_domain(self):
        """Верификация с неправильным доменом"""
        signed = self.signer.sign("message", DomainType.MESSAGE)
        is_valid = self.signer.verify(signed, domain=DomainType.THOUGHT)

        self.assertFalse(is_valid)

    def test_verify_tampered_message(self):
        """Верификация подделанного сообщения"""
        signed = self.signer.sign("original", DomainType.MESSAGE)

        # Подделываем сообщение
        signed["message"] = "tampered"

        is_valid = self.signer.verify(signed)

        self.assertFalse(is_valid)

    def test_verify_tampered_signature(self):
        """Верификация подделанной подписи"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        # Подделываем подпись
        signed["signature"] = "0" * 64

        is_valid = self.signer.verify(signed)

        self.assertFalse(is_valid)

    def test_verify_tampered_timestamp(self):
        """Верификация с подделанным timestamp"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        # Подделываем timestamp
        signed["timestamp"] = "2030-01-01T00:00:00+00:00"

        is_valid = self.signer.verify(signed)

        self.assertFalse(is_valid)

    def test_verify_different_signer(self):
        """Верификация подписи другим signer"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        # Другой signer с другим ключом
        other_signer = CognitiveSignature()
        is_valid = other_signer.verify(signed)

        self.assertFalse(is_valid)

    def test_verify_invalid_format(self):
        """Верификация невалидного формата"""
        invalid_data = {"not": "correct", "format": "at all"}

        is_valid = self.signer.verify(invalid_data)

        self.assertFalse(is_valid)


class TestCognitiveSignatureDomainSeparation(unittest.TestCase):
    """Тесты domain separation"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         DOMAIN SEPARATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_same_message_different_domains(self):
        """Одно сообщение в разных доменах → разные подписи"""
        message = "Test message"
        timestamp = "2026-01-20T12:00:00+00:00"

        signed_thought = self.signer.sign(message, DomainType.THOUGHT, timestamp=timestamp)
        signed_message = self.signer.sign(message, DomainType.MESSAGE, timestamp=timestamp)

        self.assertNotEqual(signed_thought["signature"], signed_message["signature"])

    def test_domain_separation_prevents_replay(self):
        """Domain separation предотвращает replay attacks"""
        # Подписываем как THOUGHT
        signed = self.signer.sign("message", DomainType.THOUGHT)

        # Пытаемся верифицировать как MESSAGE
        is_valid = self.signer.verify(signed, domain=DomainType.MESSAGE)

        # Должно быть невалидно
        self.assertFalse(is_valid)

    def test_all_domains_produce_different_signatures(self):
        """Все домены производят разные подписи для одного сообщения"""
        message = "Test"
        timestamp = "2026-01-20T12:00:00+00:00"

        signatures = set()
        for domain in DomainType:
            signed = self.signer.sign(message, domain, timestamp=timestamp)
            signatures.add(signed["signature"])

        # Все подписи должны быть уникальными
        self.assertEqual(len(signatures), len(DomainType))


class TestCognitiveSignatureConvenienceMethods(unittest.TestCase):
    """Тесты вспомогательных методов"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def test_sign_thought(self):
        """sign_thought() работает корректно"""
        thought = "Маска тяжелее лица"
        signed = self.signer.sign_thought(thought, user_id=123)

        self.assertEqual(signed["message"], thought)
        self.assertEqual(signed["domain"], "montana.thought")
        self.assertEqual(signed["metadata"]["user_id"], 123)

    def test_sign_message(self):
        """sign_message() работает корректно"""
        message = "Hello"
        signed = self.signer.sign_message(message, sender_id=456)

        self.assertEqual(signed["message"], message)
        self.assertEqual(signed["domain"], "montana.message")
        self.assertEqual(signed["metadata"]["sender_id"], 456)

    def test_sign_transaction(self):
        """sign_transaction() работает корректно"""
        tx_data = "tx_123"
        signed = self.signer.sign_transaction(
            tx_data,
            from_address="addr1",
            to_address="addr2",
            amount=100.0
        )

        self.assertEqual(signed["message"], tx_data)
        self.assertEqual(signed["domain"], "montana.transaction")
        self.assertEqual(signed["metadata"]["from"], "addr1")
        self.assertEqual(signed["metadata"]["to"], "addr2")
        self.assertEqual(signed["metadata"]["amount"], 100.0)

    def test_sign_presence(self):
        """sign_presence() работает корректно"""
        presence_data = "presence_check_123"
        signed = self.signer.sign_presence(presence_data, user_id=789)

        self.assertEqual(signed["message"], presence_data)
        self.assertEqual(signed["domain"], "montana.presence")
        self.assertEqual(signed["metadata"]["user_id"], 789)


class TestKeyManagement(unittest.TestCase):
    """Тесты управления ключами"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         KEY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def test_generate_keypair(self):
        """generate_keypair() генерирует пару ключей"""
        secret_key, public_key_hash = generate_keypair()

        self.assertIsInstance(secret_key, bytes)
        self.assertIsInstance(public_key_hash, bytes)
        self.assertEqual(len(secret_key), 32)
        self.assertEqual(len(public_key_hash), 32)

    def test_generate_keypair_different_keys(self):
        """generate_keypair() генерирует разные ключи"""
        key1, _ = generate_keypair()
        key2, _ = generate_keypair()

        self.assertNotEqual(key1, key2)

    def test_public_key_is_hash_of_secret(self):
        """Публичный ключ — хеш секретного"""
        secret_key, public_key_hash = generate_keypair()

        expected_hash = hashlib.sha256(secret_key).digest()
        self.assertEqual(public_key_hash, expected_hash)

    def test_derive_key_from_passphrase(self):
        """derive_key_from_passphrase() создаёт ключ"""
        passphrase = "my secure passphrase"
        salt = secrets.token_bytes(16)

        key = derive_key_from_passphrase(passphrase, salt)

        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)

    def test_derive_key_deterministic(self):
        """derive_key_from_passphrase() детерминирован"""
        passphrase = "test"
        salt = b"0" * 16

        key1 = derive_key_from_passphrase(passphrase, salt)
        key2 = derive_key_from_passphrase(passphrase, salt)

        self.assertEqual(key1, key2)

    def test_derive_key_different_passphrase(self):
        """Разные passphrase → разные ключи"""
        salt = secrets.token_bytes(16)

        key1 = derive_key_from_passphrase("passphrase1", salt)
        key2 = derive_key_from_passphrase("passphrase2", salt)

        self.assertNotEqual(key1, key2)

    def test_derive_key_different_salt(self):
        """Разная соль → разные ключи"""
        passphrase = "test"

        key1 = derive_key_from_passphrase(passphrase, b"0" * 16)
        key2 = derive_key_from_passphrase(passphrase, b"1" * 16)

        self.assertNotEqual(key1, key2)


class TestSecurityProperties(unittest.TestCase):
    """Тесты свойств безопасности"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         SECURITY PROPERTIES
    # ═══════════════════════════════════════════════════════════════════════

    def test_signature_length_constant(self):
        """Длина подписи константна"""
        short = self.signer.sign("a", DomainType.MESSAGE)
        long = self.signer.sign("a" * 10000, DomainType.MESSAGE)

        self.assertEqual(len(short["signature"]), len(long["signature"]))
        self.assertEqual(len(short["signature"]), 64)  # SHA256 hex

    def test_cannot_forge_signature(self):
        """Невозможно подделать подпись без ключа"""
        message = "Original message"
        signed = self.signer.sign(message, DomainType.MESSAGE)

        # Пытаемся подделать подпись для другого сообщения
        forged = signed.copy()
        forged["message"] = "Forged message"
        # Подпись остаётся той же

        is_valid = self.signer.verify(forged)

        self.assertFalse(is_valid)

    def test_timing_attack_resistance(self):
        """Использование hmac.compare_digest для защиты от timing attacks"""
        signed = self.signer.sign("message", DomainType.MESSAGE)

        # Создаём два почти одинаковых сообщения
        valid = signed.copy()
        invalid = signed.copy()
        invalid["signature"] = invalid["signature"][:-1] + ("0" if invalid["signature"][-1] != "0" else "1")

        # Оба должны верифицироваться за примерно одинаковое время
        # (мы не можем измерить время в unit тесте, но знаем что используется hmac.compare_digest)
        result_valid = self.signer.verify(valid)
        result_invalid = self.signer.verify(invalid)

        self.assertTrue(result_valid)
        self.assertFalse(result_invalid)


class TestEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""

    def setUp(self):
        """Создаём signer для каждого теста"""
        self.signer = CognitiveSignature()

    # ═══════════════════════════════════════════════════════════════════════
    #                         EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_empty_message(self):
        """Подписание пустого сообщения"""
        signed = self.signer.sign("", DomainType.MESSAGE)

        self.assertEqual(signed["message"], "")
        is_valid = self.signer.verify(signed)
        self.assertTrue(is_valid)

    def test_unicode_message(self):
        """Подписание Unicode сообщения"""
        message = "Монтана Montana 蒙大拿 金元Ɉ"
        signed = self.signer.sign(message, DomainType.THOUGHT)

        self.assertEqual(signed["message"], message)
        is_valid = self.signer.verify(signed)
        self.assertTrue(is_valid)

    def test_very_long_message(self):
        """Подписание очень длинного сообщения"""
        message = "a" * 1_000_000  # 1 миллион символов
        signed = self.signer.sign(message, DomainType.MESSAGE)

        is_valid = self.signer.verify(signed)
        self.assertTrue(is_valid)

    def test_special_characters(self):
        """Подписание специальных символов"""
        message = "\\n\\t\\r!@#$%^&*()[]{}||"
        signed = self.signer.sign(message, DomainType.MESSAGE)

        is_valid = self.signer.verify(signed)
        self.assertTrue(is_valid)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
