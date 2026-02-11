#!/bin/bash
# MontanaSign Deployment
# montana.network/install

set -e

echo "🏔 MontanaSign — Deployment"
echo "==========================="

# Устанавливаем зависимости
apt update
apt install -y python3 python3-pip nginx certbot python3-certbot-nginx

# zsign для подписи IPA
if ! command -v zsign &> /dev/null; then
    echo "📦 Installing zsign..."
    git clone https://github.com/AdenKenny/zsign.git /tmp/zsign
    cd /tmp/zsign
    g++ *.cpp common/*.cpp -lcrypto -lzip -o zsign -O3
    mv zsign /usr/local/bin/
    cd -
fi

# Python зависимости
pip3 install flask flask-cors gunicorn

# Создаём директории
mkdir -p /var/montana/{ipa,signed,certs}

# Копируем сервер
cp server.py /var/montana/

# Systemd service
cat > /etc/systemd/system/montanasign.service << 'EOF'
[Unit]
Description=MontanaSign iOS Distribution
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/montana
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:8080 server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Nginx config
cat > /etc/nginx/sites-available/montanasign << 'EOF'
server {
    listen 80;
    server_name install.montana.network;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # IPA downloads - большие файлы
    location /api/download {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
        client_max_body_size 500M;
    }

    # Статика (иконки)
    location /static {
        alias /var/montana/static;
    }
}
EOF

ln -sf /etc/nginx/sites-available/montanasign /etc/nginx/sites-enabled/

# SSL
certbot --nginx -d install.montana.network --non-interactive --agree-tos -m admin@montana.network

# Запуск
systemctl daemon-reload
systemctl enable montanasign
systemctl restart montanasign
systemctl restart nginx

echo ""
echo "✅ MontanaSign deployed!"
echo ""
echo "🌐 https://install.montana.network"
echo ""
echo "Next steps:"
echo "1. Загрузи IPA файлы в /var/montana/ipa/"
echo "2. Добавь сертификат в /var/montana/certs/montana.p12"
echo "3. Для каждого UDID нужен .mobileprovision"
echo ""
echo "Или используй Enterprise сертификат для всех устройств"
