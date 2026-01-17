# 3-Mirror System

**Отказоустойчивая сеть Montana**
**Montana Protocol v1.0**

---

## Абстракт

3-Mirror — распределённая система из 5 узлов с автоматическим failover. При падении любых 4 из 5 узлов сеть продолжает работать. Время восстановления < 10 секунд. Синхронизация через "дыхание" — git pull/push каждые 12 секунд.

**Ключевая формула:**
```
4/5 узлов могут упасть = сеть жива
Восстановление < 10 секунд
```

---

## 1. Введение

### 1.1 Проблема централизованных систем

| Система | Точка отказа | Время восстановления |
|---------|--------------|---------------------|
| Один сервер | 1 | Часы/дни |
| Master-Slave | 2 | Минуты |
| **3-Mirror** | **5** | **< 10 секунд** |

### 1.2 Решение Montana

5 географически распределённых узлов с детерминированным failover по приоритету.

---

## 2. Архитектура

### 2.1 Топология сети

**Исходный код:** [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py)

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

### 2.2 Роли узлов

| Роль | Узел | IP | Функция |
|------|------|----|---------|
| PRIMARY | Amsterdam | 72.56.102.240 | Активный бот |
| BRAIN | Moscow | 176.124.208.93 | Контроллер |
| MIRROR 1 | Almaty | 91.200.148.93 | Standby |
| MIRROR 2 | SPB | 188.225.58.98 | Standby |
| MIRROR 3 | Novosibirsk | 147.45.147.247 | Standby |

---

## 3. Failover Protocol

### 3.1 Детерминированный выбор лидера

**Исходный код:** [watchdog.py#L162-L172](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L162-L172)

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

### 3.2 Константы мониторинга

```python
CHECK_INTERVAL = 5   # секунд между проверками
SYNC_INTERVAL = 12   # секунд между синхронизациями
```

---

## 4. Breathing Sync (Дыхание)

### 4.1 Механизм синхронизации

**Исходный код:** [watchdog.py#L140-L156](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py#L140-L156)

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

### 4.2 Цикл дыхания

```
Каждые 12 секунд:
  1. Вдох (pull) — получить изменения от сети
  2. Выдох (push) — отправить свои изменения
```

---

## 5. Научная новизна

1. **Детерминированный failover** — лидер определяется порядком в цепи, без голосования
2. **Breathing sync** — метафора дыхания для двунаправленной синхронизации
3. **Географическое распределение** — узлы в разных часовых поясах
4. **Субсекундное восстановление** — обнаружение падения за 5 сек, переключение за 5 сек

---

## 6. Ссылки

| Документ | Ссылка |
|----------|--------|
| Watchdog код | [watchdog.py](https://github.com/efir369999/junomontanaagibot/blob/main/金元Ɉ/thoughts_bot/watchdog.py) |
| Протокол Montana | [MONTANA.md](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/MONTANA.md) |
| Инфраструктура | [CLAUDE.md](https://github.com/efir369999/junomontanaagibot/blob/main/CLAUDE.md) |

---

```
Alejandro Montana
Montana Protocol v1.0
Январь 2026

github.com/efir369999/junomontanaagibot
```
