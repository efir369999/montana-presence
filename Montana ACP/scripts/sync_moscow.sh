#!/bin/bash
# Синхронизация Локально ↔ Москва (176.124.208.93)
# Двусторонняя через rsync

REMOTE="root@176.124.208.93"
LOCAL_DIR="/Users/kh./Python/ACP_1"
REMOTE_DIR="/root/ACP_1"
LOCK="/tmp/sync_moscow.lock"

[ -f "$LOCK" ] && exit 0
touch "$LOCK"
trap "rm -f $LOCK" EXIT

log() { echo "[$(date -u '+%H:%M:%S UTC')] $1"; }

# Создать директорию на сервере если нет
ssh $REMOTE "mkdir -p $REMOTE_DIR" 2>/dev/null

# 1. Pull с сервера (что изменилось там)
log "PULL: Москва → Локально"
rsync -avz --delete \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    --exclude='venv/' \
    --exclude='node_modules/' \
    $REMOTE:$REMOTE_DIR/ $LOCAL_DIR/ 2>/dev/null

# 2. Push на сервер (что изменилось локально)
log "PUSH: Локально → Москва"
rsync -avz --delete \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    --exclude='venv/' \
    --exclude='node_modules/' \
    --exclude='Bitcoin Core*' \
    $LOCAL_DIR/ $REMOTE:$REMOTE_DIR/ 2>/dev/null

log "DONE: Синхронизация завершена"
