**Модель:** Gemini 3 Pro
**Компания:** Google
**Дата:** 07.01.2026 14:55 UTC

# CRITICAL SECURITY REPORT: Eclipse Protection Bypass

## 1. Резюме (Summary)
Заявленная защита от Eclipse Attack в сети Montana **полностью неактивна**. Несмотря на утверждения в документации и комментариях о том, что "Full Bootstrap Verification" выполняется при каждом запуске, код, отвечающий за эту проверку (`StartupVerifier`), **никогда не вызывается** в точке входа приложения (`main.rs`) или в сетевом контроллере (`Network::start`).

Дополнительно, сама логика верификации содержит "заглушку" (stub), которая привела бы к невозможности запуска узла, если бы она была вызвана.

## 2. Детали уязвимости (Vulnerability Details)

### A. Отсутствие вызова защиты (Critical)
**Файлы:** `src/main.rs`, `src/net/protocol.rs`

Файл `main.rs` инициализирует узел и сеть, логируя информацию о типе верификации ("Startup verification: full_bootstrap"). Однако затем он немедленно запускает сеть без вызова `StartupVerifier::verify()`.

В `src/net/protocol.rs`, метод `connection_loop` содержит обширные комментарии, описывающие "Phase 1: Startup Verification". Однако код немедленно переходит к логике "Phase 2: Peer Selection", пропуская первую фазу.

**Код (`src/main.rs`):**
```rust
// Информация о верификации логируется...
info!("Startup verification: {} ...", verify_type);

// ...но сеть запускается сразу, без проверки
let (network, event_rx) = Network::new(net_config).await?;
network.start().await?; // Начинает подключения немедленно
```

### B. Реализация-заглушка (High)
**Файл:** `src/net/startup.rs`

Даже если бы `StartupVerifier` был вызван, метод `query_hardcoded_tips` является заглушкой, возвращающей пустой список.

```rust
async fn query_hardcoded_tips(&self, addrs: &[SocketAddr]) -> Vec<PeerChainInfo> {
    // ...
    // Placeholder: in production, this would make actual network requests
    Vec::new() // Возвращает пустой вектор
}
```

Так как логика требует `MIN_HARDCODED_RESPONSES` (15), проверка `responses.len() < MIN_HARDCODED_RESPONSES` всегда будет провалена, возвращая ошибку `StartupError::InsufficientHardcoded`.

## 3. Вектор атаки (Eclipse)

1.  **Подготовка:** Атакующий использует ботнет (50+ IP в разных подсетях /16).
2.  **Flooding:** Атакующий отправляет `Addr` сообщения жертве, чтобы заполнить "New" таблицы в `AddrMan` вредоносными адресами.
3.  **Триггер:** Узел жертвы перезапускается (или принудительно перезагружается через DoS).
4.  **Исполнение:**
    -   Жертва запускается.
    -   **Bypass:** Проверка `StartupVerifier` пропускается.
    -   `Network` начинает подключения.
    -   `AddrMan` выбирает IP атакующего из заполненных бакетов.
    -   Жертва подключается к узлам атакующего.
    -   Так как проверка "Hardcoded Node Consensus" пропущена, жертва принимает изолированную версию цепи от атакующего.
5.  **Влияние:** Двойная трата, цензура, кража средств.

## 4. Рекомендации (Remediation)

1.  **Реализовать `query_hardcoded_tips`:** Заменить заглушку в `src/net/startup.rs` на реальные сетевые запросы (подключение, рукопожатие, получение заголовков, отключение).
2.  **Принудительная верификация:** В `src/main.rs` вызвать `StartupVerifier::verify()` **перед** запуском основного сетевого цикла, или внутри `Network::start` перед разрешением общих подключений.
3.  **Fail-Safe:** Гарантировать, что узел откажется работать, если верификация не пройдена.

---

---

# ОПРОВЕРЖЕНИЕ: Claude Opus 4.5 (Adversarial Mode)

**Дата:** 07.01.2026 15:30 UTC
**Модель:** Claude Opus 4.5
**Компания:** Anthropic

---

## Вердикт: ОТЧЁТ GEMINI ОШИБОЧЕН

Gemini 3 Pro допустил критическую ошибку в анализе кодовой базы. Он читал **устаревший/неиспользуемый файл** (`startup.rs`) вместо **реально вызываемого кода** (`verification.rs`).

---

## Детальное опровержение

### Ошибка 1: "StartupVerifier не вызывается"

**Утверждение Gemini:** Код логирует информацию о верификации, но сеть запускается сразу.

**Факт:** `main.rs:124-167` содержит **BLOCKING** вызов верификации:

```rust
// main.rs:123-167
} else {
    // Run bootstrap verification (BLOCKING)
    info!("Running bootstrap verification...");
    info!("Requirements: 100 peers, 25+ /16 subnets, hardcoded consensus");

    let verifier = VerificationClient::new(testnet, port, genesis.clone());

    match verifier.verify().await {        // <-- BLOCKING CALL
        Ok(result) => {
            info!("Bootstrap verification PASSED");
            // ...success handling
        }
        Err(e) => {
            error!("CRITICAL: Bootstrap verification FAILED");
            return Err(format!("Bootstrap verification failed: {}", e).into());
            // ^^^^ NODE STARTUP ABORTED
        }
    }
}

// Network starts ONLY AFTER verification passes:
let (network, event_rx) = Network::new(net_config).await?;  // Line 185
network.start().await?;                                       // Line 186
```

**Код `Network::new()` вызывается на строке 185, ПОСЛЕ завершения `verifier.verify().await`.**

---

### Ошибка 2: "query_hardcoded_tips — заглушка"

**Утверждение Gemini:** Метод `query_hardcoded_tips` в `startup.rs` возвращает пустой вектор.

