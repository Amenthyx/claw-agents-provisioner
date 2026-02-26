#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ZeroClaw — Bare-Metal Install Script
# Installs ZeroClaw AI agent on a fresh Ubuntu 24.04 / Debian 12 machine
# Usage: curl -fsSL .../install-zeroclaw.sh | bash
# Idempotent: safe to run multiple times
# =============================================================================

ZEROCLAW_VERSION="${ZEROCLAW_VERSION:-latest}"
ZEROCLAW_USER="${ZEROCLAW_USER:-$(whoami)}"
ZEROCLAW_HOME="${HOME}/.zeroclaw"
ZEROCLAW_BIN="/usr/local/bin/zeroclaw"
ZEROCLAW_REPO="https://github.com/zeroclaw-labs/zeroclaw"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[zeroclaw]${NC} $*"; }
warn() { echo -e "${YELLOW}[zeroclaw]${NC} $*"; }
err()  { echo -e "${RED}[zeroclaw]${NC} $*" >&2; }

# --- Step 1: System dependencies ---
log "Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl ca-certificates git build-essential pkg-config libssl-dev
elif command -v dnf &>/dev/null; then
    sudo dnf install -y curl ca-certificates git gcc openssl-devel
else
    warn "Unsupported package manager — ensure curl, git, and build tools are installed"
fi

# --- Step 2: Install Rust toolchain (needed for building from source as fallback) ---
if ! command -v rustc &>/dev/null; then
    log "Installing Rust toolchain..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
    # shellcheck source=/dev/null
    source "${HOME}/.cargo/env"
else
    log "Rust already installed: $(rustc --version)"
fi

# --- Step 3: Download pre-built binary (preferred) ---
log "Downloading ZeroClaw binary (version: ${ZEROCLAW_VERSION})..."
DOWNLOAD_SUCCESS=false

if [ "${ZEROCLAW_VERSION}" = "latest" ]; then
    DOWNLOAD_URL="${ZEROCLAW_REPO}/releases/latest/download/zeroclaw-linux-x86_64"
else
    DOWNLOAD_URL="${ZEROCLAW_REPO}/releases/download/v${ZEROCLAW_VERSION}/zeroclaw-linux-x86_64"
fi

if curl -fsSL -o /tmp/zeroclaw "${DOWNLOAD_URL}" 2>/dev/null; then
    sudo mv /tmp/zeroclaw "${ZEROCLAW_BIN}"
    sudo chmod +x "${ZEROCLAW_BIN}"
    DOWNLOAD_SUCCESS=true
    log "Binary downloaded successfully"
fi

# --- Step 4: Build from source (fallback) ---
if [ "${DOWNLOAD_SUCCESS}" = "false" ]; then
    warn "Pre-built binary not available — building from source..."
    # shellcheck source=/dev/null
    source "${HOME}/.cargo/env" 2>/dev/null || true

    TMPDIR=$(mktemp -d)
    git clone --depth 1 "${ZEROCLAW_REPO}.git" "${TMPDIR}/zeroclaw" 2>/dev/null || {
        err "Failed to clone ZeroClaw repository"
        exit 1
    }

    cd "${TMPDIR}/zeroclaw"
    cargo build --release
    sudo cp target/release/zeroclaw "${ZEROCLAW_BIN}"
    sudo chmod +x "${ZEROCLAW_BIN}"
    cd - >/dev/null
    rm -rf "${TMPDIR}"
    log "Built from source successfully"
fi

# --- Step 5: Create config directory ---
log "Setting up config directory..."
mkdir -p "${ZEROCLAW_HOME}"

# Create default config.toml if not present
if [ ! -f "${ZEROCLAW_HOME}/config.toml" ]; then
    cat > "${ZEROCLAW_HOME}/config.toml" <<'TOML'
# =============================================================================
# ZeroClaw Configuration
# Docs: https://github.com/zeroclaw-labs/zeroclaw
# =============================================================================

[llm]
# provider = "anthropic"
# model = "claude-sonnet-4-6"
# api_key is read from ANTHROPIC_API_KEY env var

[server]
host = "0.0.0.0"
port = 3100

[security]
# encrypt_config = true
TOML
    log "Created default config.toml"
fi

# --- Step 6: Set up systemd service ---
log "Creating systemd service..."
sudo tee /etc/systemd/system/zeroclaw.service > /dev/null <<EOF
[Unit]
Description=ZeroClaw AI Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${ZEROCLAW_USER}
Group=${ZEROCLAW_USER}
WorkingDirectory=${ZEROCLAW_HOME}
EnvironmentFile=-${ZEROCLAW_HOME}/.env
ExecStart=${ZEROCLAW_BIN} serve
Restart=on-failure
RestartSec=5
LimitNOFILE=65535

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${ZEROCLAW_HOME}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable zeroclaw.service

# --- Step 7: Verify installation ---
log "Verifying installation..."
if command -v zeroclaw &>/dev/null; then
    echo -e "${GREEN}[zeroclaw]${NC} ZeroClaw installed successfully!"
    echo -e "${BLUE}  Binary:${NC}  ${ZEROCLAW_BIN}"
    echo -e "${BLUE}  Config:${NC}  ${ZEROCLAW_HOME}/config.toml"
    echo -e "${BLUE}  Service:${NC} sudo systemctl start zeroclaw"
    echo -e "${BLUE}  Logs:${NC}    journalctl -u zeroclaw -f"
    echo -e "${BLUE}  Health:${NC}  zeroclaw doctor"
else
    err "Installation verification failed"
    exit 1
fi
