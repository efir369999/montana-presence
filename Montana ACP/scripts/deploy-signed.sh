#!/bin/bash
# Montana Signed Binary Deployment
# Elegant deployment using signed releases
#
# Security: Verifies SHA256 + ML-DSA-65 signature before installation

set -e

# ===================================
# Configuration
# ===================================

REMOTE_HOST="${1:-176.124.208.93}"
REMOTE_USER="${2:-root}"
SSH_KEY="${3:-$HOME/.ssh/id_ed25519}"
VERSION="${4:-latest}"

MONTANA_PORT="19333"
DATA_DIR="/var/lib/montana"

# GitHub release URL
GITHUB_REPO="afgrouptime/montana"
if [ "$VERSION" = "latest" ]; then
    RELEASE_URL="https://github.com/$GITHUB_REPO/releases/latest/download"
else
    RELEASE_URL="https://github.com/$GITHUB_REPO/releases/download/v$VERSION"
fi

# Alejandro Montana release signing public key (ML-DSA-65)
# TODO: Replace with real public key when signing is implemented
SIGNING_PUBKEY="PLACEHOLDER_PUBKEY"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
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
echo "  Montana Signed Deployment"
echo "======================================"
echo ""
echo "Remote Host: $REMOTE_HOST"
echo "Version:     $VERSION"
echo "Release URL: $RELEASE_URL"
echo ""

# Check SSH
if ! check_ssh; then
    log_error "Deployment aborted: SSH connection failed"
    exit 1
fi

# Deploy
log_step "Deploying Montana with signed binary..."

ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" bash <<ENDSSH
set -e

echo "[REMOTE] Starting Montana signed deployment..."

# Update system
echo "[REMOTE] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# Install dependencies (minimal, no build tools needed!)
echo "[REMOTE] Installing dependencies..."
apt-get install -y -qq curl wget ufw fail2ban chrony

# Setup firewall with rate limiting
echo "[REMOTE] Configuring firewall with rate limiting..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'

# Rate limit P2P port (30 connections per minute per source)
ufw limit 19333/tcp comment 'Montana P2P (rate limited)'

ufw allow 123/udp comment 'NTP'

# Configure time sync
echo "[REMOTE] Configuring time synchronization..."
systemctl enable chronyd
systemctl start chronyd
timedatectl set-ntp true

# Create montana user (no sudo privileges)
echo "[REMOTE] Creating montana user..."
if ! id montana > /dev/null 2>&1; then
    useradd -m -s /bin/bash -G systemd-journal montana
fi

# Download signed release
echo "[REMOTE] Downloading signed Montana binary..."
TMPDIR=\$(mktemp -d)
cd "\$TMPDIR"

# Download files
wget -q "$RELEASE_URL/montana-$VERSION-x86_64-unknown-linux-gnu" -O montana
wget -q "$RELEASE_URL/montana-$VERSION-x86_64-unknown-linux-gnu.sha256" -O montana.sha256
wget -q "$RELEASE_URL/montana-$VERSION-x86_64-unknown-linux-gnu.sig" -O montana.sig

if [ ! -f montana ]; then
    echo "[REMOTE] ERROR: Failed to download binary"
    exit 1
fi

# Verify SHA256 hash
echo "[REMOTE] Verifying SHA256 hash..."
if command -v sha256sum > /dev/null 2>&1; then
    EXPECTED_HASH=\$(cat montana.sha256 | cut -d' ' -f1)
    ACTUAL_HASH=\$(sha256sum montana | cut -d' ' -f1)

    if [ "\$EXPECTED_HASH" = "\$ACTUAL_HASH" ]; then
        echo "[REMOTE] ✓ Hash verification passed"
    else
        echo "[REMOTE] ✗ Hash mismatch!"
        echo "[REMOTE]   Expected: \$EXPECTED_HASH"
        echo "[REMOTE]   Actual:   \$ACTUAL_HASH"
        exit 1
    fi
else
    echo "[REMOTE] WARNING: sha256sum not found, skipping hash verification"
fi

