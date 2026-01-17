# Детальный анализ Eclipse Attack на сеть Montana

**Модель:** Composer 1  
**Компания:** Cursor  
**Дата:** 07.01.2026 14:15 UTC

---

## Резюме

Обнаружена **критическая уязвимость** к Eclipse атаке в сетевом слое Montana. Основная проблема: отсутствие механизма anchor connections между рестартами узла, что позволяет атакующему изолировать жертву от честной сети после перезапуска.

---

## Что такое Eclipse Attack?

Eclipse атака — это изоляция узла от честной сети путем заполнения всех его соединений вредоносными узлами атакующего. После рестарта жертва подключается только к узлам атакующего и не может получить доступ к честной сети.

---

## Анализ защиты от Eclipse в Montana

### 1. Netgroup Diversity — ЧАСТИЧНО РАБОТАЕТ

**Код:** `connection.rs:264-270`
```rust
pub async fn can_connect(&self, addr: &SocketAddr) -> bool {
    let netgroup = get_netgroup(addr);
    let counts = self.netgroup_counts.lock().await;
    let current = counts.get(&netgroup).copied().unwrap_or(0);
    current < MAX_PEERS_PER_NETGROUP  // MAX_PEERS_PER_NETGROUP = 2
}
```

**Статус:** ✅ Работает для активных соединений  
**Проблема:** ❌ При рестарте `netgroup_counts` пуст, проверка неэффективна

**Анализ:**
- `MAX_PEERS_PER_NETGROUP = 2` — максимум 2 peers из одной /16 подсети
- Для `MAX_OUTBOUND = 8` нужно минимум 4 различных /16 подсети
- При рестарте `netgroup_counts` сбрасывается в пустое состояние
- Первые 2 соединения из одной подсети проходят проверку
- Атакующий может использовать 2 IP из каждой /16 подсети

**Слабое место:**
```rust
// При рестарте:
netgroup_counts = HashMap::new()  // ← ПУСТОЙ
// Первое соединение: current = 0 < 2 ✅ ПРОХОДИТ
// Второе соединение: current = 1 < 2 ✅ ПРОХОДИТ
// Третье соединение: current = 2 < 2 ❌ ОТКЛОНЯЕТСЯ
```

---

### 2. Anchor Connections — ОТСУТСТВУЕТ

**Код:** `protocol.rs:167-204`, `connection.rs:188-229`

**Статус:** ❌ **КРИТИЧЕСКАЯ УЯЗВИМОСТЬ**

**Анализ:**

1. **AddrMan сохраняет только адреса:**
   ```rust
   // protocol.rs:171-179
   let addr_path = config.data_dir.join("addresses.dat");
   let addresses = if addr_path.exists() {
       AddrMan::load(&addr_path).unwrap_or_else(|e| {
           warn!("Failed to load addresses: {}", e);
           AddrMan::new()
       })
   } else {
       AddrMan::new()
   };
   ```
   - Сохраняются адреса из NEW и TRIED таблиц
   - **НЕ сохраняются активные соединения**
   - При рестарте все соединения теряются

2. **ConnectionManager не сохраняет соединения:**
   ```rust
   // connection.rs:188-229
   pub struct ConnectionManager {
       outbound_count: AtomicUsize,
       inbound_count: AtomicUsize,
       netgroup_counts: Mutex<HashMap<u32, usize>>,
       // ← НЕТ МЕХАНИЗМА СОХРАНЕНИЯ СОЕДИНЕНИЙ
   }
   ```
   - Сохраняются только баны (`ban_list`)
   - Активные соединения не сохраняются
   - При рестарте `netgroup_counts` пуст

3. **Protocol не приоритизирует предыдущие соединения:**
   ```rust
   // protocol.rs:494-502
   let net_addr = {
       let mut addrman = addresses.write().await;
       match addrman.select() {
           Some(addr) => addr,  // ← СЛУЧАЙНЫЙ ВЫБОР
           None => continue,
       }
   };
   ```
   - `select()` выбирает случайно из AddrMan
   - Нет приоритизации предыдущих outbound соединений
   - Нет гарантии восстановления соединений после рестарта

**Вектор атаки:**
```
1. Атакующий заполняет AddrMan своими адресами
2. Жертва перезапускается
3. Все соединения теряются
4. select() выбирает случайно из AddrMan
5. Высокая вероятность выбора адресов атакующего
6. Все outbound → к атакующему
```

