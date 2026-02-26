#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# PicoClaw — Bare-Metal Install Script
# Installs PicoClaw AI agent on a fresh Ubuntu 24.04 / Debian 12 machine
# Ultra-lightweight Go agent designed for edge/IoT (8 MB RAM idle)
# Usage: curl -fsSL .../install-picoclaw.sh | bash
# Idempotent: safe to run multiple times
# =============================================================================

PICOCLAW_VERSION="${PICOCLAW_VERSION:-latest}"
PICOCLAW_USER="${PICOCLAW_USER:-$(whoami)}"
PICOCLAW_HOME="${HOME}/.picoclaw"
PICOCLAW_BIN="/usr/local/bin/picoclaw"
PICOCLAW_REPO="https://github.com/sipeed/picoclaw"
GO_VERSION="1.21.13"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[picoclaw]${NC} $*"; }
warn() { echo -e "${YELLOW}[picoclaw]${NC} $*"; }
err()  { echo -e "${RED}[picoclaw]${NC} $*" >&2; }

# --- Detect architecture ---
ARCH=$(uname -m)
case "${ARCH}" in
    x86_64)  GO_ARCH="amd64" ;;
    aarch64) GO_ARCH="arm64" ;;
    armv7l)  GO_ARCH="armv6l" ;;
    *)       GO_ARCH="amd64"; warn "Unknown arch ${ARCH}, defaulting to amd64" ;;
esac

# --- Step 1: System dependencies ---
log "Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl ca-certificates git
elif command -v dnf &>/dev/null; then
    sudo dnf install -y curl ca-certificates git
elif command -v apk &>/dev/null; then
    sudo apk add --no-cache curl ca-certificates git
else
    warn "Unsupported package manager — ensure curl and git are installed"
fi

# --- Step 2: Install Go ---
if ! command -v go &>/dev/null; then
    log "Installing Go ${GO_VERSION}..."
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz" | sudo tar -C /usr/local -xzf -
    echo 'export PATH=$PATH:/usr/local/go/bin' | sudo tee /etc/profile.d/golang.sh >/dev/null
    export PATH="${PATH}:/usr/local/go/bin"
else
    log "Go already installed: $(go version)"
fi

# --- Step 3: Clone and build PicoClaw ---
log "Building PicoClaw from source..."
TMPDIR=$(mktemp -d)

git clone --depth 1 "${PICOCLAW_REPO}.git" "${TMPDIR}/picoclaw" 2>/dev/null || {
    err "Failed to clone PicoClaw repository"
    exit 1
}

cd "${TMPDIR}/picoclaw"

# Build the binary
export GOPATH="${TMPDIR}/gopath"
export PATH="${PATH}:/usr/local/go/bin"
CGO_ENABLED=0 go build -ldflags="-s -w" -o "${TMPDIR}/picoclaw-bin" ./... 2>/dev/null || {
    warn "Full build failed — attempting main package only"
    CGO_ENABLED=0 go build -ldflags="-s -w" -o "${TMPDIR}/picoclaw-bin" . 2>/dev/null || {
        err "Build failed"
        exit 1
    }
}

sudo mv "${TMPDIR}/picoclaw-bin" "${PICOCLAW_BIN}"
sudo chmod +x "${PICOCLAW_BIN}"

cd - >/dev/null
rm -rf "${TMPDIR}"
log "PicoClaw built successfully"

# --- Step 4: Create config directory ---
log "Setting up config directory..."
mkdir -p "${PICOCLAW_HOME}"

# Create default config.json if not present
if [ ! -f "${PICOCLAW_HOME}/config.json" ]; then
    cat > "${PICOCLAW_HOME}/config.json" <<'JSON'
{
  "server": {
    "host": "0.0.0.0",
    "port": 3300
  },
  "llm": {
    "provider": "deepseek",
    "model": "deepseek-chat"
  },
  "agent": {
    "name": "PicoClaw Agent",
    "max_memory_mb": 128
  }
}
JSON
    log "Created default config.json"
fi

# --- Step 5: Set up systemd service ---
log "Creating systemd service..."
sudo tee /etc/systemd/system/picoclaw.service > /dev/null <<EOF
[Unit]
Description=PicoClaw AI Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${PICOCLAW_USER}
Group=${PICOCLAW_USER}
WorkingDirectory=${PICOCLAW_HOME}
EnvironmentFile=-${PICOCLAW_HOME}/.env
ExecStart=${PICOCLAW_BIN} serve
Restart=on-failure
RestartSec=5
LimitNOFILE=65535

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${PICOCLAW_HOME}
PrivateTmp=true
MemoryMax=128M

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable picoclaw.service

# --- Step 6: Verify installation ---
log "Verifying installation..."
if command -v picoclaw &>/dev/null; then
    echo -e "${GREEN}[picoclaw]${NC} PicoClaw installed successfully!"
    echo -e "${BLUE}  Binary:${NC}  ${PICOCLAW_BIN}"
    echo -e "${BLUE}  Config:${NC}  ${PICOCLAW_HOME}/config.json"
    echo -e "${BLUE}  Service:${NC} sudo systemctl start picoclaw"
    echo -e "${BLUE}  Logs:${NC}    journalctl -u picoclaw -f"
    echo -e "${BLUE}  Health:${NC}  picoclaw agent -m \"ping\""
    echo -e "${BLUE}  Size:${NC}    $(du -h "${PICOCLAW_BIN}" | cut -f1) binary"
else
    err "Installation verification failed"
    exit 1
fi
