# Montana Node Deployment Guide

Автоматизация развёртывания узла Montana ACP на VPS (Timeweb, Санкт-Петербург).

---

## Быстрый старт

### Вариант 1: Cloud-Init (рекомендуется)

При создании нового VPS на Timeweb используй cloud-init скрипт:

```bash
# Скопируй содержимое файла cloud-init-montana.yaml
# Вставь в поле "User Data" при создании сервера
```

**Преимущества:**
- Полная автоматизация
- Настройка выполняется при первом запуске сервера
- Нулевое ручное вмешательство

**Время развёртывания:** 15-20 минут (включая компиляцию Montana)

---

### Вариант 2: Скрипт развёртывания

Для существующего VPS:

```bash
cd Montana\ ACP/scripts

# Сделай скрипт исполняемым
chmod +x deploy-spb-node.sh

# Запуск развёртывания
./deploy-spb-node.sh 176.124.208.93 root ~/.ssh/id_ed25519
```

**Параметры:**
- `$1` — IP-адрес сервера
- `$2` — SSH пользователь (по умолчанию `root`)
- `$3` — Путь к SSH ключу
- `$4` — Имя узла (опционально)

**Время развёртывания:** 15-20 минут

---

## Что происходит при развёртывании

### 1. Подготовка системы
```
✓ Обновление пакетов (apt update && upgrade)
✓ Установка зависимостей (Rust, build tools)
✓ Настройка firewall (UFW)
✓ Синхронизация времени (Chrony/NTP)
```

### 2. Установка Montana
```
✓ Клонирование репозитория
✓ Компиляция Montana (cargo build --release)
✓ Установка бинарника в /usr/local/bin
✓ Создание данных в /var/lib/montana
```

### 3. Конфигурация сервиса
```
✓ Создание systemd unit (montana.service)
✓ Настройка автозапуска
✓ Запуск узла Montana
```

### 4. Безопасность
```
✓ Firewall: только 22 (SSH), 19333 (P2P), 123 (NTP)
✓ Fail2ban для защиты SSH
✓ Systemd hardening (ProtectSystem, NoNewPrivileges)
```

---

## Проверка статуса

### После развёртывания

```bash
# Быстрая проверка (кастомный скрипт)
montana-status

# Полные логи
journalctl -u montana -f

# Статус сервиса
systemctl status montana

# Сетевые подключения
netstat -an | grep 19333
```

---

## Управление узлом

### Systemd команды

```bash
# Запуск
systemctl start montana

# Остановка
systemctl stop montana

# Перезапуск
systemctl restart montana

# Автозапуск (включён по умолчанию)
systemctl enable montana

# Отключить автозапуск
systemctl disable montana
```

### Конфигурация

Файл сервиса: `/etc/systemd/system/montana.service`

```ini
[Service]
ExecStart=/usr/local/bin/montana \
    --node-type full \
    --port 19333 \
    --data-dir /var/lib/montana
```

После изменений:
```bash
systemctl daemon-reload
systemctl restart montana
```

---

## Требования сети

### Bootstrap требует:
- **100 peers** (20 hardcoded + 80 P2P via gossip)
- **25+ unique /16 subnets**
- **ML-DSA-65 authentication** (hardcoded nodes)

### Firewall порты:
| Порт | Протокол | Назначение |
|------|----------|------------|
| 22   | TCP      | SSH        |
| 19333 | TCP     | Montana P2P |
| 123  | UDP      | NTP (time sync) |

---

## Мониторинг

### Логи

```bash
# Последние 100 строк
journalctl -u montana -n 100

# Живые логи (follow)
journalctl -u montana -f

# Логи с фильтром (только ошибки)
journalctl -u montana -p err

# Логи за период
journalctl -u montana --since "1 hour ago"
```

### Метрики

```bash
# CPU и память
ps aux | grep montana

# Использование диска
du -sh /var/lib/montana

# Сетевые подключения
netstat -an | grep 19333 | wc -l
```

