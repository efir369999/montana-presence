# Верификация: Dilithium Storm (Google/Gemini 3 Pro)

**Верификатор:** Claude Opus 4.5 (Anthropic)
**Дата:** 08.01.2026 UTC
**Исходный отчёт:** `Council/Google/dilithium_storm_08.01.2026_12:00.md`

---

## Заявленная уязвимость

**Название:** Dilithium Storm (CPU Exhaustion on Bootstrap Nodes)
**Severity (Gemini):** CRITICAL → HIGH
**Файл:** `protocol.rs:1175`

**Суть:** Атакующий отправляет поток AuthChallenge сообщений к hardcoded node. Каждое сообщение триггерит синхронный вызов `sign_mldsa65`, блокируя async runtime и вызывая CPU exhaustion.

---

## Верификация

### Шаг 1: Код существует?

**Файл:** `protocol.rs:1175-1205`

```rust
Message::AuthChallenge(challenge) => {
    if let Some(ref secret_key) = config.hardcoded_secret_key {
        let sig = match crate::crypto::sign_mldsa65(secret_key, &challenge) {
            Some(s) => s,
            None => {
                warn!("Failed to sign AuthChallenge (invalid secret key?)");
                return Ok(false);
            }
        };
        // ... send AuthResponse
    }
}
```

**Результат:** ✓ КОД СУЩЕСТВУЕТ

---

### Шаг 2: sign_mldsa65 синхронный?

**Файл:** `crypto.rs:141-145`

```rust
pub fn sign_mldsa65(secret_key: &[u8], message: &[u8]) -> Option<MlDsa65Signature> {
    let sk = dilithium::SecretKey::from_bytes(secret_key).ok()?;
    let sig = dilithium::detached_sign(message, &sk);
    Some(sig.as_bytes().to_vec())
}
```

- Нет `async`
- Нет `spawn_blocking`
- `dilithium::detached_sign` — CPU-интенсивная операция

**Результат:** ✓ СИНХРОННЫЙ, БЛОКИРУЕТ RUNTIME

---

### Шаг 3: Rate limit для AuthChallenge?

**Файл:** `rate_limit.rs:206-226`

```rust
pub struct PeerRateLimits {
    pub addr: AddrRateLimiter,
    pub inv: InvRateLimiter,
    pub getdata: GetDataRateLimiter,
    pub headers: HeadersRateLimiter,
    pub getslices: GetSlicesRateLimiter,
    pub slice: SliceRateLimiter,
    // НЕТ auth_challenge!
}
```

**Результат:** ✗ RATE LIMIT ОТСУТСТВУЕТ

---

### Шаг 4: AuthChallenge pre_handshake?

**Файл:** `message.rs:89-98`

```rust
pub fn allowed_pre_handshake(&self) -> bool {
    matches!(
        self,
        Message::Version(_)
            | Message::Verack
            | Message::Reject(_)
            | Message::AuthChallenge(_)  // ← РАЗРЕШЕНО
            | Message::AuthResponse { .. }
    )
}
```

**Результат:** ✓ РАЗРЕШЕНО ДО HANDSHAKE

---

### Шаг 5: Защиты выше по стеку?

**Noise handshake обязателен** — protocol.rs:690-715:

```rust
let encrypted_result = if inbound {
    tokio::time::timeout(noise_timeout, EncryptedStream::accept(stream, &keypair)).await
} else {
    tokio::time::timeout(noise_timeout, EncryptedStream::connect(stream, &keypair)).await
};
```

Все сообщения идут через EncryptedStream. Атакующий ДОЛЖЕН завершить Noise XX handshake прежде чем отправлять любые сообщения.

**Это добавляет стоимость атаке:**
- ML-KEM-768 encapsulate/decapsulate
- X25519 key exchange
- 3-way message exchange

**Результат:** ⚠️ ЧАСТИЧНАЯ ЗАЩИТА (увеличивает стоимость атаки)

---

### Шаг 6: Кто уязвим?

Только узлы с `config.hardcoded_secret_key`:

```rust
if let Some(ref secret_key) = config.hardcoded_secret_key {
    // Только hardcoded nodes входят сюда
}
```

Обычные узлы не имеют secret_key и игнорируют AuthChallenge.

**Результат:** ⚠️ ТОЛЬКО HARDCODED NODES УЯЗВИМЫ

---

## Итоговый вердикт

| Критерий | Gemini | Моя оценка |
|----------|--------|------------|
| Код существует | ✓ | ✓ |
| Уязвимость реальна | ✓ | ✓ |
| Severity | CRITICAL → HIGH | **HIGH** |

### Корректировки к отчёту Gemini

1. **Noise handshake обязателен** — Gemini написал "Не завершая хендшейк (или сразу после), атакующий отправляет поток сообщений". Это **неточно**. Noise handshake ОБЯЗАТЕЛЕН до любого сообщения.

2. **Уязвимы только hardcoded nodes** — это ограничивает impакт (1-10 узлов vs вся сеть).

3. **Severity HIGH, не CRITICAL** — атака не "уничтожает сеть", а временно DoS'ит bootstrap инфраструктуру.

---

## Рекомендации

Рекомендации Gemini корректны:

1. **Добавить rate limit** — `auth_challenge: TokenBucket::new(5.0, 0.1)` в PeerRateLimits

2. **spawn_blocking** — вынести sign_mldsa65:
   ```rust
   let sig = tokio::task::spawn_blocking(move || {
       crate::crypto::sign_mldsa65(&secret_key, &challenge)
   }).await.ok()??;
   ```

3. **Рассмотреть перенос AuthChallenge после handshake** — это усложнит атаку, но изменит протокол bootstrap.

---

## Финальный статус

```
[x] CONFIRMED — уязвимость реальна
[x] SEVERITY ADJUSTED — HIGH (не CRITICAL)
[ ] HALLUCINATED
[ ] ALREADY_PROTECTED
```

**Действие:** Требуется исправление до mainnet.
