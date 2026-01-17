#!/bin/bash
# ============================================================
#  VPN JUNO MONTANA
#  Deploy to All Nodes
# ============================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Узлы сети Montana
NODES=(
    "72.56.102.240"    # Амстердам
    "176.124.208.93"   # Москва
    "91.200.148.93"    # Алматы
    "188.225.58.98"    # СПб
    "147.45.147.247"   # Новосибирск
)

NODE_NAMES=(
    "Амстердам"
    "Москва"
    "Алматы"
    "СПб"
    "Новосибирск"
)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${CYAN}"
echo "============================================================"
echo "  VPN JUNO MONTANA"
echo "  Развёртывание на все узлы"
echo "============================================================"
echo -e "${NC}"

# Копирование и запуск на каждом узле
for i in "${!NODES[@]}"; do
    NODE="${NODES[$i]}"
    NAME="${NODE_NAMES[$i]}"

    echo -e "\n${YELLOW}[$((i+1))/5] ${NAME} (${NODE})${NC}"

    # Копируем скрипты
    echo "  Копирование скриптов..."
    scp -q "$SCRIPT_DIR/setup_wireguard.sh" "root@${NODE}:/tmp/"
    scp -q "$SCRIPT_DIR/add_client.sh" "root@${NODE}:/tmp/"

    # Запускаем установку
    echo "  Запуск установки..."
    ssh "root@${NODE}" "chmod +x /tmp/setup_wireguard.sh && /tmp/setup_wireguard.sh"

    # Копируем add_client в постоянное место
    ssh "root@${NODE}" "cp /tmp/add_client.sh /etc/wireguard/ && chmod +x /etc/wireguard/add_client.sh"

    echo -e "  ${GREEN}Готово${NC}"
done

echo -e "\n${CYAN}============================================================"
echo "  РАЗВЁРТЫВАНИЕ ЗАВЕРШЕНО"
echo "============================================================${NC}"

# Собираем публичные ключи
echo -e "\n${YELLOW}Публичные ключи узлов:${NC}"
for i in "${!NODES[@]}"; do
    NODE="${NODES[$i]}"
    NAME="${NODE_NAMES[$i]}"
    PUB_KEY=$(ssh "root@${NODE}" "cat /etc/wireguard/server_public.key" 2>/dev/null || echo "N/A")
    echo "  ${NAME}: ${PUB_KEY}"
done

echo -e "\n${GREEN}VPN Juno Montana готов к работе!${NC}"
echo "Для добавления клиента на любом узле:"
echo "  ssh root@<node_ip> '/etc/wireguard/add_client.sh <имя>'"
