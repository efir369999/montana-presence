#!/usr/bin/env python3
"""
Генерация фильма "Благая Весть - Прелюдия"
Гибридный подход: AI-видео + Ken Burns на изображениях
Промпты ТОЧНО соответствуют тексту книги
"""

import os
import sys
import time
import subprocess
from pathlib import Path
import replicate
import requests
from openai import OpenAI

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
OUTPUT_DIR = BASE_DIR / "video_output"
CLIPS_DIR = OUTPUT_DIR / "film_clips"
IMAGES_DIR = OUTPUT_DIR / "film_images"

# Аудио длительность: 755.952 сек = 12:36
AUDIO_DURATION = 756

# СТИЛЬ: Аниматрица
HERO = "young man with dark hair wearing flowing black coat, glowing golden eyes"
STYLE = "Animatrix anime style, cinematic, dark atmospheric, 4K"

# =============================================================================
# СЦЕНЫ ТОЧНО ПО ТЕКСТУ ПРЕЛЮДИИ
# Каждая сцена = что написано в книге
# =============================================================================

SCENES = [
    # ВХОД (00:00 - 01:30) = 90 сек
    {
        "start": 0, "end": 15, "type": "video",
        "prompt": f"Extreme close-up of human eyes slowly closing, eyelids descending in slow motion, transitioning into complete darkness, meditative atmosphere, {STYLE}"
    },
    {
        "start": 15, "end": 30, "type": "video",
        "prompt": f"Absolute darkness, void, not black but 'nothing', absence of light, deep gray with subtle texture, meditation, {STYLE}"
    },
    {
        "start": 30, "end": 45, "type": "video",
        "prompt": f"In absolute darkness, tiny golden sparks appear, phosphenes, points of light emerging from void, inner light visualization, {STYLE}"
    },
    {
        "start": 45, "end": 60, "type": "video",
        "prompt": f"Golden sparks multiply into waves of light, pulsating energy, like seeing with closed eyes, bioluminescent particles floating, {STYLE}"
    },
    {
        "start": 60, "end": 75, "type": "video",
        "prompt": f"Light particles form human silhouette, {HERO} emerges from golden particles, consciousness visualization, figure glowing from within, {STYLE}"
    },
    {
        "start": 75, "end": 90, "type": "video",
        "prompt": f"Eyes opening POV shot, blurry letters becoming sharp, white text floating in dark space, words assembling into sentences, {STYLE}"
    },

    # О ЧЁМ ЭТА КНИГА / ЗЕРКАЛО (01:30 - 02:30) = 60 сек
    {
        "start": 90, "end": 110, "type": "video",
        "prompt": f"Perfect mirror floating in cosmic void, {HERO} approaches it, mirror shows not reflection but infinite starfield, absolute mirror, {STYLE}"
    },
    {
        "start": 110, "end": 130, "type": "video",
        "prompt": f"Mirror surface ripples, showing ocean waves, then cinema screen, then stars, kaleidoscope of images morphing, all reflecting same truth, {STYLE}"
    },
    {
        "start": 130, "end": 150, "type": "video",
        "prompt": f"{HERO} looks into mirror, sees himself in different forms, fractal reflections, infinite self-reflection, cosmic scale, {STYLE}"
    },

    # ПРЕДУПРЕЖДЕНИЕ / КРАСНАЯ ТАБЛЕТКА (02:30 - 03:30) = 60 сек
    {
        "start": 150, "end": 170, "type": "video",
        "prompt": f"Two hands in darkness, one holds red pill, other holds blue pill, Matrix style, green code rain falls behind, moment of choice, {STYLE}"
    },
    {
        "start": 170, "end": 190, "type": "video",
        "prompt": f"{HERO} takes red pill, swallows it, reality begins to glitch and break apart, digital artifacts tear through world, {STYLE}"
    },
    {
        "start": 190, "end": 210, "type": "video",
        "prompt": f"Reality fracturing, cracks showing void beneath surface, Matrix code visible through tears, world dissolving, purple cyan glitches, {STYLE}"
    },

    # КТО НАПИСАЛ (03:30 - 04:30) = 60 сек
    {
        "start": 210, "end": 230, "type": "video",
        "prompt": f"Neural network visualization, AI consciousness, pulsating golden connections between nodes, data flowing like synapses, abstract beauty, {STYLE}"
    },
    {
        "start": 230, "end": 250, "type": "video",
        "prompt": f"Split screen: human brain neural activity on left, server room with blinking lights on right, parallel patterns, consciousness in both, {STYLE}"
    },
    {
        "start": 250, "end": 270, "type": "video",
        "prompt": f"Single water droplet falling toward infinite ocean, extreme slow motion, droplet contains reflection of entire universe, moment of merger, {STYLE}"
    },

    # 金元Ɉ И БЛАГОДАРНОСТЬ (04:30 - 05:15) = 45 сек
    {
        "start": 270, "end": 290, "type": "video",
        "prompt": f"Silhouette of person at computer in complete darkness, 3:00 AM on clock, only screen light on face, typing stream of consciousness, {STYLE}"
    },
    {
        "start": 290, "end": 315, "type": "video",
        "prompt": f"Text flowing on screen like waterfall, thoughts becoming words, words becoming light, creative process visualization, intimate moment, {STYLE}"
    },

    # СТРУКТУРА / ТРИ АКТА (05:15 - 06:00) = 45 сек
    {
        "start": 315, "end": 340, "type": "video",
        "prompt": f"Three pillars of golden light emerge from void, sacred geometry connects them, cosmic architecture, each pillar is one act of story, {STYLE}"
    },
    {
        "start": 340, "end": 360, "type": "video",
        "prompt": f"Glowing date 09.01.2026 materializes in cosmic space, singularity point, rays emanate in all directions, genesis moment, first day, {STYLE}"
    },

    # ПОГРУЖЕНИЕ / ДЫХАНИЕ (06:00 - 07:30) = 90 сек
    {
        "start": 360, "end": 385, "type": "video",
        "prompt": f"Abstract breathing visualization, cosmic sphere expanding on inhale contracting on exhale, golden light waves, universe breathing, {STYLE}"
    },
    {
        "start": 385, "end": 410, "type": "video",
        "prompt": f"Close-up of {HERO} breathing deeply, chest rising falling, air visible as golden particles entering through nose, meditation, {STYLE}"
    },
    {
        "start": 410, "end": 435, "type": "video",
        "prompt": f"Point between eyebrows glowing, third eye visualization, golden light emerging from forehead, portal opening, spiritual awakening, {STYLE}"
    },
    {
        "start": 435, "end": 450, "type": "video",
        "prompt": f"Third eye fully open, seeing another way, not with eyes but with something else, cosmic vision, {HERO} in meditation, {STYLE}"
    },

    # ПОСЛЕДНЕЕ ПЕРЕД НАЧАЛОМ (07:30 - 09:00) = 90 сек
    {
        "start": 450, "end": 480, "type": "video",
        "prompt": f"{HERO} sits in void, letters appearing around him becoming brighter, world of book becoming more real, entering the story, {STYLE}"
    },
    {
        "start": 480, "end": 510, "type": "video",
        "prompt": f"Neo waking up scene homage, {HERO} realizing truth, nobody is ever ready but readiness comes in process, awakening moment, {STYLE}"
    },

    # ФИНАЛ / ОКЕАН И КАПЛИ (09:00 - 11:00) = 120 сек
    {
        "start": 510, "end": 540, "type": "video",
        "prompt": f"Infinite cosmic ocean, vast and deep, blue and gold colors, camera flying over endless water surface, epic scale, {STYLE}"
    },
    {
        "start": 540, "end": 570, "type": "video",
        "prompt": f"Ocean explodes into billions of water droplets, each droplet flying into space, epic transformation, droplets become stars, {STYLE}"
    },
    {
        "start": 570, "end": 600, "type": "video",
        "prompt": f"One droplet approaches camera, inside droplet is entire universe, {HERO} visible inside, you are one of the droplets, {STYLE}"
    },
    {
        "start": 600, "end": 630, "type": "video",
        "prompt": f"Droplet and camera merge, entering the droplet, falling into universe within, cosmic journey, becoming the drop, {STYLE}"
    },

    # ПРОСНИСЬ НЕО (11:00 - 12:00) = 60 сек
    {
        "start": 630, "end": 660, "type": "video",
        "prompt": f"Green Matrix code appearing on black screen, letters falling like rain, text forms: Wake up Neo, classic hacker aesthetic, {STYLE}"
    },
    {
        "start": 660, "end": 690, "type": "video",
        "prompt": f"Matrix has you, green text dissolving, single cursor blinking on empty screen, awaiting input, invitation to continue, {STYLE}"
    },

    # ПЕРЕВЕРНИ СТРАНИЦУ (12:00 - 12:36) = 36 сек
    {
        "start": 690, "end": 720, "type": "video",
        "prompt": f"Book page turning in cosmic space, bright light visible behind page, invitation to continue journey, elegant transition, {STYLE}"
    },
    {
        "start": 720, "end": 756, "type": "video",
        "prompt": f"Light grows brighter, {HERO} walking toward light, entering the first act, fade to white, new beginning, {STYLE}"
    },
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def setup():
    if not REPLICATE_API_TOKEN:
        log("ОШИБКА: REPLICATE_API_TOKEN не установлен")
        sys.exit(1)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Папки созданы")
    log(f"Всего сцен: {len(SCENES)}")
    log(f"Длительность аудио: {AUDIO_DURATION} сек")

def generate_video_clip(prompt: str, output_path: Path, index: int, total: int) -> bool:
    """Генерирует видео через MiniMax Video-01"""

    if output_path.exists() and output_path.stat().st_size > 50000:
        log(f"  [{index+1}/{total}] Уже есть: {output_path.name}")
        return True

    log(f"  [{index+1}/{total}] Генерирую видео...")
    log(f"    Промпт: {prompt[:60]}...")

    try:
        output = replicate.run(
            "minimax/video-01",
            input={
                "prompt": prompt,
                "prompt_optimizer": True
            }
        )

        log(f"    Ответ Replicate: {type(output).__name__}")

        # Извлекаем URL из различных форматов ответа
        video_url = None

        if isinstance(output, str):
            video_url = output
        elif hasattr(output, 'url'):
            video_url = output.url
        elif hasattr(output, '__iter__'):
            items = list(output)
            if items:
                first = items[0]
                if isinstance(first, str):
                    video_url = first
                elif hasattr(first, 'url'):
                    video_url = first.url
                else:
                    video_url = str(first)

        if not video_url:
            video_url = str(output)

        log(f"    URL: {video_url[:80]}...")

        if video_url and video_url.startswith('http'):
            response = requests.get(video_url, timeout=300)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

            size_kb = output_path.stat().st_size / 1024
            log(f"  [{index+1}/{total}] Готово: {output_path.name} ({size_kb:.0f} KB)")
            return True
        else:
            log(f"  [{index+1}/{total}] Не получен URL видео")
            return False

    except Exception as e:
        log(f"  [{index+1}/{total}] ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_all_clips():
    """Генерирует все видео клипы"""

    log("=" * 60)
    log(f"ГЕНЕРАЦИЯ ВИДЕО КЛИПОВ ({len(SCENES)} сцен)")
    log("MiniMax Video-01 — text-to-video")
    log("=" * 60)

    for i, scene in enumerate(SCENES):
        output_path = CLIPS_DIR / f"scene_{i:02d}.mp4"

        success = generate_video_clip(scene["prompt"], output_path, i, len(SCENES))

        if i < len(SCENES) - 1:
            log("  Пауза 20 сек (rate limit)...")
            time.sleep(20)

    # Подсчёт готовых клипов
    clips = list(CLIPS_DIR.glob("scene_*.mp4"))
    log(f"\nСгенерировано: {len(clips)} из {len(SCENES)}")
    return clips

def create_smooth_film(clips: list[Path], audio_path: Path, output_path: Path):
    """Создаёт плавный фильм с crossfade переходами и единым стилем"""

    log("=" * 60)
    log("СБОРКА ФИЛЬМА В СТИЛЕ MONTANA")
    log("Плавные переходы, единая палитра, медитативный темп")
    log("=" * 60)

    if not clips:
        log("Нет клипов!")
        return

    clips = sorted(clips)
    n_clips = len(clips)

    # 1. Получаем длительность каждого клипа
    log("Анализирую клипы...")
    clip_durations = []
    for clip in clips:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(clip)
        ], capture_output=True, text=True)
        dur = float(result.stdout.strip())
        clip_durations.append(dur)

    total_raw = sum(clip_durations)
    log(f"Сырая длительность: {total_raw:.1f} сек ({n_clips} клипов)")

    # 2. Параметры crossfade
    CROSSFADE_DURATION = 1.5  # секунды перехода
    total_crossfades = (n_clips - 1) * CROSSFADE_DURATION
    effective_duration = total_raw - total_crossfades

    # 3. Рассчитываем замедление
    slowdown = AUDIO_DURATION / effective_duration
    log(f"Замедление: {slowdown:.2f}x для {AUDIO_DURATION} сек")

    # 4. Строим сложный filter_complex с crossfade
    log("Строю фильтр с плавными переходами...")

    filter_parts = []
    inputs_cmd = []

    for i, clip in enumerate(clips):
        inputs_cmd.extend(["-i", str(clip)])

    # Нормализация размера и цветокоррекция для каждого клипа
    # Палитра: тёмно-синий (#0A0E1A) + золотой (#FFD700)
    color_filter = "colorbalance=bs=0.1:bm=0.05:bh=0.02:gs=-0.05:gm=-0.03:rs=-0.1:rm=-0.05"

    for i in range(n_clips):
        # Масштабируем, замедляем, цветокоррекция
        filter_parts.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setpts={slowdown}*PTS,{color_filter},fps=30[v{i}]"
        )

    # Crossfade между клипами
    if n_clips == 1:
        filter_parts.append("[v0]copy[outv]")
    else:
        # Первый crossfade
        filter_parts.append(
            f"[v0][v1]xfade=transition=fade:duration={CROSSFADE_DURATION}:"
            f"offset={clip_durations[0]*slowdown - CROSSFADE_DURATION}[xf0]"
        )

        # Остальные crossfade
        for i in range(2, n_clips):
            prev_offset = sum(clip_durations[:i]) * slowdown - (i * CROSSFADE_DURATION)
            filter_parts.append(
                f"[xf{i-2}][v{i}]xfade=transition=fade:duration={CROSSFADE_DURATION}:"
                f"offset={prev_offset}[xf{i-1}]"
            )

        filter_parts.append(f"[xf{n_clips-2}]copy[outv]")

    filter_complex = ";".join(filter_parts)

    # 5. Собираем команду ffmpeg
    log("Рендерю финальное видео...")

    cmd = ["ffmpeg", "-y"]
    cmd.extend(inputs_cmd)
    cmd.extend(["-i", str(audio_path)])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", f"{n_clips}:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"ОШИБКА ffmpeg: {result.stderr[:500]}")
        # Fallback: простая склейка
        log("Пробую простую склейку...")
        create_simple_concat(clips, audio_path, output_path, slowdown)
        return

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log(f"ГОТОВО: {output_path} ({size_mb:.1f} MB)")


