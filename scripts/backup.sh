#!/usr/bin/env bash
# =============================================================================
# Claw Agents Provisioner -- Automated Backup Script
# =============================================================================
# Creates timestamped backup archives of all critical data:
#   - SQLite databases (memory, billing, audit, orchestrator, DAL)
#   - Port maps (data/port_map.json)
#   - Instance configs (data/claws/*.json)
#   - Agent configurations
#   - Environment template
#
# Rotation policy:
#   - Keep last 7 daily backups
#   - Keep last 4 weekly backups (Sundays)
#
# Usage:
#   ./scripts/backup.sh                    # Full backup
#   ./scripts/backup.sh --db-only          # Database files only
#   ./scripts/backup.sh --config-only      # Config files only
#   ./scripts/backup.sh --output /custom   # Custom output directory
#
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_OUTPUT:-$PROJECT_ROOT/backups}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
DAY_OF_WEEK="$(date +%u)"  # 1=Mon, 7=Sun
BACKUP_NAME="claw-backup-${TIMESTAMP}"

# Retention
DAILY_KEEP=7
WEEKLY_KEEP=4

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# -----------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------
MODE="full"
QUIET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-only)    MODE="db"; shift ;;
        --config-only) MODE="config"; shift ;;
        --output)     BACKUP_DIR="$2"; shift 2 ;;
        --quiet)      QUIET=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--db-only|--config-only] [--output DIR] [--quiet]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# -----------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------
log() {
    if [ "$QUIET" = false ]; then
        echo -e "  ${GREEN}[backup]${NC} $1"
    fi
}

warn() {
    echo -e "  ${YELLOW}[backup]${NC} $1"
}

err() {
    echo -e "  ${RED}[backup]${NC} $1" >&2
}

# -----------------------------------------------------------------------
# Create backup directory
# -----------------------------------------------------------------------
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
STAGING_DIR="$BACKUP_DIR/.staging/${BACKUP_NAME}"

mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$STAGING_DIR"

log "Starting ${MODE} backup: ${BACKUP_NAME}"
log "Project root: ${PROJECT_ROOT}"

# -----------------------------------------------------------------------
# Collect files
# -----------------------------------------------------------------------
FILE_COUNT=0

