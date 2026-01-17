# Решение: Dilithium Storm

**Дата:** 08.01.2026
**Автор:** Claude Opus 4.5 (Anthropic)
**Источник:** Google/Gemini 3 Pro audit

---

## 1. Подтверждённые проблемы

### [HIGH] Dilithium Storm — CPU Exhaustion

**Файл:** `protocol.rs:1175-1183`

```rust
Message::AuthChallenge(challenge) => {
    if let Some(ref secret_key) = config.hardcoded_secret_key {
        // ПРОБЛЕМА: Синхронный вызов блокирует async runtime
        let sig = match crate::crypto::sign_mldsa65(secret_key, &challenge) {
            Some(s) => s,
            None => { ... }
        };
```

**Проблемы:**
1. `sign_mldsa65` — синхронная CPU-интенсивная операция (~1-5ms)
2. Нет rate limit для AuthChallenge в PeerRateLimits
3. AuthChallenge разрешён pre_handshake (до Version/Verack)

### [MEDIUM] Несовместимость verification.rs и protocol.rs

**Файлы:** `verification.rs:472`, `protocol.rs:690-715`

- verification.rs использует **raw TCP** без шифрования
- protocol.rs требует **Noise XX handshake** для всех соединений
- Эти компоненты **несовместимы** в текущем виде

---

## 2. Сравнение с Bitcoin Core

**Bitcoin Core net_processing.cpp:**

```cpp
// Строка 3849-3852: ВСЕ сообщения кроме VERSION/VERACK отклоняются до handshake
if (!pfrom.fSuccessfullyConnected) {
    LogDebug(BCLog::NET, "Unsupported message \"%s\" prior to verack from peer=%d\n", ...);
    return;
}

// Строка 379-388: Token bucket для Addr rate limiting
double m_addr_token_bucket;
if (peer->m_addr_token_bucket < 1.0) {
    if (rate_limited) {
        ++num_rate_limit;
        continue;
    }
}
```

**Ключевые отличия:**
| Bitcoin | Montana | Проблема |
|---------|---------|----------|
| Только VERSION/VERACK до handshake | AuthChallenge разрешён | CPU exhaustion |
| Token bucket для Addr | Нет rate limit для AuthChallenge | Нет защиты |
| Синхронная обработка | Синхронная обработка | Блокирует runtime |

---

## 3. Идеальное решение

### Изменение 1: Rate limit для AuthChallenge

**Файл:** `rate_limit.rs`

```rust
// Добавить в PeerRateLimits:
pub struct PeerRateLimits {
    pub addr: AddrRateLimiter,
    pub inv: InvRateLimiter,
    pub getdata: GetDataRateLimiter,
    pub headers: HeadersRateLimiter,
    pub getslices: GetSlicesRateLimiter,
    pub slice: SliceRateLimiter,
    pub auth_challenge: TokenBucket,  // НОВОЕ
}

impl PeerRateLimits {
    pub fn new() -> Self {
        Self {
            // ...existing...
            auth_challenge: TokenBucket::new(
                3.0,   // burst: 3 challenges allowed
                0.05,  // recovery: 1 challenge per 20 seconds
            ),
        }
    }
}
```

### Изменение 2: spawn_blocking для sign_mldsa65

**Файл:** `protocol.rs:1175-1205`

```rust
Message::AuthChallenge(challenge) => {
    // Rate limit check ПЕРВЫМ
    if !peer.rate_limits.auth_challenge.try_consume() {
        debug!("Rate limited AuthChallenge from {}", peer.addr);
        return Ok(false);
    }

    if let Some(ref secret_key) = config.hardcoded_secret_key {
        // Клонируем для move в spawn_blocking
        let sk = secret_key.clone();
        let ch = challenge.clone();

        // КРИТИЧНО: Выносим CPU-интенсивную операцию из async runtime
        let sig = tokio::task::spawn_blocking(move || {
            crate::crypto::sign_mldsa65(&sk, &ch)
        })
        .await
        .ok()
        .flatten();

        let sig = match sig {
            Some(s) => s,
            None => {
                warn!("Failed to sign AuthChallenge");
                return Ok(false);
            }
        };

        // ... rest of response ...
    }
}
```

### Изменение 3: Требовать Version/Verack до AuthChallenge (опционально)

**Файл:** `message.rs:89-98`

