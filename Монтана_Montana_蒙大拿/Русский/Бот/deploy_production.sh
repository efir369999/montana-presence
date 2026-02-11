#!/bin/bash
# Montana Protocol — Production Deployment Script
# Deploys to all 3 nodes: Amsterdam, Moscow, Almaty

set -e

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BOT_DIR"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           MONTANA PROTOCOL — PRODUCTION DEPLOYMENT            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

# Load SSH key from keychain
PASS_HEX=$(security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w 2>/dev/null || echo "")
if [ -z "$PASS_HEX" ]; then
    echo "❌ SSH passphrase not found in keychain"
    exit 1
fi
PASS=$(echo "$PASS_HEX" | xxd -r -p)

# Prepare SSH key
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PRIVATE" -w 2>/dev/null | base64 -d > /tmp/jn_srv
chmod 600 /tmp/jn_srv

deploy_to_node() {
    local NODE_NAME=$1
    local NODE_IP=$2

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Deploying to $NODE_NAME ($NODE_IP)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Create directory
    expect -c "
    spawn ssh -i /tmp/jn_srv -o StrictHostKeyChecking=no root@$NODE_IP \"mkdir -p /root/montana/data\"
    expect {
        \"passphrase\" { send \"$PASS\r\"; exp_continue }
        eof
    }
    " 2>/dev/null

    # Copy core files
    for FILE in montana_api.py montana_db.py node_crypto.py node_kem.py node_tls.py time_bank.py timechain.py time_ledger.py event_ledger.py breathing_sync.py leader_election.py nts_sync.py distributed_registry.py council_voting.py requirements.txt; do
        if [ -f "$FILE" ]; then
            echo "   📄 $FILE"
            expect -c "
            spawn scp -i /tmp/jn_srv -o StrictHostKeyChecking=no $FILE root@$NODE_IP:/root/montana/
            expect {
                \"passphrase\" { send \"$PASS\r\"; exp_continue }
                eof
            }
            " 2>/dev/null
        fi
    done

    # Create systemd service with correct NODE_ID
    cat > /tmp/montana_$NODE_NAME.service << EOF
[Unit]
Description=Montana Protocol API ($NODE_NAME)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/montana
ExecStart=/usr/bin/python3 /root/montana/montana_api.py
Restart=always
RestartSec=5
Environment=NODE_ID=$NODE_NAME
Environment=PORT=8889
Environment=HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

    # Copy service file
    expect -c "
    spawn scp -i /tmp/jn_srv -o StrictHostKeyChecking=no /tmp/montana_$NODE_NAME.service root@$NODE_IP:/root/montana/montana.service
    expect {
        \"passphrase\" { send \"$PASS\r\"; exp_continue }
        eof
    }
    " 2>/dev/null

    # Install and start service
    expect -c "
    spawn ssh -i /tmp/jn_srv -o StrictHostKeyChecking=no root@$NODE_IP \"
        cp /root/montana/montana.service /etc/systemd/system/montana.service
        systemctl daemon-reload
        systemctl enable montana
        pip3 install flask flask-cors dilithium_py -q 2>/dev/null || pip install flask flask-cors dilithium_py -q
        systemctl restart montana
        sleep 2
        systemctl is-active montana && echo SERVICE_OK || echo SERVICE_FAILED
    \"
    expect {
        \"passphrase\" { send \"$PASS\r\"; exp_continue }
        eof
    }
    " 2>/dev/null

    rm -f /tmp/montana_$NODE_NAME.service
    echo "✅ $NODE_NAME deployed"
}

# Deploy to all nodes
deploy_to_node "amsterdam" "72.56.102.240"
deploy_to_node "moscow" "176.124.208.93"
deploy_to_node "almaty" "91.200.148.93"

# Cleanup
rm -f /tmp/jn_srv

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT COMPLETE                        ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Amsterdam: http://72.56.102.240:8889/api/health              ║"
echo "║  Moscow:    http://176.124.208.93:8889/api/health             ║"
echo "║  Almaty:    http://91.200.148.93:8889/api/health              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

# Verify nodes
echo ""
echo "🔍 Verifying nodes..."
sleep 3
for IP in 72.56.102.240 176.124.208.93 91.200.148.93; do
    RESULT=$(curl -s --connect-timeout 5 "http://$IP:8889/api/health" 2>/dev/null || echo "FAILED")
    echo "   $IP: $RESULT"
done
