#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine script directory dynamically
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOG_DIR/montana_bot.pid"

echo -e "${YELLOW}=== Остановка Montana Verified Users Bot ===${NC}"

if [ -f "$PID_FILE" ]; then
    BOT_PID=$(cat "$PID_FILE")
    if ps -p $BOT_PID > /dev/null 2>&1; then
        kill $BOT_PID
        echo -e "${GREEN}Montana Bot (PID: $BOT_PID) остановлен${NC}"
        rm -f "$PID_FILE"
    else
        echo -e "${YELLOW}Процесс с PID $BOT_PID не найден${NC}"
        rm -f "$PID_FILE"
    fi
else
    echo -e "${YELLOW}PID файл не найден, ищу процесс...${NC}"
    pkill -f "python.*run_bot.py" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Montana Bot остановлен${NC}"
    else
        echo -e "${RED}Montana Bot не запущен${NC}"
    fi
fi
