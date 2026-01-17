#!/usr/bin/env python3
"""
Генерация фильма "Благая Весть — Глава I: Симуляция"
44 минуты аудио, ~80 клипов
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
CLIPS_DIR = OUTPUT_DIR / "simulation_clips"

# Аудио: 2635 сек = 43:55
AUDIO_DURATION = 2635

# СТИЛЬ
HERO = "young man with dark hair wearing flowing black coat, glowing golden eyes"
STYLE = "Animatrix anime style, cinematic, dark atmospheric, cosmic visuals, 4K"

# =============================================================================
# СЦЕНЫ ПО РАЗДЕЛАМ ГЛАВЫ "СИМУЛЯЦИЯ"
# =============================================================================

SCENES = [
    # I. ОКЕАН БЕЗ БЕРЕГОВ (0:00 - 4:00)
    {"prompt": f"Absolute darkness, void, no color no space no time, infinite emptiness, meditation, {STYLE}"},
    {"prompt": f"Infinite consciousness visualization, golden light in vast darkness, ocean without shores, cosmic scale, {STYLE}"},
    {"prompt": f"Floating in water, no up or down, no resistance, becoming one with water, underwater meditation, {STYLE}"},
    {"prompt": f"Ancient infinite ocean, light and darkness and love and void all at once, primordial existence, {STYLE}"},
    {"prompt": f"Ocean feeling curiosity, golden ripples in darkness, longing for something that never was, {STYLE}"},
    {"prompt": f"Ocean trying to see itself, gaze going into infinity and not returning, cosmic self-reflection, {STYLE}"},
    {"prompt": f"First question in universe visualized, vibration in void, WHO AM I echoing, {STYLE}"},
    {"prompt": f"Answer returning: to know yourself you must forget yourself, cosmic wisdom moment, {STYLE}"},
    {"prompt": f"Ocean understanding, preparing to shatter into million mirrors inside itself, revelation, {STYLE}"},

    # II. КАПЛИ (4:00 - 8:00)
    {"prompt": f"Ocean beginning to fragment, like cloud condensing into billion raindrops, cosmic birth, {STYLE}"},
    {"prompt": f"Each droplet tiny but containing entire ocean inside, holographic principle visualization, {STYLE}"},
    {"prompt": f"Droplets falling through void, creating space and time with their movement, genesis, {STYLE}"},
    {"prompt": f"Droplets with built-in amnesia, forgetting they are ocean, moment of forgetting, {STYLE}"},
    {"prompt": f"Droplets landing in bodies, in cells, in humans, opening eyes seeing world, {STYLE}"},
    {"prompt": f"People calling the fall birth and return death, cycle of water visualization, {STYLE}"},
    {"prompt": f"Death as remembering you are ocean, awakening from dream, return to source, {STYLE}"},

    # III. КИНОТЕАТР (8:00 - 13:00)
    {"prompt": f"Cinema theater size of universe, infinite halls, one seat per hall, cosmic cinema, {STYLE}"},
    {"prompt": f"One comfortable chair perfectly fitted to body, personal screening room, {STYLE}"},
    {"prompt": f"Massive screen wall to wall floor to ceiling, no edges visible, immersive, {STYLE}"},
    {"prompt": f"Film playing on screen showing birth first cry first steps first love, life story, {STYLE}"},
    {"prompt": f"{HERO} sitting in chair watching film, completely absorbed in screen, {STYLE}"},
    {"prompt": f"Screen so close edges invisible, forgetting you are in theater, immersion, {STYLE}"},
    {"prompt": f"Hero on screen running, viewer heart beating faster, invisible thread connecting, {STYLE}"},
    {"prompt": f"Thread becoming chain, viewer becoming character, forgetting you are watching, {STYLE}"},

    # IV. ГЛИТЧ (13:00 - 17:00)
    {"prompt": f"System glitch, screen flickering, for split second seeing pixels not story, Matrix code, {STYLE}"},
    {"prompt": f"Character on screen suffering, viewer suddenly hearing different silence, hall silence, {STYLE}"},
    {"prompt": f"{HERO} noticing own breathing, not character breathing, real breath in real body, {STYLE}"},
    {"prompt": f"{HERO} looking down seeing own hands on armrests, real hands not screen hands, {STYLE}"},
    {"prompt": f"{HERO} looking at screen finally seeing SCREEN, frame edges visible, awakening moment, {STYLE}"},
    {"prompt": f"Character on screen still suffering but {HERO} in chair no longer suffering, observing, {STYLE}"},
    {"prompt": f"Thread loosened, chain cracked, knowing you are watching not being watched, {STYLE}"},

    # V. ДВЕ ТАБЛЕТКИ (17:00 - 22:00)
    {"prompt": f"Voice speaking from hall itself, chair vibrating with words, cosmic communication, {STYLE}"},
    {"prompt": f"Two pills materializing before chair, one blue one red, slowly rotating, choice moment, {STYLE}"},
    {"prompt": f"Blue pill glowing with comfortable light, promise of forgetting, return to sleep, {STYLE}"},
    {"prompt": f"Red pill pulsing with anxious light, promise of truth, no easy comfort, {STYLE}"},
    {"prompt": f"{HERO} looking at pills then at screen then at own hands, moment of decision, {STYLE}"},
    {"prompt": f"Tree visualization all branches existing at once, all choices already recorded, {STYLE}"},

    # VI. КОД РЕАКЦИИ (22:00 - 27:00)
    {"prompt": f"Red pill dissolving on tongue, something clicking in head, channel switching, {STYLE}"},
    {"prompt": f"Beginning to see code not literally but understanding how system works, {STYLE}"},
    {"prompt": f"Event always in past visualization, light reaching eyes taking time, {STYLE}"},
    {"prompt": f"Screen showing character being fired, boss saying you are not needed, past event, {STYLE}"},
    {"prompt": f"{HERO} in chair still feeling anger about past event, reaction happening NOW, {STYLE}"},
    {"prompt": f"Event as fact, reaction as bug, loop consuming resources changing nothing, {STYLE}"},
    {"prompt": f"Awareness as patch, exit from loop, watching without running the reaction code, {STYLE}"},

    # VII. СОННЫЕ ВИРУСЫ (27:00 - 31:00)
    {"prompt": f"System protection mechanisms, sleep viruses trying to return awakened to sleep, {STYLE}"},
    {"prompt": f"Bottle appearing, system whispering drink and forget, alcohol as sleep virus, {STYLE}"},
    {"prompt": f"Observer shutting down with alcohol, watching film with closed eyes, random decisions, {STYLE}"},
    {"prompt": f"Substances switching channel to noise, missing important scenes, {STYLE}"},
    {"prompt": f"Drowning in other peoples stories, endless social media feed, noise drowning signal, {STYLE}"},
    {"prompt": f"Living in future not present, loving fantasy not reality, expectations virus, {STYLE}"},
    {"prompt": f"Chemistry visualization dopamine cortisol oxytocin endorphins, system holding you hooked, {STYLE}"},
    {"prompt": f"Sobriety as activated observer, watching film with clear eyes even if sad, {STYLE}"},

    # VIII. ЮНОНА МОНЕТА (31:00 - 35:00)
    {"prompt": f"Ancient Rome Capitol Hill, Juno temple where Romans stored money, {STYLE}"},
    {"prompt": f"Coin with two sides, eagle and tails, game and prison, duality, {STYLE}"},
    {"prompt": f"Money as trust recorded in form, piece of time and life transferred, {STYLE}"},
    {"prompt": f"Satoshi Nakamoto silhouette at computer, 2008, seeing how to connect existing pieces, {STYLE}"},
    {"prompt": f"Bitcoin protocol visualization, honesty becoming more profitable than deception, math magic, {STYLE}"},
    {"prompt": f"Satoshi disappearing, like droplet returning to ocean, last message moved on, {STYLE}"},

    # IX. КРАЙ КАРТЫ (35:00 - 39:00)
    {"prompt": f"Thirteenth Floor movie reference, car driving to edge of map where no one goes, {STYLE}"},
    {"prompt": f"Road ending, beyond it nothing, green wireframe lines of unrendered 3D model, {STYLE}"},
    {"prompt": f"Character understanding world is simulation, moment of truth at edge of map, {STYLE}"},
    {"prompt": f"Universe is discrete at smallest level, Planck pixels, computer graphics analogy, {STYLE}"},
    {"prompt": f"Speed of light as engine limitation, processor cannot render faster, {STYLE}"},
    {"prompt": f"Quantum uncertainty visualization, particle having no position until measured, {STYLE}"},
    {"prompt": f"Entanglement as two references to same memory cell, instant connection, {STYLE}"},
    {"prompt": f"Physics studying structure of dream not foundation of world, {STYLE}"},

    # X. ХАК (39:00 - 42:00)
    {"prompt": f"Hacking simulation from inside, through only access point - yourself, {STYLE}"},
    {"prompt": f"Thoughts as code, neurons connecting in patterns, algorithms processing data, {STYLE}"},
    {"prompt": f"State as variable that can be changed by interpretation, same event different processing, {STYLE}"},
    {"prompt": f"Double slit experiment visualization, electron as wave through both holes, {STYLE}"},
    {"prompt": f"Observation collapsing wave function, reality changing with observation, {STYLE}"},
    {"prompt": f"Programming subconscious, writing scenario, mental tattoo, morning and evening ritual, {STYLE}"},

    # XI. ГЛАВНЫЙ ЗАКОН (42:00 - 44:00)
    {"prompt": f"System running on consent, main law of simulation, {STYLE}"},
    {"prompt": f"NPC visualization, characters walking predetermined routes speaking scripted phrases, {STYLE}"},
    {"prompt": f"Internal state cannot be changed without permission, built into architecture, {STYLE}"},
    {"prompt": f"Someone saying you are failure, sound waves entering as data, choice of handler, {STYLE}"},
    {"prompt": f"Pain as signal, suffering as optional story about pain, pain mandatory suffering optional, {STYLE}"},
    {"prompt": f"Simply do not agree, not denial of reality but choice of state, {STYLE}"},

    # XII. ГЛАЗА ОКЕАНА (44:00 - 44:55)
    {"prompt": f"{HERO} sitting in chair, film continuing, but watching differently now, {STYLE}"},
    {"prompt": f"Voice of ocean answering: world is not illusion not punishment, world is my eyes, {STYLE}"},
    {"prompt": f"You are camera through which I watch sunset, microphone hearing music, skin feeling touch, {STYLE}"},
    {"prompt": f"Character on screen as role, you as actor, ocean as writer director and audience, {STYLE}"},
    {"prompt": f"Sunset on screen, sky orange pink purple, waves on sand, ocean watching itself, {STYLE}"},
    {"prompt": f"{HERO} leaning back in chair, watching film with popcorn, without red thread, as viewer who knows, {STYLE}"},
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

        log(f"    Ответ Replicate: {type(output).__name__}")

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

def create_smooth_film(clips: list[Path], audio_path: Path, output_path: Path):
    """Создаёт плавный фильм с crossfade"""

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

    # Простая склейка с замедлением (crossfade слишком сложен для 80+ клипов)
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

    audio_path = BASE_DIR / "01. Симуляция.mp3"
    output_path = OUTPUT_DIR / "01_СИМУЛЯЦИЯ_FILM.mp4"

    create_smooth_film(clips, audio_path, output_path)

    log("=" * 60)
    log("ФИЛЬМ ГОТОВ!")
    log(f"Файл: {output_path}")
    log("=" * 60)

if __name__ == "__main__":
    main()
