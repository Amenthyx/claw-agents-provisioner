#!/usr/bin/env bash
# ===================================================================
# rotate-secrets.sh — Automated Secret Rotation for Claw Agents
# ===================================================================
#
# Wraps claw_vault.py rotation commands for scheduled execution
# (e.g., via cron, systemd timer, or CI pipeline).
#
# Actions:
#   1. Check which secrets are due for rotation
#   2. Clear expired grace periods
#   3. Rotate due secrets (auto-generate or from environment)
#   4. Log results to rotation audit log
#   5. Optionally notify via webhook
#
# Usage:
#   bash scripts/rotate-secrets.sh                    # Interactive mode
#   bash scripts/rotate-secrets.sh --auto             # Auto-generate values
#   bash scripts/rotate-secrets.sh --check            # Check only (no rotate)
#   bash scripts/rotate-secrets.sh --auto --notify    # Auto + webhook notify
#
# Cron example (check daily at 2 AM):
#   0 2 * * * cd /opt/claw && bash scripts/rotate-secrets.sh --auto --notify
#
# Environment:
#   CLAW_VAULT_PASSWORD — Vault password (required for non-interactive)
#   CLAW_ALERT_WEBHOOK_URL — Webhook URL for rotation notifications
#   CLAW_ROTATE_<KEY> — Pre-set new value for a specific key
# ===================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default paths
VAULT_FILE="${CLAW_VAULT_FILE:-${PROJECT_ROOT}/secrets.vault}"
POLICY_FILE="${CLAW_ROTATION_POLICY:-${PROJECT_ROOT}/rotation-policy.json}"
PASSWORD_FILE="${CLAW_PASSWORD_FILE:-}"
PYTHON="${CLAW_PYTHON:-python3}"
VAULT_CMD="${PROJECT_ROOT}/shared/claw_vault.py"

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BOLD='' NC=''
fi

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Parse arguments ──────────────────────────────────────────────────

AUTO_MODE=false
CHECK_ONLY=false
NOTIFY=false

for arg in "$@"; do
    case "${arg}" in
        --auto)    AUTO_MODE=true ;;
        --check)   CHECK_ONLY=true ;;
        --notify)  NOTIFY=true ;;
        --help|-h)
            echo "Usage: $0 [--auto] [--check] [--notify] [--help]"
            echo "  --auto    Auto-generate new secret values"
            echo "  --check   Check rotation status only (no changes)"
            echo "  --notify  Send webhook notification on rotation"
            echo "  --help    Show this help"
            exit 0
            ;;
        *)
            error "Unknown argument: ${arg}"
            exit 1
            ;;
    esac
done

# ── Validation ───────────────────────────────────────────────────────

echo -e "${BOLD}=== Claw Secret Rotation ===${NC}"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

if [ ! -f "${VAULT_CMD}" ]; then
    error "Vault CLI not found: ${VAULT_CMD}"
    exit 1
fi

if [ ! -f "${VAULT_FILE}" ]; then
    error "Vault file not found: ${VAULT_FILE}"
    error "Initialize with: ${PYTHON} ${VAULT_CMD} init"
    exit 1
fi

if [ "${AUTO_MODE}" = true ] && [ -z "${CLAW_VAULT_PASSWORD:-}" ]; then
    error "CLAW_VAULT_PASSWORD must be set for --auto mode"
    exit 1
fi

# Build common args
COMMON_ARGS="--vault-file ${VAULT_FILE}"
if [ -n "${PASSWORD_FILE}" ]; then
    COMMON_ARGS="${COMMON_ARGS} --password-file ${PASSWORD_FILE}"
fi

# ── Initialize policy if missing ─────────────────────────────────────

if [ ! -f "${POLICY_FILE}" ]; then
    info "Rotation policy not found — initializing..."
    ${PYTHON} "${VAULT_CMD}" ${COMMON_ARGS} rotation-init \
        --policy "${POLICY_FILE}" \
        --rotation-days 90 \
        --grace-hours 24
    echo ""
fi

# ── Check rotation status ───────────────────────────────────────────

info "Checking rotation status..."
echo ""
${PYTHON} "${VAULT_CMD}" ${COMMON_ARGS} rotation-status \
    --policy "${POLICY_FILE}"
echo ""

if [ "${CHECK_ONLY}" = true ]; then
    info "Check-only mode — exiting without changes"
    exit 0
fi

# ── Perform rotation ────────────────────────────────────────────────

ROTATE_ARGS="--policy ${POLICY_FILE}"

if [ "${AUTO_MODE}" = true ]; then
    ROTATE_ARGS="${ROTATE_ARGS} --force --auto-generate"
fi

info "Starting secret rotation..."
echo ""

ROTATION_OUTPUT=$(${PYTHON} "${VAULT_CMD}" ${COMMON_ARGS} rotate-secrets \
    ${ROTATE_ARGS} 2>&1) || true

echo "${ROTATION_OUTPUT}"
echo ""

# ── Post-rotation status ────────────────────────────────────────────

info "Post-rotation status:"
echo ""
${PYTHON} "${VAULT_CMD}" ${COMMON_ARGS} rotation-status \
    --policy "${POLICY_FILE}"

# ── Webhook notification ────────────────────────────────────────────

if [ "${NOTIFY}" = true ]; then
    WEBHOOK_URL="${CLAW_ALERT_WEBHOOK_URL:-}"

    if [ -z "${WEBHOOK_URL}" ]; then
        warn "CLAW_ALERT_WEBHOOK_URL not set — skipping notification"
    else
        info "Sending rotation notification..."

        # Extract rotation summary
        ROTATED_COUNT=$(echo "${ROTATION_OUTPUT}" | grep -oP '\d+(?= rotated)' || echo "0")
        SKIPPED_COUNT=$(echo "${ROTATION_OUTPUT}" | grep -oP '\d+(?= skipped)' || echo "0")

        PAYLOAD=$(cat <<JSONEOF
{
    "event": "secret_rotation",
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "hostname": "$(hostname)",
    "summary": "Secret rotation completed: ${ROTATED_COUNT} rotated, ${SKIPPED_COUNT} skipped",
    "rotated": ${ROTATED_COUNT},
    "skipped": ${SKIPPED_COUNT}
}
JSONEOF
)

        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "${PAYLOAD}" \
            --max-time 10 \
            2>/dev/null || echo "000")

        if [ "${HTTP_CODE}" -ge 200 ] && [ "${HTTP_CODE}" -lt 300 ]; then
            info "Webhook notification sent (HTTP ${HTTP_CODE})"
        else
            warn "Webhook notification failed (HTTP ${HTTP_CODE})"
        fi
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
info "Secret rotation complete"
