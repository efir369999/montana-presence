#!/bin/bash
# Montana Node Deployment Script for Timeweb (Saint Petersburg)
# Быстрое развёртывание узла Montana на VPS в Санкт-Петербурге

set -e

# ===================================
# Configuration
# ===================================

REMOTE_HOST="${1:-176.124.208.93}"
REMOTE_USER="${2:-root}"
SSH_KEY="${3:-$HOME/.ssh/id_ed25519}"
NODE_NAME="${4:-montana-spb-$(date +%s)}"

MONTANA_PORT="19333"
DATA_DIR="/var/lib/montana"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ===================================
# Functions
# ===================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_ssh() {
    log_info "Checking SSH connection to $REMOTE_HOST..."
    if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "echo 'SSH OK'" > /dev/null 2>&1; then
        log_info "SSH connection successful"
        return 0
    else
        log_error "Cannot connect to $REMOTE_HOST via SSH"
        return 1
    fi
}

# ===================================
# Main
# ===================================

echo "======================================"
echo "  Montana Node Deployment"
echo "======================================"
echo ""
echo "Remote Host: $REMOTE_HOST"
echo "Remote User: $REMOTE_USER"
echo "Node Name:   $NODE_NAME"
echo "P2P Port:    $MONTANA_PORT"
echo ""

# Check SSH connection
if ! check_ssh; then
    log_error "Deployment aborted: SSH connection failed"
    exit 1
fi

# Upload cloud-init script
log_info "Uploading cloud-init configuration..."
scp -i "$SSH_KEY" "$(dirname "$0")/cloud-init-montana.yaml" "$REMOTE_USER@$REMOTE_HOST:/tmp/cloud-init-montana.yaml"

# Deploy via SSH
log_info "Deploying Montana node..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" bash <<'ENDSSH'
set -e

echo "[REMOTE] Starting Montana deployment..."

# Update system
echo "[REMOTE] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# Install dependencies
echo "[REMOTE] Installing dependencies..."
apt-get install -y -qq curl wget git build-essential pkg-config libssl-dev ufw fail2ban htop ntp chrony

# Setup firewall
echo "[REMOTE] Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 19333/tcp comment 'Montana P2P'
ufw allow 123/udp comment 'NTP'

# Configure time sync
echo "[REMOTE] Configuring time synchronization..."
systemctl enable chronyd
systemctl start chronyd
timedatectl set-ntp true

# Create montana user
echo "[REMOTE] Creating montana user..."
if ! id montana > /dev/null 2>&1; then
    useradd -m -s /bin/bash montana
fi

# Install Rust for montana user
echo "[REMOTE] Installing Rust..."
su - montana -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable"

# Clone Montana repository
echo "[REMOTE] Cloning Montana repository..."
if [ -d "/home/montana/montana" ]; then
    rm -rf /home/montana/montana
fi
su - montana -c "git clone https://github.com/afgrouptime/montana.git /home/montana/montana"

# Build Montana
echo "[REMOTE] Building Montana (this may take 10-15 minutes)..."
su - montana -c 'cd /home/montana/montana/Montana\ ACP/montana && source $HOME/.cargo/env && cargo build --release'

# Install binary
echo "[REMOTE] Installing Montana binary..."
cp "/home/montana/montana/Montana ACP/montana/target/release/montana" /usr/local/bin/montana
chmod +x /usr/local/bin/montana

# Create data directory
mkdir -p /var/lib/montana
chown -R montana:montana /var/lib/montana

# Create systemd service
echo "[REMOTE] Creating systemd service..."
cat > /etc/systemd/system/montana.service <<'EOF'
[Unit]
Description=Montana ACP Full Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=montana
Group=montana
WorkingDirectory=/var/lib/montana

Restart=always
RestartSec=10

LimitNOFILE=65536

Environment="RUST_LOG=montana=info"
Environment="RUST_BACKTRACE=1"

ExecStart=/usr/local/bin/montana \
    --node-type full \
    --port 19333 \
    --data-dir /var/lib/montana

ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/montana
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Create monitoring script
cat > /usr/local/bin/montana-status <<'EOF'
#!/bin/bash
echo "====================================="
echo "  Montana Node Status"
echo "====================================="
echo ""

echo "[Service Status]"
systemctl status montana --no-pager | head -5
echo ""

echo "[Network Connections]"
netstat -an | grep 19333 | wc -l | xargs echo "Active connections:"
echo ""

echo "[Resource Usage]"
ps aux | grep montana | grep -v grep | awk '{print "CPU: "$3"% | MEM: "$4"% | RSS: "$6" KB"}'
echo ""

echo "[Disk Usage]"
du -sh /var/lib/montana 2>/dev/null || echo "No data yet"
echo ""

echo "[Recent Logs (last 10 lines)]"
journalctl -u montana -n 10 --no-pager
EOF
chmod +x /usr/local/bin/montana-status

# Start service
echo "[REMOTE] Starting Montana service..."
systemctl daemon-reload
systemctl enable montana
systemctl start montana

# Wait for service to start
sleep 5

# Check status
echo "[REMOTE] Checking service status..."
if systemctl is-active --quiet montana; then
    echo "[REMOTE] ✓ Montana service is running"
else
    echo "[REMOTE] ✗ Montana service failed to start"
    journalctl -u montana -n 20 --no-pager
    exit 1
fi

echo ""
echo "======================================"
echo "  Montana Node Deployed Successfully"
echo "======================================"
echo ""
echo "Commands:"
echo "  Status:  montana-status"
echo "  Logs:    journalctl -u montana -f"
echo "  Restart: systemctl restart montana"
echo ""
echo "Network: P2P port 19333"
echo "Data: /var/lib/montana"
echo ""
ENDSSH

log_info "Deployment complete"
echo ""
echo "======================================"
echo "  Next Steps"
echo "======================================"
echo ""
echo "1. Monitor bootstrap progress:"
echo "   ssh $REMOTE_USER@$REMOTE_HOST 'montana-status'"
echo ""
echo "2. Watch live logs:"
echo "   ssh $REMOTE_USER@$REMOTE_HOST 'journalctl -u montana -f'"
echo ""
echo "3. Check network connections:"
echo "   ssh $REMOTE_USER@$REMOTE_HOST 'netstat -an | grep 19333'"
echo ""
echo "Bootstrap requires:"
echo "  - 100 peers (20 hardcoded + 80 P2P)"
echo "  - 25+ unique /16 subnets"
echo "  - ML-DSA-65 authentication"
echo ""
echo "lim(evidence → ∞) 1 Ɉ → 1 секунда"
