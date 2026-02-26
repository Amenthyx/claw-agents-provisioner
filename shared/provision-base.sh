#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — Base System Provisioning
# ===================================================================
# Prepares a fresh Ubuntu 24.04 (or Debian 12) machine with all
# common dependencies needed by any Claw agent.
#
# This script is idempotent — safe to run multiple times.
#
# Usage:
#   sudo ./shared/provision-base.sh
#
# What it installs:
#   - System utilities: curl, wget, git, jq, unzip, build-essential
#   - Python 3.11+ with pip and venv
#   - Docker Engine + Docker Compose plugin
#   - Docker group permissions for the current user
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11
DOCKER_GPG_URL="https://download.docker.com/linux/ubuntu/gpg"
DOCKER_REPO_URL="https://download.docker.com/linux/ubuntu"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[INFO]\033[0m $*"
}

log_ok() {
    echo -e "\033[1;32m[OK]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $*"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)."
        exit 1
    fi
}

# -------------------------------------------------------------------
# 1. Pre-flight checks
# -------------------------------------------------------------------
log_info "=== Claw Agents Provisioner — Base System Setup ==="
log_info "Detected OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo 'Unknown')"

check_root

# Detect the actual non-root user (for Docker group addition)
ACTUAL_USER="${SUDO_USER:-${USER}}"
log_info "Configuring for user: ${ACTUAL_USER}"

# -------------------------------------------------------------------
# 2. Update apt package index
# -------------------------------------------------------------------
log_info "Updating apt package index..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

log_ok "Package index updated."

# -------------------------------------------------------------------
# 3. Install common system utilities
# -------------------------------------------------------------------
log_info "Installing common system utilities..."

COMMON_PACKAGES=(
    curl
    wget
    git
    jq
    unzip
    zip
    ca-certificates
    gnupg
    lsb-release
    software-properties-common
    build-essential
    make
    apt-transport-https
)

apt-get install -y -qq "${COMMON_PACKAGES[@]}" > /dev/null 2>&1

log_ok "System utilities installed."

# -------------------------------------------------------------------
# 4. Install Python 3.11+
# -------------------------------------------------------------------
log_info "Checking Python installation..."

install_python() {
    log_info "Installing Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+..."

    # Add deadsnakes PPA if needed (Ubuntu may not have 3.11+ in default repos)
    if ! apt-cache show "python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" > /dev/null 2>&1; then
        log_info "Adding deadsnakes PPA for Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}..."
        add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1 || true
        apt-get update -qq
    fi

    apt-get install -y -qq \
        "python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" \
        "python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}-venv" \
        "python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}-dev" \
        > /dev/null 2>&1

    # Set as default python3 if no python3 exists
    if ! command -v python3 > /dev/null 2>&1; then
        update-alternatives --install /usr/bin/python3 python3 \
            "/usr/bin/python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" 1
    fi
}

# Check if a suitable Python version is already installed
PYTHON_OK=false
if command -v python3 > /dev/null 2>&1; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -ge "$REQUIRED_PYTHON_MAJOR" ]] && [[ "$PY_MINOR" -ge "$REQUIRED_PYTHON_MINOR" ]]; then
        PYTHON_OK=true
        log_ok "Python ${PY_VERSION} already installed (meets ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ requirement)."
    else
        log_warn "Python ${PY_VERSION} found but ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ required."
    fi
fi

if [[ "$PYTHON_OK" != "true" ]]; then
    install_python
    log_ok "Python $(python3 --version 2>&1 | awk '{print $2}') installed."
fi

# -------------------------------------------------------------------
# 5. Install pip
# -------------------------------------------------------------------
log_info "Checking pip installation..."

if ! command -v pip3 > /dev/null 2>&1; then
    log_info "Installing pip..."
    apt-get install -y -qq python3-pip > /dev/null 2>&1 || true

    # Fallback: use ensurepip if apt package unavailable
    if ! command -v pip3 > /dev/null 2>&1; then
        python3 -m ensurepip --upgrade 2>/dev/null || true
    fi
