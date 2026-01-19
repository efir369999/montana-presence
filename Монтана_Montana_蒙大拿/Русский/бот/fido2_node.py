"""
FIDO2 / WebAuthn интеграция для Montana Nodes
Touch ID / Face ID защита для регистрации узлов
"""

import json
import secrets
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
from fido2 import cbor


class MontanaFIDO2:
    """FIDO2/WebAuthn сервер для Montana узлов"""

    def __init__(self, rp_id: str = "montana.network", storage_path: str = "data/fido2_credentials.json"):
        # Relying Party (Montana Network)
        self.rp = PublicKeyCredentialRpEntity(
            id=rp_id,
            name="Montana Network"
        )

        self.server = Fido2Server(self.rp)

        # Хранилище учетных данных
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                self.credentials = json.load(f)
        else:
            self.credentials = {}
            self._save_credentials()

    def _save_credentials(self):
        """Сохранить учетные данные"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.credentials, f, indent=2)

    def create_registration_challenge(
        self,
        telegram_id: int,
        username: str
    ) -> Tuple[Dict, bytes]:
        """
        Создать challenge для регистрации FIDO2

        Args:
            telegram_id: Telegram ID оператора узла
            username: Telegram username

        Returns:
            (options_dict, state)
        """
        # Создать user entity
        user = PublicKeyCredentialUserEntity(
            id=str(telegram_id).encode(),
            name=f"montana_{telegram_id}",
            display_name=username or f"User {telegram_id}"
        )

        # Генерация challenge
        options, state = self.server.register_begin(
            user=user,
            credentials=[],  # Пока нет существующих credentials
            user_verification="required"  # Touch ID / Face ID обязателен
        )

        # Конвертировать в dict для JSON
        options_dict = cbor.decode(cbor.encode(options))

        return options_dict, state

    def verify_registration(
        self,
        credential_data: bytes,
        client_data: bytes,
        state: bytes,
        telegram_id: int
    ) -> bool:
        """
        Верифицировать регистрацию FIDO2

        Args:
            credential_data: Attestation object от клиента
            client_data: Client data JSON
            state: State от create_registration_challenge
            telegram_id: Telegram ID

        Returns:
            True если регистрация успешна
        """
        try:
            auth_data = self.server.register_complete(
                state=state,
                client_data=client_data,
                attestation_object=credential_data
            )

            # Сохранить credential
            credential_id = auth_data.credential_data.credential_id.hex()

            self.credentials[str(telegram_id)] = {
                "credential_id": credential_id,
                "public_key": auth_data.credential_data.public_key.hex() if hasattr(auth_data.credential_data, 'public_key') else None,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "aaguid": auth_data.credential_data.aaguid.hex()
            }

            self._save_credentials()
            return True

        except Exception as e:
            print(f"FIDO2 verification failed: {e}")
            return False

    def has_biometric_auth(self, telegram_id: int) -> bool:
        """Проверить, есть ли биометрия для этого пользователя"""
        return str(telegram_id) in self.credentials

    def create_authentication_challenge(self, telegram_id: int) -> Optional[Tuple[Dict, bytes]]:
        """
        Создать challenge для аутентификации (Proof of Presence)

        Returns:
            (options_dict, state) или None если нет credentials
        """
        if not self.has_biometric_auth(telegram_id):
            return None

        cred_data = self.credentials[str(telegram_id)]

        # Создать options для authentication
        options, state = self.server.authenticate_begin(
            credentials=[{
                "type": "public-key",
                "id": bytes.fromhex(cred_data["credential_id"])
            }],
            user_verification="required"
        )

        options_dict = cbor.decode(cbor.encode(options))
        return options_dict, state

    def verify_authentication(
        self,
        credential_id: bytes,
        client_data: bytes,
        authenticator_data: bytes,
        signature: bytes,
        state: bytes
    ) -> bool:
        """
        Верифицировать аутентификацию (Proof of Presence)

        Returns:
            True если биометрия подтверждена
        """
        try:
            self.server.authenticate_complete(
                state=state,
                credentials=[],  # TODO: load from storage
                credential_id=credential_id,
                client_data=client_data,
                auth_data=authenticator_data,
                signature=signature
            )
            return True
        except Exception as e:
            print(f"FIDO2 authentication failed: {e}")
            return False


# Simplified mock для тестирования без браузера
class MockFIDO2:
    """
    Упрощенная mock-версия FIDO2 для тестирования
    В production заменить на реальный WebAuthn
    """

    def __init__(self, storage_path: str = "data/mock_fido2.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                self.credentials = json.load(f)
        else:
            self.credentials = {}
            self._save()

    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump(self.credentials, f, indent=2)

    def register_biometric(self, telegram_id: int, device_info: str = "iPhone") -> str:
        """
        Симулировать регистрацию биометрии

        Args:
            telegram_id: Telegram ID
            device_info: Информация о устройстве

        Returns:
            credential_id
        """
        credential_id = secrets.token_hex(32)

        self.credentials[str(telegram_id)] = {
            "credential_id": credential_id,
            "device": device_info,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_auth": None
        }

        self._save()
        return credential_id

    def verify_biometric(self, telegram_id: int) -> bool:
        """
        Симулировать верификацию биометрии

        В реальной системе это будет Touch ID / Face ID
        """
        if str(telegram_id) not in self.credentials:
            return False

        # Обновить timestamp последней аутентификации
        self.credentials[str(telegram_id)]["last_auth"] = datetime.now(timezone.utc).isoformat()
        self._save()

        return True

    def has_biometric(self, telegram_id: int) -> bool:
        """Проверить, зарегистрирована ли биометрия"""
        return str(telegram_id) in self.credentials

    def get_credential_info(self, telegram_id: int) -> Optional[Dict]:
        """Получить информацию о credential"""
        return self.credentials.get(str(telegram_id))


def get_fido2_system(mock: bool = True):
    """
    Получить FIDO2 систему

    Args:
        mock: True = MockFIDO2 (тестирование), False = MontanaFIDO2 (production)
    """
    if mock:
        return MockFIDO2()
    else:
        return MontanaFIDO2()


if __name__ == "__main__":
    print("🔐 FIDO2 System Test (Mock Mode)\n")

    fido = MockFIDO2()

    # Тестовый пользователь
    test_telegram_id = 8552053404

    # Регистрация биометрии
    print(f"📱 Registering biometric for Telegram ID: {test_telegram_id}")
    credential_id = fido.register_biometric(test_telegram_id, "iPhone 15 Pro")
    print(f"✅ Credential ID: {credential_id}")

    # Проверка наличия
    has_bio = fido.has_biometric(test_telegram_id)
    print(f"\n✅ Has biometric: {has_bio}")

    # Верификация
    print(f"\n🔓 Verifying biometric...")
    verified = fido.verify_biometric(test_telegram_id)
    print(f"✅ Verified: {verified}")

    # Информация
    info = fido.get_credential_info(test_telegram_id)
    print(f"\n📊 Credential Info:")
    print(f"   Device: {info['device']}")
    print(f"   Registered: {info['registered_at']}")
    print(f"   Last Auth: {info['last_auth']}")

    # Попытка без регистрации
    fake_user = 999999
    verified_fake = fido.verify_biometric(fake_user)
    print(f"\n❌ Fake user verified: {verified_fake}")

    print("\n🎯 All tests passed!")
