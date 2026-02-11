#!/bin/bash
# deploy_nodes.sh — Rolling Deploy бота на все узлы Montana
#
# ZERO-DOWNTIME DEPLOYMENT:
# 1. Обновляем узлы по одному (rolling)
# 2. Ждём 20 сек между узлами (failover time)
# 3. Проверяем здоровье после каждого деплоя
# 4. Если узел недоступен — пропускаем, не ломаем остальных
#
# Использование:
#   ./deploy_nodes.sh           — rolling deploy (по одному)
#   ./deploy_nodes.sh --fast    — быстрый deploy (все сразу, ОПАСНО)
#   ./deploy_nodes.sh --node moscow  — deploy только на один узел

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# ЦВЕТА
# ═══════════════════════════════════════════════════════════════════════════════
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════
ROLLING_DELAY=20  # Секунд между узлами (время на failover)
HEALTH_CHECK_DELAY=5  # Секунд ожидания перед health check

NODE_NAMES="amsterdam moscow almaty spb novosibirsk"
NODE_IPS="72.56.102.240 176.124.208.93 91.200.148.93 188.225.58.98 147.45.147.247"

BOT_DIR="/root/bot"
SSH_USER="root"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Файлы для деплоя
FILES="junomontanaagibot.py montana_api.py leader_election.py junona_ai.py junona_agents.py node_crypto.py time_bank.py timechain.py dialogue_coordinator.py hippocampus.py junona_rag.py breathing_sync.py contracts.py council_voting.py montana_db.py sms_gateway.py webrtc_signaling.py wallet_wizard.py event_ledger.py requirements.txt junona.service"

# ═══════════════════════════════════════════════════════════════════════════════
# ПАРСИНГ АРГУМЕНТОВ
# ═══════════════════════════════════════════════════════════════════════════════
FAST_MODE=false
SINGLE_NODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            FAST_MODE=true
            shift
            ;;
        --node)
            SINGLE_NODE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# ЗАГРУЗКА КЛЮЧЕЙ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}🔧 Configuring SSH & Keys...${NC}"

# SSH ключи из Keychain (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  🍏 macOS: loading keys from Keychain..."
    ssh-add --apple-load-keychain 2>/dev/null || ssh-add -A 2>/dev/null || true
fi

# Функция для чтения из keychain
get_key() {
    local env_name="$1"
    eval "val=\$$env_name"
    if [ -n "$val" ]; then echo "$val"; return; fi
    if command -v security >/dev/null; then
        val=$(security find-generic-password -a "montana" -s "$env_name" -w 2>/dev/null || echo "")
        if [ -n "$val" ]; then echo "$val"; return; fi
    fi
    echo ""
}

TELEGRAM_TOKEN=$(get_key "TELEGRAM_TOKEN_JUNONA")
OPENAI_KEY=$(get_key "OPENAI_API_KEY")

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo -e "${RED}❌ Error: TELEGRAM_TOKEN_JUNONA not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Keys loaded${NC}"

# ═══════════════════════════════════════════════════════════════════════════════
# ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

# Проверка доступности узла
check_node() {
    local ip="$1"
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_USER@$ip" "echo ok" >/dev/null 2>&1
}

# Проверка здоровья бота на узле
health_check() {
    local ip="$1"
    local status=$(ssh -o ConnectTimeout=10 "$SSH_USER@$ip" "systemctl is-active junona 2>/dev/null || echo 'inactive'")
    if [ "$status" = "active" ]; then
        return 0
    fi
    return 1
}

