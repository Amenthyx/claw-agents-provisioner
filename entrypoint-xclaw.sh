#!/usr/bin/env bash
# =============================================================================
# XClaw All-in-One Entrypoint
# =============================================================================
# Starts the full XClaw stack inside the container:
#   1. Agent platform (stub or native binary)
#   2. Security gate (compiled rules)
#   3. Optimizer pipeline
#   4. Gateway router
#   5. Watchdog health monitor
#   6. Wizard API + Dashboard
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[xclaw]${NC} $1"; }
warn() { echo -e "${YELLOW}[xclaw]${NC} $1"; }

XCLAW_DIR="/opt/xclaw"
SHARED_DIR="${XCLAW_DIR}/shared"
DATA_DIR="${XCLAW_DIR}/data"

# Defaults from env
AGENT="${CLAW_AGENT:-zeroclaw}"
AGENT_PORT="${CLAW_AGENT_PORT:-3100}"
AGENT_NAME="${CLAW_AGENT_NAME:-xclaw-agent}"

# Track child PIDs for clean shutdown
PIDS=()

cleanup() {
    log "Shutting down all services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait
    log "All services stopped."
    exit 0
}
trap cleanup SIGTERM SIGINT

# ── Create .env if not exists ────────────────────────────────────────
if [ ! -f "${XCLAW_DIR}/.env" ] && [ -f "${XCLAW_DIR}/.env.template" ]; then
    cp "${XCLAW_DIR}/.env.template" "${XCLAW_DIR}/.env"
    log "Created .env from template"
fi

# Patch .env with runtime values
if [ -f "${XCLAW_DIR}/.env" ]; then
    sed -i "s|^CLAW_AGENT=.*|CLAW_AGENT=${AGENT}|" "${XCLAW_DIR}/.env" 2>/dev/null || true
    sed -i "s|^CLAW_AGENT_NAME=.*|CLAW_AGENT_NAME=${AGENT_NAME}|" "${XCLAW_DIR}/.env" 2>/dev/null || true
fi

log "=================================================="
log "  XClaw Isolated Environment"
log "  Agent:    ${AGENT} (${AGENT_NAME})"
log "  Port:     :${AGENT_PORT}"
log "=================================================="

# ── 0. Initialize Storage ────────────────────────────────────────────
log "[0/7] Initializing storage backends"
if [ -f "${SHARED_DIR}/claw_storage.py" ]; then
    python "${SHARED_DIR}/claw_storage.py" --init 2>/dev/null || warn "  Storage init skipped (no config yet)"
    log "  Storage initialized"
else
    warn "  Storage module not found — skipping"
fi

# ── 1. Start Agent Platform ──────────────────────────────────────────
log "[1/7] Starting agent: ${AGENT} on :${AGENT_PORT}"

# Try native entrypoint first, fall back to Python stub
AGENT_DIR="${XCLAW_DIR}/${AGENT}"
if [ -f "${AGENT_DIR}/entrypoint.sh" ]; then
    log "  Using native entrypoint: ${AGENT}/entrypoint.sh"
    bash "${AGENT_DIR}/entrypoint.sh" &
    PIDS+=($!)
elif [ -f "${SHARED_DIR}/claw_agent_stub.py" ]; then
    log "  Using Python agent stub on :${AGENT_PORT}"
    python "${SHARED_DIR}/claw_agent_stub.py" --port "${AGENT_PORT}" --name "${AGENT}" &
    PIDS+=($!)
else
    warn "  No agent binary or stub found — skipping"
fi

sleep 2

# ── 2. Start Security Gate ───────────────────────────────────────────
log "[2/7] Initializing security gate"
if [ -f "${SHARED_DIR}/claw_security.py" ]; then
    python "${SHARED_DIR}/claw_security.py" --init-config 2>/dev/null || true
    log "  Security rules compiled"
else
    warn "  Security module not found — skipping"
fi

# ── 3. Start Optimizer Pipeline ──────────────────────────────────────
log "[3/7] Starting optimizer on :9091"
if [ -f "${SHARED_DIR}/claw_optimizer.py" ]; then
    python "${SHARED_DIR}/claw_optimizer.py" -c "${SHARED_DIR}/optimization.json" &
    PIDS+=($!)
    sleep 1
    log "  Optimizer started"
else
    warn "  Optimizer not found — skipping"
fi

# ── 4. Start Gateway Router ─────────────────────────────────────────
log "[4/7] Starting gateway router on :9095"
if [ -f "${SHARED_DIR}/claw_router.py" ]; then
    python "${SHARED_DIR}/claw_router.py" --start --port 9095 &
    PIDS+=($!)
    sleep 1
    log "  Gateway router started"
else
    warn "  Router not found — skipping"
fi

# ── 5. Start Watchdog ────────────────────────────────────────────────
log "[5/7] Starting watchdog on :9097"
if [ -f "${SHARED_DIR}/claw_watchdog.py" ]; then
    # Generate watchdog config
    cat > "${DATA_DIR}/watchdog.json" <<WDEOF
{
    "check_interval": 30,
    "failure_threshold": 3,
    "alert_cooldown": 300,
    "auto_restart": true,
    "dashboard_port": 9097,
    "agents": [
        {
            "name": "${AGENT}-agent",
            "port": ${AGENT_PORT},
            "health_url": "http://localhost:${AGENT_PORT}/health",
            "auto_restart": true
        }
    ]
}
WDEOF
    python "${SHARED_DIR}/claw_watchdog.py" -c "${DATA_DIR}/watchdog.json" &
    PIDS+=($!)
    sleep 1
    log "  Watchdog started"
else
    warn "  Watchdog not found — skipping"
fi

# ── 6. Start Wizard API (serves dashboard endpoints too) ─────────────
log "[6/7] Starting wizard API on :9098"
if [ -f "${SHARED_DIR}/claw_wizard_api.py" ]; then
    python "${SHARED_DIR}/claw_wizard_api.py" --start --port 9098 &
    PIDS+=($!)
    sleep 1
    log "  Wizard API started"
else
    warn "  Wizard API not found — skipping"
fi

# ── Health summary ───────────────────────────────────────────────────
log ""
log "=================================================="
log "  All services started inside container"
log "=================================================="
log "  Agent (${AGENT}):    http://localhost:${AGENT_PORT}"
log "  Gateway Router:      http://localhost:9095"
log "  Optimizer:           http://localhost:9091"
log "  Watchdog:            http://localhost:9097"
log "  Wizard API:          http://localhost:9098"
log ""
log "  Health: curl http://localhost:${AGENT_PORT}/health"
log "  API:    curl http://localhost:9098/api/dashboard/agents"
log "=================================================="

# Wait for all child processes
wait
