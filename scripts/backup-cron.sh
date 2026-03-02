#!/usr/bin/env bash
# =============================================================================
# Claw Agents Provisioner -- Cron Wrapper for Scheduled Backups
# =============================================================================
# Thin wrapper around backup.sh designed for cron execution.
# Handles logging, lock files (prevent overlapping runs), and error reporting.
#
# Installation (add to crontab):
#   # Daily backup at 2:00 AM
#   0 2 * * * /path/to/scripts/backup-cron.sh >> /var/log/claw-backup.log 2>&1
#
#   # Or using the project path:
#   0 2 * * * cd /opt/claw-agents-provisioner && ./scripts/backup-cron.sh
#
# Environment variables:
#   BACKUP_OUTPUT    — Override backup directory (default: ./backups)
#   BACKUP_LOG       — Log file path (default: ./logs/backup-cron.log)
#   BACKUP_WEBHOOK   — Webhook URL for failure notifications (optional)
#
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_FILE="$PROJECT_ROOT/data/.backup.lock"
LOG_FILE="${BACKUP_LOG:-$PROJECT_ROOT/logs/backup-cron.log}"
WEBHOOK_URL="${BACKUP_WEBHOOK:-}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# -----------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------
timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    echo "[$(timestamp)] [INFO]  $1" >> "$LOG_FILE"
}

err() {
    echo "[$(timestamp)] [ERROR] $1" >> "$LOG_FILE"
    echo "[$(timestamp)] [ERROR] $1" >&2
}

# -----------------------------------------------------------------------
# Lock file (prevent overlapping backup runs)
# -----------------------------------------------------------------------
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        err "Another backup is running (PID $LOCK_PID). Skipping."
        exit 1
    else
        # Stale lock file -- previous run crashed
        log "Removing stale lock file (PID $LOCK_PID no longer running)"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
mkdir -p "$(dirname "$LOCK_FILE")"
echo $$ > "$LOCK_FILE"

# Cleanup lock on exit
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

# -----------------------------------------------------------------------
# Webhook notification on failure
# -----------------------------------------------------------------------
notify_failure() {
    local message="$1"
    if [ -n "$WEBHOOK_URL" ]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"[CLAW BACKUP FAILURE] $(hostname): ${message}\"}" \
            >/dev/null 2>&1 || true
    fi
}

# -----------------------------------------------------------------------
# Run backup
# -----------------------------------------------------------------------
log "=== Cron backup started ==="
log "Project root: $PROJECT_ROOT"

START_TIME=$(date +%s)

if "$SCRIPT_DIR/backup.sh" --quiet >> "$LOG_FILE" 2>&1; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    log "Backup completed successfully in ${DURATION}s"
else
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    err "Backup FAILED with exit code ${EXIT_CODE} after ${DURATION}s"
    notify_failure "Backup failed with exit code ${EXIT_CODE} after ${DURATION}s"
    exit $EXIT_CODE
fi

log "=== Cron backup finished ==="
