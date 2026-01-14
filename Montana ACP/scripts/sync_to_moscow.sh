#!/bin/bash
#
# Montana Node Sync — Москва (First Full Node)
# =============================================
#
# Синхронизация локальной папки с сервером Timeweb.
#
# ЗАКОН: Один ключ, одна подпись, один раз.
# Москва = первый Full Node сети Montana.
#
# Использование:
#   ./sync_to_moscow.sh          # Полная синхронизация
#   ./sync_to_moscow.sh --dry    # Только показать что будет синхронизировано
#   ./sync_to_moscow.sh --watch  # Автоматическая синхронизация при изменениях
#

set -e

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

SERVER_IP="176.124.208.93"
SERVER_USER="root"
SERVER_PATH="/root/montana"

LOCAL_PATH="/Users/kh./Python/ACP_1/Montana ACP"

# Исключаемые файлы/папки
EXCLUDES=(
    ".git"
    "target"
    ".DS_Store"
    "*.pyc"
    "__pycache__"
    "venv*"
    "*.egg-info"
    ".idea"
    ".vscode"
    "montana-data"
    "*.log"
    "*.tmp"
)

# ============================================================================
# ФУНКЦИИ
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $1"
}

build_excludes() {
    local excludes=""
    for ex in "${EXCLUDES[@]}"; do
        excludes="$excludes --exclude='$ex'"
    done
    echo "$excludes"
}

sync_to_server() {
    local dry_run=""
    if [[ "$1" == "--dry" ]]; then
        dry_run="--dry-run"
        log "DRY RUN — показываю что будет синхронизировано"
    fi

    log "Синхронизация: $LOCAL_PATH → $SERVER_USER@$SERVER_IP:$SERVER_PATH"

    # Собираем команду rsync
    eval rsync -avz --progress --delete \
        $dry_run \
        $(build_excludes) \
        "\"$LOCAL_PATH/\"" \
        "$SERVER_USER@$SERVER_IP:$SERVER_PATH/"

    if [[ -z "$dry_run" ]]; then
        log "Синхронизация завершена"
    fi
}

sync_from_server() {
    log "Синхронизация: $SERVER_USER@$SERVER_IP:$SERVER_PATH → $LOCAL_PATH"

    eval rsync -avz --progress \
        $(build_excludes) \
        "$SERVER_USER@$SERVER_IP:$SERVER_PATH/" \
        "\"$LOCAL_PATH/\""

    log "Загрузка с сервера завершена"
}

watch_and_sync() {
    log "Запуск автоматической синхронизации (Ctrl+C для остановки)"
    log "Отслеживаю изменения в: $LOCAL_PATH"

    # Проверяем наличие fswatch
    if ! command -v fswatch &> /dev/null; then
        echo "Ошибка: fswatch не установлен."
        echo "Установи: brew install fswatch"
        exit 1
    fi

    # Первая синхронизация
    sync_to_server

    # Мониторинг изменений
    fswatch -o "$LOCAL_PATH" \
        --exclude "\.git" \
        --exclude "target" \
        --exclude "__pycache__" \
        --exclude "\.DS_Store" \
        --exclude "venv" \
        | while read -r _; do
            log "Обнаружены изменения, синхронизирую..."
            sync_to_server
        done
}

show_status() {
    log "Проверка сервера: $SERVER_IP"

    ssh -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP "
        echo '=== Сервер ==='
        hostname
        echo ''
        echo '=== Montana папка ==='
        ls -la $SERVER_PATH 2>/dev/null || echo 'Папка не найдена'
        echo ''
        echo '=== Место на диске ==='
        df -h / | tail -1
        echo ''
        echo '=== Rust версия ==='
        rustc --version 2>/dev/null || echo 'Rust не установлен'
    "
}

show_help() {
    echo "Montana Node Sync — Москва (First Full Node)"
    echo ""
    echo "Использование:"
    echo "  $0              Полная синхронизация на сервер"
    echo "  $0 --dry        Показать что будет синхронизировано (без изменений)"
    echo "  $0 --watch      Автоматическая синхронизация при изменениях"
    echo "  $0 --pull       Загрузить изменения с сервера"
    echo "  $0 --status     Показать статус сервера"
    echo "  $0 --help       Показать эту справку"
    echo ""
    echo "Сервер: $SERVER_USER@$SERVER_IP:$SERVER_PATH"
    echo "Локальная папка: $LOCAL_PATH"
}

# ============================================================================
# MAIN
# ============================================================================

case "${1:-}" in
    --dry)
        sync_to_server --dry
        ;;
    --watch)
        watch_and_sync
        ;;
    --pull)
        sync_from_server
        ;;
    --status)
        show_status
        ;;
    --help|-h)
        show_help
        ;;
    "")
        sync_to_server
        ;;
    *)
        echo "Неизвестная опция: $1"
        show_help
        exit 1
        ;;
esac
