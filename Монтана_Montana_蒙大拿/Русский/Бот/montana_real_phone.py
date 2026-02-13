#!/usr/bin/env python3
"""
Montana Protocol — Real Phone Number Binding
Привязка реальных телефонных номеров к Montana адресам.

Модель:
1. Пользователь вводит свой реальный номер (+7-921-123-4567)
2. Montana отправляет SMS с кодом верификации
3. Пользователь вводит код
4. Номер привязывается к Montana адресу
5. Теперь номер = кошелек (может звонить за 1 Ɉ/сек)
"""

import json
import threading
import fcntl
import time
import random
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

log = logging.getLogger("montana_real_phone")

# ═══════════════════════════════════════════════════════════════════════════════
#                      REAL PHONE NUMBER BINDING SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class RealPhoneService:
    """
    Сервис привязки реальных телефонных номеров к Montana адресам.

    Workflow:
    1. request_verification(phone, montana_address) → отправляет SMS с кодом
    2. verify_code(phone, code) → проверяет код и привязывает номер
    3. lookup(phone) → возвращает Montana адрес владельца
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.bindings_file = self.data_dir / "real_phone_bindings.json"
        self.pending_file = self.data_dir / "real_phone_pending.json"
        self._lock = threading.Lock()
        self._ensure_files()

    def _ensure_files(self):
        """Создать файлы если не существуют"""
        if not self.bindings_file.exists():
            self._save_bindings({})
        if not self.pending_file.exists():
            self._save_pending({})

    def _load_bindings(self) -> Dict[str, Dict]:
        """Загрузить привязанные номера"""
        with open(self.bindings_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_bindings(self, bindings: Dict[str, Dict]):
        """Сохранить привязанные номера"""
        with open(self.bindings_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(bindings, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load_pending(self) -> Dict[str, Dict]:
        """Загрузить pending верификации"""
        with open(self.pending_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_pending(self, pending: Dict[str, Dict]):
        """Сохранить pending верификации"""
        with open(self.pending_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(pending, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _normalize_phone(self, phone: str) -> str:
        """
        Нормализовать телефонный номер.

        Examples:
            +7-921-123-4567 → +79211234567
            8 (921) 123-45-67 → +79211234567
            +1 (555) 123-4567 → +15551234567
        """
        # Удалить все кроме цифр и +
        normalized = ''.join(c for c in phone if c.isdigit() or c == '+')

        # Если начинается с 8 (Россия) → +7
        if normalized.startswith('8') and len(normalized) == 11:
            normalized = '+7' + normalized[1:]

        # Добавить + если нет
        if not normalized.startswith('+'):
            # Определить страну по длине (упрощенно)
            if len(normalized) == 10:  # USA
                normalized = '+1' + normalized
            elif len(normalized) == 11:  # Russia
                normalized = '+' + normalized

        return normalized

    def _generate_code(self) -> str:
        """Сгенерировать 6-значный код верификации"""
        return f"{random.randint(100000, 999999)}"

    def _send_sms(self, phone: str, code: str) -> bool:
        """
        Отправить SMS с кодом верификации.

        В production это интегрируется с SMS провайдером (Twilio, etc.)
        Сейчас просто логируем код.
        """
        # TODO: Интеграция с SMS API (Twilio, MessageBird, etc.)
        log.info(f"SMS → {phone}: Your Montana verification code: {code}")

        # В dev режиме просто возвращаем True
        # В production проверяем результат SMS API
        return True

    def request_verification(
        self,
        phone: str,
        montana_address: str
    ) -> Dict:
        """
        Запросить верификацию номера.

        Args:
            phone: Телефонный номер (любой формат)
            montana_address: Montana адрес для привязки

        Returns:
            Dict с результатом запроса
        """
        phone_normalized = self._normalize_phone(phone)

        with self._lock:
            bindings = self._load_bindings()
            pending = self._load_pending()

            # Проверить что номер не привязан к другому адресу
            if phone_normalized in bindings:
                existing_owner = bindings[phone_normalized]['montana_address']
                if existing_owner != montana_address:
                    raise ValueError(
                        f"Phone number already bound to different address: {existing_owner[:10]}..."
                    )
                return {
                    "status": "already_verified",
                    "phone": phone_normalized,
                    "montana_address": montana_address
                }

            # Сгенерировать код
            code = self._generate_code()

            # Сохранить в pending (expires in 10 minutes)
            expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat() + "Z"
            pending[phone_normalized] = {
                "code": code,
                "montana_address": montana_address,
                "expires": expires,
                "created": datetime.utcnow().isoformat() + "Z",
                "attempts": 0
            }
            self._save_pending(pending)

            # Отправить SMS
            sms_sent = self._send_sms(phone_normalized, code)

            if not sms_sent:
                raise Exception("Failed to send SMS")

            log.info(f"Verification requested: {phone_normalized} → {montana_address[:10]}...")

            return {
                "status": "code_sent",
                "phone": phone_normalized,
                "montana_address": montana_address,
                "expires": expires,
                "dev_code": code if __debug__ else None  # Only in debug mode
            }

    def verify_code(
        self,
        phone: str,
        code: str
    ) -> Dict:
        """
        Проверить код верификации и привязать номер.

        Args:
            phone: Телефонный номер
            code: 6-значный код из SMS

        Returns:
            Dict с результатом верификации
        """
        phone_normalized = self._normalize_phone(phone)

        with self._lock:
            pending = self._load_pending()

            if phone_normalized not in pending:
                raise ValueError("No pending verification for this phone number")

            verification = pending[phone_normalized]

            # Проверить expiration
            expires = datetime.fromisoformat(verification['expires'].replace('Z', '+00:00'))
            if datetime.utcnow() > expires.replace(tzinfo=None):
                del pending[phone_normalized]
                self._save_pending(pending)
                raise ValueError("Verification code expired")

            # Проверить код
            if verification['code'] != code:
                verification['attempts'] += 1
                if verification['attempts'] >= 3:
                    del pending[phone_normalized]
                    self._save_pending(pending)
                    raise ValueError("Too many failed attempts")
                else:
                    self._save_pending(pending)
                    raise ValueError(f"Invalid code ({verification['attempts']}/3 attempts)")

            # Код правильный — привязать номер
            montana_address = verification['montana_address']

            bindings = self._load_bindings()
            bindings[phone_normalized] = {
                "montana_address": montana_address,
                "verified": datetime.utcnow().isoformat() + "Z",
                "phone": phone_normalized,
                "audio_seconds_used": 0,
                "video_seconds_used": 0
            }
            self._save_bindings(bindings)

            # Удалить из pending
            del pending[phone_normalized]
            self._save_pending(pending)

            log.info(f"Phone verified: {phone_normalized} → {montana_address[:10]}...")

            return {
                "status": "verified",
                "phone": phone_normalized,
                "montana_address": montana_address,
                "verified": bindings[phone_normalized]['verified']
            }

    def lookup(self, phone: str) -> Optional[Dict]:
        """
        Найти Montana адрес по телефонному номеру.

        Args:
            phone: Телефонный номер

        Returns:
            Dict с информацией о привязке или None
        """
        phone_normalized = self._normalize_phone(phone)

        with self._lock:
            bindings = self._load_bindings()
            if phone_normalized in bindings:
                return bindings[phone_normalized].copy()
            return None

    def is_verified(self, phone: str) -> bool:
        """Проверить привязан ли номер"""
        return self.lookup(phone) is not None

    def get_by_address(self, montana_address: str) -> List[str]:
        """
        Найти все телефонные номера привязанные к Montana адресу.

        Args:
            montana_address: Montana адрес

        Returns:
            Список телефонных номеров
        """
        with self._lock:
            bindings = self._load_bindings()
            phones = []
            for phone, info in bindings.items():
                if info['montana_address'] == montana_address:
                    phones.append(phone)
            return phones


# ═══════════════════════════════════════════════════════════════════════════════
#                            GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_real_phone_service: Optional[RealPhoneService] = None

def get_real_phone_service(data_dir: Path = None) -> RealPhoneService:
    """Получить глобальный экземпляр RealPhoneService (singleton)"""
    global _real_phone_service
    if _real_phone_service is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _real_phone_service = RealPhoneService(data_dir)
    return _real_phone_service
