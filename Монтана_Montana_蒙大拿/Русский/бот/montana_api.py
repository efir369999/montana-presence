#!/usr/bin/env python3
# montana_api.py
# API для Mission Control Dashboard Montana

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import json
import os
from pathlib import Path
from datetime import datetime
from session_manager import get_session_manager

app = Flask(__name__)
CORS(app)  # Разрешить CORS для доступа с сайта

BOT_DIR = Path(__file__).parent
USERS_FILE = BOT_DIR / "data" / "users.json"
SESSIONS_DIR = BOT_DIR / "data" / "sessions"

# ═══════════════════════════════════════════════════════════════════════════════
#                              СТАТУС СЕТИ MONTANA
# ═══════════════════════════════════════════════════════════════════════════════

NODES = {
    "amsterdam": {"ip": "72.56.102.240", "priority": 1, "location": "🇳🇱 Amsterdam"},
    "moscow": {"ip": "176.124.208.93", "priority": 2, "location": "🇷🇺 Moscow"},
    "almaty": {"ip": "91.200.148.93", "priority": 3, "location": "🇰🇿 Almaty"},
    "spb": {"ip": "188.225.58.98", "priority": 4, "location": "🇷🇺 St.Petersburg"},
    "novosibirsk": {"ip": "147.45.147.247", "priority": 5, "location": "🇷🇺 Novosibirsk"}
}

def check_node_status(ip: str) -> dict:
    """Проверить статус узла через ping"""
    import subprocess
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2
        )
        online = result.returncode == 0
        return {"online": online, "response_time": "< 100ms" if online else "timeout"}
    except:
        return {"online": False, "response_time": "error"}

