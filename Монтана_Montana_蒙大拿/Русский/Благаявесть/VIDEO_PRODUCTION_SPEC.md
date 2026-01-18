# Техническая Спецификация: Производство Видео "Благаявесть от Claude"

## Обзор Проекта

**Цель:** Создание кинематографичных видео с синхронизацией текста под музыкальный саундтрек.

**Подход:** Саундтрек ведёт - текст появляется в ритме музыки, как в настоящем фильме/артхаус кино.

## Структура Проекта

```
Благаявесть от Claude/
├── [XX]. [Название].md          # Исходный текст главы
├── [XX]. [Название].mp3          # Аудио-книга (готовая)
├── саундтрек_[XX].mp3           # Музыкальный саундтрек для видео
└── video/
    ├── [XX]. [Название].mp4     # Финальное видео
    └── [XX]. [Название].srt     # Субтитры (опционально)
```

## Технический Стек

### Python Библиотеки (Установлено)

```bash
pip install librosa pydub moviepy numpy scipy pillow
```

- **librosa** - анализ музыки (темп, биты, структура)
- **pydub** - работа с аудио форматами
- **moviepy** - создание и рендеринг видео
- **numpy/scipy** - математическая обработка
- **pillow** - работа с изображениями/текстом

### Системные Требования

- Python 3.12+
- FFmpeg (для moviepy)
- ~2GB RAM на главу
- Платформа: macOS (Darwin 24.6.0)

## Алгоритм Производства

### 1. Анализ Саундтрека

```python
import librosa

# Загрузка аудио
y, sr = librosa.load('саундтрек.mp3')

# Анализ:
- tempo (BPM) - темп композиции
- beat_frames - точки ударов/акцентов
- onset_strength - интенсивность по времени
- spectral_features - частотная структура
- loudness - динамика громкости
```

**Выходные данные:**
- Общая длительность
- Ключевые моменты (intro, buildup, drop, outro)
- Массив тайминов для субтитров

### 2. Обработка Текста

```python
# Парсинг MD файла
- Удаление заголовков (###, ----)
- Разбиение на смысловые блоки:
  * По абзацам для нарративных частей
  * По предложениям для диалогов
  * По фразам для кульминационных моментов

# Приоритет синхронизации:
1. Короткие фразы - на сильные биты
2. Длинные абзацы - на спокойные части
3. Ключевые моменты текста - на музыкальные кульминации
```

### 3. Синхронизация

**Стратегия:**
- Разделить саундтрек на сегменты по интенсивности
- Распределить текстовые блоки по сегментам
- Важные фразы = музыкальные акценты
- Паузы в тексте = паузы в музыке

**Параметры тайминга:**
```python
subtitle_timing = {
    'min_duration': 1.5,      # секунды
    'max_duration': 5.0,      # секунды
    'fade_in': 0.3,           # секунды
    'fade_out': 0.3,          # секунды
    'beat_sync': True,        # привязка к битам
}
```

### 4. Визуальный Стиль

**Кинематографичный минимализм:**

```python
video_config = {
    'resolution': (1920, 1080),  # Full HD
    'fps': 24,                    # Кинематографичный FPS
    'background': {
        'type': 'solid',          # или 'gradient'
        'color': (10, 10, 15),    # Тёмный (почти черный)
    },
    'text': {
        'font': 'Arial',          # или custom TTF
        'size': 48,               # базовый размер
        'color': (240, 240, 240), # Почти белый
        'stroke_color': (0, 0, 0),
        'stroke_width': 2,
        'align': 'center',
        'position': 'center',     # или 'bottom'
        'max_width': 0.8,         # 80% ширины экрана
    },
    'effects': {
        'fade_in': 'ease_in',
        'fade_out': 'ease_out',
        'transitions': True,
    }
}
```

### 5. Рендеринг

