#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Claw Agents Provisioner — Interactive Installer
# =============================================================================
# Single entry point to set up the entire Claw platform.
# Walks the user through system provisioning, configuration, agent deployment,
# fine-tuning, and monitoring setup via an interactive menu.
#
# Usage:
#   ./install.sh              # Interactive menu
#   ./install.sh --full       # Run all steps non-interactively
#   ./install.sh --help       # Show usage
#
# Idempotent: safe to run any step multiple times.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Colors & UI ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()  { echo -e "${GREEN}[claw]${NC} $*"; }
info() { echo -e "${BLUE}[info]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; }
step() { echo -e "\n${MAGENTA}${BOLD}━━━ $* ━━━${NC}\n"; }

# --- Helpers ---
command_exists() { command -v "$1" &>/dev/null; }

prompt_yn() {
    local question="$1" default="${2:-y}"
    local prompt
    if [[ "$default" == "y" ]]; then prompt="[Y/n]"; else prompt="[y/N]"; fi
    echo -ne "${CYAN}$question ${prompt}:${NC} "
    read -r answer
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy] ]]
}

prompt_choice() {
    local question="$1"
    shift
    local options=("$@")
    echo -e "\n${CYAN}$question${NC}"
    for i in "${!options[@]}"; do
        echo -e "  ${BOLD}$((i + 1)))${NC} ${options[$i]}"
    done
    echo -ne "\n${CYAN}Enter choice [1-${#options[@]}]:${NC} "
    read -r choice
    echo "$choice"
}

prompt_input() {
    local question="$1" default="${2:-}"
    if [[ -n "$default" ]]; then
        echo -ne "${CYAN}$question ${DIM}[$default]${NC}: "
    else
        echo -ne "${CYAN}$question:${NC} "
    fi
    read -r answer
    echo "${answer:-$default}"
}

wait_key() {
    echo -ne "\n${DIM}Press Enter to continue...${NC}"
    read -r
}

# =============================================================================
#  Pre-flight: System Requirements Check
# =============================================================================

check_requirements() {
    step "System Requirements Check"

    local all_ok=true

    # Git
    if command_exists git; then
        log "Git: $(git --version | awk '{print $3}')"
    else
        warn "Git: not found"
        all_ok=false
    fi

    # Python
    if command_exists python3; then
        local pyver
        pyver=$(python3 --version 2>&1 | awk '{print $2}')
        local pymajor pyminor
        pymajor=$(echo "$pyver" | cut -d. -f1)
        pyminor=$(echo "$pyver" | cut -d. -f2)
        if [[ "$pymajor" -ge 3 ]] && [[ "$pyminor" -ge 8 ]]; then
            log "Python: $pyver"
        else
            warn "Python: $pyver (3.8+ recommended, 3.11+ ideal)"
        fi
    else
        warn "Python 3: not found"
        all_ok=false
    fi

    # pip
    if command_exists pip3 || python3 -m pip --version &>/dev/null 2>&1; then
        log "pip: available"
    else
        warn "pip: not found"
    fi

    # Docker
    if command_exists docker; then
        log "Docker: $(docker --version 2>&1 | awk '{print $3}' | tr -d ',')"
        if docker compose version &>/dev/null 2>&1; then
            log "Docker Compose: $(docker compose version --short 2>&1)"
        else
            warn "Docker Compose: not found"
        fi
    else
        warn "Docker: not found"
        all_ok=false
    fi

    # Vagrant (optional)
    if command_exists vagrant; then
        log "Vagrant: $(vagrant --version 2>&1 | awk '{print $2}')"
    else
        info "Vagrant: not installed (optional — Docker is preferred)"
    fi

    echo ""
    if [[ "$all_ok" == "true" ]]; then
        log "All core requirements met."
    else
        warn "Some requirements are missing. Run the Base System Provisioning step to install them."
    fi
}

# =============================================================================
#  Step 1: Base System Provisioning
# =============================================================================

provision_base() {
    step "Step 1: Base System Provisioning"

    info "This installs: curl, git, jq, Python 3.11+, pip, Docker, Docker Compose"
    info "Requires sudo. Targets Ubuntu 24.04 / Debian 12."
    echo ""

    if [[ ! -f "${SCRIPT_DIR}/shared/provision-base.sh" ]]; then
        err "shared/provision-base.sh not found!"
        return 1
    fi

    if prompt_yn "Run base system provisioning?"; then
        sudo bash "${SCRIPT_DIR}/shared/provision-base.sh"
        log "Base provisioning complete."
    else
        info "Skipped."
    fi
}

# =============================================================================
#  Step 2: Python Dependencies
# =============================================================================

install_python_deps() {
    step "Step 2: Python Dependencies"

    info "Assessment pipeline requires: reportlab, pypdf, jsonschema"
    info "Fine-tuning requires: torch, transformers, peft, bitsandbytes, etc."
    echo ""

    echo -e "  ${BOLD}1)${NC} Assessment only  ${DIM}(reportlab pypdf jsonschema)${NC}"
    echo -e "  ${BOLD}2)${NC} Assessment + Fine-tuning  ${DIM}(full requirements.txt)${NC}"
    echo -e "  ${BOLD}3)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-3]:${NC} "
    read -r pychoice

    case "$pychoice" in
        1)
            log "Installing assessment dependencies..."
            pip3 install --user reportlab pypdf jsonschema 2>/dev/null || \
            python3 -m pip install --user reportlab pypdf jsonschema
            log "Assessment dependencies installed."
            ;;
        2)
            log "Installing assessment dependencies..."
            pip3 install --user reportlab pypdf jsonschema 2>/dev/null || \
            python3 -m pip install --user reportlab pypdf jsonschema

            if [[ -f "${SCRIPT_DIR}/finetune/requirements.txt" ]]; then
                log "Installing fine-tuning dependencies..."
                pip3 install --user -r "${SCRIPT_DIR}/finetune/requirements.txt" 2>/dev/null || \
                python3 -m pip install --user -r "${SCRIPT_DIR}/finetune/requirements.txt"
                log "Fine-tuning dependencies installed."
            else
                warn "finetune/requirements.txt not found — skipping."
            fi
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 3: Environment Configuration
# =============================================================================

