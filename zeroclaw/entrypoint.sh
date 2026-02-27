#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — ZeroClaw Entrypoint
# ===================================================================
# Translates unified .env variables into ZeroClaw's TOML config format
# and starts the ZeroClaw agent.
#
# ZeroClaw config: ~/.zeroclaw/config.toml (TOML format)
# Credential resolution order:
#   explicit api_key > provider env var > ZEROCLAW_API_KEY > API_KEY
#
# This script:
#   1. Reads unified env vars (from .env / Docker environment)
#   2. Generates ~/.zeroclaw/config.toml
#   3. Optionally loads LoRA adapter config
#   4. Starts zeroclaw
#
# Usage (Docker): CMD ["./zeroclaw/entrypoint.sh"]
# Usage (native): CLAW_LLM_PROVIDER=anthropic ./zeroclaw/entrypoint.sh
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
ZEROCLAW_CONFIG_DIR="${HOME}/.zeroclaw"
ZEROCLAW_CONFIG_FILE="${ZEROCLAW_CONFIG_DIR}/config.toml"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[zeroclaw-entrypoint]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[zeroclaw-entrypoint]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[zeroclaw-entrypoint]\033[0m $*"
}

# Safely read an env var with a default value
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
# 1. Resolve LLM provider configuration
# -------------------------------------------------------------------
log_info "Resolving LLM provider configuration..."

PROVIDER=$(env_or_default "CLAW_LLM_PROVIDER" "anthropic")
MODEL=$(env_or_default "CLAW_LLM_MODEL" "claude-sonnet-4-6")
LOG_LEVEL=$(env_or_default "ZEROCLAW_LOG_LEVEL" "info")

# Map unified provider names to ZeroClaw provider identifiers
case "$PROVIDER" in
    anthropic)
        PROVIDER_KEY="anthropic"
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        API_BASE=""
        ;;
    openai)
        PROVIDER_KEY="openai"
        API_KEY=$(read_secret "OPENAI_API_KEY" "")
        API_BASE=""
        ;;
    openrouter)
        PROVIDER_KEY="openrouter"
        API_KEY=$(read_secret "OPENROUTER_API_KEY" "")
        API_BASE="https://openrouter.ai/api/v1"
        ;;
    deepseek)
        PROVIDER_KEY="deepseek"
        API_KEY=$(read_secret "DEEPSEEK_API_KEY" "")
        API_BASE="https://api.deepseek.com/v1"
        ;;
    gemini)
        PROVIDER_KEY="google"
        API_KEY=$(read_secret "GEMINI_API_KEY" "")
        API_BASE=""
        ;;
    groq)
        PROVIDER_KEY="groq"
        API_KEY=$(read_secret "GROQ_API_KEY" "")
        API_BASE=""
        ;;
    local)
        PROVIDER_KEY="local"
        API_KEY="local"
        API_BASE=$(env_or_default "CLAW_LOCAL_LLM_ENDPOINT" "http://host.docker.internal:11434/v1")
        log_info "Using local LLM provider at ${API_BASE}"
        ;;
    *)
        log_warn "Unknown provider '${PROVIDER}', defaulting to anthropic."
        PROVIDER_KEY="anthropic"
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        API_BASE=""
        ;;
esac

if [[ -z "$API_KEY" ]] && [[ "$PROVIDER" != "local" ]]; then
    log_error "No API key found for provider '${PROVIDER}'. Set the appropriate *_API_KEY env var."
    exit 1
fi

# -------------------------------------------------------------------
# 2. Resolve chat channel configuration
# -------------------------------------------------------------------
log_info "Resolving chat channel configuration..."

TELEGRAM_TOKEN=$(read_secret "TELEGRAM_BOT_TOKEN" "")
DISCORD_TOKEN=$(read_secret "DISCORD_BOT_TOKEN" "")
SLACK_TOKEN=$(read_secret "SLACK_BOT_TOKEN" "")

# -------------------------------------------------------------------
# 3. Create config directory
# -------------------------------------------------------------------
mkdir -p "${ZEROCLAW_CONFIG_DIR}"

# -------------------------------------------------------------------
# 4. Generate config.toml
# -------------------------------------------------------------------
log_info "Generating ${ZEROCLAW_CONFIG_FILE}..."

cat > "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF
# ===================================================================
# ZeroClaw Configuration — Auto-generated by claw-agents-provisioner
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ===================================================================
# WARNING: This file is regenerated on each container start.
# For persistent overrides, use ZEROCLAW_EXTRA_TOML env var.
# ===================================================================

[general]
log_level = "${LOG_LEVEL}"

[llm]
provider = "${PROVIDER_KEY}"
model = "${MODEL}"
api_key = "${API_KEY}"
TOML_EOF

# Add API base URL if specified (for OpenRouter, DeepSeek, etc.)
if [[ -n "$API_BASE" ]]; then
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF
api_base = "${API_BASE}"
TOML_EOF
fi

# -------------------------------------------------------------------
# 5. Add chat channel configuration
# -------------------------------------------------------------------
if [[ -n "$TELEGRAM_TOKEN" ]]; then
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[channels.telegram]
enabled = true
bot_token = "${TELEGRAM_TOKEN}"
TOML_EOF
    log_info "Telegram channel configured."
fi

if [[ -n "$DISCORD_TOKEN" ]]; then
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[channels.discord]
enabled = true
bot_token = "${DISCORD_TOKEN}"
TOML_EOF
    log_info "Discord channel configured."
