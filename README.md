# ATC Protocol v7

**Asymptotic Trust Consensus** — a temporal consensus mechanism where trust approaches zero asymptotically.

```
Trust(t) → 0 as t → ∞
```

## Overview

ATC is a three-layer consensus protocol that uses **time** as the fundamental scarce resource instead of energy (PoW) or capital (PoS).

| Layer | Name | Trust Formula | Mechanism |
|-------|------|---------------|-----------|
| 0 | Physical Time | T₀ = 0 | Global atomic clocks (34 laboratories) |
| 1 | Temporal Proof | T₁(c) = 1/√c | VDF + STARK proofs |
| 2 | Finalization | T₂(c) = 2^(-c) | Bitcoin anchoring |

**Key insight:** Time from atomic clocks is a physical observable, not a cryptographic claim.

## Features

- **Post-quantum cryptography:** SPHINCS+ signatures, SHAKE256 hashing, ML-KEM key exchange
- **ASIC-resistant rate limiting:** Argon2id + RandomX personal proof of work
- **Sybil resistance:** √N efficiency decay makes identity multiplication unprofitable
- **Equal distribution:** Every participant receives exactly 86,400 seconds per day

## Installation

```bash
pip install atc-protocol
```

With full cryptographic support:

```bash
pip install atc-protocol[full]
```

### Building Rust Extensions

For native performance (STARK proofs and RandomX):

```bash
# STARK proofs
cd rust/winterfell_stark
maturin develop --release

# RandomX PoW
cd rust/randomx
maturin develop --release
```

## Quick Start

### Run a Node

```bash
atc-node --testnet
```

### Configuration

```python
from atc.node.config import NodeConfig

config = NodeConfig.default_testnet()
config.network.listen_port = 19657
config.api.port = 8546
config.save("config.json")
```

### API

The node exposes a JSON-RPC API:

```bash
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"atc_chainInfo","params":[],"id":1}'
```

Available methods:
- `atc_status` — Node status
- `atc_chainInfo` — Blockchain info
- `atc_getBlock` — Get block by height or hash
- `atc_getAccount` — Get account info
- `atc_sendTransaction` — Submit transaction
- `atc_getScore` — Get account score

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ATC Protocol v7                       │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Bitcoin Finalization                          │
│  ├── Epoch anchoring (halving cycle)                    │
│  └── Trust: T₂(c) = 2^(-c)                              │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Temporal Proof                                │
│  ├── VDF: SHAKE256 (2^24 - 2^28 iterations)             │
│  ├── STARK proofs (Winterfell)                          │
│  └── Trust: T₁(c) = 1/√c                                │
├─────────────────────────────────────────────────────────┤
│  Layer 0: Physical Time                                 │
│  ├── 34 atomic clock laboratories                       │
│  ├── W-MSR Byzantine consensus                          │
│  └── Trust: T₀ = 0 (physical observable)                │
└─────────────────────────────────────────────────────────┘
```

## Protocol Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PROTOCOL_VERSION` | 7 | Current protocol version |
| `VDF_BASE_ITERATIONS` | 2^24 | ~2.5 seconds computation |
| `VDF_MAX_ITERATIONS` | 2^28 | ~40 seconds maximum |
| `HEARTBEAT_INTERVAL` | 60s | Time between heartbeats |
| `EPOCH_BLOCKS` | 210,000 | Bitcoin halving cycle |
| `MAX_TIME_DRIFT` | 100ms | Maximum allowed clock drift |

## Score Function

Influence is determined by the square root of heartbeat count:

```
Score = √(epoch_heartbeats)
```

This creates natural Sybil resistance:
- 1 identity with 100 heartbeats: Score = 10
- 100 identities with 1 heartbeat each: Score = 100 × 1 = 100, but 100× cost

Efficiency decreases as 1/√N, making Sybil attacks economically irrational.

## Repository Structure

```
ATC v7/          Current implementation
├── atc/         Python package
├── rust/        Rust extensions (STARK, RandomX)
└── tests/       Test suite
```

## Development

```bash
cd "ATC v7"

# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Run specific test
pytest tests/test_layer1.py -v
```

## Documentation

- [Whitepaper](ATC%20v7/Asymptotic_Trust_Consensus.md) — Academic paper
- [Technical Specification](ATC%20v7/Asymptotic_Trust_Consensus_TECH_SPECIFICATION.md) — Implementation details

## License

MIT License

---

*Dedicated to the memory of*

**Hal Finney** (1956-2014)

*First recipient of a Bitcoin transaction. Creator of RPOW.*

*"Running bitcoin" — January 11, 2009*
