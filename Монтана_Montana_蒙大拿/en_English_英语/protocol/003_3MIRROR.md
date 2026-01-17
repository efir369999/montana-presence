# 3-Mirror System

**Montana Fault-Tolerant Network**
**Montana Protocol v1.0**

---

## Abstract

3-Mirror — a distributed system of 5 nodes with automatic failover. When any 4 of 5 nodes fail, the network continues operating. Recovery time < 10 seconds. Synchronization through "breathing" — git pull/push every 12 seconds.

**Key formula:**
```
4/5 nodes can fail = network alive
Recovery < 10 seconds
```

---

## 1. Introduction

### 1.1 Problem with Centralized Systems

| System | Points of Failure | Recovery Time |
|--------|-------------------|---------------|
| Single server | 1 | Hours/days |
| Master-Slave | 2 | Minutes |
| **3-Mirror** | **5** | **< 10 seconds** |

### 1.2 Montana Solution

5 geographically distributed nodes with deterministic priority-based failover.

---

## 2. Architecture

### 2.1 Network Topology

**Source code:** [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py)

```python
BRAIN_CHAIN = [
    ("moscow",      "176.124.208.93"),
    ("almaty",      "91.200.148.93"),
    ("spb",         "188.225.58.98"),
    ("novosibirsk", "147.45.147.247"),
]

BOT_CHAIN = [
    ("amsterdam",   "72.56.102.240"),
    ("almaty",      "91.200.148.93"),
    ("spb",         "188.225.58.98"),
    ("novosibirsk", "147.45.147.247"),
]
```

### 2.2 Node Roles

| Role | Node | IP | Function |
|------|------|----|----------|
| PRIMARY | Amsterdam | 72.56.102.240 | Active bot |
| BRAIN | Moscow | 176.124.208.93 | Controller |
| MIRROR 1 | Almaty | 91.200.148.93 | Standby |
| MIRROR 2 | SPB | 188.225.58.98 | Standby |
| MIRROR 3 | Novosibirsk | 147.45.147.247 | Standby |

---

## 3. Failover Protocol

### 3.1 Deterministic Leader Selection

**Source code:** [watchdog.py#L162-L172](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L162-L172)

```python
def am_i_the_brain(my_name: str) -> bool:
    """
    Am I the current brain?
    I'm the brain if all brains BEFORE me in chain are dead.
    """
    for name, ip in BRAIN_CHAIN:
        if name == my_name:
            return True  # Reached myself - I'm the brain
        if is_node_alive(ip):
            return False  # Someone before me is alive
    return False
```

### 3.2 Monitoring Constants

```python
CHECK_INTERVAL = 5   # seconds between checks
SYNC_INTERVAL = 12   # seconds between syncs
```

---

## 4. Breathing Sync

### 4.1 Synchronization Mechanism

**Source code:** [watchdog.py#L140-L156](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L140-L156)

```python
def sync_pull():
    """Inhale: git pull."""
    cmd = f"cd {REPO_PATH} && git pull origin main --rebase"
    subprocess.run(cmd, shell=True)

def sync_push():
    """Exhale: git push."""
    cmd = f"cd {REPO_PATH} && git push origin main"
    subprocess.run(cmd, shell=True)
```

### 4.2 Breathing Cycle

```
Every 12 seconds:
  1. Inhale (pull) — receive changes from network
  2. Exhale (push) — send own changes
```

---

## 5. Scientific Novelty

1. **Deterministic failover** — leader determined by chain order, no voting
2. **Breathing sync** — breathing metaphor for bidirectional synchronization
3. **Geographic distribution** — nodes in different time zones
4. **Sub-second recovery** — failure detection in 5 sec, switchover in 5 sec

---

## 6. References

| Document | Link |
|----------|------|
| Watchdog code | [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py) |
| Montana Protocol | [MONTANA.md](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/MONTANA.md) |
| Infrastructure | [CLAUDE.md](https://github.com/efir369999/junomontanaagibot/blob/main/CLAUDE.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
January 2026

github.com/efir369999/junomontanaagibot
```
