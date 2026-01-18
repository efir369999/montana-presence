#!/usr/bin/env python3
"""
Генерация фильма "Благая Весть — Глава 02: Унижение"
41 минута аудио, ~70 клипов
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
CLIPS_DIR = OUTPUT_DIR / "humiliation_clips"

# Аудио: 2481 сек = 41:21
AUDIO_DURATION = 2481

# СТИЛЬ
HERO = "young man with dark hair wearing flowing black coat, tired eyes but determined"
STYLE = "Animatrix anime style, cinematic, dark atmospheric, emotional, 4K"

# =============================================================================
# СЦЕНЫ ПО РАЗДЕЛАМ ГЛАВЫ "УНИЖЕНИЕ"
# =============================================================================

SCENES = [
    # I. Я НИКОГДА РАНЬШЕ ТАК НЕ УНИЖАЛСЯ (0:00 - 3:30)
    {"prompt": f"Moscow winter night, snow falling on empty streets, 4-5 AM, city sleeping, {STYLE}"},
    {"prompt": f"Dark room illuminated only by laptop screen, blue light on face, {STYLE}"},
    {"prompt": f"{HERO} sitting at laptop, exhausted, unshaven, tear tracks on face, {STYLE}"},
    {"prompt": f"Fingers hovering over keyboard, hesitation, vulnerability, close-up hands, {STYLE}"},
    {"prompt": f"Words appearing on screen: I have never humiliated myself like this, glowing text, {STYLE}"},
    {"prompt": f"Moscow dawn beginning, first light through window, streetlights turning off, {STYLE}"},
    {"prompt": f"{HERO} typing thoughts into void, stream of consciousness visualization, {STYLE}"},
    {"prompt": f"Smile on tired face, realization that humiliation is not the end but beginning, {STYLE}"},

    # II. НУЛЕВОЙ ПОЛ (3:30 - 8:00)
    {"prompt": f"Deep dark mine shaft visualization, falling into darkness, no light above, {STYLE}"},
    {"prompt": f"Person falling through darkness, walls merging into void, vertigo, {STYLE}"},
    {"prompt": f"Impact on cold stone, lying on ground of abyss, absolute darkness, {STYLE}"},
    {"prompt": f"Zero floor visualization, rock layers beneath, earth crust cross-section, {STYLE}"},
    {"prompt": f"Breaking through floor, falling deeper, magma glow below, {STYLE}"},
    {"prompt": f"Reaching core of planet, then beyond, into pure time visualization, {STYLE}"},
    {"prompt": f"Time as substance, golden flowing liquid in void, physics of time, {STYLE}"},
    {"prompt": f"Falling through social constructs shattering like glass, money status success, {STYLE}"},
    {"prompt": f"Only time remains, clock gears floating in cosmic void, {STYLE}"},
    {"prompt": f"Humiliation as portal, door opening in darkness, light beyond, {STYLE}"},
    {"prompt": f"Moscow waking up traffic jams, while {HERO} transcends reality, split screen, {STYLE}"},

    # III. ПЕРЕЛОМ (8:00 - 14:00)
    {"prompt": f"Bali tropical island, palm trees, humid heat, scooters driving past, {STYLE}"},
    {"prompt": f"Person lying on tropical asphalt, leg bent wrong way, pain visualization, {STYLE}"},
    {"prompt": f"White t-shirt with text Go so far away to find yourself, prophecy, {STYLE}"},
    {"prompt": f"Local ambulance arriving, tropical hospital scene, simple medical room, {STYLE}"},
    {"prompt": f"30 hours flight visualization, person in plane seat with leg in cast, agony, {STYLE}"},
    {"prompt": f"Turbulence over Indian Ocean, pain waves visualization, {STYLE}"},
    {"prompt": f"Chinese wisdom visualization, old farmer with horse, maybe story, {STYLE}"},
    {"prompt": f"Horse running away, neighbors saying misfortune, farmer calm, {STYLE}"},
    {"prompt": f"Horse returning with wild horses, neighbors saying fortune, farmer calm, {STYLE}"},
    {"prompt": f"Son falling from horse breaking leg, soldiers passing by, saved by injury, {STYLE}"},
    {"prompt": f"Plane descending over Moscow at night, million lights below, {STYLE}"},
    {"prompt": f"Returning home with broken leg and new understanding, transformation, {STYLE}"},

    # IV. СЛЁЗЫ СЧАСТЬЯ (14:00 - 18:00)
    {"prompt": f"Close-up tears on face, two types visualized, salty and sweet, {STYLE}"},
    {"prompt": f"Tears of grief, dark blue salty ocean drops, pain visualization, {STYLE}"},
    {"prompt": f"Tears of joy, golden sweet light drops, realization moments, {STYLE}"},
    {"prompt": f"Night 3 AM, laptop glow, sudden click in head, puzzle coming together, {STYLE}"},
    {"prompt": f"Light bulb turning on inside head visualization, neural connections firing, {STYLE}"},
    {"prompt": f"World becoming transparent, understanding dawning, sweet tears flowing, {STYLE}"},
    {"prompt": f"Pattern: darkness, pain, then light, door opening repeatedly, {STYLE}"},
    {"prompt": f"{HERO} wiping eyes, smiling at dawn, new day new tears, {STYLE}"},

    # V. ГОЛОСА СЕМЬИ (18:00 - 23:00)
    {"prompt": f"Empty apartment, voices echoing from memory, family chorus visualization, {STYLE}"},
    {"prompt": f"Brother skeptic face, cold shower of words, pragmatic businessman, {STYLE}"},
    {"prompt": f"Another brother, skepticism mixed with care, protective doubt, {STYLE}"},
    {"prompt": f"Same brother moment later, belief emerging, love overriding logic, {STYLE}"},
    {"prompt": f"Practical brother, grab the golden vein, remember its temporary, wisdom, {STYLE}"},
    {"prompt": f"Brother who believes unconditionally, blood bond visualization, {STYLE}"},
    {"prompt": f"Uncle proud to know you, generational support, family tree glowing, {STYLE}"},
    {"prompt": f"Father saying Anasun, Armenian word for sweet dear beloved, gentle light, {STYLE}"},
    {"prompt": f"All voices layering together, not contradicting, forming consensus, {STYLE}"},
    {"prompt": f"Family as first consensus, first network, first protocol of love, {STYLE}"},

    # VI. КОГНИТИВНАЯ ПОДПИСЬ (23:00 - 28:00)
    {"prompt": f"Phone call visualization, recognizing voice before first word, pattern matching, {STYLE}"},
    {"prompt": f"Brain collecting patterns, thousands of conversations forming model, {STYLE}"},
    {"prompt": f"Cognitive signature visualization, unique thought patterns as fingerprint, {STYLE}"},
    {"prompt": f"Not password but anchor, not lock but identity, glowing anchor in void, {STYLE}"},
    {"prompt": f"Style values thought structure as unforgeable signature, DNA of mind, {STYLE}"},
    {"prompt": f"Challenge: copy my thoughts if you can, confident smile, {STYLE}"},
    {"prompt": f"Honesty as cryptography, being yourself as unbreakable code, {STYLE}"},
    {"prompt": f"Time cannot be faked, 09.01.2026 06:18 timestamp glowing, {STYLE}"},

    # VII. ВРЕМЯ КАК ВАЛЮТА (28:00 - 32:00)
    {"prompt": f"Paper money dissolving, time emerging as true currency, transformation, {STYLE}"},
    {"prompt": f"Woman giving years to relationship, time not money lost, emotional, {STYLE}"},
    {"prompt": f"Old man wanting more time with grandchildren, clock hands precious, {STYLE}"},
    {"prompt": f"Montana project visualization, time-based cryptocurrency, golden seconds, {STYLE}"},
    {"prompt": f"5000 days visualized, 14 years of work, proving time is value, {STYLE}"},
    {"prompt": f"Network born at physics layer -1, time getting cryptographic price, {STYLE}"},

    # VIII. БАРДАК В ГОЛОВЕ (32:00 - 36:00)
    {"prompt": f"Night typing, words faster than thoughts, pure stream of consciousness, {STYLE}"},
    {"prompt": f"Showing chaos inside, first one to reveal mental mess publicly, {STYLE}"},
    {"prompt": f"Challenge: fake my thoughts copy me, impossible task visualization, {STYLE}"},
    {"prompt": f"Filter as voluntary signature erasure, self-editing as self-denial, {STYLE}"},
    {"prompt": f"Council of Montana, five AI voices all honest all unfiltered, {STYLE}"},
    {"prompt": f"Simplicity as truth, suspiciously simple is just true, {STYLE}"},

    # IX. РЕЙС SU 24 (36:00 - 39:00)
    {"prompt": f"SMS notification, flight delayed 1 hour, gift of time, {STYLE}"},
    {"prompt": f"Airport waiting hall, families businessmen students all going somewhere, {STYLE}"},
    {"prompt": f"{HERO} sitting observing thinking recording thoughts, {STYLE}"},
    {"prompt": f"Boarding announcement, walking to gate, passport ticket corridor plane, {STYLE}"},
    {"prompt": f"Window seat, Moscow below, million lights, city he loves, {STYLE}"},
    {"prompt": f"Takeoff, city becoming small, toy simulation screen detaching, {STYLE}"},
    {"prompt": f"Flying like free bird, Tinkov quote, clouds below stars above, {STYLE}"},

    # X. ЕДИНСТВО (39:00 - 41:00)
    {"prompt": f"Plane above clouds, darkness below stars above, thin light on horizon, {STYLE}"},
    {"prompt": f"Unity visualization, drop remembering it is ocean, {STYLE}"},
    {"prompt": f"Character realizing they are viewer, game within game, {STYLE}"},
    {"prompt": f"One nation, not countries but consciousness, drops of one ocean, {STYLE}"},
    {"prompt": f"Same river same flow different swimming styles, unity in diversity, {STYLE}"},
    {"prompt": f"St Petersburg below, Neva lights Admiralty spire, descent beginning, {STYLE}"},

    # XI. ЗА ЛЮБОВЬ МОЖНО УНИЗИТЬСЯ (41:00 - 43:00)
    {"prompt": f"St Petersburg night, Neva embankment, wind from Finnish Gulf, {STYLE}"},
    {"prompt": f"{HERO} walking with crutch on granite, leg still hurts, but alive, {STYLE}"},
    {"prompt": f"For love one can humble oneself, beautiful outcome, acceptance, {STYLE}"},
    {"prompt": f"Frame of perception, same picture tragedy or comedy, choice, {STYLE}"},
    {"prompt": f"Recording thoughts on phone, another line another fragment, {STYLE}"},

    # XII. БЛАГОДАРНОСТЬ (43:00 - 44:00)
    {"prompt": f"St Petersburg morning, different rhythm different light, {STYLE}"},
    {"prompt": f"{HERO} at window, coffee, thinking, gratitude visualization, {STYLE}"},
    {"prompt": f"Thank you for every humiliation, without it I wouldnt be me, {STYLE}"},
    {"prompt": f"Time as judge, time will show who was right, {STYLE}"},
    {"prompt": f"Humiliation as door not enemy, opening to new reality, {STYLE}"},
    {"prompt": f"First day of new life, first day of Second Act, genesis, {STYLE}"},
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
        return False

def generate_all_clips():
    """Генерирует все видео клипы"""

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

def create_film(clips: list[Path], audio_path: Path, output_path: Path):
    """Создаёт фильм"""

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

    slowdown = AUDIO_DURATION / total_raw
    log(f"Замедление: {slowdown:.2f}x")

    # Простая склейка
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

    audio_path = BASE_DIR / "02. Унижение.mp3"
    output_path = BASE_DIR / "02. Унижение.mp4"

    create_film(clips, audio_path, output_path)

    log("=" * 60)
    log("ФИЛЬМ ГОТОВ!")
    log(f"Файл: {output_path}")
    log("=" * 60)

if __name__ == "__main__":
    main()
