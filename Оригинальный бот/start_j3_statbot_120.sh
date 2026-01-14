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
    "$SCRIPT_DIR/../Montana ACP/venv_junona3"
    "$PROJECT_ROOT/venv_junona3"
    "$SCRIPT_DIR/../venv_junona3"
    "/root/projects/venv_junona3"
)

# Find VENV and Python executable
VENV_PYTHON=""
for venv in "${POTENTIAL_VENVS[@]}"; do
    if [ -f "$venv/bin/python3" ]; then
        VENV_PYTHON="$venv/bin/python3"
        VENV_DIR="$venv"
        break
    fi
done

if [ -z "$VENV_PYTHON" ]; then
    echo -e "${RED}Ошибка: Python venv не найден!${NC}"
    echo "Проверены пути:"
    for venv in "${POTENTIAL_VENVS[@]}"; do
        echo "  - $venv"
    done
    exit 1
fi

LOG_DIR="$SCRIPT_DIR/logs"
BOT_SCRIPT="j3_statbot_120.py"

echo -e "${GREEN}=== Запуск j3_statbot_120 ===${NC}"
echo -e "${GREEN}Рабочая директория: $SCRIPT_DIR${NC}"
echo -e "${GREEN}Python: $VENV_PYTHON${NC}"

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

# Construct command using direct python path (avoids broken 'activate' scripts)
# We execute inside SCRIPT_DIR
CMD="cd \"$SCRIPT_DIR\" && \"$VENV_PYTHON\" \"$BOT_SCRIPT\""

if [ -n "$SESSION_KEY" ]; then
    echo -e "${YELLOW}Запуск j3_statbot_120 с ключом сессии...${NC}"
    nohup bash -c "$CMD <<< \"$SESSION_KEY\"" > "$LOG_DIR/j3_statbot_120.log" 2>&1 &
else
    echo -e "${YELLOW}Запуск j3_statbot_120 (без ключа сессии)...${NC}"
    nohup bash -c "$CMD" > "$LOG_DIR/j3_statbot_120.log" 2>&1 &
fi

# PID
BOT_PID=$!
echo $BOT_PID > "$LOG_DIR/j3_statbot_120.pid"

echo -e "${GREEN}j3_statbot_120 успешно запущен в фоновом режиме!${NC}"
echo -e "${GREEN}PID процесса: $BOT_PID${NC}"
echo -e "${GREEN}Логи: $LOG_DIR/j3_statbot_120.log${NC}"
echo -e "${YELLOW}Для просмотра логов: tail -f \"$LOG_DIR/j3_statbot_120.log\"${NC}"

# Check status
echo -e "${YELLOW}Проверка запуска через 3 секунды...${NC}"
sleep 3
if ps -p $BOT_PID > /dev/null; then
   echo -e "${GREEN}Процесс $BOT_PID работает.${NC}"
else
   echo -e "${RED}Процесс $BOT_PID остановлен! Проверьте логи:${NC}"
   head -n 20 "$LOG_DIR/j3_statbot_120.log"
fi
