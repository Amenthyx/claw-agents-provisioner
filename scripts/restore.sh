#!/usr/bin/env bash
# =============================================================================
# Claw Agents Provisioner -- Backup Restore Script
# =============================================================================
# Restores data from a backup archive created by backup.sh.
# Supports full restore or selective restore of specific categories.
#
# Usage:
#   ./scripts/restore.sh <backup-archive>              # Full restore
#   ./scripts/restore.sh <backup-archive> --db-only    # Databases only
#   ./scripts/restore.sh <backup-archive> --config-only # Config only
#   ./scripts/restore.sh <backup-archive> --dry-run    # Preview only
#   ./scripts/restore.sh --list                        # List available backups
#
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_OUTPUT:-$PROJECT_ROOT/backups}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# -----------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------
log() { echo -e "  ${GREEN}[restore]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[restore]${NC} $1"; }
err() { echo -e "  ${RED}[restore]${NC} $1" >&2; }

# -----------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------
ARCHIVE=""
MODE="full"
DRY_RUN=false
LIST_MODE=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-only)     MODE="db"; shift ;;
        --config-only) MODE="config"; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --list)        LIST_MODE=true; shift ;;
        --force)       FORCE=true; shift ;;
        --help|-h)
            echo "Usage: $0 <backup-archive> [--db-only|--config-only] [--dry-run] [--force]"
            echo "       $0 --list"
            exit 0
            ;;
        *)
            if [ -z "$ARCHIVE" ]; then
                ARCHIVE="$1"
            else
                err "Unknown option: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# -----------------------------------------------------------------------
# List available backups
# -----------------------------------------------------------------------
if [ "$LIST_MODE" = true ]; then
    echo ""
    echo -e "  ${BOLD}Available Backups${NC}"
    echo -e "  ${DIM}-----------------------------------${NC}"

    if [ -d "$BACKUP_DIR/daily" ]; then
        echo -e "  ${BOLD}Daily:${NC}"
        find "$BACKUP_DIR/daily" -name "claw-backup-*.tar.gz" -type f -printf '    %T@ %Tc  %s  %f\n' 2>/dev/null | \
            sort -rn | cut -d' ' -f2- | head -20 || echo "    (none)"
    fi

    if [ -d "$BACKUP_DIR/weekly" ]; then
        echo ""
        echo -e "  ${BOLD}Weekly:${NC}"
        find "$BACKUP_DIR/weekly" -name "claw-backup-*-weekly.tar.gz" -type f -printf '    %T@ %Tc  %s  %f\n' 2>/dev/null | \
            sort -rn | cut -d' ' -f2- | head -20 || echo "    (none)"
    fi

    echo ""
    exit 0
fi

# -----------------------------------------------------------------------
# Validate archive
# -----------------------------------------------------------------------
if [ -z "$ARCHIVE" ]; then
    err "Backup archive path is required."
    echo "  Usage: $0 <backup-archive> [options]"
    echo "  Run '$0 --list' to see available backups."
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    # Try looking in backup directories
    for search_dir in "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR"; do
        if [ -f "$search_dir/$ARCHIVE" ]; then
            ARCHIVE="$search_dir/$ARCHIVE"
            break
        fi
    done

    if [ ! -f "$ARCHIVE" ]; then
        err "Archive not found: $ARCHIVE"
        exit 1
    fi
fi

log "Archive: $ARCHIVE"
log "Mode: $MODE"
if [ "$DRY_RUN" = true ]; then
    warn "DRY RUN -- no files will be modified"
fi

# -----------------------------------------------------------------------
# Extract to staging area
# -----------------------------------------------------------------------
STAGING_DIR="$BACKUP_DIR/.restore-staging"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

log "Extracting archive..."
tar -xzf "$ARCHIVE" -C "$STAGING_DIR"

