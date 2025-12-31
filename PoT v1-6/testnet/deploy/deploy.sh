#!/bin/bash
# Time Testnet Node Deployment Script
# Usage: ./deploy.sh <moscow|beijing> <moscow_ip> <beijing_ip>

set -e

NODE_TYPE=${1:-moscow}
MOSCOW_IP=${2:-"127.0.0.1"}
BEIJING_IP=${3:-"127.0.0.1"}

echo "=== Time Testnet Deployment ==="
echo "Node: $NODE_TYPE"
echo "Moscow IP: $MOSCOW_IP"
echo "Beijing IP: $BEIJING_IP"
echo ""

# Determine peer IP
if [ "$NODE_TYPE" = "moscow" ]; then
    PEER_IP=$BEIJING_IP
    MY_IP=$MOSCOW_IP
    ENV_FILE="moscow.env"
else
    PEER_IP=$MOSCOW_IP
    MY_IP=$BEIJING_IP
    ENV_FILE="beijing.env"
fi

# Create directories
echo "Creating directories..."
sudo mkdir -p /var/lib/pot
sudo mkdir -p /var/log/pot
sudo mkdir -p /opt/pot

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git

# Clone or update repository
if [ -d "/opt/pot/proofoftime" ]; then
    echo "Updating repository..."
    cd /opt/pot/proofoftime
    git pull
else
    echo "Cloning repository..."
    cd /opt/pot
    git clone https://github.com/afgrouptime/proofoftime.git
    cd proofoftime
fi

# Create virtual environment
echo "Setting up Python environment..."
python3 -m venv /opt/pot/venv
source /opt/pot/venv/bin/activate
pip install --upgrade pip
pip install pynacl

# Create environment file
echo "Creating environment file..."
cat > /opt/pot/node.env << EOF
# Time Testnet - $NODE_TYPE Node
POT_NETWORK=TESTNET
POT_NODE_NAME=$NODE_TYPE-01
POT_P2P_PORT=18333
POT_RPC_PORT=18332
POT_BOOTSTRAP_PEERS=$PEER_IP:18333
POT_DATA_DIR=/var/lib/pot
POT_LOG_LEVEL=INFO
POT_ALLOW_UNSAFE=1
POT_EXTERNAL_IP=$MY_IP
EOF

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/pot-node.service > /dev/null << EOF
[Unit]
Description=Time (Proof of Time) Testnet Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pot/proofoftime
EnvironmentFile=/opt/pot/node.env
ExecStart=/opt/pot/venv/bin/python node.py --run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "Starting node..."
sudo systemctl daemon-reload
sudo systemctl enable pot-node
sudo systemctl start pot-node

# Show status
echo ""
echo "=== Deployment Complete ==="
echo ""
sudo systemctl status pot-node --no-pager
echo ""
echo "Commands:"
echo "  View logs:    sudo journalctl -u pot-node -f"
echo "  Stop node:    sudo systemctl stop pot-node"
echo "  Restart:      sudo systemctl restart pot-node"
echo ""
echo "P2P Port: 18333 (ensure firewall allows TCP)"
echo "RPC Port: 18332"
echo ""
