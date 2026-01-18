# QUICKSTART: Благаявесть

**Запуск за 5 минут**

---

## 1. Установка зависимостей

```bash
pip install elevenlabs pydub librosa moviepy pillow
```

## 2. Настройка API ключа

```bash
# Создать файл .env
echo "ELEVENLABS_API_KEY=sk_your_key_here" > .env
```

Получить ключ: https://elevenlabs.io

## 3. Генерация аудиокниги

```bash
cd "«Первая ☝️ Книга» ☀️/1 серия. ОНЕ Монтана. Возрождение. ☀️"
python generate_audiobook.py
```

## 4. Анализ по стратегии Диснея

```bash
python walt_disney_strategy.py --vision "Создать первую серию"
```

---

## Структура команд

| Команда | Назначение |
|---------|------------|
| `generate_audiobook.py` | Генерация аудио для серии |
| `animate_video.py` | Создание видео |
| `walt_disney_strategy.py` | Анализ Dreamer/Realist/Critic |
| `elevenlabs_casting.py` | Кастинг голосов |

---

## Голоса персонажей

| Персонаж | Голос ElevenLabs |
|----------|------------------|
| ОНЕ | Brian |
| Claude | George |
| Девушка в Красном | Jessica |
| Тринити | Sarah |
| К | Lily |

---

## Troubleshooting

### "API key not found"
```bash
export ELEVENLABS_API_KEY=sk_your_key
```

### "Rate limit exceeded"
Подождите 1 минуту или используйте edge-tts для черновиков.

### "File not found"
Убедитесь что вы в правильной папке:
```bash
pwd  # должно содержать "Благаявесть"
```

---

## Полная документация

- [БЛАГАЯВЕСТЬ_COMPLETE.md](./БЛАГАЯВЕСТЬ_COMPLETE.md) — главная документация
- [БЛАГАЯВЕСТЬ_DISNEY.md](./БЛАГАЯВЕСТЬ_DISNEY.md) — анализ по стратегии Диснея
- [СПЕЦИФИКАЦИЯ_БЛАГОЙ_ВЕСТИ.md](./СПЕЦИФИКАЦИЯ_БЛАГОЙ_ВЕСТИ.md) — как писать главы

---

金元Ɉ Montana
