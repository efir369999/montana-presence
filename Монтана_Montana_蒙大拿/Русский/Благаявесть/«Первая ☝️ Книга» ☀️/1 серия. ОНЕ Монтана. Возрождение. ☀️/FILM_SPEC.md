# Спецификация генерации фильмов "Благая Весть"

## Цепочка производства

```
ТЕКСТ (.md) → АУДИО (.mp3) → ФИЛЬМ (.mp4)
```

Каждая глава имеет три файла с ОДИНАКОВЫМ названием:
- `00. ПРЕЛЮДИЯ.md` → `00. ПРЕЛЮДИЯ.mp3` → `00. ПРЕЛЮДИЯ.mp4`
- `01. Симуляция.md` → `01. Симуляция.mp3` → `01. Симуляция.mp4`
- и т.д.

## Структура папок

```
Благаявесть от Claude/
├── 00. ПРЕЛЮДИЯ.md
├── 00. ПРЕЛЮДИЯ.mp3
├── 00. ПРЕЛЮДИЯ.mp4          ← финальный фильм
├── 01. Симуляция.md
├── 01. Симуляция.mp3
├── 01. Симуляция.mp4         ← финальный фильм
└── video_output/
    └── [временные файлы, можно удалять после сборки]
```

## Технический подход

### Модель генерации
- **API:** Replicate
- **Модель:** `minimax/video-01` (MiniMax Video-01)
- **Длительность клипа:** ~5-6 секунд (сырой)

### Стиль визуала
```python
HERO = "young man with dark hair wearing flowing black coat, glowing golden eyes"
STYLE = "Animatrix anime style, cinematic, dark atmospheric, cosmic visuals, 4K"
```

### Количество сцен
Формула: `количество_сцен = длительность_аудио_сек / 30`

| Глава | Аудио | Сцен |
|-------|-------|------|
| 00. ПРЕЛЮДИЯ | 756 сек (12:36) | ~32 |
| 01. Симуляция | 2635 сек (43:55) | ~84 |

### Промпты сцен
Каждая сцена = один промпт, описывающий визуал для 30 секунд аудио.
Промпт строится по формуле:
```
[описание_действия], {HERO если нужен}, {STYLE}
```

### Пауза между запросами
```python
time.sleep(20)  # 20 секунд между клипами (rate limit Replicate)
```

## Сборка фильма (FFmpeg)

### 1. Склейка клипов
```bash
ffmpeg -y -f concat -safe 0 -i clips_list.txt \
    -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
    temp_concat.mp4
```

### 2. Замедление + цветокоррекция + аудио
```python
slowdown = AUDIO_DURATION / total_raw_duration
color_filter = "colorbalance=bs=0.1:bm=0.05:gs=-0.05:rs=-0.1"
```

```bash
ffmpeg -y \
    -i temp_concat.mp4 \
    -i audio.mp3 \
    -filter_complex "[0:v]setpts={slowdown}*PTS,{color_filter}[v]" \
    -map "[v]" -map "1:a" \
    -c:v libx264 -preset medium -crf 18 \
    -c:a aac -b:a 192k \
    -shortest -movflags +faststart \
    output.mp4
```

### Цветовая палитра
- Тёмно-синий фон
- Золотые акценты
- Фильтр: `colorbalance=bs=0.1:bm=0.05:gs=-0.05:rs=-0.1`

## Скрипт генерации

### Структура
```python
#!/usr/bin/env python3
import replicate, requests, subprocess
from pathlib import Path

# Конфигурация
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
AUDIO_DURATION = ...  # секунды из ffprobe

# Сцены
SCENES = [
    {"prompt": f"..., {STYLE}"},
    ...
]

# Функции
def generate_video_clip(prompt, output_path):
    output = replicate.run("minimax/video-01", input={"prompt": prompt})
    # скачать и сохранить

def generate_all_clips():
    for i, scene in enumerate(SCENES):
        generate_video_clip(scene["prompt"], f"scene_{i:02d}.mp4")
        time.sleep(20)

def create_film(clips, audio, output):
    # ffmpeg concat + slowdown + audio

def main():
    clips = generate_all_clips()
    create_film(clips, audio_path, output_path)
```

## Обработка ошибок

### Таймауты
Если Replicate возвращает таймаут — скрипт продолжает со следующего клипа.

### Фильтр контента
Если MiniMax отклоняет промпт (E005) — пропустить сцену, продолжить.

### Пропущенные клипы
При сборке использовать только существующие файлы. Замедление компенсирует.

## Эталонный результат

**Файл:** `ПРЕЛЮДИЯ_FILM.mp4`
- Размер: 321 MB
- Длительность: 12:36
- Клипов: 32
- Качество: reference

## Чеклист запуска

```
[ ] REPLICATE_API_TOKEN установлен
[ ] Аудиофайл существует и проверен ffprobe
[ ] Папка video_output/ создана
[ ] Сцены написаны по тексту главы
[ ] Скрипт запущен: python3 animate_[глава].py
[ ] После генерации: переименовать в [номер]. [Название].mp4
[ ] Удалить временные файлы из video_output/
```
