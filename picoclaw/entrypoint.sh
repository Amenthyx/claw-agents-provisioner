#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — PicoClaw Entrypoint
# ===================================================================
# Translates unified .env variables into PicoClaw's JSON config format
# and starts the PicoClaw agent.
#
# PicoClaw config: ~/.picoclaw/config.json (JSON format)
# Simplest agent to automate — single Go binary, JSON config.
# Targets low-resource hardware (RISC-V, ARM, Raspberry Pi).
#
# This script:
#   1. Reads unified env vars
#   2. Translates to PicoClaw-expected env var names
#   3. Generates ~/.picoclaw/config.json with full configuration
#   4. Optionally configures adapter endpoint
#   5. Starts picoclaw
#
# Usage (Docker): CMD ["./picoclaw/entrypoint.sh"]
# Usage (native): CLAW_LLM_PROVIDER=deepseek ./picoclaw/entrypoint.sh
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
PICOCLAW_HOME="${HOME}/.picoclaw"
CONFIG_FILE="${PICOCLAW_HOME}/config.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[picoclaw-entrypoint]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[picoclaw-entrypoint]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[picoclaw-entrypoint]\033[0m $*"
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

# JSON-escape a string value
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
# 1. Create PicoClaw home directory
# -------------------------------------------------------------------
mkdir -p "${PICOCLAW_HOME}"

# -------------------------------------------------------------------
# 2. Translate unified env vars to PicoClaw-expected names
# -------------------------------------------------------------------
log_info "Translating unified env vars to PicoClaw format..."

PROVIDER=$(env_or_default "CLAW_LLM_PROVIDER" "deepseek")
MODEL=$(env_or_default "CLAW_LLM_MODEL" "deepseek-chat")
LOG_LEVEL=$(env_or_default "PICOCLAW_LOG_LEVEL" "info")
GATEWAY_HOST=$(env_or_default "PICOCLAW_GATEWAY_HOST" "0.0.0.0")
GATEWAY_PORT=$(env_or_default "PICOCLAW_GATEWAY_PORT" "8080")

# Map provider to API key and export PicoClaw-expected vars
case "$PROVIDER" in
    anthropic)
        API_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_ANTHROPIC_KEY="${API_KEY}"
        API_BASE="https://api.anthropic.com/v1"
        ;;
    openai)
        API_KEY=$(read_secret "OPENAI_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_OPENAI_KEY="${API_KEY}"
        API_BASE="https://api.openai.com/v1"
        ;;
    openrouter)
        API_KEY=$(read_secret "OPENROUTER_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_OPENROUTER_KEY="${API_KEY}"
        API_BASE="https://openrouter.ai/api/v1"
        ;;
    deepseek)
        API_KEY=$(read_secret "DEEPSEEK_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_API_KEY="${API_KEY}"
        API_BASE="https://api.deepseek.com/v1"
        ;;
    gemini)
        API_KEY=$(read_secret "GEMINI_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_GEMINI_KEY="${API_KEY}"
        API_BASE="https://generativelanguage.googleapis.com/v1beta"
        ;;
    groq)
        API_KEY=$(read_secret "GROQ_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_GROQ_KEY="${API_KEY}"
        API_BASE="https://api.groq.com/openai/v1"
        ;;
    *)
        API_KEY=$(read_secret "DEEPSEEK_API_KEY" "")
        [[ -n "$API_KEY" ]] && export PICOCLAW_API_KEY="${API_KEY}"
        API_BASE="https://api.deepseek.com/v1"
        log_warn "Unknown provider '${PROVIDER}', defaulting to deepseek."
        ;;
esac

if [[ -z "${API_KEY:-}" ]]; then
    log_error "No API key found for provider '${PROVIDER}'. Set the appropriate *_API_KEY env var."
    exit 1
fi

# Also export any additional provider keys that are set
ANTHROPIC_KEY=$(read_secret "ANTHROPIC_API_KEY" "")
OPENAI_KEY=$(read_secret "OPENAI_API_KEY" "")
[[ -n "$ANTHROPIC_KEY" ]] && export PICOCLAW_ANTHROPIC_KEY="${ANTHROPIC_KEY}"
[[ -n "$OPENAI_KEY" ]] && export PICOCLAW_OPENAI_KEY="${OPENAI_KEY}"