---

### 3. Bucket Collision Handling — РАБОТАЕТ, НО НЕДОСТАТОЧНО

**Код:** `addrman.rs:154-163`, `201-205`

**Статус:** ✅ Работает, но не защищает от Eclipse

**Анализ:**

1. **NEW table collision handling:**
   ```rust
   // addrman.rs:154-163
   if let Some(existing_idx) = self.new_table[idx] {
       if let Some(existing) = self.addrs.get(&existing_idx)
           && !existing.is_terrible()
       {
           return false; // Keep existing good address
       }
       self.remove_from_new(existing_idx);
   }
   ```
   - Если слот занят хорошим адресом, новый адрес отклоняется
   - Если слот занят плохим адресом, он заменяется
   - **Проблема:** Атакующий может заполнить большинство buckets хорошими адресами

2. **TRIED table collision handling:**
   ```rust
   // addrman.rs:201-205
   if let Some(existing_idx) = self.tried_table[idx] {
       self.move_to_new(existing_idx);  // Move existing back to new
   }
   ```
   - При коллизии существующий адрес перемещается обратно в NEW
   - **Проблема:** Если атакующий заполнил TRIED, честные адреса выталкиваются

3. **Bucket distribution:**
   ```rust
   // addrman.rs:441-450
   fn get_new_bucket(&self, addr: &SocketAddr, source: Option<&SocketAddr>) -> usize {
       let mut hasher = SipHasher24::new_with_key(&self.key[..16].try_into().unwrap());
       hasher.write(&get_netgroup_bytes(addr));
       if let Some(src) = source {
           hasher.write(&get_netgroup_bytes(src));
       }
       (hasher.finish() as usize) % NEW_BUCKET_COUNT  // 1024 buckets
   }
   ```
   - Random key предотвращает предсказание buckets
   - Но атакующий может заполнить большинство buckets через множество адресов
   - NEW table: 1024 buckets × 64 слота = 65,536 адресов
   - Если атакующий заполняет 80% buckets → высокая вероятность выбора его адресов

**Слабое место:**
- Коллизии защищают от замены хороших адресов плохими
- Но не защищают от заполнения большинства buckets хорошими адресами атакующего

---

### 4. Select Logic — СЛУЧАЙНЫЙ ВЫБОР ИЗ ЗАПОЛНЕННОГО ADDRMAN

**Код:** `addrman.rs:223-248`, `511-545`, `547-569`

**Статус:** ⚠️ Работает корректно, но уязвим к Eclipse

**Анализ:**

1. **50/50 выбор между NEW и TRIED:**
   ```rust
   // addrman.rs:233-247
   fn select_inner(&mut self, new_only: bool) -> Option<NetAddress> {
       let mut rng = ChaCha20Rng::from_entropy();
       let use_new = new_only || rng.gen_bool(0.5);  // 50% chance
       
       if use_new && self.new_count > 0 {
           self.select_from_new(&mut rng)
       } else if self.tried_count > 0 {
           self.select_from_tried(&mut rng)
       } else if self.new_count > 0 {
           self.select_from_new(&mut rng)
       } else {
           None
       }
   }
   ```
   - Случайный выбор между NEW и TRIED таблицами
   - **Проблема:** Если обе таблицы заполнены адресами атакующего, выбор будет из них

2. **Случайный выбор из buckets:**
   ```rust
   // addrman.rs:519-544
   for _ in 0..1000 {
       let bucket = rng.gen_range(0..NEW_BUCKET_COUNT);  // Random bucket
       let pos = rng.gen_range(0..BUCKET_SIZE);          // Random position
       let idx = bucket * BUCKET_SIZE + pos;
       
       if let Some(addr_idx) = self.new_table[idx]
           && let Some(info) = self.addrs.get(&addr_idx)
       {
           // Skip if connected, terrible, or too old
           if self.connected.contains(&socket_addr) {
               continue;
           }
           if info.is_terrible() || info.addr.timestamp < horizon {
               continue;
           }
           return Some(info.addr.clone());
       }
   }
   ```
   - Случайный выбор bucket и позиции
   - До 1000 попыток найти валидный адрес
   - **Проблема:** Если большинство buckets заполнены адресами атакующего, высока вероятность выбора его адресов