configure_env() {
    step "Step 3: Environment Configuration"

    local env_file="${SCRIPT_DIR}/.env"
    local template="${SCRIPT_DIR}/.env.template"

    if [[ -f "$env_file" ]]; then
        info ".env file already exists."
        if ! prompt_yn "Reconfigure it?" "n"; then
            info "Keeping existing .env"
            return 0
        fi
    fi

    if [[ ! -f "$template" ]]; then
        err ".env.template not found!"
        return 1
    fi

    cp "$template" "$env_file"
    info "Created .env from template."
    echo ""

    # --- LLM Provider ---
    echo -e "${BOLD}LLM Provider Configuration${NC}"
    echo ""
    local provider
    provider=$(prompt_choice "Which LLM provider will you use?" \
        "Anthropic (Claude)" \
        "OpenAI (GPT)" \
        "DeepSeek (free tier)" \
        "OpenRouter (multi-provider)" \
        "Gemini (Google)" \
        "Groq (fast inference)" \
        "Skip — configure later")

    case "$provider" in
        1)
            local key
            key=$(prompt_input "Enter your Anthropic API key" "")
            if [[ -n "$key" ]]; then
                sed -i "s|ANTHROPIC_API_KEY=sk-ant-REPLACE_ME|ANTHROPIC_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=anthropic|" "$env_file"

            local model
            model=$(prompt_choice "Which Claude model?" \
                "Claude Sonnet 4.6 (recommended)" \
                "Claude Opus 4.6 (most capable)" \
                "Claude Haiku 4.5 (fastest)")
            case "$model" in
                1) sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=claude-sonnet-4-6|" "$env_file" ;;
                2) sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=claude-opus-4-6|" "$env_file" ;;
                3) sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=claude-haiku-4-5|" "$env_file" ;;
            esac
            ;;
        2)
            local key
            key=$(prompt_input "Enter your OpenAI API key" "")
            if [[ -n "$key" ]]; then
                sed -i "s|OPENAI_API_KEY=sk-REPLACE_ME|OPENAI_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=openai|" "$env_file"
            sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=gpt-4.1|" "$env_file"
            ;;
        3)
            local key
            key=$(prompt_input "Enter your DeepSeek API key (leave empty for free tier)" "")
            if [[ -n "$key" ]]; then
                sed -i "s|DEEPSEEK_API_KEY=sk-REPLACE_ME|DEEPSEEK_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=deepseek|" "$env_file"
            sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=deepseek-chat|" "$env_file"
            ;;
        4)
            local key
            key=$(prompt_input "Enter your OpenRouter API key" "")
            if [[ -n "$key" ]]; then
                sed -i "s|OPENROUTER_API_KEY=sk-or-REPLACE_ME|OPENROUTER_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=openrouter|" "$env_file"
            ;;
        5)
            local key
            key=$(prompt_input "Enter your Gemini API key" "")
            if [[ -n "$key" ]]; then
                sed -i "s|GEMINI_API_KEY=REPLACE_ME|GEMINI_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=gemini|" "$env_file"
            sed -i "s|CLAW_LLM_MODEL=claude-sonnet-4-6|CLAW_LLM_MODEL=gemini-2.0-flash|" "$env_file"
            ;;
        6)
            local key
            key=$(prompt_input "Enter your Groq API key" "")
            if [[ -n "$key" ]]; then
                sed -i "s|GROQ_API_KEY=gsk_REPLACE_ME|GROQ_API_KEY=$key|" "$env_file"
            fi
            sed -i "s|CLAW_LLM_PROVIDER=anthropic|CLAW_LLM_PROVIDER=groq|" "$env_file"
            ;;
        *) info "Skipped — edit .env manually later." ;;
    esac

    # --- Chat Channels ---
    echo ""
    echo -e "${BOLD}Chat Channel Configuration${NC}"
    echo ""

    if prompt_yn "Configure Telegram bot?" "n"; then
        local tg_token
        tg_token=$(prompt_input "Telegram bot token" "")
        if [[ -n "$tg_token" ]]; then
            sed -i "s|TELEGRAM_BOT_TOKEN=123456789:REPLACE_ME|TELEGRAM_BOT_TOKEN=$tg_token|" "$env_file"
        fi
    fi

    if prompt_yn "Configure Discord bot?" "n"; then
        local dc_token
        dc_token=$(prompt_input "Discord bot token" "")
        if [[ -n "$dc_token" ]]; then
            sed -i "s|DISCORD_BOT_TOKEN=REPLACE_ME|DISCORD_BOT_TOKEN=$dc_token|" "$env_file"
        fi
    fi

    if prompt_yn "Configure Slack bot?" "n"; then
        local slack_bot slack_app
        slack_bot=$(prompt_input "Slack bot token (xoxb-...)" "")
        slack_app=$(prompt_input "Slack app token (xapp-...)" "")
        if [[ -n "$slack_bot" ]]; then
            sed -i "s|SLACK_BOT_TOKEN=xoxb-REPLACE_ME|SLACK_BOT_TOKEN=$slack_bot|" "$env_file"
        fi
        if [[ -n "$slack_app" ]]; then
            sed -i "s|SLACK_APP_TOKEN=xapp-REPLACE_ME|SLACK_APP_TOKEN=$slack_app|" "$env_file"
        fi
    fi

    # --- Agent Selection ---
    echo ""
    echo -e "${BOLD}Agent Platform Selection${NC}"
    echo ""

    local agent
    agent=$(prompt_choice "Which agent platform?" \
        "ZeroClaw  — Rust, 7.8 MB, encryption, multi-provider" \
        "NanoClaw  — TypeScript, container isolation, Claude-native" \
        "PicoClaw  — Go, 8 MB RAM, edge/IoT, budget" \
        "OpenClaw  — TypeScript, 50+ channels, full-featured" \
        "Skip — decide later")

    case "$agent" in
        1) sed -i "s|CLAW_AGENT=zeroclaw|CLAW_AGENT=zeroclaw|" "$env_file" ;;
        2) sed -i "s|CLAW_AGENT=zeroclaw|CLAW_AGENT=nanoclaw|" "$env_file" ;;
        3) sed -i "s|CLAW_AGENT=zeroclaw|CLAW_AGENT=picoclaw|" "$env_file" ;;
        4) sed -i "s|CLAW_AGENT=zeroclaw|CLAW_AGENT=openclaw|" "$env_file" ;;
        *) info "Skipped." ;;
    esac

    log ".env configuration complete."
    info "File saved to: $env_file"
    info "You can edit it manually at any time: \$EDITOR .env"

    # --- Vault Migration ---
    echo ""
    echo -e "${BOLD}Security Vault (Optional)${NC}"
    echo ""
    info "You can encrypt your API keys in a vault instead of storing them in plaintext .env."
    info "This prevents keys from appearing in docker inspect and on-disk config files."
    echo ""

    if prompt_yn "Set up encrypted secrets vault?" "n"; then
        # Check for cryptography package
        if ! python3 -c "import cryptography" 2>/dev/null; then
            log "Installing cryptography package..."
            pip3 install --user cryptography 2>/dev/null || \
            python3 -m pip install --user cryptography
        fi

        local vault_py="${SCRIPT_DIR}/shared/claw_vault.py"
        if [[ -f "$vault_py" ]]; then
            if [[ -f "${SCRIPT_DIR}/secrets.vault" ]]; then
                info "Vault already exists at secrets.vault"
                if prompt_yn "Import current .env keys into existing vault?" "y"; then
                    python3 "$vault_py" import-env "$env_file"
                    log "Keys imported into vault."
                fi
            else
                log "Creating new vault..."
                python3 "$vault_py" init
                if [[ -f "${SCRIPT_DIR}/secrets.vault" ]]; then
                    log "Importing .env keys into vault..."
                    python3 "$vault_py" import-env "$env_file"
                    log "Vault created and keys imported."
                    info "Your API keys are now encrypted in secrets.vault"
                    info "Set CLAW_VAULT_PASSWORD env var before starting agents."
                    info "The .env file is kept for non-secret config vars."
                fi
            fi
        else
            warn "shared/claw_vault.py not found — skipping vault setup."
        fi
    fi
}

