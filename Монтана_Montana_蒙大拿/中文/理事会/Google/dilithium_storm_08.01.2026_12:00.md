# Security Audit: Network Layer / DoS

**Модель:** Gemini 3 Pro
**Компания:** Google
**Дата:** 08.01.2026 12:00 UTC

---

## 1. Понимание архитектуры

Montana ACP — это система, где консенсус достигается не через PoW/PoS, а через "наблюдаемое время" и физические инварианты (Слой -1). Слайсы (Slices) заменяют блоки и упорядочиваются по временным меткам.

Сетевой слой должен защищать этот хрупкий механизм синхронизации. Однако, внедрение пост-квантовой криптографии (ML-DSA, ML-KEM) создает новые векторы атак, связанные с высокой вычислительной стоимостью этих примитивов. Я атакую именно это: стоимость защиты.

---

## 2. Изученные файлы

| Файл | LOC | Ключевые компоненты |
|------|-----|---------------------|
| `net/protocol.rs` | 1500+ | Основной цикл обработки сообщений, хендшейк, диспетчер. |
| `net/rate_limit.rs` | 880 | TokenBucket реализация, лимитеры для Inv/Addr/Get. |
| `crypto.rs` | 150 | Обертки над Dilithium (ML-DSA-65). |
| `net/message.rs` | 160 | Определения сообщений и их размеров. |

---

## 3. Attack Surface

Точки входа:
1.  **Handshake (Noise XX):** Потенциально тяжелый, но защищен таймаутами.
2.  **Message Processing:** Основной цикл `process_message`.
3.  **Hardcoded Node Auth:** Механизм, позволяющий узлам доказать, что они "официальные".

---

## 4. Найденные уязвимости

### [CRITICAL] Dilithium Storm (CPU Exhaustion on Bootstrap Nodes)

**Файл:** `Montana ACP/montana/src/net/protocol.rs:1175`

**Уязвимый код:**
```rust
1175|            Message::AuthChallenge(challenge) => {
1176|                if let Some(ref secret_key) = config.hardcoded_secret_key {
1177|                    // СИНХРОННАЯ ТЯЖЕЛАЯ ОПЕРАЦИЯ БЕЗ RATE LIMIT
1178|                    let sig = match crate::crypto::sign_mldsa65(secret_key, &challenge) {
// ...
```

**Вектор атаки:**
1.  Атакующий устанавливает TCP-соединение с Seed Node (адрес известен, это публичная инфраструктура).
2.  Не завершая хендшейк (или сразу после), атакующий отправляет поток сообщений `AuthChallenge`.
3.  В `rate_limit.rs` структура `PeerRateLimits` **не содержит** лимитера для `AuthChallenge`.
4.  Узел принимает сообщение (оно `allowed_pre_handshake`), вызывает `sign_mldsa65`.
5.  Так как `sign_mldsa65` — синхронная функция, выполняющая сложные операции над решетками (Lattice-based cryptography), поток `tokio` блокируется.
6.  При потоке в 1000 msg/sec процессор узла уходит в 100% Load, переставая обрабатывать легитимные соединения.

**Импакт:**
Полный отказ в обслуживании (DoS) критической инфраструктуры (Bootstrap Nodes). Новые узлы не могут подключиться к сети, так как не могут получить список пиров от сидов. Сеть фрагментируется.

**Сложность:**
Низкая. Требуется 1 CPU атакующего, чтобы положить 1 CPU сервера (асимметрия в пользу защиты отсутствует, так как проверка подписи дешевле генерации, но здесь мы заставляем сервер *генерировать*).

**PoC сценарий:**
```rust
// Pseudo-code attacker
let stream = TcpStream::connect(seed_ip).await?;
let mut noise = NoiseBuilder::new_initiator()...; // Handshake
// Flood loop
loop {
    let challenge = [0u8; 32];
    let msg = Message::AuthChallenge(challenge);
    noise.write_encrypted(msg).await?;
    // No wait for response
}
```

---

## 5. Атаки, которые НЕ работают

1.  **Memory Exhaustion via Large Messages:**
    В `net/encrypted.rs` реализована защита через чанкинг. Даже если я пошлю заголовок 2MB, память аллоцируется постепенно. Глобальный лимит памяти на 117 соединений (~250MB) приемлем.

2.  **Sybil via Subnet Flooding:**
    В `net/rate_limit.rs` реализован `GlobalSubnetLimiter` (Erebus protection) с разделением на Fast/Slow tiers. Это очень надежная защита от захвата слотов с одного провайдера.

---

## 6. Рекомендации

1.  **Добавить Rate Limit:** В `PeerRateLimits` добавить `auth_challenge: TokenBucket::new(5.0, 0.1)`. 5 запросов в берсте, 1 раз в 10 секунд восстановление.
2.  **Make it Async:** Вынести `sign_mldsa65` в `tokio::task::spawn_blocking`, чтобы не блокировать сетевой цикл.
3.  **Disable Pre-Handshake Auth:** Запретить `AuthChallenge` до завершения Noise-хендшейка.

---

## 7. Вердикт

[ ] CRITICAL — есть уязвимости, позволяющие уничтожить сеть (инфраструктуру)
[x] HIGH — есть серьёзные уязвимости
[ ] MEDIUM — есть уязвимости среднего риска
[ ] LOW — только minor issues
[ ] SECURE — уязвимостей не найдено

