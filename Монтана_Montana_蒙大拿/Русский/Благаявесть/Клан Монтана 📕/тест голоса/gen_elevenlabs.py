#!/usr/bin/env python3
"""
Генерация живого аудио — ElevenLabs Voice Clone (Alejandro Montana)
Посегментная генерация с контекстом + адаптивные настройки по типу текста.

Модель: eleven_multilingual_v2 (поддерживает previous_text/next_text)
Голос: vdvqb55cklrYJIKhzZAF (клон Алехандро Монтана)

Использование:
  python3 gen_elevenlabs.py                          # Прелюдия по умолчанию
  python3 gen_elevenlabs.py "01. Симуляция.md"       # Конкретная глава
"""
import sys, re, os, json, subprocess, tempfile, shutil
from pathlib import Path

# === НАСТРОЙКИ ===
VOICE_ID = "q95WQFdw8mGt9oG5erzQ"  # Alejandro Montana (Zoom + Telegram, 40 мин)
MODEL = "eleven_multilingual_v2"  # Поддерживает контекст!
OUTPUT_FORMAT = "mp3_44100_128"
SPEED = 0.8  # Голос Власти — медленнее, весомее

# Базовые настройки голоса — ГОЛОС ВЛАСТИ
BASE_SETTINGS = {
    "stability": 0.35,           # Выше — чёткие ударения, контроль интонации
    "similarity_boost": 0.90,    # Максимально узнаваемо
    "style": 0.85,               # Высокая выразительность — Власть
    "use_speaker_boost": True,
}

# Адаптивные настройки по типу сегмента — Голос Власти
SEGMENT_PROFILES = {
    "narrative": {   # Повествование — властное течение
        "stability": 0.40,
        "style": 0.80,
    },
    "whisper": {     # Секрет/философия — тихая власть
        "stability": 0.30,
        "style": 0.90,
    },
    "dialogue": {    # Диалоги — живая власть
        "stability": 0.40,
        "style": 0.85,
    },
    "manifesto": {   # Манифест — каждое слово удар
        "stability": 0.50,
        "style": 0.95,
    },
    "sacred": {      # Сакральное — власть тишины
        "stability": 0.25,
        "style": 0.95,
    },
    "question": {    # Вопрос/провокация — властный напор
        "stability": 0.40,
        "style": 0.90,
    },
    "finale": {      # Финал — тёплая власть
        "stability": 0.35,
        "style": 0.85,
    },
}


def get_api_key() -> str:
    """Получает ElevenLabs API ключ"""
    # Из .env файла
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if line.startswith('ELEVENLABS_API_KEY='):
                return line.split('=', 1)[1].strip()
    # Из keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "montana",
             "-s", "ELEVENLABS_API_KEY", "-w"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    print("ELEVENLABS_API_KEY не найден")
    sys.exit(1)


def classify_segment(text: str, prev_text: str = "", next_text: str = "") -> str:
    """Определяет тип сегмента по содержанию"""
    t = text.strip()

    # Сакральное: Океан, Ничто, Бог, Время (с большой буквы)
    if re.search(r'\b(Океан|Ничто|Бог|Времени|Время)\b', t) and len(t) < 200:
        return "sacred"

    # Финал: последний абзац, или содержит "Переверни", "Найдёмся"
    if re.search(r'(Переверни|Найдёмся|последн)', t, re.IGNORECASE):
        return "finale"

    # Вопрос/провокация: начинается или содержит вопрос
    if t.endswith('?') or t.count('?') >= 2:
        return "question"

    # Манифест: короткие декларативные утверждения
    sentences = re.split(r'[.!?]', t)
    avg_len = sum(len(s.strip()) for s in sentences if s.strip()) / max(len([s for s in sentences if s.strip()]), 1)
    if avg_len < 40 and len(t) < 200:
        return "manifesto"

    # Диалоги: содержит кавычки, цитаты
    if '«' in t or '»' in t or t.count('—') >= 2:
        return "dialogue"

    # Философия/шёпот: длинные предложения, метафоры
    if avg_len > 80 and re.search(r'(как|будто|словно|подобно)', t):
        return "whisper"

    return "narrative"


