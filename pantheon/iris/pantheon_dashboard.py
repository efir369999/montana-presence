#!/usr/bin/env python3
"""
Pantheon + Adonis Audit Dashboard

Web-based dashboard showing:
- All 12 Pantheon gods (protocol modules)
- Adonis reputation data
- Geographic diversity
- Network statistics

Usage:
    python pantheon_dashboard.py [--port 8080] [--demo]
"""

import json
import time
import argparse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional

from pantheon.adonis import (
    AdonisEngine, ReputationDimension, ReputationEvent
)

logger = logging.getLogger("pantheon_dashboard")

# ============================================================================
# PANTHEON GODS DATA
# ============================================================================

PANTHEON_GODS = [
    {
        "id": 1,
        "name": "Chronos",
        "domain": "Time / VDF",
        "symbol": "hourglass",
        "color": "#FFD700",
        "description": "Sequential time proofs via Verifiable Delay Functions",
        "module": "crypto.WesolowskiVDF",
        "status": "active"
    },
    {
        "id": 2,
        "name": "Adonis",
        "domain": "Reputation",
        "symbol": "star",
        "color": "#FF69B4",
        "description": "Multi-dimensional trust scoring with 6 dimensions",
        "module": "adonis.AdonisEngine",
        "status": "active"
    },
    {
        "id": 3,
        "name": "Hermes",
        "domain": "Network / P2P",
        "symbol": "network",
        "color": "#00CED1",
        "description": "Peer-to-peer message relay with Noise Protocol",
        "module": "network.P2PNode",
        "status": "active"
    },
    {
        "id": 4,
        "name": "Hades",
        "domain": "Storage",
        "symbol": "database",
        "color": "#4B0082",
        "description": "Persistent blockchain and DAG storage",
        "module": "database.BlockchainDB",
        "status": "active"
    },
    {
        "id": 5,
        "name": "Athena",
        "domain": "Consensus",
        "symbol": "scale",
        "color": "#9370DB",
        "description": "Leader selection via VRF with probability weights",
        "module": "consensus.ConsensusCalculator",
        "status": "active"
    },
    {
        "id": 6,
        "name": "Prometheus",
        "domain": "Cryptography",
        "symbol": "fire",
        "color": "#FF4500",
        "description": "VRF, VDF, signatures, and proof generation",
        "module": "crypto.ECVRF",
        "status": "active"
    },
    {
        "id": 7,
        "name": "Mnemosyne",
        "domain": "Memory / Cache",
        "symbol": "brain",
        "color": "#20B2AA",
        "description": "Transaction pool and mempool management",
        "module": "mempool.Mempool",
        "status": "active"
    },
    {
        "id": 8,
        "name": "Plutus",
        "domain": "Wallet",
        "symbol": "wallet",
        "color": "#32CD32",
        "description": "Key management and transaction signing",
        "module": "wallet.Wallet",
        "status": "active"
    },
    {
        "id": 9,
        "name": "Nyx",
        "domain": "Privacy",
        "symbol": "moon",
        "color": "#191970",
        "description": "Stealth addresses, ring signatures, confidential TX",
        "module": "privacy.PrivacyEngine",
        "status": "limited"
    },
    {
        "id": 10,
        "name": "Themis",
        "domain": "Validation",
        "symbol": "check",
        "color": "#DC143C",
        "description": "Block and transaction rule enforcement",
        "module": "validation.Validator",
        "status": "active"
    },
    {
        "id": 11,
        "name": "Iris",
        "domain": "API / RPC",
        "symbol": "api",
        "color": "#FF1493",
        "description": "External JSON-RPC interface",
        "module": "rpc.RPCServer",
        "status": "active"
    },
    {
        "id": 12,
        "name": "Ananke",
        "domain": "Governance",
        "symbol": "vote",
        "color": "#8B4513",
        "description": "Protocol upgrades and parameter changes",
        "module": "governance.GovernanceEngine",
        "status": "planned"
    }
]

# ============================================================================
# HTML DASHBOARD
# ============================================================================

DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pantheon Dashboard - Proof of Time</title>
    <style>
        :root {
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-hover: #1a1a25;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --border: #2a2a35;
            --gold: #FFD700;
            --green: #3fb950;
            --red: #f85149;
            --blue: #58a6ff;
            --purple: #a371f7;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 24px 32px;
            border-bottom: 1px solid var(--border);
            text-align: center;
        }

        .header h1 {
            font-size: 28px;
            background: linear-gradient(90deg, var(--gold), #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }

        .header .subtitle {
            color: var(--text-secondary);
            font-size: 14px;
        }

        .header .protocol-prompt {
            margin-top: 16px;
            padding: 12px 24px;
            background: rgba(255, 215, 0, 0.1);
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 8px;
            display: inline-block;
            font-style: italic;
            color: var(--gold);
        }

        .nav {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 0 32px;
            display: flex;
            gap: 8px;
        }

        .nav-item {
            padding: 16px 20px;
            color: var(--text-secondary);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .nav-item:hover { color: var(--text-primary); }
        .nav-item.active {
            color: var(--gold);
            border-bottom-color: var(--gold);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }

        .section { display: none; }
        .section.active { display: block; }

        /* Gods Grid */
        .gods-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }

        .god-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }

        .god-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }

        .god-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }

        .god-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }

        .god-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }

        .god-info h3 {
            font-size: 18px;
            margin-bottom: 4px;
        }

        .god-domain {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .god-desc {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 16px;
            line-height: 1.5;
        }

        .god-module {
            font-family: monospace;
            font-size: 12px;
            color: var(--blue);
            background: rgba(88, 166, 255, 0.1);
            padding: 6px 10px;
            border-radius: 6px;
            display: inline-block;
        }

        .god-status {
            position: absolute;
            top: 16px;
            right: 16px;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .god-status.active { background: rgba(63, 185, 80, 0.2); color: var(--green); }
        .god-status.limited { background: rgba(210, 153, 34, 0.2); color: #d29922; }
        .god-status.planned { background: rgba(136, 136, 136, 0.2); color: var(--text-secondary); }

        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }

        .stat-value {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .stat-label {
            font-size: 13px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }

        /* Dimension Bars */
        .dimensions-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }

        .dimension-row {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }

        .dimension-name {
            width: 120px;
            font-size: 14px;
        }

        .dimension-bar {
            flex: 1;
            height: 24px;
            background: var(--bg-dark);
            border-radius: 12px;
            overflow: hidden;
        }

        .dimension-fill {
            height: 100%;
            border-radius: 12px;
            transition: width 0.5s;
            display: flex;
            align-items: center;
            padding-left: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .dimension-weight {
            width: 50px;
            text-align: right;
            font-size: 14px;
            color: var(--text-secondary);
        }

        /* Tables */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
        }

        .data-table th {
            background: var(--bg-hover);
            padding: 16px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
        }

        .data-table td {
            padding: 16px;
            border-bottom: 1px solid var(--border);
        }

        .data-table tr:hover td {
            background: var(--bg-hover);
        }

        .mono { font-family: monospace; }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .badge.green { background: rgba(63, 185, 80, 0.2); color: var(--green); }
        .badge.red { background: rgba(248, 81, 73, 0.2); color: var(--red); }
        .badge.blue { background: rgba(88, 166, 255, 0.2); color: var(--blue); }
        .badge.purple { background: rgba(163, 113, 247, 0.2); color: var(--purple); }
        .badge.gold { background: rgba(255, 215, 0, 0.2); color: var(--gold); }

        /* City Distribution */
        .city-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
        }

        .city-item {
            background: var(--bg-hover);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }

        .city-hash {
            font-family: monospace;
            font-size: 12px;
            color: #39c5cf;
            margin-bottom: 8px;
        }

        .city-count {
            font-size: 24px;
            font-weight: 700;
        }

        .city-label {
            font-size: 11px;
            color: var(--text-secondary);
        }

        /* Events */
        .event-item {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
        }

        .event-time {
            font-size: 12px;
            color: var(--text-secondary);
            width: 80px;
        }

        .event-node {
            font-family: monospace;
            font-size: 12px;
            color: var(--blue);
            width: 140px;
        }

        .event-impact {
            width: 60px;
            text-align: right;
            font-weight: 600;
        }

        .event-impact.positive { color: var(--green); }
        .event-impact.negative { color: var(--red); }

        .card-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .card-title::before {
            content: '';
            width: 4px;
            height: 24px;
            background: var(--gold);
            border-radius: 2px;
        }

        .two-col {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }

        @media (max-width: 900px) {
            .two-col { grid-template-columns: 1fr; }
        }

        .refresh-info {
            text-align: center;
            padding: 16px;
            color: var(--text-secondary);
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>PANTHEON</h1>
        <div class="subtitle">Proof of Time Protocol Dashboard</div>
        <div class="protocol-prompt">
            "Chronos proves, Athena selects, Adonis trusts."
        </div>
    </div>

    <nav class="nav">
        <div class="nav-item active" data-section="gods">12 Gods</div>
        <div class="nav-item" data-section="adonis">Adonis</div>
        <div class="nav-item" data-section="geography">Geography</div>
        <div class="nav-item" data-section="nodes">Nodes</div>
        <div class="nav-item" data-section="events">Events</div>
    </nav>

    <div class="container">
        <!-- Gods Section -->
        <section id="gods" class="section active">
            <div class="gods-grid" id="gods-grid"></div>
        </section>

        <!-- Adonis Section -->
        <section id="adonis" class="section">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--blue)" id="adonis-total">-</div>
                    <div class="stat-label">Total Nodes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--green)" id="adonis-active">-</div>
                    <div class="stat-label">Active</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--red)" id="adonis-penalized">-</div>
                    <div class="stat-label">Penalized</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--purple)" id="adonis-avg">-</div>
                    <div class="stat-label">Avg Score</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--gold)" id="adonis-vouches">-</div>
                    <div class="stat-label">Total Vouches</div>
                </div>
            </div>

            <div class="dimensions-card">
                <div class="card-title">Reputation Dimensions</div>
                <div id="dimensions-container"></div>
            </div>
        </section>

        <!-- Geography Section -->
        <section id="geography" class="section">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color: #39c5cf" id="geo-cities">-</div>
                    <div class="stat-label">Unique Cities</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--purple)" id="geo-diversity">-</div>
                    <div class="stat-label">Diversity Score</div>
                </div>
            </div>

            <div class="dimensions-card">
                <div class="card-title">City Distribution</div>
                <div class="city-grid" id="city-grid"></div>
            </div>
        </section>

        <!-- Nodes Section -->
        <section id="nodes" class="section">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Node</th>
                        <th>Score</th>
                        <th>City</th>
                        <th>Vouches In</th>
                        <th>Events</th>
                    </tr>
                </thead>
                <tbody id="nodes-table"></tbody>
            </table>
        </section>

        <!-- Events Section -->
        <section id="events" class="section">
            <div class="dimensions-card">
                <div class="card-title">Recent Events</div>
                <div id="events-list"></div>
            </div>
        </section>

        <div class="refresh-info">
            Auto-refresh every 10 seconds | <span id="last-update">-</span>
        </div>
    </div>

    <script>
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
                item.classList.add('active');
                document.getElementById(item.dataset.section).classList.add('active');
            });
        });

        // Dimension colors
        const dimColors = {
            'INTEGRITY': '#f85149',
            'RELIABILITY': '#58a6ff',
            'LONGEVITY': '#a371f7',
            'CONTRIBUTION': '#3fb950',
            'COMMUNITY': '#d29922',
            'GEOGRAPHY': '#39c5cf'
        };

        // God icons (emoji fallback)
        const godIcons = {
            'Chronos': '⏳', 'Adonis': '⭐', 'Hermes': '🌐',
            'Hades': '💾', 'Athena': '⚖️', 'Prometheus': '🔥',
            'Mnemosyne': '🧠', 'Plutus': '💰', 'Nyx': '🌙',
            'Themis': '✓', 'Iris': '📡', 'Ananke': '🗳️'
        };

        // Render gods
        function renderGods(gods) {
            const html = gods.map(g => `
                <div class="god-card" style="border-top: 3px solid ${g.color}">
                    <div class="god-status ${g.status}">${g.status}</div>
                    <div class="god-header">
                        <div class="god-icon" style="background: ${g.color}20; color: ${g.color}">
                            ${godIcons[g.name] || '?'}
                        </div>
                        <div class="god-info">
                            <h3 style="color: ${g.color}">${g.name}</h3>
                            <div class="god-domain">${g.domain}</div>
                        </div>
                    </div>
                    <div class="god-desc">${g.description}</div>
                    <div class="god-module">${g.module}</div>
                </div>
            `).join('');
            document.getElementById('gods-grid').innerHTML = html;
        }

        // Render dimensions
        function renderDimensions(weights, avgs) {
            const html = Object.entries(weights).map(([name, weight]) => {
                const avg = avgs[name]?.avg || 0;
                const color = dimColors[name] || '#888';
                return `
                    <div class="dimension-row">
                        <span class="dimension-name">${name}</span>
                        <div class="dimension-bar">
                            <div class="dimension-fill" style="width:${avg*100}%;background:${color}">
                                ${(avg*100).toFixed(1)}%
                            </div>
                        </div>
                        <span class="dimension-weight">${(weight*100).toFixed(0)}%</span>
                    </div>
                `;
            }).join('');
            document.getElementById('dimensions-container').innerHTML = html;
        }

        // Format time
        function formatTime(ts) {
            return new Date(ts * 1000).toLocaleTimeString();
        }

        // Fetch data
        async function refreshData() {
            try {
                // Gods
                const gods = await fetch('/api/gods').then(r => r.json());
                renderGods(gods.gods);

                // Overview
                const overview = await fetch('/api/overview').then(r => r.json());
                document.getElementById('adonis-total').textContent = overview.total_nodes;
                document.getElementById('adonis-active').textContent = overview.active_nodes;
                document.getElementById('adonis-penalized').textContent = overview.penalized_nodes;
                document.getElementById('adonis-avg').textContent = overview.average_score.toFixed(3);
                document.getElementById('adonis-vouches').textContent = overview.total_vouches;

                // Dimensions
                const dims = await fetch('/api/dimensions').then(r => r.json());
                renderDimensions(overview.dimension_weights, dims.dimensions);

                // Geography
                const geo = await fetch('/api/cities').then(r => r.json());
                document.getElementById('geo-cities').textContent = geo.total_cities;
                document.getElementById('geo-diversity').textContent = (geo.diversity_score * 100).toFixed(1) + '%';

                const cityHtml = geo.cities.slice(0, 12).map(c => `
                    <div class="city-item">
                        <div class="city-hash">${c.hash}</div>
                        <div class="city-count">${c.nodes}</div>
                        <div class="city-label">nodes</div>
                    </div>
                `).join('');
                document.getElementById('city-grid').innerHTML = cityHtml || '<div style="color:var(--text-secondary)">No cities registered</div>';

                // Top nodes
                const top = await fetch('/api/top?limit=15').then(r => r.json());
                const nodesHtml = top.nodes.map((n, i) => `
                    <tr>
                        <td>${i + 1}</td>
                        <td class="mono">${n.pubkey_short}</td>
                        <td><span class="badge ${n.score > 0.5 ? 'green' : 'gold'}">${n.score.toFixed(3)}</span></td>
                        <td class="mono" style="color:#39c5cf">${n.city_hash || '-'}</td>
                        <td>${n.vouches_received}</td>
                        <td>${n.total_events}</td>
                    </tr>
                `).join('');
                document.getElementById('nodes-table').innerHTML = nodesHtml || '<tr><td colspan="6" style="color:var(--text-secondary)">No nodes</td></tr>';

                // Events
                const events = await fetch('/api/events?limit=20').then(r => r.json());
                const eventsHtml = events.events.map(e => `
                    <div class="event-item">
                        <span class="event-time">${formatTime(e.timestamp)}</span>
                        <span class="event-node">${e.pubkey}</span>
                        <span class="badge ${e.impact >= 0 ? 'green' : 'red'}">${e.event}</span>
                        <span class="event-impact ${e.impact >= 0 ? 'positive' : 'negative'}">
                            ${e.impact >= 0 ? '+' : ''}${e.impact.toFixed(2)}
                        </span>
                    </div>
                `).join('');
                document.getElementById('events-list').innerHTML = eventsHtml || '<div style="color:var(--text-secondary);padding:20px">No events</div>';

                document.getElementById('last-update').textContent = 'Updated: ' + new Date().toLocaleTimeString();

            } catch (err) {
                console.error('Error:', err);
            }
        }

        refreshData();
        setInterval(refreshData, 10000);
    </script>
