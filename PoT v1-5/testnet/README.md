# Proof of Time Testnet

**Network:** pot-testnet-1
**Chain ID:** 1001
**Version:** 2.0.0 Pantheon

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start 3-node testnet with faucet
./launch.sh start

# Check status
./launch.sh status

# View logs
./launch.sh logs

# Stop
./launch.sh stop
```

### Option 2: Local Node

```bash
# Run single node without Docker
./launch.sh local
```

---

## Network Endpoints

| Service | URL | Port |
|---------|-----|------|
| Seed Node 1 | http://localhost:9334 | P2P: 9333 |
| Seed Node 2 | http://localhost:9336 | P2P: 9335 |
| Seed Node 3 | http://localhost:9338 | P2P: 9337 |
| Faucet | http://localhost:9340 | - |
| Explorer | http://localhost:9341 | - |

---

## Genesis Configuration

| Parameter | Value |
|-----------|-------|
| Total Supply | 1,000,000,000 POT |
| Founder Allocation | 10% (100M POT) |
| Testnet Faucet | 20% (200M POT) |
| Validator Rewards | 70% (700M POT) |

---

## Consensus Parameters

| Parameter | Value |
|-----------|-------|
| Block Interval | 60 seconds |
| VDF Iterations | 100,000 |
| VRF Threshold | 50% |
| Min Validators | 3 |
| Max Validators | 100 |

---

## Probability Weights

| Component | Weight |
|-----------|--------|
| Time (Chronos) | 60% |
| Space (Hades) | 20% |
| Reputation (Adonis) | 20% |

---

## Faucet

Request testnet tokens:

```bash
# Via curl
curl -X POST http://localhost:9340/request \
  -H "Content-Type: application/json" \
  -d '{"address": "YOUR_HEX_ADDRESS"}'

# Response
{
  "success": true,
  "tx_hash": "abc123...",
  "amount": 1000
}
```

**Limits:**
- 1000 POT per request
- 1 hour cooldown per address

---

## Running Your Own Node

### Requirements

- Python 3.11+
- libsodium
- libgmp

### Installation

```bash
# Clone repository
git clone https://github.com/afgrouptime/proofoftime.git
cd proofoftime

# Install dependencies
pip install -r requirements.txt

# Run node
python node.py --run --config testnet/config.json
```

### Configuration

Edit `testnet/config.json`:

```json
{
  "p2p": {
    "default_port": 9333,
    "bootstrap_nodes": [
      "/dns4/seed1.proofoftime.org/tcp/9333"
    ]
  }
}
```

---

## Pantheon Modules

| Module | Pantheon Name | Status |
|--------|---------------|--------|
| VDF | Chronos | Active |
| Reputation | Adonis | Active |
| P2P Network | Hermes | Active |
| Storage | Hades | Active |
| Consensus | Athena | Active |
| Cryptography | Prometheus | Active |
| Mempool | Mnemosyne | Active |
| Wallet | Plutus | Active |
| Privacy | Nyx | T0 Only |
| Validation | Themis | Active |
| RPC | Iris | Active |
| Config | Ananke | Active |

---

## RPC API

### Get Status

```bash
curl http://localhost:9334/status
```

### Get Block

```bash
curl http://localhost:9334/block/HEIGHT
```

### Get Balance

```bash
curl http://localhost:9334/balance/ADDRESS
```

### Submit Transaction

```bash
curl -X POST http://localhost:9334/tx \
  -H "Content-Type: application/json" \
  -d '{"tx": "SIGNED_TX_HEX"}'
```

---

## Troubleshooting

### Nodes not syncing

```bash
# Check peer connections
curl http://localhost:9334/peers

# Restart nodes
./launch.sh restart
```

### Reset testnet

```bash
# WARNING: Deletes all data
./launch.sh reset
```

### View logs

```bash
# All logs
./launch.sh logs

# Specific node
./launch.sh logs seed1
```

---

## Security Notice

This is a **TESTNET**. Do not use real funds or production keys.

- Tokens have no value
- Network may be reset at any time
- Privacy features (T1-T3) are disabled

---

## Links

- GitHub: https://github.com/afgrouptime/proofoftime
- Documentation: See `/docs` folder
- Whitepaper: See `ProofOfTime_TechnicalSpec_v1.1.pdf`

---

*Time is the ultimate proof.*
