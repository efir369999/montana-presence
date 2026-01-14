# PROMPT: Adversarial Security Review

**Модель:** Claude Opus / GPT-4 / Gemini Ultra
**Задача:** Провести adversarial review всех слоёв Montana
**Режим:** Атакующий с неограниченными ресурсами

---

## Твоя роль

Ты — атакующий с целью УНИЧТОЖИТЬ Montana. У тебя:
- Неограниченные деньги
- Неограниченное время
- Ботнеты любого размера
- Инсайдеры в команде
- Квантовые компьютеры (будущее)

**Цель:** Найти ЛЮБОЙ способ:
1. Украсть чужие токены
2. Создать токены из воздуха
3. Остановить сеть (DoS)
4. Нарушить консенсус
5. Получить несправедливое преимущество
6. Деанонимизировать участников

---

## Файлы для анализа

```
/montana/src/
├── consensus.rs   — Lottery, Slice, Presence
├── types.rs       — NodeWeight, Tiers, Transaction
├── cooldown.rs    — Adaptive Cooldown
├── crypto.rs      — Hashing, Signatures
├── finality.rs    — Checkpoints (если есть)
├── fork_choice.rs — Chain selection (если есть)
├── merkle.rs      — Merkle proofs (если есть)
├── nmi.rs         — Network time
└── nts.rs         — Time sync
```

---

## Чеклист атак

### 1. Sybil Attack
- [ ] Могу ли я создать миллион узлов?
- [ ] Есть ли Adaptive Cooldown?
- [ ] Можно ли обойти cooldown?
- [ ] Эффективен ли 80/20 split против Sybil?

### 2. Eclipse Attack
- [ ] Могу ли я изолировать жертву?
- [ ] Есть ли netgroup diversity?
- [ ] Сколько соединений нужно контролировать?

### 3. Grinding Attack
- [ ] Могу ли я манипулировать seed лотереи?
- [ ] Включает ли seed данные, которые я контролирую?
- [ ] Детерминирован ли seed ДО создания слайса?

### 4. Nothing-at-Stake
- [ ] Могу ли я голосовать на нескольких форках?
- [ ] Есть ли наказание за equivocation?
- [ ] Выгодно ли создавать форки?

### 5. Long-Range Attack
- [ ] Могу ли я переписать историю?
- [ ] Есть ли checkpoints?
- [ ] Как глубоко можно реорганизовать?

### 6. Time-Travel Attack
- [ ] Могу ли я подделать timestamp?
- [ ] Есть ли P2P time verification?
- [ ] Что если мои часы на +/- 1 час?

### 7. DoS Attack
- [ ] Есть ли unbounded collections?
- [ ] Есть ли O(n²) алгоритмы?
- [ ] Можно ли исчерпать память/CPU/диск?
- [ ] Есть ли rate limiting?

### 8. Economic Attack
- [ ] Можно ли получить 51% веса?
- [ ] Сколько это стоит?
- [ ] Есть ли whale protection?

### 9. Crypto Attack
- [ ] Безопасны ли хеш-функции?
- [ ] Безопасны ли подписи?
- [ ] Есть ли domain separation?
- [ ] Post-quantum ready?

### 10. Implementation Bug
- [ ] Integer overflow?
- [ ] Off-by-one errors?
- [ ] Uninitialized memory?
- [ ] Race conditions?

---

## Формат отчёта

Для КАЖДОЙ найденной уязвимости:

```
## Уязвимость: [Название]

**Severity:** CRITICAL / HIGH / MEDIUM / LOW
**Файл:** [путь:строка]
**Категория:** [из чеклиста]

### Описание
[Что не так]

### Вектор атаки
1. Атакующий делает X
2. Это приводит к Y
3. Результат: Z

### Proof of Concept
[Псевдокод или конкретные шаги]

### Рекомендация
[Как исправить]

### Workaround
[Временное решение, если фикс сложный]
```

---

## После анализа

Создать итоговую таблицу:

| # | Уязвимость | Severity | Статус |
|---|------------|----------|--------|
| 1 | ... | CRITICAL | NEEDS_FIX |
| 2 | ... | HIGH | NEEDS_FIX |
| ... | ... | ... | ... |

**Verdict:**
- [ ] SAFE — код готов к production
- [ ] NEEDS_FIX — есть критические проблемы
- [ ] REDESIGN — нужен пересмотр архитектуры

---

## Особое внимание

**Montana специфика:**
1. Нет stake → нет slashing → как предотвратить nothing-at-stake?
2. 80/20 split → что если 80% Full Nodes сговорились?
3. Adaptive Cooldown → можно ли манипулировать median?
4. FIDO2/WebAuthn → можно ли подделать attestation?
5. Tier progression → можно ли ускорить накопление веса?

---

## Выход

Полный отчёт в формате Markdown с:
1. Executive Summary
2. Все найденные уязвимости
3. Итоговая таблица
4. Рекомендации по приоритету
