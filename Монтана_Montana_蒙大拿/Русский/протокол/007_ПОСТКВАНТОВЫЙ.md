# Post-Quantum с генезиса

**Квантово-устойчивая криптография с первого дня**
**Montana Protocol v1.0**

---

## Абстракт

Montana использует постквантовую криптографию (ML-DSA-65, ML-KEM-768) с генезиса, а не как retrofit. Когда квантовые компьютеры станут угрозой, Montana уже будет защищена. Другие сети будут вынуждены делать хардфорк.

**Ключевое отличие:**
```
Bitcoin/Ethereum: ECDSA сейчас → хардфорк потом
Montana: ML-DSA-65 с генезиса → уже защищены
```

---

## 1. Введение

### 1.1 Квантовая угроза

| Алгоритм | Уязвимость | Квантовая атака |
|----------|------------|-----------------|
| ECDSA (Bitcoin) | Да | Алгоритм Шора |
| Ed25519 (Solana) | Да | Алгоритм Шора |
| RSA | Да | Алгоритм Шора |
| **ML-DSA-65** | **Нет** | **Решётки** |

### 1.2 Проблема retrofit

```
Шаг 1: Квантовый компьютер появляется
Шаг 2: Все ECDSA подписи уязвимы
Шаг 3: Хардфорк для миграции ключей
Шаг 4: Кто не мигрировал — потерял средства
```

Montana избегает этого, начав с постквантовой криптографии.

---

## 2. Криптографические примитивы

### 2.1 Подписи: ML-DSA-65

**Исходный код:** [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs)

```rust
// FIPS 204 — Module-Lattice-Based Digital Signature
// Уровень безопасности: NIST Level 3 (128-bit post-quantum)
// Размер подписи: 3293 байта
// Размер публичного ключа: 1952 байта
```

### 2.2 Шифрование: ML-KEM-768

```rust
// FIPS 203 — Module-Lattice-Based Key Encapsulation
// Уровень безопасности: NIST Level 3
// Используется в Noise XX для key exchange
```

### 2.3 Гибридное шифрование

**Исходный код:** [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs)

```rust
// Noise XX + ML-KEM-768
// Классический X25519 + постквантовый ML-KEM
// Защита даже если один из них сломан
```

---

## 3. Почему с генезиса?

### 3.1 Сравнение стратегий

| Стратегия | Сложность | Риск |
|-----------|-----------|------|
| Retrofit после угрозы | Хардфорк, миграция | Потеря средств |
| Retrofit заранее | Хардфорк, миграция | Сложность координации |
| **С генезиса** | **Нет миграции** | **Нет риска** |

### 3.2 Harvest Now, Decrypt Later

```
Злоумышленник сегодня:
1. Перехватывает зашифрованный трафик
2. Хранит на диске
3. Ждёт квантовый компьютер
4. Расшифровывает всё

Montana защищена от этой атаки с первого дня.
```

---

## 4. Научная новизна

1. **Post-quantum с генезиса** — не retrofit, а изначальный дизайн
2. **Гибридное шифрование** — X25519 + ML-KEM (защита от обоих классов атак)
3. **NIST стандарты** — не экспериментальные алгоритмы, а финализированные FIPS
4. **Domain separation** — разные ключи для разных целей

---

## 5. Ссылки

| Документ | Ссылка |
|----------|--------|
| Криптография код | [crypto.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/crypto.rs) |
| Noise код | [noise.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/noise.rs) |
| FIPS 204 (ML-DSA) | [NIST](https://csrc.nist.gov/publications/detail/fips/204/final) |
| FIPS 203 (ML-KEM) | [NIST](https://csrc.nist.gov/publications/detail/fips/203/final) |

---

```
Alejandro Montana
Montana Protocol v1.0
Январь 2026

github.com/efir369999/junomontanaagibot
```
