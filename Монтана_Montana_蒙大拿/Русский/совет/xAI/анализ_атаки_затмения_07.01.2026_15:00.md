# Eclipse Attack Analysis: Montana Network

**Модель:** Grok 3
**Компания:** xAI
**Дата:** 07.01.2026 15:00 UTC

## Executive Summary

После тщательного анализа кода сети Montana я обнаружил **критическую уязвимость Eclipse Attack**, которая позволяет атакующему полностью изолировать жертву от честной сети. Атака требует контроля над 51+ пирами из 25+ разных /16 подсетей и использует комбинацию нескольких уязвимостей в bootstrap verification, address management и connection limits.

## Attack Vector Analysis

### 1. Bootstrap Verification Bypass (CRITICAL)

**Location:** `startup.rs:179`
**Vulnerability:** Функция `query_hardcoded_tips()` возвращает пустой `Vec::new()`

**Code Evidence:**
```rust
// startup.rs:164-180
async fn query_hardcoded_tips(&self, addrs: &[SocketAddr]) -> Vec<PeerChainInfo> {
    // This is a simplified implementation
    // Real implementation would:
    // 1. Connect to each hardcoded node
    // 2. Complete handshake
    // 3. Get their best slice height
    // 4. Disconnect

    // For now, return empty - actual network queries would be done
    // by the Network module when it starts
    info!("Querying {} hardcoded nodes for chain tips", addrs.len());

    // Placeholder: in production, this would make actual network requests
    // The Network module handles this during start()
    Vec::new() // ← CRITICAL: Always returns empty vector
}
```

**Impact:** Full bootstrap verification полностью не работает. Вместо проверки 100 пиров из 25+ подсетей, код получает 0 пиров, что делает невозможной защиту от Eclipse Attack.

### 2. Address Manager Bucket Collision (HIGH)

**Location:** `addrman.rs:210-221`
**Vulnerability:** При коллизии в TRIED table атакующий может вытеснить честные адреса обратно в NEW table

**Code Evidence:**
```rust
// addrman.rs:210-221
pub fn mark_good(&mut self, addr: &SocketAddr) {
    // ... existing code ...
    // Add to tried
    let bucket = self.get_tried_bucket(addr);
    let pos = self.get_bucket_position(addr, bucket, false);
    let idx = bucket * BUCKET_SIZE + pos;

    // Handle collision
    if let Some(existing_idx) = self.tried_table[idx] {
        // Move existing back to new ← VULNERABILITY
        self.move_to_new(existing_idx);
    }

    self.tried_table[idx] = Some(addr_idx);
    self.tried_count += 1;
}
```

**Attack Scenario:**
1. Атакующий заполняет NEW table вредоносными адресами
2. Создает fake соединения для продвижения в TRIED table
3. Использует bucket collisions для вытеснения честных адресов
4. После рестарта жертвы все адреса в TRIED table - атакующие

### 3. Insufficient Netgroup Diversity Protection (HIGH)

**Location:** `types.rs:209`, `connection.rs:272-277`
**Vulnerability:** `MAX_PEERS_PER_NETGROUP = 2` недостаточно для защиты от распределенного Eclipse Attack

**Code Evidence:**
```rust
// types.rs:202-209
/// Maximum peers from the same /16 subnet.
/// Prevents single datacenter from dominating connections.
///
/// Security analysis:
/// - With MAX_PEERS_PER_NETGROUP=2 and MAX_OUTBOUND=8
/// - Attacker needs control of 4+ different /16 subnets
pub const MAX_PEERS_PER_NETGROUP: usize = 2;
```

**Attack Enhancement:** Атакующий с контролем над 4+ подсетями может занять все 8 outbound слотов, что достаточно для Eclipse Attack.

### 4. Inbound Slot Exhaustion (MEDIUM)

**Location:** `eviction.rs:75-139`
**Vulnerability:** Eviction защищает только 28 inbound слотов из 117 доступных

**Code Evidence:**
```rust
// eviction.rs:70-75
const PROTECTED_BY_NETGROUP: usize = 4;
const PROTECTED_BY_PING: usize = 8;
const PROTECTED_BY_TX: usize = 4;
const PROTECTED_BY_SLICE: usize = 4;
const PROTECTED_BY_LONGEVITY: usize = 8;
// Total: 4+8+4+4+8 = 28 protected slots
```

