#!/usr/bin/env python3
"""
Экспорт потока мыслей Montana в Markdown
========================================

Использование:
    python export_stream.py                    # Все мысли
    python export_stream.py --today            # Только сегодня
    python export_stream.py --week             # Последняя неделя
    python export_stream.py --month            # Последний месяц
    python export_stream.py --from 2026-01-15  # С определённой даты
    python export_stream.py --from 2026-01-10 --to 2026-01-15  # Период
    python export_stream.py --output мои_мысли.md  # В конкретный файл
"""

import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path


# Путь к потоку мыслей
STREAM_FILE = Path(__file__).parent / "data" / "stream.jsonl"


def load_stream() -> list[dict]:
    """Загрузить все мысли из потока"""
    if not STREAM_FILE.exists():
        return []

    thoughts = []
    with open(STREAM_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    thoughts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return thoughts


def filter_by_date(thoughts: list[dict], from_date: str = None, to_date: str = None) -> list[dict]:
    """Фильтровать мысли по дате"""
    if not from_date and not to_date:
        return thoughts

    filtered = []
    for t in thoughts:
        ts = t.get("timestamp", "")[:10]  # YYYY-MM-DD

        if from_date and ts < from_date:
            continue
        if to_date and ts > to_date:
            continue

        filtered.append(t)

    return filtered


def to_markdown(thoughts: list[dict], title: str = "Поток мыслей Montana") -> str:
    """Конвертировать мысли в Markdown"""
    if not thoughts:
        return f"# {title}\n\nПоток пуст. Напиши первую мысль в @junomontanaagibot"

    lines = [
        f"# {title}",
        "",
        f"**Всего мыслей:** {len(thoughts)}",
        f"**Период:** {thoughts[0]['timestamp'][:10]} — {thoughts[-1]['timestamp'][:10]}",
        "",
        "---",
        ""
    ]

    # Группируем по дням
    current_date = None
    for t in thoughts:
        date = t.get("timestamp", "")[:10]
        time = t.get("timestamp", "")[11:16]
        thought = t.get("thought", "")
        username = t.get("username", "аноним")
        lang = t.get("lang", "ru")

        # Новый день — новый заголовок
        if date != current_date:
            current_date = date
            lines.append(f"## {date}")
            lines.append("")

        # Мысль
        lines.append(f"**[{time}]** @{username} ({lang})")
        lines.append(f"> {thought}")
        lines.append("")

    # Подпись
    lines.extend([
        "---",
        "",
        f"*Экспортировано: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "金元Ɉ Montana — Внешний гиппокамп"
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Экспорт потока мыслей Montana в Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python export_stream.py                      # Все мысли
  python export_stream.py --today              # Сегодня
  python export_stream.py --week               # Неделя
  python export_stream.py --from 2026-01-15    # С даты
  python export_stream.py -o мысли.md          # В файл
        """
    )

    # Периоды
    parser.add_argument('--today', action='store_true', help='Только сегодня')
    parser.add_argument('--week', action='store_true', help='Последняя неделя')
    parser.add_argument('--month', action='store_true', help='Последний месяц')
    parser.add_argument('--from', dest='from_date', type=str, help='С даты (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date', type=str, help='По дату (YYYY-MM-DD)')

    # Вывод
    parser.add_argument('--output', '-o', type=str, help='Файл для сохранения')
    parser.add_argument('--print', '-p', action='store_true', help='Вывести в консоль')

    args = parser.parse_args()

    # Определяем период
    today = datetime.now().strftime('%Y-%m-%d')
    from_date = args.from_date
    to_date = args.to_date
    title = "Поток мыслей Montana"

    if args.today:
        from_date = today
        to_date = today
        title = f"Мысли за {today}"
    elif args.week:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        title = "Мысли за последнюю неделю"
    elif args.month:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        title = "Мысли за последний месяц"
    elif from_date:
        if to_date:
            title = f"Мысли с {from_date} по {to_date}"
        else:
            title = f"Мысли с {from_date}"

    # Загружаем и фильтруем
    thoughts = load_stream()
    thoughts = filter_by_date(thoughts, from_date, to_date)

    # Конвертируем в Markdown
    markdown = to_markdown(thoughts, title)

    # Выводим или сохраняем
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(markdown, encoding='utf-8')
        print(f"✓ Сохранено в {output_path}")
        print(f"  Мыслей: {len(thoughts)}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