**Вектор атаки:**
```
1. Атакующий заполняет 80% buckets в NEW table
2. Атакующий заполняет 80% buckets в TRIED table
3. При select():
   - 50% вероятность выбрать из NEW → 80% вероятность выбрать адрес атакующего
   - 50% вероятность выбрать из TRIED → 80% вероятность выбрать адрес атакующего
4. Общая вероятность выбора адреса атакующего: ~80%
```

---

### 5. Feeler Connections — СЛИШКОМ МЕДЛЕННО

**Код:** `feeler.rs:15-122`

**Статус:** ✅ Работает, но недостаточно для защиты

**Анализ:**

1. **Feeler interval:**
   ```rust
   // feeler.rs:15-16
   pub const FEELER_INTERVAL: Duration = Duration::from_secs(120);  // 2 минуты
   pub const MAX_CONCURRENT_FEELERS: usize = 1;  // Только 1 feeler одновременно
   ```
   - Один feeler каждые 2 минуты
   - **Проблема:** Слишком медленно для защиты от Eclipse
   - Для проверки 1000 адресов нужно: 1000 × 2 минуты = 2000 минут = 33 часа

2. **Feeler валидирует только NEW table:**
   ```rust
   // feeler.rs:110-114
   let addr = {
       let mut am = addrman.lock().await;
       am.select_with_option(true).map(|a| a.socket_addr())  // new_only = true
   };
   ```
   - Проверяет только адреса из NEW table
   - Успешные feeler перемещают адреса в TRIED
   - **Проблема:** Не проверяет адреса в TRIED table

**Слабое место:**
- Feeler слишком медленный для защиты от Eclipse
- Не проверяет адреса в TRIED table
- Атакующий может заполнить TRIED через fake connections быстрее, чем feeler проверит их

---

## Детальный вектор Eclipse атаки

### Фаза 1: Заполнение NEW table

**Цель:** Заполнить большинство buckets в NEW table вредоносными адресами

**Метод:**
```rust
// Атакующий отправляет Addr сообщения с множеством адресов
// Каждый адрес попадает в случайный bucket через SipHash
for i in 0..50000 {
    let addr = NetAddress::new(
        IpAddr::V4(Ipv4Addr::new(
            attacker_prefix,
            (i / 256) as u8,
            (i % 256) as u8,
            1
        )),
        19333,
        NODE_FULL
    );
    send_addr_message(victim, vec![addr]);
}

// NEW table: 1024 buckets × 64 слота = 65,536 адресов
// Атакующий заполняет 50,000 адресов → ~76% buckets заполнены
```

**Результат:**
- Большинство buckets в NEW table содержат адреса атакующего
- Честные адреса занимают только ~24% buckets
- При `select_from_new()` высока вероятность выбора адреса атакующего

---

### Фаза 2: Продвижение в TRIED table

**Цель:** Переместить адреса из NEW в TRIED через fake connections

**Метод:**
```rust
// Атакующий устанавливает соединения и завершает handshake
for addr in attacker_addresses_from_new_table {
    let stream = connect(victim, addr);
    
    // Завершаем handshake
    send_version(stream);
    receive_verack(stream);
    
    // mark_good() вызывается автоматически
    // Адрес перемещается из NEW в TRIED
    close_connection(stream);
}

// После множества успешных соединений:
// - Адреса атакующего перемещаются в TRIED
// - Честные адреса остаются в NEW или выталкиваются
```

**Результат:**
- Большинство адресов в TRIED table принадлежат атакующему
- Честные адреса выталкиваются из TRIED при коллизиях
- При `select_from_tried()` высока вероятность выбора адреса атакующего

---

### Фаза 3: Ожидание рестарта

**Цель:** Дождаться рестарта жертвы для активации атаки

**Метод:**
```rust
// Атакующий мониторит жертву
while victim_is_online {
    // Поддерживаем соединения
    // Отправляем валидные сообщения
    // Избегаем подозрительного поведения
    wait_for_restart();
}

// При рестарте:
// 1. Все соединения теряются
// 2. AddrMan загружается из addresses.dat
// 3. netgroup_counts сбрасывается
// 4. connection_loop() начинает выбирать адреса заново
```

**Результат:**
- При рестарте все соединения теряются
- AddrMan загружается с адресами атакующего
- Нет anchor connections для восстановления честных соединений

---

### Фаза 4: Захват outbound соединений

**Цель:** Заставить жертву подключиться только к узлам атакующего

