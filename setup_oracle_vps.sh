#!/usr/bin/env bash
# ==============================================================================
# Linework AI - Oracle Cloud VPS 1-Click Production Setup Script
# Ubuntu 22.04 / 24.04 LTS (x86_64 or ARM64 Ampere A1)
# ==============================================================================
set -e

echo "=================================================================="
echo "  Starting Linework AI High-Performance Production Setup..."
echo "=================================================================="

# 1. Update system packages
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-pip python3-venv git curl ufw \
    libglib2.0-0 libgomp1 libfontconfig1 potrace librsvg2-bin libvips \
    nginx certbot python3-certbot-nginx

# 2. Configure Firewall (UFW)
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# 3. Clone Repository
APP_DIR="/opt/linework"
if [ -d "$APP_DIR" ]; then
    echo "[+] Updating existing repository in $APP_DIR..."
    cd "$APP_DIR" && sudo git pull origin main
else
    echo "[+] Cloning repository to $APP_DIR..."
    sudo git clone https://github.com/khanezaz566-code/linework-saas.git "$APP_DIR"
    sudo chown -R $USER:$USER "$APP_DIR"
fi

cd "$APP_DIR"

# 4. Create Python Virtual Environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Environment configuration with permanent Supabase Cloud PostgreSQL
cat << 'EOF' > .env
DATABASE_URL=postgresql://postgres.aqilhnaqytvgdaqxobmn:ezaz%40566%40%3F%3F@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres
LINEWORK_WORKERS=4
LINEWORK_INLINE=1
PORT=8000
HOST=127.0.0.1
RELOAD=0
EOF

# 6. Create Systemd Daemon Service
sudo bash -c "cat << 'EOF' > /etc/systemd/system/linework.service
[Unit]
Description=Linework AI SaaS Production Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable linework
sudo systemctl restart linework

# 7. Configure Nginx Reverse Proxy
sudo bash -c "cat << 'EOF' > /etc/nginx/sites-available/linework
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF"

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/linework /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

echo "=================================================================="
echo "  🎉 LINEWORK AI ORACLE CLOUD SERVER IS NOW FULLY LIVE!"
echo "  Check status: sudo systemctl status linework"
echo "  Access URL  : http://$(curl -s ifconfig.me)"
echo "=================================================================="