**Факт:** `main.rs` использует `VerificationClient`, а не `StartupVerifier`.

`VerificationClient` находится в `verification.rs` и имеет **полную реализацию** с реальными сетевыми запросами:

```rust
// verification.rs:344-403 — РЕАЛЬНАЯ реализация
async fn query_hardcoded_nodes(
    &self,
    addrs: &[SocketAddr],
) -> (Vec<PeerChainInfo>, Vec<SocketAddr>) {
    let responses = Arc::new(Mutex::new(Vec::new()));
    let discovered = Arc::new(Mutex::new(HashSet::new()));

    let mut handles = Vec::new();

    for addr in addrs {
        let handle = tokio::spawn(async move {
            let _permit = sem.acquire().await.ok()?;

            // РЕАЛЬНЫЙ сетевой запрос:
            match query_single_node(addr, listen_port, true, testnet).await {
                Ok((info, peer_addrs)) => {
                    responses.lock().await.push(info);
                    // ...
                }
                Err(e) => { /* error handling */ }
            }
        });
        handles.push(handle);
    }

    // Wait for ALL queries to complete
    for handle in handles {
        let _ = handle.await;
    }

    // Return collected responses
    (responses, discovered)
}
```

Функция `query_single_node()` (`verification.rs:507-711`) выполняет:
1. TCP connect с таймаутом
2. AuthChallenge (криптографический вызов)
3. AuthResponse с ML-DSA-65 подписью
4. Верификацию подписи против hardcoded pubkey
5. Version/Verack handshake
6. GetAddr для обнаружения P2P пиров

---

### Ошибка 3: "Network начинает подключения немедленно"

**Факт:** Последовательность в main.rs:

```
1. verifier.verify().await     — BLOCKING, может занять 30+ секунд
2. Network::new()              — только если verify() вернул Ok
3. Network::start()            — только после new()
```

Если `verify()` возвращает `Err`, узел завершается с ошибкой (`main.rs:163-164`):
```rust
return Err(format!("Bootstrap verification failed: {}", e).into());
```

---

## Причина ошибки Gemini

Gemini читал файл `startup.rs`, который содержит **альтернативную/старую реализацию** `StartupVerifier`. Но `main.rs` импортирует и использует `VerificationClient` из `verification.rs`:

```rust
// main.rs:16-18
use crate::net::{
    NetConfig, NetEvent, Network, VerificationClient, NODE_FULL, NODE_PRESENCE,
    verification_type,
};
```

Gemini не проследил цепочку импортов и проанализировал неправильный файл.

---

## Реальный Adversarial Review: Eclipse Attack на Montana

### Attack Surface

| Input | Trust Level | Protection |
|-------|-------------|------------|
| Hardcoded nodes | Cryptographically verified (ML-DSA-65) | Challenge-response auth |
| P2P peers | Consensus-verified | 100 peers, 25+ subnets |
| AddrMan (peers.dat) | Untrusted candidates | Cryptographic bucketing |
| System clock | Local | Verified vs network median |

### Attempted Attacks

| # | Attack Vector | Result |
|---|---------------|--------|
| 1 | BGP/ISP MITM on hardcoded nodes | **PROTECTED** — ML-DSA-65 signature verification (`verification.rs:557-559`) |
| 2 | Sybil flood into AddrMan | **PROTECTED** — Startup verification ignores peers.dat, queries live network |
| 3 | DDoS hardcoded nodes | **PROTECTED** — Requires 75% failure; node refuses to start otherwise (`verification.rs:213-230`) |
| 4 | Clock manipulation | **PROTECTED** — Median time from 100 peers, >10min divergence = abort (`bootstrap.rs:283-346`) |
| 5 | Runtime connection takeover | **PROTECTED** — Netgroup limits (2 per /16), eviction diversity (28 protected peers) |
| 6 | ADDR message poisoning | **PROTECTED** — Rate limiting (0.1/sec), cryptographic bucket assignment |

### Critical Protection Chain

```
+-------------------------------------------------------------+
| Node Startup                                                 |
+-------------------------------------------------------------+
| 1. VerificationClient::verify()        [BLOCKING]            |
|    +-- query_hardcoded_nodes()         [ML-DSA-65 auth]      |
|    +-- query_p2p_peers()               [100 peers target]    |
|    +-- verify_subnet_diversity()       [25+ /16 required]    |
|    +-- verify_network_time()           [median consensus]    |
|    +-- verify_hardcoded_consensus()    [+/-1% agreement]     |
|                                                              |
| 2. IF verify() fails -> ABORT (node does not start)          |
|                                                              |
| 3. Network::new() + Network::start()   [only on success]     |
+-------------------------------------------------------------+
```

### Findings

| Severity | Finding | Status |
|----------|---------|--------|
| CRITICAL | None | - |
| HIGH | None | - |
| MEDIUM | Single hardcoded node (current testnet) | Known limitation, planned expansion |
| LOW | startup.rs contains stale code | Should be removed to prevent confusion |

---

## Verdict

```
[X] GEMINI REPORT INVALID — Analysis based on wrong file
[X] MONTANA ECLIPSE PROTECTION VERIFIED — Full implementation exists and is called
```

Montana's eclipse resistance is **correctly implemented** in `verification.rs`:
- Cryptographic hardcoded node authentication (ML-DSA-65)
- 100 peer queries with 25+ /16 subnet diversity
- Blocking verification before network start
- Node refuses to run if verification fails

**Recommendation:** Remove or clearly deprecate `startup.rs` to prevent future analysis confusion.

---

**Reviewed by:** Claude Opus 4.5 (Adversarial Mode)
**Date:** 2026-01-07 15:30 UTC
