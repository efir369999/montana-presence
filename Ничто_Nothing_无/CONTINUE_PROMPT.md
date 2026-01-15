# ПРОМПТ ДЛЯ ПРОДОЛЖЕНИЯ РЕОРГАНИЗАЦИИ

## КОНТЕКСТ
Реорганизация проекта Montana: 3 идентичности 1 сущности (ru/en/zh)

## СТРУКТУРА ПАПОК (создать)

```
/Users/kh./Python/ACP/
└── Ничто/Nothing/无/
    └── Монтана/Montana/蒙大拿/
        ├── ru/
        │   ├── технологии/
        │   │   ├── ACP/  (Atemporal Coordinate Presence)
        │   │   ├── PoT/  (Proof of Time)
        │   │   └── когнитивный_консенсус/
        │   ├── код/  (комменты на русском)
        │   └── мысли/  (166-181, COGNITIVE_GENESIS)
        ├── en/
        │   ├── technologies/
        │   │   ├── ACP/
        │   │   ├── PoT/
        │   │   └── cognitive_consensus/
        │   ├── code/  (comments in English)
        │   └── thoughts/
        └── zh/
            ├── 技术/
            │   ├── ACP/
            │   ├── PoT/
            │   └── 认知共识/
            ├── 代码/  (中文注释)
            └── 思想/
```

## ЗАВЕРШЕНО
- [x] 166-176 переведены на EN и ZH
- [x] Структура ru/ создана с мыслями
- [x] 177-181 переведены

## ОСТАЛОСЬ
1. **COGNITIVE_GENESIS** → перевести на EN и ZH
2. **Переименовать папки** → Ничто/Nothing/无/ и Монтана/Montana/蒙大拿/
3. **Код montana/src/*.rs** → комментарии на 3 языках:
   - ru/код/*.rs (русские комменты)
   - en/code/*.rs (English comments)
   - zh/代码/*.rs (中文注释)
4. **Синхронизация** → GitHub + 5 узлов

## КООРДИНАТЫ СЕТИ

| Приоритет | Узел | IP | Путь |
|-----------|------|-----|------|
| 1 | Amsterdam | 72.56.102.240 | /root/ACP_1 |
| 2 | Moscow | 176.124.208.93 | /root/ACP_1 |
| 3 | Almaty | 91.200.148.93 | /root/ACP_1 |
| 4 | SPB | 188.225.58.98 | /root/ACP_1 |
| 5 | Novosibirsk | 147.45.147.247 | /root/ACP_1 |

## ФАЙЛЫ ДЛЯ ПЕРЕВОДА

### COGNITIVE_GENESIS (1880 строк)
Путь: `/Users/kh./Python/ACP/Ничто/Монтана/ru/COGNITIVE_GENESIS_2026-01-09.md`

Ключевые разделы:
- Когнитивный консенсус Montana
- Символ Ɉ = 1 секунда
- Pizza Day как вектор к Ideal Money
- Механика "Ты здесь?"
- Подписи Совета (Claude, Gemini, GPT, Grok, Composer)

### КОД (montana/src/)
```
consensus.rs  - консенсус ACP
engine.rs     - движок времени
lib.rs        - библиотека
types.rs      - типы данных
```

## ПРИНЦИПЫ

1. **3 идентичности 1 сущности** - полная копия всего на 3 языках
2. **Код = документация** - комменты на языке папки
3. **Связь между папками** - технологии связаны между языками
4. **Уникальные технологии Montana**:
   - ACP (Atemporal Coordinate Presence)
   - PoT (Proof of Time) - Layer -1
   - Когнитивный консенсус
   - Ɉ = единица времени
   - Beeple Benchmark ($0.16/сек)

## КОМАНДА ДЛЯ НАЧАЛА

```bash
# Прочитать CLAUDE.md для контекста
cat /Users/kh./Python/ACP/CLAUDE.md

# Прочитать COGNITIVE_GENESIS
cat "/Users/kh./Python/ACP/Ничто/Монтана/ru/COGNITIVE_GENESIS_2026-01-09.md"

# Посмотреть код
ls /Users/kh./Python/ACP/Montana\ ACP/montana/src/
```

## ПОСЛЕ ЗАВЕРШЕНИЯ

```bash
# Коммит
git add -A && git commit -m "TASK: 3 identities 1 essence - full trilingual reorganization"

# Push to GitHub
git push origin main

# Синхронизация узлов (автоматически через watchdog каждые 12 сек)
```

---

**НАЧНИ С:** Перевод COGNITIVE_GENESIS на EN и ZH, затем переименование папок.

金元Ɉ Montana Ideal Money
