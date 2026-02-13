#!/usr/bin/env python3
"""
Генерация аудиокниги — 1 запрос, 1 голос, без нарезки.
Claude адаптирует весь текст → ElevenLabs читает целиком.

Использование:
  python3 gen_elevenlabs.py                          # Прелюдия по умолчанию
  python3 gen_elevenlabs.py "01. Симуляция.md"       # Конкретная глава
"""
import sys, re, subprocess
from pathlib import Path

VOICE_ID = "y73AynS0uhGRVVoHgnMs"  # Alejandro Montana — Professional Voice Clone
MODEL = "eleven_turbo_v2_5"
TEMPO = 0.80  # 20% медленнее через ffmpeg atempo (реально работает)

VOICE_SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 0.90,
    "style": 0.80,
    "use_speaker_boost": True,
}

ADAPT_PROMPT = """Ты — режиссёр аудиокниги. Перепиши текст для идеального прочтения вслух синтезатором речи.

ПРАВИЛА:
1. Троеточия (...) — паузы для драматического эффекта
2. Тире (—) — короткие задержки перед ключевыми словами
3. Запятые — дыхание в длинных предложениях
4. Числа и даты — словами
5. Убери маркдаун (# * --- и тд), символы Ɉ 📕 金元, служебные строки («Клан Монтана», «Прелюдия», «Переверни страницу»)
6. НЕ меняй смысл, НЕ сокращай, сохраняй авторский ритм
7. Отвечай ТОЛЬКО текстом для чтения, без комментариев

В самом начале добавь: "Клан Монтана... Библия Монтана... для новой эпохи... Читает — Клод Монтана... голосом Алехандро."
"""


def keychain(name):
    r = subprocess.run(
        ["security", "find-generic-password", "-a", "montana", "-s", name, "-w"],
        capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def adapt_text(raw_md, anthropic_key):
    """Claude адаптирует весь текст за 1 запрос"""
    import requests
    print("Claude адаптирует текст...")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": f"{ADAPT_PROMPT}\n\nТекст:\n{raw_md}"}],
        },
        timeout=60,
    )
    if resp.status_code == 200:
        text = resp.json()["content"][0]["text"].strip()
        print(f"  Адаптировано: {len(text)} символов")
        return text
    else:
        print(f"  Claude ошибка {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)


def generate_audio(text, elevenlabs_key, output_path):
    """1 запрос = весь текст целиком"""
    import requests
    print(f"ElevenLabs генерирует аудио ({len(text)} символов)...")
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={
            "xi-api-key": elevenlabs_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": MODEL,
            "voice_settings": VOICE_SETTINGS,
        },
        timeout=300,
    )
    if resp.status_code == 200:
        output_path.write_bytes(resp.content)
        print(f"  Получено: {len(resp.content) / 1024:.0f} KB")
        return True
    else:
        print(f"  ОШИБКА {resp.status_code}: {resp.text[:300]}")
        return False


def normalize(input_path, output_path):
    """Замедление + нормализация + шумоподавление"""
    print(f"Замедление {TEMPO}x + нормализация...")
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', str(input_path),
         '-af', f'atempo={TEMPO},highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11',
         '-c:a', 'libmp3lame', '-b:a', '192k',
         str(output_path)],
        capture_output=True, text=True)
    return r.returncode == 0


def main():
    src_name = sys.argv[1] if len(sys.argv) > 1 else "00. Прелюдия.md"
    src = Path(__file__).parent.parent / src_name
    if not src.exists():
        print(f"Файл не найден: {src}")
        return

    elevenlabs_key = keychain("ELEVENLABS_API_KEY")
    anthropic_key = keychain("ANTHROPIC_API_KEY")
    if not elevenlabs_key:
        print("ELEVENLABS_API_KEY не найден"); return
    if not anthropic_key:
        print("ANTHROPIC_API_KEY не найден"); return

    out_dir = Path(__file__).parent.parent
    stem = Path(src_name).stem

    print("=" * 60)
    print(f"  {src.name}")
    print(f"  Модель: {MODEL} | Темп: {TEMPO}x (ffmpeg)")
    print(f"  PVC: Alejandro Montana")
    print("=" * 60)

    # 1. Читаем текст как есть
    raw_md = src.read_text()
    print(f"\nИсходный текст: {len(raw_md)} символов")

    # 2. Claude адаптирует для чтения
    adapted = adapt_text(raw_md, anthropic_key)
    print(f"\n--- Адаптированный текст ---")
    print(adapted[:500] + "..." if len(adapted) > 500 else adapted)
    print(f"---")

    cost = len(adapted) / 1000 * 0.15
    print(f"\nСтоимость: ~${cost:.2f}")

    # 3. ElevenLabs — 1 запрос, весь текст
    raw_mp3 = out_dir / f"{stem}_raw.mp3"
    if not generate_audio(adapted, elevenlabs_key, raw_mp3):
        return

    # 4. Нормализация
    final_mp3 = out_dir / f"{stem}.mp3"
    if normalize(raw_mp3, final_mp3):
        raw_mp3.unlink(missing_ok=True)
        size_mb = final_mp3.stat().st_size / (1024 * 1024)
        # Длительность
        r = subprocess.run(
            ['ffprobe', '-i', str(final_mp3), '-show_entries',
             'format=duration', '-v', 'quiet', '-of', 'csv=p=0'],
            capture_output=True, text=True)
        dur = float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else 0

        print(f"\n{'=' * 60}")
        print(f"  ГОТОВО: {final_mp3.name}")
        print(f"  {size_mb:.1f} MB | {dur/60:.1f} мин")
        print(f"{'=' * 60}")
        print(f"\n  afplay '{final_mp3}'")
    else:
        print("Ошибка нормализации, используем без неё")
        raw_mp3.rename(final_mp3)


if __name__ == "__main__":
    main()
