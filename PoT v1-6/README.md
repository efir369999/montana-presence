# Ɉ Montana: Time-Proven Human Temporal Currency

*A peer-to-peer electronic cash system based on time and humanity.*

**Ticker:** $MONT | **Version:** 4.3

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

---

## Consensus: ADAM (Anchored Deterministic Asynchronous Mesh)

**Bitcoin is the clock. SHAKE256 VDF is the insurance.**

### 7 Temporal Levels

| Level | Name | Description |
|-------|------|-------------|
| 0 | NODE_UTC | Hardware clock (UTC) |
| 1 | GLOBAL_NTP | 13 national metrology laboratories |
| 2 | MEMPOOL_TIME | Bitcoin mempool observation |
| 3 | BLOCK_TIME | Bitcoin block confirmation |
| 4 | BITCOIN_ACTIVE | Normal operation, VDF not needed |
| 5 | VDF_FALLBACK | Bitcoin down 2+ blocks, SHAKE256 VDF active |
| 6 | VDF_DEACTIVATE | Bitcoin returned +20 blocks, transition back |

**Normal operation:** Levels 0-4. Bitcoin provides authoritative time.

**Fallback only:** Level 5 activates ONLY when Bitcoin unavailable for 2+ blocks (~20 min). SHAKE256 VDF provides sovereign timekeeping. PoH (SHA3-256 chain) provides instant transaction ordering.

### 13 National Metrology Laboratories

```
USA: NIST/USNO (time.nist.gov)
UK: NPL (ntp1.npl.co.uk)
Germany: PTB (ptbtime1.ptb.de)
Russia: ВНИИФТРИ (ntp2.vniiftri.ru)
China: NIM (cn.pool.ntp.org)
Japan: NICT (ntp.jst.mfeed.ad.jp)
Canada: NRC (time.nrc.ca)
Australia: NMI (ntp.ausaid.gov.au)
India: NPL (in.pool.ntp.org)
Sweden: Netnod (ntp.se)
Switzerland: METAS (ntp.metas.ch)
South Korea: KRISS (time.kriss.re.kr)
Mexico: CENAM (ntp.cenam.mx)
```

### DAG-PHANTOM Ordering

In DAG architecture, there is no leader selection. Any eligible node can produce blocks. ECVRF determines eligibility. PHANTOM orders blocks.

### Five Fingers (Reputation)

| Finger | Weight | Saturation |
|--------|--------|------------|
| TIME | 50% | 210,000 BTC blocks (resets at halving) |
| INTEGRITY | 20% | No violations |
| STORAGE | 15% | Full chain history |
| EPOCHS | 10% | Bitcoin halvings survived |
| HANDSHAKE | 5% | 12 Apostle trust bonds |

TIME measured in Bitcoin blocks. Resets at each halving.

### The Twelve Apostles

Each node selects exactly 12 trust partners. Attack one → collective slashing.

### HAL: Human Analyse Language

Proof of humanity, not just proof of time. Named after Hal Finney (1956-2014).

| Tier | Max Apostles | Weight | Proof |
|------|--------------|--------|-------|
| Hardware | 3 | 0.3 | TPM / Secure Enclave / FIDO2 |
| Social | 6 | 0.6 | Custom social graph |
| Time-Locked | 12 | 1.0 | Bitcoin halving anchored |

**Sybil cost:** N fake identities = N × 4 years waiting.

---

## Post-Quantum Cryptography

VDF (SHAKE256) is backup timing when Bitcoin unavailable. Quantum-resistant cryptography ensures long-term security.

| Function | Algorithm | Standard |
|----------|-----------|----------|
| Signatures | SPHINCS+-SHAKE-128f | NIST FIPS 205 |
| Hashing | SHA3-256 | NIST FIPS 202 |
| VDF | SHAKE256 | NIST FIPS 202 |
| Key Exchange | ML-KEM-768 | NIST FIPS 203 |

---

## Privacy

| Tier | Hidden | Fee | Status |
|------|--------|-----|--------|
| T0 | Nothing | 1× | Production |
| T1 | Receiver (stealth) | 2× | Production |

T2/T3 removed. Only T0 and T1 supported.

---

## Architecture: 11 Pantheon Gods

| Module | Name | Responsibility |
|--------|------|----------------|
| ADAM | Anchored Deterministic Asynchronous Mesh | 7 temporal levels, Bitcoin anchor, VDF fallback |
| PAUL | Peer Authenticated Unified Link | P2P, Noise Protocol |
| HADES | Storage | SQLite, DAG persistence |
| ATHENA | Consensus | DAG ordering, PHANTOM, finality (no leader) |
| PROMETHEUS | Crypto | VDF, VRF, SPHINCS+, SHA3 |
| PLUTUS | Wallet | Key management, AES-256-GCM |
| NYX | Privacy | T0/T1 only, stealth addresses |
| THEMIS | Validation | Block/TX verification |
| IRIS | RPC | JSON-RPC 2.0 |
| APOSTLES | Trust | 12 Apostles, handshakes, slashing |
| HAL | Human Analyse Language | Reputation, Sybil detection |

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
| [Montana_v4.3.md](Montana_v4.3.md) | Whitepaper v4.3 |
| [Montana_v4.3.pdf](Montana_v4.3.pdf) | PDF version |

---

## Roadmap

| Version | Status | Features |
|---------|--------|----------|
| v1.0 | ✓ Done | Core PoT consensus, VDF, basic wallet |
| v2.0 | ✓ Done | DAG-PHANTOM, tiered privacy |
| v3.0 | ✓ Done | Post-quantum crypto (SPHINCS+, ML-KEM) |
| v3.1 | ✓ Done | Network hardening, VPN blocking |
| v4.0 | ✓ Done | 12 Apostles, EPOCHS, Bitcoin Oracle |
| v4.1 | ✓ Done | HAL: Human Analyse Language |
| v4.2 | ✓ Done | Bitcoin-anchored TIME dimension |
| v4.3 | ✓ Done | Module consolidation: ADAM, HAL, PAUL |
| v5.0 | Planned | Mainnet launch, mobile wallet |

---

## Contact

alejandromontana@tutamail.com

---

**Ɉ Montana** — Time-Proven Human Temporal Currency

*Time cannot be bought. Humanity cannot be faked.*

**Ɉ**
