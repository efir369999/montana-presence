#!/usr/bin/env python3
"""
Скрипт для скачивания образцов голосов кандидаток на роль #К
Montana Voice Casting System
18.01.2026
"""

import os
import subprocess
from pathlib import Path

# Папка для сохранения образцов
OUTPUT_DIR = Path(__file__).parent / "образцы"
OUTPUT_DIR.mkdir(exist_ok=True)

# Образцы голосов кандидаток с YouTube
VOICE_SAMPLES = {
    "Стася_Милославская": [
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # ЗАМЕНИТЬ НА РЕАЛЬНОЕ ИНТЕРВЬЮ
            "name": "Стася_интервью_Лёд",
            "start": "0:30",  # начало фрагмента
            "duration": "2:00"  # длительность
        }
    ],
    "Александра_Бортич": [
        {
            "url": "https://www.youtube.com/watch?v=PLACEHOLDER",  # ЗАМЕНИТЬ
            "name": "Александра_интервью",
            "start": "1:00",
            "duration": "2:00"
        }
    ],
    "Виталия_Корниенко": [
        {
            "url": "https://www.youtube.com/watch?v=PLACEHOLDER",  # ЗАМЕНИТЬ
            "name": "Виталия_Дылды_интервью",
            "start": "0:45",
            "duration": "2:00"
        }
    ],
    "Полина_Гухман": [
        {
            "url": "https://www.youtube.com/watch?v=PLACEHOLDER",  # ЗАМЕНИТЬ
            "name": "Полина_интервью",
            "start": "1:15",
            "duration": "2:00"
        }
    ],
    "Милана_Хаметова": [
        {
            "url": "https://www.youtube.com/watch?v=PLACEHOLDER",  # ЗАМЕНИТЬ
            "name": "Милана_Гранд_интервью",
            "start": "0:20",
            "duration": "2:00"
        }
    ]
}


def download_audio_sample(actress_name, sample_info):
    """
    Скачивает фрагмент аудио с YouTube

    Args:
        actress_name: имя актрисы
        sample_info: словарь с url, name, start, duration
    """
    output_file = OUTPUT_DIR / f"{actress_name}_{sample_info['name']}.mp3"

    if output_file.exists():
        print(f"✓ Уже скачано: {output_file.name}")
        return

    print(f"⬇️  Скачиваю: {actress_name} - {sample_info['name']}")

    # yt-dlp команда для скачивания только аудио с вырезкой фрагмента
    cmd = [
        "yt-dlp",
        "-x",  # только аудио
        "--audio-format", "mp3",
        "--audio-quality", "0",  # лучшее качество
        "--download-sections", f"*{sample_info['start']}-{sample_info['duration']}",
        "-o", str(output_file.with_suffix("")),
        sample_info['url']
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"✅ Скачано: {output_file.name}")
        else:
            print(f"❌ Ошибка при скачивании {actress_name}")
            print(f"   {result.stderr}")
    except subprocess.TimeoutExpired:
        print(f"⏱️  Таймаут при скачивании {actress_name}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def download_all_samples():
    """Скачивает все образцы голосов"""
    print("\n🎙️  MONTANA VOICE CASTING - Скачивание образцов\n")
    print("=" * 60)

    total = sum(len(samples) for samples in VOICE_SAMPLES.values())
    current = 0

    for actress_name, samples in VOICE_SAMPLES.items():
        print(f"\n📥 {actress_name}:")
        for sample in samples:
            current += 1
            print(f"   [{current}/{total}]", end=" ")
            download_audio_sample(actress_name, sample)

    print("\n" + "=" * 60)
    print(f"✅ Готово! Образцы сохранены в: {OUTPUT_DIR}")
    print(f"📁 Всего файлов: {len(list(OUTPUT_DIR.glob('*.mp3')))}")


def search_videos(actress_name, query):
    """
    Поиск видео на YouTube по запросу

    Args:
        actress_name: имя актрисы
        query: поисковый запрос
    """
    print(f"\n🔍 Поиск для {actress_name}: {query}")

    cmd = [
        "yt-dlp",
        "--get-title",
        "--get-id",
        "--get-duration",
        f"ytsearch5:{query}"  # первые 5 результатов
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i in range(0, len(lines), 3):
                if i+2 < len(lines):
                    title = lines[i]
                    video_id = lines[i+1]
                    duration = lines[i+2]
                    print(f"   📹 {title}")
                    print(f"      https://youtube.com/watch?v={video_id} ({duration})")
        else:
            print(f"   ❌ Ошибка поиска")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")


def search_all_actresses():
    """Ищет интервью для всех актрис"""
    print("\n🔍 ПОИСК ИНТЕРВЬЮ НА YOUTUBE\n")
    print("=" * 60)

    searches = {
        "Стася_Милославская": "Стася Милославская интервью Лёд",
        "Александра_Бортич": "Александра Бортич интервью подкаст",
        "Виталия_Корниенко": "Виталия Корниенко интервью Дылды",
        "Полина_Гухман": "Полина Гухман интервью Мажор",
        "Милана_Хаметова": "Милана Хаметова интервью Гранд"
    }

    for actress, query in searches.items():
        search_videos(actress, query)

    print("\n" + "=" * 60)
    print("✅ Поиск завершен!")
    print("💡 Выбери понравившиеся видео и обнови URLs в скрипте")


if __name__ == "__main__":
    import sys

    print("\n" + "=" * 60)
    print("🎭 MONTANA VOICE CASTING SYSTEM")
    print("   Кастинг роли #К (КрасноеПлатье)")
    print("   18.01.2026")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "--search":
        # Режим поиска
        search_all_actresses()
    else:
        # Режим скачивания
        print("\n⚠️  ВНИМАНИЕ: Перед скачиванием обнови URLs в скрипте!")
        print("   Запусти с --search чтобы найти видео\n")

        response = input("Продолжить скачивание? (y/n): ")
        if response.lower() == 'y':
            download_all_samples()
        else:
            print("\n💡 Сначала запусти: python download_voice_samples.py --search")
            print("   Чтобы найти подходящие видео")
