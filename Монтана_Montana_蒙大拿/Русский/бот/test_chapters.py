#!/usr/bin/env python3
# Тест доступности файлов глав

from dialogue_coordinator import get_coordinator
from pathlib import Path

coord = get_coordinator(Path("/root/junona_bot"))
print(f"Chapters dir: {coord.chapters_dir}")
print(f"Exists: {coord.chapters_dir.exists()}")

for i in range(3):
    chapter = coord.get_chapter_files(i)
    print(f"\nChapter {i}: {chapter['name']}")
    print(f"  Text exists: {chapter['text'] and chapter['text'].exists()}")
    print(f"  Audio exists: {chapter['audio'] and chapter['audio'].exists()}")
    if chapter['audio']:
        print(f"  Audio path: {chapter['audio']}")
