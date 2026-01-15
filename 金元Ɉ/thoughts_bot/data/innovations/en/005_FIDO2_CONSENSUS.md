# FIDO2 in Consensus

**Biometric Verification at Protocol Level**
**Montana Protocol v1.0**

---

## Abstract

Montana — the first blockchain where biometric verification (FIDO2/WebAuthn) is integrated directly into consensus. Verified User must physically confirm presence (touch) and pass biometrics (fingerprint/face) to participate in block production.

**Key difference:**
```
Other blockchains: private key = voting right
Montana: private key + biometrics = voting right
```

---

## 1. Introduction

### 1.1 Key Problem

| System | Authorization | Problem |
|--------|---------------|---------|
| Bitcoin | Private key | Key can be stolen |
| Ethereum | Private key | Key can be copied |
| Exchanges | 2FA (TOTP) | Seed can be stolen |
| **Montana** | **FIDO2 + key** | **Need finger/face** |

### 1.2 Montana Solution

Verified User (20% of consensus) requires two factors:
1. Private key (something you HAVE)
2. Biometrics (something you ARE)

---

## 2. Architecture

### 2.1 FIDO2 Flags in Consensus

**Source code:** [consensus.rs#L382-L389](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs#L382-L389)

```rust
// User Present (UP) — physical touch of device
if flags & 0x01 == 0 {
    return Err(PresenceError::Fido2UserNotPresent);
}

// User Verified (UV) — biometrics (fingerprint/face)
if flags & 0x04 == 0 {
    return Err(PresenceError::Fido2UserNotVerified);
}
```

### 2.2 Two Node Tiers

| Tier | Verification | Consensus Share |
|------|--------------|-----------------|
| Full Node | Key only | 80% |
| Verified User | Key + FIDO2 | 20% |

---

## 3. Verification Protocol

### 3.1 Attestation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Node receives challenge from network                    │
│  2. User touches device (UP=1)                              │
│  3. Device verifies fingerprint/face (UV=1)                 │
│  4. Secure Element signs attestation                        │
│  5. Node sends signed presence proof                        │
│  6. Network verifies UP and UV flags                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Random Interval (Anti-Bot)

**Source code:** [consensus.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs)

```rust
// Verified User must confirm presence
// at random moment within 10-40 minute window
// Bot cannot predict when
```

---

## 4. Attack Protection

| Attack | Defense | Mechanism |
|--------|---------|-----------|
| Key theft | Need biometrics | UV flag required |
| Remote bot | Need touch | UP flag required |
| Replay | Challenge-Response | Fresh challenge each time |
| Fake device | Secure Element | Hardware attestation |

---

## 5. Scientific Novelty

1. **FIDO2 in consensus** — first blockchain with biometrics at protocol level
2. **Two-factor consensus** — key + biometrics for voting rights
3. **Anti-Bot** — random interval makes automation impossible
4. **80/20 Hybrid** — servers without biometrics + humans with biometrics

---

## 6. References

| Document | Link |
|----------|------|
| Consensus code | [consensus.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs) |
| FIDO2 specification | [WebAuthn W3C](https://www.w3.org/TR/webauthn-2/) |
| ACP Consensus | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
