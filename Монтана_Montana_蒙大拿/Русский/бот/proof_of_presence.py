"""
Proof of Presence для Montana
Случайные проверки Face ID / Touch ID каждые ~40 минут
"""

import json
import random
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
import logging

from fido2_node import MockFIDO2

logger = logging.getLogger(__name__)


class ProofOfPresenceManager:
    """
    Управление Proof of Presence проверками

    Юнона запрашивает Face ID / Touch ID в случайном порядке
    для подтверждения присутствия реального человека
    """

    def __init__(
        self,
        storage_path: str = "data/proof_of_presence.json",
        base_interval_minutes: int = 40,
        randomness_minutes: int = 10
    ):
        """
        Args:
            storage_path: Путь к файлу с данными проверок
            base_interval_minutes: Базовый интервал (например, 40 минут)
            randomness_minutes: Случайность ±N минут (например, ±10 = 30-50 минут)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.base_interval = base_interval_minutes
        self.randomness = randomness_minutes

        # Загрузить данные
        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "users": {},
                "checks": []
            }
            self._save()

        self.fido = MockFIDO2()

    def _save(self):
        """Сохранить данные"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _get_next_check_time(self) -> datetime:
        """
        Вычислить следующее время проверки (случайное)

        Returns:
            datetime в UTC
        """
        # Базовый интервал ± randomness
        minutes = self.base_interval + random.randint(-self.randomness, self.randomness)
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def register_user(self, telegram_id: int, username: str):
        """
        Зарегистрировать пользователя для Proof of Presence

        Args:
            telegram_id: Telegram ID
            username: Telegram username
        """
        user_key = str(telegram_id)

        if user_key not in self.data["users"]:
            self.data["users"][user_key] = {
                "telegram_id": telegram_id,
                "username": username,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "last_check": None,
                "next_check": self._get_next_check_time().isoformat(),
                "checks_completed": 0,
                "checks_failed": 0,
                "status": "active"
            }
            self._save()

            logger.info(f"User {telegram_id} registered for PoP")

    def is_check_due(self, telegram_id: int) -> bool:
        """
        Проверить, нужна ли проверка для пользователя

        Returns:
            True если время проверки пришло
        """
        user_key = str(telegram_id)

        if user_key not in self.data["users"]:
            return False

        user = self.data["users"][user_key]

        if user["status"] != "active":
            return False

        next_check_str = user.get("next_check")
        if not next_check_str:
            return False

        next_check = datetime.fromisoformat(next_check_str)
        now = datetime.now(timezone.utc)

        return now >= next_check

    def request_check(self, telegram_id: int) -> Dict:
        """
        Запросить проверку присутствия

        Returns:
            {
                "check_id": "...",
                "telegram_id": 123,
                "requested_at": "...",
                "expires_at": "...",
                "message": "Юнона запрашивает подтверждение присутствия..."
            }
        """
        user_key = str(telegram_id)

        if user_key not in self.data["users"]:
            raise ValueError(f"User {telegram_id} not registered for PoP")

        # Создать check
        check_id = f"pop_{telegram_id}_{int(datetime.now(timezone.utc).timestamp())}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=5)  # 5 минут на подтверждение

        check = {
            "check_id": check_id,
            "telegram_id": telegram_id,
            "requested_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "completed": False,
            "verified": False
        }

        self.data["checks"].append(check)
        self._save()

        logger.info(f"PoP check requested for user {telegram_id}: {check_id}")

        return {
            "check_id": check_id,
            "telegram_id": telegram_id,
            "requested_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "message": (
                "🏔 Юнона Montana запрашивает подтверждение присутствия.\n\n"
                f"⏰ Время на подтверждение: 5 минут\n"
                f"📱 Используй Touch ID / Face ID\n\n"
                f"Команда: /verify_presence {check_id}"
            )
        }

    def verify_check(self, telegram_id: int, check_id: str) -> bool:
        """
        Верифицировать проверку присутствия

        Args:
            telegram_id: Telegram ID
            check_id: ID проверки

        Returns:
            True если верификация успешна
        """
        user_key = str(telegram_id)

        # Найти check
        check = None
        for c in self.data["checks"]:
            if c["check_id"] == check_id and c["telegram_id"] == telegram_id:
                check = c
                break

        if not check:
            logger.warning(f"Check {check_id} not found for user {telegram_id}")
            return False

        # Проверить не истёк ли срок
        expires_at = datetime.fromisoformat(check["expires_at"])
        now = datetime.now(timezone.utc)

        if now > expires_at:
            logger.warning(f"Check {check_id} expired")
            check["completed"] = True
            check["verified"] = False
            self.data["users"][user_key]["checks_failed"] += 1
            self._save()
            return False

        # Верифицировать через FIDO2
        verified = self.fido.verify_biometric(telegram_id)

        if verified:
            # Успешная верификация
            check["completed"] = True
            check["verified"] = True
            check["verified_at"] = now.isoformat()

            user = self.data["users"][user_key]
            user["last_check"] = now.isoformat()
            user["next_check"] = self._get_next_check_time().isoformat()
            user["checks_completed"] += 1

            self._save()

            logger.info(f"PoP verified for user {telegram_id}: {check_id}")
            return True
        else:
            # Неудачная верификация
            check["completed"] = True
            check["verified"] = False
            self.data["users"][user_key]["checks_failed"] += 1
            self._save()

            logger.warning(f"PoP failed for user {telegram_id}: {check_id}")
            return False

    def get_user_status(self, telegram_id: int) -> Optional[Dict]:
        """Получить статус пользователя"""
        user_key = str(telegram_id)
        return self.data["users"].get(user_key)

    def get_pending_checks(self, telegram_id: int) -> list:
        """Получить незавершённые проверки пользователя"""
        now = datetime.now(timezone.utc)

        pending = []
        for check in self.data["checks"]:
            if check["telegram_id"] == telegram_id and not check["completed"]:
                expires_at = datetime.fromisoformat(check["expires_at"])
                if now <= expires_at:
                    pending.append(check)

        return pending

    async def background_checker(self, notify_callback: Callable):
        """
        Background task для автоматических проверок

        Args:
            notify_callback: async функция для отправки уведомлений
                             notify_callback(telegram_id, message)
        """
        logger.info("PoP background checker started")

        while True:
            try:
                # Проверить всех пользователей
                for user_key, user in self.data["users"].items():
                    if user["status"] != "active":
                        continue

                    telegram_id = user["telegram_id"]

                    if self.is_check_due(telegram_id):
                        # Запросить проверку
                        check_data = self.request_check(telegram_id)

                        # Отправить уведомление
                        await notify_callback(telegram_id, check_data["message"])

                        logger.info(f"PoP check sent to user {telegram_id}")

            except Exception as e:
                logger.error(f"Error in PoP background checker: {e}")

            # Проверять каждые 60 секунд
            await asyncio.sleep(60)


