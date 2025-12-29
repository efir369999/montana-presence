# Proof of Time

**Consensus on time. Not money.**

---

## Core Idea

Time is the only resource that cannot be bought, accelerated, or transferred. Run a node for 180 days = maximum influence. Your capital doesn't matter.

```
1Ɉ = 1 second
Emission: 21,000,000 minutes (~132 years)
Block: 10 minutes
Halving: every 210,000 blocks
```

---

## How It Works

### Dual-Layer Consensus

```
Layer 1: PoH (Proof of History)
├─ 1 block/second
├─ Sequential hash chain
└─ Fast transactions

Layer 2: PoT (Proof of Time)
├─ Checkpoint every 10 minutes
├─ Wesolowski VDF (1M iterations)
└─ Finality — cannot be reverted
```

### Leader Selection

**ECVRF** (Verifiable Random Function) selects block producer proportionally to node weight.

### Node Weight

```
P(i) = 60% × Time + 20% × Storage + 20% × Reputation

Time:       saturates at 180 days uptime
Storage:    saturates at 80% chain history
Reputation: 7-dimensional Adonis score
```

**Saturation** = newcomer catches up to veteran in 180 days. This is a feature.

### Reputation: Adonis System

7 dimensions that encourage decentralization:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Integrity | 25% | No violations, valid proofs |
| Reliability | 20% | Uptime, block production |
| Longevity | 15% | Time in network |
| **Country** | **12%** | Unique country bonus |
| Contribution | 12% | Storage, relay, validation |
| Community | 8% | Peer vouching |
| City | 8% | Unique city bonus |

**Geographic decentralization**: First node from a new country gets +0.25 bonus. First from a new city gets +0.15. Fewer nodes in your location = higher score. This incentivizes global distribution.

### DAG

Each block references 1-8 parents. PHANTOM-PoT algorithm for ordering. Horizontal TPS scaling.

---

## Architecture: Pantheon

12 modules (Greek gods):

| # | God | Function |
|---|-----|----------|
| 1 | **Chronos** | VDF, PoH, time proofs |
| 2 | **Adonis** | 7-dimensional reputation |
| 3 | **Hermes** | P2P, Noise Protocol |
| 4 | **Hades** | DAG, SQLite storage |
| 5 | **Athena** | VRF consensus |
| 6 | **Prometheus** | Ed25519, ECVRF, RSA |
| 7 | **Mnemosyne** | Mempool |
| 8 | **Plutus** | Wallet, UTXO |
| 9 | **Nyx** | Privacy (LSAG, stealth) |
| 10 | **Themis** | Block validation |
| 11 | **Iris** | RPC, WebSocket |
| 12 | **Ananke** | Governance |

---

## Privacy: 4 Tiers

| Tier | Hidden | Size | Fee |
|------|--------|------|-----|
| T0 | Nothing | 250 B | 1× |
| T1 | Receiver | 400 B | 2× |
| T2 | + Amounts | 1.2 KB | 5× |
| T3 | Full RingCT | 2.5 KB | 10× |

T2/T3 experimental. Enable: `POT_ENABLE_EXPERIMENTAL_PRIVACY=1`

---

## Run

```bash
# Dev
pip install pynacl
python pot.py          # Dashboard with metrics
python node.py --run   # Run node

# Production (Linux)
curl -sSL https://raw.githubusercontent.com/afgrouptime/proofoftime/main/install.sh | bash
```

**Environment:**
```bash
POT_DATA_DIR=/path/to/data
POT_NETWORK=TESTNET        # MAINNET, TESTNET, REGTEST
POT_PORT=8333              # P2P
POT_RPC_PORT=8332          # API
POT_ALLOW_UNSAFE=1         # Testnet features
```

---

## Why Not PoW/PoS

| | Bitcoin | Ethereum | Proof of Time |
|---|---------|----------|---------------|
| Consensus | PoW | PoS | VDF + Time |
| Influence | Money→ASIC | Money→Stake | Time (can't buy) |
| Entry barrier | High | Medium | Low |
| 51% attack | $20B | $10B | N × 180 days |

---

## Contact

alejandromontana@tutamail.com

---

*In time, we are all equal.*

**Ɉ**