</body>
</html>
'''


# ============================================================================
# HTTP SERVER
# ============================================================================

class DashboardHandler(BaseHTTPRequestHandler):
    engine: AdonisEngine = None

    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        try:
            if path == '/' or path == '/dashboard':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(DASHBOARD_HTML.encode())

            elif path == '/api/gods':
                self.send_json({"gods": PANTHEON_GODS})

            elif path == '/api/overview':
                stats = self.engine.get_stats()
                self.send_json({
                    "total_nodes": stats["total_profiles"],
                    "active_nodes": stats["active_profiles"],
                    "penalized_nodes": stats["penalized_profiles"],
                    "total_vouches": stats["total_vouches"],
                    "average_score": round(stats["average_score"], 4),
                    "unique_cities": stats["unique_cities"],
                    "dimension_weights": stats["dimension_weights"]
                })

            elif path == '/api/dimensions':
                dims = {dim.name: {"total": 0, "count": 0, "avg": 0}
                       for dim in ReputationDimension}
                for p in self.engine.profiles.values():
                    for dim, score in p.dimensions.items():
                        dims[dim.name]["total"] += score.value
                        dims[dim.name]["count"] += 1
                for d in dims.values():
                    if d["count"] > 0:
                        d["avg"] = round(d["total"] / d["count"], 4)
                self.send_json({"dimensions": dims})

            elif path == '/api/cities':
                dist = self.engine.get_city_distribution()
                cities = [{"hash": k, "nodes": v}
                         for k, v in sorted(dist.items(), key=lambda x: x[1], reverse=True)]
                self.send_json({
                    "cities": cities,
                    "total_cities": len(cities),
                    "diversity_score": round(self.engine.get_geographic_diversity_score(), 4)
                })

            elif path == '/api/top':
                limit = int(params.get('limit', [20])[0])
                top = self.engine.get_top_nodes(limit)
                nodes = []
                for pk, score in top:
                    p = self.engine.get_profile(pk)
                    if p:
                        nodes.append({
                            "pubkey": pk.hex(),
                            "pubkey_short": pk.hex()[:16] + "...",
                            "score": round(score, 4),
                            "city_hash": p.city_hash.hex()[:8] if p.city_hash else None,
                            "vouches_received": len(p.trusted_by),
                            "total_events": p.total_events
                        })
                self.send_json({"nodes": nodes})

            elif path == '/api/events':
                limit = int(params.get('limit', [50])[0])
                events = []
                for pk, p in self.engine.profiles.items():
                    for e in p.history[-10:]:
                        events.append({
                            "pubkey": pk.hex()[:16] + "...",
                            "event": e.event_type.name,
                            "impact": round(e.impact, 3),
                            "timestamp": e.timestamp
                        })
                events.sort(key=lambda x: x["timestamp"], reverse=True)
                self.send_json({"events": events[:limit]})

            else:
                self.send_json({"error": "Not found"}, 404)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)


def generate_demo_data(engine: AdonisEngine):
    """Generate demo data."""
    import random

    cities = [
        ("US", "New York"), ("US", "Los Angeles"), ("JP", "Tokyo"),
        ("DE", "Berlin"), ("GB", "London"), ("FR", "Paris"),
        ("SG", "Singapore"), ("AU", "Sydney"), ("KR", "Seoul"),
        ("CA", "Toronto"), ("NL", "Amsterdam"), ("BR", "Sao Paulo")
    ]

    for i in range(25):
        pk = bytes([i + 1] * 32)
        country, city = random.choice(cities)
        engine.register_node_location(pk, country, city)

        for _ in range(random.randint(10, 50)):
            evt = random.choice([
                ReputationEvent.BLOCK_PRODUCED,
                ReputationEvent.BLOCK_VALIDATED,
                ReputationEvent.TX_RELAYED,
                ReputationEvent.UPTIME_CHECKPOINT
            ]) if random.random() > 0.15 else ReputationEvent.DOWNTIME
            engine.record_event(pk, evt, height=random.randint(1, 10000))

        if i > 0 and random.random() > 0.5:
            voucher = bytes([random.randint(1, i)] * 32)
            engine.add_vouch(voucher, pk)

    # One penalized
    bad = bytes([99] * 32)
    engine.register_node_location(bad, "XX", "Unknown")
    engine.record_event(bad, ReputationEvent.EQUIVOCATION)

    logger.info(f"Generated {len(engine.profiles)} demo nodes")


def main():
    parser = argparse.ArgumentParser(description="Pantheon Dashboard")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    engine = AdonisEngine()
    if args.demo:
        generate_demo_data(engine)

    DashboardHandler.engine = engine

    print(f"\n{'='*60}")
    print(f"  PANTHEON DASHBOARD")
    print(f"  http://{args.host}:{args.port}")
    print(f"{'='*60}\n")

    HTTPServer((args.host, args.port), DashboardHandler).serve_forever()


if __name__ == "__main__":
    main()