```rust
pub fn allowed_pre_handshake(&self) -> bool {
    matches!(
        self,
        Message::Version(_)
            | Message::Verack
            | Message::Reject(_)
            // УБРАТЬ: | Message::AuthChallenge(_)
            // УБРАТЬ: | Message::AuthResponse { .. }
    )
}
```

**ВНИМАНИЕ:** Это изменение требует обновления verification.rs для отправки Version до AuthChallenge.

### Изменение 4: Исправить verification.rs (обязательно)

**Файл:** `verification.rs`

Добавить Noise handshake:

```rust
async fn query_single_node(
    addr: SocketAddr,
    listen_port: u16,
    is_hardcoded: bool,
    testnet: bool,
    keypair: &StaticKeypair,  // НОВЫЙ параметр
) -> Result<(PeerChainInfo, Vec<SocketAddr>), VerificationError> {
    let stream = timeout(
        Duration::from_secs(CONNECT_TIMEOUT_SECS),
        TcpStream::connect(addr),
    )
    .await??;

    // НОВОЕ: Noise handshake
    let encrypted = timeout(
        Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
        EncryptedStream::connect(stream, keypair),
    )
    .await
    .map_err(|_| VerificationError::Timeout("noise".into()))?
    .map_err(|e| VerificationError::Handshake(e.to_string()))?;

    let (mut reader, mut writer) = encrypted.split();

    // Теперь используем encrypted reader/writer
    // ... rest of function ...
}
```

---

## 4. Порядок исправлений

| # | Изменение | Риск | Приоритет |
|---|-----------|------|-----------|
| 1 | Rate limit для AuthChallenge | Низкий | ВЫСОКИЙ |
| 2 | spawn_blocking для sign_mldsa65 | Низкий | ВЫСОКИЙ |
| 3 | Noise в verification.rs | Средний | ВЫСОКИЙ |
| 4 | Убрать AuthChallenge из pre_handshake | Высокий | СРЕДНИЙ |

**Рекомендация:** Применить #1, #2, #3 немедленно. #4 — после тестирования.

---

## 5. Почему это работает

### Defense in Depth:

1. **Rate limit** — ограничивает количество AuthChallenge до 3 burst + 0.05/sec
   - Атакующий может вызвать max 3 подписи, затем throttling
   - При 117 inbound connections: 117 × 3 = 351 подписей (одноразово)
   - После burst: 117 × 0.05 = 5.85 подписей/sec (приемлемо)

2. **spawn_blocking** — не блокирует async runtime
   - tokio scheduler распределяет CPU между signing и networking
   - Сервер продолжает отвечать на другие запросы

3. **Noise handshake** — увеличивает стоимость атаки
   - Атакующий должен завершить ML-KEM-768 + X25519 handshake
   - Это ~1ms CPU с обеих сторон
   - Асимметрия уменьшается

4. **Post-handshake AuthChallenge** (опционально) — требует Version/Verack
   - Соответствует Bitcoin Core модели
   - Дополнительная валидация перед CPU-интенсивной операцией

---

## 6. Тестирование

### Unit test для rate limit:

```rust
#[tokio::test]
async fn test_auth_challenge_rate_limit() {
    let mut peer = Peer::new(addr, true, tx);

    // Первые 3 должны пройти (burst)
    assert!(peer.rate_limits.auth_challenge.try_consume());
    assert!(peer.rate_limits.auth_challenge.try_consume());
    assert!(peer.rate_limits.auth_challenge.try_consume());

    // 4-й должен быть отклонён
    assert!(!peer.rate_limits.auth_challenge.try_consume());

    // После 20 секунд — 1 разрешён
    tokio::time::sleep(Duration::from_secs(20)).await;
    assert!(peer.rate_limits.auth_challenge.try_consume());
}
```

### Integration test для spawn_blocking:

```rust
#[tokio::test]
async fn test_concurrent_auth_challenges() {
    // Запустить 100 параллельных AuthChallenge
    // Проверить что сервер остаётся responsive (ping/pong работает)
}
```

---

## 7. Финальный вердикт

| Проблема | Статус | Решение |
|----------|--------|---------|
| Dilithium Storm (CPU DoS) | CONFIRMED | Rate limit + spawn_blocking |
| verification.rs несовместимость | CONFIRMED | Добавить Noise |
| AuthChallenge pre_handshake | DESIGN ISSUE | Опционально убрать |

**Действие:** Требуется исправление до mainnet.
