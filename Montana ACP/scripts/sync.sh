#!/bin/bash
# Montana Auto-Sync Script
# Синхронизирует локальный репо с remote автоматически
# Запускать через cron каждую минуту: * * * * * /path/to/sync.sh

set -e

REPO_DIR="${1:-/Users/kh./Python/ACP_1}"
LOCK_FILE="/tmp/montana_sync.lock"
LOG_FILE="/tmp/montana_sync.log"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$REPO_DIR"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $1" >> "$LOG_FILE"
}

# Fetch remote changes
git fetch origin main 2>/dev/null || {
    log "WARN: fetch failed, skipping"
    exit 0
}

# Check for local changes
LOCAL_CHANGES=$(git status --porcelain)
BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo "0")

# If remote has changes, pull them
if [ "$BEHIND" -gt 0 ]; then
    log "Pulling $BEHIND commits from origin"
    git pull --rebase origin main 2>/dev/null || {
        log "ERROR: pull failed, manual intervention needed"
        exit 1
    }
fi

# If local has uncommitted changes, commit them
if [ -n "$LOCAL_CHANGES" ]; then
    log "Auto-committing local changes"
    git add -A
    git commit -m "AUTO-SYNC: $(date -u '+%Y-%m-%d %H:%M UTC')

Co-Authored-By: Montana Sync <sync@montana.local>" 2>/dev/null || true
    AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo "0")
fi

# If local is ahead, push
if [ "$AHEAD" -gt 0 ]; then
    log "Pushing $AHEAD commits to origin"
    git push origin main 2>/dev/null || {
        log "WARN: push failed, will retry"
    }
fi

log "Sync complete: behind=$BEHIND ahead=$AHEAD local_changes=${LOCAL_CHANGES:+yes}"
