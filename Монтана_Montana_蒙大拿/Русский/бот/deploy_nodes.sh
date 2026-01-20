#!/bin/bash
# deploy_nodes.sh — Деплой бота на все узлы Montana
#
# Использование:
#   ./deploy_nodes.sh
#
# Скрипт:
# 1. Копирует файлы на все узлы
# 2. Устанавливает MONTANA_NODE_NAME
# 3. Перезапускает сервисы

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ УЗЛОВ
# ═══════════════════════════════════════════════════════════════════════════════

declare -A NODES=(
    ["amsterdam"]="72.56.102.240"
    ["moscow"]="176.124.208.93"
    ["almaty"]="91.200.148.93"
    ["spb"]="188.225.58.98"
    ["novosibirsk"]="147.45.147.247"
)

BOT_DIR="/root/bot"
SSH_USER="root"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Файлы для деплоя
FILES=(
    "junomontanaagibot.py"
    "leader_election.py"
    "junona_ai.py"
    "junona_agents.py"
    "node_crypto.py"
    "time_bank.py"
    "dialogue_coordinator.py"
    "hippocampus.py"
    "junona_rag.py"
    "junona.service"
)

echo "🏔 Montana Protocol — Deploy to all nodes"
echo "=========================================="

for node_name in "${!NODES[@]}"; do
    ip="${NODES[$node_name]}"
    echo ""
    echo "📡 Deploying to $node_name ($ip)..."

    # Копируем файлы
    for file in "${FILES[@]}"; do
        if [ -f "$LOCAL_DIR/$file" ]; then
            scp -q "$LOCAL_DIR/$file" "$SSH_USER@$ip:$BOT_DIR/$file"
            echo "  ✓ $file"
        fi
    done

    # Копируем node_crypto директорию
    if [ -d "$LOCAL_DIR/node_crypto" ]; then
        scp -rq "$LOCAL_DIR/node_crypto" "$SSH_USER@$ip:$BOT_DIR/"
        echo "  ✓ node_crypto/"
    fi

    # Создаём systemd service с правильным NODE_NAME
    ssh "$SSH_USER@$ip" "cat > /etc/systemd/system/junona.service" << EOF
[Unit]
Description=Junona Montana Protocol Bot - $node_name
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BOT_DIR
ExecStart=/usr/bin/python3 junomontanaagibot.py
Environment="MONTANA_NODE_NAME=$node_name"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    echo "  ✓ systemd service (NODE_NAME=$node_name)"

    # Перезапускаем сервис
    ssh "$SSH_USER@$ip" "systemctl daemon-reload && systemctl restart junona"
    echo "  ✓ Service restarted"

    echo "✅ $node_name deployed!"
done

echo ""
echo "=========================================="
echo "🎉 All nodes deployed!"
echo ""
echo "Check status:"
for node_name in "${!NODES[@]}"; do
    ip="${NODES[$node_name]}"
    echo "  ssh $SSH_USER@$ip 'journalctl -u junona -n 20'"
done
