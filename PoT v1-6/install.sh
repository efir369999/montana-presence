#!/bin/bash
# Proof of Time - One-Click Install & Run Script
# https://github.com/afgrouptime/proofoftime
#
# Usage: curl -sSL https://raw.githubusercontent.com/afgrouptime/proofoftime/main/install.sh | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[PoT]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Handle root vs non-root
if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         PROOF OF TIME - NODE INSTALLER            ║${NC}"
echo -e "${GREEN}║         One-Click Install & Auto-Start            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

log "Starting installation..."

# Detect OS
if [[ -f /etc/debian_version ]]; then
    PKG_MANAGER="apt"
    log "Detected: Debian/Ubuntu"
    $SUDO apt update -qq
    $SUDO apt install -y -qq python3 python3-pip python3-venv libsodium-dev git curl >/dev/null 2>&1
elif [[ -f /etc/redhat-release ]]; then
    PKG_MANAGER="yum"
    log "Detected: RHEL/CentOS"
    $SUDO yum install -y -q python3 python3-pip libsodium-devel git curl >/dev/null 2>&1
else
    error "Unsupported OS. Use Debian/Ubuntu or RHEL/CentOS."
fi
log "System dependencies installed ✓"

# Directories
POT_HOME="/opt/proofoftime"
POT_DATA="/var/lib/proofoftime"
POT_LOG="/var/log/proofoftime"
POT_USER="pot"

# Create user and directories
log "Creating user and directories..."
$SUDO useradd -r -s /bin/false $POT_USER 2>/dev/null || true
$SUDO mkdir -p $POT_HOME $POT_DATA $POT_LOG
$SUDO chown -R $POT_USER:$POT_USER $POT_DATA $POT_LOG
log "Directories created ✓"

# Clone repository
log "Downloading Proof of Time..."
if [[ -d "$POT_HOME/.git" ]]; then
    cd $POT_HOME && $SUDO git pull -q
else
    $SUDO rm -rf $POT_HOME
    $SUDO git clone -q https://github.com/afgrouptime/proofoftime.git $POT_HOME
fi
$SUDO chown -R $POT_USER:$POT_USER $POT_HOME
log "Source code downloaded ✓"

# Setup Python environment
log "Setting up Python environment (this may take a minute)..."
cd $POT_HOME
sudo -u $POT_USER python3 -m venv venv
sudo -u $POT_USER ./venv/bin/pip install --upgrade pip -q 2>/dev/null
sudo -u $POT_USER ./venv/bin/pip install -r requirements.txt -q 2>/dev/null
log "Python environment ready ✓"

# Verify installation
log "Verifying installation..."
sudo -u $POT_USER ./venv/bin/python -c "
from crypto import WesolowskiVDF
from consensus import ConsensusEngine
from privacy import LSAG
print('OK')
" >/dev/null 2>&1 || error "Module verification failed"
log "All modules verified ✓"

# Create config
log "Creating configuration..."
$SUDO tee /etc/proofoftime.json > /dev/null << 'EOF'
{
    "data_dir": "/var/lib/proofoftime",
    "log_dir": "/var/log/proofoftime",
    "p2p_port": 8333,
    "rpc_port": 8332,
    "rpc_bind": "127.0.0.1",
    "log_level": "INFO",
    "max_peers": 125,
    "dns_seeds": []
}
EOF
$SUDO chown $POT_USER:$POT_USER /etc/proofoftime.json

# Create systemd service
log "Creating systemd service..."
$SUDO tee /etc/systemd/system/proofoftime.service > /dev/null << EOF
[Unit]
Description=Proof of Time Node
Documentation=https://github.com/afgrouptime/proofoftime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$POT_USER
Group=$POT_USER
WorkingDirectory=$POT_HOME
ExecStart=$POT_HOME/venv/bin/python node.py --run --no-dashboard --config /etc/proofoftime.json
Restart=always
RestartSec=10
TimeoutStopSec=60

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$POT_DATA $POT_LOG

# Resource limits
LimitNOFILE=65535
MemoryMax=4G

[Install]
WantedBy=multi-user.target
EOF

# Create helper commands
$SUDO tee /usr/local/bin/pot-cli > /dev/null << 'EOF'
#!/bin/bash
curl -s -X POST -H "Content-Type: application/json" \
    -d "{\"method\": \"$1\", \"params\": [${@:2}]}" \
    http://127.0.0.1:8332/
EOF
$SUDO chmod +x /usr/local/bin/pot-cli

$SUDO tee /usr/local/bin/pot-log > /dev/null << 'EOF'
#!/bin/bash
journalctl -u proofoftime -f
EOF
$SUDO chmod +x /usr/local/bin/pot-log

$SUDO tee /usr/local/bin/pot-status > /dev/null << 'EOF'
#!/bin/bash
systemctl status proofoftime
EOF
$SUDO chmod +x /usr/local/bin/pot-status

$SUDO tee /usr/local/bin/pot-restart > /dev/null << 'EOF'
#!/bin/bash
sudo systemctl restart proofoftime
EOF
$SUDO chmod +x /usr/local/bin/pot-restart

$SUDO tee /usr/local/bin/pot-dashboard > /dev/null << 'EOF'
#!/bin/bash
cd /opt/proofoftime && ./venv/bin/python dashboard.py "$@"
EOF
$SUDO chmod +x /usr/local/bin/pot-dashboard

log "Helper commands created ✓"

# Firewall
if command -v ufw &> /dev/null; then
    $SUDO ufw allow 8333/tcp comment "Proof of Time P2P" 2>/dev/null || true
    log "Firewall configured (ufw) ✓"
elif command -v firewall-cmd &> /dev/null; then
    $SUDO firewall-cmd --permanent --add-port=8333/tcp 2>/dev/null || true
    $SUDO firewall-cmd --reload 2>/dev/null || true
    log "Firewall configured (firewalld) ✓"
fi

# Enable and start service
log "Starting Proof of Time node..."
$SUDO systemctl daemon-reload
$SUDO systemctl enable proofoftime >/dev/null 2>&1
$SUDO systemctl start proofoftime

# Wait for startup
sleep 3

# Show dashboard
echo ""
log "Installation complete!"
echo ""

cd $POT_HOME && ./venv/bin/python dashboard.py --live