# =============================================================================
#  Step 4: Assessment Pipeline
# =============================================================================

run_assessment() {
    step "Step 4: Assessment Pipeline"

    echo -e "  ${BOLD}1)${NC} Validate an existing assessment JSON"
    echo -e "  ${BOLD}2)${NC} Generate a blank PDF form (Private tier)"
    echo -e "  ${BOLD}3)${NC} Generate a blank PDF form (Enterprise tier)"
    echo -e "  ${BOLD}4)${NC} Convert a filled PDF back to JSON"
    echo -e "  ${BOLD}5)${NC} Generate pre-filled PDF from example (both tiers)"
    echo -e "  ${BOLD}6)${NC} Use example assessment (Lucia — Real Estate)"
    echo -e "  ${BOLD}7)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-7]:${NC} "
    read -r asschoice

    case "$asschoice" in
        1)
            local path
            path=$(prompt_input "Path to assessment JSON file" "client-assessment.json")
            python3 "${SCRIPT_DIR}/assessment/validate.py" "$path"
            ;;
        2)
            log "Generating blank Private assessment PDF..."
            python3 "${SCRIPT_DIR}/assessment/generate_pdf_form.py" --tier private
            log "PDF saved to assessment/claw-assessment-private-blank.pdf"
            ;;
        3)
            log "Generating blank Enterprise assessment PDF..."
            python3 "${SCRIPT_DIR}/assessment/generate_pdf_form.py" --tier enterprise
            log "PDF saved to assessment/claw-assessment-enterprise-blank.pdf"
            ;;
        4)
            local pdfpath outpath
            pdfpath=$(prompt_input "Path to filled PDF" "")
            outpath=$(prompt_input "Output JSON path" "client-assessment.json")
            python3 "${SCRIPT_DIR}/assessment/pdf_to_json.py" "$pdfpath" -o "$outpath" --validate
            log "JSON saved to $outpath"
            ;;
        5)
            log "Generating pre-filled PDFs from example..."
            python3 "${SCRIPT_DIR}/assessment/generate_pdf_form.py" --tier private \
                --prefill "${SCRIPT_DIR}/assessment/client-assessment.example.json"
            python3 "${SCRIPT_DIR}/assessment/generate_pdf_form.py" --tier enterprise \
                --prefill "${SCRIPT_DIR}/assessment/client-assessment.example.json"
            log "PDFs saved to assessment/"
            ;;
        6)
            if [[ -f "${SCRIPT_DIR}/assessment/client-assessment.example.json" ]]; then
                cp "${SCRIPT_DIR}/assessment/client-assessment.example.json" \
                   "${SCRIPT_DIR}/client-assessment.json"
                log "Example assessment copied to client-assessment.json"
                info "Edit it to match your client, then deploy."
            else
                err "Example assessment file not found!"
            fi
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 5: Agent Deployment
# =============================================================================