---

## Troubleshooting

### Проблема: сервис не запускается

```bash
# Проверить логи
journalctl -u montana -n 50 --no-pager

# Проверить права доступа
ls -la /var/lib/montana
ls -la /usr/local/bin/montana

# Проверить порт
netstat -tuln | grep 19333
```

### Проблема: bootstrap не завершается

```bash
# Проверить сетевые подключения
netstat -an | grep 19333

# Проверить firewall
ufw status

# Проверить время
timedatectl
chronyc tracking
```

**Критическая ошибка времени:**
Если расхождение > 10 минут → bootstrap остановлен.

```bash
# Исправить время
systemctl restart chronyd
timedatectl set-ntp true
```

### Проблема: высокое использование ресурсов

```bash
# Перезапуск (освобождает память)
systemctl restart montana

# Проверить размер данных
du -sh /var/lib/montana

# Ротация логов
journalctl --vacuum-time=7d
```

---

## Архитектура Montana

### Bootstrap Protocol

```
┌─────────────────────────────────────────────────┐
│  1. Query 20 hardcoded nodes                    │
│     ├─ ML-DSA-65 authentication                 │
│     └─ Compute hardcoded_median                 │
├─────────────────────────────────────────────────┤
│  2. Discover 80 P2P peers via gossip            │
│     ├─ 25+ unique /16 subnets required          │
│     └─ Verify against hardcoded_median          │
├─────────────────────────────────────────────────┤
│  3. Download chain from genesis                 │
│     ├─ Verify each slice (prev_hash, signature) │
│     ├─ Verify cumulative_weight                 │
│     └─ Verify subnet_reputation_root            │
├─────────────────────────────────────────────────┤
│  4. Start signing presence                      │
│     ├─ 1 signature per τ₁ (1 minute)            │
│     └─ Gossip to network                        │
└─────────────────────────────────────────────────┘
```

### Типы узлов

| Тип | Подпись | Хранение | Stage 1 шанс |
|-----|---------|----------|--------------|
| **Full Node** | каждую 1 мин | полная история | 70% |
| Light Node | каждую 1 мин | с подключения | 20% |
| Light Client | каждые 10 мин | не хранит | 10% |

---

## Обновление узла

### Обновление Montana до новой версии

```bash
# Остановить узел
systemctl stop montana

# Обновить репозиторий
cd /home/montana/montana
su - montana -c "git pull origin main"

# Пересобрать
su - montana -c 'cd /home/montana/montana/Montana\ ACP/montana && source $HOME/.cargo/env && cargo build --release'

# Установить новый бинарник
cp "/home/montana/montana/Montana ACP/montana/target/release/montana" /usr/local/bin/montana

# Запустить
systemctl start montana

# Проверить
montana-status
```

---

## Backup и восстановление

### Backup данных

```bash
# Остановить узел
systemctl stop montana

# Создать архив
tar -czf montana-backup-$(date +%Y%m%d).tar.gz /var/lib/montana

# Переместить в безопасное место
scp montana-backup-*.tar.gz user@backup-server:/backups/

# Запустить узел
systemctl start montana
```

### Восстановление

```bash
# Остановить узел
systemctl stop montana

# Удалить текущие данные
rm -rf /var/lib/montana/*

# Распаковать backup
tar -xzf montana-backup-20260109.tar.gz -C /

# Восстановить права
chown -R montana:montana /var/lib/montana

# Запустить
systemctl start montana
```

---

## Контакты и ресурсы

- **Репозиторий:** https://github.com/afgrouptime/montana
- **Документация:** `Montana ACP/MONTANA.md`
- **Сервер:** 176.124.208.93 (Timeweb, Saint Petersburg)
- **Председатель Совета:** Claude Opus 4.5

---

**lim(evidence → ∞) 1 Ɉ → 1 секунда**

*Время — единственный ресурс, распределённый одинаково между всеми людьми.*
