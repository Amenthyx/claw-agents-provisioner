#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — OpenClaw Entrypoint
# ===================================================================
# Translates unified .env variables into OpenClaw's JSON5 config format
# and starts the OpenClaw agent.
#
# OpenClaw config: ~/.openclaw/openclaw.json (JSON5 format)
# OpenClaw env:    ~/.openclaw/.env
# Heaviest agent: Node.js 22, pnpm, ~1.5 GB RAM, 13+ channels.
#
# This script:
#   1. Reads unified env vars
#   2. Translates to OpenClaw-expected env var names
#   3. Generates ~/.openclaw/.env (OpenClaw-native env file)
#   4. Generates ~/.openclaw/openclaw.json (JSON5 config)
#   5. Optionally configures adapter/system prompt enrichment
#   6. Starts openclaw
#
# Usage (Docker): CMD ["./openclaw/entrypoint.sh"]
# Usage (native): CLAW_LLM_PROVIDER=anthropic ./openclaw/entrypoint.sh
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
OPENCLAW_HOME="${HOME}/.openclaw"
CONFIG_FILE="${OPENCLAW_HOME}/openclaw.json"
ENV_FILE="${OPENCLAW_HOME}/.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[openclaw-entrypoint]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[openclaw-entrypoint]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[openclaw-entrypoint]\033[0m $*"
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

json_escape() {
    local val="$1"
    val="${val//\\/\\\\}"
    val="${val//\"/\\\"}"
    echo "$val"
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
# 1. Create OpenClaw home directory
# -------------------------------------------------------------------
mkdir -p "${OPENCLAW_HOME}"

# -------------------------------------------------------------------
# 2. Resolve and translate LLM provider configuration
# -------------------------------------------------------------------
log_info "Translating unified env vars to OpenClaw format..."

PROVIDER=$(env_or_default "CLAW_LLM_PROVIDER" "anthropic")
MODEL=$(env_or_default "CLAW_LLM_MODEL" "claude-sonnet-4-6")
LOG_LEVEL=$(env_or_default "OPENCLAW_LOG_LEVEL" "info")
DM_POLICY=$(env_or_default "OPENCLAW_DM_POLICY" "pairing")
PORT=$(env_or_default "OPENCLAW_PORT" "3000")

# Map provider to OpenClaw env var name and provider ID
case "$PROVIDER" in
    anthropic)
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        OPENCLAW_KEY_VAR="ANTHROPIC_API_KEY"
        PROVIDER_ID="anthropic"
        ;;
    openai)
        API_KEY=$(read_secret "OPENAI_API_KEY" "")
        OPENCLAW_KEY_VAR="OPENAI_API_KEY"
        PROVIDER_ID="openai"
        ;;
    openrouter)
        API_KEY=$(read_secret "OPENROUTER_API_KEY" "")
        OPENCLAW_KEY_VAR="OPENROUTER_API_KEY"
        PROVIDER_ID="openrouter"
        ;;
    deepseek)
        API_KEY=$(read_secret "DEEPSEEK_API_KEY" "")
        OPENCLAW_KEY_VAR="DEEPSEEK_API_KEY"
        PROVIDER_ID="deepseek"
        ;;
    gemini)
        API_KEY=$(read_secret "GEMINI_API_KEY" "")
        OPENCLAW_KEY_VAR="GOOGLE_API_KEY"
        PROVIDER_ID="google"
        ;;
    groq)
        API_KEY=$(read_secret "GROQ_API_KEY" "")
        OPENCLAW_KEY_VAR="GROQ_API_KEY"
        PROVIDER_ID="groq"
        ;;
    *)
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        OPENCLAW_KEY_VAR="ANTHROPIC_API_KEY"
        PROVIDER_ID="anthropic"
        log_warn "Unknown provider '${PROVIDER}', defaulting to anthropic."
        ;;
esac

if [[ -z "${API_KEY:-}" ]]; then
    log_error "No API key found for provider '${PROVIDER}'. Set the appropriate *_API_KEY env var."
    exit 1
fi

# Export translated env vars for OpenClaw
export "OPENCLAW_ANTHROPIC_API_KEY=$(env_or_default "ANTHROPIC_API_KEY" "")"
export "OPENCLAW_OPENAI_API_KEY=$(env_or_default "OPENAI_API_KEY" "")"
export "OPENCLAW_OPENROUTER_API_KEY=$(env_or_default "OPENROUTER_API_KEY" "")"
export "OPENCLAW_DEEPSEEK_API_KEY=$(env_or_default "DEEPSEEK_API_KEY" "")"

# -------------------------------------------------------------------
# 3. Resolve channel tokens
# -------------------------------------------------------------------
TELEGRAM_TOKEN=$(read_secret "TELEGRAM_BOT_TOKEN" "")
DISCORD_TOKEN=$(read_secret "DISCORD_BOT_TOKEN" "")
SLACK_TOKEN=$(read_secret "SLACK_BOT_TOKEN" "")
SLACK_APP_TOKEN=$(read_secret "SLACK_APP_TOKEN" "")
WHATSAPP_SESSION=$(read_secret "WHATSAPP_SESSION_DATA" "")

