#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — Parlant Entrypoint
# ===================================================================
# Translates unified .env variables into Parlant's configuration
# and starts the Parlant conversational AI server.
#
# Parlant: Python-based framework with behavioral guidelines,
# journeys, and MCP tool integration.
#
# Parlant supports 18+ LLM providers via its pluggable backend:
#   anthropic, openai, openrouter, deepseek, gemini, groq,
#   mistral, cohere, together, replicate, perplexity, anyscale,
#   fireworks, ollama, vllm, lmstudio, local (OpenAI-compatible)
#
# This script:
#   1. Reads unified env vars (from .env / Docker environment)
#   2. Optionally decrypts vault secrets
#   3. Resolves LLM provider and API key
#   4. Exports Parlant-expected environment variables
#   5. Initializes guidelines and journeys directories
#   6. Starts parlant-server
#
# Usage (Docker): CMD ["./parlant/entrypoint.sh"]
# Usage (native): CLAW_LLM_PROVIDER=anthropic ./parlant/entrypoint.sh
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
PARLANT_HOME="${HOME}/.parlant"
PARLANT_GUIDELINES_DIR="${PARLANT_HOME}/guidelines"
PARLANT_JOURNEYS_DIR="${PARLANT_HOME}/journeys"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[parlant-entrypoint]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[parlant-entrypoint]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[parlant-entrypoint]\033[0m $*"
}

env_or_default() {
    local var_name="$1"
    local default_value="${2:-}"
    echo "${!var_name:-$default_value}"
}

# Read a secret: checks /run/secrets/decrypted/<KEY> first, falls back to env var
read_secret() {
    local key="$1"
    local default_value="${2:-}"
    local secret_file="/run/secrets/decrypted/${key}"
    if [[ -f "$secret_file" ]]; then
        cat "$secret_file"
    else
        echo "${!key:-$default_value}"
    fi
}

# -------------------------------------------------------------------
# 0. Vault decryption (if vault is mounted)
# -------------------------------------------------------------------
VAULT_FILE="${CLAW_VAULT_FILE:-/run/secrets/secrets.vault}"
if [[ -f "$VAULT_FILE" ]]; then
    log_info "Vault detected — decrypting secrets to tmpfs..."
    DECRYPT_DIR="/run/secrets/decrypted"
    mkdir -p "$DECRYPT_DIR" 2>/dev/null || true

    if command -v python3 > /dev/null 2>&1; then
        VAULT_PY="${CLAW_VAULT_PY:-/usr/local/bin/claw_vault.py}"
        if [[ -f "$VAULT_PY" ]]; then
            python3 "$VAULT_PY" inject "$DECRYPT_DIR" --vault-file "$VAULT_FILE" 2>/dev/null && \
                log_info "Secrets decrypted to tmpfs." || \
                log_warn "Vault decryption failed — falling back to env vars."
        else
            log_warn "claw_vault.py not found at $VAULT_PY — falling back to env vars."
        fi
    else
        log_warn "python3 not available — cannot decrypt vault, falling back to env vars."
    fi
fi

# -------------------------------------------------------------------
# 1. Create Parlant directories
# -------------------------------------------------------------------
mkdir -p "${PARLANT_HOME}" "${PARLANT_GUIDELINES_DIR}" "${PARLANT_JOURNEYS_DIR}"

# -------------------------------------------------------------------
# 2. Resolve LLM provider configuration
# -------------------------------------------------------------------
log_info "Resolving LLM provider configuration..."

PROVIDER=$(env_or_default "CLAW_LLM_PROVIDER" "anthropic")
MODEL=$(env_or_default "CLAW_LLM_MODEL" "claude-sonnet-4-6")
LOG_LEVEL=$(env_or_default "PARLANT_LOG_LEVEL" "$(env_or_default "CLAW_LOG_LEVEL" "info")")
PARLANT_PORT=$(env_or_default "PARLANT_PORT" "8800")
PARLANT_MCP_PORT=$(env_or_default "PARLANT_MCP_PORT" "8181")

# Map unified provider names to Parlant provider + API key
case "$PROVIDER" in
    anthropic)
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        export ANTHROPIC_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="anthropic"
        ;;
    openai)
        API_KEY=$(read_secret "OPENAI_API_KEY" "")
        export OPENAI_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="openai"
        ;;
    openrouter)
        API_KEY=$(read_secret "OPENROUTER_API_KEY" "")
        export OPENROUTER_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="openrouter"
        ;;
    deepseek)
        API_KEY=$(read_secret "DEEPSEEK_API_KEY" "")
        export DEEPSEEK_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="deepseek"
        ;;
    gemini)
        API_KEY=$(read_secret "GEMINI_API_KEY" "")
        export GOOGLE_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="google"
        ;;
    groq)
        API_KEY=$(read_secret "GROQ_API_KEY" "")
        export GROQ_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="groq"
        ;;
    local)
        API_KEY="local"
        LOCAL_ENDPOINT=$(env_or_default "CLAW_LOCAL_LLM_ENDPOINT" "http://host.docker.internal:11434/v1")
        export OPENAI_API_KEY="local"
        export OPENAI_API_BASE="${LOCAL_ENDPOINT}"
        PARLANT_PROVIDER="openai"
        log_info "Using local LLM provider at ${LOCAL_ENDPOINT}"
        ;;
    *)
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        export ANTHROPIC_API_KEY="${API_KEY}"
        PARLANT_PROVIDER="anthropic"
        log_warn "Unknown provider '${PROVIDER}', defaulting to anthropic."
        ;;
