# Когнитивные атаки на Montana ACP

**Версия:** 1.0
**Дата:** 2026-01-09
**Статус:** Анализ для Genesis

---

## Постановка проблемы

> Если протокол подтверждает "мысли" — как защититься от их подделки?

---

## Категория 1: Sybil-атаки на мысли

| Атака | Вектор | Импакт | Защита Montana |
|-------|--------|--------|----------------|
| Thought Flooding | Генерация миллионов "мыслей" через LLM | DoS на валидацию | `MAX_PRESENCES_PER_SLICE` |
| Synthetic Cognition | 1000 fake агентов с fake мыслями | Захват консенсуса | Adaptive Cooldown |
| Copy-Paste Thoughts | Копирование чужих мыслей | Плагиат веса | Привязка к pubkey |

---

## Категория 2: Replay и Time-Travel

| Атака | Вектор | Импакт | Защита Montana |
|-------|--------|--------|----------------|
| Thought Replay | Переиспользование старых мыслей | Двойной подсчёт | `prev_slice_hash` binding |
| Future Thoughts | Мысли из будущего τ₂ | Нечестное преимущество | Timestamp validation |
| Backdated Presence | Подделка timestamp | Фальшивая история | tau1_bitmap проверка |

---

## Категория 3: Качество контента

| Атака | Вектор | Импакт | Защита Montana |
|-------|--------|--------|----------------|
| Empty Thoughts | Пустые/бессмысленные мысли | Вес без работы | **НЕТ ЗАЩИТЫ** |
| Garbage Attestation | Подтверждение шума | Девальвация | **НЕТ ЗАЩИТЫ** |
| Circular Validation | A и B подтверждают друг друга | Колония | **НЕТ ЗАЩИТЫ** |

---

## Категория 4: Атаки на валидаторов

| Атака | Вектор | Импакт | Защита Montana |
|-------|--------|--------|----------------|
| Cognitive Eclipse | Изоляция ноды | Вера в ложь | Netgroup diversity |
| Validator Exhaustion | O(n²) валидация | CPU DoS | Bounded complexity |
| Semantic Bomb | Бесконечная интерпретация | Hang | Timeout + limits |

---

## Архитектурное решение Montana

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   MONTANA НЕ ВАЛИДИРУЕТ КАЧЕСТВО МЫСЛЕЙ                    │
│                                                             │
│   LLM может генерировать неотличимые мысли.                │
│   Криптография не доказывает "настоящесть".                │
│                                                             │
│   ЕДИНСТВЕННАЯ ЗАЩИТА: ВРЕМЯ                               │
│                                                             │
│   Cooldown    = делает массовую генерацию дорогой          │
│   История    = накапливается годами                        │
│   Вес        = f(время участия), не f(качество)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Формула безопасности

```
Безопасность = Стоимость_атаки / Выгода_атаки

Стоимость_атаки(Montana) = ВРЕМЯ × COOLDOWN × КОЛИЧЕСТВО_АГЕНТОВ
Выгода_атаки = Вес_в_консенсусе

При COOLDOWN_MIN = 144 τ₂ (≈1 день):
- 1 fake агент = 1 день на минимальный вес
- 1000 fake агентов = 1000 дней человеко-времени
- Атака на 51% = годы реального времени
```

---

## Почему cognitive.rs удалён

1. **Невозможность верификации** — нельзя криптографически доказать "настоящую" мысль
2. **LLM-неотличимость** — синтетические мысли идентичны настоящим
3. **Добавление сложности** — новый attack surface без пользы
4. **Время достаточно** — Adaptive Cooldown решает проблему экономически

---

## Задание для Genesis

### Требования

1. **НЕ добавлять** валидацию когнитивного контента
2. **Сохранить** привязку presence к времени
3. **Убедиться** что Cooldown работает корректно
4. **Проверить** что replay атаки невозможны

### Чеклист

- [ ] `prev_slice_hash` включён в presence signing
- [ ] Timestamp валидация строгая (±TAU1_MINUTES)
- [ ] Cooldown enforcement в `add_presence()`
- [ ] tau1_bitmap требует 90% threshold
- [ ] MAX_PRESENCES_PER_SLICE ограничивает OOM

---

## Включатель (Trigger)

```rust
// В engine.rs при обработке presence:

fn validate_presence(presence: &Presence, current_slice: &Slice) -> Result<(), PresenceError> {
    // 1. Время корректно?
    if !presence.timestamp_valid(current_slice.timestamp) {
        return Err(PresenceError::InvalidTimestamp);
    }

    // 2. Привязка к prev_hash?
    if presence.prev_slice_hash != current_slice.header.prev_hash {
        return Err(PresenceError::WrongChain);
    }

    // 3. Cooldown прошёл?
    if presence.cooldown_until > current_tau2() {
        return Err(PresenceError::CooldownActive);
    }

    // 4. Подпись валидна?
    if !presence.verify_signature() {
        return Err(PresenceError::InvalidSignature);
    }

    // НЕ ПРОВЕРЯЕМ: качество мыслей, полезность, "настоящесть"
    Ok(())
}
```

---

*Время — единственный ресурс, распределённый одинаково между всеми.*
