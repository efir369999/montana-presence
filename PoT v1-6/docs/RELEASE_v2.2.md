# Proof of Time v2.2.0 — Pantheon Dashboard Release

**Release Date:** December 28, 2025

---

## Overview

Version 2.2 adds the **Pantheon Dashboard** — a web-based audit interface displaying all 12 protocol gods and complete Adonis reputation data.

---

## New Features

### Pantheon Dashboard

Real-time web dashboard with 5 sections:

| Section | Content |
|---------|---------|
| **12 Gods** | All Pantheon modules with status |
| **Adonis** | Reputation statistics and dimensions |
| **Geography** | City distribution and diversity |
| **Nodes** | Top nodes by reputation |
| **Events** | Real-time event timeline |

### The 12 Gods

| # | God | Domain | Status |
|---|-----|--------|--------|
| 1 | Chronos | Time / VDF | Active |
| 2 | Adonis | Reputation | Active |
| 3 | Hermes | Network / P2P | Active |
| 4 | Hades | Storage | Active |
| 5 | Athena | Consensus | Active |
| 6 | Prometheus | Cryptography | Active |
| 7 | Mnemosyne | Memory / Cache | Active |
| 8 | Plutus | Wallet | Active |
| 9 | Nyx | Privacy | Limited |
| 10 | Themis | Validation | Active |
| 11 | Iris | API / RPC | Active |
| 12 | Ananke | Governance | Planned |

### Dashboard Features

- Dark theme UI
- Auto-refresh every 10 seconds
- REST API endpoints
- Demo mode with sample data
- Mobile-responsive design

---

## Quick Start

### Local Development

```bash
# Clone and run
git clone https://github.com/afgrouptime/proofoftime.git
cd proofoftime
python pantheon_dashboard.py --demo --port 8080
```

Open http://localhost:8080

### Production Server

```bash
# Install dependencies
pip install pynacl

# Run dashboard (background)
nohup python pantheon_dashboard.py --host 0.0.0.0 --port 8080 > dashboard.log 2>&1 &

# Or with systemd (recommended)
sudo systemctl start pot-dashboard
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard HTML |
| `GET /api/gods` | All 12 Pantheon gods |
| `GET /api/overview` | Adonis statistics |
| `GET /api/dimensions` | Dimension averages |
| `GET /api/cities` | Geographic distribution |
| `GET /api/top?limit=20` | Top nodes |
| `GET /api/events?limit=50` | Recent events |

---

## File Changes

### New Files
- `pantheon_dashboard.py` — Web dashboard server (+973 lines)
- `docs/RELEASE_v2.2.md` — This document

### Summary
- v2.0.0: Pantheon naming + Adonis reputation
- v2.1.0: Geographic diversity + Testnet
- v2.2.0: Pantheon Dashboard (this release)

---

## Server Deployment

### Option 1: Direct Run

```bash
# Foreground
python pantheon_dashboard.py --host 0.0.0.0 --port 8080

# Background
nohup python pantheon_dashboard.py --host 0.0.0.0 --port 8080 > /var/log/pot-dashboard.log 2>&1 &
```

### Option 2: Systemd Service

```bash
# Create service file
sudo tee /etc/systemd/system/pot-dashboard.service << 'EOF'
[Unit]
Description=Proof of Time Pantheon Dashboard
After=network.target

[Service]
Type=simple
User=pot
WorkingDirectory=/opt/proofoftime
ExecStart=/usr/bin/python3 pantheon_dashboard.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable pot-dashboard
sudo systemctl start pot-dashboard
sudo systemctl status pot-dashboard
```

### Option 3: Docker

```bash
docker run -d \
  --name pot-dashboard \
  -p 8080:8080 \
  -v $(pwd):/app \
  python:3.11-slim \
  python /app/pantheon_dashboard.py --host 0.0.0.0 --port 8080
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name dashboard.proofoftime.org;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Python files | 20 |
| Lines of code | ~17,500 |
| Pantheon gods | 12 |
| Dashboard sections | 5 |
| API endpoints | 7 |

---

*Time is the ultimate proof. The gods are watching.*