def get_pop_manager() -> ProofOfPresenceManager:
    """Получить экземпляр PoP Manager"""
    return ProofOfPresenceManager()


if __name__ == "__main__":
    # Тест
    print("🔐 Proof of Presence Test\n")

    pop = ProofOfPresenceManager(base_interval_minutes=1, randomness_minutes=0)

    # Зарегистрировать пользователя
    test_user = 8552053404
    pop.register_user(test_user, "test_user")

    status = pop.get_user_status(test_user)
    print(f"✅ User registered: {status['username']}")
    print(f"   Next check: {status['next_check']}")

    # Симулировать что время проверки пришло
    pop.data["users"][str(test_user)]["next_check"] = datetime.now(timezone.utc).isoformat()
    pop._save()

    # Проверить что нужна проверка
    is_due = pop.is_check_due(test_user)
    print(f"\n✅ Check due: {is_due}")

    if is_due:
        # Запросить проверку
        check = pop.request_check(test_user)
        print(f"\n📝 Check requested:")
        print(f"   ID: {check['check_id']}")
        print(f"   Expires: {check['expires_at']}")
        print(f"\n{check['message']}")

        # Зарегистрировать биометрию (если нет)
        if not pop.fido.has_biometric(test_user):
            pop.fido.register_biometric(test_user, "iPhone Test")

        # Верифицировать
        verified = pop.verify_check(test_user, check["check_id"])
        print(f"\n✅ Verification: {verified}")

        # Проверить статус
        status = pop.get_user_status(test_user)
        print(f"\n📊 User status:")
        print(f"   Completed: {status['checks_completed']}")
        print(f"   Failed: {status['checks_failed']}")
        print(f"   Next check: {status['next_check']}")

    print("\n🎯 Test passed!")
