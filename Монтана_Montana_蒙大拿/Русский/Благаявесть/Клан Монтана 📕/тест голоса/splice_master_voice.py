#!/usr/bin/env python3
"""
Врезает живой голос Алехандро вместо AI-финала.
Генерирует все сегменты до "партнёры по цеху",
затем вставляет запись Мастер.m4a как финал.
"""
import sys, tempfile, shutil, subprocess
from pathlib import Path

# Импортируем из основного скрипта
sys.path.insert(0, str(Path(__file__).parent))
from gen_elevenlabs import (
    get_api_key, clean_for_voice, add_intro, generate_segment,
    generate_silence, concatenate_with_pauses, quality_check,
    VOICE_ID, MODEL
)

LIVE_VOICE = Path("/Users/kh./Downloads/Мастер.m4a")
LIVE_MP3 = Path(__file__).parent / "master_voice.mp3"

def main():
    src = Path(__file__).parent.parent / "Мастерская работа Голос Власти Монтана.md"
    api_key = get_api_key()

    print("=" * 60)
    print("ГЕНЕРАЦИЯ С ЖИВЫМ ГОЛОСОМ ФИНАЛА")
    print("=" * 60)

    # Парсинг
    md = src.read_text()

    # Без технической карты

    segments = clean_for_voice(md)

    # Убираем последний сегмент (вопрос "Кивните, если слышите...")
    # — он будет заменён живым голосом
    question_text = "Кивните, если слышите"
    cut_idx = None
    for i, seg in enumerate(segments):
        if question_text in seg["text"]:
            cut_idx = i
            break

    if cut_idx is not None:
        segments = segments[:cut_idx]
        print(f"Отсечено с сегмента {cut_idx+1} (вопрос → живой голос)")

    print(f"AI-сегментов: {len(segments)}")
    total_chars = sum(len(s["text"]) for s in segments)
    print(f"Символов: {total_chars}")
    cost = total_chars / 1000 * 0.30
    print(f"Оценка: ~${cost:.2f}")

    # Конвертируем живой голос
    if not LIVE_MP3.exists() or LIVE_MP3.stat().st_mtime < LIVE_VOICE.stat().st_mtime:
        print(f"\nКонвертация живого голоса: {LIVE_VOICE.name}")
        subprocess.run([
            'ffmpeg', '-y', '-i', str(LIVE_VOICE),
            '-b:a', '128k', '-ar', '44100', str(LIVE_MP3)
        ], capture_output=True)

    dur_result = subprocess.run(
        ['ffprobe', '-i', str(LIVE_MP3), '-show_entries', 'format=duration',
         '-v', 'quiet', '-of', 'csv=p=0'],
        capture_output=True, text=True
    )
    live_dur = float(dur_result.stdout.strip()) if dur_result.returncode == 0 else 0
    print(f"Живой голос: {live_dur:.1f} сек")

    print(f"\nГенерация AI-сегментов...")

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

    # Добавляем живой голос как финальный сегмент
    segment_files.append(LIVE_MP3)
    segment_types.append("sacred")  # Священная пауза перед живым голосом

    print(f"\nСклеивание {len(segment_files)} сегментов (AI + живой голос)...")

    out_file = Path(__file__).parent / "Мастерская работа Голос Власти Монтана.mp3"

    if concatenate_with_pauses(segment_files, segment_types, out_file):
        # Копируем также в основную папку книги
        main_out = Path(__file__).parent.parent / "ПРОМПТ_ГОЛОС.mp3"
        shutil.copy2(out_file, main_out)

        print(f"\n{'=' * 60}")
        print("ГОТОВО — ЖИВОЙ ГОЛОС ФИНАЛА")
        print(f"{'=' * 60}")
        print(f"Файл: {out_file.name}")
        quality_check(out_file, segments + [{"text": "live voice " * 10}])
        print(f"\nПрослушать:")
        print(f"  afplay '{out_file}'")
    else:
        print("Ошибка склейки!")

    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