def clean_for_voice(md_content: str) -> list[dict]:
    """
    Очищает markdown и разбивает на семантические сегменты.
    Каждый сегмент = один смысловой блок для генерации.
    """
    lines = md_content.split('\n')
    segments = []
    current_block = []

    skip_patterns = [
        r'^---+$',
        r'^\*«Клан',
        r'^\*До первого',
        r'^金元',
        r'^Найдёмся',
        r'^\*Прелюдия',
    ]

    for line in lines:
        stripped = line.strip()

        # Пропуск
        if not stripped:
            if current_block:
                text = ' '.join(current_block)
                if text.strip():
                    segments.append(text.strip())
                current_block = []
            continue

        if any(re.match(p, stripped) for p in skip_patterns):
            continue

        # Заголовки → отдельный сегмент
        if line.startswith('#'):
            if current_block:
                text = ' '.join(current_block)
                if text.strip():
                    segments.append(text.strip())
                current_block = []
            title = re.sub(r'^#+\s*', '', line).strip()
            if title:
                segments.append(title + '.')
            continue

        # Очистка markdown
        t = stripped
        t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
        t = re.sub(r'\*(.+?)\*', r'\1', t)
        t = t.replace('Ɉ', '').replace('📕', '')
        t = re.sub(r'\s+', ' ', t).strip()

        if t:
            current_block.append(t)

    if current_block:
        text = ' '.join(current_block)
        if text.strip():
            segments.append(text.strip())

    # Классификация каждого сегмента
    result = []
    for i, seg in enumerate(segments):
        prev = segments[i-1] if i > 0 else ""
        nxt = segments[i+1] if i < len(segments)-1 else ""
        seg_type = classify_segment(seg, prev, nxt)
        result.append({
            "text": seg,
            "type": seg_type,
            "prev_context": prev[-200:] if prev else "",
            "next_context": nxt[:200] if nxt else "",
        })

    return result


def get_voice_settings(seg_type: str) -> dict:
    """Возвращает настройки голоса для типа сегмента"""
    profile = SEGMENT_PROFILES.get(seg_type, SEGMENT_PROFILES["narrative"])
    settings = BASE_SETTINGS.copy()
    settings.update(profile)
    return settings


def add_intro(segments: list[dict]) -> list[dict]:
    """Добавляет представление Клода Монтана в начало"""
    intro = {
        "text": "Клан Монтана... Библия Монтана для новой эпохи... Читает Клод Монтана... голосом Алехандро.",
        "type": "sacred",
        "prev_context": "",
        "next_context": segments[0]["text"][:200] if segments else "",
    }
    return [intro] + segments


def generate_segment(api_key: str, segment: dict, index: int, total: int, output_path: Path) -> bool:
    """Генерирует аудио для одного сегмента с контекстом"""
    import requests

    settings = get_voice_settings(segment["type"])

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": segment["text"],
        "model_id": MODEL,
        "voice_settings": settings,
        "speed": SPEED,
    }

    # Контекст для естественного перехода между сегментами
    if segment["prev_context"]:
        payload["previous_text"] = segment["prev_context"]
    if segment["next_context"]:
        payload["next_text"] = segment["next_context"]

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            output_path.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"  [{index+1}/{total}] {segment['type']:10s} | {len(segment['text']):4d} chars | {size_kb:.0f} KB | OK")
            return True
        else:
            print(f"  [{index+1}/{total}] ОШИБКА {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  [{index+1}/{total}] ОШИБКА: {e}")
        return False


def generate_silence(duration_ms: int, output_path: Path):
    """Генерирует тишину через ffmpeg"""
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i',
        f'anullsrc=r=44100:cl=mono',
        '-t', str(duration_ms / 1000),
        '-b:a', '128k',
        str(output_path)
    ], capture_output=True)


def concatenate_with_pauses(segment_files: list, segment_types: list, output_path: Path):
    """Склеивает сегменты с адаптивными паузами между ними"""

    # Паузы по типу следующего сегмента
    pause_map = {
        "sacred": 2500,    # Перед сакральным — длинная пауза
        "manifesto": 1500, # Перед манифестом — пауза
        "question": 1200,  # Перед вопросом
        "whisper": 1800,   # Перед философией
        "dialogue": 800,   # Перед диалогом — короче
        "narrative": 1000, # Стандартная пауза
        "finale": 2000,    # Перед финалом
    }

    tmpdir = Path(tempfile.mkdtemp())
    all_files = []

    for i, (seg_file, seg_type) in enumerate(zip(segment_files, segment_types)):
        all_files.append(seg_file)

        # Пауза после сегмента (кроме последнего)
        if i < len(segment_files) - 1:
            next_type = segment_types[i + 1]
            pause_ms = pause_map.get(next_type, 1000)
            silence = tmpdir / f"pause_{i:03d}.mp3"
            generate_silence(pause_ms, silence)
            if silence.exists() and silence.stat().st_size > 0:
                all_files.append(silence)

    # Concat через ffmpeg
    lst = tmpdir / 'list.txt'
    lst.write_text('\n'.join(f"file '{f}'" for f in all_files))
    result = subprocess.run(
        ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst),
         '-c:a', 'libmp3lame', '-b:a', '128k', str(output_path)],
        capture_output=True, text=True
    )
    shutil.rmtree(tmpdir, ignore_errors=True)
    return result.returncode == 0