# -------------------------------------------------------------------
# 3. Resolve assessment-derived fields
# -------------------------------------------------------------------
CLIENT_INDUSTRY=$(env_or_default "CLAW_CLIENT_INDUSTRY" "general")
CLIENT_LANGUAGE=$(env_or_default "CLAW_CLIENT_LANGUAGE" "en")
DATA_SENSITIVITY=$(env_or_default "CLAW_DATA_SENSITIVITY" "medium")
COMPLIANCE=$(env_or_default "CLAW_COMPLIANCE" "none")
SKILLS=$(env_or_default "CLAW_SKILLS" "")

# -------------------------------------------------------------------
# 4. Resolve adapter / fine-tuning fields
# -------------------------------------------------------------------
ADAPTER_PATH=$(env_or_default "CLAW_ADAPTER_PATH" "")
SYSTEM_PROMPT_ENRICHMENT=$(env_or_default "CLAW_SYSTEM_PROMPT_ENRICHMENT" "false")
USE_CASE=$(env_or_default "CLAW_FINETUNE_USE_CASE" "")

# -------------------------------------------------------------------
# 5. Build system prompt enrichment
# -------------------------------------------------------------------
ENRICHED_PROMPT=""
if [[ "$SYSTEM_PROMPT_ENRICHMENT" == "true" && -n "$USE_CASE" ]]; then
    PROMPT_FILE="${SCRIPT_DIR}/../finetune/adapters/${USE_CASE}/system_prompt.txt"
    if [[ -f "$PROMPT_FILE" ]]; then
        ENRICHED_PROMPT=$(cat "$PROMPT_FILE" | sed 's/"/\\"/g' | tr '\n' ' ')
        log_info "System prompt enrichment loaded from: ${PROMPT_FILE}"
    fi
fi

# Fallback: load from adapter path directly
if [[ -z "$ENRICHED_PROMPT" && -n "$ADAPTER_PATH" && -f "${ADAPTER_PATH}/system_prompt.txt" ]]; then
    ENRICHED_PROMPT=$(cat "${ADAPTER_PATH}/system_prompt.txt" | sed 's/"/\\"/g' | tr '\n' ' ')
    log_info "System prompt loaded from adapter path: ${ADAPTER_PATH}"
fi

# -------------------------------------------------------------------
# 6. Build skills array
# -------------------------------------------------------------------
SKILLS_JSON="[]"
if [[ -n "$SKILLS" ]]; then
    SKILLS_JSON="["
    IFS=',' read -ra SKILL_ARRAY <<< "$SKILLS"
    for i in "${!SKILL_ARRAY[@]}"; do
        SKILL=$(echo "${SKILL_ARRAY[$i]}" | xargs)
        [[ $i -gt 0 ]] && SKILLS_JSON="${SKILLS_JSON}, "
        SKILLS_JSON="${SKILLS_JSON}\"$(json_escape "$SKILL")\""
    done
    SKILLS_JSON="${SKILLS_JSON}]"
fi

# -------------------------------------------------------------------
# 7. Build channel configuration
# -------------------------------------------------------------------
TELEGRAM_TOKEN=$(read_secret "TELEGRAM_BOT_TOKEN" "")
DISCORD_TOKEN=$(read_secret "DISCORD_BOT_TOKEN" "")
SLACK_TOKEN=$(read_secret "SLACK_BOT_TOKEN" "")

CHANNELS_ITEMS=""
if [[ -n "$TELEGRAM_TOKEN" ]]; then
    CHANNELS_ITEMS="${CHANNELS_ITEMS}    {\"type\": \"telegram\", \"bot_token\": \"$(json_escape "$TELEGRAM_TOKEN")\"}"
    log_info "Telegram channel configured."
fi
if [[ -n "$DISCORD_TOKEN" ]]; then
    [[ -n "$CHANNELS_ITEMS" ]] && CHANNELS_ITEMS="${CHANNELS_ITEMS},
"
    CHANNELS_ITEMS="${CHANNELS_ITEMS}    {\"type\": \"discord\", \"bot_token\": \"$(json_escape "$DISCORD_TOKEN")\"}"
    log_info "Discord channel configured."
