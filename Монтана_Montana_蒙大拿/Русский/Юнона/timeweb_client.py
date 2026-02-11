#!/usr/bin/env python3
"""
Timeweb Cloud API Client — Infrastructure Monitoring for Montana Protocol

Manages 3 Montana nodes via Timeweb Cloud API:
  - Moscow (176.124.208.93)
  - Amsterdam (72.56.102.240)
  - Almaty (91.200.148.93)

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import json
import logging
import ipaddress
import subprocess
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("timeweb")

API_BASE = "https://api.timeweb.cloud/api/v1"

# Server IDs (from Timeweb API)
SERVERS = {
    "moscow": {"id": 5264781, "ip": "176.124.208.93", "location": "ru-3"},
    "amsterdam": {"id": 6397983, "ip": "72.56.102.240", "location": "nl-1"},
    "almaty": {"id": 6402637, "ip": "91.200.148.93", "location": "kz-1"},
}


def _get_token() -> str:
    """Get Timeweb API token from macOS Keychain (primary) or env (server fallback)"""
    # Primary: macOS Keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "montana",
             "-s", "TIMEWEB_API_TOKEN", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError) as e:
        log.warning("Keychain lookup failed: %s", type(e).__name__)

    # Fallback: env var (for server deployment where keychain is unavailable)
    token = os.environ.get("TIMEWEB_API_TOKEN")
    if token:
        log.warning("Using TIMEWEB_API_TOKEN from env (prefer keychain)")
        return token

    raise RuntimeError("TIMEWEB_API_TOKEN not found in keychain or env")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{API_BASE}{path}", headers=_headers(),
                        params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict = None) -> dict:
    resp = requests.post(f"{API_BASE}{path}", headers=_headers(),
                         json=data or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _delete(path: str) -> dict:
    resp = requests.delete(f"{API_BASE}{path}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─── Account ─────────────────────────────────────────────────────────────────

def account_status() -> dict:
    """Get Timeweb account status"""
    return _get("/account/status")


# ─── Servers ─────────────────────────────────────────────────────────────────

def list_servers() -> list:
    """List all Montana servers"""
    data = _get("/servers")
    return data.get("servers", [])


def get_server(node_name: str) -> Optional[dict]:
    """Get server details by node name"""
    node = SERVERS.get(node_name)
    if not node:
        return None
    data = _get(f"/servers/{node['id']}")
    return data.get("server")


def get_server_statistics(node_name: str) -> Optional[dict]:
    """Get CPU/RAM/disk/network stats for a server"""
    node = SERVERS.get(node_name)
    if not node:
        return None
    data = _get(f"/servers/{node['id']}/statistics")
    return data


_last_reboot = {}  # node_name -> timestamp

def reboot_server(node_name: str, confirm: bool = False) -> dict:
    """Reboot a Montana server (requires confirm=True, rate limited to 1/10min)"""
    if not confirm:
        return {"error": "Reboot requires confirm=True"}
    node = SERVERS.get(node_name)
    if not node:
        return {"error": f"Unknown node: {node_name}"}

    now = datetime.now(timezone.utc).timestamp()
    last = _last_reboot.get(node_name, 0)
    if now - last < 600:
        return {"error": f"Rate limited: last reboot {int(now - last)}s ago (min 600s)"}

    log.warning("REBOOT: %s (%s)", node_name, node["ip"])
    result = _post(f"/servers/{node['id']}/reboot")
    _last_reboot[node_name] = now
    return result


# ─── Firewall ────────────────────────────────────────────────────────────────

def list_firewall_groups() -> list:
    """List firewall rule groups"""
    data = _get("/firewall/groups")
    return data.get("groups", [])


def create_firewall_rule(group_id: int, direction: str, protocol: str,
                         port: int, cidr: str = "0.0.0.0/0") -> dict:
    """Create a firewall rule"""
    return _post(f"/firewall/groups/{group_id}/rules", {
        "direction": direction,
        "protocol": protocol,
        "port": port,
        "cidr": cidr,
    })


VALID_PROTOCOLS = {"tcp", "udp", "icmp"}

def block_ip(group_id: int, ip: str, protocol: str = "tcp") -> dict:
    """Block an IP address via firewall (validates IP and protocol)"""
    # Validate IP address
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return {"error": f"Invalid IP address: {ip}"}

    # Prevent self-DoS: never block Montana node IPs
    montana_ips = {s["ip"] for s in SERVERS.values()}
    if str(addr) in montana_ips:
        return {"error": "Cannot block Montana node IP"}

    if protocol not in VALID_PROTOCOLS:
        return {"error": f"Invalid protocol: {protocol} (use: {VALID_PROTOCOLS})"}

    if not isinstance(group_id, int) or group_id <= 0:
        return {"error": "group_id must be a positive integer"}

    log.warning("BLOCK IP: %s (protocol=%s, group=%d)", ip, protocol, group_id)
    return create_firewall_rule(
        group_id=group_id,
        direction="ingress",
        protocol=protocol,
        port=0,
        cidr=f"{ip}/32",
    )


def list_firewall_rules(group_id: int) -> list:
    """List rules in a firewall group"""
    data = _get(f"/firewall/groups/{group_id}/rules")
    return data.get("rules", [])


def delete_firewall_rule(group_id: int, rule_id: int) -> dict:
    """Delete a firewall rule"""
    return _delete(f"/firewall/groups/{group_id}/rules/{rule_id}")


# ─── Monitoring ──────────────────────────────────────────────────────────────

def health_check_all() -> dict:
    """Check health of all Montana servers via Timeweb API"""
    results = {}
    for name, info in SERVERS.items():
        try:
            server = get_server(name)
            if server:
                disk = server.get("disks", [{}])[0]
                networks = server.get("networks", [{}])[0]
                ips = networks.get("ips", [])
                ipv4 = next((ip["ip"] for ip in ips
                             if ip.get("type") == "ipv4"), None)

                results[name] = {
                    "status": server.get("status"),
                    "ip": ipv4,
                    "cpu": server.get("cpu"),
                    "ram_mb": server.get("ram"),
                    "disk_total_mb": disk.get("size"),
                    "disk_used_mb": disk.get("used"),
                    "disk_percent": round(
                        disk.get("used", 0) / max(disk.get("size", 1), 1) * 100, 1
                    ),
                    "os": f"{server['os']['name']} {server['os']['version']}",
                    "location": server.get("location"),
                    "ddos_guard": server.get("is_ddos_guard"),
                    "bandwidth_mbps": networks.get("bandwidth"),
                    "blocked_ports": networks.get("blocked_ports", []),
                }
            else:
                results[name] = {"status": "error", "message": "Not found"}
        except Exception as e:
            log.error("Health check failed for %s: %s", name, e)
            results[name] = {"status": "error", "message": "Health check failed"}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes": results,
        "total": len(SERVERS),
        "online": sum(1 for r in results.values() if r.get("status") == "on"),
    }


def get_node_metrics(node_name: str) -> dict:
    """Get detailed metrics for a specific node"""
    stats = get_server_statistics(node_name)
    server = get_server(node_name)
    if not stats or not server:
        return {"error": f"Cannot get metrics for {node_name}"}

    disk = server.get("disks", [{}])[0]
    return {
        "node": node_name,
        "ip": SERVERS[node_name]["ip"],
        "status": server.get("status"),
        "cpu_cores": server.get("cpu"),
        "ram_mb": server.get("ram"),
        "disk_total_mb": disk.get("size"),
        "disk_used_mb": disk.get("used"),
        "disk_free_mb": disk.get("size", 0) - disk.get("used", 0),
        "statistics": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Security Alerts ─────────────────────────────────────────────────────────

def security_summary() -> dict:
    """Generate security summary for all nodes"""
    health = health_check_all()
    alerts = []

    for name, node in health.get("nodes", {}).items():
        if node.get("status") != "on":
            alerts.append({
                "severity": "critical",
                "node": name,
                "message": f"Node {name} is {node.get('status', 'unknown')}",
            })

        disk_pct = node.get("disk_percent", 0)
        if disk_pct > 90:
            alerts.append({
                "severity": "high",
                "node": name,
                "message": f"Disk usage {disk_pct}% on {name}",
            })
        elif disk_pct > 75:
            alerts.append({
                "severity": "medium",
                "node": name,
                "message": f"Disk usage {disk_pct}% on {name}",
            })

        if not node.get("ddos_guard"):
            alerts.append({
                "severity": "info",
                "node": name,
                "message": f"DDoS Guard not enabled on {name}",
            })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "alerts": alerts,
        "alert_count": len(alerts),
        "critical": sum(1 for a in alerts if a["severity"] == "critical"),
    }


if __name__ == "__main__":
    print("Montana Infrastructure Health Check")
    print("=" * 50)
    summary = security_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