deploy_agent() {
    step "Step 5: Agent Deployment"

    if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
        warn ".env not found — run Step 3 first or copy .env.template to .env"
        return 1
    fi

    echo -e "  ${BOLD}1)${NC} Deploy from assessment (auto-selects platform + model)"
    echo -e "  ${BOLD}2)${NC} Deploy ZeroClaw via Docker"
    echo -e "  ${BOLD}3)${NC} Deploy NanoClaw via Docker"
    echo -e "  ${BOLD}4)${NC} Deploy PicoClaw via Docker"
    echo -e "  ${BOLD}5)${NC} Deploy OpenClaw via Docker"
    echo -e "  ${BOLD}6)${NC} Deploy via Vagrant (choose agent next)"
    echo -e "  ${BOLD}7)${NC} Install agent bare-metal (no Docker)"
    echo -e "  ${BOLD}8)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-8]:${NC} "
    read -r depchoice

    case "$depchoice" in
        1)
            local assessment
            assessment=$(prompt_input "Path to assessment JSON" "client-assessment.json")
            if [[ ! -f "$assessment" ]]; then
                err "File not found: $assessment"
                return 1
            fi
            log "Deploying from assessment..."
            bash "${SCRIPT_DIR}/claw.sh" deploy --assessment "$assessment"
            ;;
        2)
            log "Deploying ZeroClaw via Docker..."
            bash "${SCRIPT_DIR}/claw.sh" zeroclaw docker
            ;;
        3)
            log "Deploying NanoClaw via Docker..."
            bash "${SCRIPT_DIR}/claw.sh" nanoclaw docker
            ;;
        4)
            log "Deploying PicoClaw via Docker..."
            bash "${SCRIPT_DIR}/claw.sh" picoclaw docker
            ;;
        5)
            log "Deploying OpenClaw via Docker..."
            bash "${SCRIPT_DIR}/claw.sh" openclaw docker
            ;;
        6)
            local vagent
            vagent=$(prompt_choice "Which agent via Vagrant?" \
                "ZeroClaw" "NanoClaw" "PicoClaw" "OpenClaw")
            case "$vagent" in
                1) bash "${SCRIPT_DIR}/claw.sh" zeroclaw vagrant ;;
                2) bash "${SCRIPT_DIR}/claw.sh" nanoclaw vagrant ;;
                3) bash "${SCRIPT_DIR}/claw.sh" picoclaw vagrant ;;
                4) bash "${SCRIPT_DIR}/claw.sh" openclaw vagrant ;;
            esac
            ;;
        7)
            local bagent
            bagent=$(prompt_choice "Which agent to install bare-metal?" \
                "ZeroClaw (Rust binary)" \
                "NanoClaw (Node.js clone + npm)" \
                "PicoClaw (Go build from source)" \
                "OpenClaw (Node.js + pnpm)")
            case "$bagent" in
                1) bash "${SCRIPT_DIR}/zeroclaw/install-zeroclaw.sh" ;;
                2) bash "${SCRIPT_DIR}/nanoclaw/install-nanoclaw.sh" ;;
                3) bash "${SCRIPT_DIR}/picoclaw/install-picoclaw.sh" ;;
                4) bash "${SCRIPT_DIR}/openclaw/install-openclaw.sh" ;;
            esac
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 6: Fine-Tuning
# =============================================================================

setup_finetuning() {
    step "Step 6: Fine-Tuning"

    echo -e "  ${BOLD}1)${NC} List all 50 pre-built adapters"
    echo -e "  ${BOLD}2)${NC} Validate all datasets"
    echo -e "  ${BOLD}3)${NC} Download all datasets"
    echo -e "  ${BOLD}4)${NC} Train a LoRA adapter"
    echo -e "  ${BOLD}5)${NC} Train a QLoRA adapter (lower VRAM)"
    echo -e "  ${BOLD}6)${NC} Dry run (validate without training)"
    echo -e "  ${BOLD}7)${NC} Train from assessment"
    echo -e "  ${BOLD}8)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-8]:${NC} "
    read -r ftchoice

    case "$ftchoice" in
        1)
            bash "${SCRIPT_DIR}/claw.sh" datasets --list
            ;;
        2)
            bash "${SCRIPT_DIR}/claw.sh" datasets --validate
            ;;
        3)
            bash "${SCRIPT_DIR}/claw.sh" datasets --download-all
            ;;
        4)
            local adapter
            adapter=$(prompt_input "Adapter use case (e.g., 01-customer-support)" "")
            if [[ -n "$adapter" ]]; then
                bash "${SCRIPT_DIR}/claw.sh" finetune --adapter "$adapter"
            fi
            ;;
        5)
            local adapter
            adapter=$(prompt_input "Adapter use case (e.g., 02-real-estate)" "")
            if [[ -n "$adapter" ]]; then
                python3 "${SCRIPT_DIR}/finetune/train_qlora.py" --adapter "$adapter"
            fi
            ;;
        6)
            local adapter
            adapter=$(prompt_input "Adapter use case" "")
            if [[ -n "$adapter" ]]; then
                bash "${SCRIPT_DIR}/claw.sh" finetune --adapter "$adapter" --dry-run
            fi
            ;;
        7)
            local assessment
            assessment=$(prompt_input "Path to assessment JSON" "client-assessment.json")
            if [[ -f "$assessment" ]]; then
                bash "${SCRIPT_DIR}/claw.sh" finetune --assessment "$assessment"
            else
                err "File not found: $assessment"
            fi
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 7: Watchdog Monitoring Setup
# =============================================================================