# Find the backup directory inside staging (should be claw-backup-TIMESTAMP)
BACKUP_CONTENT_DIR=$(find "$STAGING_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)
if [ -z "$BACKUP_CONTENT_DIR" ]; then
    err "Archive appears empty or malformed."
    rm -rf "$STAGING_DIR"
    exit 1
fi

# -----------------------------------------------------------------------
# Read and display manifest
# -----------------------------------------------------------------------
MANIFEST="$BACKUP_CONTENT_DIR/backup-manifest.json"
if [ -f "$MANIFEST" ]; then
    echo ""
    echo -e "  ${BOLD}Backup Manifest${NC}"
    echo -e "  ${DIM}-----------------------------------${NC}"
    # Parse JSON without jq (bash-only)
    while IFS='"' read -r _ key _ value _; do
        if [ -n "$key" ] && [ -n "$value" ]; then
            printf "  %-14s %s\n" "$key:" "$value"
        fi
    done < <(grep -E '^\s*"' "$MANIFEST" | sed 's/[,{}]//g')
    echo ""
fi

# -----------------------------------------------------------------------
# Confirm restore (unless --force or --dry-run)
# -----------------------------------------------------------------------
if [ "$DRY_RUN" = false ] && [ "$FORCE" = false ]; then
    echo -e "  ${YELLOW}WARNING: This will overwrite existing files.${NC}"
    read -rp "  Continue? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log "Restore cancelled."
        rm -rf "$STAGING_DIR"
        exit 0
    fi
fi

# -----------------------------------------------------------------------
# Restore databases
# -----------------------------------------------------------------------
RESTORED=0

if [ "$MODE" = "full" ] || [ "$MODE" = "db" ]; then
    if [ -d "$BACKUP_CONTENT_DIR/databases" ]; then
        log "Restoring databases..."

        find "$BACKUP_CONTENT_DIR/databases" -type f \( -name "*.sqlite3" -o -name "*.db" \) | while read -r dbfile; do
            # Reconstruct relative path
            rel_path="${dbfile#$BACKUP_CONTENT_DIR/databases/}"
            dest="$PROJECT_ROOT/$rel_path"
            dest_dir="$(dirname "$dest")"

            if [ "$DRY_RUN" = true ]; then
                log "  [DRY RUN] Would restore: $rel_path"
            else
                mkdir -p "$dest_dir"
                # Create backup of current file before overwriting
                if [ -f "$dest" ]; then
                    cp "$dest" "${dest}.pre-restore" 2>/dev/null || true
                fi
                cp "$dbfile" "$dest"
                log "  + $rel_path"
            fi
            RESTORED=$((RESTORED + 1))
        done
    else
        warn "No database files found in backup."
    fi
fi

# -----------------------------------------------------------------------
# Restore configuration
# -----------------------------------------------------------------------
if [ "$MODE" = "full" ] || [ "$MODE" = "config" ]; then
    if [ -d "$BACKUP_CONTENT_DIR/config" ]; then
        log "Restoring configuration files..."

        # Port map
        if [ -f "$BACKUP_CONTENT_DIR/config/port_map.json" ]; then
            dest="$PROJECT_ROOT/data/port_map.json"
            if [ "$DRY_RUN" = true ]; then
                log "  [DRY RUN] Would restore: data/port_map.json"
            else
                mkdir -p "$PROJECT_ROOT/data"
                cp "$BACKUP_CONTENT_DIR/config/port_map.json" "$dest"
                log "  + data/port_map.json"
            fi
            RESTORED=$((RESTORED + 1))
        fi

        # Instance configs
        if [ -d "$BACKUP_CONTENT_DIR/config/claws" ]; then
            if [ "$DRY_RUN" = true ]; then
                CLAW_COUNT=$(find "$BACKUP_CONTENT_DIR/config/claws" -name "*.json" -type f 2>/dev/null | wc -l)
                log "  [DRY RUN] Would restore: data/claws/ (${CLAW_COUNT} files)"
            else
                mkdir -p "$PROJECT_ROOT/data/claws"
                find "$BACKUP_CONTENT_DIR/config/claws" -name "*.json" -type f -exec cp {} "$PROJECT_ROOT/data/claws/" \;
                CLAW_COUNT=$(find "$BACKUP_CONTENT_DIR/config/claws" -name "*.json" -type f 2>/dev/null | wc -l)
                log "  + data/claws/ (${CLAW_COUNT} files)"
                RESTORED=$((RESTORED + CLAW_COUNT))
            fi
        fi

        # Strategy config
        if [ -f "$BACKUP_CONTENT_DIR/config/strategy.json" ]; then
            if [ "$DRY_RUN" = true ]; then
                log "  [DRY RUN] Would restore: strategy.json"
            else
                cp "$BACKUP_CONTENT_DIR/config/strategy.json" "$PROJECT_ROOT/strategy.json"
                log "  + strategy.json"
            fi
            RESTORED=$((RESTORED + 1))
        fi

        # Hardware profile
        if [ -f "$BACKUP_CONTENT_DIR/config/hardware_profile.json" ]; then
            if [ "$DRY_RUN" = true ]; then
                log "  [DRY RUN] Would restore: hardware_profile.json"
            else
                cp "$BACKUP_CONTENT_DIR/config/hardware_profile.json" "$PROJECT_ROOT/hardware_profile.json"
                log "  + hardware_profile.json"
            fi
            RESTORED=$((RESTORED + 1))
        fi

        # Shared configs
        if [ -d "$BACKUP_CONTENT_DIR/config/shared" ]; then
            find "$BACKUP_CONTENT_DIR/config/shared" -name "*.json" -type f | while read -r cfg; do
                fname="$(basename "$cfg")"
                if [ "$DRY_RUN" = true ]; then
                    log "  [DRY RUN] Would restore: shared/$fname"
                else
                    cp "$cfg" "$PROJECT_ROOT/shared/$fname"
                    log "  + shared/$fname"
                fi
                RESTORED=$((RESTORED + 1))
            done
        fi
    else
        warn "No configuration files found in backup."
    fi
fi

# -----------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------
rm -rf "$STAGING_DIR"

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
if [ "$DRY_RUN" = true ]; then
    echo -e "  ${BOLD}Dry Run Complete${NC}"
else
    echo -e "  ${BOLD}Restore Complete${NC}"
fi
echo -e "  ${DIM}-----------------------------------${NC}"
echo -e "  Archive:   $(basename "$ARCHIVE")"
echo -e "  Mode:      ${MODE}"
echo -e "  Files:     ${RESTORED}"
echo ""

if [ "$DRY_RUN" = false ]; then
    log "Pre-restore backups saved as *.pre-restore where applicable."
    log "Verify services are working: ./claw.sh status"
fi
