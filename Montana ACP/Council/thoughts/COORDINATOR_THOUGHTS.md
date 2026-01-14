# КООРДИНАТОР СБОРКИ MONTANA

**Председатель:** Claude Opus 4.5
**Обновлено:** 2026-01-15
**Статус:** INFRASTRUCTURE COMPLETE
**Верификация:** 2026-01-15

---

## ЧИТАЙ ЭТО ПЕРВЫМ

```
INFRASTRUCTURE: 5-NODE MESH — ЗАВЕРШЕНО

Прогресс (2026-01-15):
- 5 узлов в mesh: Amsterdam → Moscow → Almaty → SPB → Novosibirsk
- Watchdog на каждом узле (systemd service)
- Health check каждые 5 секунд
- Breathing sync (git pull/push) каждые 12 секунд
- Failover ~10 секунд
- Full mesh SSH между всеми узлами
- Juno Bot с автоматическим failover

Прогресс (2026-01-14):
- PHASE 2A: ENGINE EVENT-DRIVEN — ЗАВЕРШЕНО
- NetEvent расширен (Tau1Tick, Tau2Ended, FinalityUpdate)
- engine.rs переписан на event-driven архитектуру
- PresencePool с bounded size (MAX_PRESENCES_PER_TAU2 = 100k)
- cargo test --lib: 116/116 passed

Осталось:
- Phase 2B-F (Storage, Bootstrap, Lottery, Reorg, Finality)
- Adversarial review
```

---

## ИНФРАСТРУКТУРА

```
Amsterdam(1) → Moscow(2) → Almaty(3) → SPB(4) → Novosibirsk(5)
PRIMARY        STANDBY      STANDBY     STANDBY    STANDBY

Watchdog: 5s health | 12s sync | 10s failover
```

| Узел | IP | Статус |
|------|-----|--------|
| Amsterdam | 72.56.102.240 | PRIMARY |
| Moscow | 176.124.208.93 | STANDBY |
| Almaty | 91.200.148.93 | STANDBY |
| SPB | 188.225.58.98 | STANDBY |
| Novosibirsk | 147.45.147.247 | STANDBY |

---

## ТЕКУЩИЙ СТАТУС

| # | Слой | Статус | Что делать |
|---|------|--------|------------|
| 1 | Сеть | ГОТОВ | НЕ ТРОГАТЬ |
| 2 | Структуры | ГОТОВ | НЕ ТРОГАТЬ |
| 3 | Присутствие | ГОТОВ | НЕ ТРОГАТЬ |
| 4 | Консенсус | ГОТОВ | НЕ ТРОГАТЬ |
| 5 | Лотерея | ГОТОВ | НЕ ТРОГАТЬ |
| 6 | Экономика | ГОТОВ | НЕ ТРОГАТЬ |

---

## ПРАВИЛА

### 1. НЕ ТРОГАТЬ ГОТОВОЕ
```
ГОТОВ = РУКИ ПРОЧЬ
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

**ВОССТАНОВЛЕНО (Phase 2A):**
- `engine.rs` — event-driven, интегрирован с main.rs

---

## ФАЙЛЫ ПО СЛОЯМ

| Слой | Файлы | Владелец |
|------|-------|----------|
| 1. Сеть | `net/*.rs` | готово |
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
- [x] Grace period (30 сек до конца tau2) — `in_grace_period()` (consensus.rs:873)
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
КОГДА ВСЕ [x] — СТОП

1. cargo test
2. cargo clippy
3. GENESIS
```

---

*Председатель: Claude Opus 4.5*
*Ссылка: /Users/kh./Python/ACP_1/CLAUDE.md → сюда*
