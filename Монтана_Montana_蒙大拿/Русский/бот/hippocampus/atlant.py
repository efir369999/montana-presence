#!/usr/bin/env python3
"""
АТЛАНТ — Гиппокамп Montana
==========================

Титан, который держит память сети.
Единая система памяти: разговоры, мысли, контекст.

Компоненты:
- Детектор новизны (is_thought)
- Память диалогов (dialogue)
- Поток мыслей (stream)
- Контекст пользователя (context)

Хранение: MontanaDB (SQLite на узлах)

Атлант ≠ Юнона.
Юнона — Лицо (интерфейс общения).
Атлант — Гиппокамп (молча несёт вес памяти).

Alejandro Montana
Montana Protocol v1.0
Январь 2026
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# Импортируем базу данных Montana
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from montana_db import get_db, MontanaDB

logger = logging.getLogger("ATLANT")


# ═══════════════════════════════════════════════════════════════════════════════
#                              СТРУКТУРЫ ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Thought:
    """Единица памяти — координата в 4D пространстве"""
    user_id: int
    username: str
    timestamp: str
    content: str
    lang: str = "ru"
    location: Optional[str] = None
    music_track: Optional[str] = None
    response: Optional[str] = None  # Ответ Юноны


@dataclass
class DialogueMessage:
    """Сообщение в диалоге"""
    role: str  # "user" или "junona"
    content: str
    timestamp: str
    metadata: Optional[Dict] = None


# ═══════════════════════════════════════════════════════════════════════════════
#                              АТЛАНТ — ГИППОКАМП
# ═══════════════════════════════════════════════════════════════════════════════

class Atlant:
    """
    Атлант — Гиппокамп Montana

    Держит память сети. Молча. Как титан.

    Функции:
    1. Детектор новизны — отличает мысли от команд
    2. Память диалогов — сохраняет историю общения с Юноной
    3. Поток мыслей — личная память пользователя
    4. Контекст — текущее состояние разговора

    Всё хранится в MontanaDB на узлах.
    """

    def __init__(self, db: MontanaDB = None, data_dir: Path = None):
        self.db = db or get_db()
        self.data_dir = data_dir or Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Файл для локального потока (backup)
        self.stream_file = self.data_dir / "stream.jsonl"

        # Папка для диалогов (JSON backup)
        self.dialogues_dir = self.data_dir / "dialogues"
        self.dialogues_dir.mkdir(parents=True, exist_ok=True)

        logger.info("🏛 Атлант инициализирован — Гиппокамп Montana")

    # ═══════════════════════════════════════════════════════════════════════
    #                         ДЕТЕКТОР НОВИЗНЫ
    # ═══════════════════════════════════════════════════════════════════════

    def is_thought(self, text: str) -> bool:
        """
        Детектор новизны — определяет, является ли текст мыслью

        Эмулирует биологический гиппокамп:
        - Сравнивает с известными паттернами
        - Возвращает True если это НОВАЯ мысль для записи

        Критерии:
        - Длина 15-500 символов
        - Минимум 3 слова
        - Не вопрос (без ?)
        - Не команда
        - Не приветствие/прощание
        """
        text = text.strip()

        # Слишком длинное — не мысль
        if len(text) > 500:
            return False

        # Слишком короткое — скорее всего не мысль (минимум 15 символов)
        if len(text) < 15:
            return False

        # Минимум 3 слова
        words = text.split()
        if len(words) < 3:
            return False

        # Вопрос — не мысль
        if text.endswith("?"):
            return False

        # Команды — не мысли
        command_patterns = [
            "покажи", "расскажи", "помоги", "объясни",
            "найди", "открой", "запусти", "сделай",
            "дай", "скинь", "отправь", "напиши",
            "/start", "/help", "/balance", "/stats",
            "/node", "/transfer", "/tx", "/feed", "/stream"
        ]
        text_lower = text.lower()
        for pattern in command_patterns:
            if text_lower.startswith(pattern):
                return False

        # Приветствия/прощания — не мысли
        greetings = [
            "привет", "здравствуй", "здорово", "хай", "hello", "hi",
            "пока", "до свидания", "bye", "ок", "окей", "okay",
            "да", "нет", "yes", "no", "спасибо", "thanks", "хорошо",
            "понял", "ясно", "ладно", "угу", "ага"
        ]
        first_word = words[0].lower().rstrip(".,!?")
        if first_word in greetings and len(words) <= 3:
            return False

        # Это мысль
        return True

    # ═══════════════════════════════════════════════════════════════════════
    #                         ПОТОК МЫСЛЕЙ
    # ═══════════════════════════════════════════════════════════════════════

    def save_thought(
        self,
        user_id: int,
        content: str,
        username: str = "unknown",
        response: str = None,
        lang: str = "ru",
        location: str = None,
        music_track: str = None
    ) -> Thought:
        """
        Сохраняет мысль в Гиппокамп

        Двойное сохранение:
        1. MontanaDB (SQLite на узлах) — основное
        2. stream.jsonl (локальный backup) — резервное
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Сохраняем в базу данных
        self.db.save_thought(
            telegram_id=user_id,
            message=content,
            response=response,
            source="atlant"
        )

        # 2. Backup в JSONL
        thought = Thought(
            user_id=user_id,
            username=username,
            timestamp=now,
            content=content,
            lang=lang,
            location=location,
            music_track=music_track,
            response=response
        )

        with open(self.stream_file, "a", encoding="utf-8") as f:
            data = {
                "user_id": thought.user_id,
                "username": thought.username,
                "timestamp": thought.timestamp,
                "thought": thought.content,
                "lang": thought.lang
            }
            if thought.location:
                data["location"] = thought.location
            if thought.music_track:
                data["music_track"] = thought.music_track
            if thought.response:
                data["response"] = thought.response

            f.write(json.dumps(data, ensure_ascii=False) + "\n")

        logger.info(f"💭 Мысль сохранена: user={user_id}")
        return thought

    def get_thoughts(self, user_id: int, limit: int = 50) -> List[Thought]:
        """Получает мысли пользователя из базы"""
        rows = self.db.get_thoughts(user_id, limit=limit)

        return [
            Thought(
                user_id=row["telegram_id"],
                username="",
                timestamp=row["timestamp"],
                content=row["message"],
                response=row.get("response")
            )
            for row in rows
        ]

    def get_all_thoughts(self, limit: int = 100) -> List[Thought]:
        """Получает все мысли из базы"""
        rows = self.db.get_all_thoughts(limit=limit)

        return [
            Thought(
                user_id=row["telegram_id"],
                username="",
                timestamp=row["timestamp"],
                content=row["message"],
                response=row.get("response")
            )
            for row in rows
        ]

    def search_thoughts(self, query: str, limit: int = 20) -> List[Thought]:
        """Поиск по мыслям"""
        all_thoughts = self.get_all_thoughts(limit=1000)
        query_lower = query.lower()

        results = []
        for thought in all_thoughts:
            if query_lower in thought.content.lower():
                results.append(thought)

        return results[:limit]

    def thought_stats(self, user_id: int = None) -> Dict[str, Any]:
        """Статистика мыслей"""
        if user_id:
            thoughts = self.get_thoughts(user_id, limit=10000)
        else:
            thoughts = self.get_all_thoughts(limit=10000)

        if not thoughts:
            return {
                "total": 0,
                "unique_users": 0,
                "density": 0
            }

        users = set(t.user_id for t in thoughts)

        # Плотность кодирования (мыслей в день)
        if len(thoughts) >= 2:
            first = datetime.fromisoformat(thoughts[-1].timestamp.replace("Z", "+00:00"))
            last = datetime.fromisoformat(thoughts[0].timestamp.replace("Z", "+00:00"))
            days = max(1, (last - first).days)
            density = round(len(thoughts) / days, 2)
        else:
            density = len(thoughts)

        return {
            "total": len(thoughts),
            "unique_users": len(users),
            "density": density,
            "first": thoughts[-1].timestamp if thoughts else None,
            "last": thoughts[0].timestamp if thoughts else None
        }

    # ═══════════════════════════════════════════════════════════════════════
    #                         ПАМЯТЬ ДИАЛОГОВ
    # ═══════════════════════════════════════════════════════════════════════

    def _get_dialogue_file(self, user_id: int) -> Path:
        """Путь к файлу диалога (JSON backup)"""
        return self.dialogues_dir / f"user_{user_id}.json"

    def _load_dialogue_state(self, user_id: int) -> Dict:
        """Загружает состояние диалога"""
        file_path = self._get_dialogue_file(user_id)

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass

        # Новый пользователь
        return {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dialogue": [],
            "preferences": {
                "format": None,
                "language": "ru"
            },
            "chapters": {
                "offered": [],
                "completed": []
            },
            "context": {
                "current_chapter": None,
                "waiting_for": None,
                "last_topic": None
            },
            "notes": []
        }

    def _save_dialogue_state(self, user_id: int, state: Dict):
        """Сохраняет состояние диалога"""
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        file_path = self._get_dialogue_file(user_id)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        metadata: Dict = None
    ):
        """
        Добавляет сообщение в диалог

        role: "user" или "junona"
        """
        state = self._load_dialogue_state(user_id)
        now = datetime.now(timezone.utc).isoformat()

        message = {
            "role": role,
            "content": content,
            "timestamp": now,
            "metadata": metadata or {}
        }

        state["dialogue"].append(message)

        # Ограничиваем историю (последние 100 сообщений)
        if len(state["dialogue"]) > 100:
            state["dialogue"] = state["dialogue"][-100:]

        self._save_dialogue_state(user_id, state)

        # Также сохраняем в базу если это мысль пользователя
        if role == "user" and self.is_thought(content):
            self.db.save_thought(
                telegram_id=user_id,
                message=content,
                source="dialogue"
            )

    def get_dialogue(self, user_id: int, limit: int = None) -> List[Dict]:
        """Получает историю диалога"""
        state = self._load_dialogue_state(user_id)
        dialogue = state["dialogue"]

        if limit:
            return dialogue[-limit:]
        return dialogue

    def get_dialogue_for_ai(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Возвращает диалог в формате для AI (OpenAI/Anthropic)

        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        dialogue = self.get_dialogue(user_id, limit=limit)

        result = []
        for msg in dialogue:
            role = "assistant" if msg["role"] == "junona" else "user"
            result.append({
                "role": role,
                "content": msg["content"]
            })

        return result

    # ═══════════════════════════════════════════════════════════════════════
    #                         КОНТЕКСТ
    # ═══════════════════════════════════════════════════════════════════════

    def get_context(self, user_id: int) -> Dict:
        """Получает текущий контекст диалога"""
        state = self._load_dialogue_state(user_id)
        return state["context"]

    def set_context(self, user_id: int, key: str, value: Any):
        """Устанавливает контекст"""
        state = self._load_dialogue_state(user_id)
        state["context"][key] = value
        self._save_dialogue_state(user_id, state)

    def clear_context(self, user_id: int):
        """Очищает контекст"""
        state = self._load_dialogue_state(user_id)
        state["context"] = {
            "current_chapter": None,
            "waiting_for": None,
            "last_topic": None
        }
        self._save_dialogue_state(user_id, state)

    # ═══════════════════════════════════════════════════════════════════════
    #                         ПРЕДПОЧТЕНИЯ
    # ═══════════════════════════════════════════════════════════════════════

    def get_preference(self, user_id: int, key: str, default=None):
        """Получает предпочтение пользователя"""
        state = self._load_dialogue_state(user_id)
        return state["preferences"].get(key, default)

    def set_preference(self, user_id: int, key: str, value: Any):
        """Устанавливает предпочтение"""
        state = self._load_dialogue_state(user_id)
        state["preferences"][key] = value
        self._save_dialogue_state(user_id, state)

    # ═══════════════════════════════════════════════════════════════════════
    #                         ГЛАВЫ
    # ═══════════════════════════════════════════════════════════════════════

    def offer_chapter(self, user_id: int, chapter_num: int):
        """Записывает что глава была предложена"""
        state = self._load_dialogue_state(user_id)
        now = datetime.now(timezone.utc).isoformat()

        state["chapters"]["offered"].append({
            "chapter": chapter_num,
            "timestamp": now
        })
        state["context"]["current_chapter"] = chapter_num
        state["context"]["waiting_for"] = "format_choice"

        self._save_dialogue_state(user_id, state)

    def complete_chapter(
        self,
        user_id: int,
        chapter_num: int,
        format_used: str,
        impression: str = None
    ):
        """Записывает что глава пройдена"""
        state = self._load_dialogue_state(user_id)
        now = datetime.now(timezone.utc).isoformat()

        state["chapters"]["completed"].append({
            "chapter": chapter_num,
            "format": format_used,
            "timestamp": now,
            "impression": impression
        })
        state["context"]["current_chapter"] = None
        state["context"]["waiting_for"] = None

        self._save_dialogue_state(user_id, state)

    def get_completed_chapters(self, user_id: int) -> List[int]:
        """Список пройденных глав"""
        state = self._load_dialogue_state(user_id)
        return [c["chapter"] for c in state["chapters"]["completed"]]

    def get_next_chapter(self, user_id: int) -> Optional[int]:
        """Номер следующей непройденной главы"""
        completed = self.get_completed_chapters(user_id)
        for i in range(10):  # Главы 0-9
            if i not in completed:
                return i
        return None

    def get_chapter_files(self, chapter_num: int) -> Optional[Dict]:
        """
        Получает пути к файлам главы

        Возвращает:
        {
            "text": Path | None,
            "audio": Path | None,
            "number": int,
            "name": str
        }
        """
        # Определяем путь к главам Montana
        montana_root = None

        # Локальная структура
        local_montana = self.data_dir.parent.parent.parent
        if (local_montana / "English" / "Gospel").exists():
            montana_root = local_montana

        # Серверные пути
        if not montana_root:
            server_paths = [
                Path("/root/ACP_1/Ничто_Nothing_无/Монтана_Montana_蒙大拿"),
                Path("/root/montana_knowledge/Монтана_Montana_蒙大拿"),
                Path("/root/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿"),
            ]
            for path in server_paths:
                if path.exists() and (path / "English" / "Gospel").exists():
                    montana_root = path
                    break

        if not montana_root:
            montana_root = Path("/root/ACP_1/Ничто_Nothing_无/Монтана_Montana_蒙大拿")

        chapters_dir = montana_root / "English" / "Gospel" / "«Book One ☝️» ☀️"

        chapter_map = {
            0: ("00. Prelude.md", "00. Prelude.mp3"),
            1: ("01. Simulation.md", "01. Simulation.mp3"),
            2: ("02. Humiliation.md", "02. Humiliation.mp3"),
            3: ("03. Flow.md", "03. Flow.mp3"),
            4: ("04. Traces.md", "04. Traces.mp3"),
            5: ("05. Anxieties.md", "05. Anxieties.mp3"),
            6: ("06. Junos Day.md", "06. Junos Day.mp3"),
            7: ("07. Seal of Time.md", "07. Seal of Time.mp3"),
            8: ("08. Five Nodes.md", "08. Five Nodes.mp3"),
            9: ("09. Comedy.md", "09. Comedy.mp3"),
        }

        if chapter_num not in chapter_map:
            return None

        text_file, audio_file = chapter_map[chapter_num]
        text_path = chapters_dir / text_file
        audio_path = chapters_dir / audio_file

        return {
            "number": chapter_num,
            "name": text_file.replace('.md', ''),
            "text": text_path if text_path.exists() else None,
            "audio": audio_path if audio_path.exists() else None
        }

    # ═══════════════════════════════════════════════════════════════════════
    #                         ЗАМЕТКИ
    # ═══════════════════════════════════════════════════════════════════════

    def add_note(self, user_id: int, note: str):
        """Добавляет заметку о пользователе"""
        state = self._load_dialogue_state(user_id)
        now = datetime.now(timezone.utc).isoformat()

        state["notes"].append({
            "note": note,
            "timestamp": now
        })

        self._save_dialogue_state(user_id, state)

    def get_notes(self, user_id: int) -> List[Dict]:
        """Получает заметки о пользователе"""
        state = self._load_dialogue_state(user_id)
        return state["notes"]

    # ═══════════════════════════════════════════════════════════════════════
    #                         ЭКСПОРТ
    # ═══════════════════════════════════════════════════════════════════════

    def export_markdown(self, user_id: int) -> str:
        """Экспортирует память пользователя в Markdown"""
        thoughts = self.get_thoughts(user_id, limit=1000)
        dialogue = self.get_dialogue(user_id)
        stats = self.thought_stats(user_id)

        lines = [
            f"# Память Montana — User {user_id}",
            "",
            f"**Мыслей:** {stats['total']}",
            f"**Плотность:** {stats['density']} мыслей/день",
            "",
            "---",
            "",
            "## Мысли",
            ""
        ]

        current_date = None
        for thought in reversed(thoughts):
            date = thought.timestamp[:10]
            if date != current_date:
                current_date = date
                lines.append(f"### {date}")
                lines.append("")

            time = thought.timestamp[11:16]
            lines.append(f"**[{time}]** {thought.content}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Диалог с Юноной",
            ""
        ])

        for msg in dialogue[-50:]:  # Последние 50 сообщений
            role = "Юнона" if msg["role"] == "junona" else "Пользователь"
            time = msg["timestamp"][11:16]
            content = msg["content"][:200]
            lines.append(f"**[{time}] {role}:** {content}")
            lines.append("")

        lines.extend([
            "---",
            "",
            f"*Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "Атлант — Гиппокамп Montana"
        ])

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_atlant: Optional[Atlant] = None


