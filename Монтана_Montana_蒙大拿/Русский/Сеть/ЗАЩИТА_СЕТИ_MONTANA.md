# Montana Protocol — Security Specification
# Техническая спецификация защиты сети

**Version:** 2.0
**Status:** MAINNET
**Date:** 2026-01-23
**Authors:** Alejandro Montana

---

## Abstract

Montana Protocol представляет собой распределённую систему консенсуса, основанную на доказательстве присутствия во времени (Atemporal Coordinate Presence, ACP). Настоящая спецификация описывает криптографические, сетевые и программные защитные механизмы протокола.

Базовые защитные механизмы:
- **ML-DSA-65 (FIPS 204)** — постквантовая цифровая подпись
- **5-Node Leader Election** — распределённое управление без единой точки отказа
- **Attack Detection + Random Failover** — обнаружение атак и непредсказуемое переключение мастера
- **Breathing Sync** — git-синхронизация состояния сети
- **Temporal Coordinates (τ₁, τ₂, τ₃, τ₄)** — иерархические временные единицы
- **Halving Mechanism** — дефляционная эмиссия
- **AtlantGuard** — защита узла от ресурсных атак

---

## 1. Топология сети

### 1.1 Узлы сети

Montana Protocol функционирует на 5 географически распределённых узлах:

| Позиция | Узел | IP | Регион | Роль |
|---------|------|-----|--------|------|
| 0 | amsterdam | 72.56.102.240 | EU | PRIMARY |
| 1 | moscow | 176.124.208.93 | RU-Central | MIRROR 1 |
| 2 | almaty | 91.200.148.93 | KZ | MIRROR 2 |
| 3 | spb | 188.225.58.98 | RU-NW | MIRROR 3 |
| 4 | novosibirsk | 147.45.147.247 | RU-Siberia | MIRROR 4 |

