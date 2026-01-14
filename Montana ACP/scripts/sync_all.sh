#!/bin/bash
# Montana Full Network Sync
# Синхронизация всех узлов сети
#
# Топология:
#   Локально (Mac) ↔ Москва (176.124.208.93)
#   Локально (Mac) ↔ GitHub
#   Амстердам (72.56.102.240) ↔ GitHub

set -e

# === КОНФИГУРАЦИЯ ===
LOCAL_DIR="/Users/kh./Python/ACP_1"
MOSCOW="root@176.124.208.93"
MOSCOW_DIR="/root/ACP_1"
AMSTERDAM="root@72.56.102.240"
AMSTERDAM_DIR="/root/ACP_1"

EXCLUDE="--exclude=.git --exclude=*.pyc --exclude=__pycache__ --exclude=.DS_Store --exclude=venv/ --exclude=node_modules/ --exclude='Bitcoin Core*'"

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $1"; }

# === СИНХРОНИЗАЦИЯ ===

sync_rsync() {
    local FROM="$1"
    local TO="$2"
    log "RSYNC: $FROM → $TO"
    rsync -avz --delete $EXCLUDE "$FROM" "$TO" 2>/dev/null || log "WARN: rsync failed $FROM → $TO"
}

sync_git() {
    cd "$LOCAL_DIR"

    # Pull
    log "GIT: Pull from origin"
    git fetch origin main 2>/dev/null || true
    git pull --rebase origin main 2>/dev/null || true

    # Commit if changes
    if [ -n "$(git status --porcelain)" ]; then
        log "GIT: Committing changes"
        git add -A
        git commit -m "SYNC: $(date -u '+%Y-%m-%d %H:%M UTC')" 2>/dev/null || true
    fi

    # Push
    log "GIT: Push to origin"
    git push origin main 2>/dev/null || log "WARN: git push failed"
}

# === ГЛАВНАЯ ЛОГИКА ===

log "=========================================="
log "  MONTANA NETWORK SYNC"
log "=========================================="

# 1. Москва → Локально
log "--- MOSCOW → LOCAL ---"
ssh $MOSCOW "mkdir -p $MOSCOW_DIR" 2>/dev/null || true
sync_rsync "$MOSCOW:$MOSCOW_DIR/" "$LOCAL_DIR/"

# 2. Амстердам → Локально
log "--- AMSTERDAM → LOCAL ---"
ssh $AMSTERDAM "mkdir -p $AMSTERDAM_DIR" 2>/dev/null || true
sync_rsync "$AMSTERDAM:$AMSTERDAM_DIR/" "$LOCAL_DIR/"

# 3. Git sync (GitHub ↔ Локально)
log "--- GITHUB SYNC ---"
sync_git

# 4. Локально → Москва
log "--- LOCAL → MOSCOW ---"
sync_rsync "$LOCAL_DIR/" "$MOSCOW:$MOSCOW_DIR/"

# 5. Локально → Амстердам
log "--- LOCAL → AMSTERDAM ---"
sync_rsync "$LOCAL_DIR/" "$AMSTERDAM:$AMSTERDAM_DIR/"

log "=========================================="
log "  SYNC COMPLETE"
log "=========================================="