def get_atlant() -> Atlant:
    """Возвращает глобальный экземпляр Атланта"""
    global _atlant
    if _atlant is None:
        _atlant = Atlant()
    return _atlant


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Атлант — Гиппокамп Montana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python atlant.py --stats                 # Статистика памяти
  python atlant.py --thoughts 123456       # Мысли пользователя
  python atlant.py --dialogue 123456       # Диалог пользователя
  python atlant.py --search "время"        # Поиск по мыслям
  python atlant.py --export 123456         # Экспорт в Markdown
        """
    )

    parser.add_argument("--stats", "-s", action="store_true", help="Статистика памяти")
    parser.add_argument("--thoughts", "-t", type=int, help="Мысли пользователя по user_id")
    parser.add_argument("--dialogue", "-d", type=int, help="Диалог пользователя по user_id")
    parser.add_argument("--search", "-q", type=str, help="Поиск по мыслям")
    parser.add_argument("--export", "-e", type=int, help="Экспорт памяти пользователя")

    args = parser.parse_args()

    atlant = get_atlant()

    if args.stats:
        stats = atlant.thought_stats()
        print("🏛 Атлант — Статистика памяти Montana")
        print()
        print(f"  Всего мыслей:     {stats['total']}")
        print(f"  Пользователей:    {stats['unique_users']}")
        print(f"  Плотность:        {stats['density']} мыслей/день")

    elif args.thoughts:
        thoughts = atlant.get_thoughts(args.thoughts, limit=20)
        print(f"🏛 Мысли пользователя {args.thoughts}:")
        print()
        for t in thoughts:
            time = t.timestamp[:16].replace("T", " ")
            print(f"[{time}] {t.content}")
            print()

    elif args.dialogue:
        dialogue = atlant.get_dialogue(args.dialogue, limit=20)
        print(f"🏛 Диалог пользователя {args.dialogue}:")
        print()
        for msg in dialogue:
            role = "Юнона" if msg["role"] == "junona" else "User"
            time = msg["timestamp"][11:16]
            print(f"[{time}] {role}: {msg['content'][:100]}")
            print()

    elif args.search:
        thoughts = atlant.search_thoughts(args.search)
        print(f"🏛 Поиск: \"{args.search}\" ({len(thoughts)} результатов)")
        print()
        for t in thoughts:
            time = t.timestamp[:16].replace("T", " ")
            print(f"[{time}] {t.content}")
            print()

    elif args.export:
        markdown = atlant.export_markdown(args.export)
        print(markdown)

    else:
        parser.print_help()
