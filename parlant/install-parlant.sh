#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — Parlant Bare-Metal Installer
# ===================================================================
# Installs Parlant on the local system without Docker.
# Creates a Python virtual environment and systemd service.
#
# Usage:
#   sudo ./parlant/install-parlant.sh
#
# Requirements: Python 3.10+, pip, systemd (optional)
# ===================================================================
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[parlant-install]${NC} $*"; }
warn() { echo -e "${YELLOW}[parlant-install]${NC} $*"; }
err()  { echo -e "${RED}[parlant-install]${NC} $*" >&2; }
info() { echo -e "${BLUE}[parlant-install]${NC} $*"; }

PARLANT_USER="${PARLANT_USER:-parlant}"
PARLANT_HOME="/home/${PARLANT_USER}"
PARLANT_VENV="${PARLANT_HOME}/.parlant-venv"
PARLANT_DATA="${PARLANT_HOME}/.parlant"
PARLANT_PORT="${PARLANT_PORT:-8800}"

# -------------------------------------------------------------------
# Pre-checks
# -------------------------------------------------------------------
log "Checking prerequisites..."

# Python 3.10+
if ! command -v python3 &>/dev/null; then
    err "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

PYVER=$(python3 --version 2>&1 | awk '{print $2}')
PYMAJOR=$(echo "$PYVER" | cut -d. -f1)
PYMINOR=$(echo "$PYVER" | cut -d. -f2)

if [[ "$PYMAJOR" -lt 3 ]] || [[ "$PYMAJOR" -eq 3 && "$PYMINOR" -lt 10 ]]; then
    err "Python 3.10+ required, found ${PYVER}"
    exit 1
fi

log "Python: ${PYVER}"

# -------------------------------------------------------------------
# Create user
# -------------------------------------------------------------------
if ! id -u "${PARLANT_USER}" &>/dev/null; then
    log "Creating user: ${PARLANT_USER}"
    useradd -m -s /bin/bash "${PARLANT_USER}"
fi

# -------------------------------------------------------------------
# Install system dependencies
# -------------------------------------------------------------------
log "Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3-venv python3-pip curl jq
elif command -v dnf &>/dev/null; then
    dnf install -y python3-pip curl jq
elif command -v yum &>/dev/null; then
    yum install -y python3-pip curl jq
fi

# -------------------------------------------------------------------
# Create virtual environment and install Parlant
# -------------------------------------------------------------------
log "Setting up Python virtual environment..."
su - "${PARLANT_USER}" -c "python3 -m venv ${PARLANT_VENV}"

log "Installing Parlant..."
su - "${PARLANT_USER}" -c "${PARLANT_VENV}/bin/pip install --upgrade pip"
su - "${PARLANT_USER}" -c "${PARLANT_VENV}/bin/pip install parlant"

# Verify installation
if su - "${PARLANT_USER}" -c "${PARLANT_VENV}/bin/python -c 'import parlant; print(parlant.__version__)'"; then
    log "Parlant installed successfully."
else
    warn "Parlant installed but version check failed — this may be fine."
fi

# -------------------------------------------------------------------
# Create data directories
# -------------------------------------------------------------------
log "Creating data directories..."
su - "${PARLANT_USER}" -c "mkdir -p ${PARLANT_DATA}/guidelines ${PARLANT_DATA}/journeys"

# -------------------------------------------------------------------
# Install systemd service (if systemd available)
# -------------------------------------------------------------------
if command -v systemctl &>/dev/null; then
    log "Installing systemd service..."

    cat > /etc/systemd/system/claw-parlant.service << EOF
[Unit]
Description=Claw Parlant — Guideline-Driven Conversational AI
After=network.target

[Service]
Type=simple
User=${PARLANT_USER}
WorkingDirectory=${PARLANT_HOME}
ExecStart=${PARLANT_VENV}/bin/parlant-server --host 0.0.0.0 --port ${PARLANT_PORT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PARLANT_DATA_DIR=${PARLANT_DATA}"

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable claw-parlant.service
    log "Systemd service installed and enabled."
    info "Start: sudo systemctl start claw-parlant"
    info "Logs:  journalctl -u claw-parlant -f"
fi

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
echo ""
log "Parlant installation complete!"
echo ""
info "  User:    ${PARLANT_USER}"
info "  Venv:    ${PARLANT_VENV}"
info "  Data:    ${PARLANT_DATA}"
info "  Port:    ${PARLANT_PORT}"
echo ""
info "Manual start: su - ${PARLANT_USER} -c '${PARLANT_VENV}/bin/parlant-server --host 0.0.0.0 --port ${PARLANT_PORT}'"
