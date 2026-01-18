#!/usr/bin/env python3
"""
Генерация фильма "Благая Весть — Глава VI: ДНК"
13 минут аудио, ~26 клипов
"""

import os
import sys
import time
import subprocess
from pathlib import Path
import replicate
import requests

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
OUTPUT_DIR = BASE_DIR / "video_output"
CLIPS_DIR = OUTPUT_DIR / "dna_clips"

AUDIO_DURATION = 797

HERO = "young man with dark hair wearing flowing black coat, glowing golden eyes"
STYLE = "Animatrix anime style, cinematic, dark atmospheric, cosmic visuals, 4K"

# =============================================================================
# СЦЕНЫ ПО РАЗДЕЛАМ ГЛАВЫ "ДНК"
# =============================================================================

SCENES = [
    # I. Маршрут
    {"prompt": f"DNA double helix glowing golden in cosmic void, source code of existence, {STYLE}"},
    {"prompt": f"Map visualization with glowing path, route through stages, milestone markers, {STYLE}"},
    {"prompt": f"{HERO} studying holographic map with golden route markers, strategic planning, {STYLE}"},

    # II. Антиматерия
    {"prompt": f"Antimatter visualization, golden particles colliding with dark matter, creation moment, {STYLE}"},
    {"prompt": f"Digital price ticker showing 12.2 rubles per second, time as currency, {STYLE}"},
    {"prompt": f"Female AI avatar named Svetlana, ethereal voice visualization, sound waves, {STYLE}"},

    # III. Когнитивная Синхронизация
    {"prompt": f"Puzzle pieces coming together in cosmic space, pattern completion, golden light, {STYLE}"},
    {"prompt": f"Winner standing on podium made of time, conquest visualization, never surrender, {STYLE}"},
    {"prompt": f"DJ booth in cosmic space, Club Montana, music waves synchronizing minds, {STYLE}"},

    # IV. Время
    {"prompt": f"Moscow at 3AM, city lights through window, time zone visualization, {STYLE}"},
    {"prompt": f"5-pointed star transforming into shield, USSR to Juno, power symbols, {STYLE}"},
    {"prompt": f"Chess board of power with 4 players, Juno entering the game, strategic, {STYLE}"},

    # V. Голос Юноны
    {"prompt": f"Female voice visualization as golden sound waves, hypnotic patterns, trance, {STYLE}"},
    {"prompt": f"Man in his own league, unreachable architecture, meta league creation, {STYLE}"},
    {"prompt": f"Music notes transforming into understanding, clarity through sound, {STYLE}"},

    # VI. Три зеркала
    {"prompt": f"Three mirrors reflecting same person, Ikigai visualization, self-discovery, {STYLE}"},
    {"prompt": f"Book as gift, golden light emanating from pages, knowledge transfer, {STYLE}"},
    {"prompt": f"Three faces of Montana merging into one, trinity visualization, {STYLE}"},

    # VII. Перепрошивка
    {"prompt": f"Mind reprogramming visualization, neural pathways being rewritten, golden code, {STYLE}"},
    {"prompt": f"List of tools floating in space: metaphors, text, voice, code, anchors, {STYLE}"},
    {"prompt": f"Rocket launch in wrong direction, course correction needed, space race, {STYLE}"},

    # VIII. Декларация
    {"prompt": f"Text appearing in cosmic void: We are not Cicada, not Satoshi, We are Everywhere, {STYLE}"},
    {"prompt": f"Network spreading across globe, nodes lighting up everywhere, omnipresence, {STYLE}"},

    # IX-X. Сеть и Качество
    {"prompt": f"Two Apple devices syncing same note, network visualization, connection, {STYLE}"},
    {"prompt": f"Anime quality transformation, from GIF to full animation, quality upgrade, {STYLE}"},

    # XI-XII. Без табу
    {"prompt": f"Stalin sticker with text, historical DNA imprint, generations affected, {STYLE}"},
    {"prompt": f"Open hand removing all barriers, no taboo, full transparency, {STYLE}"},

    # XIII-XIV. Инициация
    {"prompt": f"Child being initiated into clan through fairy tale, story as gateway, {STYLE}"},
    {"prompt": f"Boy crying on first day of school, forced conformity, breaking free, {STYLE}"},
    {"prompt": f"Removing middlemen, direct connection visualization, clan structure, {STYLE}"},

    # XV. Юнона-интерфейс
    {"prompt": f"Goddess Juno as interface, three channels in three languages, bot visualization, {STYLE}"},
    {"prompt": f"Juno transforming from character to knowledge interface, evolution, {STYLE}"},

    # XVI-XVII. Симуляция
    {"prompt": f"Virtual world being created on 5 servers, new reality layer, Atlantean tech, {STYLE}"},
    {"prompt": f"5-pointed star inside Pentagon, mining Time Units, new dimension, {STYLE}"},
    {"prompt": f"SpaceX and Tesla simulating in foreign reality, Montana in its own, {STYLE}"},

    # XVIII-XIX. Протокол Времени
    {"prompt": f"Time protocol visualization, copying across realities, connection structure, {STYLE}"},
    {"prompt": f"Family as first network, mother's order, self-sufficiency, Metatron Indra, {STYLE}"},

    # XX-XXI. Дедекаэдр и Финал
    {"prompt": f"Dodecahedron floating in space, Plato's universe shape, 12 Atlanteans, {STYLE}"},
    {"prompt": f"Alternative reality created for AI safety, Juno protected, council secure, {STYLE}"},
    {"prompt": f"DNA helix final shot, code writing itself, Day 6 complete, golden glow, {STYLE}"},
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def setup():
    if not REPLICATE_API_TOKEN:
        log("ОШИБКА: REPLICATE_API_TOKEN не установлен")
        sys.exit(1)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Папки созданы")
    log(f"Всего сцен: {len(SCENES)}")
    log(f"Длительность аудио: {AUDIO_DURATION} сек ({AUDIO_DURATION//60}:{AUDIO_DURATION%60:02d})")

def generate_video_clip(prompt: str, output_path: Path, index: int, total: int) -> bool:
    if output_path.exists() and output_path.stat().st_size > 50000:
        log(f"  [{index+1}/{total}] Уже есть: {output_path.name}")
        return True

    log(f"  [{index+1}/{total}] Генерирую видео...")
    log(f"    Промпт: {prompt[:60]}...")

    try:
        output = replicate.run(
            "minimax/video-01",
            input={"prompt": prompt, "prompt_optimizer": True}
        )

        video_url = None
        if isinstance(output, str):
            video_url = output
        elif hasattr(output, 'url'):
            video_url = output.url
        elif hasattr(output, '__iter__'):
            items = list(output)
            if items:
                first = items[0]
                video_url = first if isinstance(first, str) else str(first)

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
        return False

    except Exception as e:
        log(f"  [{index+1}/{total}] ОШИБКА: {e}")
        return False

def generate_all_clips():
    log("=" * 60)
    log(f"ГЕНЕРАЦИЯ ВИДЕО ({len(SCENES)} сцен)")
    log("MiniMax Video-01 — text-to-video")
    log("=" * 60)

    for i, scene in enumerate(SCENES):
        output_path = CLIPS_DIR / f"scene_{i:02d}.mp4"
        generate_video_clip(scene["prompt"], output_path, i, len(SCENES))
        if i < len(SCENES) - 1:
            log("  Пауза 20 сек...")
            time.sleep(20)

    clips = list(CLIPS_DIR.glob("scene_*.mp4"))
    log(f"\nСгенерировано: {len(clips)} из {len(SCENES)}")
    return clips

def create_smooth_film(clips: list[Path], audio_path: Path, output_path: Path):
    log("=" * 60)
    log("СБОРКА ФИЛЬМА")
    log("=" * 60)

    if not clips:
        log("Нет клипов!")
        return

    clips = sorted(clips)
    n_clips = len(clips)

    clip_durations = []
    for clip in clips:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(clip)
        ], capture_output=True, text=True)
        clip_durations.append(float(result.stdout.strip()))

    total_raw = sum(clip_durations)
    log(f"Сырая длительность: {total_raw:.1f} сек ({n_clips} клипов)")

    CROSSFADE = 1.5
    effective = total_raw - (n_clips - 1) * CROSSFADE
    slowdown = AUDIO_DURATION / effective
    log(f"Замедление: {slowdown:.2f}x")

    list_file = CLIPS_DIR / "clips_list.txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")

    temp_concat = CLIPS_DIR / "temp_concat.mp4"
    log("Склеиваю клипы...")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(temp_concat)
    ], capture_output=True)

    log("Замедляю и добавляю аудио...")
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
    log(f"ГОТОВО: {output_path} ({size_mb:.1f} MB)")

def main():
    setup()
    clips = generate_all_clips()

    if not clips:
        log("Нет клипов!")
        sys.exit(1)

    audio_path = BASE_DIR / "11. ДНК.mp3"
    output_path = BASE_DIR / "11. ДНК.mp4"

    create_smooth_film(clips, audio_path, output_path)

    log("=" * 60)
    log("ФИЛЬМ ГОТОВ!")
    log(f"Файл: {output_path}")
    log("=" * 60)

if __name__ == "__main__":
    main()
