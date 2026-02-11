#!/bin/bash
#
# Deploy Юнона AI API на Amsterdam (72.56.102.240)
#

SERVER="root@72.56.102.240"
LOCAL_PATH="$(dirname "$0")"

echo "🤖 Deploying Юнона AI API"
echo ""

# 1. Создаём директорию на сервере
echo "📁 Creating /opt/junona..."
ssh $SERVER "mkdir -p /opt/junona"

# 2. Копируем API
echo "📦 Uploading API..."
scp "$LOCAL_PATH/junona_api.py" "$SERVER:/opt/junona/"
scp "$LOCAL_PATH/junona_api.service" "$SERVER:/etc/systemd/system/"

# 3. Копируем фронтенд
echo "📦 Uploading frontend..."
scp "$LOCAL_PATH/junona/index.html" "$SERVER:/var/www/html/"
scp "$LOCAL_PATH/junona/manifest.json" "$SERVER:/var/www/html/"
scp "$LOCAL_PATH/junona/sw.js" "$SERVER:/var/www/html/"

# 4. Устанавливаем зависимости
echo "📦 Installing dependencies..."
ssh $SERVER "pip3 install flask flask-cors --quiet"

# 5. Настраиваем nginx
echo "⚙️ Configuring nginx..."
ssh $SERVER 'cat > /etc/nginx/sites-available/default << "EOF"
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/html;
    index index.html;

    server_name _;

    # Frontend
    location / {
        try_files $uri $uri/ =404;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }
}
EOF'

# 6. Перезагружаем nginx
ssh $SERVER "nginx -t && systemctl reload nginx"

# 7. Проверяем .env
ssh $SERVER 'if [ ! -f /opt/junona/.env ]; then
    echo "OPENAI_API_KEY=" > /opt/junona/.env
    echo "ANTHROPIC_API_KEY=" >> /opt/junona/.env
    echo "⚠️  .env создан — добавь ключи!"
fi'

# 8. Запускаем сервис
echo "🚀 Starting API service..."
ssh $SERVER "systemctl daemon-reload && systemctl enable junona_api && systemctl restart junona_api"

# 9. Проверяем статус
echo ""
echo "═══════════════════════════════════════════════════"
ssh $SERVER "systemctl status junona_api --no-pager | head -10"
echo "═══════════════════════════════════════════════════"
echo ""
echo "✅ Deployed!"
echo ""
echo "   Юнона: http://72.56.102.240/"
echo "   API:   http://72.56.102.240/api/health"
echo ""
echo "⚠️  Если ключи не настроены:"
echo "   ssh root@72.56.102.240"
echo "   nano /opt/junona/.env"
echo "   # Добавь:"
echo "   # OPENAI_API_KEY=sk-..."
echo "   # ANTHROPIC_API_KEY=sk-ant-..."
echo "   systemctl restart junona_api"
echo ""
