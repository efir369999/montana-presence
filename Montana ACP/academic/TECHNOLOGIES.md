# Montana ACP — Technologies

## Core Protocol

### Atemporal Coordinate Presence (ACP)
- Consensus mechanism based on time presence rather than computation
- Slice-based architecture (not blocks)
- VDF (Verifiable Delay Function) for time verification

### Cryptography
- **Post-quantum**: ML-KEM-768, ML-DSA-65 (NIST FIPS 203/204)
- **Hash**: SHA3-256
- **Encryption**: ChaCha20-Poly1305

### Network
- Custom P2P protocol (not libp2p)
- Presence-verified addresses
- Adaptive cooldown for Sybil resistance
- Netgroup diversity for Eclipse resistance

## Implementation

### Languages
- **Rust** — Core protocol (`montana/`)
- **Python** — Bots, tools, research

### Infrastructure
- Moscow node: 176.124.208.93
- Amsterdam node: 72.56.102.240
- P2P sync via git + custom protocol

### Telegram Integration
- Juno bot — Control node interface
- Channel parser — @mylifethoughts369, @mylifeprogram369
- Telethon for MTProto API

## Key Constants

```
T4 = 40 minutes (base interval)
τ₂ = 10 minutes (presence window)
MAX_INBOUND = 117 connections
MAX_PEERS_PER_NETGROUP = 2
```

## References

- `/Montana ACP/MONTANA.md` — Full protocol specification
- `/Montana ACP/layer_*.md` — Layer documentation
- `/Montana ACP/montana/` — Rust implementation

---
*Genesis: 2026-01-12*