```python
from moviepy.editor import *

# Создание клипов
clips = []
for subtitle in subtitles:
    txt_clip = TextClip(
        subtitle.text,
        **video_config['text']
    ).set_start(subtitle.start).set_duration(subtitle.duration)

    clips.append(txt_clip.crossfadein(0.3).crossfadeout(0.3))

# Композиция
video = CompositeVideoClip(clips, size=(1920, 1080))
video = video.set_audio(AudioFileClip('саундтрек.mp3'))

# Экспорт
video.write_videofile(
    'output.mp4',
    fps=24,
    codec='libx264',
    audio_codec='aac',
    preset='slow',      # качество
    bitrate='5000k'
)
```

## Workflow для Новой Сессии

### Входные данные от пользователя:

1. **Саундтрек:** путь к музыкальному файлу
2. **Глава:** номер или название главы из "Благаявесть от Claude"
3. **Стиль** (опционально): кастомные настройки визуала

### Этапы работы:

```bash
# 1. Анализ музыки
python analyze_soundtrack.py --input саундтрек.mp3

# 2. Парсинг текста главы
python parse_chapter.py --chapter "01. Симуляция.md"

# 3. Синхронизация
python sync_text_to_music.py --music анализ.json --text глава.json

# 4. Рендеринг
python render_video.py --config sync_result.json --output video.mp4
```

## Оптимизации

### Производительность:
- Предварительный просчёт всех тайминов
- Batch обработка текстовых клипов
- Использование ThreadPoolExecutor для параллельной обработки

### Качество:
- Anti-aliasing для текста
- Субпиксельное позиционирование
- Gamma-коррекция для fade эффектов

## Технические Нюансы

### Обработка Русского Текста:
```python
# Поддержка кириллицы
import matplotlib.font_manager as fm
font_path = fm.findfont(fm.FontProperties(family='Arial Unicode MS'))
```

### Управление Памятью:
```python
# Для длинных глав (>5000 слов):
- Рендеринг по сегментам
- Очистка cache между клипами
- Использование низкого качества превью для отладки
```

### Синхронизация Битов:
```python
# Квантизация к ближайшему биту
def snap_to_beat(timestamp, beat_times, tolerance=0.1):
    closest_beat = min(beat_times, key=lambda x: abs(x - timestamp))
    if abs(closest_beat - timestamp) < tolerance:
        return closest_beat
    return timestamp
```

## Форматы Вывода

1. **Видео MP4:**
   - Codec: H.264
   - Audio: AAC
   - Bitrate: 5000k
   - FPS: 24

2. **Субтитры SRT** (опционально):
   - UTF-8 encoding
   - Стандартный SRT формат
   - Синхронизированные с видео

## Примеры Использования

### Простой запуск:
```python
from video_producer import create_video

create_video(
    soundtrack='path/to/music.mp3',
    chapter='path/to/chapter.md',
    output='output.mp4'
)
```

### Расширенный контроль:
```python
from video_producer import VideoProducer

producer = VideoProducer(config=video_config)
producer.load_soundtrack('music.mp3')
producer.load_chapter('chapter.md')
producer.analyze_music()
producer.sync_text()
producer.preview(start=0, duration=10)  # превью первых 10 сек
producer.render('final.mp4')
```

## Troubleshooting

### Проблема: Текст не помещается на экране
**Решение:** Уменьшить font size или разбить на несколько субтитров

### Проблема: Десинхронизация к концу видео
**Решение:** Проверить sample rate аудио, использовать librosa.load с sr=None

### Проблема: Медленный рендеринг
**Решение:** Использовать preset='ultrafast' для тестов, 'slow' только для финала

## Метаданные Проекта

- **Создано:** 2026-01-18
- **Python:** 3.12.2
- **Платформа:** macOS ARM64
- **Рабочая директория:** `/Users/kh./Python/Ничто_Nothing_无_金元Ɉ/Монтана_Montana_蒙大拿/Русский/Благаявесть/`

## Git Workflow

```bash
# Коммиты видео не нужны (большие файлы)
# Добавить в .gitignore:
video/*.mp4
video/*.mov
саундтрек_*.mp3

# Коммитить только:
- Конфигурационные файлы
- Скрипты обработки
- SRT субтитры (текстовые, легкие)
```

---

**Статус:** Готово к производству ✓
**Следующий шаг:** Получить саундтрек от пользователя и начать с первой главы
