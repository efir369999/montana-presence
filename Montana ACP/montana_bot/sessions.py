"""
Montana Bot Sessions — Управление сессиями пользователей
========================================================

ЗАКОН: Один ключ, одна подпись, один раз.

Сессии отслеживают:
- Активные challenges
- Состояние диалогов (ConversationHandler)
- Последняя активность пользователя
- Pending запросы на подключение к сети

Использование:
    from sessions import SessionManager, session_manager

    # Получить сессию
    session = session_manager.get_session(user_id)

    # Обновить активность
    session_manager.touch(user_id)

    # Сохранить данные сессии
    session_manager.set_data(user_id, "key", "value")
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import threading


@dataclass
class UserSession:
    """Сессия пользователя."""
    user_id: int
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_activity: int = field(default_factory=lambda: int(time.time()))

    # Состояние диалога
    conversation_state: Optional[str] = None
    conversation_data: Dict[str, Any] = field(default_factory=dict)

    # Challenge данные
    pending_challenge_id: Optional[str] = None
    challenge_sent_at: Optional[int] = None

    # Сетевой статус
    network_status: str = "pending"  # pending, approved, denied
    network_request_sent: bool = False

    # Произвольные данные
    data: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        """Обновить время последней активности."""
        self.last_activity = int(time.time())

    def is_expired(self, timeout_secs: int = 3600) -> bool:
        """Проверить истекла ли сессия."""
        return (int(time.time()) - self.last_activity) > timeout_secs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'UserSession':
        return cls(**data)


class SessionManager:
    """Менеджер сессий пользователей."""

    def __init__(self, data_dir: Path, autosave_interval: int = 60):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = self.data_dir / "sessions.json"
        self.autosave_interval = autosave_interval

        self._sessions: Dict[int, UserSession] = {}
        self._lock = threading.Lock()
        self._last_save = time.time()

        self._load()

    def _load(self):
        """Загрузить сессии из файла."""
        if self.sessions_file.exists():
            try:
                data = json.loads(self.sessions_file.read_text())
                for user_id_str, session_data in data.get("sessions", {}).items():
                    user_id = int(user_id_str)
                    self._sessions[user_id] = UserSession.from_dict(session_data)
            except Exception as e:
                print(f"Error loading sessions: {e}")

    def _save(self, force: bool = False):
        """Сохранить сессии в файл."""
        now = time.time()
        if not force and (now - self._last_save) < self.autosave_interval:
            return

        with self._lock:
            data = {
                "sessions": {
                    str(uid): session.to_dict()
                    for uid, session in self._sessions.items()
                },
                "updated": datetime.now(timezone.utc).isoformat()
            }
            self.sessions_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            self._last_save = now

    def get_session(self, user_id: int) -> UserSession:
        """Получить или создать сессию пользователя."""
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession(user_id=user_id)
            return self._sessions[user_id]

    def has_session(self, user_id: int) -> bool:
        """Проверить есть ли сессия."""
        return user_id in self._sessions

    def touch(self, user_id: int):
        """Обновить время активности."""
        session = self.get_session(user_id)
        session.touch()
        self._save()

    def set_data(self, user_id: int, key: str, value: Any):
        """Установить данные в сессии."""
        session = self.get_session(user_id)
        session.data[key] = value
        session.touch()
        self._save()

    def get_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """Получить данные из сессии."""
        session = self.get_session(user_id)
        return session.data.get(key, default)

    def set_conversation_state(self, user_id: int, state: Optional[str], data: Dict[str, Any] = None):
        """Установить состояние диалога."""
        session = self.get_session(user_id)
        session.conversation_state = state
        if data:
            session.conversation_data = data
        session.touch()
        self._save()

    def get_conversation_state(self, user_id: int) -> tuple:
        """Получить состояние диалога."""
        session = self.get_session(user_id)
        return session.conversation_state, session.conversation_data

    def clear_conversation(self, user_id: int):
        """Очистить состояние диалога."""
        session = self.get_session(user_id)
        session.conversation_state = None
        session.conversation_data = {}
        session.touch()
        self._save()

    def set_pending_challenge(self, user_id: int, challenge_id: str):
        """Установить активный challenge."""
        session = self.get_session(user_id)
        session.pending_challenge_id = challenge_id
        session.challenge_sent_at = int(time.time())
        session.touch()
        self._save()

    def clear_challenge(self, user_id: int):
        """Очистить challenge."""
        session = self.get_session(user_id)
        session.pending_challenge_id = None
        session.challenge_sent_at = None
        session.touch()
        self._save()

    def get_pending_challenge(self, user_id: int) -> Optional[str]:
        """Получить ID активного challenge."""
        session = self.get_session(user_id)
        return session.pending_challenge_id

    def set_network_status(self, user_id: int, status: str):
        """Установить статус в сети."""
        session = self.get_session(user_id)
        session.network_status = status
        session.touch()
        self._save()

    def get_network_status(self, user_id: int) -> str:
        """Получить статус в сети."""
        session = self.get_session(user_id)
        return session.network_status

    def cleanup_expired(self, timeout_secs: int = 86400):
        """Удалить истёкшие сессии."""
        with self._lock:
            expired = [
                uid for uid, session in self._sessions.items()
                if session.is_expired(timeout_secs)
            ]
            for uid in expired:
                del self._sessions[uid]
            if expired:
                self._save(force=True)
        return len(expired)

    def get_active_users(self, within_secs: int = 3600) -> List[int]:
        """Получить список активных пользователей."""
        now = int(time.time())
        return [
            uid for uid, session in self._sessions.items()
            if (now - session.last_activity) <= within_secs
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику сессий."""
        now = int(time.time())
        active_1h = sum(1 for s in self._sessions.values() if (now - s.last_activity) <= 3600)
        active_24h = sum(1 for s in self._sessions.values() if (now - s.last_activity) <= 86400)

        pending_challenges = sum(1 for s in self._sessions.values() if s.pending_challenge_id)

        network_stats = {
            "pending": sum(1 for s in self._sessions.values() if s.network_status == "pending"),
            "approved": sum(1 for s in self._sessions.values() if s.network_status == "approved"),
            "denied": sum(1 for s in self._sessions.values() if s.network_status == "denied"),
        }

        return {
            "total_sessions": len(self._sessions),
            "active_1h": active_1h,
            "active_24h": active_24h,
            "pending_challenges": pending_challenges,
            "network_stats": network_stats,
        }

    def save(self):
        """Принудительно сохранить."""
        self._save(force=True)


# Глобальный менеджер сессий
_session_manager: Optional[SessionManager] = None


def get_session_manager(data_dir: Path = None) -> SessionManager:
    """Получить глобальный менеджер сессий."""
    global _session_manager
    if _session_manager is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _session_manager = SessionManager(data_dir)
    return _session_manager


# Удобный алиас
session_manager = None


def init_sessions(data_dir: Path = None):
    """Инициализировать менеджер сессий."""
    global session_manager
    session_manager = get_session_manager(data_dir)
    return session_manager


if __name__ == "__main__":
    # Тест
    manager = SessionManager(Path("./test_sessions"))

    # Создать сессию
    session = manager.get_session(12345)
    print(f"Session created: {session.user_id}")

    # Установить данные
    manager.set_data(12345, "test_key", "test_value")
    print(f"Data set: {manager.get_data(12345, 'test_key')}")

    # Challenge
    manager.set_pending_challenge(12345, "challenge_abc123")
    print(f"Challenge: {manager.get_pending_challenge(12345)}")

    # Статистика
    stats = manager.get_stats()
    print(f"Stats: {stats}")

    # Сохранить
    manager.save()
    print("Saved!")
