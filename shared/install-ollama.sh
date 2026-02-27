#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — Ollama Installer
# ===================================================================
# Idempotent installer for Ollama local LLM runtime.
# Installs Ollama, starts the service, and pulls requested models.
#
# Usage:
#   ./shared/install-ollama.sh                      # Install only
#   ./shared/install-ollama.sh pull llama3.2 qwen2.5  # Install + pull models
#   ./shared/install-ollama.sh list                 # List installed models
#   ./shared/install-ollama.sh status               # Check Ollama status
# ===================================================================
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ollama]${NC} $*"; }
warn() { echo -e "${YELLOW}[ollama]${NC} $*"; }
err()  { echo -e "${RED}[ollama]${NC} $*" >&2; }
info() { echo -e "${BLUE}[ollama]${NC} $*"; }

# -------------------------------------------------------------------
# Install Ollama (idempotent)
# -------------------------------------------------------------------
install_ollama() {
    if command -v ollama &>/dev/null; then
        local version
        version=$(ollama --version 2>/dev/null || echo "unknown")
        log "Ollama already installed: ${version}"
        return 0
    fi

    log "Installing Ollama..."

    if [[ "$(uname -s)" == "Linux" ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        if command -v brew &>/dev/null; then
            brew install ollama
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    else
        err "Unsupported OS: $(uname -s)"
        err "Install Ollama manually from: https://ollama.com/download"
        return 1
    fi

    if command -v ollama &>/dev/null; then
        log "Ollama installed successfully."
    else
        err "Ollama installation failed."
        return 1
    fi
}

# -------------------------------------------------------------------
# Start Ollama service (idempotent)
# -------------------------------------------------------------------
start_ollama() {
    # Check if already running
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        log "Ollama service is already running."
        return 0
    fi

    log "Starting Ollama service..."

    # Try systemd first
    if command -v systemctl &>/dev/null && systemctl is-enabled ollama &>/dev/null 2>&1; then
        sudo systemctl start ollama
        sleep 2
    else
        # Start in background
        ollama serve &>/dev/null &
        sleep 3
    fi

    # Verify
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        log "Ollama service started."
    else
        warn "Ollama service may not be running. Check with: ollama serve"
    fi
}

# -------------------------------------------------------------------
# Pull models
# -------------------------------------------------------------------
pull_models() {
    local models=("$@")

    if [[ ${#models[@]} -eq 0 ]]; then
        return 0
    fi

    log "Pulling ${#models[@]} model(s)..."

    for model in "${models[@]}"; do
        info "Pulling ${model}..."
        if ollama pull "${model}" 2>&1; then
            log "${model} — pulled successfully."
        else
            warn "${model} — pull failed. You can retry with: ollama pull ${model}"
        fi
    done
}

# -------------------------------------------------------------------
# List installed models
# -------------------------------------------------------------------
list_models() {
    if ! command -v ollama &>/dev/null; then
        err "Ollama is not installed."
        return 1
    fi

    log "Installed models:"
    ollama list 2>/dev/null || warn "Could not list models. Is Ollama running?"
}

# -------------------------------------------------------------------
# Status check
# -------------------------------------------------------------------
check_status() {
    echo ""
    info "Ollama Status:"
    echo ""

    # Binary
    if command -v ollama &>/dev/null; then
        log "Binary: $(command -v ollama)"
        log "Version: $(ollama --version 2>/dev/null || echo 'unknown')"
    else
        err "Binary: not found"
        return 1
    fi

    # Service
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        log "Service: running (http://localhost:11434)"
    else
        warn "Service: not running"
    fi

    # Models
    echo ""
    list_models
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
ACTION="${1:-install}"
shift 2>/dev/null || true

case "$ACTION" in
    install)
        install_ollama
        start_ollama
        if [[ $# -gt 0 ]]; then
            pull_models "$@"
        fi
        ;;
    pull)
        if [[ $# -eq 0 ]]; then
            err "Usage: $0 pull <model1> [model2] ..."
            exit 1
        fi
        start_ollama
        pull_models "$@"
        ;;
    list)
        list_models
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 [install|pull|list|status] [models...]"
        echo ""
        echo "Commands:"
        echo "  install              Install Ollama (idempotent)"
        echo "  pull <model> ...     Pull one or more models"
        echo "  list                 List installed models"
        echo "  status               Show Ollama status"
        exit 1
        ;;
esac
