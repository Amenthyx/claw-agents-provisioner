#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# NanoClaw — Bare-Metal Install Script
# Installs NanoClaw AI agent on a fresh Ubuntu 24.04 / Debian 12 machine
# NanoClaw has no config files — it is configured by modifying source code.
# This script clones the repo, injects env vars, and sets up as a service.
# Usage: curl -fsSL .../install-nanoclaw.sh | bash
# Idempotent: safe to run multiple times
# =============================================================================

NANOCLAW_USER="${NANOCLAW_USER:-$(whoami)}"
NANOCLAW_HOME="${HOME}/.nanoclaw"
NANOCLAW_INSTALL="/opt/nanoclaw"
NANOCLAW_REPO="https://github.com/qwibitai/nanoclaw"
NANOCLAW_BRANCH="${NANOCLAW_BRANCH:-main}"
NODE_MAJOR=20

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[nanoclaw]${NC} $*"; }
warn() { echo -e "${YELLOW}[nanoclaw]${NC} $*"; }
err()  { echo -e "${RED}[nanoclaw]${NC} $*" >&2; }

# --- Step 1: System dependencies ---
log "Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq curl ca-certificates git build-essential

# --- Step 2: Install Node.js 20+ ---
if ! command -v node &>/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt "${NODE_MAJOR}" ]; then
    log "Installing Node.js ${NODE_MAJOR}..."
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
    sudo apt-get install -y -qq nodejs
else
    log "Node.js already installed: $(node -v)"
fi

# --- Step 3: Install Docker (NanoClaw needs container isolation) ---
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo bash
    sudo usermod -aG docker "${NANOCLAW_USER}"
    log "Docker installed — user added to docker group"
else
    log "Docker already installed: $(docker --version)"
fi

# --- Step 4: Clone NanoClaw repository ---
log "Cloning NanoClaw repository..."
if [ -d "${NANOCLAW_INSTALL}" ]; then
    warn "Directory ${NANOCLAW_INSTALL} exists — pulling latest..."
    cd "${NANOCLAW_INSTALL}"
    git pull --ff-only 2>/dev/null || warn "Git pull failed — using existing code"
    cd - >/dev/null
else
    sudo mkdir -p "${NANOCLAW_INSTALL}"
    sudo chown "${NANOCLAW_USER}:${NANOCLAW_USER}" "${NANOCLAW_INSTALL}"
    git clone --depth 1 --branch "${NANOCLAW_BRANCH}" "${NANOCLAW_REPO}.git" "${NANOCLAW_INSTALL}"
fi

# --- Step 5: Install npm dependencies ---
log "Installing npm dependencies..."
cd "${NANOCLAW_INSTALL}"
npm install --production 2>/dev/null || npm install || {
    warn "npm install failed — attempting with legacy peer deps"
    npm install --legacy-peer-deps
}
cd - >/dev/null

# --- Step 6: Create config directory ---
log "Setting up config directory..."
mkdir -p "${NANOCLAW_HOME}"

# Create a .env loader script (NanoClaw reads env vars, not config files)
cat > "${NANOCLAW_HOME}/load-env.sh" <<'ENVLOADER'
#!/usr/bin/env bash
# Load .env file for NanoClaw
# NanoClaw has no config file — all config is via environment variables
# injected into the source code or passed at runtime
if [ -f "${HOME}/.nanoclaw/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "${HOME}/.nanoclaw/.env"
    set +a
fi
ENVLOADER
chmod +x "${NANOCLAW_HOME}/load-env.sh"

# --- Step 7: Set up systemd service ---
log "Creating systemd service..."
sudo tee /etc/systemd/system/nanoclaw.service > /dev/null <<EOF
[Unit]
Description=NanoClaw AI Agent
After=network.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=${NANOCLAW_USER}
Group=${NANOCLAW_USER}
WorkingDirectory=${NANOCLAW_INSTALL}
EnvironmentFile=-${NANOCLAW_HOME}/.env
ExecStartPre=/bin/bash ${NANOCLAW_HOME}/load-env.sh
ExecStart=/usr/bin/node src/index.js
Restart=on-failure
RestartSec=5
LimitNOFILE=65535

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${NANOCLAW_HOME} ${NANOCLAW_INSTALL}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nanoclaw.service

# --- Step 8: Verify installation ---
log "Verifying installation..."
if [ -d "${NANOCLAW_INSTALL}/node_modules" ] && command -v node &>/dev/null; then
    echo -e "${GREEN}[nanoclaw]${NC} NanoClaw installed successfully!"
    echo -e "${BLUE}  Code:${NC}    ${NANOCLAW_INSTALL}"
    echo -e "${BLUE}  Config:${NC}  ${NANOCLAW_HOME}/.env (env vars only)"
    echo -e "${BLUE}  Service:${NC} sudo systemctl start nanoclaw"
    echo -e "${BLUE}  Logs:${NC}    journalctl -u nanoclaw -f"
    echo -e "${BLUE}  Note:${NC}    NanoClaw has no config file. Set env vars in ${NANOCLAW_HOME}/.env"
else
    err "Installation verification failed"
    exit 1
fi