setup_watchdog() {
    step "Step 7: Watchdog Monitoring Setup"

    local watchdog_py="${SCRIPT_DIR}/shared/claw_watchdog.py"
    local watchdog_cfg="${SCRIPT_DIR}/shared/watchdog.json"

    if [[ ! -f "$watchdog_py" ]]; then
        err "shared/claw_watchdog.py not found!"
        return 1
    fi

    echo -e "  ${BOLD}1)${NC} Generate watchdog config (watchdog.json)"
    echo -e "  ${BOLD}2)${NC} Edit watchdog config"
    echo -e "  ${BOLD}3)${NC} Run a single health check"
    echo -e "  ${BOLD}4)${NC} Start continuous monitoring (foreground)"
    echo -e "  ${BOLD}5)${NC} Setup Telegram alerts"
    echo -e "  ${BOLD}6)${NC} Install as systemd service"
    echo -e "  ${BOLD}7)${NC} View status dashboard"
    echo -e "  ${BOLD}8)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-8]:${NC} "
    read -r wdchoice

    case "$wdchoice" in
        1)
            python3 "$watchdog_py" --init-config
            log "Config generated at: $watchdog_cfg"
            info "Edit it with your agent names, container names, and bot tokens."
            ;;
        2)
            if [[ ! -f "$watchdog_cfg" ]]; then
                warn "No watchdog.json found — generating one first..."
                python3 "$watchdog_py" --init-config
            fi
            local editor="${EDITOR:-${VISUAL:-nano}}"
            info "Opening $watchdog_cfg with $editor..."
            "$editor" "$watchdog_cfg"
            ;;
        3)
            if [[ ! -f "$watchdog_cfg" ]]; then
                warn "No watchdog.json found — generating default config first..."
                python3 "$watchdog_py" --init-config
            fi
            log "Running single health check..."
            python3 "$watchdog_py" -c "$watchdog_cfg" --once
            ;;
        4)
            if [[ ! -f "$watchdog_cfg" ]]; then
                warn "No watchdog.json found — generating default config first..."
                python3 "$watchdog_py" --init-config
            fi
            log "Starting continuous monitoring (Ctrl+C to stop)..."
            python3 "$watchdog_py" -c "$watchdog_cfg"
            ;;
        5)
            echo ""
            info "To receive Telegram alerts, you need:"
            echo "  1. A Telegram bot token (create via @BotFather)"
            echo "  2. Your chat ID"
            echo ""

            local tg_token tg_chat
            tg_token=$(prompt_input "Telegram bot token" "")
            tg_chat=$(prompt_input "Telegram chat ID" "")

            if [[ -n "$tg_token" && -n "$tg_chat" ]]; then
                if [[ ! -f "$watchdog_cfg" ]]; then
                    python3 "$watchdog_py" --init-config
                fi

                # Update the watchdog config with the tokens
                python3 -c "
import json
with open('$watchdog_cfg', 'r') as f:
    cfg = json.load(f)
cfg['telegram_alerts'] = {
    'enabled': True,
    'bot_token': '$tg_token',
    'chat_id': '$tg_chat'
}
if 'connectivity' in cfg and 'telegram' in cfg['connectivity']:
    cfg['connectivity']['telegram']['enabled'] = True
    cfg['connectivity']['telegram']['bot_token'] = '$tg_token'
with open('$watchdog_cfg', 'w') as f:
    json.dump(cfg, f, indent=2)
"
                log "Telegram alerts configured in watchdog.json"

                # Test the connection
                info "Testing Telegram connectivity..."
                local test_url="https://api.telegram.org/bot${tg_token}/getMe"
                if curl -fsSL "$test_url" &>/dev/null; then
                    log "Telegram bot token is valid."
                else
                    warn "Could not verify bot token — check it manually."
                fi
            else
                info "Skipped — no tokens provided."
            fi
            ;;
        6)
            if [[ ! -f "$watchdog_cfg" ]]; then
                warn "No watchdog.json found — generating one first..."
                python3 "$watchdog_py" --init-config
            fi

            info "Installing watchdog as a systemd service..."
            local service_user
            service_user=$(prompt_input "Run as user" "$(whoami)")

            sudo tee /etc/systemd/system/claw-watchdog.service > /dev/null <<EOF
[Unit]
Description=Claw Agents Watchdog — Zero-Token Reliability Monitor
After=docker.service
Wants=docker.service

[Service]
Type=simple
User=${service_user}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=$(command -v python3) ${watchdog_py} -c ${watchdog_cfg}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

            sudo systemctl daemon-reload
            sudo systemctl enable claw-watchdog.service
            log "Systemd service installed and enabled."
            info "Start with: sudo systemctl start claw-watchdog"
            info "Logs:       journalctl -u claw-watchdog -f"
            ;;
        7)
            local port=9090
            if [[ -f "$watchdog_cfg" ]]; then
                port=$(python3 -c "import json; print(json.load(open('$watchdog_cfg')).get('dashboard_port', 9090))" 2>/dev/null || echo 9090)
            fi
            info "Fetching status from http://localhost:${port}/status ..."
            if curl -fsSL "http://localhost:${port}/status" 2>/dev/null | python3 -m json.tool 2>/dev/null; then
                true
            else
                warn "Watchdog is not running or dashboard port ${port} is not accessible."
                info "Start it first with option 4 or 6."
            fi
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 8: Health Check
# =============================================================================

