# Ɉ Montana: Time-Proven Human Temporal Currency

*A peer-to-peer electronic cash system based on time and humanity.*

**Ticker:** $MONT | **Version:** 4.2

---

## Overview

**Ɉ Montana** is a cryptocurrency built on Proof of Time (PoT) consensus. Time cannot be bought, accelerated, or transferred.

```
Symbol: Ɉ
Ticker: $MONT
Unit: 1 Ɉ = 1 second
Supply: 1,260,000,000 Ɉ (21 million minutes)
Block reward: 50 min → 25 min → 12.5 min → ...
Halving: every 210,000 blocks (~4 years)
Emission: 132 years
```

**Temporal Compression:** Reward ratio converges from 5:1 to 1:1. Inflation asymptotically approaches zero. Nash's Ideal Money realized.

---

## Consensus: Proof of Time

Consensus based on time, not capital.

### Dual Layer

**Layer 1 — Proof of History.** Sequential SHA3-256 chain. Transaction ordering.

**Layer 2 — Proof of Time.** VDF checkpoints every 10 minutes. Finality.

### Leader Selection

ECVRF selects block producer. Probability proportional to Adonis score.

### Adonis Score (v4.0+)

Five dimensions. All saturate.

| Dimension | Weight | Saturation |
|-----------|--------|------------|
| TIME | 50% | 210,000 BTC blocks (resets at halving) |
| INTEGRITY | 20% | No violations |
| STORAGE | 15% | Full chain history |
| EPOCHS | 10% | Bitcoin halvings survived |
| HANDSHAKE | 5% | 12 Apostle trust bonds |

TIME measured in Bitcoin blocks. Resets at each halving. Capital irrelevant.

### The Twelve Apostles (v4.0)

Each node selects exactly 12 trust partners. Attack one → collective slashing.

### Hal Humanity System (v4.1)

Proof of humanity, not just proof of time. Named after Hal Finney.

| Tier | Max Apostles | Weight | Proof |
|------|--------------|--------|-------|
| Hardware | 3 | 0.3 | TPM / Secure Enclave / FIDO2 |
| Social | 6 | 0.6 | Custom social graph |
| Time-Locked | 12 | 1.0 | Bitcoin halving anchored |

**Sybil cost:** Creating N fake identities = N × 4 years waiting.

### Security Properties — ALL PROVEN

| Property | Status | Evidence |
|----------|--------|----------|
| Cluster-cap bypass | PROVEN | 50% → 45% attacker influence |
| Adaptive adversary | PROVEN | 100% detection rate |
| 33% = Byzantine | PROVEN | Mathematical proof |
| TIME = human time | PROVEN | VDF anchoring |

**Run proofs:** `python3 tests/test_security_proofs.py`

Defense mechanisms:
- **GlobalByzantineTracker** — Detects subdivided clusters by behavioral fingerprint
- **Correlation Detection** — Nodes acting synchronously are penalized
- **33% Cluster Cap** — No cluster exceeds Byzantine threshold
- **VDF Anchoring** — TIME cannot be manipulated via clock attacks

See [SECURITY_MODEL.md](SECURITY_MODEL.md) for full details.

### DAG

1-8 parent references per block. PHANTOM ordering. Horizontal scaling.

---

## Post-Quantum Cryptography (v3.0)

- **SPHINCS+** — Hash-based signatures (NIST FIPS 205)
- **SHA3-256** — Keccak hashing (NIST FIPS 202)
- **SHAKE256 VDF** — Quantum-resistant VDF with STARK proofs
- **ML-KEM** — Lattice-based key exchange (NIST FIPS 203)

## Network Security (v3.1)

- **Static IP** — Dynamic residential and CGNAT blocked
- **VPN Detection** — ASN-based VPN/Tor/Proxy blocking
- **Sybil Protection** — Node registration after block validation only
- **Eclipse Defense** — Minimum 8 outbound connections enforced
- **Rate Limiting** — Per-IP and per-subnet throttling
- **Wallet Encryption** — Minimum 8-character password

