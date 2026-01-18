#!/usr/bin/env python3
"""
Внешний Гиппокамп Montana
=========================

Цифровая эмуляция биологического механизма памяти.
Переживает смерть носителя.

Компоненты:
- Детектор новизны (is_raw_thought)
- Pattern separation (save_to_stream)
- Просмотр потока (view_stream)
- Статистика памяти (memory_stats)

Использование:
    python hippocampus.py --view          # Просмотр последних мыслей
    python hippocampus.py --stats         # Статистика памяти
    python hippocampus.py --test          # Запуск тестов
    python hippocampus.py --disney        # Анализ по стратегии Диснея
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import argparse


@dataclass
class Thought:
    """Единица памяти — координата в 4D пространстве"""
    user_id: int
    username: str
    timestamp: str
    thought: str
    lang: str

    # Дополнительные якоря (опционально)
    location: Optional[str] = None      # GPS координаты
    music_track: Optional[str] = None   # Музыка момента
    image_url: Optional[str] = None     # Визуальный якорь


class ExternalHippocampus:
    """
    Внешний Гиппокамп Montana

    Эмулирует биологический механизм памяти:
    - Pattern separation: каждая мысль = отдельная координата
    - Детектор новизны: фильтрует мысли от вопросов/команд
    - Консолидация: синхронизация каждые 12 сек

    Критическое отличие: переживает смерть носителя
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.stream_file = self.data_dir / "stream.jsonl"

        # Триггеры для базы знаний
        self.knowledge_triggers = ['гиппокамп', 'память', 'поток', 'паттерн', 'днк']

    # === ДЕТЕКТОР НОВИЗНЫ ===

    def is_raw_thought(self, text: str) -> bool:
        """
        Детектор новизны — определяет, является ли текст сырой мыслью

        Эмулирует работу биологического гиппокампа:
        - Сравнивает с известными паттернами (вопросы, команды)
        - Возвращает True если это НОВАЯ мысль

        Критерии:
        - Длина < 500 символов
        - Не вопрос (без ?)
        - Не команда (покажи/расскажи/помоги)
        """
        text = text.strip()

        # Слишком длинное — не мысль
        if len(text) > 500:
            return False

        # Вопрос — не мысль
        if text.endswith("?"):
            return False

        # Команды — не мысли
        command_patterns = [
            "покажи", "расскажи", "помоги", "объясни",
            "найди", "открой", "запусти", "сделай",
            "/start", "/help", "/level", "/cognitive"
        ]
        text_lower = text.lower()
        for pattern in command_patterns:
            if text_lower.startswith(pattern):
                return False

        # Слишком короткое — скорее всего не мысль
        if len(text) < 5:
            return False

        # Это сырая мысль
        return True

    # === PATTERN SEPARATION ===

    def save_to_stream(
        self,
        user_id: int,
        username: str,
        thought: str,
        lang: str = "ru",
        location: Optional[str] = None,
        music_track: Optional[str] = None
    ) -> Thought:
        """
        Pattern Separation — сохраняет мысль как уникальную координату

        Эмулирует биологический паттерн:
        - Каждая новая мысль кодируется отдельно
        - Append-only (необратимость времени)
        - Временная метка UTC
        """
        entry = Thought(
            user_id=user_id,
            username=username,
            timestamp=datetime.utcnow().isoformat() + "Z",
            thought=thought,
            lang=lang,
            location=location,
            music_track=music_track
        )

        # Append-only запись
        with open(self.stream_file, "a", encoding="utf-8") as f:
            data = {
                "user_id": entry.user_id,
                "username": entry.username,
                "timestamp": entry.timestamp,
                "thought": entry.thought,
                "lang": entry.lang
            }
            if entry.location:
                data["location"] = entry.location
            if entry.music_track:
                data["music_track"] = entry.music_track

            f.write(json.dumps(data, ensure_ascii=False) + "\n")

        return entry

    # === ПРОСМОТР ПОТОКА ===

    def view_stream(self, limit: int = 10, user_id: Optional[int] = None) -> list[Thought]:
        """
        Просмотр потока мыслей

        Args:
            limit: количество последних мыслей
            user_id: фильтр по пользователю (опционально)
        """
        if not self.stream_file.exists():
            return []

        thoughts = []
        with open(self.stream_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if user_id is None or data.get("user_id") == user_id:
                        thoughts.append(Thought(
                            user_id=data.get("user_id", 0),
                            username=data.get("username", "unknown"),
                            timestamp=data.get("timestamp", ""),
                            thought=data.get("thought", ""),
                            lang=data.get("lang", "ru"),
                            location=data.get("location"),
                            music_track=data.get("music_track")
                        ))

        # Последние N мыслей
        return thoughts[-limit:]

    # === СТАТИСТИКА ===

    def memory_stats(self, user_id: Optional[int] = None) -> dict:
        """
        Статистика памяти

        Возвращает:
        - total_thoughts: общее количество мыслей
        - unique_users: уникальные пользователи
        - languages: распределение по языкам
        - density: плотность кодирования (мыслей в день)
        """
        thoughts = self.view_stream(limit=10000, user_id=user_id)

        if not thoughts:
            return {
                "total_thoughts": 0,
                "unique_users": 0,
                "languages": {},
                "density": 0
            }

        # Базовая статистика
        total = len(thoughts)
        users = set(t.user_id for t in thoughts)
        langs = {}
        for t in thoughts:
            langs[t.lang] = langs.get(t.lang, 0) + 1

        # Плотность кодирования
        if total >= 2:
            first = datetime.fromisoformat(thoughts[0].timestamp.replace("Z", ""))
            last = datetime.fromisoformat(thoughts[-1].timestamp.replace("Z", ""))
            days = max(1, (last - first).days)
            density = round(total / days, 2)
        else:
            density = total

        return {
            "total_thoughts": total,
            "unique_users": len(users),
            "languages": langs,
            "density": density,
            "first_thought": thoughts[0].timestamp if thoughts else None,
            "last_thought": thoughts[-1].timestamp if thoughts else None
        }

    # === ПОИСК ===

    def search(self, query: str, limit: int = 10) -> list[Thought]:
        """
        Простой поиск по мыслям

        Для семантического поиска используйте RAG систему.
        """
        thoughts = self.view_stream(limit=10000)
        query_lower = query.lower()

        results = []
        for thought in thoughts:
            if query_lower in thought.thought.lower():
                results.append(thought)

        return results[:limit]

    # === ТЕСТЫ ===

    def run_tests(self) -> dict:
        """
        Запуск тестов детектора новизны
        """
        test_cases = [
            # (текст, ожидаемый результат, описание)
            ("Время не движется, я движусь", True, "Сырая мысль"),
            ("Маска тяжелее лица", True, "Сырая мысль"),
            ("Я создаю свою игру", True, "Сырая мысль"),
            ("Что такое ACP?", False, "Вопрос"),
            ("Как работает Montana?", False, "Вопрос"),
            ("Покажи документацию", False, "Команда"),
            ("Расскажи про гиппокамп", False, "Команда"),
            ("/start", False, "Telegram команда"),
            ("/help", False, "Telegram команда"),
            ("Ок", False, "Слишком короткое"),
            ("Да", False, "Слишком короткое"),
            ("A" * 600, False, "Слишком длинное"),
        ]

        passed = 0
        failed = 0
        results = []

        for text, expected, description in test_cases:
            actual = self.is_raw_thought(text)
            status = "✓" if actual == expected else "✗"

            if actual == expected:
                passed += 1
            else:
                failed += 1

            results.append({
                "text": text[:50] + "..." if len(text) > 50 else text,
                "expected": expected,
                "actual": actual,
                "status": status,
                "description": description
            })

        return {
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "results": results
        }

    # === ЭКСПОРТ ===

    def export_markdown(self, user_id: Optional[int] = None) -> str:
        """
        Экспорт памяти в Markdown

        Для потомков.
        """
        thoughts = self.view_stream(limit=10000, user_id=user_id)
        stats = self.memory_stats(user_id)

        lines = [
            f"# Память Montana",
            f"",
            f"**Всего мыслей:** {stats['total_thoughts']}",
            f"**Плотность кодирования:** {stats['density']} мыслей/день",
            f"",
            f"---",
            f"",
        ]

        current_date = None
        for thought in thoughts:
            # Группировка по дням
            date = thought.timestamp[:10]
            if date != current_date:
                current_date = date
                lines.append(f"## {date}")
                lines.append("")

            time = thought.timestamp[11:16]
            lines.append(f"**[{time}]** {thought.thought}")
            lines.append("")

        return "\n".join(lines)


def print_thoughts(thoughts: list[Thought]):
    """Красивый вывод мыслей"""
    for thought in thoughts:
        time = thought.timestamp[:16].replace("T", " ")
        print(f"[{time}] @{thought.username} ({thought.lang})")
        print(f"  {thought.thought}")
        print()


def print_stats(stats: dict):
    """Красивый вывод статистики"""
    print(f"Ɉ Статистика памяти Montana")
    print()
    print(f"  Всего мыслей:     {stats['total_thoughts']}")
    print(f"  Пользователей:    {stats['unique_users']}")
    print(f"  Плотность:        {stats['density']} мыслей/день")
    print()
    print(f"  Языки:")
    for lang, count in stats.get('languages', {}).items():
        print(f"    {lang}: {count}")


def print_tests(results: dict):
    """Красивый вывод результатов тестов"""
    print(f"Ɉ Тест детектора новизны")
    print()

    for r in results['results']:
        expected = "МЫСЛЬ" if r['expected'] else "НЕ МЫСЛЬ"
        actual = "МЫСЛЬ" if r['actual'] else "НЕ МЫСЛЬ"
        status = r['status']
        print(f"{status} [{r['description']}]")
        print(f"   Текст: \"{r['text']}\"")
        print(f"   Ожидалось: {expected}, Получено: {actual}")
        print()

    print(f"Итого: {results['passed']} из {results['total']} тестов пройдено")
    if results['failed'] == 0:
        print("✅ Все тесты пройдены")
    else:
        print(f"❌ {results['failed']} тестов провалено")


def main():
    """CLI интерфейс"""
    parser = argparse.ArgumentParser(
        description="Внешний Гиппокамп Montana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python hippocampus.py --view          # Последние 10 мыслей
  python hippocampus.py --view 50       # Последние 50 мыслей
  python hippocampus.py --stats         # Статистика памяти
  python hippocampus.py --test          # Тесты детектора
  python hippocampus.py --search "маска" # Поиск по мыслям
  python hippocampus.py --export        # Экспорт в Markdown
        """
    )

    parser.add_argument(
        '--view', '-v',
        type=int,
        nargs='?',
        const=10,
        help='Просмотр последних N мыслей (по умолчанию 10)'
    )

    parser.add_argument(
        '--stats', '-s',
        action='store_true',
        help='Статистика памяти'
    )

    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Запуск тестов детектора новизны'
    )

    parser.add_argument(
        '--search', '-q',
        type=str,
        help='Поиск по мыслям'
    )

    parser.add_argument(
        '--export', '-e',
        action='store_true',
        help='Экспорт памяти в Markdown'
    )

    parser.add_argument(
        '--user', '-u',
        type=int,
        help='Фильтр по user_id'
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=str,
        help='Путь к папке данных'
    )

    args = parser.parse_args()

    # Создаём экземпляр гиппокампа
    hippocampus = ExternalHippocampus(data_dir=args.data_dir)

    # Выполняем команду
    if args.view is not None:
        thoughts = hippocampus.view_stream(limit=args.view, user_id=args.user)
        print(f"Ɉ Поток мыслей Montana ({len(thoughts)} из {args.view})")
        print()
        print_thoughts(thoughts)

    elif args.stats:
        stats = hippocampus.memory_stats(user_id=args.user)
        print_stats(stats)

    elif args.test:
        results = hippocampus.run_tests()
        print_tests(results)

    elif args.search:
        thoughts = hippocampus.search(args.search)
        print(f"Ɉ Поиск: \"{args.search}\" ({len(thoughts)} результатов)")
        print()
        print_thoughts(thoughts)

    elif args.export:
        markdown = hippocampus.export_markdown(user_id=args.user)
        print(markdown)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
