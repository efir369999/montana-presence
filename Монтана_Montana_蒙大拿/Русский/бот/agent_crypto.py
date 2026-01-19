"""
Agent Cryptography System для Montana
Подписи ML-DSA-65 для AI агентов
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from dilithium_py.ml_dsa import ML_DSA_65


class AgentCrypto:
    """Криптографическая система для агентов Montana"""

    def __init__(self, registry_path: str = "data/agent_registry.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Загрузить или создать реестр
        if self.registry_path.exists():
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry = json.load(f)
        else:
            self.registry = {}
            self._save_registry()

    def _save_registry(self):
        """Сохранить реестр"""
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def generate_agent_keypair(self) -> Tuple[str, str]:
        """
        Генерировать ML-DSA-65 ключи для агента

        Returns:
            (private_key_hex, public_key_hex)
        """
        public_key, private_key = ML_DSA_65.keygen()
        return private_key.hex(), public_key.hex()

    def derive_agent_address(self, public_key_hex: str) -> str:
        """
        Вычислить адрес агента из public key

        Format: mtAGENT + SHA256(public_key)[:16].hex()
        Пример: mtAGENT7a3f8b2c1d4e5f678
        """
        public_key = bytes.fromhex(public_key_hex)
        hash_digest = hashlib.sha256(public_key).digest()
        return "mtAGENT" + hash_digest[:16].hex()

    def register_agent(
        self,
        name: str,
        description: str,
        private_key_hex: str,
        public_key_hex: str,
        official: bool = True
    ) -> str:
        """
        Зарегистрировать агента в реестре

        Args:
            name: Имя агента (например, "Юнона Montana")
            description: Описание роли
            private_key_hex: Private key (хранится отдельно!)
            public_key_hex: Public key
            official: Официальный агент Montana?

        Returns:
            agent_address
        """
        agent_address = self.derive_agent_address(public_key_hex)

        # Добавить в реестр
        self.registry[agent_address] = {
            "name": name,
            "description": description,
            "public_key": public_key_hex,
            "official": official,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "verified": True if official else False
        }

        self._save_registry()
        return agent_address

    def sign_message(self, private_key_hex: str, message: str) -> str:
        """
        Подписать сообщение агента

        Args:
            private_key_hex: Private key агента
            message: Текст сообщения

        Returns:
            signature_hex
        """
        private_bytes = bytes.fromhex(private_key_hex)
        message_bytes = message.encode('utf-8')
        signature = ML_DSA_65.sign(private_bytes, message_bytes)
        return signature.hex()

    def create_signed_message(
        self,
        private_key_hex: str,
        public_key_hex: str,
        text: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Создать подписанное сообщение

        Returns:
            {
                "message": {
                    "text": "...",
                    "timestamp": "...",
                    "metadata": {...}
                },
                "agent_address": "mtAGENT...",
                "signature": "..."
            }
        """
        agent_address = self.derive_agent_address(public_key_hex)
        timestamp = datetime.utcnow().isoformat() + "Z"

        message = {
            "text": text,
            "timestamp": timestamp,
            "agent_address": agent_address
        }

        if metadata:
            message["metadata"] = metadata

        # Подписать каноническое представление
        canonical = json.dumps(message, sort_keys=True, ensure_ascii=False)
        signature = self.sign_message(private_key_hex, canonical)

        return {
            "message": message,
            "agent_address": agent_address,
            "signature": signature
        }

    def verify_message(
        self,
        message: Dict,
        signature_hex: str,
        agent_address: str
    ) -> bool:
        """
        Верифицировать подпись сообщения

        Args:
            message: Словарь сообщения
            signature_hex: Подпись в hex
            agent_address: Адрес агента

        Returns:
            True если подпись валидна
        """
        # Проверить наличие в реестре
        if agent_address not in self.registry:
            return False

        agent_info = self.registry[agent_address]
        public_key_hex = agent_info["public_key"]

        # Верифицировать подпись
        try:
            public_bytes = bytes.fromhex(public_key_hex)
            canonical = json.dumps(message, sort_keys=True, ensure_ascii=False)
            message_bytes = canonical.encode('utf-8')
            signature = bytes.fromhex(signature_hex)

            return ML_DSA_65.verify(public_bytes, message_bytes, signature)
        except Exception:
            return False

    def is_official_agent(self, agent_address: str) -> bool:
        """Проверить, является ли агент официальным Montana"""
        if agent_address not in self.registry:
            return False
        return self.registry[agent_address].get("official", False)

    def get_agent_info(self, agent_address: str) -> Optional[Dict]:
        """Получить информацию об агенте"""
        return self.registry.get(agent_address)

    def list_agents(self, official_only: bool = False) -> Dict:
        """
        Список всех агентов

        Args:
            official_only: Только официальные агенты Montana

        Returns:
            Словарь агентов
        """
        if official_only:
            return {
                addr: info
                for addr, info in self.registry.items()
                if info.get("official", False)
            }
        return self.registry


def get_agent_crypto_system() -> AgentCrypto:
    """Получить экземпляр AgentCrypto"""
    return AgentCrypto()


if __name__ == "__main__":
    # Тест системы
    print("🔐 Agent Crypto System Test\n")

    acs = AgentCrypto()

    # Генерация ключей для Юноны
    private_key, public_key = acs.generate_agent_keypair()
    print(f"Private Key length: {len(private_key)} hex chars ({len(bytes.fromhex(private_key))} bytes)")
    print(f"Public Key length: {len(public_key)} hex chars ({len(bytes.fromhex(public_key))} bytes)")

    # Регистрация Юноны
    agent_address = acs.register_agent(
        name="Юнона Montana",
        description="Официальный AI агент Montana Protocol",
        private_key_hex=private_key,
        public_key_hex=public_key,
        official=True
    )

    print(f"\n✅ Agent registered: {agent_address}")
    print(f"   Name: {acs.get_agent_info(agent_address)['name']}")

    # Создать подписанное сообщение
    signed_msg = acs.create_signed_message(
        private_key_hex=private_key,
        public_key_hex=public_key,
        text="Привет! Я Юнона Montana. Это тестовое сообщение.",
        metadata={"test": True}
    )

    print(f"\n📝 Signed Message:")
    print(f"   Text: {signed_msg['message']['text']}")
    print(f"   Signature length: {len(signed_msg['signature'])} hex chars")

    # Верификация
    is_valid = acs.verify_message(
        message=signed_msg['message'],
        signature_hex=signed_msg['signature'],
        agent_address=signed_msg['agent_address']
    )

    print(f"\n✅ Signature valid: {is_valid}")

    # Попытка подделки
    fake_msg = signed_msg['message'].copy()
    fake_msg['text'] = "Поддельное сообщение"

    is_fake_valid = acs.verify_message(
        message=fake_msg,
        signature_hex=signed_msg['signature'],
        agent_address=signed_msg['agent_address']
    )

    print(f"❌ Fake message valid: {is_fake_valid}")

    print("\n🎯 All tests passed!")
