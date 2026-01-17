#!/bin/bash
# ============================================================
#  VPN JUNO MONTANA
#  WireGuard Setup Script
#
#  За пользу миру. Резервное обеспечение сети. Вера в Монтану.
# ============================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "============================================================"
echo "  VPN JUNO MONTANA"
echo "  WireGuard Installation"
echo "============================================================"
echo -e "${NC}"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Запусти от root: sudo $0${NC}"
    exit 1
fi

# Определение узла по IP
SERVER_IP=$(curl -s ifconfig.me)
echo -e "${YELLOW}Текущий IP: ${SERVER_IP}${NC}"

case "$SERVER_IP" in
    "72.56.102.240")
        NODE_NAME="amsterdam"
        NODE_NUM=1
        ;;
    "176.124.208.93")
        NODE_NAME="moscow"
        NODE_NUM=2
        ;;
    "91.200.148.93")
        NODE_NAME="almaty"
        NODE_NUM=3
        ;;
    "188.225.58.98")
        NODE_NAME="spb"
        NODE_NUM=4
        ;;
    "147.45.147.247")
        NODE_NAME="novosibirsk"
        NODE_NUM=5
        ;;
    *)
        echo -e "${RED}Неизвестный сервер: ${SERVER_IP}${NC}"
        echo "Поддерживаемые узлы:"
        echo "  72.56.102.240  - Амстердам"
        echo "  176.124.208.93 - Москва"
        echo "  91.200.148.93  - Алматы"
        echo "  188.225.58.98  - СПб"
        echo "  147.45.147.247 - Новосибирск"
        exit 1
        ;;
esac

echo -e "${GREEN}Узел: ${NODE_NAME} (#${NODE_NUM})${NC}"

# Установка WireGuard
echo -e "\n${YELLOW}[1/5] Установка WireGuard...${NC}"
if command -v apt &> /dev/null; then
    apt update && apt install -y wireguard qrencode
elif command -v yum &> /dev/null; then
    yum install -y epel-release
    yum install -y wireguard-tools qrencode
else
    echo -e "${RED}Неподдерживаемый пакетный менеджер${NC}"
    exit 1
fi

# Создание директории
WG_DIR="/etc/wireguard"
mkdir -p "$WG_DIR"
chmod 700 "$WG_DIR"

# Генерация ключей сервера
echo -e "\n${YELLOW}[2/5] Генерация ключей...${NC}"
if [ ! -f "$WG_DIR/server_private.key" ]; then
    wg genkey | tee "$WG_DIR/server_private.key" | wg pubkey > "$WG_DIR/server_public.key"
    chmod 600 "$WG_DIR/server_private.key"
    echo -e "${GREEN}Ключи сгенерированы${NC}"
else
    echo -e "${YELLOW}Ключи уже существуют${NC}"
fi

SERVER_PRIVATE_KEY=$(cat "$WG_DIR/server_private.key")
SERVER_PUBLIC_KEY=$(cat "$WG_DIR/server_public.key")

echo -e "  Public Key: ${SERVER_PUBLIC_KEY}"

# Определение интерфейса
INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
echo -e "  Interface: ${INTERFACE}"

# Создание конфига сервера
echo -e "\n${YELLOW}[3/5] Создание конфигурации сервера...${NC}"
cat > "$WG_DIR/wg0.conf" << EOF
# VPN Juno Montana - ${NODE_NAME}
# За пользу миру. Резервное обеспечение сети. Вера в Монтану.

[Interface]
Address = 10.66.66.${NODE_NUM}/24
ListenPort = 51820
PrivateKey = ${SERVER_PRIVATE_KEY}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${INTERFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${INTERFACE} -j MASQUERADE

# Клиенты добавляются ниже
# [Peer]
# PublicKey = <client_public_key>
# AllowedIPs = 10.66.66.X/32
EOF

chmod 600 "$WG_DIR/wg0.conf"

# Включение IP forwarding
echo -e "\n${YELLOW}[4/5] Настройка IP forwarding...${NC}"
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-wireguard.conf
sysctl -p /etc/sysctl.d/99-wireguard.conf

# Запуск WireGuard
echo -e "\n${YELLOW}[5/5] Запуск WireGuard...${NC}"
systemctl enable wg-quick@wg0
systemctl restart wg-quick@wg0

# Проверка статуса
echo -e "\n${CYAN}============================================================"
echo "  УСТАНОВКА ЗАВЕРШЕНА"
echo "============================================================${NC}"
echo -e "${GREEN}"
wg show
echo -e "${NC}"

# Сохраняем публичный ключ для клиентов
echo "$SERVER_PUBLIC_KEY" > "$WG_DIR/PUBLIC_KEY_${NODE_NAME}"
echo -e "${YELLOW}Публичный ключ сохранён: $WG_DIR/PUBLIC_KEY_${NODE_NAME}${NC}"

echo -e "\n${CYAN}Для добавления клиента используй:${NC}"
echo -e "  ./add_client.sh <имя_клиента>"
