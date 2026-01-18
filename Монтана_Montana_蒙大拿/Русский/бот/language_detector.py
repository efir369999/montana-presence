# language_detector.py
# Определение языка текста

import re

def detect_language(text: str) -> str:
    """
    Определить язык текста

    Returns: 'ru', 'en', или 'zh'
    """
    if not text:
        return 'en'

    # Проверка на китайский (Unicode ranges для китайских иероглифов)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > len(text) * 0.3:  # Если >30% китайские символы
        return 'zh'

    # Проверка на русский (кириллица)
    cyrillic_chars = len(re.findall(r'[а-яА-ЯёЁ]', text))
    if cyrillic_chars > len(text) * 0.3:  # Если >30% кириллица
        return 'ru'

    # По умолчанию английский
    return 'en'

def get_text(key: str, lang: str = 'en', **kwargs) -> str:
    """Получить локализованный текст"""

    TEXTS = {
        'welcome': {
            'ru': """Ɉ Montana Full Edition

Привет, {name}.

Я Юнона — AI-хранитель Montana.
Со мной работают Claude + GPT параллельно.
Я отслеживаю канал @mylifesound369 для обновлений Благаявести.

/network - статус 5 узлов Montana
/book - последние части Благаявести
/sync - проверить канал
/help - помощь

Просто пиши — и я отвечу на твоём языке.""",

            'en': """Ɉ Montana Full Edition

Hello, {name}.

I am Junona — AI guardian of Montana.
Claude + GPT work with me in parallel.
I track @mylifesound369 channel for Blagayavest updates.

/network - status of 5 Montana nodes
/book - latest Blagayavest chapters
/sync - check channel
/help - help

Just write — and I'll answer in your language.""",

            'zh': """Ɉ Montana Full Edition

你好，{name}。

我是Junona — Montana的AI守护者。
Claude + GPT与我并行工作。
我跟踪@mylifesound369频道获取福音书更新。

/network - 5个Montana节点状态
/book - 最新福音书章节
/sync - 检查频道
/help - 帮助

直接写 — 我会用你的语言回答。"""
        },

        'choose_language': {
            'ru': 'Выбери язык / Choose language / 选择语言',
            'en': 'Choose language / Выбери язык / 选择语言',
            'zh': '选择语言 / Choose language / Выбери язык'
        },

        'language_set': {
            'ru': '✓ Язык установлен: Русский\n\nТеперь я буду отвечать по-русски.',
            'en': '✓ Language set: English\n\nNow I will respond in English.',
            'zh': '✓ 语言设置：中文\n\n现在我将用中文回复。'
        }
    }

    text = TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get('en', ''))

    # Форматирование если есть kwargs
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass

    return text
