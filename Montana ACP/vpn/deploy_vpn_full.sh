#!/bin/bash
# ============================================================
#  VPN JUNO MONTANA
#  Полное развёртывание на все узлы
#
#  Запускать с сервера, где настроен SSH доступ к узлам
# ============================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
echo "  Полное развёртывание"
echo "============================================================"
echo -e "${NC}"

# Проверяем наличие скриптов
for script in setup_wireguard.sh add_client.sh add_client_silent.sh; do
    if [ ! -f "$SCRIPT_DIR/$script" ]; then
        echo -e "${RED}Ошибка: $SCRIPT_DIR/$script не найден${NC}"
        exit 1
    fi
done

echo -e "${GREEN}Скрипты найдены${NC}"

# Развёртывание на каждый узел
for i in "${!NODES[@]}"; do
    NODE="${NODES[$i]}"
    NAME="${NODE_NAMES[$i]}"

    echo -e "\n${YELLOW}[$((i+1))/5] ${NAME} (${NODE})${NC}"

    # Проверяем доступность
    echo -e "  Проверка доступности..."
    if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@${NODE}" "echo ok" >/dev/null 2>&1; then
        echo -e "  ${RED}Недоступен, пропускаю${NC}"
        continue
    fi

    # Копируем скрипты
    echo -e "  Копирование скриптов..."
    scp -q "$SCRIPT_DIR/setup_wireguard.sh" "root@${NODE}:/tmp/"
    scp -q "$SCRIPT_DIR/add_client.sh" "root@${NODE}:/tmp/"
    scp -q "$SCRIPT_DIR/add_client_silent.sh" "root@${NODE}:/tmp/"

    # Проверяем, установлен ли WireGuard
    WG_INSTALLED=$(ssh "root@${NODE}" "command -v wg >/dev/null && echo yes || echo no")

    if [ "$WG_INSTALLED" = "no" ]; then
        echo -e "  Установка WireGuard..."
        ssh "root@${NODE}" "chmod +x /tmp/setup_wireguard.sh && /tmp/setup_wireguard.sh"
    else
        echo -e "  WireGuard уже установлен"
    fi

    # Копируем скрипты в постоянное место
    echo -e "  Установка скриптов в /etc/wireguard/..."
    ssh "root@${NODE}" "
        cp /tmp/add_client.sh /etc/wireguard/
        cp /tmp/add_client_silent.sh /etc/wireguard/
        chmod +x /etc/wireguard/add_client.sh
        chmod +x /etc/wireguard/add_client_silent.sh
    "

    echo -e "  ${GREEN}✓ Готово${NC}"
done

echo -e "\n${CYAN}============================================================"
echo "  РАЗВЁРТЫВАНИЕ ЗАВЕРШЕНО"
echo "============================================================${NC}"

# Показываем статус узлов
echo -e "\n${YELLOW}Статус узлов:${NC}"
for i in "${!NODES[@]}"; do
    NODE="${NODES[$i]}"
    NAME="${NODE_NAMES[$i]}"

    STATUS=$(ssh -o ConnectTimeout=5 "root@${NODE}" "wg show wg0 2>/dev/null | head -1 || echo 'OFFLINE'" 2>/dev/null || echo "UNREACHABLE")

    if [[ "$STATUS" == *"interface"* ]]; then
        echo -e "  ${GREEN}✓${NC} ${NAME}: VPN активен"
    elif [[ "$STATUS" == "OFFLINE" ]]; then
        echo -e "  ${YELLOW}○${NC} ${NAME}: WireGuard не запущен"
    else
        echo -e "  ${RED}✗${NC} ${NAME}: недоступен"
    fi
done

echo -e "\n${GREEN}VPN Juno Montana готов!${NC}"
echo -e "Для теста через бота: /vpn 1"
echo -e "\n_За пользу миру. Резервное обеспечение сети. Вера в Монтану._"
echo -e "bc1qrezesm4qd9qyxtg2x7agdvzn94rwgsee8x77gw"
