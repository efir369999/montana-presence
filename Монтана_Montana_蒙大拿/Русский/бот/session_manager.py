# session_manager.py
# Montana Evolution: Изоляция сессий (git worktree analog)
# Каждый чат пользователя = отдельная папка с историей

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict


@dataclass
class Session:
    """Изолированная сессия пользователя"""
    id: str
    dir: Path
    user_id: int
    created_at: str

    def __post_init__(self):
        self.messages_file = self.dir / "messages.jsonl"
        self.reasoning_file = self.dir / "reasoning.jsonl"
        self.signatures_file = self.dir / "cognitive_sigs.json"
        self.agents_dir = self.dir / "agents"

    async def log_message(self, role: str, content: str, agent: Optional[str] = None):
        """
        Append-only лог сообщений

        role: user | assistant | system
        agent: claude | gpt | junona (если известен)
        """
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "role": role,
            "content": content
        }
        if agent:
            entry["agent"] = agent

        with open(self.messages_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def log_reasoning(self, agent: str, thinking: str, metadata: Optional[Dict] = None):
        """
        Append-only лог мышления агентов

        agent: claude | gpt
        thinking: полный блок <thinking>...</thinking>
        metadata: дополнительная информация
        """
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "agent": agent,
            "session": self.id,
            "thinking": thinking,
            "tokens": len(thinking) // 4  # грубая оценка
        }
        if metadata:
            entry["metadata"] = metadata

        with open(self.reasoning_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def save_cognitive_signature(self, agent: str, signature: Dict):
        """Сохранить когнитивную подпись агента в этой сессии"""
        sigs = {}
        if self.signatures_file.exists():
            sigs = json.loads(self.signatures_file.read_text(encoding="utf-8"))

        sigs[agent] = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "signature": signature
        }

        self.signatures_file.write_text(
            json.dumps(sigs, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """Получить историю сообщений"""
        if not self.messages_file.exists():
            return []

        messages = []
        with open(self.messages_file, "r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line))

        if limit:
            return messages[-limit:]
        return messages

    def get_reasoning_logs(self, agent: Optional[str] = None) -> List[Dict]:
        """Получить логи мышления (опционально отфильтровать по агенту)"""
        if not self.reasoning_file.exists():
            return []

        logs = []
        with open(self.reasoning_file, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if agent is None or entry.get("agent") == agent:
                    logs.append(entry)

        return logs

    def get_cognitive_signatures(self) -> Dict:
        """Получить когнитивные подписи всех агентов в сессии"""
        if not self.signatures_file.exists():
            return {}
        return json.loads(self.signatures_file.read_text(encoding="utf-8"))


class SessionManager:
    """
    Менеджер сессий пользователей
    Аналог git worktree — каждая сессия изолирована
    """

    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent / "data" / "sessions"

        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Параметры активной сессии
        self.session_timeout = timedelta(hours=1)  # Сессия активна 1 час

    def _get_user_dir(self, user_id: int) -> Path:
        """Получить папку пользователя"""
        user_dir = self.base_dir / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def create_session(self, user_id: int) -> Session:
        """
        Создать новую изолированную сессию для пользователя
        Аналог: git worktree add
        """
        user_dir = self._get_user_dir(user_id)

        # Уникальный ID сессии с timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        session_id = f"session_{timestamp}"
        session_dir = user_dir / session_id

        # Создаём структуру как в git worktree
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "agents" / "claude").mkdir(parents=True, exist_ok=True)
        (session_dir / "agents" / "gpt").mkdir(parents=True, exist_ok=True)

        session = Session(
            id=f"user_{user_id}_{session_id}",
            dir=session_dir,
            user_id=user_id,
            created_at=datetime.utcnow().isoformat() + "Z"
        )

        # Сохраняем метаданные сессии
        metadata_file = session_dir / "session.json"
        metadata_file.write_text(json.dumps({
            "id": session.id,
            "user_id": user_id,
            "created_at": session.created_at
        }, indent=2))

        return session

    def get_active_session(self, user_id: int) -> Session:
        """
        Получить активную сессию пользователя или создать новую

        Сессия считается активной если:
        1. Последнее сообщение не старше session_timeout (1 час)
        2. Сессия существует
        """
        user_dir = self._get_user_dir(user_id)

        # Ищем последнюю сессию
        sessions = sorted(user_dir.glob("session_*"), reverse=True)

        for session_dir in sessions:
            messages_file = session_dir / "messages.jsonl"

            # Если нет сообщений — пропускаем
            if not messages_file.exists():
                continue

            # Читаем последнее сообщение
            with open(messages_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    continue

                last_message = json.loads(lines[-1])
                last_ts = datetime.fromisoformat(last_message["ts"].replace("Z", "+00:00"))

                # Проверяем timeout
                if datetime.utcnow().replace(tzinfo=None) - last_ts.replace(tzinfo=None) < self.session_timeout:
                    # Сессия ещё активна
                    session_id = session_dir.name
                    metadata = json.loads((session_dir / "session.json").read_text())

                    return Session(
                        id=f"user_{user_id}_{session_id}",
                        dir=session_dir,
                        user_id=user_id,
                        created_at=metadata["created_at"]
                    )

        # Активной сессии нет — создаём новую
        return self.create_session(user_id)

    def get_session_by_id(self, user_id: int, session_id: str) -> Optional[Session]:
        """Получить конкретную сессию по ID"""
        user_dir = self._get_user_dir(user_id)
        session_dir = user_dir / session_id

        if not session_dir.exists():
            return None

        metadata_file = session_dir / "session.json"
        if not metadata_file.exists():
            return None

        metadata = json.loads(metadata_file.read_text())

        return Session(
            id=f"user_{user_id}_{session_id}",
            dir=session_dir,
            user_id=user_id,
            created_at=metadata["created_at"]
        )

    def list_sessions(self, user_id: int, limit: int = 10) -> List[Session]:
        """Получить список сессий пользователя (последние limit штук)"""
        user_dir = self._get_user_dir(user_id)
        sessions = sorted(user_dir.glob("session_*"), reverse=True)[:limit]

        result = []
        for session_dir in sessions:
            metadata_file = session_dir / "session.json"
            if not metadata_file.exists():
                continue

            metadata = json.loads(metadata_file.read_text())
            result.append(Session(
                id=f"user_{user_id}_{session_dir.name}",
                dir=session_dir,
                user_id=user_id,
                created_at=metadata["created_at"]
            ))

        return result

    def get_user_stats(self, user_id: int) -> Dict:
        """
        Статистика пользователя по всем сессиям
        Для расчёта уровня Орангутанга
        """
        user_dir = self._get_user_dir(user_id)

        total_messages = 0
        total_raw_thoughts = 0
        total_reasoning_logs = 0
        sessions_count = 0
        first_session_date = None

        for session_dir in user_dir.glob("session_*"):
            sessions_count += 1

            # Сообщения
            messages_file = session_dir / "messages.jsonl"
            if messages_file.exists():
                with open(messages_file, "r", encoding="utf-8") as f:
                    messages = [json.loads(line) for line in f]
                    total_messages += len(messages)

                    # Считаем сырые мысли (определяется по длине и отсутствию вопросов)
                    raw_thoughts = [m for m in messages if m.get("role") == "user" and len(m.get("content", "")) > 20]
                    total_raw_thoughts += len(raw_thoughts)

                    # Дата первой сессии
                    if messages and (first_session_date is None or messages[0]["ts"] < first_session_date):
                        first_session_date = messages[0]["ts"]

            # Reasoning logs
            reasoning_file = session_dir / "reasoning.jsonl"
            if reasoning_file.exists():
                with open(reasoning_file, "r", encoding="utf-8") as f:
                    total_reasoning_logs += sum(1 for _ in f)

        # Дни активности
        days_active = 0
        if first_session_date:
            first_date = datetime.fromisoformat(first_session_date.replace("Z", ""))
            days_active = (datetime.utcnow() - first_date).days

        return {
            "user_id": user_id,
            "sessions": sessions_count,
            "total_messages": total_messages,
            "raw_thoughts": total_raw_thoughts,
            "reasoning_logs": total_reasoning_logs,
            "days_active": days_active,
            "first_session": first_session_date
        }


# Singleton instance для использования в боте
_manager = None

def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


# Тесты
if __name__ == "__main__":
    import asyncio

    async def test():
        manager = SessionManager(Path("./test_sessions"))

        # Создать сессию
        session = manager.create_session(user_id=123456)
        print(f"✓ Сессия создана: {session.id}")
        print(f"  Папка: {session.dir}")

        # Логировать сообщения
        await session.log_message("user", "Что такое Montana?")
        await session.log_message("assistant", "Montana — протокол времени.", agent="claude")
        print(f"✓ Сообщения залогированы")

        # Логировать reasoning
        await session.log_reasoning(
            agent="claude",
            thinking="Пользователь спрашивает о Montana. Нужно объяснить через VDF и presence proofs..."
        )
        print(f"✓ Reasoning залогирован")

        # Cognitive signature
        await session.save_cognitive_signature("claude", {
            "security_focus": 0.85,
            "architectural": 0.72
        })
        print(f"✓ Cognitive signature сохранена")

        # Получить активную сессию (должна быть та же)
        active = manager.get_active_session(user_id=123456)
        assert active.id == session.id
        print(f"✓ Активная сессия получена: {active.id}")

        # Статистика
        stats = manager.get_user_stats(user_id=123456)
        print(f"✓ Статистика пользователя:")
        print(f"  Сессий: {stats['sessions']}")
        print(f"  Сообщений: {stats['total_messages']}")
        print(f"  Сырых мыслей: {stats['raw_thoughts']}")
        print(f"  Reasoning логов: {stats['reasoning_logs']}")

    asyncio.run(test())
    print("\n🏔 SessionManager: все тесты пройдены")
