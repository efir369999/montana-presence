# КООРДИНАТОР СБОРКИ MONTANA

**Председатель:** Claude Opus 4.5
**Обновлено:** 2026-01-09 (текущая дата)
**Статус:** ✅ ВСЕ СЛОИ ЗАВЕРШЕНЫ
**Верификация:** 2026-01-09

---

## ЧИТАЙ ЭТО ПЕРВЫМ

```
✅ ВСЕ СЛОИ ЗАВЕРШЕНЫ

СТОП-УСЛОВИЕ АКТИВИРОВАНО:
- НЕ ДОБАВЛЯТЬ ФИЧИ
- НЕ РЕФАКТОРИТЬ
- НЕ "УЛУЧШАТЬ"
- ГОТОВО К GENESIS

Верификация (2026-01-09):
✅ cargo test --lib: 113/113 passed
✅ cargo check: 10 warnings, 0 errors
   - 8x ip_to_subnet16 deprecated → Phase 2
   - 2x dead code (ek, read/write_message) → Phase 2

Следующий этап: Фаза 2 (engine.rs интеграция)
```

---

## ТЕКУЩИЙ СТАТУС

| # | Слой | Статус | Что делать |
|---|------|--------|------------|
| 1 | Сеть | ✅ ГОТОВ | НЕ ТРОГАТЬ |
| 2 | Структуры | ✅ ГОТОВ | НЕ ТРОГАТЬ |
| 3 | Присутствие | ✅ ГОТОВ | НЕ ТРОГАТЬ |
| 4 | Консенсус | ✅ ГОТОВ | НЕ ТРОГАТЬ |
| 5 | Лотерея | ✅ ГОТОВ | НЕ ТРОГАТЬ |
| 6 | Экономика | ✅ ГОТОВ | НЕ ТРОГАТЬ |

---

## ПРАВИЛА

### 1. НЕ ТРОГАТЬ ГОТОВОЕ
```
✅ = РУКИ ПРОЧЬ
Сеть (net/*.rs) готова. Не рефакторить.
```

### 2. ОДИН АГЕНТ = ОДИН ФАЙЛ
```
Работаешь над finality.rs → не трогай consensus.rs
Работаешь над types.rs → не трогай merkle.rs
```

### 3. ТЕСТЫ
```bash
CARGO_TARGET_DIR=/tmp/montana_test cargo test --lib [module]
```

### 4. ПРОВЕРКА
```bash
CARGO_TARGET_DIR=/tmp/montana_test cargo check
```

---

## УДАЛЁННЫЕ МОДУЛИ

**НЕ ВОССТАНАВЛИВАТЬ:**
- `cognitive.rs` — удалён
- `engine.rs` — закомментирован (Фаза 2)

---

## ФАЙЛЫ ПО СЛОЯМ

| Слой | Файлы | Владелец |
|------|-------|----------|
| 1. Сеть | `net/*.rs` | ✅ готово |
| 2. Структуры | `types.rs`, `merkle.rs` | — |
| 3. Присутствие | `types.rs` (PresenceProof) | — |
| 4. Консенсус | `finality.rs`, `fork_choice.rs` | — |
| 5. Лотерея | `consensus.rs` (Lottery) | — |
| 6. Экономика | `cooldown.rs` | — |

---

## ЗАДАЧИ (TODO)

### Слой 2: Структуры
- [x] Все структуры данных готовы (Slice, Transaction, PresenceProof, MerkleTree)

### Слой 3: Присутствие
- [x] `PresenceProof.verify()` метод (в consensus.rs: FullNodePresence, VerifiedUserPresence)
- [x] `compute_presence_root()` (Slice.compute_presence_root() в consensus.rs)
- [x] tau1_bitmap 90% threshold (PresenceProof.meets_threshold())

### Слой 4: Консенсус
- [x] `Slice.verify()` полная (consensus.rs:720)
- [x] Reorg в `fork_choice.rs` (can_reorg_to(), MAX_REORG_DEPTH)

### Слой 5: Лотерея
- [x] Grace period (30 сек до конца τ₂) — `in_grace_period()` (consensus.rs:873)
- [x] Slot timeout → backup producer (SLOTS_PER_TAU2 = 10)

### Слой 6: Экономика
- [x] AdaptiveCooldown реализован (cooldown.rs)
- [x] Тиры веса интегрированы (types.rs: TIER1-4_WEIGHT)
- [x] Cooldown tracking в PresenceProof (cooldown_until поле)

---

## КОММУНИКАЦИЯ

**Если взял задачу:**
1. Напиши в `Council/thoughts/[твой_id]_working.md`
2. Укажи какой файл

**Если закончил:**
1. Обнови этот файл (поставь [x])
2. Удали свой _working.md

**Если нашёл баг:**
1. Создай `Council/thoughts/[твой_id]_bug_[дата].md`
2. Опиши проблему
3. Жди одобрения

---

## ЗАПРЕЩЕНО

- Создавать новые модули
- Менять API готовых модулей
- Добавлять зависимости
- Восстанавливать удалённые файлы
- Работать над 2+ слоями сразу

---

## СТОП-УСЛОВИЕ

```
┌─────────────────────────────────────┐
│                                     │
│   КОГДА ВСЕ [x] — СТОП             │
│                                     │
│   1. cargo test                    │
│   2. cargo clippy                  │
│   3. GENESIS                       │
│                                     │
└─────────────────────────────────────┘
```

---

*Председатель: Claude Opus 4.5*
*Ссылка: /Users/kh./Python/ACP_1/CLAUDE.md → сюда*
