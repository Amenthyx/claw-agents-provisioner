#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — NanoClaw Entrypoint
# ===================================================================
# NanoClaw has NO config file — it is designed to be configured by
# Claude Code modifying source code directly. This entrypoint uses
# sed/envsubst to patch NanoClaw source files with values from the
# unified .env before building and starting the agent.
#
# NanoClaw source: https://github.com/qwibitai/nanoclaw
# Channels: WhatsApp (Baileys), Telegram, Discord, Slack, Signal
#
# This script:
#   1. Reads unified env vars
#   2. Translates to NanoClaw-expected env var names
#   3. Patches NanoClaw source files with sed where needed
#   4. Injects system prompt enrichment into CLAUDE.md
#   5. Starts NanoClaw
#
# Usage (Docker): CMD ["./nanoclaw/entrypoint.sh"]
# Usage (native): CLAW_LLM_PROVIDER=anthropic ./nanoclaw/entrypoint.sh
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
NANOCLAW_HOME="${HOME}/.nanoclaw"
NANOCLAW_DIR="${NANOCLAW_SRC_DIR:-/opt/nanoclaw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_info() {
    echo -e "\033[1;34m[nanoclaw-entrypoint]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[nanoclaw-entrypoint]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[nanoclaw-entrypoint]\033[0m $*"
}

env_or_default() {
    local var_name="$1"
    local default_value="${2:-}"
    echo "${!var_name:-$default_value}"
}

# Safely apply sed substitution — skip if file does not exist
safe_sed() {
    local pattern="$1"
    local file="$2"
    if [[ -f "$file" ]]; then
        sed -i "$pattern" "$file"
    fi
}

# -------------------------------------------------------------------
# 1. Create NanoClaw home directory
# -------------------------------------------------------------------
mkdir -p "${NANOCLAW_HOME}"

# -------------------------------------------------------------------
# 2. Translate unified env vars to NanoClaw-expected names
# -------------------------------------------------------------------
log_info "Translating unified env vars to NanoClaw format..."

PROVIDER=$(env_or_default "CLAW_LLM_PROVIDER" "anthropic")
MODEL=$(env_or_default "CLAW_LLM_MODEL" "claude-sonnet-4-6")
CHANNEL=$(env_or_default "NANOCLAW_CHANNEL" "telegram")
MAX_MEMORY=$(env_or_default "NANOCLAW_MAX_MEMORY_MB" "512")

# 2a. Map LLM provider API key to NanoClaw's expected env var
# NanoClaw primarily expects CLAUDE_API_KEY for Anthropic
case "$PROVIDER" in
    anthropic)
        API_KEY=$(env_or_default "ANTHROPIC_API_KEY" "")
        if [[ -n "$API_KEY" ]]; then
            export CLAUDE_API_KEY="${API_KEY}"
            export ANTHROPIC_API_KEY="${API_KEY}"
        fi
        ;;
    openai)
        API_KEY=$(env_or_default "OPENAI_API_KEY" "")
        if [[ -n "$API_KEY" ]]; then
            export OPENAI_API_KEY="${API_KEY}"
        fi
        ;;
    openrouter)
        API_KEY=$(env_or_default "OPENROUTER_API_KEY" "")
        if [[ -n "$API_KEY" ]]; then
            export OPENROUTER_API_KEY="${API_KEY}"
        fi
        ;;
    deepseek)
        API_KEY=$(env_or_default "DEEPSEEK_API_KEY" "")
        if [[ -n "$API_KEY" ]]; then
            export DEEPSEEK_API_KEY="${API_KEY}"
        fi
        ;;
    *)
        API_KEY=$(env_or_default "ANTHROPIC_API_KEY" "")
        if [[ -n "$API_KEY" ]]; then
            export CLAUDE_API_KEY="${API_KEY}"
        fi
        log_warn "Unknown provider '${PROVIDER}', falling back to Anthropic."
        ;;
esac

if [[ -z "${API_KEY:-}" ]]; then
    log_error "No API key found for provider '${PROVIDER}'. Set the appropriate *_API_KEY env var."
    exit 1
fi

# 2b. Map channel tokens to NanoClaw-expected env var names
TELEGRAM_TOKEN=$(env_or_default "TELEGRAM_BOT_TOKEN" "")
DISCORD_TOKEN=$(env_or_default "DISCORD_BOT_TOKEN" "")
SLACK_TOKEN=$(env_or_default "SLACK_BOT_TOKEN" "")
WHATSAPP_SESSION=$(env_or_default "WHATSAPP_SESSION_DATA" "")

