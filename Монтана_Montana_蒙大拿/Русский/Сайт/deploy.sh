#!/bin/bash
#
# Deploy сайта на Amsterdam (72.56.102.240)
#

SERVER="root@72.56.102.240"
REMOTE_PATH="/var/www/html"
LOCAL_PATH="$(dirname "$0")"

echo "🏔 Deploying Montana Site to Amsterdam"
echo ""

# Копируем всё
echo "📦 Uploading files..."
scp -r "$LOCAL_PATH/montana_explorer.html" "$SERVER:$REMOTE_PATH/"
scp -r "$LOCAL_PATH/junona" "$SERVER:$REMOTE_PATH/"

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Deployed!"
echo ""
echo "   Explorer: http://72.56.102.240/montana_explorer.html"
echo "   Юнона:    http://72.56.102.240/junona/"
echo ""
echo "🦧 Орангутанг:"
echo "   1. Открой http://72.56.102.240/junona/ в Safari"
echo "   2. Тапни Share → Add to Home Screen"
echo "   3. ВСЁ."
echo "═══════════════════════════════════════════════════"
