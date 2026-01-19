# Montana Cryptographic Node System

**Post-Quantum Cryptography from Genesis**

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
Key:     Private key (Ed25519 → ML-DSA-65)
Owner:   Telegram ID of operator
IP:      Networking only
Alias:   For convenience
```

---

## Security

| Attack | Status |
|--------|--------|
| IP Hijacking | ✅ BLOCKED |
| DNS Spoofing | ✅ BLOCKED |
| MITM | ✅ BLOCKED |
| Transaction Forgery | ✅ BLOCKED |
| Quantum Computer | 🔄 Migrating to ML-DSA-65 |

---

## Files

### Core
- `node_crypto.py` — Cryptographic system
- `test_node_crypto.py` — Tests
- `junona_bot_simple.py` — Bot integration

### Documentation
- `NODE_CRYPTO_SYSTEM.md` — Full specification
- `ARCHITECTURE_FINAL.md` — Architecture overview
- `CRYPTOGRAPHY_SPECIFICATION.md` — Protocol-level crypto
- `SESSION_SUMMARY.md` — Implementation summary

---

## Migration Roadmap

- **Q1 2026:** Ed25519 (✅ current)
- **Q2 2026:** Hybrid (Ed25519 + ML-DSA-65)
- **Q3 2026:** Full ML-DSA-65
- **Q4 2026:** Post-quantum ready

---

**Ɉ Montana — Protocol of Ideal Money**

*Built on Ed25519, migrating to ML-DSA-65*