case "$CHANNEL" in
    telegram)
        if [[ -n "$TELEGRAM_TOKEN" ]]; then
            export TELEGRAM_TOKEN="${TELEGRAM_TOKEN}"
            log_info "Telegram channel configured."
        else
            log_warn "TELEGRAM_BOT_TOKEN not set — Telegram channel will not work."
        fi
        ;;
    discord)
        if [[ -n "$DISCORD_TOKEN" ]]; then
            export DISCORD_TOKEN="${DISCORD_TOKEN}"
            log_info "Discord channel configured."
        else
            log_warn "DISCORD_BOT_TOKEN not set — Discord channel will not work."
        fi
        ;;
    whatsapp)
        if [[ -n "$WHATSAPP_SESSION" ]]; then
            export WA_SESSION="${WHATSAPP_SESSION}"
            log_info "WhatsApp channel configured."
        else
            log_warn "WHATSAPP_SESSION_DATA not set — WhatsApp channel will not work."
        fi
        ;;
    slack)
        if [[ -n "$SLACK_TOKEN" ]]; then
            export SLACK_TOKEN="${SLACK_TOKEN}"
            SLACK_APP=$(env_or_default "SLACK_APP_TOKEN" "")
            [[ -n "$SLACK_APP" ]] && export SLACK_APP_TOKEN="${SLACK_APP}"
            log_info "Slack channel configured."
        else
            log_warn "SLACK_BOT_TOKEN not set — Slack channel will not work."
        fi
        ;;
    signal)
        SIGNAL_PHONE=$(env_or_default "SIGNAL_PHONE_NUMBER" "")
        if [[ -n "$SIGNAL_PHONE" ]]; then
            export SIGNAL_PHONE_NUMBER="${SIGNAL_PHONE}"
            log_info "Signal channel configured."
        else
            log_warn "SIGNAL_PHONE_NUMBER not set — Signal channel will not work."
        fi
        ;;
    *)
        log_warn "Unknown channel '${CHANNEL}', defaulting to telegram."
        [[ -n "$TELEGRAM_TOKEN" ]] && export TELEGRAM_TOKEN="${TELEGRAM_TOKEN}"
        ;;
esac

# -------------------------------------------------------------------
# 3. Patch NanoClaw source files with configuration
# -------------------------------------------------------------------
log_info "Patching NanoClaw source with configuration..."

if [[ -d "${NANOCLAW_DIR}/src" ]]; then
    # 3a. Replace hardcoded model references with configured model
    for src_file in $(find "${NANOCLAW_DIR}/src" -name "*.ts" -o -name "*.js" 2>/dev/null || true); do
        safe_sed "s/claude-sonnet-4-20250514/${MODEL}/g" "$src_file"
        safe_sed "s/claude-3-5-sonnet-20241022/${MODEL}/g" "$src_file"
        safe_sed "s/claude-3-sonnet-20240229/${MODEL}/g" "$src_file"
    done
    # 3a-verify. Validate that model replacement actually took effect
    PATCHED_COUNT=$(grep -rl "${MODEL}" "${NANOCLAW_DIR}/src" 2>/dev/null | wc -l)
    if [[ "$PATCHED_COUNT" -gt 0 ]]; then
        log_info "Model references patched to: ${MODEL} (found in ${PATCHED_COUNT} file(s))"
    else
        log_warn "Model replacement could not be verified — no files contain '${MODEL}' after patching."
    fi

    # 3b. Patch sandbox runtime if configured
    SANDBOX_RUNTIME=$(env_or_default "NANOCLAW_SANDBOX_RUNTIME" "docker")
    if [[ "$SANDBOX_RUNTIME" == "none" ]]; then
        for src_file in $(find "${NANOCLAW_DIR}/src" -name "*.ts" -o -name "*.js" 2>/dev/null || true); do
            safe_sed "s/useDocker: true/useDocker: false/g" "$src_file"
            safe_sed "s/sandbox: true/sandbox: false/g" "$src_file"
        done
        log_info "Sandbox runtime disabled."
    fi
else
    log_warn "NanoClaw src directory not found at ${NANOCLAW_DIR}/src — skipping source patching."
fi

# -------------------------------------------------------------------
# 4. Inject assessment-derived configuration
# -------------------------------------------------------------------
CLIENT_INDUSTRY=$(env_or_default "CLAW_CLIENT_INDUSTRY" "")
CLIENT_LANGUAGE=$(env_or_default "CLAW_CLIENT_LANGUAGE" "en")
CLIENT_NAME=$(env_or_default "CLAW_CLIENT_NAME" "")
SKILLS=$(env_or_default "CLAW_SKILLS" "")

# -------------------------------------------------------------------
# 5. System prompt enrichment — inject into CLAUDE.md
# -------------------------------------------------------------------
SYSTEM_PROMPT_ENRICHMENT=$(env_or_default "CLAW_SYSTEM_PROMPT_ENRICHMENT" "false")
USE_CASE=$(env_or_default "CLAW_FINETUNE_USE_CASE" "")
ADAPTER_PATH=$(env_or_default "CLAW_ADAPTER_PATH" "")

# Check for enriched system prompt from adapter path (legacy support)
if [[ -n "$ADAPTER_PATH" ]] && [[ -f "${ADAPTER_PATH}/system_prompt.txt" ]]; then
    export NANOCLAW_SYSTEM_PROMPT=$(cat "${ADAPTER_PATH}/system_prompt.txt")
    log_info "Loaded enriched system prompt from adapter path: ${ADAPTER_PATH}"
