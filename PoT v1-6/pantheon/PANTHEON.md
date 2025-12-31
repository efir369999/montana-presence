# Pantheon

**13 gods. One protocol.**

---

## Architecture

```
                              ADAM
                         (Time / VDF)
                              │
                              ▼
    HERMES ◄──────────► ATHENA ◄──────────► HAL
   (Network)          (Consensus)         (Humanity)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           HADES          THEMIS          PROMETHEUS
         (Storage)      (Validation)      (Crypto)
              │               │               │
              └───────────────┼───────────────┘
                              ▼
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           PLUTUS           NYX            IRIS
          (Wallet)       (Privacy)         (API)
```

---

## The Gods

| # | God | Domain | Status |
|---|-----|--------|--------|
| 1 | **Adam** | Time / VDF / Bitcoin Oracle | Active |
| 2 | **Hermes** | P2P Network | Active |
| 3 | **Hades** | DAG Storage | Active |
| 4 | **Athena** | Consensus | Active |
| 5 | **Prometheus** | Cryptography | Active |
| 6 | **Mnemosyne** | Mempool | Integrated |
| 7 | **Plutus** | Wallet | Active |
| 8 | **Nyx** | Privacy | Active |
| 9 | **Themis** | Validation | Active |
| 10 | **Iris** | RPC/Dashboard | Active |
| 11 | **Ananke** | Governance | Planned |
| 12 | **Apostles** | 12 Trust Partners | Active |
| 13 | **Hal** | Humanity / Reputation | Active |

---

## Module Details

### Adam — Time

```python
from pantheon.adam import Adam, AdamLevel, FinalityState

adam = Adam()
adam.start()
ts = adam.get_timestamp()
```

**7 Levels (0-6):**
- 0: NODE_UTC — Hardware clock
- 1: GLOBAL_NTP — 12 national laboratories
- 2: MEMPOOL_TIME — Bitcoin mempool
- 3: BLOCK_TIME — Bitcoin blocks
- 4: BITCOIN_ACTIVE — Normal operation
- 5: VDF_FALLBACK — SHAKE256 VDF (quantum-resistant)
- 6: VDF_DEACTIVATE — Transitioning back

### Hal — Humanity

```python
from pantheon.hal import HalEngine, HumanityTier

hal = HalEngine()
score = hal.compute_reputation(pubkey)
```

**Five Fingers:**
- THUMB (TIME): 50% — uptime
- INDEX (INTEGRITY): 20% — no violations
- MIDDLE (STORAGE): 15% — chain history
- RING (EPOCHS): 10% — Bitcoin halvings survived
- PINKY (HANDSHAKE): 5% — mutual trust bonds

**Humanity Tiers:**
- Tier 1: HARDWARE (3 Apostles max)
- Tier 2: SOCIAL (6 Apostles max)
- Tier 3: TIME-LOCKED (12 Apostles max)

### Hermes — Network

```python
from pantheon.hermes import P2PNode
```

- Noise Protocol XX encryption
- Peer discovery and gossip

### Hades — Storage

```python
from pantheon.hades import BlockchainDB, DAGStorage
```

- SQLite persistent storage
- DAG block structure (1-8 parents)
- PHANTOM ordering

### Athena — Consensus

```python
from pantheon.athena import ConsensusCalculator, ConsensusEngine
```

- ECVRF leader selection
- VDF checkpoint validation

### Prometheus — Cryptography

```python
from pantheon.prometheus import Ed25519, sha256, WesolowskiVDF
```

- Ed25519 signatures
- SHA3-256, SHAKE256
- Post-quantum ready

### Nyx — Privacy

```python
from pantheon.nyx import StealthAddress, RingSignature, TieredPrivacy
```

**4 Tiers:**
- T0: Public
- T1: Stealth (receiver hidden)
- T2: Confidential (amount hidden)
- T3: Ring (sender hidden)

---

## Usage

```python
from pantheon.adam import Adam, AdamLevel
from pantheon.hal import HalEngine
from pantheon.athena import ConsensusCalculator

# Time oracle
adam = Adam()
adam.start()
ts = adam.get_timestamp()

# Reputation
hal = HalEngine()
score = hal.compute_reputation(pubkey)

# Leader selection
calc = ConsensusCalculator()
leader = calc.select_leader(nodes, seed)
```

---

## The Shortest Prompt

```
Proof of Time: Adam proves, Athena selects, Hal trusts.
```

---

*Time is the ultimate proof.*
