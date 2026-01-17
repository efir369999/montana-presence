#!/bin/bash
# ============================================================
#  VPN JUNO MONTANA
#  Add Client Script
# ============================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}Использование: $0 <имя_клиента>${NC}"
    echo "Пример: $0 iphone_alik"
    exit 1
fi

CLIENT_NAME="$1"
WG_DIR="/etc/wireguard"
CLIENTS_DIR="$WG_DIR/clients"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Запусти от root: sudo $0 $1${NC}"
    exit 1
fi

# Создание директории для клиентов
mkdir -p "$CLIENTS_DIR"

# Определение узла
SERVER_IP=$(curl -s ifconfig.me)
case "$SERVER_IP" in
    "72.56.102.240") NODE_NAME="amsterdam"; NODE_NUM=1 ;;
    "176.124.208.93") NODE_NAME="moscow"; NODE_NUM=2 ;;
    "91.200.148.93") NODE_NAME="almaty"; NODE_NUM=3 ;;
    "188.225.58.98") NODE_NAME="spb"; NODE_NUM=4 ;;
    "147.45.147.247") NODE_NAME="novosibirsk"; NODE_NUM=5 ;;
    *) echo -e "${RED}Неизвестный сервер${NC}"; exit 1 ;;
esac

echo -e "${CYAN}"
echo "============================================================"
echo "  VPN JUNO MONTANA"
echo "  Добавление клиента: ${CLIENT_NAME}"
echo "  Узел: ${NODE_NAME}"
echo "============================================================"
echo -e "${NC}"

# Подсчёт существующих клиентов для определения IP
EXISTING_CLIENTS=$(grep -c "^\[Peer\]" "$WG_DIR/wg0.conf" 2>/dev/null || echo "0")
CLIENT_NUM=$((EXISTING_CLIENTS + 10))  # Клиенты начинаются с .10
CLIENT_IP="10.66.66.${CLIENT_NUM}"

echo -e "${YELLOW}IP клиента: ${CLIENT_IP}${NC}"

# Генерация ключей клиента
echo -e "\n${YELLOW}Генерация ключей клиента...${NC}"
CLIENT_PRIVATE_KEY=$(wg genkey)
CLIENT_PUBLIC_KEY=$(echo "$CLIENT_PRIVATE_KEY" | wg pubkey)

# Чтение публичного ключа сервера
SERVER_PUBLIC_KEY=$(cat "$WG_DIR/server_public.key")

# Создание конфига клиента
CLIENT_CONF="$CLIENTS_DIR/${CLIENT_NAME}.conf"
cat > "$CLIENT_CONF" << EOF
# VPN Juno Montana
# Клиент: ${CLIENT_NAME}
# Узел: ${NODE_NAME} (${SERVER_IP})
#
# За пользу миру. Резервное обеспечение сети. Вера в Монтану.
# bc1qrezesm4qd9qyxtg2x7agdvzn94rwgsee8x77gw

[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_IP}/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_IP}:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

chmod 600 "$CLIENT_CONF"

# Добавление peer в серверный конфиг
echo -e "\n${YELLOW}Добавление клиента в сервер...${NC}"
cat >> "$WG_DIR/wg0.conf" << EOF

# ${CLIENT_NAME} - $(date +%Y-%m-%d)
[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_IP}/32
EOF

# Применение конфигурации
wg syncconf wg0 <(wg-quick strip wg0)

echo -e "\n${GREEN}============================================================"
echo "  КЛИЕНТ ДОБАВЛЕН"
echo "============================================================${NC}"
echo -e "Конфиг: ${CLIENT_CONF}"
echo ""

# Генерация QR-кода
echo -e "${CYAN}QR-код для мобильного приложения WireGuard:${NC}"
echo ""
qrencode -t ansiutf8 < "$CLIENT_CONF"
echo ""

# Сохраняем QR как PNG
qrencode -o "$CLIENTS_DIR/${CLIENT_NAME}_qr.png" < "$CLIENT_CONF"
echo -e "${YELLOW}QR сохранён: $CLIENTS_DIR/${CLIENT_NAME}_qr.png${NC}"

echo -e "\n${CYAN}Конфигурация клиента:${NC}"
echo "----------------------------------------"
cat "$CLIENT_CONF"
echo "----------------------------------------"
