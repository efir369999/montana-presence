#!/usr/bin/env python3
"""
Массовая генерация аудио для всех глав Благаявести
"""

import asyncio
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
SCRIPT = Path(__file__).parent / "generate_audio_smart.py"


async def main():
    # Находим все .md файлы (кроме служебных)
    md_files = sorted([
        f for f in BASE_DIR.glob("*.md")
        if not f.name.startswith("_")
           and not f.name.startswith("SORA")
           and not f.name.startswith("VK")
    ])

    if not md_files:
        print("✗ Не найдено .md файлов")
        return

    print("=" * 70)
    print("МАССОВАЯ ГЕНЕРАЦИЯ АУДИО")
    print("=" * 70)
    print(f"\nНайдено файлов: {len(md_files)}")
    print()

    for i, md_file in enumerate(md_files, 1):
        print(f"\n[{i}/{len(md_files)}] {md_file.name}")
        print("-" * 70)

        # Запускаем генерацию для каждого файла
        result = subprocess.run([
            "python3",
            str(SCRIPT),
            md_file.name
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"✗ Ошибка:")
            print(result.stderr)

    print("\n" + "=" * 70)
    print("ВСЕ ФАЙЛЫ ОБРАБОТАНЫ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
