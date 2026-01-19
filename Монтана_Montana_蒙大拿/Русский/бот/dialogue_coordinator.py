# dialogue_coordinator.py
# Юнона — Координация диалога Montana
# Запоминает предпочтения, ведет нить разговора, предлагает главы

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

# ═══════════════════════════════════════════════════════════════════════════════
#                              КООРДИНАТОР ДИАЛОГА
# ═══════════════════════════════════════════════════════════════════════════════

class DialogueCoordinator:
    """
    Координатор диалога Юноны с пользователем

    Отслеживает:
    - Полную историю диалога
    - Предпочтения формата (текст/аудио/оба)
    - Какие главы предложила
    - Какие главы прочитал/прослушал
    - Впечатления и заметки пользователя
    - Текущий контекст разговора
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "dialogues"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Путь к главам Montana
        # Определяем корневую папку Montana
        # Локально: бот находится в Montana/Русский/бот/
        # На сервере: бот в /root/junona_bot/, а Montana в /root/ACP_1/Ничто_Nothing_无/

        # Пытаемся найти Montana корень автоматически
        montana_root = None

        # Проверяем локальную структуру (бот внутри Montana)
        local_montana = data_dir.parent.parent.parent  # data -> бот -> Русский -> Монтана
        if (local_montana / "English" / "Gospel").exists():
            montana_root = local_montana

        # Если не локально, ищем на сервере
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

        # Формируем путь к главам
        if montana_root:
            self.chapters_dir = montana_root / "English" / "Gospel" / "«Book One ☝️» ☀️"
        else:
            # Fallback
            self.chapters_dir = Path("/root/ACP_1/Ничто_Nothing_无/Монтана_Montana_蒙大拿/English/Gospel/«Book One ☝️» ☀️")

    def _get_user_file(self, user_id: int) -> Path:
        """Путь к файлу координации пользователя"""
        return self.data_dir / f"user_{user_id}.json"

    def _load_state(self, user_id: int) -> dict:
        """Загрузить состояние диалога пользователя"""
        file_path = self._get_user_file(user_id)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Инициализация нового пользователя
        return {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dialogue": [],  # Вся история диалога
            "preferences": {
                "format": None,  # text, audio, both
                "language": "ru"
            },
            "chapters": {
                "offered": [],  # [{chapter: 1, timestamp: "..."}]
                "completed": []  # [{chapter: 1, format: "text", timestamp: "...", impression: "..."}]
            },
            "context": {
                "current_chapter": None,
                "waiting_for": None,  # format_choice, impression, etc.
                "last_topic": None
            },
            "notes": []  # Важные моменты из диалога
        }

    def _save_state(self, user_id: int, state: dict):
        """Сохранить состояние диалога"""
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        file_path = self._get_user_file(user_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def add_message(self, user_id: int, role: str, content: str, metadata: dict = None):
        """
        Добавить сообщение в диалог

        role: "user" или "junona"
        metadata: дополнительная информация (тип сообщения, контекст и т.д.)
        """
        state = self._load_state(user_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        state["dialogue"].append(message)
        self._save_state(user_id, state)

    def set_preference(self, user_id: int, key: str, value):
        """Установить предпочтение пользователя"""
        state = self._load_state(user_id)
        state["preferences"][key] = value
        self._save_state(user_id, state)

    def get_preference(self, user_id: int, key: str, default=None):
        """Получить предпочтение пользователя"""
        state = self._load_state(user_id)
        return state["preferences"].get(key, default)

    def offer_chapter(self, user_id: int, chapter_num: int):
        """Записать что глава была предложена"""
        state = self._load_state(user_id)
        state["chapters"]["offered"].append({
            "chapter": chapter_num,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        state["context"]["current_chapter"] = chapter_num
        state["context"]["waiting_for"] = "format_choice"
        self._save_state(user_id, state)

    def complete_chapter(self, user_id: int, chapter_num: int, format_used: str, impression: str = None):
        """Записать что глава пройдена"""
        state = self._load_state(user_id)
        state["chapters"]["completed"].append({
            "chapter": chapter_num,
            "format": format_used,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "impression": impression
        })
        state["context"]["current_chapter"] = None
        state["context"]["waiting_for"] = None
        self._save_state(user_id, state)

    def get_completed_chapters(self, user_id: int) -> List[int]:
        """Список пройденных глав"""
        state = self._load_state(user_id)
        return [c["chapter"] for c in state["chapters"]["completed"]]

    def get_next_chapter(self, user_id: int) -> int:
        """Номер следующей непройденной главы"""
        completed = self.get_completed_chapters(user_id)
        # Главы 0-9 (Prelude до Comedy)
        for i in range(10):
            if i not in completed:
                return i
        return None

    def add_note(self, user_id: int, note: str):
        """Добавить заметку о пользователе"""
        state = self._load_state(user_id)
        state["notes"].append({
            "note": note,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self._save_state(user_id, state)

    def get_context(self, user_id: int) -> dict:
        """Получить текущий контекст диалога"""
        state = self._load_state(user_id)
        return state["context"]

    def set_context(self, user_id: int, key: str, value):
        """Установить контекст"""
        state = self._load_state(user_id)
        state["context"][key] = value
        self._save_state(user_id, state)

    def get_dialogue_history(self, user_id: int, limit: int = None) -> List[dict]:
        """Получить историю диалога"""
        state = self._load_state(user_id)
        dialogue = state["dialogue"]
        if limit:
            return dialogue[-limit:]
        return dialogue

    def get_chapter_files(self, chapter_num: int) -> dict:
        """
        Получить пути к файлам главы

        Возвращает:
        {
            "text": Path | None,
            "audio": Path | None,
            "number": int,
            "name": str
        }
        """
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
        text_path = self.chapters_dir / text_file
        audio_path = self.chapters_dir / audio_file

        return {
            "number": chapter_num,
            "name": text_file.replace('.md', ''),
            "text": text_path if text_path.exists() else None,
            "audio": audio_path if audio_path.exists() else None
        }

    def should_offer_chapter(self, user_id: int, recent_messages: List[str]) -> Optional[int]:
        """
        Анализирует диалог и решает, пора ли предложить главу

        Логика:
        - Если пользователь спрашивает о Montana, времени, памяти → предложить релевантную главу
        - Если пользователь выражает интерес → предложить следующую главу
        - Не предлагать слишком часто (минимум 3-5 сообщений между предложениями)
        """
        state = self._load_state(user_id)
        dialogue_length = len(state["dialogue"])

        # Если диалог только начался, не предлагаем главу сразу
        if dialogue_length < 3:
            return None

        # Если уже ждем ответа пользователя
        if state["context"].get("waiting_for"):
            return None

        # Проверяем последние сообщения на ключевые слова
        text = " ".join(recent_messages[-5:]).lower()

        keywords_to_chapters = {
            0: ["начал", "начать", "с чего", "что почитать"],  # Prelude
            1: ["симуляц", "реальност", "матриц"],  # Simulation
            2: ["унижен", "достоинств", "уважен"],  # Humiliation
            3: ["поток", "flow", "время"],  # Flow
            4: ["след", "память", "trace"],  # Traces
            5: ["тревог", "страх", "anxiet"],  # Anxieties
            6: ["юнона", "juno", "день"],  # Juno's Day
            7: ["время", "печать", "seal"],  # Seal of Time
            8: ["узл", "сеть", "node"],  # Five Nodes
            9: ("комед", "смех", "юмор"),  # Comedy
        }

        # Проверяем какая глава релевантна
        for chapter, keywords in keywords_to_chapters.items():
            if chapter not in self.get_completed_chapters(user_id):
                if any(kw in text for kw in keywords):
                    return chapter

        # Если пользователь проявляет интерес, предлагаем следующую главу
        interest_keywords = ["интересн", "хочу", "расскажи", "узнать", "больше", "дальше", "продолж"]
        if any(kw in text for kw in interest_keywords):
            return self.get_next_chapter(user_id)

        return None


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЛОБАЛЬНЫЙ ИНСТАНС
# ═══════════════════════════════════════════════════════════════════════════════

_coordinator = None

def get_coordinator(data_dir: Path = None) -> DialogueCoordinator:
    """Получить глобальный координатор"""
    global _coordinator
    if _coordinator is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _coordinator = DialogueCoordinator(data_dir)
    return _coordinator