run_healthcheck() {
    step "Step 8: Health Check"

    echo -e "  ${BOLD}1)${NC} Check all agents"
    echo -e "  ${BOLD}2)${NC} Check ZeroClaw"
    echo -e "  ${BOLD}3)${NC} Check NanoClaw"
    echo -e "  ${BOLD}4)${NC} Check PicoClaw"
    echo -e "  ${BOLD}5)${NC} Check OpenClaw"
    echo -e "  ${BOLD}6)${NC} Show Docker container status"
    echo -e "  ${BOLD}7)${NC} Show agent logs"
    echo -e "  ${BOLD}8)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-8]:${NC} "
    read -r hcchoice

    case "$hcchoice" in
        1) bash "${SCRIPT_DIR}/claw.sh" health all ;;
        2) bash "${SCRIPT_DIR}/claw.sh" health zeroclaw ;;
        3) bash "${SCRIPT_DIR}/claw.sh" health nanoclaw ;;
        4) bash "${SCRIPT_DIR}/claw.sh" health picoclaw ;;
        5) bash "${SCRIPT_DIR}/claw.sh" health openclaw ;;
        6)
            info "Running Docker container status..."
            docker compose -f "${SCRIPT_DIR}/docker-compose.yml" ps 2>/dev/null || \
                docker ps --filter "name=claw" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
                warn "No Docker containers found."
            ;;
        7)
            local lagent
            lagent=$(prompt_choice "Which agent's logs?" \
                "ZeroClaw" "NanoClaw" "PicoClaw" "OpenClaw")
            case "$lagent" in
                1) bash "${SCRIPT_DIR}/claw.sh" logs zeroclaw ;;
                2) bash "${SCRIPT_DIR}/claw.sh" logs nanoclaw ;;
                3) bash "${SCRIPT_DIR}/claw.sh" logs picoclaw ;;
                4) bash "${SCRIPT_DIR}/claw.sh" logs openclaw ;;
            esac
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 9: Multi-Instance Setup
# =============================================================================

setup_multi_instance() {
    step "Step 9: Multi-Instance Deployment"

    info "Run multiple named agent instances, each with its own ports and data."
    echo ""

    if ! prompt_yn "Set up a named instance?" "n"; then
        info "Skipped."
        return 0
    fi

    local inst_name inst_agent inst_port

    inst_name=$(prompt_input "Instance name (e.g., lucia, priya, kai)" "")
    if [[ -z "$inst_name" ]]; then
        info "No name provided — skipping."
        return 0
    fi

    inst_agent=$(prompt_choice "Agent platform for '$inst_name'?" \
        "ZeroClaw" "NanoClaw" "PicoClaw" "OpenClaw")

    local profile port_var
    case "$inst_agent" in
        1) profile="zeroclaw"; port_var="CLAW_ZEROCLAW_PORT" ;;
        2) profile="nanoclaw"; port_var="CLAW_NANOCLAW_PORT" ;;
        3) profile="picoclaw"; port_var="CLAW_PICOCLAW_PORT" ;;
        4) profile="openclaw"; port_var="CLAW_OPENCLAW_PORT" ;;
        *) return 0 ;;
    esac

    inst_port=$(prompt_input "Port for this instance" "")

    if prompt_yn "Create a separate .env file for '$inst_name'?" "y"; then
        local inst_env="${SCRIPT_DIR}/.env.${inst_name}"
        if [[ -f "${SCRIPT_DIR}/.env" ]]; then
            cp "${SCRIPT_DIR}/.env" "$inst_env"
            info "Created $inst_env — edit it with instance-specific keys."
        else
            cp "${SCRIPT_DIR}/.env.template" "$inst_env"
            info "Created $inst_env from template — fill in the keys."
        fi
    fi

    echo ""
    log "To start instance '$inst_name':"
    echo ""
    if [[ -n "$inst_port" ]]; then
        echo -e "  ${BOLD}${port_var}=${inst_port} docker compose -p ${inst_name} --profile ${profile} up -d${NC}"
    else
        echo -e "  ${BOLD}docker compose -p ${inst_name} --profile ${profile} up -d${NC}"
    fi
    echo ""
    echo -e "  Manage:  docker compose -p ${inst_name} ps"
    echo -e "  Logs:    docker compose -p ${inst_name} logs -f"
    echo -e "  Stop:    docker compose -p ${inst_name} --profile ${profile} down"
}

# =============================================================================
#  Step 10: Vault Management
# =============================================================================

