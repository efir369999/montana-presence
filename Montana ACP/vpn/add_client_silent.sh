#!/bin/bash
# ============================================================
#  VPN JUNO MONTANA
#  Silent Client Generator (для бота)
#  Выводит только конфиг, без лишнего текста
# ============================================================

CLIENT_NAME="$1"
WG_DIR="/etc/wireguard"
CLIENTS_DIR="$WG_DIR/clients"

if [ -z "$CLIENT_NAME" ]; then
    echo "ERROR: Имя клиента не указано"
    exit 1
fi

if [ ! -f "$WG_DIR/wg0.conf" ]; then
    echo "ERROR: WireGuard не настроен"
    exit 1
fi

# Создание директории
mkdir -p "$CLIENTS_DIR"

# Определение сервера
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null)
SERVER_PUBLIC_KEY=$(cat "$WG_DIR/server_public.key" 2>/dev/null)

if [ -z "$SERVER_PUBLIC_KEY" ]; then
    echo "ERROR: Публичный ключ сервера не найден"
    exit 1
fi

# Проверяем, существует ли уже клиент
if [ -f "$CLIENTS_DIR/${CLIENT_NAME}.conf" ]; then
    # Возвращаем существующий конфиг
    cat "$CLIENTS_DIR/${CLIENT_NAME}.conf"
    exit 0
fi

# Подсчёт клиентов для IP
EXISTING_CLIENTS=$(grep -c "^\[Peer\]" "$WG_DIR/wg0.conf" 2>/dev/null || echo "0")
CLIENT_NUM=$((EXISTING_CLIENTS + 10))
CLIENT_IP="10.66.66.${CLIENT_NUM}"

# Генерация ключей
CLIENT_PRIVATE_KEY=$(wg genkey)
CLIENT_PUBLIC_KEY=$(echo "$CLIENT_PRIVATE_KEY" | wg pubkey)

# Создание конфига клиента
cat > "$CLIENTS_DIR/${CLIENT_NAME}.conf" << EOF
# VPN Juno Montana
# ${CLIENT_NAME}
# $(date +%Y-%m-%d)

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

chmod 600 "$CLIENTS_DIR/${CLIENT_NAME}.conf"

# Добавление peer в сервер
cat >> "$WG_DIR/wg0.conf" << EOF

# ${CLIENT_NAME} - $(date +%Y-%m-%d)
[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_IP}/32
EOF

# Применение конфигурации
wg syncconf wg0 <(wg-quick strip wg0) 2>/dev/null

# Выводим конфиг
cat "$CLIENTS_DIR/${CLIENT_NAME}.conf"
