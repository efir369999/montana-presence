# Ɉ Montana

A peer-to-peer electronic cash system based on time.

**Ticker:** $MONT

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

### Adonis Score

Five dimensions. All saturate.

| Dimension | Weight | Saturation |
|-----------|--------|------------|
| TIME | 50% | 180 days uptime |
| INTEGRITY | 20% | No violations |
| STORAGE | 15% | Full chain history |
| GEOGRAPHY | 10% | Location diversity |
| HANDSHAKE | 5% | Veteran trust bonds |

180 days = maximum influence. Capital irrelevant.

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

12 modules (Pantheon):

Chronos (VDF), Adonis (reputation), Hermes (P2P), Hades (storage), Athena (consensus), Prometheus (crypto), Mnemosyne (mempool), Plutus (wallet), Nyx (privacy), Themis (validation), Iris (RPC), Ananke (governance).

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
| [Montana_v3.1.md](Montana_v3.1.md) | Whitepaper v3.1. Post-quantum. Network hardening. Full specification. |
| [SECURITY_MODEL.md](SECURITY_MODEL.md) | Security model. Anti-cluster. All properties proven. |

---

## Security

### AI Audits

| Auditor | Version | Score | Status |
|---------|---------|-------|--------|
| Claude Opus 4.5 | v3.1 | 9.8/10 | [PASS](audits/anthropic/claude_opus_4.5_v3.1_audit.md) |
| Claude Opus 4.5 | v2.6 | 9.5/10 | [PASS](audits/anthropic/claude_opus_4.5_v2.6_audit.md) |
| Claude Opus 4.5 | v2.5 | 9.0/10 | [PASS](audits/anthropic/SECURITY_AUDIT.md) |
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

## Contact

alejandromontana@tutamail.com

---

Time is priceless. Now it has a price.

**Ɉ**
