"""
ГИППОКАМП — Система памяти Montana
==================================

Атлант — титан, который держит память сети.

Модули:
- atlant.py — единая система памяти (мысли, диалоги, контекст)

Использование:
    from hippocampus import get_atlant

    atlant = get_atlant()
    atlant.save_thought(user_id, "Время не движется, я движусь")
    atlant.add_message(user_id, "user", "Привет")

Атлант ≠ Юнона.
Юнона — Лицо (интерфейс).
Атлант — Гиппокамп (память).
"""

from .atlant import Atlant, get_atlant, Thought, DialogueMessage

__all__ = [
    "Atlant",
    "get_atlant",
    "Thought",
    "DialogueMessage"
]