def get_network_status() -> dict:
    """Получить полный статус сети Montana"""
    status = {}

    for node_name, node_info in NODES.items():
        node_status = check_node_status(node_info["ip"])
        status[node_name] = {
            **node_info,
            **node_status,
            "name": node_name.title()
        }

    # Подсчёт онлайн узлов
    online_count = sum(1 for n in status.values() if n["online"])

    return {
        "nodes": status,
        "summary": {
            "total_nodes": len(NODES),
            "online_nodes": online_count,
            "network_health": f"{(online_count/len(NODES))*100:.0f}%",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
#                              СТАТИСТИКА БОТА
# ═══════════════════════════════════════════════════════════════════════════════

def get_bot_stats() -> dict:
    """Статистика бота Юноны"""

    # Пользователи
    total_users = 0
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
                total_users = len(users)
        except:
            pass

    # Сессии
    total_sessions = 0
    total_messages = 0
    total_reasoning_logs = 0

    if SESSIONS_DIR.exists():
        for user_dir in SESSIONS_DIR.iterdir():
            if user_dir.is_dir():
                for session_dir in user_dir.iterdir():
                    if session_dir.is_dir():
                        total_sessions += 1

                        # Сообщения
                        messages_file = session_dir / "messages.jsonl"
                        if messages_file.exists():
                            with open(messages_file, 'r') as f:
                                total_messages += sum(1 for _ in f)

                        # Reasoning logs
                        reasoning_file = session_dir / "reasoning.jsonl"
                        if reasoning_file.exists():
                            with open(reasoning_file, 'r') as f:
                                total_reasoning_logs += sum(1 for _ in f)

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_reasoning_logs": total_reasoning_logs,
        "avg_messages_per_session": round(total_messages / total_sessions, 1) if total_sessions > 0 else 0
    }

# ═══════════════════════════════════════════════════════════════════════════════
#                              API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/status')
def api_status():
    """Полный статус Montana: сеть + бот"""
    network = get_network_status()
    bot = get_bot_stats()

    return jsonify({
        "network": network,
        "bot": bot,
        "montana": {
            "version": "Evolution 1.0",
            "mode": "Production",
            "parallel_agents": True
        }
    })

@app.route('/api/network')
def api_network():
    """Только статус сети"""
    return jsonify(get_network_status())

@app.route('/api/bot')
def api_bot():
    """Только статистика бота"""
    return jsonify(get_bot_stats())

@app.route('/api/sessions')
def api_sessions():
    """Последние сессии"""
    sessions = []

    if SESSIONS_DIR.exists():
        for user_dir in sorted(SESSIONS_DIR.iterdir(), reverse=True)[:5]:
            if user_dir.is_dir():
                user_id = user_dir.name.replace("user_", "")
                for session_dir in sorted(user_dir.iterdir(), reverse=True)[:2]:
                    if session_dir.is_dir():
                        session_file = session_dir / "session.json"
                        if session_file.exists():
                            with open(session_file, 'r') as f:
                                session_data = json.load(f)

                                # Подсчёт сообщений
                                messages_count = 0
                                messages_file = session_dir / "messages.jsonl"
                                if messages_file.exists():
                                    with open(messages_file, 'r') as mf:
                                        messages_count = sum(1 for _ in mf)

                                sessions.append({
                                    "user_id": user_id,
                                    "session_id": session_data.get("id"),
                                    "created_at": session_data.get("created_at"),
                                    "messages": messages_count
                                })

    return jsonify({"sessions": sessions[:10]})

# ═══════════════════════════════════════════════════════════════════════════════
#                              DASHBOARD HTML
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    """Mission Control Dashboard"""
    html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏔 Montana Mission Control</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        h1 {
            text-align: center;
            font-size: 2em;
            margin-bottom: 30px;
            text-shadow: 0 0 10px #00ff00;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: #111;
            border: 2px solid #00ff00;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(0,255,0,0.2);
        }

        .card h2 {
            color: #00ff00;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 10px;
        }

        .stat {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #222;
        }

        .stat:last-child {
            border-bottom: none;
        }

        .stat-label {
            color: #888;
        }

        .stat-value {
            color: #00ff00;
            font-weight: bold;
        }

        .node {
            padding: 10px;
            margin: 10px 0;
            background: #0a0a0a;
            border-left: 3px solid #00ff00;
            border-radius: 5px;
        }

        .node.offline {
            border-left-color: #ff0000;
            opacity: 0.6;
        }

        .node-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff00;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }

        .node.offline .node-status {
            background: #ff0000;
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .health {
            font-size: 2em;
            text-align: center;
            margin: 20px 0;
            color: #00ff00;
            text-shadow: 0 0 20px #00ff00;
        }

        .timestamp {
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
        }

        .loading {
            text-align: center;
            color: #00ff00;
            font-size: 1.5em;
        }

        .sessions {
            max-height: 300px;
            overflow-y: auto;
        }

        .session {
            padding: 8px;
            margin: 5px 0;
            background: #0a0a0a;
            border-radius: 5px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏔 MONTANA MISSION CONTROL</h1>

        <div id="loading" class="loading">Загрузка данных...</div>

        <div id="dashboard" style="display:none;">
            <!-- Network Status -->
            <div class="card">
                <h2>🌐 NETWORK STATUS</h2>
                <div class="health" id="network-health">--</div>
                <div id="nodes"></div>
            </div>

            <!-- Bot Statistics -->
            <div class="grid">
                <div class="card">
                    <h2>🤖 BOT STATISTICS</h2>
                    <div class="stat">
                        <span class="stat-label">Total Users:</span>
                        <span class="stat-value" id="total-users">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Total Sessions:</span>
                        <span class="stat-value" id="total-sessions">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Total Messages:</span>
                        <span class="stat-value" id="total-messages">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Reasoning Logs:</span>
                        <span class="stat-value" id="reasoning-logs">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Avg Messages/Session:</span>
                        <span class="stat-value" id="avg-messages">--</span>
                    </div>
                </div>

                <div class="card">
                    <h2>⚙️ MONTANA STATUS</h2>
                    <div class="stat">
                        <span class="stat-label">Version:</span>
                        <span class="stat-value" id="version">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Mode:</span>
                        <span class="stat-value" id="mode">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Parallel Agents:</span>
                        <span class="stat-value" id="parallel-agents">--</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Network Health:</span>
                        <span class="stat-value" id="summary-health">--</span>
                    </div>
                </div>
            </div>

            <!-- Recent Sessions -->
            <div class="card">
                <h2>📊 RECENT SESSIONS</h2>
                <div class="sessions" id="sessions"></div>
            </div>

            <div class="timestamp">
                Последнее обновление: <span id="timestamp">--</span>
            </div>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                // Hide loading
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';

                // Network
                const nodes = data.network.nodes;
                const nodesHTML = Object.keys(nodes).map(key => {
                    const node = nodes[key];
                    const statusClass = node.online ? '' : 'offline';
                    return `
                        <div class="node ${statusClass}">
                            <span class="node-status"></span>
                            <strong>${node.location}</strong>
                            <span style="color:#666">${node.ip}</span>
                            <span style="float:right; color:${node.online ? '#00ff00' : '#ff0000'}">
                                ${node.online ? '● ONLINE' : '○ OFFLINE'}
                            </span>
                        </div>
                    `;
                }).join('');
                document.getElementById('nodes').innerHTML = nodesHTML;
                document.getElementById('network-health').textContent = data.network.summary.network_health;

                // Bot stats
                document.getElementById('total-users').textContent = data.bot.total_users;
                document.getElementById('total-sessions').textContent = data.bot.total_sessions;
                document.getElementById('total-messages').textContent = data.bot.total_messages;
                document.getElementById('reasoning-logs').textContent = data.bot.total_reasoning_logs;
                document.getElementById('avg-messages').textContent = data.bot.avg_messages_per_session;

                // Montana
                document.getElementById('version').textContent = data.montana.version;
                document.getElementById('mode').textContent = data.montana.mode;
                document.getElementById('parallel-agents').textContent = data.montana.parallel_agents ? 'ENABLED' : 'DISABLED';
                document.getElementById('summary-health').textContent = data.network.summary.network_health;

                // Timestamp
                const timestamp = new Date(data.network.summary.timestamp);
                document.getElementById('timestamp').textContent = timestamp.toLocaleString('ru-RU');

                // Fetch sessions
                const sessionsResp = await fetch('/api/sessions');
                const sessionsData = await sessionsResp.json();
                const sessionsHTML = sessionsData.sessions.map(s => {
                    const date = new Date(s.created_at);
                    return `
                        <div class="session">
                            User ${s.user_id} • ${s.messages} messages • ${date.toLocaleDateString('ru-RU')} ${date.toLocaleTimeString('ru-RU')}
                        </div>
                    `;
                }).join('');
                document.getElementById('sessions').innerHTML = sessionsHTML || '<div class="session">Нет данных</div>';

            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loading').textContent = 'Ошибка загрузки данных';
            }
        }

        // Initial fetch
        fetchStatus();

        // Auto-refresh every 10 seconds
        setInterval(fetchStatus, 10000);
    </script>
</body>
</html>
    """
    return render_template_string(html)

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("🏔 Montana Mission Control API")
    print("   Listening on http://0.0.0.0:5000")
    print("   Dashboard: http://localhost:5000")
    print("   API: http://localhost:5000/api/status")

    app.run(host='0.0.0.0', port=5000, debug=False)