fi

if command -v pip3 > /dev/null 2>&1; then
    log_ok "pip $(pip3 --version 2>&1 | awk '{print $2}') installed."
else
    log_warn "pip installation could not be verified. You may need to install it manually."
fi

# -------------------------------------------------------------------
# 6. Install Docker Engine
# -------------------------------------------------------------------
log_info "Checking Docker installation..."

install_docker() {
    log_info "Installing Docker Engine..."

    # Remove old Docker packages if present
    for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
        apt-get remove -y -qq "$pkg" > /dev/null 2>&1 || true
    done

    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "$DOCKER_GPG_URL" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    UBUNTU_CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME:-noble}}")
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] ${DOCKER_REPO_URL} ${UBUNTU_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq

    # Install Docker packages
    apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin \
        > /dev/null 2>&1
}

if command -v docker > /dev/null 2>&1; then
    DOCKER_VERSION=$(docker --version 2>&1 | awk '{print $3}' | tr -d ',')
    log_ok "Docker ${DOCKER_VERSION} already installed."
else
    install_docker
    log_ok "Docker $(docker --version 2>&1 | awk '{print $3}' | tr -d ',') installed."
fi

# -------------------------------------------------------------------
# 7. Verify Docker Compose plugin
# -------------------------------------------------------------------
log_info "Checking Docker Compose plugin..."

if docker compose version > /dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version --short 2>&1)
    log_ok "Docker Compose ${COMPOSE_VERSION} available."
else
    log_warn "Docker Compose plugin not found. Attempting install..."
    apt-get install -y -qq docker-compose-plugin > /dev/null 2>&1 || true

    if docker compose version > /dev/null 2>&1; then
        log_ok "Docker Compose $(docker compose version --short 2>&1) installed."
    else
        log_error "Docker Compose plugin could not be installed. Install manually."
    fi
fi

# -------------------------------------------------------------------
# 8. Configure Docker permissions
# -------------------------------------------------------------------
log_info "Configuring Docker permissions for user '${ACTUAL_USER}'..."

# Create docker group if it does not exist
if ! getent group docker > /dev/null 2>&1; then
    groupadd docker
fi

# Add user to docker group (idempotent — no error if already a member)
usermod -aG docker "${ACTUAL_USER}" 2>/dev/null || true

log_ok "User '${ACTUAL_USER}' added to docker group."
log_warn "You may need to log out and back in (or run 'newgrp docker') for group changes to take effect."

# -------------------------------------------------------------------
# 9. Enable and start Docker service
# -------------------------------------------------------------------
log_info "Enabling Docker service..."

systemctl enable docker > /dev/null 2>&1 || true
systemctl start docker > /dev/null 2>&1 || true

if systemctl is-active --quiet docker; then
    log_ok "Docker service is running."
else
    log_warn "Docker service may not be running. Check with: systemctl status docker"
fi

# -------------------------------------------------------------------
# 10. Summary
# -------------------------------------------------------------------
echo ""
log_info "========================================="
log_info "  Base provisioning complete!"
log_info "========================================="
echo ""
log_info "Installed components:"
echo "  - System utilities: curl, git, jq, build-essential, etc."
echo "  - Python: $(python3 --version 2>&1 || echo 'not found')"
echo "  - pip: $(pip3 --version 2>&1 | awk '{print $2}' || echo 'not found')"
echo "  - Docker: $(docker --version 2>&1 | awk '{print $3}' | tr -d ',' || echo 'not found')"
echo "  - Docker Compose: $(docker compose version --short 2>&1 || echo 'not found')"
echo ""
log_info "Next steps:"
echo "  1. Log out and back in (for Docker group permissions)"
echo "  2. Copy .env.template to .env and fill in your keys"
echo "  3. Run: ./claw.sh <agent> docker"
echo ""