# --- SQLite databases ---
if [ "$MODE" = "full" ] || [ "$MODE" = "db" ]; then
    log "Collecting SQLite databases..."
    mkdir -p "$STAGING_DIR/databases"

    # Find all .sqlite3 and .db files in project
    for db_pattern in "*.sqlite3" "*.db"; do
        while IFS= read -r -d '' dbfile; do
            # Skip if in node_modules, .git, venv, etc.
            case "$dbfile" in
                */node_modules/*|*/.git/*|*/venv/*|*/.venv/*) continue ;;
            esac

            # Use sqlite3 .backup if available, otherwise copy
            rel_path="${dbfile#$PROJECT_ROOT/}"
            dest_dir="$STAGING_DIR/databases/$(dirname "$rel_path")"
            mkdir -p "$dest_dir"

            if command -v sqlite3 &>/dev/null; then
                # Hot backup -- safe even if database is in use
                sqlite3 "$dbfile" ".backup '$dest_dir/$(basename "$dbfile")'" 2>/dev/null || \
                    cp "$dbfile" "$dest_dir/" 2>/dev/null || true
            else
                cp "$dbfile" "$dest_dir/" 2>/dev/null || true
            fi
            FILE_COUNT=$((FILE_COUNT + 1))
            log "  + ${rel_path}"
        done < <(find "$PROJECT_ROOT" -maxdepth 3 -name "$db_pattern" -type f -print0 2>/dev/null)
    done
fi

# --- Configuration files ---
if [ "$MODE" = "full" ] || [ "$MODE" = "config" ]; then
    log "Collecting configuration files..."
    mkdir -p "$STAGING_DIR/config"

    # Port map
    if [ -f "$PROJECT_ROOT/data/port_map.json" ]; then
        cp "$PROJECT_ROOT/data/port_map.json" "$STAGING_DIR/config/"
        FILE_COUNT=$((FILE_COUNT + 1))
        log "  + data/port_map.json"
    fi

    # Instance configs (claw definitions)
    if [ -d "$PROJECT_ROOT/data/claws" ]; then
        mkdir -p "$STAGING_DIR/config/claws"
        find "$PROJECT_ROOT/data/claws" -name "*.json" -type f -exec cp {} "$STAGING_DIR/config/claws/" \; 2>/dev/null
        CLAW_COUNT=$(find "$STAGING_DIR/config/claws" -name "*.json" -type f 2>/dev/null | wc -l)
        FILE_COUNT=$((FILE_COUNT + CLAW_COUNT))
        log "  + data/claws/ (${CLAW_COUNT} files)"
    fi

    # Strategy config
    if [ -f "$PROJECT_ROOT/strategy.json" ]; then
        cp "$PROJECT_ROOT/strategy.json" "$STAGING_DIR/config/"
        FILE_COUNT=$((FILE_COUNT + 1))
        log "  + strategy.json"
    fi

    # Environment template (not .env -- never backup secrets)
    if [ -f "$PROJECT_ROOT/.env.template" ]; then
        cp "$PROJECT_ROOT/.env.template" "$STAGING_DIR/config/"
        FILE_COUNT=$((FILE_COUNT + 1))
        log "  + .env.template"
    fi

    # Hardware profile
    if [ -f "$PROJECT_ROOT/hardware_profile.json" ]; then
        cp "$PROJECT_ROOT/hardware_profile.json" "$STAGING_DIR/config/"
        FILE_COUNT=$((FILE_COUNT + 1))
        log "  + hardware_profile.json"
    fi

    # Shared config files
    mkdir -p "$STAGING_DIR/config/shared"
    for cfg in "$PROJECT_ROOT/shared/"*.json; do
        if [ -f "$cfg" ]; then
            cp "$cfg" "$STAGING_DIR/config/shared/"
            FILE_COUNT=$((FILE_COUNT + 1))
            log "  + shared/$(basename "$cfg")"
        fi
    done
fi

# -----------------------------------------------------------------------
# Create backup metadata
# -----------------------------------------------------------------------
cat > "$STAGING_DIR/backup-manifest.json" <<EOF
{
  "backup_name": "${BACKUP_NAME}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "mode": "${MODE}",
  "file_count": ${FILE_COUNT},
  "project_root": "${PROJECT_ROOT}",
  "hostname": "$(hostname)",
  "git_commit": "$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(cd "$PROJECT_ROOT" && git branch --show-current 2>/dev/null || echo 'unknown')"
}
EOF

# -----------------------------------------------------------------------
# Create compressed archive
# -----------------------------------------------------------------------
log "Creating compressed archive..."
ARCHIVE_PATH="$DAILY_DIR/${BACKUP_NAME}.tar.gz"

(cd "$BACKUP_DIR/.staging" && tar -czf "$ARCHIVE_PATH" "$BACKUP_NAME")

ARCHIVE_SIZE=$(du -sh "$ARCHIVE_PATH" | cut -f1)
log "Archive created: ${ARCHIVE_PATH} (${ARCHIVE_SIZE})"

# -----------------------------------------------------------------------
# Weekly backup (copy to weekly dir on Sundays)
# -----------------------------------------------------------------------
if [ "$DAY_OF_WEEK" = "7" ]; then
    WEEKLY_ARCHIVE="$WEEKLY_DIR/${BACKUP_NAME}-weekly.tar.gz"
    cp "$ARCHIVE_PATH" "$WEEKLY_ARCHIVE"
    log "Weekly backup created: ${WEEKLY_ARCHIVE}"
fi

# -----------------------------------------------------------------------
# Cleanup staging
# -----------------------------------------------------------------------
rm -rf "$BACKUP_DIR/.staging"

# -----------------------------------------------------------------------
# Rotation -- remove old backups
# -----------------------------------------------------------------------
log "Applying retention policy..."

# Daily: keep last N
DAILY_COUNT=$(find "$DAILY_DIR" -name "claw-backup-*.tar.gz" -type f 2>/dev/null | wc -l)
if [ "$DAILY_COUNT" -gt "$DAILY_KEEP" ]; then
    REMOVE_COUNT=$((DAILY_COUNT - DAILY_KEEP))
    find "$DAILY_DIR" -name "claw-backup-*.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | \
        sort -n | head -n "$REMOVE_COUNT" | cut -d' ' -f2- | \
        xargs rm -f 2>/dev/null || true
    log "  Removed ${REMOVE_COUNT} old daily backup(s)"
fi

# Weekly: keep last N
WEEKLY_COUNT=$(find "$WEEKLY_DIR" -name "claw-backup-*-weekly.tar.gz" -type f 2>/dev/null | wc -l)
if [ "$WEEKLY_COUNT" -gt "$WEEKLY_KEEP" ]; then
    REMOVE_COUNT=$((WEEKLY_COUNT - WEEKLY_KEEP))
    find "$WEEKLY_DIR" -name "claw-backup-*-weekly.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | \
        sort -n | head -n "$REMOVE_COUNT" | cut -d' ' -f2- | \
        xargs rm -f 2>/dev/null || true
    log "  Removed ${REMOVE_COUNT} old weekly backup(s)"
fi

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
echo -e "  ${BOLD}Backup Complete${NC}"
echo -e "  ${DIM}-----------------------------------${NC}"
echo -e "  Name:      ${BACKUP_NAME}"
echo -e "  Mode:      ${MODE}"
echo -e "  Files:     ${FILE_COUNT}"
echo -e "  Size:      ${ARCHIVE_SIZE}"
echo -e "  Archive:   ${ARCHIVE_PATH}"
echo -e "  Daily:     $(find "$DAILY_DIR" -name "*.tar.gz" -type f 2>/dev/null | wc -l) / ${DAILY_KEEP} max"
echo -e "  Weekly:    $(find "$WEEKLY_DIR" -name "*.tar.gz" -type f 2>/dev/null | wc -l) / ${WEEKLY_KEEP} max"
echo ""