**Метод:**
```rust
// После рестарта жертвы:
// connection_loop() начинает выбирать адреса из AddrMan

for i in 0..MAX_OUTBOUND {  // MAX_OUTBOUND = 8
    let addr = addrman.select();  // Случайный выбор
    
    // Вероятность выбора адреса атакующего: ~80%
    if addr.is_attacker() {
        accept_connection(victim, addr);
        // Жертва подключается к атакующему
    }
}

// Результат:
// - Все 8 outbound соединений → к атакующему
// - Жертва изолирована от честной сети
```

**Результат:**
- Все outbound соединения направлены к атакующему
- Жертва не может получить доступ к честной сети
- Eclipse атака успешна

---

## Эксплуатация Eclipse атаки

### Шаг 1: Подготовка адресов

```rust
// Атакующий готовит множество адресов из разных /16 подсетей
// Для обхода MAX_PEERS_PER_NETGROUP = 2 использует 2 IP из каждой подсети

let mut attacker_addresses = Vec::new();
for subnet in 0..1000 {  // 1000 различных /16 подсетей
    let base = subnet * 256;
    attacker_addresses.push((base, 1));  // Первый IP
    attacker_addresses.push((base, 2));   // Второй IP
}
// Итого: 2000 адресов из 1000 подсетей
```

### Шаг 2: Заполнение AddrMan

```rust
// Отправка Addr сообщений с адресами атакующего
// Используем rate limiting: 1000 burst, 0.1/sec sustained

let mut sent = 0;
for batch in attacker_addresses.chunks(1000) {
    send_addr_message(victim, batch);
    sent += batch.len();
    
    // Ждем refill token bucket (0.1/sec)
    if sent >= 1000 {
        wait_for_refill();
        sent = 0;
    }
}

// Результат: AddrMan заполнен адресами атакующего
```

### Шаг 3: Продвижение в TRIED

```rust
// Установка fake connections для перемещения адресов в TRIED
// Используем MAX_CONNECTIONS_PER_IP = 2 для обхода ограничений

for subnet in 0..1000 {
    let addr1 = (subnet * 256, 1);
    let addr2 = (subnet * 256, 2);
    
    // Первое соединение
    connect_and_handshake(victim, addr1);
    // mark_good() → перемещение в TRIED
    
    // Второе соединение
    connect_and_handshake(victim, addr2);
    // mark_good() → перемещение в TRIED
}

// Результат: Большинство адресов в TRIED принадлежат атакующему
```

### Шаг 4: Ожидание рестарта

```rust
// Атакующий поддерживает соединения и ждет рестарта
while victim_is_online {
    // Отправляем валидные сообщения
    send_ping();
    send_slice();
    send_transaction();
    
    // Избегаем подозрительного поведения
    avoid_ban();
    
    // Мониторим рестарт
    if victim_restarted() {
        break;
    }
}
```

### Шаг 5: Захват после рестарта

```rust
// После рестарта жертвы:
// 1. Все соединения потеряны
// 2. AddrMan загружен с адресами атакующего
// 3. connection_loop() начинает выбирать адреса

// Жертва пытается установить 8 outbound соединений
for i in 0..8 {
    let addr = addrman.select();  // ~80% вероятность выбрать адрес атакующего
    
    if addr.is_attacker() {
        accept_connection(victim, addr);
        // Жертва подключается к атакующему
    }
}

// Результат: Все outbound → к атакующему
// Eclipse атака успешна!
```

---

## Критические слабые места

### 1. Отсутствие Anchor Connections

**Проблема:**
- При рестарте все соединения теряются
- Нет механизма восстановления предыдущих outbound соединений
- Узел начинает выбирать адреса заново из AddrMan

**Влияние:**
- Высокая уязвимость к Eclipse атаке после рестарта
- Атакующий может заполнить AddrMan и захватить все соединения

**Рекомендация:**
- Реализовать anchor connections механизм
- Сохранять последние 8 outbound соединений в файл
- При рестарте приоритизировать эти адреса для переподключения

---

### 2. Netgroup Diversity не защищает при первом выборе

**Проблема:**
- При рестарте `netgroup_counts` пуст
- Первые 2 соединения из одной подсети проходят проверку
- Атакующий может использовать 2 IP из каждой подсети

**Влияние:**
- Атакующий может обойти netgroup diversity при первом выборе
- Достаточно 4 различных /16 подсетей для 8 outbound соединений