**Исходный код:** [leader_election.py:39-46](Бот/leader_election.py#L39-L46)

```python
BOT_CHAIN: List[Tuple[str, str]] = [
    ("amsterdam",   "72.56.102.240"),
    ("moscow",      "176.124.208.93"),
    ("almaty",      "91.200.148.93"),
    ("spb",         "188.225.58.98"),
    ("novosibirsk", "147.45.147.247"),
]
```

### 1.2 Конфигурация узлов

Каждый узел идентифицируется через переменную окружения `MONTANA_NODE_NAME`:

```ini
[Service]
Environment="MONTANA_NODE_NAME=moscow"
Environment="PYTHONUNBUFFERED=1"
WatchdogSec=60
Restart=always
RestartSec=15
TimeoutStopSec=30
MemoryMax=512M
MemoryHigh=400M
```

**Исходный код:** [junona.service](Бот/junona.service)

---

## 2. Криптографическая безопасность

### 2.1 ML-DSA-65 (FIPS 204)

Montana Protocol использует постквантовый алгоритм подписи ML-DSA-65 (Module Lattice Digital Signature Algorithm), стандартизованный NIST как FIPS 204.

| Параметр | Значение |
|----------|----------|
| Алгоритм | ML-DSA-65 (Dilithium) |
| Стандарт | FIPS 204 |
| Уровень безопасности | NIST Level 3 |
| Private Key | 4032 байта |
| Public Key | 1952 байта |
| Signature | 3309 байт |
| Адрес | `mt` + SHA256(pubkey)[:20].hex() = 42 символа |

**Исходный код:** [node_crypto.py](Бот/node_crypto.py)

### 2.2 Формат адреса

```python
def generate_address(public_key: bytes) -> str:
    """Генерация Montana адреса из публичного ключа ML-DSA-65."""
    hash_bytes = hashlib.sha256(public_key).digest()[:20]
    return "mt" + hash_bytes.hex()  # mt + 40 hex chars = 42 total
```

Пример адреса: `mt7a3f2e1d4c5b6a8f9e0d1c2b3a4f5e6d7c8b9a0`

---

## 3. Leader Election

### 3.1 Алгоритм выбора мастера

Детерминированный алгоритм определения активного мастера:

```python
def am_i_the_master(self) -> bool:
    """Проверяет, является ли текущий узел мастером."""
    for name, ip in self.chain:
        if name == self.node_name:
            return True  # Дошли до себя — я мастер
        if check_node_health(ip):
            return False  # Узел выше жив — он мастер
    return False
```

**Исходный код:** [leader_election.py:326-349](Бот/leader_election.py#L326-L349)

### 3.2 Health Check

Проверка здоровья узла выполняется через HTTP endpoint на порту 8889:

```python
def check_node_health(ip: str) -> bool:
    """Проверяет здоровье узла через HTTP health endpoint."""
    try:
        url = f"http://{ip}:8889/health"
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except:
        return False
```

**Исходный код:** [leader_election.py:102-134](Бот/leader_election.py#L102-L134)

### 3.3 Интервалы проверки

| Параметр | Значение | Назначение |
|----------|----------|------------|
| CHECK_INTERVAL | 5 сек | Интервал проверки здоровья узлов |
| STARTUP_DELAY | 7-15 сек | Задержка при старте (избежание конфликта polling) |
| FAILOVER_TIME | < 10 сек | Время переключения на резервный узел |

---

## 4. Обнаружение атак

### 4.1 AttackDetector

Класс `AttackDetector` отслеживает метрики, указывающие на атаку:

```python
class AttackDetector:
    def __init__(self):
        self.failure_count = 0
        self.max_failures = 10
        self.response_times = deque(maxlen=10)
        self.cpu_threshold = 80.0
        self.response_time_threshold = 5.0
        self.network_threshold = 100 * 1024 * 1024  # 100 MB/s
        self.under_attack = False
```

**Исходный код:** [leader_election.py:190-232](Бот/leader_election.py#L190-L232)

### 4.2 Метрики обнаружения атак

| Метрика | Порог | Действие |
|---------|-------|----------|
| CPU Usage | > 80% | Флаг атаки |
| Network Traffic | > 100 MB/s входящего | Флаг атаки |
| Failure Count | > 10 подряд | Флаг атаки |
| Response Time (avg) | > 5 секунд | Флаг атаки |

### 4.3 Random Failover при атаке

При обнаружении атаки цепочка узлов перемешивается случайным образом:

```python
def shuffle_chain_on_attack(self, external_trigger: bool = False):
    """Перемешивает цепочку при обнаружении атаки."""
    if not self.attack_detector.is_under_attack() and not external_trigger:
        return

    logger.warning("АТАКА ОБНАРУЖЕНА! Переход на случайный failover")

    shuffled = list(self.chain)
    random.shuffle(shuffled)

    healthy_nodes = [
        (name, ip) for (name, ip) in shuffled
        if check_node_health(ip)
    ]

    if healthy_nodes:
        self.chain = healthy_nodes
        self.chain_shuffled = True
```

**Исходный код:** [leader_election.py:395-430](Бот/leader_election.py#L395-L430)

---

## 5. AtlantGuard — Защита узла

### 5.1 Архитектура

Класс `AtlantGuard` обеспечивает локальную защиту узла от ресурсных атак:

```python
class AtlantGuard:
    def __init__(self):
        self.start_time = time.time()
        self.request_log = {}
        self.registration_log = []
        self.suspicious_ips = set()
        self.blocked_ips = set()
        self.cpu_history = []  # Буфер последних 5 измерений CPU
        self.degraded_count = 0  # Счётчик высоких значений подряд
```

**Исходный код:** [junomontanaagibot.py:709-754](Бот/junomontanaagibot.py#L709-L754)

### 5.2 Health Check с защитой от ложных срабатываний

Метод `health_check()` использует скользящее среднее CPU для предотвращения ложных алертов:

```python
def health_check(self) -> Dict[str, Any]:
    # Скользящее среднее CPU (последние 5 измерений)
    cpu_instant = psutil.cpu_percent(interval=None)
    self.cpu_history.append(cpu_instant)
    if len(self.cpu_history) > 5:
        self.cpu_history.pop(0)
    cpu_avg = sum(self.cpu_history) / len(self.cpu_history)

    # Защита от ложных спайков: требуем 3 подряд высоких значения
    if cpu_avg > 90 or memory.percent > 90:
        self.degraded_count += 1
        if self.degraded_count >= 3:
            status = "degraded"
        else:
            status = "healthy"
    else:
        status = "healthy"
        self.degraded_count = 0
```

**Исходный код:** [junomontanaagibot.py:1001-1051](Бот/junomontanaagibot.py#L1001-L1051)

### 5.3 Пороги AtlantGuard

| Метрика | Порог | Статус |
|---------|-------|--------|
| CPU (среднее за 5 измерений) | > 90% | degraded (после 3 подряд) |
| Memory | > 90% | degraded (после 3 подряд) |
| Suspicious IPs | > 5 | degraded |
| Under attack flag | true | under_attack |

### 5.4 Rate Limiting

```python
MAX_REQUESTS_PER_MINUTE = 60   # Запросов/мин с одного источника
MAX_REGISTRATIONS_PER_HOUR = 20  # Новых регистраций/час
MAX_NODE_SYNCS_PER_MINUTE = 10   # Синхронизаций узла/мин
MAX_API_CALLS_PER_MINUTE = 100   # API вызовов/мин на endpoint
```

**Исходный код:** [junomontanaagibot.py:734-738](Бот/junomontanaagibot.py#L734-L738)

---

## 6. Breathing Sync

### 6.1 Механизм синхронизации

Git-синхронизация состояния сети каждые 12 секунд:

```
Цикл:
  Вдох (Inhale) — git pull с rebase
    ↓
  12 секунд работы
    ↓
  Выдох (Exhale) — git add + commit + push
    ↓
  Повтор
```

**Исходный код:** [breathing_sync.py](Бот/breathing_sync.py)

### 6.2 Интеграция с Leader Election

Breathing Sync активируется только для мастер-узла:

```python
only_when_master=True
is_master_func=lambda: self.is_master
```

---

## 7. Временные координаты

### 7.1 Иерархия

| Единица | Длительность | Назначение |
|---------|--------------|------------|
| **τ₁** | 60 секунд | Интервал подписи Presence Proof |
| **τ₂** | 600 секунд (10 минут) | Слайс эмиссии |
| **τ₃** | 1,209,600 секунд (14 дней) | Checkpoint |
| **τ₄** | 126,144,000 секунд (4 года) | Эпоха халвинга |

### 7.2 Соотношения

```
1 τ₄ = 104 τ₃ = 209,664 τ₂ = 126,144,000 секунд
1 τ₃ = 2016 τ₂ = 1,209,600 секунд
1 τ₂ = 10 τ₁ = 600 секунд
```

**Исходный код:** [time_bank.py:44-80](Бот/time_bank.py#L44-L80)

---

## 8. TIME_BANK

### 8.1 Резерв

```python
BANK_TOTAL_MINUTES = 21_000_000        # 21 млн минут (~40 лет)
BANK_TOTAL_SECONDS = 1_260_000_000     # 1.26 млрд секунд
```

### 8.2 Halving

```python
def halving_coefficient(tau4_count: int) -> float:
    """Коэффициент халвинга для текущей эпохи."""
    return 1.0 / (2 ** tau4_count)
```

| Эпоха τ₄ | Годы | Коэффициент | 1 секунда = |
|----------|------|-------------|-------------|
| 0 | 0-4 | 1.0 | 1.0 Ɉ |
| 1 | 4-8 | 0.5 | 0.5 Ɉ |
| 2 | 8-12 | 0.25 | 0.25 Ɉ |
| 3 | 12-16 | 0.125 | 0.125 Ɉ |

**Исходный код:** [time_bank.py:88-113](Бот/time_bank.py#L88-L113)

---

## 9. Синхронизация сети

### 9.1 Состояние на 2026-01-23

| Узел | MD5 Hash | Статус | Python | telegram-bot |
|------|----------|--------|--------|--------------|
| amsterdam | 5a0ac1903151eef7a85cd72f3060eb6c | active | 3.12.3 | 22.5 |
| moscow | 5a0ac1903151eef7a85cd72f3060eb6c | active | 3.12.3 | 22.5 |
| almaty | 5a0ac1903151eef7a85cd72f3060eb6c | active | 3.12.3 | 22.5 |
| spb | 5a0ac1903151eef7a85cd72f3060eb6c | active | 3.12.3 | 22.5 |
| novosibirsk | 5a0ac1903151eef7a85cd72f3060eb6c | active | 3.12.3 | 22.5 |

### 9.2 Деплой

Rolling deploy выполняется скриптом `deploy_nodes.sh`:

```bash
./deploy_nodes.sh           # Rolling deploy (по одному)
./deploy_nodes.sh --fast    # Быстрый deploy (опасно)
./deploy_nodes.sh --node moscow  # Только один узел
```

**Исходный код:** [deploy_nodes.sh](Бот/deploy_nodes.sh)

---

## 10. Файловая структура

```
Монтана_Montana_蒙大拿/Русский/Бот/
├── junomontanaagibot.py   # Главный бот (229 KB)
├── leader_election.py      # Leader Election + AttackDetector
├── time_bank.py            # TIME_BANK + Presence Proofs
├── node_crypto.py          # ML-DSA-65 криптография
├── breathing_sync.py       # Git синхронизация
├── montana_db.py           # База данных + Event Sourcing
├── junona_ai.py            # AI интеграция (OpenAI/Anthropic)
├── contracts.py            # Смарт-контракты времени
├── deploy_nodes.sh         # Скрипт деплоя
└── junona.service          # Systemd unit
```

---

## 11. Известные ограничения

| Проблема | Severity | Статус |
|----------|----------|--------|
| Split-brain через local lock | HIGH | Требует distributed lock |
| tau4_count не персистит | MEDIUM | Сбрасывается при рестарте |
| time.time() может быть изменён root | LOW | Требует time.monotonic() + NTP |
| Presence Proofs не верифицируются | MEDIUM | Генерируются, но не проверяются |

---

## Заключение

Montana Protocol реализует многоуровневую защиту:

1. **Постквантовая криптография (ML-DSA-65)** — защита от квантовых компьютеров
2. **5-Node Leader Election** — отсутствие единой точки отказа
3. **AtlantGuard со скользящим средним** — защита от ложных алертов
4. **Random Failover** — непредсказуемость при атаке
5. **Breathing Sync** — консистентность состояния сети

---

```
Alejandro Montana
Montana Protocol Security Specification v2.0
2026-01-23
```
