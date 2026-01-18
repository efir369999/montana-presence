#!/usr/bin/env python3
"""
Генератор 5-минутного отрывка: 1 серия. ОНЕ Монтана. Возрождение. ☀️

КВО 018 - 18.01.2026
Москва, Россия
"""

import os
import time
import subprocess
from pathlib import Path
import requests

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    print("❌ REPLICATE_API_TOKEN не установлен!")
    print("Установите: export REPLICATE_API_TOKEN='your-token'")
    exit(1)

# Пути
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "video_clips_5min"
OUTPUT_DIR.mkdir(exist_ok=True)

FINAL_OUTPUT = SCRIPT_DIR / "1_серия_ОНЕ_Монтана_5min.mp4"

# ============================================================================
# ПРОМПТЫ ДЛЯ ГЕНЕРАЦИИ (10 клипов × 30 сек)
# ============================================================================

CLIPS = [
    {
        "name": "01_darkness_to_code",
        "duration": 30,
        "prompt": (
            "Pure darkness transitioning to green matrix code emerging slowly, "
            "digital rain forming human silhouette, Animatrix style, "
            "cinematic atmosphere, 4K"
        )
    },
    {
        "name": "02_eyes_opening",
        "duration": 30,
        "prompt": (
            "Matrix code accelerating and coalescing, close-up of golden glowing eyes opening, "
            "young man with dark hair and intense gaze, cinematic lighting, "
            "particles effect, 4K"
        )
    },
    {
        "name": "03_architects_room",
        "duration": 30,
        "prompt": (
            "Man in flowing black coat standing in infinite monitor room, "
            "screens showing different timelines and matrix code, dark blue lighting, "
            "Architect's chamber Matrix style, cinematic wide shot"
        )
    },
    {
        "name": "04_time_freeze",
        "duration": 30,
        "prompt": (
            "Hand raised with golden energy, time freezing effect, "
            "particles suspended mid-air, everything stops in dramatic slow motion, "
            "cinematic power moment, 4K"
        )
    },
    {
        "name": "05_writing_in_air",
        "duration": 30,
        "prompt": (
            "Man writing in air with golden light trails, glowing letters forming in space "
            "against dark cosmic background, magical cinematic effect, "
            "bioluminescent text, 4K"
        )
    },
    {
        "name": "06_text_formation",
        "duration": 30,
        "prompt": (
            "Golden glowing text appearing: 'Another time, another place', "
            "floating luminous letters in cosmic void, cinematic typography, "
            "elegant font, particles around text"
        )
    },
    {
        "name": "07_dna_transformation",
        "duration": 30,
        "prompt": (
            "Golden letters transforming into rotating double helix DNA structure, "
            "molecular visualization, bioluminescent golden spiral, cosmic background, "
            "scientific art, smooth animation, 4K"
        )
    },
    {
        "name": "08_journey_to_core",
        "duration": 30,
        "prompt": (
            "DNA helix traveling toward glowing sphere core, matrix central system, "
            "golden spiral approaching bright luminous center, cosmic journey with camera following, "
            "cinematic movement"
        )
    },
    {
        "name": "09_injection_wave",
        "duration": 30,
        "prompt": (
            "DNA entering core sphere with explosion of golden light, shockwave spreading outward, "
            "matrix code transforming from green to gold in wave pattern, system-wide change, "
            "dramatic energy burst, Animatrix style"
        )
    },
    {
        "name": "10_credits",
        "duration": 30,
        "prompt": (
            "Black screen with elegant golden typography appearing, cinematic title cards: "
            "'ONE Montana', 'Resurgence', 'Клан Монтана', minimalist design, "
            "sophisticated credits style"
        )
    }
]

# ============================================================================
# ФУНКЦИИ
# ============================================================================

def generate_video_clip(clip_info: dict, output_path: Path) -> bool:
    """
    Генерирует видео клип через Replicate API (minimax/video-01)

    Args:
        clip_info: Словарь с name, prompt, duration
        output_path: Путь для сохранения MP4

    Returns:
        True если успешно, False если ошибка
    """
    try:
        print(f"🎬 Генерация: {clip_info['name']}")
        print(f"   Промпт: {clip_info['prompt'][:80]}...")

        # Запрос к Replicate API
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {REPLICATE_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "version": "minimax/video-01",  # или актуальная версия модели
                "input": {
                    "prompt": clip_info['prompt'],
                    "prompt_optimizer": True
                }
            }
        )

        if response.status_code != 201:
            print(f"   ❌ Ошибка API: {response.status_code}")
            print(f"   {response.text}")
            return False

        prediction = response.json()
        prediction_id = prediction['id']

        print(f"   ⏳ Ожидание генерации (ID: {prediction_id[:8]}...)")

        # Polling результата
        while True:
            time.sleep(5)

            check_response = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Token {REPLICATE_API_TOKEN}"}
            )

            if check_response.status_code != 200:
                print(f"   ❌ Ошибка проверки статуса")
                return False

            status_data = check_response.json()
            status = status_data['status']

            if status == 'succeeded':
                video_url = status_data['output']
                print(f"   ✓ Генерация завершена!")

                # Скачивание видео
                print(f"   📥 Скачивание...")
                video_response = requests.get(video_url)

                if video_response.status_code == 200:
                    output_path.write_bytes(video_response.content)
                    print(f"   ✓ Сохранено: {output_path.name}")
                    return True
                else:
                    print(f"   ❌ Ошибка скачивания")
                    return False

            elif status == 'failed':
                error = status_data.get('error', 'Unknown error')
                print(f"   ❌ Генерация провалилась: {error}")
                return False

            else:
                print(f"   ⏳ Статус: {status}")

    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return False

