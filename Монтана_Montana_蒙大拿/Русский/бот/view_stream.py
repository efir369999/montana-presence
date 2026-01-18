#!/usr/bin/env python3
# view_stream.py
# Просмотр потока сырых мыслей

import json
from pathlib import Path
from datetime import datetime

STREAM_FILE = Path(__file__).parent / "data" / "stream.jsonl"

def view_stream(limit: int = 50):
    """Показать последние N мыслей из потока"""
    if not STREAM_FILE.exists():
        print("Ɉ Поток пуст")
        return

    thoughts = []
    with open(STREAM_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                thoughts.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not thoughts:
        print("Ɉ Поток пуст")
        return

    # Последние N
    recent = thoughts[-limit:]

    print(f"Ɉ Поток мыслей Montana ({len(recent)} из {len(thoughts)})\n")

    for entry in recent:
        username = entry.get('username', 'аноним')
        timestamp = entry.get('timestamp', '')
        thought = entry.get('thought', '')
        lang = entry.get('lang', 'ru')

        # Парсим timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime('%Y-%m-%d %H:%M')
        except:
            time_str = timestamp

        print(f"[{time_str}] @{username} ({lang})")
        print(f"  {thought}\n")

if __name__ == "__main__":
    import sys

    limit = 50
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass

    view_stream(limit)
