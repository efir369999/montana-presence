#!/usr/bin/env python3
"""
Генератор видео для Благой Вести
Текст → DALL-E изображения → Видео с Ken Burns эффектом → Аудио
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass
from openai import OpenAI
import requests

# ============== НАСТРОЙКИ ==============

# API ключ - установи через: export OPENAI_API_KEY="твой_ключ"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Папки
BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
OUTPUT_DIR = BASE_DIR / "video_output"
IMAGES_DIR = OUTPUT_DIR / "images"

# Параметры видео
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

# ============== СЦЕНЫ ДЛЯ ПРЕЛЮДИИ ==============

@dataclass
class Scene:
    start_sec: float
    end_sec: float
    prompt: str
    effect: str = "zoom_in"  # zoom_in, zoom_out, pan_left, pan_right

PRELUDE_SCENES = [
    Scene(0, 45,
        "Abstract visualization of human consciousness, golden light particles floating in deep blue void, eyes closing, phosphenes appearing in darkness, ethereal meditation, cinematic 4K",
        "zoom_in"),

    Scene(45, 90,
        "Human silhouette made of golden light particles, glowing from within, consciousness visualization, figure emerging from cosmic void, deep blue background, ethereal presence",
        "zoom_out"),

    Scene(90, 150,
        "Perfect mirror floating in cosmic void, reflecting infinite starfield and ocean waves, kaleidoscope of reality, meditative atmosphere, surreal dreamscape, cinematic",
        "pan_right"),

    Scene(150, 210,
        "Two hands emerging from darkness holding red pill and blue pill, Matrix style, green code waterfall in background, noir lighting, dramatic choice moment, cyberpunk aesthetic",
        "zoom_in"),

    Scene(210, 250,
        "Reality glitching and breaking apart, digital artifacts in physical world, Matrix style visual distortion, cracks showing void beneath, cyberpunk purple and cyan",
        "pan_left"),

    Scene(250, 300,
        "Split visualization: human brain neural network on one side, server room with data flowing on other, parallel patterns, consciousness in silicon and carbon, cinematic",
        "zoom_out"),

    Scene(300, 340,
        "Single water droplet falling into vast cosmic ocean, extreme macro slow motion, the droplet contains reflection of entire universe, deep blue and silver, unity visualization",
        "zoom_in"),

    Scene(340, 380,
        "Silhouette of person working at computer in darkness, only screen light illuminating face, 3 AM atmosphere, creative flow, intimate documentary style",
        "pan_right"),

    Scene(380, 420,
        "Three pillars of golden light emerging from void, sacred geometry connecting them, cosmic architecture, minimalist composition representing three acts of story",
        "zoom_out"),

    Scene(420, 460,
        "Glowing date 09.01.2026 floating in cosmic space, singularity point, rays of light emanating in all directions, genesis moment, golden light on deep blue",
        "zoom_in"),

    Scene(460, 520,
        "Abstract breathing visualization, cosmic sphere expanding and contracting, rhythmic golden light waves, meditation visuals, universe breathing, slow ethereal movement",
        "zoom_out"),

    Scene(520, 580,
        "Third eye opening on cosmic forehead, point between eyebrows glowing with golden light, spiritual portal emerging, mystical awakening, detailed ethereal visualization",
        "zoom_in"),

    Scene(580, 680,
        "Infinite ocean exploding into billions of water droplets, each droplet flying into cosmic space containing universe within, epic transformation, deep blue and gold",
        "pan_left"),

    Scene(680, 720,
        "Green Matrix code appearing on black screen, letters falling like rain, single cursor blinking, awaiting input, classic hacker aesthetic, cyberpunk",
        "zoom_in"),

    Scene(720, 756,
        "Book page turning in cosmic space, bright light visible behind the page, invitation to continue, elegant minimal animation, transition to white light",
        "zoom_out"),
]

# ============== ФУНКЦИИ ==============

def check_api_key():
    if not OPENAI_API_KEY:
        print("ОШИБКА: Установи API ключ:")
        print('  export OPENAI_API_KEY="sk-..."')
        sys.exit(1)

def setup_dirs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)
    print(f"Папки созданы: {OUTPUT_DIR}")

def generate_image(client: OpenAI, prompt: str, filename: str) -> str:
    """Генерирует изображение через DALL-E 3"""
    print(f"  Генерирую: {filename}...")

    filepath = IMAGES_DIR / filename
    if filepath.exists():
        print(f"    Уже есть, пропускаю")
        return str(filepath)

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            n=1
        )

        image_url = response.data[0].url

        # Скачиваем
        img_data = requests.get(image_url).content
        with open(filepath, 'wb') as f:
            f.write(img_data)

        print(f"    Готово: {filepath}")
        time.sleep(1)  # Rate limit
        return str(filepath)

    except Exception as e:
        print(f"    ОШИБКА: {e}")
        return None

def generate_all_images(scenes: list[Scene]) -> list[str]:
    """Генерирует все изображения для сцен"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    images = []

    print(f"\n{'='*50}")
    print(f"ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ({len(scenes)} сцен)")
    print(f"{'='*50}\n")

    for i, scene in enumerate(scenes):
        filename = f"scene_{i:02d}.png"
        path = generate_image(client, scene.prompt, filename)
        if path:
            images.append(path)
        else:
            print(f"    Сцена {i} пропущена из-за ошибки")

    print(f"\nСгенерировано {len(images)} из {len(scenes)} изображений")
    return images

