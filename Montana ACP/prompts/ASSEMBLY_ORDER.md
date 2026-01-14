# ПОРЯДОК СБОРКИ MONTANA

**Версия:** 1.0
**Статус:** В РАБОТЕ

---

## СТОП-УСЛОВИЕ

**Когда ВСЕ слои отмечены [x] — ОСТАНОВИТЬСЯ.**

Не добавлять новые фичи. Не рефакторить. Не "улучшать".
Система готова к запуску genesis.

---

## Слои (в порядке зависимостей)

```
┌─────────────────────────────────────────────────────────┐
│  СЛОЙ 6: ЭКОНОМИКА                                      │
│  Тиры, кулдаун, халвинг, награды                        │
├─────────────────────────────────────────────────────────┤
│  СЛОЙ 5: ЛОТЕРЕЯ                                        │
│  Выбор победителя τ₂, backup slots, seed               │
├─────────────────────────────────────────────────────────┤
│  СЛОЙ 4: КОНСЕНСУС                                      │
│  Комитет, голосование, финальность                      │
├─────────────────────────────────────────────────────────┤
│  СЛОЙ 3: ПРИСУТСТВИЕ                                    │
│  Подписание координат, presence_root, bitmap            │
├─────────────────────────────────────────────────────────┤
│  СЛОЙ 2: СТРУКТУРЫ ДАННЫХ                               │
│  Slice, SliceHeader, PresenceProof, Transaction         │
├─────────────────────────────────────────────────────────┤
│  СЛОЙ 1: СЕТЬ                                           │
│  P2P, gossip, handshake, bootstrap                      │
└─────────────────────────────────────────────────────────┘
```

---

## Чеклист готовности

### Слой 1: Сеть
- [x] P2P соединения (TCP + Noise)
- [x] Handshake протокол
- [x] Bootstrap от hardcoded peers
- [x] Gossip распространение
- [x] Rate limiting
- [x] Eclipse protection (netgroup diversity)
- [x] Адрес-менеджер (NEW/TRIED buckets)

**Файлы:** `net/*.rs`
**Статус:** ✅ ГОТОВ

---

### Слой 2: Структуры данных
- [x] `Hash`, `PublicKey`, `Signature` типы
- [x] `SliceHeader` с cumulative_weight
- [x] `Slice` с presences, transactions
- [x] `PresenceProof` с tau1_bitmap
- [x] `Transaction` с inputs/outputs
- [x] `NodeWeight` с тирами
- [x] Merkle proof для light clients

**Файлы:** `types.rs`, `merkle.rs`
**Статус:** ✅ ГОТОВ

---

### Слой 3: Присутствие
- [x] Подписание координат (timestamp + prev_hash + pubkey)
- [x] tau1_bitmap сбор (10 бит на τ₂)
- [x] presence_root вычисление (через MerkleTree)
- [x] 90% threshold проверка (`PresenceProof.meets_threshold()`)
- [x] Cooldown tracking в presence (`cooldown_until`)

**Файлы:** `types.rs` (PresenceProof), `consensus.rs` (FullNodePresence, VerifiedUserPresence)
**Статус:** ✅ ГОТОВ

---

### Слой 4: Консенсус
- [x] FinalityTracker (attestations)
- [x] FinalityStatus (SAFE/FINAL)
- [x] FinalityCheckpoint (каждые τ₃)
- [x] ForkChoice (heaviest chain)
- [x] Slice validation (`Slice.verify()` в consensus.rs)
- [x] Reorg handling (`ForkChoice.can_reorg_to()`)

**Файлы:** `finality.rs`, `fork_choice.rs`, `consensus.rs`
**Статус:** ✅ ГОТОВ

---

### Слой 5: Лотерея
- [x] Seed = SHA3(prev_hash || τ₂_index)
- [x] Ticket = SHA3(seed || pubkey)
- [x] 10 backup slots (SLOTS_PER_TAU2)
- [x] 80/20 tier caps (FULL_NODE_CAP_PERCENT, VERIFIED_USER_CAP_PERCENT)
- [x] Grace period enforcement (`in_grace_period()`)
- [x] Slot timeout handling (SLOT_DURATION_SECS)

**Файлы:** `consensus.rs` (Lottery)
**Статус:** ✅ ГОТОВ

---

### Слой 6: Экономика
- [x] Тиры веса (TIER1_WEIGHT=1, TIER2_WEIGHT=20, TIER3_WEIGHT=60480, TIER4_WEIGHT=8409600)
- [x] COOLDOWN_MIN/MAX/WINDOW константы
- [x] AdaptiveCooldown медианы (smoothed median, rate limiting)
- [x] Халвинг (HALVING_INTERVAL = 210000 slices)
- [x] calculate_reward() с халвингом
- [x] Интеграция cooldown с PresenceProof (cooldown_until)

**Файлы:** `types.rs`, `cooldown.rs`
**Статус:** ✅ ГОТОВ

---

## Правила работы

### 1. Один слой за раз
Не начинать следующий слой пока предыдущий не [x].

### 2. Тесты обязательны
Каждый компонент должен иметь unit тесты.
```
cargo test --lib [module_name]
```

### 3. Проверка компиляции
После каждого изменения:
```
cargo check
```

### 4. Без костылей
Если что-то требует "временного решения" — это архитектурная проблема.
Исправить архитектуру, не добавлять костыль.

### 5. Документация в коде
```rust
/// Краткое описание (одна строка)
///
/// Детали если нужны.
pub fn function() { }
```

---

## Критерии ГОТОВ

Слой считается готовым когда:

1. **Компилируется** без ошибок
2. **Тесты проходят** (cargo test --lib)
3. **Интегрируется** с предыдущими слоями
4. **Нет TODO** в коде
5. **Нет panic!()** в production paths

---

## После завершения всех слоёв

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   ВСЕ СЛОИ [x] = СТОП                                  │
│                                                         │
│   1. Запустить полный cargo test                       │
│   2. Проверить cargo clippy                            │
│   3. Сгенерировать genesis                             │
│   4. Запустить первую ноду                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**НЕ ДОБАВЛЯТЬ:**
- Новые фичи
- Оптимизации
- Рефакторинг
- "Улучшения"

**Genesis = точка отсчёта. Изменения только через governance.**

---

## Текущий статус

| Слой | Название | Статус | Прогресс |
|------|----------|--------|----------|
| 1 | Сеть | ✅ | 100% |
| 2 | Структуры данных | ✅ | 100% |
| 3 | Присутствие | ✅ | 100% |
| 4 | Консенсус | ✅ | 100% |
| 5 | Лотерея | ✅ | 100% |
| 6 | Экономика | ✅ | 100% |

**Общий прогресс:** 100%

---

## Следующие шаги

**ВСЕ СЛОИ ЗАВЕРШЕНЫ ✅**

1. ✅ Merkle proofs реализованы (Слой 2)
2. ✅ Presence signing интегрирован (Слой 3)
3. ✅ Slice validation добавлена (Слой 4)
4. ✅ Grace period реализован (Слой 5)
5. ✅ Cooldown интегрирован (Слой 6)

**Готово к Фазе 2:**
- Интеграция всех модулей в `engine.rs`
- End-to-end тестирование
- Genesis generation

---

*Когда все [x] — Montana готова к genesis.*