fi

# Check for system prompt enrichment from use case config
if [[ "$SYSTEM_PROMPT_ENRICHMENT" == "true" ]]; then
    CLAUDE_MD="${NANOCLAW_DIR}/CLAUDE.md"

    # Build enrichment content
    ENRICHMENT_CONTENT=""

    # Load use-case-specific system prompt
    if [[ -n "$USE_CASE" ]]; then
        PROMPT_FILE="${SCRIPT_DIR}/../finetune/adapters/${USE_CASE}/system_prompt.txt"
        if [[ -f "$PROMPT_FILE" ]]; then
            ENRICHMENT_CONTENT=$(cat "$PROMPT_FILE")
            log_info "Loaded system prompt from: ${PROMPT_FILE}"
        else
            log_warn "System prompt file not found: ${PROMPT_FILE}"
        fi
    fi

    # Build context block from assessment fields
    CONTEXT_LINES=""
    [[ -n "$CLIENT_INDUSTRY" ]] && CONTEXT_LINES="${CONTEXT_LINES}\n- Industry: ${CLIENT_INDUSTRY}"
    [[ -n "$CLIENT_LANGUAGE" && "$CLIENT_LANGUAGE" != "en" ]] && CONTEXT_LINES="${CONTEXT_LINES}\n- Primary language: ${CLIENT_LANGUAGE}"
    [[ -n "$CLIENT_NAME" ]] && CONTEXT_LINES="${CONTEXT_LINES}\n- Client: ${CLIENT_NAME}"
    [[ -n "$SKILLS" ]] && CONTEXT_LINES="${CONTEXT_LINES}\n- Installed skills: ${SKILLS}"

    # Append to CLAUDE.md if any assessment env vars are set or we have enrichment content
    if [[ -n "$ENRICHMENT_CONTENT" || -n "$CONTEXT_LINES" || -n "$CLIENT_INDUSTRY" || -n "$CLIENT_LANGUAGE" || -n "$(env_or_default "CLAW_DATA_SENSITIVITY" "")" ]]; then
        if [[ -f "$CLAUDE_MD" ]]; then
            {
                echo ""
                echo "## Domain Specialization (auto-generated by claw-agents-provisioner)"
                if [[ -n "$CONTEXT_LINES" ]]; then
                    echo -e "\n### Client Context${CONTEXT_LINES}"
                fi
                if [[ -n "$ENRICHMENT_CONTENT" ]]; then
                    echo -e "\n### Domain Knowledge\n${ENRICHMENT_CONTENT}"
                fi
            } >> "$CLAUDE_MD"
            log_info "CLAUDE.md enriched with domain context."
        else
            log_warn "CLAUDE.md not found at ${CLAUDE_MD} — creating new file."
            {
                echo "# NanoClaw Agent Configuration"
                echo ""
                echo "## Domain Specialization (auto-generated by claw-agents-provisioner)"
                if [[ -n "$CONTEXT_LINES" ]]; then
                    echo -e "\n### Client Context${CONTEXT_LINES}"
                fi
                if [[ -n "$ENRICHMENT_CONTENT" ]]; then
                    echo -e "\n### Domain Knowledge\n${ENRICHMENT_CONTENT}"
                fi
            } > "$CLAUDE_MD"
        fi
    fi
fi

# -------------------------------------------------------------------
# 6. Start NanoClaw
# -------------------------------------------------------------------
log_info "Starting NanoClaw (channel: ${CHANNEL}, model: ${MODEL})..."

# Try standard NanoClaw locations
if [[ -d "${NANOCLAW_DIR}" ]]; then
    cd "${NANOCLAW_DIR}"
elif [[ -d "${NANOCLAW_HOME}" ]]; then
    cd "${NANOCLAW_HOME}"
else
    log_error "NanoClaw source directory not found at ${NANOCLAW_DIR} or ${NANOCLAW_HOME}."
    exit 1
fi

# Verify that at least one way to run NanoClaw exists before attempting start
if [[ ! -f "package.json" && ! -f "src/index.js" && ! -f "dist/index.js" ]]; then
    log_error "Could not determine how to start NanoClaw. No package.json, src/index.js, or dist/index.js found in $(pwd)."
    exit 1
fi

# Start using available package manager or direct node
if [[ -f "package.json" ]]; then
    if command -v pnpm > /dev/null 2>&1; then
        exec pnpm run start
    elif command -v npm > /dev/null 2>&1; then
        exec npm run start
    else
        log_error "package.json found but neither pnpm nor npm is available in PATH."
        exit 1
    fi
fi

# Fallback: direct node execution
if ! command -v node > /dev/null 2>&1; then
    log_error "node binary not found in PATH. Cannot start NanoClaw."
    exit 1
fi

if [[ -f "src/index.js" ]]; then
    exec node src/index.js
elif [[ -f "dist/index.js" ]]; then
    exec node dist/index.js
else
    log_error "Could not determine how to start NanoClaw. No start script or index.js found."
    exit 1
fi
