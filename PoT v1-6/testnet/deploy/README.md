# Time Testnet Deployment

Two-node testnet: Moscow + Beijing.

## Prerequisites

- 2 Linux servers (Ubuntu 20.04+)
- Open ports: 18333 (P2P), 18332 (RPC)
- Python 3.8+

## Quick Deploy

### 1. Get Server IPs

```
MOSCOW_IP=x.x.x.x
BEIJING_IP=y.y.y.y
```

### 2. Deploy Moscow Node

SSH to Moscow server:

```bash
curl -sSL https://raw.githubusercontent.com/afgrouptime/proofoftime/main/testnet/deploy/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh moscow $MOSCOW_IP $BEIJING_IP
```

### 3. Deploy Beijing Node

SSH to Beijing server:

```bash
curl -sSL https://raw.githubusercontent.com/afgrouptime/proofoftime/main/testnet/deploy/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh beijing $MOSCOW_IP $BEIJING_IP
```

## Manual Deploy

### Moscow

```bash
export POT_BOOTSTRAP_PEERS="$BEIJING_IP:18333"
export POT_NETWORK=TESTNET
export POT_NODE_NAME=moscow-01
python node.py --run
```

### Beijing

```bash
export POT_BOOTSTRAP_PEERS="$MOSCOW_IP:18333"
export POT_NETWORK=TESTNET
export POT_NODE_NAME=beijing-01
python node.py --run
```

## Verify Connection

On either node:

```bash
# Check logs
sudo journalctl -u pot-node -f

# Look for:
# - "Registered self in consensus"
# - "Connected to peer"
# - "Auto-registered peer from block"
# - "Accepted block"
```

## Firewall

```bash
# Ubuntu/Debian
sudo ufw allow 18333/tcp
sudo ufw allow 18332/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=18333/tcp --permanent
sudo firewall-cmd --add-port=18332/tcp --permanent
sudo firewall-cmd --reload
```

## Troubleshooting

### Nodes can't connect

1. Check firewall on both servers
2. Verify IPs are correct
3. Check `POT_BOOTSTRAP_PEERS` is set

### Blocks not syncing

1. Both nodes must have same genesis (deterministic)
2. Check clock sync: `timedatectl status`
3. Ensure NTP is enabled: `sudo timedatectl set-ntp true`

### Check consensus

```bash
# In Python
from pantheon.athena.consensus import ConsensusEngine
engine = ConsensusEngine()
print(f"Registered nodes: {len(engine.nodes)}")
```

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Moscow Node    │◄───────►│  Beijing Node   │
│  (moscow-01)    │  P2P    │  (beijing-01)   │
│                 │ 18333   │                 │
│  Chronos (VDF)  │         │  Chronos (VDF)  │
│  Adonis (rep)   │         │  Adonis (rep)   │
│  Athena (cons)  │         │  Athena (cons)  │
│  ...            │         │  ...            │
└─────────────────┘         └─────────────────┘
```

## Monitoring

Both nodes share:
- Genesis block (deterministic)
- Consensus state (synced via blocks)
- Mempool (synced via P2P)

Each node has:
- Own private key
- Own Adonis score (starts at 0, grows over 180 days)
- Own block production rights (weighted by Adonis)