manage_vault() {
    step "Step 10: Encrypted Secrets Vault"

    local vault_py="${SCRIPT_DIR}/shared/claw_vault.py"

    if [[ ! -f "$vault_py" ]]; then
        err "shared/claw_vault.py not found!"
        return 1
    fi

    # Check for cryptography package
    if ! python3 -c "import cryptography" 2>/dev/null; then
        warn "cryptography package not installed."
        if prompt_yn "Install it now?" "y"; then
            pip3 install --user cryptography 2>/dev/null || \
            python3 -m pip install --user cryptography
        else
            info "Skipped — vault requires: pip install cryptography"
            return 0
        fi
    fi

    echo -e "  ${BOLD}1)${NC} Create new vault"
    echo -e "  ${BOLD}2)${NC} Import .env into vault"
    echo -e "  ${BOLD}3)${NC} List vault secrets"
    echo -e "  ${BOLD}4)${NC} Get a secret value"
    echo -e "  ${BOLD}5)${NC} Set a secret"
    echo -e "  ${BOLD}6)${NC} Rotate vault password"
    echo -e "  ${BOLD}7)${NC} Export vault to .env"
    echo -e "  ${BOLD}8)${NC} Delete a secret"
    echo -e "  ${BOLD}9)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-9]:${NC} "
    read -r vchoice

    case "$vchoice" in
        1)
            python3 "$vault_py" init
            ;;
        2)
            local envpath
            envpath=$(prompt_input "Path to .env file" "${SCRIPT_DIR}/.env")
            if [[ -f "$envpath" ]]; then
                python3 "$vault_py" import-env "$envpath"
            else
                err "File not found: $envpath"
            fi
            ;;
        3)
            python3 "$vault_py" list
            ;;
        4)
            local key
            key=$(prompt_input "Secret key name" "")
            if [[ -n "$key" ]]; then
                python3 "$vault_py" get "$key"
            fi
            ;;
        5)
            local key val
            key=$(prompt_input "Secret key name" "")
            val=$(prompt_input "Secret value" "")
            if [[ -n "$key" && -n "$val" ]]; then
                python3 "$vault_py" set "$key" "$val"
            fi
            ;;
        6)
            python3 "$vault_py" rotate
            ;;
        7)
            local outpath
            outpath=$(prompt_input "Output .env path" "${SCRIPT_DIR}/.env.from-vault")
            python3 "$vault_py" export-env "$outpath"
            ;;
        8)
            local key
            key=$(prompt_input "Secret key to delete" "")
            if [[ -n "$key" ]]; then
                python3 "$vault_py" delete "$key"
            fi
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 11: Optimization Engine Setup
# =============================================================================

setup_optimizer() {
    step "Step 11: Multi-Model Optimization Engine"

    local optimizer_py="${SCRIPT_DIR}/shared/claw_optimizer.py"
    local optimizer_cfg="${SCRIPT_DIR}/shared/optimization.json"

    if [[ ! -f "$optimizer_py" ]]; then
        err "shared/claw_optimizer.py not found!"
        return 1
    fi

    echo -e "  ${BOLD}1)${NC} Generate optimization config (optimization.json)"
    echo -e "  ${BOLD}2)${NC} Edit optimization config"
    echo -e "  ${BOLD}3)${NC} Run optimization report"
    echo -e "  ${BOLD}4)${NC} Start optimization proxy service"
    echo -e "  ${BOLD}5)${NC} View cost report from logs"
    echo -e "  ${BOLD}6)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-6]:${NC} "
    read -r optchoice

    case "$optchoice" in
        1)
            python3 "$optimizer_py" --init-config
            log "Config generated at: $optimizer_cfg"
            info "Edit it to customize rules, budgets, and model tiers."
            ;;
        2)
            if [[ ! -f "$optimizer_cfg" ]]; then
                warn "No optimization.json found — generating one first..."
                python3 "$optimizer_py" --init-config
            fi
            local editor="${EDITOR:-${VISUAL:-nano}}"
            info "Opening $optimizer_cfg with $editor..."
            "$editor" "$optimizer_cfg"
            ;;
        3)
            python3 "$optimizer_py" --once
            ;;
        4)
            if [[ ! -f "$optimizer_cfg" ]]; then
                warn "No optimization.json found — generating default config first..."
                python3 "$optimizer_py" --init-config
            fi
            log "Starting optimization proxy (Ctrl+C to stop)..."
            python3 "$optimizer_py" -c "$optimizer_cfg"
            ;;
        5)
            python3 "$optimizer_py" --report
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Step 12: Security Rules
# =============================================================================

setup_security() {
    step "Step 12: Security Rules Engine"

    local security_py="${SCRIPT_DIR}/shared/claw_security.py"

    if [[ ! -f "$security_py" ]]; then
        err "shared/claw_security.py not found!"
        return 1
    fi

    echo -e "  ${BOLD}1)${NC} Generate default security rules (security_rules.json)"
    echo -e "  ${BOLD}2)${NC} View security posture report"
    echo -e "  ${BOLD}3)${NC} Test a URL against rules"
    echo -e "  ${BOLD}4)${NC} Test content against rules"
    echo -e "  ${BOLD}5)${NC} Test an IP address against rules"
    echo -e "  ${BOLD}6)${NC} Generate system prompt security appendix"
    echo -e "  ${BOLD}7)${NC} Validate current rules"
    echo -e "  ${BOLD}8)${NC} Edit security rules"
    echo -e "  ${BOLD}9)${NC} Skip"
    echo -ne "\n${CYAN}Choose [1-9]:${NC} "
    read -r secchoice

    case "$secchoice" in
        1)
            python3 "$security_py" --init-config
            ;;
        2)
            python3 "$security_py" --report
            ;;
        3)
            local url
            url=$(prompt_input "URL to test" "")
            if [[ -n "$url" ]]; then
                python3 "$security_py" --check-url "$url"
            fi
            ;;
        4)
            local content
            content=$(prompt_input "Content to test" "")
            if [[ -n "$content" ]]; then
                python3 "$security_py" --check-content "$content"
            fi
            ;;
        5)
            local ip
            ip=$(prompt_input "IP address to test" "")
            if [[ -n "$ip" ]]; then
                python3 "$security_py" --check-ip "$ip"
            fi
            ;;
        6)
            local compliance
            compliance=$(prompt_input "Active compliance frameworks (e.g., gdpr,hipaa)" "${CLAW_COMPLIANCE:-none}")
            python3 "$security_py" --generate-prompt --compliance "$compliance"
            ;;
        7)
            python3 "$security_py" --validate
            ;;
        8)
            local rules_file="${SCRIPT_DIR}/shared/security_rules.json"
            if [[ ! -f "$rules_file" ]]; then
                warn "No security_rules.json found — generating one first..."
                python3 "$security_py" --init-config
            fi
            local editor="${EDITOR:-${VISUAL:-nano}}"
            info "Opening $rules_file with $editor..."
            "$editor" "$rules_file"
            ;;
        *)
            info "Skipped."
            ;;
    esac
}