# Деплой на один узел
deploy_node() {
    local node_name="$1"
    local ip="$2"

    echo -e "\n${BLUE}📡 Deploying to $node_name ($ip)...${NC}"

    # Проверяем доступность
    if ! check_node "$ip"; then
        echo -e "  ${YELLOW}⚠️ SKIP: $node_name unreachable${NC}"
        return 1
    fi

    # Создаём директорию
    ssh "$SSH_USER@$ip" "mkdir -p $BOT_DIR $BOT_DIR/data $BOT_DIR/node_crypto"

    # Копируем файлы
    for file in $FILES; do
        if [ -f "$LOCAL_DIR/$file" ]; then
            scp -q "$LOCAL_DIR/$file" "$SSH_USER@$ip:$BOT_DIR/$file"
            echo -e "  ${GREEN}✓${NC} $file"
        fi
    done

    # Копируем директории
    if [ -d "$LOCAL_DIR/node_crypto" ]; then
        scp -rq "$LOCAL_DIR/node_crypto" "$SSH_USER@$ip:$BOT_DIR/"
        echo -e "  ${GREEN}✓${NC} node_crypto/"
    fi

    # Создаём systemd service с правильным NODE_NAME
    ssh "$SSH_USER@$ip" "cat > /etc/systemd/system/junona.service" << EOF
[Unit]
Description=Junona Montana Protocol Bot - $node_name
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=$BOT_DIR
ExecStart=/usr/bin/python3 -u junomontanaagibot.py
Environment="MONTANA_NODE_NAME=$node_name"
Environment="TELEGRAM_TOKEN_JUNONA=$TELEGRAM_TOKEN"
Environment="OPENAI_API_KEY=$OPENAI_KEY"
Environment="PYTHONUNBUFFERED=1"
WatchdogSec=60
Restart=always
RestartSec=15
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM
MemoryMax=512M
MemoryHigh=400M
StandardOutput=journal
StandardError=journal
SyslogIdentifier=junona

[Install]
WantedBy=multi-user.target
EOF
    echo -e "  ${GREEN}✓${NC} systemd service (NODE_NAME=$node_name)"

    # Перезапускаем сервис
    ssh "$SSH_USER@$ip" "systemctl daemon-reload && systemctl enable junona && systemctl restart junona"
    echo -e "  ${GREEN}✓${NC} Service restarted"

    # Ждём и проверяем здоровье
    echo -e "  ⏳ Waiting ${HEALTH_CHECK_DELAY}s for health check..."
    sleep $HEALTH_CHECK_DELAY

    if health_check "$ip"; then
        echo -e "${GREEN}✅ $node_name deployed & healthy!${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ $node_name deployed but health check failed${NC}"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "\n${BLUE}🏔 Montana Protocol — Deploy${NC}"
echo "=========================================="

if [ "$FAST_MODE" = true ]; then
    echo -e "${YELLOW}⚠️ FAST MODE: deploying all nodes simultaneously${NC}"
    echo -e "${YELLOW}   This may cause brief downtime!${NC}"
else
    echo -e "${GREEN}🔄 ROLLING MODE: deploying one node at a time${NC}"
    echo -e "   Delay between nodes: ${ROLLING_DELAY}s"
fi
echo ""

# Конвертируем в массивы
names_arr=($NODE_NAMES)
ips_arr=($NODE_IPS)

deployed=0
failed=0

for i in "${!names_arr[@]}"; do
    node_name="${names_arr[$i]}"
    ip="${ips_arr[$i]}"

    # Если указан конкретный узел — деплоим только его
    if [ -n "$SINGLE_NODE" ] && [ "$SINGLE_NODE" != "$node_name" ]; then
        continue
    fi

    if deploy_node "$node_name" "$ip"; then
        ((deployed++))
    else
        ((failed++))
    fi

    # Rolling delay (кроме последнего узла и fast mode)
    if [ "$FAST_MODE" = false ] && [ $i -lt $((${#names_arr[@]} - 1)) ]; then
        echo -e "\n${BLUE}⏳ Waiting ${ROLLING_DELAY}s before next node (failover time)...${NC}"
        sleep $ROLLING_DELAY
    fi
done

# ═══════════════════════════════════════════════════════════════════════════════
# РЕЗУЛЬТАТ
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "=========================================="
if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 Deploy complete! $deployed/$((deployed + failed)) nodes updated${NC}"
else
    echo -e "${YELLOW}⚠️ Deploy finished with issues: $deployed success, $failed failed${NC}"
fi

echo ""
echo "Check logs:"
for i in "${!names_arr[@]}"; do
    node_name="${names_arr[$i]}"
    ip="${ips_arr[$i]}"
    echo "  ssh $SSH_USER@$ip 'journalctl -u junona -n 20 --no-pager'"
done

echo ""
echo "Health check:"
for i in "${!names_arr[@]}"; do
    node_name="${names_arr[$i]}"
    ip="${ips_arr[$i]}"
    if check_node "$ip"; then
        if health_check "$ip"; then
            echo -e "  ${GREEN}🟢${NC} $node_name ($ip) — active"
        else
            echo -e "  ${YELLOW}🟡${NC} $node_name ($ip) — inactive"
        fi
    else
        echo -e "  ${RED}🔴${NC} $node_name ($ip) — unreachable"
    fi
done