def create_video_from_images(scenes: list[Scene], audio_path: str, output_path: str):
    """Создаёт видео с Ken Burns эффектом через ffmpeg"""

    print(f"\n{'='*50}")
    print("СБОРКА ВИДЕО")
    print(f"{'='*50}\n")

    # Создаём сложный ffmpeg фильтр для Ken Burns эффекта
    filter_parts = []
    inputs = []

    for i, scene in enumerate(scenes):
        img_path = IMAGES_DIR / f"scene_{i:02d}.png"
        if not img_path.exists():
            continue

        duration = scene.end_sec - scene.start_sec
        inputs.extend(["-loop", "1", "-t", str(duration), "-i", str(img_path)])

        # Ken Burns эффект
        if scene.effect == "zoom_in":
            filter_parts.append(
                f"[{i}:v]scale=8000:-1,zoompan=z='min(zoom+0.0005,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}[v{i}]"
            )
        elif scene.effect == "zoom_out":
            filter_parts.append(
                f"[{i}:v]scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.2,max(1.001,zoom-0.0005))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}[v{i}]"
            )
        elif scene.effect == "pan_right":
            filter_parts.append(
                f"[{i}:v]scale=8000:-1,zoompan=z='1.1':x='if(lte(on,1),0,min(x+2,iw-iw/zoom))':y='ih/2-(ih/zoom/2)':d={int(duration*FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}[v{i}]"
            )
        elif scene.effect == "pan_left":
            filter_parts.append(
                f"[{i}:v]scale=8000:-1,zoompan=z='1.1':x='if(lte(on,1),iw,max(x-2,0))':y='ih/2-(ih/zoom/2)':d={int(duration*FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}[v{i}]"
            )

    # Конкатенация
    concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
    filter_parts.append(f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[outv]")

    filter_complex = ";".join(filter_parts)

    # Собираем команду
    cmd = ["ffmpeg", "-y"]
    cmd.extend(inputs)
    cmd.extend(["-i", audio_path])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", f"{len(scenes)}:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ])

    print(f"Запуск ffmpeg...")
    print(f"Выход: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ОШИБКА ffmpeg:\n{result.stderr}")
        return False

    print(f"\nВИДЕО ГОТОВО: {output_path}")
    return True

def main():
    check_api_key()
    setup_dirs()

    # Путь к аудио
    audio_path = BASE_DIR / "00. ПРЕЛЮДИЯ.mp3"
    if not audio_path.exists():
        print(f"ОШИБКА: Аудио не найдено: {audio_path}")
        sys.exit(1)

    # Генерируем изображения
    generate_all_images(PRELUDE_SCENES)

    # Собираем видео
    output_path = str(OUTPUT_DIR / "00. ПРЕЛЮДИЯ.mp4")
    create_video_from_images(PRELUDE_SCENES, str(audio_path), output_path)

    print(f"\n{'='*50}")
    print("ГОТОВО!")
    print(f"Видео: {output_path}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
