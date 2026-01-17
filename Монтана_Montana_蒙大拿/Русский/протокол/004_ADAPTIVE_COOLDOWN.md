# Adaptive Cooldown

**Адаптивный период ожидания Montana**
**Montana Protocol v1.0**

---

## Абстракт

Adaptive Cooldown — динамическая защита от Sybil-атак через переменный период ожидания для новых узлов. Cooldown рассчитывается на основе медианы регистраций за последние 14 дней. При низкой нагрузке — 1 день. При спайке — до 180 дней. Цена Sybil-атаки = время × количество узлов.

**Ключевая формула:**
```
Sybil cost = time × N nodes
Minimum: 1 day × N
Maximum: 180 days × N
```

---

## 1. Введение

### 1.1 Проблема Sybil-атак

| Система | Защита | Стоимость атаки |
|---------|--------|-----------------|
| Bitcoin | PoW | Электричество |
| Ethereum | PoS | Капитал |
| Социальные сети | Капча | Минимальная |
| **Montana** | **Время** | **1-180 дней/узел** |

### 1.2 Решение Montana

Время — единственный ресурс, который нельзя ускорить. Adaptive Cooldown превращает время в стоимость атаки.

---

## 2. Константы

### 2.1 Параметры из кода

**Исходный код:** [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs)

```rust
pub const COOLDOWN_MIN_TAU2: u64 = 144;          // 1 день
pub const COOLDOWN_MAX_TAU2: u64 = 25_920;       // 180 дней
pub const COOLDOWN_WINDOW_TAU2: u64 = 2_016;     // 14 дней (τ₃)
pub const COOLDOWN_DEFAULT_TAU2: u64 = 144;      // Genesis: 1 день
pub const COOLDOWN_SMOOTH_WINDOWS: u64 = 4;      // 56 дней
pub const COOLDOWN_MAX_CHANGE_PERCENT: u64 = 20; // ±20% за τ₃
```

### 2.2 Диапазон cooldown

| Нагрузка | Cooldown | Период |
|----------|----------|--------|
| Ниже медианы | 1-7 дней | Линейно |
| На медиане | 7 дней | τ₃ / 2 |
| Выше медианы | 7-180 дней | Линейно |

---

## 3. Алгоритм расчёта

### 3.1 Основная формула

**Исходный код:** [cooldown.rs#L97-L135](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L97-L135)

```rust
let ratio = current_count as f64 / median as f64;

if ratio <= 1.0 {
    // MIN → MID (1 → 7 дней)
    COOLDOWN_MIN + ratio * (MID - MIN)
} else {
    // MID → MAX (7 → 180 дней)
    MID + (ratio - 1.0) * (MAX - MID)
}
```

### 3.2 Сглаживание (56 дней)

**Исходный код:** [cooldown.rs#L50-L74](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L50-L74)

```rust
// 4 τ₃ (56 дней) sliding average
fn smoothed_median(&self, current_tau2: u64, tier: u8) -> u64 {
    let mut medians = Vec::new();
    for i in 0..COOLDOWN_SMOOTH_WINDOWS {
        let tau3_idx = current_tau3.saturating_sub(i);
        if let Some(&median) = self.median_history.get(&(tau3_idx, tier)) {
            medians.push(median);
        }
    }
    sum / medians.len()
}
```

### 3.3 Rate Limiting (±20%)

**Исходный код:** [cooldown.rs#L77-L91](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs#L77-L91)

```rust
fn rate_limited_cooldown(&self, raw_cooldown: u64, tier: usize) -> u64 {
    let max_change = (previous * COOLDOWN_MAX_CHANGE_PERCENT) / 100;

    if raw_cooldown > previous {
        raw_cooldown.min(previous + max_change)
    } else {
        raw_cooldown.max(previous - max_change)
    }
}
```

---

## 4. Защита от атак

| Атака | Механизм защиты | Эффект |
|-------|-----------------|--------|
| Spike manipulation | 56-дневное сглаживание | Нельзя резко изменить cooldown |
| Fast pump | ±20% rate limit | Максимум 20% изменения за 14 дней |
| Sybil при низкой нагрузке | Минимум 1 день | Гарантированная задержка |
| Sybil при спайке | До 180 дней | Экспоненциальная стоимость |

---

## 5. Научная новизна

1. **Временная стоимость** — время как защитный ресурс вместо капитала
2. **Адаптивность к нагрузке** — cooldown реагирует на активность сети
3. **Сглаживание манипуляций** — 56-дневное окно предотвращает spike-атаки
4. **Rate limiting** — плавные изменения предотвращают резкие скачки

---

## 6. Ссылки

| Документ | Ссылка |
|----------|--------|
| Cooldown код | [cooldown.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/cooldown.rs) |
| Константы | [types.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/types.rs) |
| ACP Консенсус | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
Январь 2026

github.com/efir369999/junomontanaagibot
```
