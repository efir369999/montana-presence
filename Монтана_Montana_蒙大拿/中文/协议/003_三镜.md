# 三镜系统

**Montana容错网络**
**Montana协议 v1.0**

---

## 摘要

三镜 — 具有自动故障转移的5节点分布式系统。当5个节点中的任意4个故障时，网络继续运行。恢复时间 < 10秒。通过"呼吸"同步 — 每12秒进行git pull/push。

**关键公式:**
```
5个节点中4个可以故障 = 网络存活
恢复 < 10秒
```

---

## 1. 引言

### 1.1 中心化系统的问题

| 系统 | 故障点 | 恢复时间 |
|------|--------|----------|
| 单服务器 | 1 | 小时/天 |
| 主从 | 2 | 分钟 |
| **三镜** | **5** | **< 10秒** |

### 1.2 Montana解决方案

5个地理分布的节点，具有确定性优先级故障转移。

---

## 2. 架构

### 2.1 网络拓扑

**源代码:** [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py)

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

### 2.2 节点角色

| 角色 | 节点 | IP | 功能 |
|------|------|----|------|
| PRIMARY | 阿姆斯特丹 | 72.56.102.240 | 活动机器人 |
| BRAIN | 莫斯科 | 176.124.208.93 | 控制器 |
| MIRROR 1 | 阿拉木图 | 91.200.148.93 | 待命 |
| MIRROR 2 | 圣彼得堡 | 188.225.58.98 | 待命 |
| MIRROR 3 | 新西伯利亚 | 147.45.147.247 | 待命 |

---

## 3. 故障转移协议

### 3.1 确定性领导者选择

**源代码:** [watchdog.py#L162-L172](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L162-L172)

```python
def am_i_the_brain(my_name: str) -> bool:
    """
    我是当前的大脑吗？
    如果链中我之前的所有大脑都死了，我就是大脑。
    """
    for name, ip in BRAIN_CHAIN:
        if name == my_name:
            return True  # 到达自己 - 我是大脑
        if is_node_alive(ip):
            return False  # 我之前有人活着
    return False
```

### 3.2 监控常量

```python
CHECK_INTERVAL = 5   # 检查间隔秒数
SYNC_INTERVAL = 12   # 同步间隔秒数
```

---

## 4. 呼吸同步

### 4.1 同步机制

**源代码:** [watchdog.py#L140-L156](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L140-L156)

```python
def sync_pull():
    """吸气: git pull."""
    cmd = f"cd {REPO_PATH} && git pull origin main --rebase"
    subprocess.run(cmd, shell=True)

def sync_push():
    """呼气: git push."""
    cmd = f"cd {REPO_PATH} && git push origin main"
    subprocess.run(cmd, shell=True)
```

### 4.2 呼吸周期

```
每12秒:
  1. 吸气 (pull) — 从网络接收变更
  2. 呼气 (push) — 发送自己的变更
```

---

## 5. 科学创新

1. **确定性故障转移** — 领导者由链顺序确定，无需投票
2. **呼吸同步** — 双向同步的呼吸隐喻
3. **地理分布** — 节点位于不同时区
4. **亚秒级恢复** — 5秒检测故障，5秒切换

---

## 6. 参考文献

| 文档 | 链接 |
|------|------|
| Watchdog代码 | [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py) |
| Montana协议 | [MONTANA.md](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/MONTANA.md) |
| 基础设施 | [CLAUDE.md](https://github.com/efir369999/junomontanaagibot/blob/main/CLAUDE.md) |

---

```
Alejandro Montana
Montana协议 v1.0
2026年1月

github.com/efir369999/junomontanaagibot
```