---

## Privacy

| Tier | Hidden | Fee |
|------|--------|-----|
| T0 | Nothing | 1× |
| T1 | Receiver | 2× |
| T2 | + Amount | 5× |
| T3 | + Sender | 10× |

---

## Architecture

14 modules (Pantheon):

| Module | Domain | Description |
|--------|--------|-------------|
| Chronos | VDF | Time proofs, SHAKE256 VDF |
| Adonis | Reputation | 5 dimensions, score calculation |
| Hermes | P2P | Noise Protocol, peer management |
| Hades | Storage | SQLite, DAG persistence |
| Athena | Consensus | Leader selection, finality |
| Prometheus | Crypto | SPHINCS+, ECVRF, SHA3 |
| Mnemosyne | Mempool | Transaction pool |
| Plutus | Wallet | Key management, TX building |
| Nyx | Privacy | T0-T3 tiers, Bulletproofs |
| Themis | Validation | Block/TX verification |
| Iris | RPC | JSON-RPC interface |
| Ananke | Governance | Protocol upgrades |
| Apostles | Trust | 12 Apostle handshakes, slashing |
| Hal | Humanity | Sybil resistance (v4.1) |

---

## Run

```bash
pip install pynacl
python node.py --run
```

---

## Documentation

| Document | Content |
|----------|---------|
| [Montana_v4.2.md](Montana_v4.2.md) | Whitepaper v4.2. 12 Apostles. Hal Humanity. Full specification. |
| [Montana_v4.2.pdf](Montana_v4.2.pdf) | PDF version. |
| [SECURITY_MODEL.md](SECURITY_MODEL.md) | Security model. Anti-cluster. All properties proven. |

---

## Security

### AI Audits

| Auditor | Version | Score | Status |
|---------|---------|-------|--------|
| Claude Opus 4.5 | v4.0 | 9.2/10 | [PASS](audits/anthropic/claude_opus_4.5_v4.0_audit.md) |
| Claude Opus 4.5 | v3.1 | 9.8/10 | [PASS](audits/anthropic/claude_opus_4.5_v3.1_audit.md) |
| Claude Opus 4.5 | v2.6 | 9.5/10 | [PASS](audits/anthropic/claude_opus_4.5_v2.6_audit.md) |
| Gemini 3 Flash | v2.5 | 9.0/10 | [PASS](audits/alphabet/gemini_3_flash_audit.md) |

See [audits/](audits/) for full reports.

---

## Comparison

| | Bitcoin | Ethereum | Ɉ Montana |
|---|---------|----------|-----------|
| Consensus | PoW | PoS | PoT |
| Influence | Hardware | Stake | Time |
| 51% attack | $20B | $10B | N × 180 days |
| Cluster attack | N/A | Possible | Blocked (33% cap) |
| Quantum-safe | No | No | Yes |

---

## Roadmap

| Version | Status | Features |
|---------|--------|----------|
| v1.0 | ✓ Done | Core PoT consensus, VDF, basic wallet |
| v2.0 | ✓ Done | DAG-PHANTOM, tiered privacy |
| v3.0 | ✓ Done | Post-quantum crypto (SPHINCS+, ML-KEM) |
| v3.1 | ✓ Done | Network hardening, VPN blocking, rate limits |
| v4.0 | ✓ Done | 12 Apostles, EPOCHS, Bitcoin Oracle |
| v4.1 | ✓ Done | Hal Humanity System (Sybil resistance) |
| v4.2 | ✓ Done | Documentation, integration completeness |
| v5.0 | Planned | Mainnet launch, mobile wallet |

---

## Contact

alejandromontana@tutamail.com

---

**Ɉ Montana** — Time-Proven Human Temporal Currency

*Time cannot be bought. Humanity cannot be faked.*

**Ɉ**
