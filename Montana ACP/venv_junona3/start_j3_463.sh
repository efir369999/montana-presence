#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Запуск j3_463 ===${NC}"

# Проверка существования виртуального окружения
if [ ! -d "/root/projects/venv_junona3/bin" ]; then
    echo -e "${RED}Ошибка: Виртуальное окружение не найдено!${NC}"
    exit 1
fi

# Проверка существования Python файла
if [ ! -f "/root/projects/venv_junona3/j3_463.py" ]; then
    echo -e "${RED}Ошибка: Файл j3_463.py не найден!${NC}"
    exit 1
fi

# Запрос ключа сессии
echo -e "${YELLOW}Введите ключ сессии для j3_463:${NC}"
read -s SESSION_KEY

# Проверка, что ключ введен
if [ -z "$SESSION_KEY" ]; then
    echo -e "${RED}Ошибка: Ключ сессии не может быть пустым!${NC}"
    exit 1
fi

# Создание директории для логов
mkdir -p /root/projects/venv_junona3/logs

# Запуск скрипта с передачей ключа через echo и pipe
echo -e "${YELLOW}Запуск j3_463 в фоновом режиме...${NC}"

# Создаем временный файл с ключом
echo "$SESSION_KEY" > /tmp/j3_463_key.tmp

# Запуск с передачей ключа через stdin
nohup bash -c "cd /root/projects/venv_junona3/ && source bin/activate && python3 j3_463.py < /tmp/j3_463_key.tmp" > /root/projects/venv_junona3/logs/j3_463.log 2>&1 &

# Получение PID процесса
BOT_PID=$!

# Удаляем временный файл через 5 секунд
(sleep 5 && rm -f /tmp/j3_463_key.tmp) &

# Сохранение PID в файл
echo $BOT_PID > /root/projects/venv_junona3/logs/j3_463.pid

echo -e "${GREEN}j3_463 успешно запущен в фоновом режиме!${NC}"
echo -e "${GREEN}PID процесса: $BOT_PID${NC}"
echo -e "${GREEN}Логи: /root/projects/venv_junona3/logs/j3_463.log${NC}"
echo -e "${YELLOW}Для остановки: ./stop_j3_463.sh${NC}"
echo -e "${YELLOW}Для просмотра логов: tail -f /root/projects/venv_junona3/logs/j3_463.log${NC}"

# Показать первые несколько строк логов через 3 секунды
echo -e "${YELLOW}Проверка запуска через 3 секунды...${NC}"
sleep 3
if [ -f "/root/projects/venv_junona3/logs/j3_463.log" ]; then
    echo -e "${GREEN}Первые строки логов:${NC}"
    head -n 10 /root/projects/venv_junona3/logs/j3_463.log
fi
