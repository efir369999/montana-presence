# ВСЕ КЛЮЧИ MONTANA + ПРАВИЛА ИСПОЛЬЗОВАНИЯ

## Быстрый старт
```bash
source GET_ALL_KEYS.sh    # Загрузить все ключи в env
bash SETUP_SSH.sh         # Восстановить SSH
```

---

# API KEYS

## TELEGRAM_TOKEN_JUNONA
**Назначение:** Токен бота @junomontanaagibot
**Правила:**
- Использовать ТОЛЬКО для Telegram Bot API
- НЕ публиковать в коде — только из keychain
- При утечке: /revoke через @BotFather
```bash
security find-generic-password -a "montana" -s "TELEGRAM_TOKEN_JUNONA" -w
```

## OPENAI_API_KEY
**Назначение:** GPT-4o для AI функций бота
**Правила:**
- Использовать для OpenAI API calls
- Лимиты: следить за usage на platform.openai.com
- При утечке: rotate на dashboard
```bash
security find-generic-password -a "montana" -s "OPENAI_API_KEY" -w
```

## ANTHROPIC_API_KEY
**Назначение:** Claude для AI функций
**Правила:**
- Резервный AI провайдер
- Использовать если OpenAI недоступен
```bash
security find-generic-password -a "montana" -s "ANTHROPIC_API_KEY" -w
```

## GITHUB_TOKEN
**Назначение:** Доступ к репо efir369999/-_Nothing_-
**Правила:**
- git push/pull операции
- Создание releases
- НЕ давать write access третьим лицам
```bash
security find-generic-password -a "montana" -s "GITHUB_TOKEN" -w
```

## ADMIN_TELEGRAM_ID
**Назначение:** ID владельца для админ-команд бота
**Правила:**
- Только этот ID может: /admin, /broadcast, /stats
- НЕ менять без крайней необходимости
```bash
security find-generic-password -a "montana" -s "ADMIN_TELEGRAM_ID" -w
```

## AI_PROVIDER
**Назначение:** Текущий AI провайдер (openai/anthropic)
**Правила:**
- Менять через бота или напрямую
- Влияет на какой API используется
```bash
security find-generic-password -a "montana" -s "AI_PROVIDER" -w
```

---

# ВСЕ УЗЛЫ СЕТИ (6 штук)

## NODE 1: Amsterdam (Главный)
**IP:** 72.56.102.240
**Роль:** P2P координатор, первичный узел
**Правила:**
- Бот работает здесь
- git remote "amsterdam"
- Критичный узел — мониторить 24/7
```bash
security find-generic-password -a "montana" -s "NODE_1_IP" -w
ssh root@72.56.102.240
```

## NODE 2: Moscow (Timeweb)
**IP:** 176.124.208.93
**Роль:** Резервный узел, P2P
**Правила:**
- Требует passphrase при SSH
- Использовать ssh my-timeweb (из config)
```bash
security find-generic-password -a "montana" -s "NODE_2_IP" -w
ssh my-timeweb  # или ssh root@176.124.208.93
```

## NODE 3
**IP:** 91.200.148.93
**Роль:** P2P узел
**Правила:**
- Сетевой узел
- Автономная работа
```bash
security find-generic-password -a "montana" -s "NODE_3_IP" -w
ssh root@91.200.148.93
```

## NODE 4
**IP:** 188.225.58.98
**Роль:** P2P узел
**Правила:**
- Сетевой узел
- Автономная работа
```bash
security find-generic-password -a "montana" -s "NODE_4_IP" -w
ssh root@188.225.58.98
```

## NODE 5
**IP:** 147.45.147.247
**Роль:** P2P узел
**Правила:**
- Сетевой узел
- Автономная работа
```bash
security find-generic-password -a "montana" -s "NODE_5_IP" -w
ssh root@147.45.147.247
```

## NODE 6
**IP:** 185.221.152.242
**Роль:** P2P узел
**Правила:**
- Сетевой узел
- Автономная работа
```bash
security find-generic-password -a "montana" -s "NODE_6_IP" -w
ssh root@185.221.152.242
```

---

# SSH KEYS

## SSH_KEY_ED25519
**Назначение:** GitHub авторизация
**Правила:**
- git операции с GitHub
- НЕ использовать для серверов
```bash
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PRIVATE" -w | base64 -d
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PUBLIC" -w
```

## SSH_KEY_JN_SRV
**Назначение:** Доступ к серверам (особенно Timeweb)
**Правила:**
- ЗАШИФРОВАН паролем (passphrase)
- Использовать для ssh my-timeweb
```bash
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PRIVATE" -w | base64 -d
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w
```

## SSH_CONFIG
**Назначение:** Конфигурация ~/.ssh/config
**Правила:**
- Содержит алиасы: my-timeweb, montana-ams
- Восстановить при новой установке
```bash
security find-generic-password -a "montana" -s "SSH_CONFIG" -w | base64 -d
```

---

# БЫСТРЫЕ КОМАНДЫ

## Подключение ко ВСЕМ узлам
```bash
ssh root@72.56.102.240     # Amsterdam (NODE 1)
ssh my-timeweb             # Moscow (NODE 2, нужен passphrase)
ssh root@91.200.148.93     # NODE 3
ssh root@188.225.58.98     # NODE 4
ssh root@147.45.147.247    # NODE 5
ssh root@185.221.152.242   # NODE 6
```

## Управление keychain
```bash
# Добавить
security add-generic-password -a "montana" -s "ИМЯ" -w "ЗНАЧЕНИЕ"

# Обновить
security add-generic-password -a "montana" -s "ИМЯ" -w "НОВОЕ" -U

# Удалить
security delete-generic-password -a "montana" -s "ИМЯ"

# Список всех montana ключей
security dump-keychain | grep -A2 "montana"
```