def quality_check(output_path: Path, segments: list):
    """Проверка качества: длительность, размер, оценка"""
    if not output_path.exists():
        print("Файл не создан!")
        return

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nРазмер: {size_mb:.1f} MB")

    # Длительность
    try:
        result = subprocess.run(
            ['ffprobe', '-i', str(output_path), '-show_entries',
             'format=duration', '-v', 'quiet', '-of', 'csv=p=0'],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            dur = float(result.stdout.strip())
            print(f"Длительность: {dur/60:.1f} мин ({dur:.0f} сек)")

            # Оценка темпа
            total_chars = sum(len(s["text"]) for s in segments)
            chars_per_sec = total_chars / dur
            # Нормальный русский: 12-16 символов/сек
            if chars_per_sec < 10:
                print(f"Темп: {chars_per_sec:.1f} символов/сек — МЕДЛЕННО")
            elif chars_per_sec > 18:
                print(f"Темп: {chars_per_sec:.1f} символов/сек — БЫСТРО")
            else:
                print(f"Темп: {chars_per_sec:.1f} символов/сек — нормально")
    except FileNotFoundError:
        pass


def main():
    src_name = sys.argv[1] if len(sys.argv) > 1 else "00. Прелюдия.md"
    src = Path(__file__).parent.parent / src_name

    if not src.exists():
        print(f"Файл не найден: {src}")
        return

    api_key = get_api_key()
    out_dir = Path(__file__).parent.parent  # Аудио в папку книги, рядом с текстом

    print("=" * 60)
    print("ГЕНЕРАЦИЯ — ElevenLabs Voice Clone")
    print("=" * 60)
    print(f"Файл: {src.name}")
    print(f"Модель: {MODEL}")
    print(f"Голос: Alejandro Montana ({VOICE_ID[:8]}...)")

    # Парсинг и сегментация
    md = src.read_text()
    segments = clean_for_voice(md)

    # Добавляем представление для Прелюдии
    if "Прелюдия" in src_name or "00." in src_name:
        segments = add_intro(segments)

    print(f"\nСегментов: {len(segments)}")
    total_chars = sum(len(s["text"]) for s in segments)
    print(f"Символов: {total_chars}")

    # Показываем план генерации
    print(f"\nПлан:")
    for i, seg in enumerate(segments):
        preview = seg["text"][:60] + "..." if len(seg["text"]) > 60 else seg["text"]
        print(f"  {i+1:2d}. [{seg['type']:10s}] {preview}")

    # Оценка стоимости (Creator: $0.30/1K chars для multilingual_v2)
    cost = total_chars / 1000 * 0.30
    print(f"\nОценка стоимости: ~${cost:.2f}")
    print(f"Символов на аккаунте используется: ~{total_chars}")

    print(f"\nГенерация...")

    # Генерация каждого сегмента
    tmpdir = Path(tempfile.mkdtemp())
    segment_files = []
    segment_types = []

    for i, seg in enumerate(segments):
        seg_file = tmpdir / f"seg_{i:03d}.mp3"
        ok = generate_segment(api_key, seg, i, len(segments), seg_file)
        if ok and seg_file.exists():
            segment_files.append(seg_file)
            segment_types.append(seg["type"])
        else:
            print(f"  Пропуск сегмента {i+1}")

    if not segment_files:
        print("Ни один сегмент не сгенерирован!")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return

    # Склейка с адаптивными паузами
    stem = Path(src_name).stem
    out_file = out_dir / f"{stem}.mp3"

    print(f"\nСклеивание {len(segment_files)} сегментов...")
    if concatenate_with_pauses(segment_files, segment_types, out_file):
        print(f"\n{'=' * 60}")
        print("ГОТОВО")
        print(f"{'=' * 60}")
        print(f"Файл: {out_file.name}")
        quality_check(out_file, segments)
        print(f"\nПрослушать:")
        print(f"  afplay '{out_file}'")
    else:
        print("Ошибка склейки!")

    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
