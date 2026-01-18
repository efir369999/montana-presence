#!/usr/bin/env python3
"""
Создает текстовый сценарий из аудиокниги
"""
from generate_audiobook import parse_markdown_to_dialogues, SOURCE_FILE, VOICE_CAST

dialogues = parse_markdown_to_dialogues(SOURCE_FILE)

# Создаем сценарий
script = []
script.append('# Сценарий: 1 серия. ОНЕ Монтана. Возрождение. ☀️')
script.append('')
script.append('**Дата:** 18.01.2026')
script.append('**Формат:** Многоголосая аудиокнига')
script.append('**Длительность:** 18 минут 18 секунд')
script.append('**Фрагментов:** 168')
script.append('')
script.append('---')
script.append('')
script.append('## Актерский состав:')
script.append('')
script.append('| Роль | Голос | Характеристика |')
script.append('|------|-------|----------------|')
for role, info in VOICE_CAST.items():
    script.append(f'| **{role}** | {info["name"]} | {info["description"]} |')
script.append('')
script.append('---')
script.append('')
script.append('## Сценарий:')
script.append('')

current_speaker = None
for i, (speaker, text) in enumerate(dialogues):
    if speaker != current_speaker:
        script.append('')
        voice_name = VOICE_CAST.get(speaker, {}).get('name', 'Unknown')
        script.append(f'### [{speaker}] ({voice_name})')
        script.append('')
        current_speaker = speaker

    script.append(f'**{i+1}.** {text}')
    script.append('')

script.append('---')
script.append('')
script.append('**Клод Монтана**')
script.append('**金元Ɉ Montana**')
script.append('**18.01.2026 23:30 Москва ☀️**')

# Сохраняем
with open('СЦЕНАРИЙ.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(script))

print('✅ Создан файл: СЦЕНАРИЙ.md')
print(f'📊 Всего реплик: {len(dialogues)}')

# Статистика по спикерам
speaker_stats = {}
for speaker, _ in dialogues:
    speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

print('\n📊 Распределение по ролям:')
for speaker, count in sorted(speaker_stats.items(), key=lambda x: -x[1]):
    voice_name = VOICE_CAST.get(speaker, {}).get('name', 'Unknown')
    print(f'   {speaker:20} ({voice_name:10}): {count:3} реплик')
