#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine script directory dynamically
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Define potential VENV paths
POTENTIAL_VENVS=(
    "$SCRIPT_DIR/venv"
    "$SCRIPT_DIR/../venv_junona3"
    "$PROJECT_ROOT/venv_junona3"
    "/root/projects/venv_junona3"
    "/root/montana/montana_bot/venv"
)

# Find VENV directory
VENV_DIR=""
for venv in "${POTENTIAL_VENVS[@]}"; do
    if [ -f "$venv/bin/python3" ]; then
        VENV_DIR="$venv"
        break
    fi
done

if [ -z "$VENV_DIR" ]; then
    echo -e "${RED}Ошибка: Python venv не найден!${NC}"
    echo "Проверены пути:"
    for venv in "${POTENTIAL_VENVS[@]}"; do
        echo "  - $venv"
    done
    exit 1
fi

LOG_DIR="$SCRIPT_DIR/logs"
BOT_SCRIPT="run_bot.py"
KEY_TMP="/tmp/montana_bot_key.tmp"

echo -e "${GREEN}=== Запуск Montana Verified Users Bot ===${NC}"
echo -e "${GREEN}Рабочая директория: $SCRIPT_DIR${NC}"
echo -e "${GREEN}VENV: $VENV_DIR${NC}"

# Check Python file
if [ ! -f "$SCRIPT_DIR/$BOT_SCRIPT" ]; then
    echo -e "${RED}Ошибка: Файл $BOT_SCRIPT не найден в $SCRIPT_DIR!${NC}"
    exit 1
fi

# Bitwarden Session Key
echo -e "${YELLOW}Введите ключ сессии Bitwarden (нажмите Enter если используется .env):${NC}"
read -s SESSION_KEY

# Create logs dir
mkdir -p "$LOG_DIR"

# Construct command using venv activation
CMD="cd \"$VENV_DIR\" && source bin/activate && cd \"$SCRIPT_DIR\" && python3 \"$BOT_SCRIPT\""

if [ -n "$SESSION_KEY" ]; then
    echo -e "${YELLOW}Запуск Montana Bot с ключом сессии...${NC}"
    echo "$SESSION_KEY" > "$KEY_TMP"
    nohup bash -c "$CMD < \"$KEY_TMP\"" > "$LOG_DIR/montana_bot.log" 2>&1 &
else
    echo -e "${YELLOW}Запуск Montana Bot (без ключа сессии, ожидается .env)...${NC}"
    nohup bash -c "$CMD" > "$LOG_DIR/montana_bot.log" 2>&1 &
fi

# PID
BOT_PID=$!
echo $BOT_PID > "$LOG_DIR/montana_bot.pid"

echo -e "${GREEN}Montana Bot успешно запущен в фоновом режиме!${NC}"
echo -e "${GREEN}PID процесса: $BOT_PID${NC}"
echo -e "${GREEN}Логи: $LOG_DIR/montana_bot.log${NC}"
echo -e "${YELLOW}Для остановки: ./stop_montana_bot.sh${NC}"
echo -e "${YELLOW}Для просмотра логов: tail -f \"$LOG_DIR/montana_bot.log\"${NC}"

# Check status
echo -e "${YELLOW}Проверка запуска через 3 секунды...${NC}"
sleep 3
if ps -p $BOT_PID > /dev/null; then
   echo -e "${GREEN}Процесс $BOT_PID работает.${NC}"
else
   echo -e "${RED}Процесс $BOT_PID остановлен! Проверьте логи:${NC}"
   head -n 20 "$LOG_DIR/montana_bot.log"
fi