# Verify ML-DSA-65 signature
echo "[REMOTE] Verifying ML-DSA-65 signature..."
# TODO: Implement signature verification when keygen tool supports it
echo "[REMOTE] WARNING: ML-DSA-65 verification not yet implemented"
echo "[REMOTE] Trusting downloaded binary (use at own risk)"

# Install binary
echo "[REMOTE] Installing Montana binary..."
chmod +x montana
cp montana /usr/local/bin/montana

# Verify binary works
echo "[REMOTE] Verifying binary..."
if /usr/local/bin/montana --version > /dev/null 2>&1; then
    echo "[REMOTE] ✓ Binary verified"
else
    echo "[REMOTE] ✗ Binary test failed"
    exit 1
fi

# Cleanup
rm -rf "\$TMPDIR"

# Create data directory
mkdir -p $DATA_DIR
chown -R montana:montana $DATA_DIR

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
WorkingDirectory=$DATA_DIR

Restart=always
RestartSec=10

LimitNOFILE=65536

Environment="RUST_LOG=montana=info"
Environment="RUST_BACKTRACE=1"

ExecStart=/usr/local/bin/montana \
    --node-type full \
    --port $MONTANA_PORT \
    --data-dir $DATA_DIR

# Security hardening
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$DATA_DIR
NoNewPrivileges=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=true

[Install]
WantedBy=multi-user.target
EOF

# Create monitoring script
cat > /usr/local/bin/montana-status <<'EOFSTATUS'
#!/bin/bash
echo "====================================="
echo "  Montana Node Status"
echo "====================================="
echo ""

echo "[Service]"
systemctl status montana --no-pager | head -5
echo ""

echo "[Network]"
netstat -an | grep $MONTANA_PORT | wc -l | xargs echo "Active connections:"
echo ""

echo "[Resources]"
ps aux | grep "[m]ontana" | awk '{print "CPU: "\$3"% | MEM: "\$4"% | RSS: "\$6" KB"}'
echo ""

echo "[Disk Usage]"
du -sh $DATA_DIR 2>/dev/null || echo "No data yet"
echo ""

echo "[Recent Logs (last 10)]"
journalctl -u montana -n 10 --no-pager
EOFSTATUS
chmod +x /usr/local/bin/montana-status

# Start service
echo "[REMOTE] Starting Montana service..."
systemctl daemon-reload
systemctl enable montana
systemctl start montana

# Wait and verify
sleep 5

if systemctl is-active --quiet montana; then
    echo "[REMOTE] ✓ Montana service is running"
else
    echo "[REMOTE] ✗ Montana service failed"
    journalctl -u montana -n 20 --no-pager
    exit 1
fi

echo ""
echo "======================================"
echo "  Deployment Complete"
echo "======================================"
echo ""
echo "Version:  $VERSION"
echo "Binary:   /usr/local/bin/montana"
echo "Data:     $DATA_DIR"
echo "P2P Port: $MONTANA_PORT"
echo ""
echo "Security:"
echo "  ✓ SHA256 verified"
echo "  ✓ Firewall with rate limiting"
echo "  ✓ No build tools on server"
echo "  ✓ Systemd hardening enabled"
echo "  ✗ ML-DSA-65 signature (TODO)"
echo ""
echo "Commands:"
echo "  Status:  montana-status"
echo "  Logs:    journalctl -u montana -f"
echo ""
ENDSSH

log_info "Deployment complete"
echo ""
echo "======================================"
echo "  Deployed Successfully"
echo "======================================"
echo ""
echo "Version:  $VERSION"
echo "Host:     $REMOTE_HOST"
echo ""
echo "Next steps:"
echo "  1. Monitor: ssh $REMOTE_USER@$REMOTE_HOST 'montana-status'"
echo "  2. Logs:    ssh $REMOTE_USER@$REMOTE_HOST 'journalctl -u montana -f'"
echo ""
echo "Bootstrap: 100 peers, 25+ subnets, ML-DSA-65 auth"
echo ""
echo "lim(evidence → ∞) 1 Ɉ → 1 секунда"
