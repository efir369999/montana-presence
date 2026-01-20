# Montana Cryptographic Node System

**ML-DSA-65 MAINNET — Post-Quantum from Genesis**

---

## Quick Start

### Node Address Format
```
mt + SHA256(public_key)[:20].hex()

Example: mta46b633d258059b90db46adffc6c5ca08f0e8d6c
```

### Commands
```bash
# View nodes
/node                                  # All nodes
/node amsterdam.montana.network        # By alias
/node mta46b633d...                   # By address

# Transfer
/transfer amsterdam.montana.network 100  # To node (alias)
/transfer mta46b633d... 100             # To node (address)
/transfer 123456789 100                 # To user (Telegram ID)

# Balance
/balance                               # Your balance

# Register node (admin only)
/register_node tokyo "🇯🇵 Tokyo" 1.2.3.4 123456789 light
```

---

## Cryptography: ML-DSA-65 (FIPS 204)

### MAINNET Implementation
```python
from dilithium_py.ml_dsa import ML_DSA_65

# Key generation
public_key, private_key = ML_DSA_65.keygen()

# Address derivation
address = "mt" + hashlib.sha256(public_key).digest()[:20].hex()

# Signing
signature = ML_DSA_65.sign(private_key, message)

# Verification
ML_DSA_65.verify(public_key, message, signature)
```

### Key Sizes
| Parameter | Size |
|-----------|------|
| Private key | 4032 bytes |
| Public key | 1952 bytes |
| Signature | 3309 bytes |
| Address | 42 characters |

---

## Architecture

### Users
```
Address: Telegram ID
Key:     Telegram Session
UX:      Maximum simplicity
```

### Nodes
```
Address: mt + SHA256(public_key)[:20]
Key:     Private key ML-DSA-65 (4032 bytes)
Owner:   Telegram ID of operator
IP:      Networking only
Alias:   For convenience
```

---

## Security

| Attack | Status |
|--------|--------|
| Quantum Computer | ✅ PROTECTED (ML-DSA-65) |
| IP Hijacking | ✅ BLOCKED |
| DNS Spoofing | ✅ BLOCKED |
| MITM | ✅ BLOCKED |
| Harvest Now Decrypt Later | ✅ BLOCKED |
| Transaction Forgery | ✅ BLOCKED |

---

## Files

### Core
- `node_crypto.py` — ML-DSA-65 cryptographic system
- `node_wallet.py` — Wallet system
- `test_node_crypto.py` — Tests
- `junomontanaagibot.py` — Bot integration

### Documentation
- `NODE_CRYPTO_SYSTEM.md` — Full specification
- `ARCHITECTURE_FINAL.md` — Architecture overview
- `CRYPTOGRAPHY_SPECIFICATION.md` — Protocol-level crypto
- `SESSION_SUMMARY.md` — Implementation summary

---

## Status: MAINNET PRODUCTION

**January 2026:** ML-DSA-65 ACTIVE

- ✅ All nodes on ML-DSA-65
- ✅ Montana protected from quantum computers from day one
- ✅ No legacy Ed25519 — pure post-quantum
- ✅ FIPS 204 compliant

---

**Ɉ Montana — Protocol of Ideal Money**

*ML-DSA-65 MAINNET — Post-quantum from genesis*

*FIPS 204 compliant*