# =============================================================================
#  Main Menu
# =============================================================================

show_banner() {
    echo ""
    echo -e "${BLUE}${BOLD}"
    echo "  ███████╗██╗   ██╗███████╗██████╗ ██╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗"
    echo "  ██╔════╝██║   ██║██╔════╝██╔══██╗╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██║    ██║"
    echo "  █████╗  ██║   ██║█████╗  ██████╔╝ ╚████╔╝ ██║     ██║     ███████║██║ █╗ ██║"
    echo "  ██╔══╝  ╚██╗ ██╔╝██╔══╝  ██╔══██╗  ╚██╔╝  ██║     ██║     ██╔══██║██║███╗██║"
    echo "  ███████╗ ╚████╔╝ ███████╗██║  ██║   ██║   ╚██████╗███████╗██║  ██║╚███╔███╔╝"
    echo "  ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝"
    echo -e "${NC}"
    echo -e "  ${DIM}Claw Agents Provisioner — Interactive Setup${NC}"
    echo -e "  ${DIM}One-command deployment of personalized AI agents${NC}"
    echo ""
}

show_menu() {
    echo -e "${BOLD}Main Menu${NC}"
    echo ""
    echo -e "  ${BOLD}0)${NC}  System requirements check"
    echo -e "  ${BOLD}1)${NC}  Base system provisioning     ${DIM}(Docker, Python, Git)${NC}"
    echo -e "  ${BOLD}2)${NC}  Install Python dependencies   ${DIM}(reportlab, torch, etc.)${NC}"
    echo -e "  ${BOLD}3)${NC}  Configure environment         ${DIM}(API keys, channels, agent)${NC}"
    echo -e "  ${BOLD}4)${NC}  Assessment pipeline           ${DIM}(PDF forms, validation)${NC}"
    echo -e "  ${BOLD}5)${NC}  Deploy agent                  ${DIM}(Docker, Vagrant, bare-metal)${NC}"
    echo -e "  ${BOLD}6)${NC}  Fine-tuning                   ${DIM}(LoRA/QLoRA, datasets)${NC}"
    echo -e "  ${BOLD}7)${NC}  Watchdog monitoring            ${DIM}(alerts, auto-restart, dashboard)${NC}"
    echo -e "  ${BOLD}8)${NC}  Health check                  ${DIM}(verify running agents)${NC}"
    echo -e "  ${BOLD}9)${NC}  Multi-instance setup          ${DIM}(named instances, separate ports)${NC}"
    echo -e "  ${BOLD}10)${NC} Vault management              ${DIM}(encrypted secrets, rotate, import)${NC}"
    echo -e "  ${BOLD}11)${NC} Optimization engine            ${DIM}(cost routing, caching, budgets)${NC}"
    echo -e "  ${BOLD}12)${NC} Security rules                 ${DIM}(forbidden URLs, content, data, network)${NC}"
    echo ""
    echo -e "  ${BOLD}f)${NC}  Full setup (steps 1-7 sequentially)"
    echo -e "  ${BOLD}q)${NC}  Quit"
    echo ""
    echo -ne "${CYAN}Choose [0-11/f/q]:${NC} "
}

run_full_setup() {
    provision_base
    wait_key
    install_python_deps
    wait_key
    configure_env
    wait_key
    run_assessment
    wait_key
    deploy_agent
    wait_key
    setup_finetuning
    wait_key
    setup_watchdog
    echo ""
    log "Full setup complete!"
    info "Run ./install.sh again to access individual options."
}

main() {
    # Handle CLI flags
    case "${1:-}" in
        --full)
            show_banner
            run_full_setup
            exit 0
            ;;
        --help|-h)
            echo "Claw Agents Provisioner — Interactive Installer"
            echo ""
            echo "Usage:"
            echo "  ./install.sh              # Interactive menu"
            echo "  ./install.sh --full       # Run all steps sequentially"
            echo "  ./install.sh --help       # Show this help"
            exit 0
            ;;
    esac

    show_banner

    while true; do
        show_menu
        read -r choice

        case "$choice" in
            0) check_requirements; wait_key ;;
            1) provision_base; wait_key ;;
            2) install_python_deps; wait_key ;;
            3) configure_env; wait_key ;;
            4) run_assessment; wait_key ;;
            5) deploy_agent; wait_key ;;
            6) setup_finetuning; wait_key ;;
            7) setup_watchdog; wait_key ;;
            8) run_healthcheck; wait_key ;;
            9) setup_multi_instance; wait_key ;;
            10) manage_vault; wait_key ;;
            11) setup_optimizer; wait_key ;;
            12) setup_security; wait_key ;;
            f|F) run_full_setup; wait_key ;;
            q|Q)
                echo ""
                log "Goodbye!"
                exit 0
                ;;
            *)
                warn "Invalid choice: $choice"
                ;;
        esac
        echo ""
    done
}

main "$@"
