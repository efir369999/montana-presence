# Ɉ Montana: Temporal Time Unit

**Version:** 3.6
**Ticker:** $MONT
**Architecture:** Timechain

---

## What Is Ɉ Montana?

**Ɉ** (inverted t) is a Temporal Time Unit. **Montana** is the Timechain that produces it.

```
lim(evidence → ∞) 1 Ɉ → 1 second
```

**Timechain:** chain of time, bounded by physics. "Time passed — this is fact."

Montana builds trust through **Asymptotic Trust Consensus** (ATC):
- Physical constraints (thermodynamics, sequentiality)
- Computational hardness (post-quantum cryptography)
- Protocol primitives (VDF, VRF)
- Consensus mechanisms (DAG, UTC finality)

**v3.6:** Timechain architecture, UTC finality, ±5s tolerance, platform-independent light clients.

---

## Definition

```
1 Ɉ     ≈ 1 second
60 Ɉ    ≈ 1 minute
3600 Ɉ  ≈ 1 hour
86400 Ɉ ≈ 1 day

Total: 1,260,000,000 Ɉ ≈ 21 million minutes
```

---

## Time Verification

| Layer | Method | Guarantee |
|-------|--------|-----------|
| **VDF** | Sequential computation | Bounded by physics |
| **Finality** | Accumulated VDF depth | Physics-based (self-sovereign) |

---

## Finality Model

```
Hard Finality (3 min)    → 3 UTC boundaries passed
     ↑
Medium Finality (2 min)  → 2 UTC boundaries passed
     ↑
Soft Finality (1 min)    → 1 UTC boundary passed
```

**Attack cost:** Requires advancing UTC. Time is physical.

Finality at UTC boundaries (00:00, 00:01, ...). No hardware advantage.

---

## Participation (3 Tiers, 2 Node Types)

**Node Types:**
| Type | Storage | Tier |
|------|---------|------|
| **Full Node** | Full timechain history | Tier 1 |
| **Light Node** | From connection only | Tier 2 |

**Tiers:**
| Tier | Participants | Lottery | Purpose |
|------|--------------|---------|---------|
| **1** | Full Node operators | 70% | Network security |
| **2** | Light Node / Light Client owners | 20% | Infrastructure |
| **3** | Light Client users | 10% | Mass adoption |

**Light Client Platforms:**

Montana has no dependency on any specific platform. Supported:
- Telegram, Discord, WeChat (messaging)
- iOS (App Store), Android (Google Play) (mobile)
- Web Application (browser)

Time passes equally for all. No platform provides advantage.

---

## Key Properties

| Property | Value |
|----------|-------|
| Project | Ɉ Montana |
| Symbol | Ɉ |
| Ticker | $MONT |
| Architecture | Timechain |
| Definition | lim(evidence → ∞) 1 Ɉ → 1 second |
| Total Supply | 1,260,000,000 Ɉ |
| Pre-allocation | 0 |
| Node Types | 2 (Full, Light) |
| Tiers | 3 (numbered 1-2-3) |
| Cryptography | Post-quantum (NIST 2024) |
| Finality | UTC boundaries (self-sovereign) |
| Time Tolerance | ±5 seconds |

---

## Documentation

| Document | Description |
|----------|-------------|
| [WHITEPAPER.md](WHITEPAPER.md) | Complete specification |
| [MONTANA_TECHNICAL_SPECIFICATION.md](MONTANA_TECHNICAL_SPECIFICATION.md) | Implementation details |
| [MONTANA_ATC_MAPPING.md](MONTANA_ATC_MAPPING.md) | ATC layer mapping |

---

## ATC Foundation

```
Layer 3+: Ɉ Montana — Timechain (TTU)
       ↑
Layer 2:  Consensus (DAG, UTC Finality)
       ↑
Layer 1:  Primitives (VDF, VRF)
       ↑
Layer 0:  Computation (SHA-3, SPHINCS+)
       ↑
Layer -1: Physics (Thermodynamics, Sequentiality)
```

---

## Principle

```
lim(evidence → ∞) Trust = 1
∀t: Trust(t) < 1
```

We approach certainty; we never claim to reach it.

**Time is the universal constant. Ɉ Montana builds trust in its value.**

---

## Installation

### Prerequisites

- Python 3.9+
- Rust 1.75+ (for STARK proofs)

### Quick Start

```bash
# Clone repository
git clone https://github.com/afgrouptime/atc.git
cd atc/Montana

# Install Python package
pip install -e .

# Build Rust STARK library (optional, for fast verification)
cd montana-stark
pip install maturin
maturin develop --release
cd ..

# Verify installation
python -c "from montana.core.vdf import VDF; print('OK')"
python -c "from montana.crypto.stark import STARK_AVAILABLE; print(f'STARK: {STARK_AVAILABLE}')"
```

### Docker

```bash
# Build and run
docker-compose up montana-node

# Or build manually
docker build -t montana .
docker run -p 8545:8545 -p 8546:8546 -p 30303:30303 montana node --rpc --ws
```

---

## Usage

### Python API

```python
from montana.core.vdf import VDF
from montana.crypto.stark import generate_vdf_proof, verify_vdf_proof

# VDF computation
vdf = VDF(iterations=16_777_216)
result = vdf.compute(input_bytes)

# STARK proof (if available)
if STARK_AVAILABLE:
    proof = generate_vdf_proof(input_bytes, result.output, result.checkpoints)
    is_valid = verify_vdf_proof(input_bytes, result.output, proof)
```

### CLI

```bash
# Start full node
montana node --rpc --ws

# Start light node
montana node --light

# Check status
montana status
```

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black montana/
ruff check montana/

# Type check
mypy montana/
```

---

## Project Structure

```
Montana/
├── montana/                 # Python implementation
│   ├── core/               # VDF, blocks, types
│   ├── crypto/             # SPHINCS+, VRF, STARK
│   ├── consensus/          # DAG, eligibility
│   ├── network/            # P2P protocol
│   ├── privacy/            # Tiers T0-T3
│   ├── node/               # Full/Light nodes
│   ├── api/                # RPC, WebSocket
│   └── cli/                # Command line
├── montana-stark/          # Rust STARK library
│   ├── src/                # Prover, verifier, AIR
│   ├── tests/              # Integration tests
│   └── benches/            # Benchmarks
├── Dockerfile              # Production image
├── docker-compose.yml      # Container orchestration
├── pyproject.toml          # Python package config
└── requirements.txt        # Dependencies
```

---

## Links

- **Repository:** https://github.com/afgrouptime/atc
- **X:** https://x.com/tojesatoshi

---

<div align="center">

**Ɉ Montana**

*lim(evidence → ∞) 1 Ɉ → 1 second*

**Self-sovereign. Physics-based.**

**$MONT**

</div>
