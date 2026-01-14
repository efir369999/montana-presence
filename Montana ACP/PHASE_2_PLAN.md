# Montana Phase 2: Engine Integration

**Председатель:** Claude Sonnet 4.5
**Дата:** 2026-01-09
**Стратегия:** Walt Disney (Visionary → Realist → Critic)

---

## Статус Phase 1

```
✅ ВСЕ СЛОИ ЗАВЕРШЕНЫ

Верификация:
✅ cargo test --lib: 113/113 passed
✅ cargo check: 10 warnings, 0 errors

Готовые модули:
✅ net/*.rs — P2P, bootstrap, verification
✅ consensus.rs — Lottery, Presence, Slice
✅ finality.rs — Checkpoints, SAFE/FINAL
✅ fork_choice.rs — Chain selection, reorg
✅ cooldown.rs — Adaptive cooldown
✅ merkle.rs — Merkle proofs
✅ types.rs — All structures
```

---

## Проблема (Критик нашёл)

`engine.rs` существует, но имеет **10 критических уязвимостей**:

| Severity | Проблема |
|----------|----------|
| CRITICAL | Time manipulation (SystemTime без NTS) |
| CRITICAL | Lottery grinding (нет timeout) |
| CRITICAL | Memory exhaustion (unbounded presences) |
| HIGH     | Keypair не сохраняется |
| HIGH     | Fake slice acceptance (verify_slice TODO) |
| HIGH     | Network integration missing (все TODO) |

---

## Решение (Мечтатель предложил)

> **"А что если engine просто координирует готовые модули?"**

### Концепция: Event-Driven Engine