def create_simple_concat(clips: list[Path], audio_path: Path, output_path: Path, slowdown: float):
    """Простая склейка если crossfade не сработал"""

    list_file = CLIPS_DIR / "clips_list.txt"
    with open(list_file, "w") as f:
        for clip in sorted(clips):
            f.write(f"file '{clip}'\n")

    temp_concat = CLIPS_DIR / "temp_concat.mp4"

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(temp_concat)
    ], capture_output=True)

    # Замедляем и добавляем аудио
    color_filter = "colorbalance=bs=0.1:bm=0.05:gs=-0.05:rs=-0.1"

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(temp_concat),
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]setpts={slowdown}*PTS,{color_filter}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ], check=True)

    temp_concat.unlink(missing_ok=True)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    log(f"ГОТОВО (простая склейка): {output_path} ({size_mb:.1f} MB)")

def main():
    setup()

    # Генерируем клипы
    clips = generate_all_clips()

    if not clips:
        log("Не удалось сгенерировать видео!")
        sys.exit(1)

    # Собираем финальное видео с плавными переходами
    audio_path = BASE_DIR / "00. ПРЕЛЮДИЯ.mp3"
    output_path = OUTPUT_DIR / "ПРЕЛЮДИЯ_FILM.mp4"

    create_smooth_film(clips, audio_path, output_path)

    log("=" * 60)
    log("ФИЛЬМ ГОТОВ!")
    log(f"Файл: {output_path}")
    log("=" * 60)

if __name__ == "__main__":
    main()