fi

if [[ -n "$SLACK_TOKEN" ]]; then
    SLACK_APP=$(read_secret "SLACK_APP_TOKEN" "")
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[channels.slack]
enabled = true
bot_token = "${SLACK_TOKEN}"
TOML_EOF
    if [[ -n "$SLACK_APP" ]]; then
        cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF
app_token = "${SLACK_APP}"
TOML_EOF
    fi
    log_info "Slack channel configured."
fi

# -------------------------------------------------------------------
# 6. Add assessment-derived configuration
# -------------------------------------------------------------------
CLIENT_INDUSTRY=$(env_or_default "CLAW_CLIENT_INDUSTRY" "")
CLIENT_LANGUAGE=$(env_or_default "CLAW_CLIENT_LANGUAGE" "")
DATA_SENSITIVITY=$(env_or_default "CLAW_DATA_SENSITIVITY" "")
COMPLIANCE=$(env_or_default "CLAW_COMPLIANCE" "")

if [[ -n "$CLIENT_INDUSTRY" || -n "$CLIENT_LANGUAGE" || -n "$DATA_SENSITIVITY" ]]; then
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[agent]
TOML_EOF

    [[ -n "$CLIENT_INDUSTRY" ]] && echo "industry = \"${CLIENT_INDUSTRY}\"" >> "${ZEROCLAW_CONFIG_FILE}"
    [[ -n "$CLIENT_LANGUAGE" ]] && echo "language = \"${CLIENT_LANGUAGE}\"" >> "${ZEROCLAW_CONFIG_FILE}"
    [[ -n "$DATA_SENSITIVITY" ]] && echo "data_sensitivity = \"${DATA_SENSITIVITY}\"" >> "${ZEROCLAW_CONFIG_FILE}"
    [[ -n "$COMPLIANCE" && "$COMPLIANCE" != "none" ]] && echo "compliance = \"${COMPLIANCE}\"" >> "${ZEROCLAW_CONFIG_FILE}"
fi

# -------------------------------------------------------------------
# 7. Add adapter / fine-tuning configuration
# -------------------------------------------------------------------
ADAPTER_PATH=$(env_or_default "CLAW_ADAPTER_PATH" "")
FINETUNE_ENABLED=$(env_or_default "CLAW_FINETUNE_ENABLED" "false")

if [[ -n "$ADAPTER_PATH" && -d "$ADAPTER_PATH" ]]; then
    cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[adapter]
enabled = true
path = "${ADAPTER_PATH}"
TOML_EOF
    log_info "LoRA adapter configured from: ${ADAPTER_PATH}"
elif [[ "$FINETUNE_ENABLED" == "true" ]]; then
    log_warn "Fine-tuning is enabled but no CLAW_ADAPTER_PATH provided. Adapter will need to be trained first."
fi

# -------------------------------------------------------------------
# 8. Add system prompt enrichment for API-only models
# -------------------------------------------------------------------
SYSTEM_PROMPT_ENRICHMENT=$(env_or_default "CLAW_SYSTEM_PROMPT_ENRICHMENT" "false")
USE_CASE=$(env_or_default "CLAW_FINETUNE_USE_CASE" "")

if [[ "$SYSTEM_PROMPT_ENRICHMENT" == "true" && -n "$USE_CASE" ]]; then
    PROMPT_FILE="${SCRIPT_DIR:-/app}/../finetune/adapters/${USE_CASE}/system_prompt.txt"
    if [[ -f "$PROMPT_FILE" ]]; then
        # Read system prompt and escape for TOML (escape quotes, replace newlines with \n)
        SYSTEM_PROMPT=$(printf '%s' "$(cat "$PROMPT_FILE")" | sed 's/"/\\"/g; s/$/\\n/' | tr -d '\n')
        cat >> "${ZEROCLAW_CONFIG_FILE}" << TOML_EOF

[system_prompt]
enriched = true
content = "${SYSTEM_PROMPT}"
TOML_EOF
        log_info "System prompt enrichment applied from: ${PROMPT_FILE}"
    else
        log_warn "System prompt file not found: ${PROMPT_FILE}"
    fi
fi

# -------------------------------------------------------------------
# 9. Append extra TOML if provided
# -------------------------------------------------------------------
EXTRA_TOML=$(env_or_default "ZEROCLAW_EXTRA_TOML" "")
if [[ -n "$EXTRA_TOML" ]]; then
    echo "" >> "${ZEROCLAW_CONFIG_FILE}"
    echo "# === Extra TOML (from ZEROCLAW_EXTRA_TOML) ===" >> "${ZEROCLAW_CONFIG_FILE}"
    echo -e "$EXTRA_TOML" >> "${ZEROCLAW_CONFIG_FILE}"
    log_info "Extra TOML configuration appended."
fi

log_info "Config written to ${ZEROCLAW_CONFIG_FILE}"

# -------------------------------------------------------------------
# 10. Start ZeroClaw
# -------------------------------------------------------------------
log_info "Starting ZeroClaw agent..."

# If zeroclaw binary is available, start it
if command -v zeroclaw > /dev/null 2>&1; then
    exec zeroclaw start
else
    log_error "zeroclaw binary not found in PATH."
    log_error "Ensure ZeroClaw is installed. Run: install-zeroclaw.sh"
    exit 1
fi
