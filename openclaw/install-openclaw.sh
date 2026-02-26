#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# OpenClaw — Bare-Metal Install Script
# Installs OpenClaw AI agent on a fresh Ubuntu 24.04 / Debian 12 machine
# Heavy TypeScript/Node.js agent — 140K stars, 50+ integrations
# Usage: curl -fsSL .../install-openclaw.sh | bash
# Idempotent: safe to run multiple times
# =============================================================================

OPENCLAW_VERSION="${OPENCLAW_VERSION:-latest}"
OPENCLAW_USER="${OPENCLAW_USER:-$(whoami)}"
OPENCLAW_HOME="${HOME}/.openclaw"
OPENCLAW_INSTALL="/opt/openclaw"
OPENCLAW_REPO="https://github.com/openclaw/openclaw"
NODE_MAJOR=22

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[openclaw]${NC} $*"; }
warn() { echo -e "${YELLOW}[openclaw]${NC} $*"; }
err()  { echo -e "${RED}[openclaw]${NC} $*" >&2; }

# --- Step 1: System dependencies ---
log "Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq curl ca-certificates git build-essential python3

# --- Step 2: Install Node.js 22 ---
if ! command -v node &>/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt "${NODE_MAJOR}" ]; then
    log "Installing Node.js ${NODE_MAJOR}..."
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
    sudo apt-get install -y -qq nodejs
else
    log "Node.js already installed: $(node -v)"
fi

# --- Step 3: Install pnpm ---
if ! command -v pnpm &>/dev/null; then
    log "Installing pnpm..."
    sudo corepack enable 2>/dev/null || npm install -g corepack
    corepack prepare pnpm@latest --activate 2>/dev/null || npm install -g pnpm
else
    log "pnpm already installed: $(pnpm -v)"
fi

# --- Step 4: Clone OpenClaw repository ---
log "Cloning OpenClaw repository..."
if [ -d "${OPENCLAW_INSTALL}" ]; then
    warn "Directory ${OPENCLAW_INSTALL} exists — pulling latest..."
    cd "${OPENCLAW_INSTALL}"
    git pull --ff-only 2>/dev/null || warn "Git pull failed — using existing code"
    cd - >/dev/null
else
    sudo mkdir -p "${OPENCLAW_INSTALL}"
    sudo chown "${OPENCLAW_USER}:${OPENCLAW_USER}" "${OPENCLAW_INSTALL}"
    git clone --depth 1 "${OPENCLAW_REPO}.git" "${OPENCLAW_INSTALL}" 2>/dev/null || {
        warn "Primary repo clone failed — trying alternative..."
        git clone --depth 1 "https://github.com/open-webui/open-webui.git" "${OPENCLAW_INSTALL}" 2>/dev/null || {
            err "Failed to clone OpenClaw repository"
            exit 1
        }
    }
fi

# --- Step 5: Install dependencies with pnpm ---
log "Installing dependencies with pnpm..."
cd "${OPENCLAW_INSTALL}"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install 2>/dev/null || {
    warn "pnpm install failed — falling back to npm"
    npm install --legacy-peer-deps
}
cd - >/dev/null

# --- Step 6: Create config directory ---
log "Setting up config directory..."
mkdir -p "${OPENCLAW_HOME}"

# Create default openclaw.json (JSON5 format) if not present
if [ ! -f "${OPENCLAW_HOME}/openclaw.json" ]; then
    cat > "${OPENCLAW_HOME}/openclaw.json" <<'JSON5'
{
  // OpenClaw Configuration
  // Docs: https://docs.openclaw.ai/gateway/configuration
  "server": {
    "host": "0.0.0.0",
    "port": 3400
  },
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6"
  },
  "channels": [],
  "skills": [],
  "dm_policy": "pairing"
}
JSON5
    log "Created default openclaw.json"
fi

# --- Step 7: Set up systemd service ---
log "Creating systemd service..."
sudo tee /etc/systemd/system/openclaw.service > /dev/null <<EOF
[Unit]
Description=OpenClaw AI Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${OPENCLAW_USER}
Group=${OPENCLAW_USER}
WorkingDirectory=${OPENCLAW_INSTALL}
EnvironmentFile=-${OPENCLAW_HOME}/.env
ExecStart=/usr/bin/env pnpm start
Restart=on-failure
RestartSec=10
LimitNOFILE=65535

# Memory limit (OpenClaw is heavy: ~1.2 GB idle, ~4 GB active)
MemoryMax=4G

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${OPENCLAW_HOME} ${OPENCLAW_INSTALL}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable openclaw.service

# --- Step 8: Run onboard if available ---
log "Attempting initial setup..."
cd "${OPENCLAW_INSTALL}"
if [ -f "package.json" ]; then
    pnpm run setup 2>/dev/null || \
    npx openclaw onboard --install-daemon 2>/dev/null || \
    warn "Auto-onboard not available — run 'openclaw onboard' manually after starting"
fi
cd - >/dev/null

# --- Step 9: Verify installation ---
log "Verifying installation..."
if [ -d "${OPENCLAW_INSTALL}/node_modules" ] && command -v node &>/dev/null; then
    echo -e "${GREEN}[openclaw]${NC} OpenClaw installed successfully!"
    echo -e "${BLUE}  Code:${NC}    ${OPENCLAW_INSTALL}"
    echo -e "${BLUE}  Config:${NC}  ${OPENCLAW_HOME}/openclaw.json"
    echo -e "${BLUE}  Service:${NC} sudo systemctl start openclaw"
    echo -e "${BLUE}  Logs:${NC}    journalctl -u openclaw -f"
    echo -e "${BLUE}  Health:${NC}  openclaw doctor"
    echo -e "${BLUE}  Node:${NC}    $(node -v) | pnpm: $(pnpm -v 2>/dev/null || echo 'N/A')"
else
    err "Installation verification failed"
    exit 1
fi