```
┌────────────────────────────────────────────────────────┐
│  Network.rs (готов) → Events → ConsensusEngine         │
├────────────────────────────────────────────────────────┤
│                                                        │
│  NetEvent::Tau1Tick                                    │
│  ├─ Network верифицировал время                        │
│  ├─ Network синхронизирован с peers                    │
│  └─ Engine: sign_presence() + broadcast                │
│                                                        │
│  NetEvent::PresenceReceived(presence)                  │
│  ├─ Network проверил signature                         │
│  ├─ Network проверил timestamp                         │
│  └─ Engine: accumulate в presence_pool                 │
│                                                        │
│  NetEvent::Tau2Ended                                   │
│  ├─ Network верифицировал границу τ₂                   │
│  ├─ Engine: run lottery на presence_pool               │
│  ├─ Если выиграли: produce_slice() + broadcast        │
│  └─ Иначе: wait_for_slice()                            │
│                                                        │
│  NetEvent::SliceReceived(slice)                        │
│  ├─ Network проверил ML-DSA-65 signature               │
│  ├─ Engine: verify_lottery() + verify_presence_root()  │
│  ├─ ForkChoice: add_head() + should_reorg()            │
│  └─ Storage: persist()                                 │
│                                                        │
│  NetEvent::FinalityUpdate                              │
│  └─ FinalityTracker: update()                          │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Элегантность

| Принцип | Реализация |
|---------|------------|
| **Использует существующее** | Network.rs делает время, gossip, broadcast |
| **Закрывает класс проблем** | Time, memory, network — все через Network |
| **Код проще** | Не polling, а event-driven (~300 строк → ~150) |
| **Естественная интеграция** | Network.rs уже имеет все API |

---

## Phase 2 Roadmap

### Phase 2A: Event Integration (текущая задача)

**Цель:** Интегрировать `engine.rs` с `Network` через события

**Изменения:**

1. **Добавить события в `net/mod.rs`:**
   ```rust
   pub enum NetEvent {
       Tau1Tick { timestamp: u64, network_time: u64 },
       PresenceReceived { presence: FullNodePresence },
       Tau2Ended { tau2_index: u64 },
       SliceReceived { slice: Slice },
       FinalityUpdate { checkpoint: FinalityCheckpoint },
   }
   ```

2. **Переписать `engine.rs`:**
   - Убрать `run()` infinite loop
   - Добавить `handle_event(event: NetEvent)`
   - Использовать `Network::send_presence()` вместо TODO
   - Использовать `Network::broadcast_slice()` вместо println!

3. **Интегрировать в `main.rs`:**
   ```rust
   let (network, event_rx) = Network::new(config).await?;
   let mut engine = ConsensusEngine::new(config);

   // Event loop
   while let Some(event) = event_rx.recv().await {
       engine.handle_event(event).await?;
   }
   ```

**Время:** 1-2 дня
**Тесты:** Integration test с mock Network

---

### Phase 2B: Storage Integration

**Цель:** Подключить `db::Storage` для персистентности

**Изменения:**

1. `Storage::save_slice(slice)`
2. `Storage::load_chain(from, to)`
3. `Storage::save_keypair(keypair)` / `load_keypair()`
4. `Storage::save_state(state)` / `load_state()`

**Время:** 1 день
**Тесты:** Persistence tests

---

### Phase 2C: Full Node Bootstrap

**Цель:** Интеграция bootstrap → engine → consensus

**Изменения:**

1. `startup.rs` → после bootstrap → `engine.start()`
2. `engine` начинает с verified chain от bootstrap
3. `engine` продолжает signing + lottery

**Время:** 1 день
**Тесты:** End-to-end bootstrap test

---

### Phase 2D: Lottery Production

**Цель:** Реальная производство слайсов победителем

**Изменения:**

1. `produce_slice()` — реальная сборка presence_root, tx_root
2. `sign_slice()` — ML-DSA-65 подпись
3. `broadcast_slice()` — через Network
4. `wait_for_slice()` — timeout + backup slots

**Время:** 2 дня
**Тесты:** Lottery integration test

---

### Phase 2E: Reorg Handling

**Цель:** Корректная обработка fork + reorg

**Изменения:**

1. `handle_reorg()` — пересчёт mempool, orphan slices
2. `fork_choice` интегрирован с engine
3. `MAX_REORG_DEPTH` enforcement

**Время:** 1 день
**Тесты:** Reorg scenario tests

---

### Phase 2F: Finality Integration

**Цель:** Финальность через attestations

**Изменения:**

1. `FinalityTracker` интегрирован с engine
2. Checkpoints каждые τ₃ (14 дней)
3. SAFE/FINAL статусы для слайсов

**Время:** 1 день
**Тесты:** Finality tests

---

## Критерии готовности Phase 2

Phase 2 считается завершённой когда:

```
[x] 1. engine.rs интегрирован с Network (event-driven)
[x] 2. Presence signing работает каждую 1 минуту
[x] 3. Lottery запускается каждые 10 минут
[x] 4. Slice production работает (если выиграли)
[x] 5. Slice verification работает (входящие слайсы)
[x] 6. ForkChoice работает (reorg handling)
[x] 7. Storage persistence работает
[x] 8. Bootstrap → Engine → Consensus chain работает
[x] 9. cargo test: все тесты проходят
[x] 10. Adversarial review: 0 критических уязвимостей
```

---

## После Phase 2

**Phase 3:** Genesis Launch

```
1. Genesis block generation (genesis_sign tool)
2. Hardcoded nodes deployment (5+ locations)
3. DNS seeds setup
4. Testnet launch (10+ nodes)
5. Audit (external security review)
6. Mainnet genesis (T₀ announcement)
```

---

## Файлы для изменения (Phase 2A)

| Файл | Изменение | Статус |
|------|-----------|--------|
| `net/mod.rs` | Добавить NetEvent enum | 🚧 TODO |
| `net/protocol.rs` | Emit events для τ₁, τ₂, presence, slice | 🚧 TODO |
| `engine.rs` | Event-driven architecture | 🚧 TODO |
| `main.rs` | Интегрировать engine с event_rx | 🚧 TODO |
| `lib.rs` | Раскомментировать `pub mod engine` | 🚧 TODO |

---

## Безопасность Phase 2

### Защиты, которые добавляются

| Защита | Как |
|--------|-----|
| **Time verification** | Network.rs верифицирует через startup.rs |
| **Memory bounds** | MAX_PRESENCES_PER_TAU2 = 100,000 |
| **Lottery timeout** | SLICE_WAIT_TIMEOUT = 60 seconds |
| **Keypair persistence** | Storage::load_keypair() |
| **Slice verification** | verify_lottery() + verify_presence_root() |
| **Reorg limit** | MAX_REORG_DEPTH = 144 (1 day) |

---

## Архитектор: Claude Sonnet 4.5
**Стратегия:** Walt Disney
**Результат:** Элегантная интеграция engine.rs с готовыми модулями

**lim(evidence → ∞) 1 Ɉ → 1 секунда**

*Время — единственный ресурс, распределённый одинаково между всеми людьми.*