**Attack Vector:** Атакующий может заполнить все 117 inbound слотов (MAX_INBOUND), из которых только 28 будут защищены eviction.

## Complete Eclipse Attack Scenario

### Prerequisites
- Контроль над 51+ пирами из 25+ разных /16 подсетей
- Возможность создавать большое количество соединений

### Attack Steps

#### Phase 1: Address Table Poisoning
1. **Заполнить NEW table вредоносными адресами:**
   - Использовать `add()` для добавления контролируемых адресов
   - NEW table имеет 1024 buckets × 64 slots = 65,536 позиций

2. **Продвинуть адреса в TRIED table:**
   - Создать fake соединения к жертве
   - Использовать `mark_good()` для перемещения в TRIED table
   - Использовать bucket collisions для вытеснения существующих адресов

#### Phase 2: Connection Slot Exhaustion
3. **Заполнить inbound слоты:**
   - MAX_INBOUND = 117 слотов
   - Eviction защищает только 28 слотов
   - Атакующий может занять 89+ слотов

4. **Контролировать outbound соединения:**
   - MAX_OUTBOUND = 8 слотов
   - MAX_PEERS_PER_NETGROUP = 2
   - Атакующий занимает все 8 слотов из разных подсетей

#### Phase 3: Bootstrap Bypass
5. **Обойти bootstrap verification:**
   - `query_hardcoded_tips()` возвращает пустой вектор
   - Нет проверки 100 пиров из 25+ подсетей
   - Нет верификации hardcoded nodes

#### Phase 4: Restart Exploitation
6. **Ждать рестарта жертвы:**
   - После рестарта `startup.rs` не выполняет реальную верификацию
   - Все outbound соединения идут к атакующим пирам
   - Жертва полностью изолирована от честной сети

## Attack Cost Analysis

### Resource Requirements
- **Минимальный контроль:** 51 пиров из 25+ /16 подсетей
- **Оптимальный контроль:** 8 пиров из 8 разных подсетей (для outbound слотов)
- **Дополнительно:** Способность создавать множество соединений для заполнения inbound слотов

### Economic Feasibility
- **Низкая стоимость:** Контроль над 25+ подсетями требует значительных ресурсов, но возможен для state actors
- **Высокая эффективность:** Полная изоляция жертвы после успешной атаки

## Mitigation Recommendations

### Immediate Fixes (CRITICAL)

1. **Исправить bootstrap verification:**
   ```rust
   // startup.rs - IMPLEMENT query_hardcoded_tips
   async fn query_hardcoded_tips(&self, addrs: &[SocketAddr]) -> Vec<PeerChainInfo> {
       // Actually connect to hardcoded nodes and get chain info
   }
   ```

2. **Увеличить netgroup diversity:**
   ```rust
   // types.rs
   pub const MAX_PEERS_PER_NETGROUP: usize = 1; // Bitcoin uses 1
   ```

3. **Улучшить eviction protection:**
   ```rust
   // eviction.rs - Increase protected slots
   const PROTECTED_BY_NETGROUP: usize = 8; // Increase from 4
   ```

### Long-term Improvements

4. **Реализовать age-based peer selection при bootstrap**
5. **Добавить runtime diversity monitoring**
6. **Внедрить anchor connections (как в Bitcoin Core)**

## Risk Assessment

- **Вероятность:** HIGH (критические уязвимости в bootstrap и address management)
- **Влияние:** CRITICAL (полная изоляция от сети)
- **Сложность эксплуатации:** MEDIUM (требует контроля над множественными подсетями)
- **Обнаруживаемость:** LOW (атака проявляется только после рестарта)

## Conclusion

Сеть Montana имеет серьезные уязвимости Eclipse Attack, особенно в bootstrap verification и address management. Основная проблема - нереализованная функция `query_hardcoded_tips()` делает всю защиту от Eclipse Attack неработоспособной. Атакующий с контролем над 51+ пирами из 25+ подсетей может полностью изолировать любую жертву от честной сети.

Рекомендуется немедленное исправление bootstrap verification и усиление diversity protection перед запуском сети в производство.