def generate_all_clips() -> list[Path]:
    """
    Генерирует все 10 клипов

    Returns:
        Список путей к успешно сгенерированным клипам
    """
    print("=" * 80)
    print("🎬 Генерация клипов для серии 1: ОНЕ Монтана. Возрождение")
    print("=" * 80)

    generated_clips = []

    for i, clip in enumerate(CLIPS, start=1):
        print(f"\n[{i}/10] {clip['name']}")

        output_path = OUTPUT_DIR / f"{clip['name']}.mp4"

        # Пропускаем если уже существует
        if output_path.exists():
            print(f"   ⏭️  Файл уже существует, пропускаем")
            generated_clips.append(output_path)
            continue

        # Генерация
        success = generate_video_clip(clip, output_path)

        if success:
            generated_clips.append(output_path)
        else:
            print(f"   ⚠️  Пропускаем этот клип")

        # Пауза между запросами (rate limit)
        if i < len(CLIPS):
            print("   💤 Пауза 20 сек (rate limit)...")
            time.sleep(20)

    print("\n" + "=" * 80)
    print(f"✓ Генерация завершена: {len(generated_clips)}/{len(CLIPS)} клипов")
    print("=" * 80)

    return generated_clips

def create_concat_file(clips: list[Path]) -> Path:
    """
    Создаёт файл для FFmpeg concat

    Args:
        clips: Список путей к видео файлам

    Returns:
        Путь к concat файлу
    """
    concat_file = OUTPUT_DIR / "concat_list.txt"

    with open(concat_file, 'w', encoding='utf-8') as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")

    print(f"✓ Создан concat файл: {concat_file}")
    return concat_file

def merge_videos(clips: list[Path], output: Path) -> bool:
    """
    Склеивает видео клипы в один файл

    Args:
        clips: Список путей к клипам
        output: Путь к финальному файлу

    Returns:
        True если успешно
    """
    try:
        print("\n" + "=" * 80)
        print("🎞️  Склейка видео клипов")
        print("=" * 80)

        # Создаём concat файл
        concat_file = create_concat_file(clips)

        # Временный файл для склейки
        temp_output = OUTPUT_DIR / "temp_concat.mp4"

        # FFmpeg склейка
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(temp_output)
        ]

        print(f"🔧 Запуск FFmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Ошибка FFmpeg:")
            print(result.stderr)
            return False

        # Перемещаем результат
        temp_output.rename(output)

        # Получаем длительность
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(output)
        ]

        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        if duration_result.returncode == 0:
            duration = float(duration_result.stdout.strip())
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"✓ Длительность: {minutes}:{seconds:02d}")

        print(f"✓ Финальный файл: {output}")
        print(f"✓ Размер: {output.stat().st_size / 1024 / 1024:.1f} MB")

        return True

    except Exception as e:
        print(f"❌ Ошибка при склейке: {e}")
        return False

def main():
    """
    Главная функция
    """
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "1 серия. ОНЕ Монтана. Возрождение. ☀️" + " " * 24 + "║")
    print("║" + " " * 30 + "5 минут" + " " * 41 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")

    # Этап 1: Генерация клипов
    clips = generate_all_clips()

    if not clips:
        print("\n❌ Не удалось сгенерировать ни одного клипа!")
        return

    # Этап 2: Склейка
    success = merge_videos(clips, FINAL_OUTPUT)

    if success:
        print("\n" + "=" * 80)
        print("🎉 Готово!")
        print("=" * 80)
        print(f"\n📁 Финальный файл:")
        print(f"   {FINAL_OUTPUT}")
        print(f"\n💡 Следующий шаг:")
        print(f"   1. Подготовить аудио дорожку (музыка + голос)")
        print(f"   2. Добавить аудио через FFmpeg:")
        print(f"      ffmpeg -i '{FINAL_OUTPUT}' -i audio.mp3 \\")
        print(f"             -c:v copy -c:a aac -b:a 192k -shortest \\")
        print(f"             final_with_audio.mp4")
        print("\n")
    else:
        print("\n❌ Ошибка при финальной сборке")

if __name__ == "__main__":
    main()