fi
if [[ -n "$SLACK_TOKEN" ]]; then
    [[ -n "$CHANNELS_ITEMS" ]] && CHANNELS_ITEMS="${CHANNELS_ITEMS},
"
    CHANNELS_ITEMS="${CHANNELS_ITEMS}    {\"type\": \"slack\", \"bot_token\": \"$(json_escape "$SLACK_TOKEN")\"}"
    log_info "Slack channel configured."
fi

# -------------------------------------------------------------------
# 8. Build model_list with optional adapter endpoint
# -------------------------------------------------------------------
MODEL_LIST="    {
      \"model_name\": \"$(json_escape "$MODEL")\",
      \"litellm_params\": {
        \"model\": \"$(json_escape "$PROVIDER/$MODEL")\",
        \"api_key\": \"$(json_escape "$API_KEY")\",
        \"api_base\": \"$(json_escape "$API_BASE")\"
      }
    }"

if [[ -n "$ADAPTER_PATH" ]]; then
    MODEL_LIST="${MODEL_LIST},
    {
      \"model_name\": \"local-adapter\",
      \"litellm_params\": {
        \"model\": \"openai/local-adapter\",
        \"api_base\": \"http://localhost:8000/v1\",
        \"api_key\": \"local\"
      }
    }"
    log_info "Local adapter endpoint added to model list."
fi

# -------------------------------------------------------------------
# 9. Generate config.json
# -------------------------------------------------------------------
log_info "Generating ${CONFIG_FILE}..."

cat > "${CONFIG_FILE}" << JSON_EOF
{
  "_generated_by": "claw-agents-provisioner",
  "_generated_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "log_level": "$(json_escape "$LOG_LEVEL")",
  "server": {
    "host": "$(json_escape "$GATEWAY_HOST")",
    "port": ${GATEWAY_PORT}
  },
  "llm": {
    "provider": "$(json_escape "$PROVIDER")",
    "model": "$(json_escape "$MODEL")"
  },
  "model_list": [
${MODEL_LIST}
  ],
  "channels": [
${CHANNELS_ITEMS}
  ],
  "agent": {
    "name": "$(json_escape "$CLIENT_INDUSTRY") PicoClaw Agent",
    "industry": "$(json_escape "$CLIENT_INDUSTRY")",
    "language": "$(json_escape "$CLIENT_LANGUAGE")",
    "data_sensitivity": "$(json_escape "$DATA_SENSITIVITY")",
    "compliance": "$(json_escape "$COMPLIANCE")",
    "skills": ${SKILLS_JSON},
    "max_memory_mb": 128
  }$(if [[ -n "$ENRICHED_PROMPT" ]]; then echo ",
  \"system_prompt\": \"$(json_escape "$ENRICHED_PROMPT")\""; fi)
}
JSON_EOF

log_info "Config written to ${CONFIG_FILE}"

# Validate that the generated config file exists and is valid JSON
if [[ ! -f "${CONFIG_FILE}" ]]; then
    log_error "Config file was not created at ${CONFIG_FILE}."
    exit 1
fi
if command -v python3 > /dev/null 2>&1; then
    if ! python3 -c "import json; json.load(open('${CONFIG_FILE}'))" 2>/dev/null; then
        log_error "Generated config file is not valid JSON: ${CONFIG_FILE}"
        exit 1
    fi
    log_info "Config JSON validated successfully."
elif command -v python > /dev/null 2>&1; then
    if ! python -c "import json; json.load(open('${CONFIG_FILE}'))" 2>/dev/null; then
        log_error "Generated config file is not valid JSON: ${CONFIG_FILE}"
        exit 1
    fi
    log_info "Config JSON validated successfully."
else
    log_warn "python3/python not found — skipping JSON validation of config file."
fi

# -------------------------------------------------------------------
# 10. Start PicoClaw
# -------------------------------------------------------------------
log_info "Starting PicoClaw agent..."
log_info "Gateway: ${GATEWAY_HOST}:${GATEWAY_PORT}, Model: ${MODEL}"

if command -v picoclaw > /dev/null 2>&1; then
    exec picoclaw serve --config "${CONFIG_FILE}"
else
    log_error "picoclaw binary not found in PATH."
    log_error "Ensure PicoClaw is installed. Run: install-picoclaw.sh"
    exit 1
fi