**Рекомендация:**
- Требовать минимум 4 различных /16 подсетей для первых outbound соединений
- Не позволять выбирать адреса из одной подсети до достижения разнообразия

---

### 3. Select Logic уязвим к заполнению AddrMan

**Проблема:**
- Случайный выбор из заполненного AddrMan
- Если большинство адресов принадлежат атакующему, высока вероятность выбора его адресов
- Нет приоритизации честных адресов

**Влияние:**
- При заполнении 80% AddrMan адресами атакующего, вероятность выбора его адресов ~80%
- Eclipse атака становится вероятной

**Рекомендация:**
- Добавить приоритизацию адресов по источнику (DNS seeds, hardcoded)
- Ограничить количество адресов от одного источника
- Использовать разнообразие источников при выборе

---

### 4. Feeler Connections слишком медленные

**Проблема:**
- Один feeler каждые 2 минуты
- Для проверки 1000 адресов нужно 33 часа
- Не проверяет адреса в TRIED table

**Влияние:**
- Атакующий может заполнить AddrMan быстрее, чем feeler проверит адреса
- Недостаточно для защиты от Eclipse атаки

**Рекомендация:**
- Увеличить количество concurrent feelers
- Уменьшить feeler interval
- Добавить проверку адресов в TRIED table

---

## Защита от Eclipse атаки

### Текущие механизмы защиты:

1. ✅ **Netgroup diversity** — работает для активных соединений
2. ✅ **Bucket collision handling** — защищает от замены хороших адресов
3. ✅ **Feeler connections** — валидирует адреса, но слишком медленно
4. ✅ **Per-IP limits** — ограничивает количество соединений с одного IP
5. ✅ **Rate limiting** — ограничивает скорость заполнения AddrMan

### Отсутствующие механизмы защиты:

1. ❌ **Anchor connections** — критическая уязвимость
2. ❌ **Приоритизация источников** — нет приоритизации DNS seeds/hardcoded
3. ❌ **Разнообразие источников** — нет требования разнообразия источников
4. ❌ **Быстрая валидация** — feeler слишком медленный

---

## Выводы

### Критическая уязвимость: Eclipse Attack возможна

**Основные причины:**
1. Отсутствие anchor connections между рестартами
2. Netgroup diversity не защищает при первом выборе после рестарта
3. Select logic уязвим к заполнению AddrMan адресами атакующего
4. Feeler connections слишком медленные для защиты

**Вероятность успешной атаки:**
- При заполнении 80% AddrMan адресами атакующего: ~80%
- При заполнении 90% AddrMan адресами атакующего: ~90%

**Сложность атаки:**
- Средняя: требует контроля множества IP адресов и подсетей
- Время подготовки: несколько дней для заполнения AddrMan
- Триггер: рестарт жертвы (может быть спровоцирован)

**Рекомендации:**
1. **Немедленно:** Реализовать anchor connections механизм
2. **Высокий приоритет:** Улучшить netgroup diversity при первом выборе
3. **Средний приоритет:** Добавить приоритизацию источников адресов
4. **Низкий приоритет:** Ускорить feeler connections

---

## Дополнительные векторы атаки

### Вектор 1: BGP Hijacking

**Описание:**
- Атакующий использует BGP hijacking для контроля множества /16 подсетей
- Заполняет AddrMan адресами из контролируемых подсетей
- После рестарта жертва подключается к контролируемым подсетям

**Сложность:** Высокая (требует BGP access)  
**Вероятность:** Средняя (при наличии BGP access)

### Вектор 2: Sybil Attack + Eclipse

**Описание:**
- Атакующий создает множество Sybil узлов
- Заполняет AddrMan адресами Sybil узлов
- После рестарта жертва подключается только к Sybil узлам

**Сложность:** Средняя (требует множество IP адресов)  
**Вероятность:** Высокая (при наличии множества IP)

### Вектор 3: DNS Seed Poisoning

**Описание:**
- Атакующий компрометирует DNS seeds
- DNS seeds возвращают адреса атакующего
- Жертва загружает адреса атакующего при bootstrap

**Сложность:** Высокая (требует компрометации DNS)  
**Вероятность:** Низкая (DNS seeds защищены)

---

## Заключение

Сеть Montana **уязвима к Eclipse атаке** из-за отсутствия механизма anchor connections и недостаточной защиты при первом выборе адресов после рестарта. Рекомендуется немедленно реализовать anchor connections и улучшить механизмы защиты от Eclipse атаки.

