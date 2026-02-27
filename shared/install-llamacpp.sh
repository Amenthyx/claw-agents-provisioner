#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — llama.cpp Installer
# ===================================================================
# Idempotent installer for llama.cpp (llama-server) local LLM runtime.
# Installs the server binary, starts the service, and manages models.
#
# Usage:
#   ./shared/install-llamacpp.sh install          # Install llama-server
#   ./shared/install-llamacpp.sh start <model>    # Start server with model
#   ./shared/install-llamacpp.sh status           # Check status
#   ./shared/install-llamacpp.sh list             # List GGUF models
# ===================================================================
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()  { echo -e "${GREEN}[llamacpp]${NC} $*"; }
warn() { echo -e "${YELLOW}[llamacpp]${NC} $*"; }
err()  { echo -e "${RED}[llamacpp]${NC} $*" >&2; }
info() { echo -e "${BLUE}[llamacpp]${NC} $*"; }

LLAMACPP_PORT="${LLAMACPP_PORT:-8080}"
LLAMACPP_HOST="${LLAMACPP_HOST:-0.0.0.0}"
MODELS_DIR="${LLAMACPP_MODELS_DIR:-$HOME/.llamacpp/models}"

# -------------------------------------------------------------------
# Install llama.cpp server (idempotent)
# -------------------------------------------------------------------
install_llamacpp() {
    # Check if already installed
    if command -v llama-server &>/dev/null; then
        log "llama-server already installed: $(command -v llama-server)"
        return 0
    fi

    # Also check common install locations
    if [[ -x "/usr/local/bin/llama-server" ]]; then
        log "llama-server found at /usr/local/bin/llama-server"
        return 0
    fi

    log "Installing llama.cpp server..."

    local os_name
    os_name="$(uname -s)"

    if [[ "$os_name" == "Darwin" ]]; then
        # macOS: use Homebrew
        if command -v brew &>/dev/null; then
            brew install llama.cpp
        else
            err "Homebrew not found. Install Homebrew first: https://brew.sh"
            err "Or install llama.cpp manually: https://github.com/ggerganov/llama.cpp"
            return 1
        fi

    elif [[ "$os_name" == "Linux" ]]; then
        # Linux: download pre-built binary from GitHub releases
        local arch
        arch="$(uname -m)"

        local release_url="https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
        local tag

        tag=$(curl -sf "$release_url" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"//;s/".*//')
        if [[ -z "$tag" ]]; then
            err "Could not fetch latest release tag from GitHub."
            err "Install manually: https://github.com/ggerganov/llama.cpp/releases"
            return 1
        fi

        log "Latest release: $tag"

        # Determine binary name based on architecture
        local binary_name=""
        case "$arch" in
            x86_64|amd64)
                binary_name="llama-${tag}-bin-ubuntu-x64.zip"
                ;;
            aarch64|arm64)
                binary_name="llama-${tag}-bin-ubuntu-arm64.zip"
                ;;
            *)
                err "Unsupported architecture: $arch"
                err "Build from source: https://github.com/ggerganov/llama.cpp#build"
                return 1
                ;;
        esac

        local download_url="https://github.com/ggerganov/llama.cpp/releases/download/${tag}/${binary_name}"
        local tmp_dir
        tmp_dir=$(mktemp -d)

        log "Downloading $binary_name..."
        if curl -fSL "$download_url" -o "${tmp_dir}/llamacpp.zip" 2>/dev/null; then
            cd "$tmp_dir"
            unzip -q llamacpp.zip 2>/dev/null || true

            # Find and install llama-server binary
            local server_bin
            server_bin=$(find "$tmp_dir" -name "llama-server" -type f | head -1)

            if [[ -n "$server_bin" ]]; then
                chmod +x "$server_bin"
                sudo cp "$server_bin" /usr/local/bin/llama-server 2>/dev/null || \
                    cp "$server_bin" "$HOME/.local/bin/llama-server" 2>/dev/null || \
                    { err "Cannot copy binary. Install manually."; rm -rf "$tmp_dir"; return 1; }
                log "llama-server installed successfully."
            else
                err "llama-server binary not found in release archive."
                err "Build from source: https://github.com/ggerganov/llama.cpp#build"
                rm -rf "$tmp_dir"
                return 1
            fi

            rm -rf "$tmp_dir"
        else
            err "Download failed. Install manually: https://github.com/ggerganov/llama.cpp/releases"
            rm -rf "$tmp_dir"
            return 1
        fi

    else
        err "Unsupported OS: $os_name"
        err "Install llama.cpp manually: https://github.com/ggerganov/llama.cpp"
        return 1
    fi

    # Create models directory
    mkdir -p "$MODELS_DIR"
    log "Models directory: $MODELS_DIR"

    # Verify installation
    if command -v llama-server &>/dev/null || [[ -x "/usr/local/bin/llama-server" ]]; then
        log "Installation verified."
    else
        warn "Binary may not be in PATH. Check: /usr/local/bin/llama-server"
    fi
}

