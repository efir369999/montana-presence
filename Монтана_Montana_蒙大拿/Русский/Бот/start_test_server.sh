#!/bin/bash
# Запуск Montana Test Server для iPhone

cd "$(dirname "$0")"

echo "🏔 Montana Test Server"
echo "============================================================"
echo ""

# Проверить Юнону
if [ ! -f "data/agent_registry.json" ]; then
    echo "⚠️  Agent Registry не найден. Регистрирую Юнону..."
    python3 register_junona.py
    echo ""
fi

# Узнать локальный IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')

echo "📱 Доступ с iPhone:"
echo ""
echo "   http://127.0.0.1:5001          (на этом Mac)"
echo "   http://$LOCAL_IP:5001   (из локальной сети)"
echo "   http://127.0.0.1:5001/qr       (QR код)"
echo ""
echo "============================================================"
echo ""
echo "Запуск сервера..."
echo ""

# Запуск Flask
python3 test_iphone_web.py