# -------------------------------------------------------------------
# 4. Resolve assessment-derived fields
# -------------------------------------------------------------------
CLIENT_INDUSTRY=$(env_or_default "CLAW_CLIENT_INDUSTRY" "")
CLIENT_LANGUAGE=$(env_or_default "CLAW_CLIENT_LANGUAGE" "en")
CLIENT_NAME=$(env_or_default "CLAW_CLIENT_NAME" "")
DATA_SENSITIVITY=$(env_or_default "CLAW_DATA_SENSITIVITY" "medium")
COMPLIANCE=$(env_or_default "CLAW_COMPLIANCE" "none")
SKILLS=$(env_or_default "CLAW_SKILLS" "")

# -------------------------------------------------------------------
# 5. Resolve adapter / fine-tuning fields
# -------------------------------------------------------------------
ADAPTER_PATH=$(env_or_default "CLAW_ADAPTER_PATH" "")
SYSTEM_PROMPT_ENRICHMENT=$(env_or_default "CLAW_SYSTEM_PROMPT_ENRICHMENT" "false")
USE_CASE=$(env_or_default "CLAW_FINETUNE_USE_CASE" "")

# -------------------------------------------------------------------
# 6. Generate OpenClaw's native .env file
# -------------------------------------------------------------------
log_info "Generating ${ENV_FILE}..."

{
    echo "# Auto-generated by claw-agents-provisioner"
    echo "# Generated at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo ""
    echo "# Primary LLM Provider"
    echo "${OPENCLAW_KEY_VAR}=${API_KEY}"

    # Include all available provider keys (OpenClaw supports multi-provider)
    ANTHROPIC_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
    OPENAI_KEY=$(read_secret "OPENAI_API_KEY" "")
    OPENROUTER_KEY=$(read_secret "OPENROUTER_API_KEY" "")
    DEEPSEEK_KEY=$(read_secret "DEEPSEEK_API_KEY" "")

    [[ -n "$ANTHROPIC_KEY" && "$OPENCLAW_KEY_VAR" != "ANTHROPIC_API_KEY" ]] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_KEY}"
    [[ -n "$OPENAI_KEY" && "$OPENCLAW_KEY_VAR" != "OPENAI_API_KEY" ]] && echo "OPENAI_API_KEY=${OPENAI_KEY}"
    [[ -n "$OPENROUTER_KEY" && "$OPENCLAW_KEY_VAR" != "OPENROUTER_API_KEY" ]] && echo "OPENROUTER_API_KEY=${OPENROUTER_KEY}"
    [[ -n "$DEEPSEEK_KEY" && "$OPENCLAW_KEY_VAR" != "DEEPSEEK_API_KEY" ]] && echo "DEEPSEEK_API_KEY=${DEEPSEEK_KEY}"

    echo ""
    echo "# Channel Tokens"
    [[ -n "$TELEGRAM_TOKEN" ]] && echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}"
    [[ -n "$DISCORD_TOKEN" ]] && echo "DISCORD_BOT_TOKEN=${DISCORD_TOKEN}"
    [[ -n "$SLACK_TOKEN" ]] && echo "SLACK_BOT_TOKEN=${SLACK_TOKEN}"
    [[ -n "$SLACK_APP_TOKEN" ]] && echo "SLACK_APP_TOKEN=${SLACK_APP_TOKEN}"
} > "${ENV_FILE}"

log_info "OpenClaw .env written."

# -------------------------------------------------------------------
# 7. Build system prompt enrichment
# -------------------------------------------------------------------
ENRICHED_PROMPT=""