# -------------------------------------------------------------------
# Start llama-server
# -------------------------------------------------------------------
start_server() {
    local model_path="${1:-}"

    if [[ -z "$model_path" ]]; then
        err "Usage: $0 start <model.gguf>"
        err "Example: $0 start ~/.llamacpp/models/llama-3.2-3b.Q4_K_M.gguf"
        return 1
    fi

    if [[ ! -f "$model_path" ]]; then
        err "Model file not found: $model_path"
        return 1
    fi

    # Check if already running
    if curl -sf "http://localhost:${LLAMACPP_PORT}/health" &>/dev/null; then
        log "llama-server is already running on port ${LLAMACPP_PORT}."
        return 0
    fi

    log "Starting llama-server on port ${LLAMACPP_PORT}..."
    log "Model: $model_path"

    local server_bin="llama-server"
    if ! command -v "$server_bin" &>/dev/null; then
        if [[ -x "/usr/local/bin/llama-server" ]]; then
            server_bin="/usr/local/bin/llama-server"
        else
            err "llama-server not found. Run: $0 install"
            return 1
        fi
    fi

    "$server_bin" \
        -m "$model_path" \
        --port "$LLAMACPP_PORT" \
        --host "$LLAMACPP_HOST" \
        &>/dev/null &

    sleep 3

    if curl -sf "http://localhost:${LLAMACPP_PORT}/health" &>/dev/null; then
        log "llama-server started on http://${LLAMACPP_HOST}:${LLAMACPP_PORT}"
        info "OpenAI-compatible endpoint: http://localhost:${LLAMACPP_PORT}/v1"
    else
        warn "llama-server may not be running. Check with: $0 status"
    fi
}

# -------------------------------------------------------------------
# List GGUF models
# -------------------------------------------------------------------
list_models() {
    echo ""
    info "GGUF Models in: $MODELS_DIR"
    echo ""

    if [[ ! -d "$MODELS_DIR" ]]; then
        warn "Models directory does not exist: $MODELS_DIR"
        warn "Create it with: mkdir -p $MODELS_DIR"
        return 0
    fi

    local count=0
    while IFS= read -r -d '' model_file; do
        local name size_mb
        name=$(basename "$model_file")
        size_mb=$(du -m "$model_file" 2>/dev/null | cut -f1)
        printf "  %-50s %s MB\n" "$name" "$size_mb"
        count=$((count + 1))
    done < <(find "$MODELS_DIR" -name "*.gguf" -print0 2>/dev/null)

    if [[ $count -eq 0 ]]; then
        info "No GGUF models found."
        info "Download models from: https://huggingface.co/models?sort=downloads&search=gguf"
        info "Place them in: $MODELS_DIR"
    else
        echo ""
        info "Total: $count model(s)"
    fi
}

# -------------------------------------------------------------------
# Status check
# -------------------------------------------------------------------
check_status() {
    echo ""
    info "llama.cpp Status:"
    echo ""

    # Binary
    if command -v llama-server &>/dev/null; then
        log "Binary: $(command -v llama-server)"
    elif [[ -x "/usr/local/bin/llama-server" ]]; then
        log "Binary: /usr/local/bin/llama-server"
    else
        err "Binary: not found"
        info "Install with: $0 install"
        return 1
    fi

    # Server
    if curl -sf "http://localhost:${LLAMACPP_PORT}/health" &>/dev/null; then
        log "Server: running (http://localhost:${LLAMACPP_PORT})"
        log "OpenAI API: http://localhost:${LLAMACPP_PORT}/v1"

        # Try to get loaded model info
        local model_info
        model_info=$(curl -sf "http://localhost:${LLAMACPP_PORT}/v1/models" 2>/dev/null || echo "")
        if [[ -n "$model_info" ]]; then
            log "Models endpoint: active"
        fi
    else
        warn "Server: not running (port ${LLAMACPP_PORT})"
    fi

    # Models directory
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
        install_llamacpp
        ;;
    start)
        start_server "${1:-}"
        ;;
    list)
        list_models
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 [install|start|list|status]"
        echo ""
        echo "Commands:"
        echo "  install              Install llama-server (idempotent)"
        echo "  start <model.gguf>   Start server with a GGUF model"
        echo "  list                 List GGUF models in models directory"
        echo "  status               Show llama.cpp status"
        echo ""
        echo "Environment:"
        echo "  LLAMACPP_PORT        Server port (default: 8080)"
        echo "  LLAMACPP_HOST        Server host (default: 0.0.0.0)"
        echo "  LLAMACPP_MODELS_DIR  Models directory (default: ~/.llamacpp/models)"
        exit 1
        ;;
esac