esac

if [[ -z "${API_KEY:-}" ]] && [[ "$PROVIDER" != "local" ]]; then
    log_error "No API key found for provider '${PROVIDER}'. Set the appropriate *_API_KEY env var."
    exit 1
fi

log_info "Provider: ${PARLANT_PROVIDER} | Model: ${MODEL}"

# -------------------------------------------------------------------
# 3. Resolve chat channel tokens (Parlant uses these for integrations)
# -------------------------------------------------------------------
TELEGRAM_TOKEN=$(read_secret "TELEGRAM_BOT_TOKEN" "")
DISCORD_TOKEN=$(read_secret "DISCORD_BOT_TOKEN" "")
SLACK_TOKEN=$(read_secret "SLACK_BOT_TOKEN" "")

[[ -n "$TELEGRAM_TOKEN" ]] && export TELEGRAM_BOT_TOKEN="${TELEGRAM_TOKEN}"
[[ -n "$DISCORD_TOKEN" ]] && export DISCORD_BOT_TOKEN="${DISCORD_TOKEN}"
[[ -n "$SLACK_TOKEN" ]] && export SLACK_BOT_TOKEN="${SLACK_TOKEN}"

# -------------------------------------------------------------------
# 4. Resolve assessment-derived fields
# -------------------------------------------------------------------
CLIENT_INDUSTRY=$(env_or_default "CLAW_CLIENT_INDUSTRY" "general")
CLIENT_LANGUAGE=$(env_or_default "CLAW_CLIENT_LANGUAGE" "en")
CLIENT_NAME=$(env_or_default "CLAW_CLIENT_NAME" "")
DATA_SENSITIVITY=$(env_or_default "CLAW_DATA_SENSITIVITY" "medium")
COMPLIANCE=$(env_or_default "CLAW_COMPLIANCE" "none")
SKILLS=$(env_or_default "CLAW_SKILLS" "")

# -------------------------------------------------------------------
# 5. Resolve adapter / fine-tuning fields
# -------------------------------------------------------------------
ADAPTER_PATH=$(env_or_default "CLAW_ADAPTER_PATH" "")
SYSTEM_PROMPT_ENRICHMENT=$(env_or_default "CLAW_SYSTEM_PROMPT_ENRICHMENT" "true")
USE_CASE=$(env_or_default "CLAW_FINETUNE_USE_CASE" "")

# -------------------------------------------------------------------
# 6. Generate default guideline if none exists
# -------------------------------------------------------------------
GUIDELINE_FILE="${PARLANT_GUIDELINES_DIR}/default.md"
if [[ ! -f "$GUIDELINE_FILE" ]]; then
    log_info "Generating default behavioral guideline..."
    cat > "$GUIDELINE_FILE" << GUIDELINE_EOF
# Default Agent Behavioral Guideline
# Auto-generated by claw-agents-provisioner

## Identity
- Client: ${CLIENT_NAME:-Claw Agent}
- Industry: ${CLIENT_INDUSTRY}
- Language: ${CLIENT_LANGUAGE}

## Behavior Rules
- Always be helpful, professional, and honest
- If unsure about something, say so rather than guessing
- Respect user privacy and data sensitivity level: ${DATA_SENSITIVITY}
- Follow compliance requirements: ${COMPLIANCE}

## Tone
- Professional yet approachable
- Clear and concise responses
- Adapt formality to the user's communication style
GUIDELINE_EOF
fi

# -------------------------------------------------------------------
# 7. System prompt enrichment (if adapter exists)
# -------------------------------------------------------------------
if [[ "$SYSTEM_PROMPT_ENRICHMENT" == "true" ]] && [[ -n "$USE_CASE" ]]; then
    ADAPTER_DIR="/workspace/finetune/adapters/${USE_CASE}"
    PROMPT_FILE="${ADAPTER_DIR}/system_prompt.txt"
    if [[ -f "$PROMPT_FILE" ]]; then
        log_info "Loading enriched system prompt from adapter: ${USE_CASE}"
        ENRICHMENT_FILE="${PARLANT_GUIDELINES_DIR}/enrichment.md"
        {
            echo "# Domain-Specific Knowledge Enrichment"
            echo "# Source: finetune/adapters/${USE_CASE}/system_prompt.txt"
            echo ""
            cat "$PROMPT_FILE"
        } > "$ENRICHMENT_FILE"
    fi
fi

# -------------------------------------------------------------------
# 8. Export Parlant environment variables
# -------------------------------------------------------------------
export PARLANT_LOG_LEVEL="${LOG_LEVEL}"

# -------------------------------------------------------------------
# 9. Start Parlant server
# -------------------------------------------------------------------
log_info "Starting Parlant server on port ${PARLANT_PORT}..."
log_info "  API:  http://0.0.0.0:${PARLANT_PORT}"
log_info "  MCP:  http://0.0.0.0:${PARLANT_MCP_PORT}"
log_info "  Logs: ${LOG_LEVEL}"

# Check if parlant-server is available
if command -v parlant-server > /dev/null 2>&1; then
    exec parlant-server \
        --host 0.0.0.0 \
        --port "${PARLANT_PORT}"
elif command -v parlant > /dev/null 2>&1; then
    exec parlant server \
        --host 0.0.0.0 \
        --port "${PARLANT_PORT}"
else
    # Try Python module
    exec python3 -m parlant.server \
        --host 0.0.0.0 \
        --port "${PARLANT_PORT}"
fi