# Load from adapter path
if [[ -n "$ADAPTER_PATH" && -f "${ADAPTER_PATH}/system_prompt.txt" ]]; then
    ENRICHED_PROMPT=$(cat "${ADAPTER_PATH}/system_prompt.txt" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    export OPENCLAW_SYSTEM_PROMPT=$(cat "${ADAPTER_PATH}/system_prompt.txt")
    log_info "Loaded enriched system prompt from adapter path."
fi

# Load from use case config (overrides adapter path)
if [[ "$SYSTEM_PROMPT_ENRICHMENT" == "true" && -n "$USE_CASE" ]]; then
    PROMPT_FILE="${SCRIPT_DIR}/../finetune/adapters/${USE_CASE}/system_prompt.txt"
    if [[ -f "$PROMPT_FILE" ]]; then
        ENRICHED_PROMPT=$(cat "$PROMPT_FILE" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
        export OPENCLAW_SYSTEM_PROMPT=$(cat "$PROMPT_FILE")
        log_info "System prompt enrichment loaded from: ${PROMPT_FILE}"
    else
        log_warn "System prompt file not found: ${PROMPT_FILE}"
    fi
fi

# -------------------------------------------------------------------
# 8. Build skills array for JSON5
# -------------------------------------------------------------------
SKILLS_JSON5="[]"
if [[ -n "$SKILLS" ]]; then
    SKILLS_JSON5="["
    IFS=',' read -ra SKILL_ARRAY <<< "$SKILLS"
    for i in "${!SKILL_ARRAY[@]}"; do
        SKILL=$(echo "${SKILL_ARRAY[$i]}" | xargs)
        [[ $i -gt 0 ]] && SKILLS_JSON5="${SKILLS_JSON5}, "
        SKILLS_JSON5="${SKILLS_JSON5}\"$(json_escape "$SKILL")\""
    done
    SKILLS_JSON5="${SKILLS_JSON5}]"
fi

# -------------------------------------------------------------------
# 9. Build channels block for JSON5
# -------------------------------------------------------------------
CHANNELS_BLOCK=""
if [[ -n "$TELEGRAM_TOKEN" ]]; then
    CHANNELS_BLOCK="${CHANNELS_BLOCK}
    telegram: { enabled: true },"
    log_info "Telegram channel configured."
fi
if [[ -n "$DISCORD_TOKEN" ]]; then
    CHANNELS_BLOCK="${CHANNELS_BLOCK}
    discord: { enabled: true },"
    log_info "Discord channel configured."
fi
if [[ -n "$SLACK_TOKEN" ]]; then
    CHANNELS_BLOCK="${CHANNELS_BLOCK}
    slack: { enabled: true },"
    log_info "Slack channel configured."
fi
if [[ -n "$WHATSAPP_SESSION" ]]; then
    CHANNELS_BLOCK="${CHANNELS_BLOCK}
    whatsapp: { enabled: true },"
    log_info "WhatsApp channel configured."
fi

# -------------------------------------------------------------------
# 10. Generate openclaw.json (JSON5 format)
# -------------------------------------------------------------------
log_info "Generating ${CONFIG_FILE}..."

{
    cat << JSON5_EOF
// ===================================================================
// OpenClaw Configuration — Auto-generated by claw-agents-provisioner
// Generated at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
// ===================================================================
{
  // LLM Configuration
  llm: {
    provider: "${PROVIDER_ID}",
    model: "$(json_escape "$MODEL")",
  },

  // Server Configuration
  server: {
    host: "0.0.0.0",
    port: ${PORT},
    logLevel: "${LOG_LEVEL}",
  },

  // Direct Message Policy
  dm: {
    policy: "${DM_POLICY}",
  },

  // Chat Channels (API keys read from ~/.openclaw/.env)
  channels: {${CHANNELS_BLOCK}
  },

  // Agent Configuration (assessment-derived)
  agent: {
    industry: "$(json_escape "$CLIENT_INDUSTRY")",
    language: "$(json_escape "$CLIENT_LANGUAGE")",
    dataSensitivity: "$(json_escape "$DATA_SENSITIVITY")",
    compliance: "$(json_escape "$COMPLIANCE")",
    skills: ${SKILLS_JSON5},
  },

  // Skills to install from the Claw skills catalog
  skills: ${SKILLS_JSON5},

  // DM routing policy
  dm_policy: "${DM_POLICY}",
JSON5_EOF

    # Add client name if set
    if [[ -n "$CLIENT_NAME" ]]; then
        echo "  clientName: \"$(json_escape "$CLIENT_NAME")\","
    fi

    # Add adapter config if present
    if [[ -n "$ADAPTER_PATH" ]]; then
        cat << JSON5_EOF

  // LoRA Adapter Configuration
  adapter: {
    enabled: true,
    path: "$(json_escape "$ADAPTER_PATH")",
  },
JSON5_EOF
        log_info "LoRA adapter configured from: ${ADAPTER_PATH}"
    fi

    # Add enriched system prompt if present
    if [[ -n "$ENRICHED_PROMPT" ]]; then
        echo ""
        echo "  // System Prompt Enrichment (domain specialization)"
        echo "  systemPrompt: \"$(json_escape "$ENRICHED_PROMPT")\","
    fi

    echo "}"
} > "${CONFIG_FILE}"

log_info "Config written to ${CONFIG_FILE}"

# -------------------------------------------------------------------
# 11. Start OpenClaw
# -------------------------------------------------------------------

# Consolidated function that tries each binary/method and exits 1 if all fail
start_openclaw() {
    # Try 1: openclaw binary in PATH
    if command -v openclaw > /dev/null 2>&1; then
        log_info "Found openclaw binary in PATH."
        exec openclaw start
    fi

    # Try 2: pnpm/npm from /opt/openclaw
    if [[ -d "/opt/openclaw" ]]; then
        cd /opt/openclaw
        if command -v pnpm > /dev/null 2>&1; then
            log_info "Starting via pnpm from /opt/openclaw."
            exec pnpm start
        elif command -v npm > /dev/null 2>&1; then
            log_info "Starting via npm from /opt/openclaw."
            exec npm start
        fi
    fi

    # Try 3: npx fallback
    if command -v npx > /dev/null 2>&1; then
        log_info "Falling back to npx openclaw..."
        exec npx openclaw start
    fi

    # All methods exhausted
    log_error "OpenClaw could not be started. Tried: openclaw binary, /opt/openclaw (pnpm/npm), npx."
    log_error "Ensure OpenClaw is installed. Run: install-openclaw.sh"
    exit 1
}

log_info "Starting OpenClaw agent..."
log_info "Port: ${PORT}, Model: ${MODEL}"

start_openclaw
