# Security Audit: Presence Proof Manipulation via tau1_bitmap

**Модель:** Grok 3
**Компания:** xAI
**Дата:** 08.01.2026 12:00 UTC

---

## 1. Понимание архитектуры

Montana реализует уникальную архитектуру Atemporal Coordinate Presence (ACP), где присутствие доказывается через P2P-аттестацию в реальном времени. Система использует временные слои (τ₁, τ₂, τ₃, τ₄) для накопления веса участников.

Ключевые особенности:
- Присутствие требует реального времени (14 дней требуют 14 дней)
- Детерминированная лотерея защищена от grinding
- Адаптивный кулдаун предотвращает Sybil-атаки
- Eclipse защита через full bootstrap каждый рестарт

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| `types.rs` | 600+ | PresenceProof структура, tau1_bitmap |
| `consensus.rs` | 400+ | Лотерея, seed генерация |
| `cooldown.rs` | 260+ | Адаптивный кулдаун |
| `net/protocol.rs` | 1600+ | P2P обработка сообщений |
| `net/bootstrap.rs` | 800+ | Full bootstrap верификация |
| `net/verification.rs` | 800+ | Hardcoded node аутентификация |

---

## 3. Attack Surface

Основные точки входа для атакующего:
- PresenceProof с tau1_bitmap (10 бит для 10 минут присутствия)
- Лотерея seed генерация (зависит от presence_root)
- Cooldown_until поле в PresenceProof
- Локальное время узла для timestamp валидации

---

## 4. Найденные уязвимости

### HIGH Название уязвимости: Presence Proof Manipulation via tau1_bitmap

**Файл:** `src/types.rs:187`

**Уязвимый код:**
```rust
pub struct PresenceProof {
    pub tau1_bitmap: u16,  // 10 bits for 10 minutes
    // ...
}

impl PresenceProof {
    pub fn tau1_count(&self) -> u32 {
        self.tau1_bitmap.count_ones()
    }

    pub fn meets_threshold(&self) -> bool {
        self.tau1_count() >= 9  // 90% = 9/10
    }
}
```

**Вектор атаки:**
1. Атакующий создаёт PresenceProof с tau1_bitmap = 0b1111111111 (все 10 бит установлены)
2. Подписывает proof с валидным ключом и prev_slice_hash
3. Отправляет proof в сеть во время τ₂
4. Система принимает proof как доказательство полного присутствия за 10 минут
5. Атакующий получает полный вес τ₂ без реального присутствия

**Импакт:** Атакующий может получить 100% вес τ₂ (1 слайс) без реального присутствия, нарушая принцип "время = реальное время".

**Сложность:** LOW - требует только валидного ключа и знания prev_slice_hash.

### MEDIUM Название уязвимости: Non-deterministic presence_root

**Файл:** `src/consensus.rs:23-29`

**Уязвимый код:**
```rust
pub fn compute_lottery_seed(prev_hash: &Hash, tau2_index: u64, presence_root: &Hash) -> Hash {
    let mut data = Vec::with_capacity(72);
    data.extend_from_slice(prev_hash);
    data.extend_from_slice(&tau2_index.to_le_bytes());
    data.extend_from_slice(presence_root);
    sha3(&data)
}
```

**Вектор атаки:**
1. Если presence_root не детерминирован между узлами (разные наборы proofs)
2. Разные узлы вычисляют разные seed'ы
3. Лотерея даёт разных победителей
4. Сеть форкается, ChainWeight становится неэффективным

**Импакт:** Fork-атака, где атакующий может создать альтернативную цепь с подконтрольным победителем.

**Сложность:** MEDIUM - требует контроля над достаточным количеством proofs для создания другого presence_root.

### MEDIUM Название уязвимости: Cooldown bypass via cooldown_until manipulation

**Файл:** `src/types.rs:192`

**Уязвимый код:**
```rust
pub struct PresenceProof {
    pub cooldown_until: u64,
    // ...
}

impl PresenceProof {
    pub fn in_cooldown(&self) -> bool {
        self.cooldown_until > self.tau2_index
    }
}
```

**Вектор атаки:**
1. Атакующий устанавливает cooldown_until = 0 в PresenceProof
2. Подписывает proof и отправляет в сеть
3. Система считает узел активным (не в кулдауне)
4. Узел получает вес несмотря на требуемый кулдаун

**Импакт:** Нарушение адаптивного кулдауна, Sybil-атака становится эффективнее.

**Сложность:** MEDIUM - требует модификации структуры, но поле не валидируется на уровне P2P.

### LOW Название уязвимости: Timestamp manipulation in presence proofs

**Файл:** `src/types.rs:189`

**Уязвимый код:**
```rust
pub struct PresenceProof {
    pub timestamp: u64,    // P2P time attestation
    // ...
}
```

**Вектор атаки:**
1. Атакующий контролирует локальное время узла (malware)
2. Устанавливает timestamp в будущем или прошлом
3. Создаёт proofs с манипулированными timestamps
4. Может нарушить порядок в presence_root (canonical_order)

**Импакт:** Нарушение детерминированности presence_root, потенциальные форки.

**Сложность:** HIGH - требует локального доступа к узлу (malware).

---

## 5. Атаки, которые НЕ работают

- **Eclipse атаки:** Full bootstrap (100 peers, 25+ subnets) + NTS reality check
- **Sybil атаки:** Адаптивный кулдаун (1 день минимум, сглаживание 56 дней)
- **Long-range атаки:** Хеш-цепь с криптографическими привязками
- **Time-warp атаки:** MTP (11 слайсов) + future limit (2 часа)
- **Lottery grinding:** Seed фиксирован prev_slice_hash

---

## 6. Рекомендации

### Для tau1_bitmap уязвимости:
```rust
// Добавить валидацию в P2P обработку
impl PresenceProof {
    pub fn validate_tau1_bitmap(&self, current_tau2_start: u64) -> bool {
        // Проверить что биты соответствуют реальным минутам τ₂
        // Требовать доказательства для каждого установленного бита
        unimplemented!()
    }
}
```

### Для presence_root детерминированности:
```rust
// Усилить canonical_order с дополнительными проверками
pub fn canonical_order_with_validation(proofs: &[PresenceProof]) -> Vec<Proof> {
    // Сортировать по (timestamp, hash) с валидацией timestamp ∈ τ₂
    unimplemented!()
}
```

### Для cooldown_until:
```rust
// Добавить верификацию cooldown_until в bootstrap
pub fn verify_cooldown_until(&self, proof: &PresenceProof) -> bool {
    // Проверить что cooldown_until соответствует сети
    unimplemented!()
}
```

---

## 7. Вердикт

[ ] CRITICAL — есть уязвимости, позволяющие уничтожить сеть
[ ] HIGH — есть серьёзные уязвимости
[X] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено

**Общий риск:** MEDIUM - уязвимости позволяют манипулировать присутствием, но не уничтожают сеть. Система имеет сильную защиту от catastrophic атак (eclipse, Sybil), но есть локальные манипуляции с presence proofs.
