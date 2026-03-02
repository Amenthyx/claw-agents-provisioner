#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# claw.sh — Unified Launcher CLI for Claw Agents Provisioner
# =============================================================================
# One-command deployment of any Claw AI agent via Docker, Vagrant, or bare-metal.
#
# Usage:
#   ./claw.sh <agent> [docker|vagrant]     Start an agent
#   ./claw.sh <agent> destroy              Teardown agent (containers/VMs/volumes)
#   ./claw.sh deploy --assessment <file>   Assessment-driven deployment pipeline
#   ./claw.sh finetune --assessment <file> Trigger LoRA/QLoRA fine-tuning
#   ./claw.sh datasets --list              List all 50 use-case datasets
#   ./claw.sh datasets --validate          Validate datasets (rows, schema, license)
#   ./claw.sh datasets --download-all      Download all 50 datasets
#   ./claw.sh vault <command>               Encrypted secrets vault
#   ./claw.sh optimizer <command>           Multi-model optimization
#   ./claw.sh health <agent>               Run health check
#   ./claw.sh completions <bash|zsh|install> Shell completion scripts
#   ./claw.sh help                         Show this help
# =============================================================================

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALID_AGENTS=("zeroclaw" "nanoclaw" "picoclaw" "openclaw" "parlant")
VALID_METHODS=("docker" "vagrant")

# -------------------------------------------------------------------
# Colors
# -------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log()     { echo -e "${GREEN}[claw]${NC} $*"; }
warn()    { echo -e "${YELLOW}[claw]${NC} $*"; }
err()     { echo -e "${RED}[claw]${NC} $*" >&2; }
info()    { echo -e "${BLUE}[claw]${NC} $*"; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}\n"; }

is_valid_agent() {
    local agent="$1"
    for a in "${VALID_AGENTS[@]}"; do
        [[ "$a" == "$agent" ]] && return 0
    done
    return 1
}

check_docker() {
    # 1. Already running?
    if docker info &>/dev/null 2>&1; then
        return 0
    fi

    # 2. Installed but not running?
    if command -v docker &>/dev/null; then
        warn "Docker installed but not running — starting..."
        _start_docker_daemon
        return 0
    fi

    # 3. Not installed — auto-install
    warn "Docker not found — installing automatically..."
    _install_docker
    _start_docker_daemon
}

_install_docker() {
    local os_type
    os_type="$(uname -s)"
    case "$os_type" in
        Darwin)
            if command -v brew &>/dev/null; then
                log "Installing Docker Desktop via Homebrew..."
                brew install --cask docker
            else
                err "Homebrew not found. Install Docker Desktop from https://docs.docker.com/get-docker/"
                exit 1
            fi
            ;;
        Linux)
            log "Installing Docker via official convenience script..."
            curl -fsSL https://get.docker.com | sh
            ;;
        MINGW*|MSYS*|CYGWIN*)
            if command -v winget &>/dev/null; then
                log "Installing Docker Desktop via winget..."
                winget install -e --id Docker.DockerDesktop \
                    --accept-package-agreements --accept-source-agreements
            else
                err "winget not found. Install Docker Desktop from https://docs.docker.com/get-docker/"
                exit 1
            fi
            ;;
        *)
            err "Unsupported OS: $os_type — install Docker manually: https://docs.docker.com/get-docker/"
            exit 1
            ;;
    esac

    # Verify install
    if ! command -v docker &>/dev/null; then
        err "Docker installation failed — please install manually: https://docs.docker.com/get-docker/"
        exit 1
    fi
    log "Docker installed successfully"

    # Also check Docker Compose
    if ! docker compose version &>/dev/null 2>&1; then
        warn "Docker Compose plugin not found — it should be included with Docker Desktop."
        warn "If using Linux server, install it: https://docs.docker.com/compose/install/"
    fi
}

_start_docker_daemon() {
    local os_type max_wait=60 interval=3
    os_type="$(uname -s)"

    case "$os_type" in
        Darwin)
            open -a Docker 2>/dev/null || true
            ;;
        Linux)
            if command -v systemctl &>/dev/null; then
                sudo systemctl start docker 2>/dev/null || true
            fi
            max_wait=30; interval=2
            ;;
        MINGW*|MSYS*|CYGWIN*)
            powershell.exe -Command \
                "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" 2>/dev/null || true
            ;;
    esac

    log "Waiting for Docker daemon to start..."
    local elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        sleep "$interval"
        elapsed=$((elapsed + interval))
        if docker info &>/dev/null 2>&1; then
            log "Docker is ready (started in ${elapsed}s)"
            return 0
        fi
    done
    warn "Docker started — may need a few more seconds to initialize"
}

check_vagrant() {
    if ! command -v vagrant &>/dev/null; then
        err "Vagrant is not installed. Install Vagrant first: https://www.vagrantup.com/downloads"
        exit 1
    fi
}

# -------------------------------------------------------------------
# print_banner
# -------------------------------------------------------------------
print_banner() {
    echo -e "${CYAN}"
    echo "   _____ _                      _                    _       "
    echo "  / ____| |                 /\ | |                  | |      "
    echo " | |    | | __ ___      __ /  \| | __ _  ___ _ __ | |_ ___ "
    echo " | |    | |/ _\` \\ \\ /\\ / // /\\ \\ |/ _\` |/ _ \\ '_ \\| __/ __|"
    echo " | |____| | (_| |\\ V  V // ____ \\ | (_| |  __/ | | | |_\\__ \\"
    echo "  \\_____|_|\\__,_| \\_/\\_//_/    \\_\\_\\__, |\\___|_| |_|\\__|___/"
    echo "                                    __/ |                    "
    echo "                                   |___/   Provisioner v1.0 "
    echo -e "${NC}"
    echo -e "  ${DIM}Created by Mauro Tommasi — linkedin.com/in/maurotommasi${NC}"
    echo ""
}

# -------------------------------------------------------------------
# print_help
# -------------------------------------------------------------------
print_help() {
    print_banner
    echo -e "${BOLD}USAGE:${NC}"
    echo "  ./claw.sh <command> [options]"
    echo ""
    echo -e "${BOLD}AGENT COMMANDS:${NC}"
    echo -e "  ${GREEN}<agent> docker${NC}              Start agent via Docker Compose"
    echo -e "  ${GREEN}<agent> vagrant${NC}             Start agent via Vagrant VM"
    echo -e "  ${GREEN}<agent> destroy${NC}             Teardown agent (remove containers/VMs/volumes)"
    echo ""
    echo -e "${BOLD}DEPLOYMENT:${NC}"
    echo -e "  ${GREEN}deploy --assessment <file>${NC}  Auto-deploy from client assessment JSON"
    echo -e "  ${GREEN}validate --assessment <file>${NC} Validate assessment JSON schema"
    echo ""
    echo -e "${BOLD}FINE-TUNING:${NC}"
    echo -e "  ${GREEN}finetune --assessment <file>${NC} Generate dataset + train LoRA/QLoRA adapter"
    echo -e "  ${GREEN}finetune --adapter <use-case> [--dry-run]${NC}  Train from pre-built adapter config"
    echo ""
    echo -e "${BOLD}DATASETS:${NC}"
    echo -e "  ${GREEN}datasets --list${NC}              List all 50 use-case datasets with status"
    echo -e "  ${GREEN}datasets --validate${NC}          Validate all datasets (rows, schema, license)"
    echo -e "  ${GREEN}datasets --download-all${NC}      Download all 50 datasets"
    echo ""
    echo -e "${BOLD}SECURITY:${NC}"
    echo -e "  ${GREEN}vault init${NC}                   Create a new encrypted secrets vault"
    echo -e "  ${GREEN}vault import-env <file>${NC}      Import .env keys into the vault"
    echo -e "  ${GREEN}vault list${NC}                   List stored secret names"
    echo -e "  ${GREEN}vault get <key>${NC}              Retrieve a secret value"
    echo -e "  ${GREEN}vault set <key> <value>${NC}      Store a secret"
    echo -e "  ${GREEN}vault rotate${NC}                 Change vault password"
    echo -e "  ${GREEN}vault export-env <file>${NC}      Export secrets back to .env format"
    echo -e "  ${GREEN}security report${NC}              Security posture report"
    echo -e "  ${GREEN}security check-url <url>${NC}     Test a URL against rules"
    echo -e "  ${GREEN}security check-content <txt>${NC} Test content against rules"
    echo -e "  ${GREEN}security generate-prompt${NC}     Generate system prompt security appendix"
    echo -e "  ${GREEN}security init${NC}                Generate security_rules.json"
    echo ""
    echo -e "${BOLD}OPTIMIZATION:${NC}"
    echo -e "  ${GREEN}optimizer init${NC}               Generate optimization.json config"
    echo -e "  ${GREEN}optimizer report${NC}             Show cost optimization report"
    echo -e "  ${GREEN}optimizer start${NC}              Start optimization proxy service"
    echo ""
    echo -e "${BOLD}HARDWARE:${NC}"
    echo -e "  ${GREEN}hardware detect${NC}              Detect GPU, CPU, RAM — save hardware_profile.json"
    echo -e "  ${GREEN}hardware report${NC}              Print formatted hardware report"
    echo -e "  ${GREEN}hardware recommend${NC}           Recommend best local LLM runtime + models"
    echo -e "  ${GREEN}hardware json${NC}                Output hardware profile as JSON"
    echo -e "  ${GREEN}hardware summary${NC}             One-line summary (for scripts)"
    echo ""
    echo -e "${BOLD}LOCAL LLM:${NC}"
    echo -e "  ${GREEN}ollama install${NC}               Install Ollama runtime"
    echo -e "  ${GREEN}ollama pull <model>${NC}           Pull a model (e.g., llama3.2, qwen2.5)"
    echo -e "  ${GREEN}ollama list${NC}                  List installed local models"
    echo -e "  ${GREEN}ollama status${NC}                Check Ollama service status"
    echo -e "  ${GREEN}llamacpp install${NC}             Install llama.cpp server"
    echo -e "  ${GREEN}llamacpp start <model.gguf>${NC}  Start llama-server with a GGUF model"
    echo -e "  ${GREEN}llamacpp list${NC}                List GGUF models in models directory"
    echo -e "  ${GREEN}llamacpp status${NC}              Check llama.cpp server status"
    echo ""
    echo -e "${BOLD}STRATEGY ENGINE:${NC}"
    echo -e "  ${GREEN}strategy scan${NC}                Discover available models (local + cloud)"
    echo -e "  ${GREEN}strategy generate${NC}            Generate optimal routing strategy"
    echo -e "  ${GREEN}strategy report${NC}              Print current strategy report"
    echo -e "  ${GREEN}strategy init${NC}                Generate strategy config template"
    echo -e "  ${GREEN}strategy benchmark${NC}           Quick latency benchmark"
    echo ""
    echo -e "${BOLD}DASHBOARD & WIZARD:${NC}"
    echo -e "  ${GREEN}dashboard start [port]${NC}       Start enterprise web dashboard (default: 9099)"
    echo -e "  ${GREEN}dashboard stop${NC}               Stop the dashboard"
    echo -e "  ${GREEN}wizard start [port]${NC}          Start assessment web wizard (default: 9098)"
    echo -e "  ${GREEN}wizard stop${NC}                  Stop the wizard"
    echo ""
    echo -e "${BOLD}ROUTER & ORCHESTRATION:${NC}"
    echo -e "  ${GREEN}router start [port]${NC}          Start model router proxy (default: 9095)"
    echo -e "  ${GREEN}router stop${NC}                  Stop the router"
    echo -e "  ${GREEN}router status${NC}                Show router status"
    echo -e "  ${GREEN}orchestrator start${NC}           Start multi-agent orchestrator"
    echo -e "  ${GREEN}orchestrator stop${NC}            Stop the orchestrator"
    echo -e "  ${GREEN}orchestrator status${NC}          Show orchestrator status"
    echo ""
    echo -e "${BOLD}MEMORY & RAG:${NC}"
    echo -e "  ${GREEN}memory start [port]${NC}          Start conversation memory service (default: 9096)"
    echo -e "  ${GREEN}memory stop${NC}                  Stop the memory service"
    echo -e "  ${GREEN}memory stats${NC}                 Show memory usage stats"
    echo -e "  ${GREEN}memory search <query>${NC}        Search conversation history"
    echo -e "  ${GREEN}rag start [port]${NC}             Start RAG pipeline service (default: 9097)"
    echo -e "  ${GREEN}rag stop${NC}                     Stop the RAG service"
    echo -e "  ${GREEN}rag ingest <path>${NC}            Ingest documents into RAG index"
    echo -e "  ${GREEN}rag search <query>${NC}           Search the RAG index"
    echo ""
    echo -e "${BOLD}BILLING & SKILLS:${NC}"
    echo -e "  ${GREEN}billing report [period]${NC}      Cost report (daily|weekly|monthly)"
    echo -e "  ${GREEN}billing status${NC}               Current spend overview"
    echo -e "  ${GREEN}billing forecast${NC}             Projected spend forecast"
    echo -e "  ${GREEN}skills list${NC}                  List all available skills"
    echo -e "  ${GREEN}skills search <query>${NC}        Search skills catalog"
    echo -e "  ${GREEN}skills install <id> <agent>${NC}  Install skill for an agent"
    echo -e "  ${GREEN}adapter match <use-case>${NC}     Auto-select best LoRA adapter"
    echo -e "  ${GREEN}adapter list${NC}                 List all 50 adapters"
    echo ""
    echo -e "${BOLD}OPERATIONS:${NC}"
    echo -e "  ${GREEN}health [agent|all|services]${NC}  Run health check (services = aggregated)"
    echo -e "  ${GREEN}logs <agent>${NC}                 Tail agent logs (Docker)"
    echo -e "  ${GREEN}status${NC}                       Show status of all agents"
    echo -e "  ${GREEN}help${NC}                         Show this help message"
    echo ""
    echo -e "${BOLD}SHELL COMPLETIONS:${NC}"
    echo -e "  ${GREEN}completions bash${NC}             Print bash completion script to stdout"
    echo -e "  ${GREEN}completions zsh${NC}              Print zsh completion script to stdout"
    echo -e "  ${GREEN}completions install${NC}          Install completions to system directories"
    echo ""
    echo -e "${BOLD}AGENTS:${NC}"
    echo -e "  ${BLUE}zeroclaw${NC}   Rust agent     | 512 MB limit | Port 3100"
    echo -e "  ${BLUE}nanoclaw${NC}   TypeScript+DooD | 1 GB limit   | Port 3200"
    echo -e "  ${BLUE}picoclaw${NC}   Go agent       | 128 MB limit | Port 3300"
    echo -e "  ${BLUE}openclaw${NC}   Node.js 22     | 4 GB limit   | Port 3400"
    echo -e "  ${BLUE}parlant${NC}    Python+MCP     | 2 GB limit   | Port 8800"
    echo ""
    echo -e "${BOLD}EXAMPLES:${NC}"
    echo "  ./claw.sh zeroclaw docker                          # Start ZeroClaw in Docker"
    echo "  ./claw.sh parlant docker                           # Start Parlant in Docker"
    echo "  ./claw.sh picoclaw vagrant                         # Start PicoClaw in Vagrant VM"
    echo "  ./claw.sh zeroclaw destroy                         # Remove ZeroClaw container"
    echo "  ./claw.sh deploy --assessment client-assessment.json"
    echo "  ./claw.sh finetune --adapter 01-customer-support"
    echo "  ./claw.sh datasets --list"
    echo "  ./claw.sh ollama install                           # Install Ollama + pull models"
    echo "  ./claw.sh health all                               # Check all agents"
    echo ""
    echo -e "${BOLD}MULTI-AGENT:${NC}"
    echo "  docker compose --profile zeroclaw --profile picoclaw up -d"
    echo ""
}

# -------------------------------------------------------------------
# cmd_start_docker — Start agent via Docker Compose
# -------------------------------------------------------------------
cmd_start_docker() {
    local agent="$1"
    check_docker

    header "Starting ${agent} via Docker Compose..."

    # Determine if vault mode or legacy .env mode
    local compose_files=("-f" "docker-compose.yml")

    if [ -f "${SCRIPT_DIR}/secrets.vault" ]; then
        log "Vault detected — using encrypted secrets mode."
        if [ ! -f "${SCRIPT_DIR}/docker-compose.secrets.yml" ]; then
            err "docker-compose.secrets.yml not found. Cannot use vault mode."
            exit 1
        fi
        compose_files+=("-f" "docker-compose.secrets.yml")

        # Ensure CLAW_VAULT_PASSWORD is set
        if [ -z "${CLAW_VAULT_PASSWORD:-}" ]; then
            warn "CLAW_VAULT_PASSWORD is not set. Containers won't be able to decrypt secrets."
            warn "Set it with: export CLAW_VAULT_PASSWORD='your-password'"
        fi
    else
        # Legacy .env mode
        if [ ! -f "${SCRIPT_DIR}/.env" ]; then
            warn "No .env file found. Copying from .env.template..."
            if [ -f "${SCRIPT_DIR}/.env.template" ]; then
                cp "${SCRIPT_DIR}/.env.template" "${SCRIPT_DIR}/.env"
                warn "Please edit .env with your API keys before running agents."
            else
                err "No .env.template found either. Create a .env file with your configuration."
                exit 1
            fi
        fi
    fi

    cd "${SCRIPT_DIR}"
    docker compose "${compose_files[@]}" --profile "${agent}" up -d --build
    log "Agent ${agent} started successfully!"
    echo ""
    info "  Container: claw-${agent}"
    info "  Logs:      docker compose --profile ${agent} logs -f"
    info "  Health:    ./claw.sh health ${agent}"
    info "  Stop:      ./claw.sh ${agent} destroy"
}

# -------------------------------------------------------------------
# cmd_start_vagrant — Start agent via Vagrant
# -------------------------------------------------------------------
cmd_start_vagrant() {
    local agent="$1"
    check_vagrant

    header "Starting ${agent} via Vagrant..."

    local vagrantdir="${SCRIPT_DIR}/${agent}"
    if [ ! -f "${vagrantdir}/Vagrantfile" ]; then
        err "Vagrantfile not found at ${vagrantdir}/Vagrantfile"
        exit 1
    fi

    cd "${vagrantdir}"
    vagrant up
    log "Agent ${agent} VM started successfully!"
    echo ""
    info "  SSH:       cd ${agent} && vagrant ssh"
    info "  Status:    cd ${agent} && vagrant status"
    info "  Destroy:   ./claw.sh ${agent} destroy"
}

# -------------------------------------------------------------------
# cmd_destroy — Teardown agent
# -------------------------------------------------------------------
cmd_destroy() {
    local agent="$1"

    header "Destroying ${agent}..."

    # Destroy Docker container
    if command -v docker &>/dev/null; then
        log "Stopping Docker container..."
        cd "${SCRIPT_DIR}"
        docker compose --profile "${agent}" down -v 2>/dev/null || true
        docker rm -f "claw-${agent}" 2>/dev/null || true
    fi

    # Destroy Vagrant VM
    if command -v vagrant &>/dev/null && [ -f "${SCRIPT_DIR}/${agent}/Vagrantfile" ]; then
        log "Destroying Vagrant VM..."
        cd "${SCRIPT_DIR}/${agent}"
        vagrant destroy -f 2>/dev/null || true
    fi

    log "Agent ${agent} destroyed."
}

# -------------------------------------------------------------------
# cmd_deploy — Assessment-driven deployment
# -------------------------------------------------------------------
cmd_deploy() {
    local assessment_file=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --assessment)
                assessment_file="${2:-}"
                shift 2
                ;;
            *)
                err "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    if [ -z "${assessment_file}" ]; then
        err "Usage: ./claw.sh deploy --assessment <file>"
        exit 1
    fi

    if [ ! -f "${assessment_file}" ]; then
        err "Assessment file not found: ${assessment_file}"
        exit 1
    fi

    header "Assessment-Driven Deployment Pipeline"

    # Verify required assessment scripts exist
    local required_scripts=("validate.py" "resolve.py" "generate_env.py" "generate_config.py")
    for script in "${required_scripts[@]}"; do
        if [ ! -f "${SCRIPT_DIR}/assessment/${script}" ]; then
            err "Required assessment script not found: assessment/${script}"
            err "The assessment pipeline is incomplete. Please check your installation."
            exit 1
        fi
    done

    # Step 1: Validate assessment
    log "Step 1/5: Validating assessment..."
    python3 "${SCRIPT_DIR}/assessment/validate.py" "${assessment_file}"

    # Step 2: Resolve platform, model, skills
    log "Step 2/5: Resolving platform and configuration..."
    RESOLVE_JSON=$(python3 "${SCRIPT_DIR}/assessment/resolve.py" "${assessment_file}" --json)
    RESOLVED_AGENT=$(echo "${RESOLVE_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('platform','openclaw'))")

    # Step 3: Generate .env
    log "Step 3/5: Generating .env configuration..."
    python3 "${SCRIPT_DIR}/assessment/generate_env.py" "${assessment_file}"

    # Step 4: Generate agent-specific config
    log "Step 4/5: Generating agent config..."
    python3 "${SCRIPT_DIR}/assessment/generate_config.py" "${assessment_file}"

    # Step 5: Deploy
    local target_agent="${RESOLVED_AGENT:-${CLAW_AGENT:-openclaw}}"
    log "Step 5/5: Deploying ${target_agent} via Docker..."
    cmd_start_docker "${target_agent}"

    echo ""
    log "Assessment-driven deployment complete!"
    info "Agent: ${target_agent}"
    info "Assessment: ${assessment_file}"
}

# -------------------------------------------------------------------
# cmd_finetune — Fine-tuning pipeline
# -------------------------------------------------------------------
cmd_finetune() {
    local assessment_file=""
    local adapter=""
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --assessment)
                assessment_file="${2:-}"
                shift 2
                ;;
            --adapter)
                adapter="${2:-}"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                err "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    header "LoRA/QLoRA Fine-Tuning Pipeline"

    if [ -n "${adapter}" ]; then
        # Train from pre-built adapter config
        local adapter_dir="${SCRIPT_DIR}/finetune/adapters/${adapter}"
        if [ ! -d "${adapter_dir}" ]; then
            err "Adapter config not found: ${adapter_dir}"
            exit 1
        fi

        log "Adapter: ${adapter}"
        log "Config:  ${adapter_dir}/adapter_config.json"

        if [ "${dry_run}" = true ]; then
            log "Dry run — validating adapter config..."
            if [ -f "${adapter_dir}/adapter_config.json" ] && \
               [ -f "${adapter_dir}/system_prompt.txt" ] && \
               [ -f "${adapter_dir}/training_config.json" ]; then
                log "All adapter config files present. Validation passed."
            else
                err "Missing adapter config files in ${adapter_dir}"
                exit 1
            fi
            return 0
        fi

        # Run fine-tuning container
        check_docker
        log "Starting fine-tuning container..."
        cd "${SCRIPT_DIR}"
        docker compose --profile finetune run --rm finetune \
            python finetune/train_lora.py --adapter "${adapter}"

    elif [ -n "${assessment_file}" ]; then
        # Generate dataset from assessment and train
        if [ ! -f "${assessment_file}" ]; then
            err "Assessment file not found: ${assessment_file}"
            exit 1
        fi

        log "Generating training dataset from assessment..."
        if [ -f "${SCRIPT_DIR}/finetune/dataset_generator.py" ]; then
            python3 "${SCRIPT_DIR}/finetune/dataset_generator.py" "${assessment_file}"
        else
            warn "Dataset generator not found"
        fi

        log "Starting fine-tuning..."
        if [ -f "${SCRIPT_DIR}/finetune/train_lora.py" ]; then
            check_docker
            cd "${SCRIPT_DIR}"
            docker compose --profile finetune run --rm finetune \
                python finetune/train_lora.py --assessment "${assessment_file}"
        else
            warn "Training script not found"
        fi
    else
        err "Usage: ./claw.sh finetune --assessment <file>"
        err "       ./claw.sh finetune --adapter <use-case> [--dry-run]"
        exit 1
    fi
}

# -------------------------------------------------------------------
# cmd_datasets — Dataset management
# -------------------------------------------------------------------
cmd_datasets() {
    local action=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list)       action="list"; shift ;;
            --validate)   action="validate"; shift ;;
            --download-all) action="download"; shift ;;
            *)
                err "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    local datasets_dir="${SCRIPT_DIR}/finetune/datasets"

    case "${action}" in
        list)
            header "Dataset Catalog (50 Use Cases)"
            echo -e "${BOLD}#   Use Case                         Status     Rows${NC}"
            echo "--- -------------------------------- ---------- ------"

            local count=0
            for dir in "${datasets_dir}"/*/; do
                [ -d "${dir}" ] || continue
                local name
                name=$(basename "${dir}")
                local status="${RED}MISSING${NC}"
                local rows="-"

                if [ -f "${dir}/data.jsonl" ]; then
                    status="${GREEN}PRESENT${NC}"
                    rows=$(wc -l < "${dir}/data.jsonl" 2>/dev/null || echo "?")
                elif [ -f "${dir}/data.csv" ]; then
                    status="${GREEN}PRESENT${NC}"
                    rows=$(wc -l < "${dir}/data.csv" 2>/dev/null || echo "?")
                elif [ -f "${dir}/data.parquet" ]; then
                    status="${GREEN}PRESENT${NC}"
                    rows="(parquet)"
                fi

                if [ -f "${dir}/metadata.json" ]; then
                    count=$((count + 1))
                fi

                printf "%-3s %-32s %b  %s\n" "${count}" "${name}" "${status}" "${rows}"
            done

            echo ""
            info "Total: ${count} datasets with metadata"
            ;;

        validate)
            header "Validating Datasets"
            if [ -f "${SCRIPT_DIR}/finetune/validate_datasets.py" ]; then
                python3 "${SCRIPT_DIR}/finetune/validate_datasets.py"
            else
                warn "validate_datasets.py not found — performing basic validation..."
                local pass=0
                local fail=0
                for dir in "${datasets_dir}"/*/; do
                    [ -d "${dir}" ] || continue
                    local name
                    name=$(basename "${dir}")
                    if [ -f "${dir}/metadata.json" ] && \
                       { [ -f "${dir}/data.jsonl" ] || [ -f "${dir}/data.csv" ] || [ -f "${dir}/data.parquet" ]; }; then
                        echo -e "  ${GREEN}PASS${NC} ${name}"
                        pass=$((pass + 1))
                    else
                        echo -e "  ${RED}FAIL${NC} ${name} — missing data or metadata"
                        fail=$((fail + 1))
                    fi
                done
                echo ""
                info "Results: ${pass} passed, ${fail} failed"
            fi
            ;;

        download)
            header "Downloading Datasets"
            if [ -f "${SCRIPT_DIR}/finetune/download_datasets.py" ]; then
                python3 "${SCRIPT_DIR}/finetune/download_datasets.py"
            else
                err "download_datasets.py not found"
                exit 1
            fi
            ;;

        *)
            err "Usage: ./claw.sh datasets --list|--validate|--download-all"
            exit 1
            ;;
    esac
}

# -------------------------------------------------------------------
# cmd_health — Health check
# -------------------------------------------------------------------
cmd_health() {
    local target="${1:-all}"

    # "services" subcommand queries the health aggregator on port 9094
    if [[ "$target" == "services" ]]; then
        local health_port="${CLAW_HEALTH_PORT:-9094}"
        header "Platform Services Health (port ${health_port})"

        local response
        if response=$(curl -sf --max-time 5 "http://localhost:${health_port}/health" 2>/dev/null); then
            local overall
            overall=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")

            case "$overall" in
                healthy)   echo -e "  Overall: ${GREEN}HEALTHY${NC}" ;;
                degraded)  echo -e "  Overall: ${YELLOW}DEGRADED${NC}" ;;
                unhealthy) echo -e "  Overall: ${RED}UNHEALTHY${NC}" ;;
                *)         echo -e "  Overall: ${YELLOW}${overall}${NC}" ;;
            esac
            echo ""

            # Parse and display each service
            echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
services = data.get('services', {})
for name in sorted(services):
    svc = services[name]
    status = svc.get('status', 'unknown')
    port = svc.get('port', '?')
    rt = svc.get('response_time_ms')
    rt_str = f'{rt}ms' if rt is not None else 'n/a'
    symbol = '  PASS' if status == 'healthy' else '  FAIL'
    print(f'  {name:<14} :{port:<6} {status:<10}  {rt_str}')
" 2>/dev/null || echo -e "  ${RED}Failed to parse response${NC}"

            echo ""
            echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
h = data.get('counts', {}).get('healthy', 0)
t = data.get('total_services', 0)
print(f'  Summary: {h}/{t} services healthy')
" 2>/dev/null
        else
            echo -e "  ${RED}Health aggregator not reachable on port ${health_port}${NC}"
            echo -e "  Start it with: python3 shared/claw_health.py --start"
            echo -e "  Or via Docker: docker compose --profile health up -d"
        fi
        echo ""
        return
    fi

    # Default: delegate to the existing agent healthcheck script
    "${SCRIPT_DIR}/shared/healthcheck.sh" "${target}"
}

# -------------------------------------------------------------------
# cmd_logs — Tail agent logs
# -------------------------------------------------------------------
cmd_logs() {
    local agent="$1"
    check_docker
    cd "${SCRIPT_DIR}"
    docker compose --profile "${agent}" logs -f
}

# -------------------------------------------------------------------
# cmd_status — Show status of all agents
# -------------------------------------------------------------------
cmd_status() {
    header "Agent Status"

    for agent in "${VALID_AGENTS[@]}"; do
        local docker_status="${RED}stopped${NC}"
        local vagrant_status="${RED}stopped${NC}"

        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^claw-${agent}$"; then
            docker_status="${GREEN}running${NC}"
        fi

        if [ -f "${SCRIPT_DIR}/${agent}/Vagrantfile" ]; then
            local vstat
            vstat=$(cd "${SCRIPT_DIR}/${agent}" && vagrant status --machine-readable 2>/dev/null | grep ",state," | cut -d, -f4 || echo "unknown")
            if [ "${vstat}" = "running" ]; then
                vagrant_status="${GREEN}running${NC}"
            fi
        fi

        printf "  %-12s Docker: %b  |  Vagrant: %b\n" "${agent}" "${docker_status}" "${vagrant_status}"
    done
    echo ""
}

# -------------------------------------------------------------------
# Main — Route commands
# -------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    print_help
    exit 0
fi

COMMAND="${1}"
shift

case "${COMMAND}" in
    help|-h|--help)
        print_help
        ;;

    deploy)
        cmd_deploy "$@"
        ;;

    finetune)
        cmd_finetune "$@"
        ;;

    datasets)
        cmd_datasets "$@"
        ;;

    health)
        cmd_health "${1:-all}"
        ;;

    logs)
        if [[ $# -lt 1 ]]; then
            err "Usage: ./claw.sh logs <agent>"
            exit 1
        fi
        cmd_logs "$1"
        ;;

    status)
        cmd_status
        ;;

    validate)
        # Assessment validation shortcut
        if [[ "${1:-}" == "--assessment" ]] && [[ -n "${2:-}" ]]; then
            if [ -f "${SCRIPT_DIR}/assessment/validate.py" ]; then
                python3 "${SCRIPT_DIR}/assessment/validate.py" "$2"
            else
                err "Validator not found at assessment/validate.py"
                exit 1
            fi
        else
            err "Usage: ./claw.sh validate --assessment <file>"
            exit 1
        fi
        ;;

    security)
        # Security rules engine
        local security_py="${SCRIPT_DIR}/shared/claw_security.py"
        if [ ! -f "${security_py}" ]; then
            err "shared/claw_security.py not found!"
            exit 1
        fi
        local sec_action="${1:-report}"
        shift 2>/dev/null || true
        case "${sec_action}" in
            init)
                python3 "${security_py}" --init-config
                ;;
            report)
                python3 "${security_py}" --report
                ;;
            check-url)
                if [[ -z "${1:-}" ]]; then
                    err "Usage: ./claw.sh security check-url <url>"
                    exit 1
                fi
                python3 "${security_py}" --check-url "$1"
                ;;
            check-content)
                if [[ -z "${1:-}" ]]; then
                    err "Usage: ./claw.sh security check-content <text>"
                    exit 1
                fi
                python3 "${security_py}" --check-content "$1"
                ;;
            check-ip)
                if [[ -z "${1:-}" ]]; then
                    err "Usage: ./claw.sh security check-ip <ip>"
                    exit 1
                fi
                python3 "${security_py}" --check-ip "$1"
                ;;
            generate-prompt)
                local compliance="${CLAW_COMPLIANCE:-}"
                python3 "${security_py}" --generate-prompt --compliance "${compliance}"
                ;;
            validate)
                python3 "${security_py}" --validate
                ;;
            *)
                python3 "${security_py}" "$@"
                ;;
        esac
        ;;

    vault)
        # Encrypted secrets vault management
        local vault_py="${SCRIPT_DIR}/shared/claw_vault.py"
        if [ ! -f "${vault_py}" ]; then
            err "shared/claw_vault.py not found!"
            exit 1
        fi
        # Check for cryptography package
        if ! python3 -c "import cryptography" 2>/dev/null; then
            err "Missing required package. Run: pip install cryptography"
            exit 1
        fi
        # Pass all remaining args to the vault CLI
        python3 "${vault_py}" "$@"
        ;;

    optimizer)
        # Multi-model optimization engine
        local optimizer_py="${SCRIPT_DIR}/shared/claw_optimizer.py"
        if [ ! -f "${optimizer_py}" ]; then
            err "shared/claw_optimizer.py not found!"
            exit 1
        fi
        local opt_action="${1:-}"
        shift 2>/dev/null || true
        case "${opt_action}" in
            init)
                python3 "${optimizer_py}" --init-config
                ;;
            report)
                python3 "${optimizer_py}" --report
                ;;
            start)
                local opt_config="${SCRIPT_DIR}/shared/optimization.json"
                if [ ! -f "${opt_config}" ]; then
                    warn "No optimization.json found — generating default config..."
                    python3 "${optimizer_py}" --init-config
                fi
                python3 "${optimizer_py}" -c "${opt_config}"
                ;;
            ""|--help|-h)
                python3 "${optimizer_py}" --once
                ;;
            *)
                python3 "${optimizer_py}" "$@"
                ;;
        esac
        ;;

    strategy)
        # Model strategy engine
        local strategy_py="${SCRIPT_DIR}/shared/claw_strategy.py"
        if [ ! -f "${strategy_py}" ]; then
            err "shared/claw_strategy.py not found!"
            exit 1
        fi
        local strat_action="${1:-report}"
        shift 2>/dev/null || true
        case "${strat_action}" in
            scan)
                python3 "${strategy_py}" --scan
                ;;
            generate)
                python3 "${strategy_py}" --generate
                ;;
            report)
                python3 "${strategy_py}" --report
                ;;
            init)
                python3 "${strategy_py}" --init-config
                ;;
            benchmark)
                python3 "${strategy_py}" --benchmark
                ;;
            *)
                err "Unknown strategy action: ${strat_action}"
                echo "Usage: ./claw.sh strategy [scan|generate|report|init|benchmark]"
                exit 1
                ;;
        esac
        ;;

    hardware)
        # Hardware detection & runtime recommendation engine
        local hardware_py="${SCRIPT_DIR}/shared/claw_hardware.py"
        if [ ! -f "${hardware_py}" ]; then
            err "shared/claw_hardware.py not found!"
            exit 1
        fi
        local hw_action="${1:-detect}"
        shift 2>/dev/null || true
        case "${hw_action}" in
            detect)
                python3 "${hardware_py}" --detect
                ;;
            report)
                python3 "${hardware_py}" --report
                ;;
            recommend)
                python3 "${hardware_py}" --recommend
                ;;
            json)
                python3 "${hardware_py}" --json
                ;;
            summary)
                python3 "${hardware_py}" --summary
                ;;
            *)
                err "Unknown hardware action: ${hw_action}"
                echo "Usage: ./claw.sh hardware [detect|report|recommend|json|summary]"
                exit 1
                ;;
        esac
        ;;

    llamacpp)
        # llama.cpp local LLM management
        local llamacpp_script="${SCRIPT_DIR}/shared/install-llamacpp.sh"
        if [ ! -f "${llamacpp_script}" ]; then
            err "shared/install-llamacpp.sh not found!"
            exit 1
        fi
        local lc_action="${1:-status}"
        shift 2>/dev/null || true
        case "${lc_action}" in
            install)
                bash "${llamacpp_script}" install
                ;;
            start)
                if [[ $# -eq 0 ]]; then
                    err "Usage: ./claw.sh llamacpp start <model.gguf>"
                    exit 1
                fi
                bash "${llamacpp_script}" start "$1"
                ;;
            list)
                bash "${llamacpp_script}" list
                ;;
            status)
                bash "${llamacpp_script}" status
                ;;
            *)
                err "Unknown llamacpp action: ${lc_action}"
                echo "Usage: ./claw.sh llamacpp [install|start|list|status]"
                exit 1
                ;;
        esac
        ;;

    ollama)
        # Ollama local LLM management
        local ollama_script="${SCRIPT_DIR}/shared/install-ollama.sh"
        if [ ! -f "${ollama_script}" ]; then
            err "shared/install-ollama.sh not found!"
            exit 1
        fi
        local oll_action="${1:-status}"
        shift 2>/dev/null || true
        case "${oll_action}" in
            install)
                bash "${ollama_script}" install "$@"
                ;;
            pull)
                if [[ $# -eq 0 ]]; then
                    err "Usage: ./claw.sh ollama pull <model> [model2] ..."
                    exit 1
                fi
                bash "${ollama_script}" pull "$@"
                ;;
            list)
                bash "${ollama_script}" list
                ;;
            status)
                bash "${ollama_script}" status
                ;;
            *)
                err "Unknown ollama action: ${oll_action}"
                echo "Usage: ./claw.sh ollama [install|pull|list|status]"
                exit 1
                ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Dashboard — Enterprise web dashboard
    # -------------------------------------------------------------------
    dashboard)
        local dashboard_py="${SCRIPT_DIR}/shared/claw_dashboard.py"
        if [ ! -f "${dashboard_py}" ]; then
            err "shared/claw_dashboard.py not found!"
            exit 1
        fi
        case "${1:-start}" in
            start) python3 "${dashboard_py}" --start --port "${2:-9099}" ;;
            stop)  python3 "${dashboard_py}" --stop ;;
            *)     python3 "${dashboard_py}" --start --port "${1:-9099}" ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Wizard — Assessment web wizard
    # -------------------------------------------------------------------
    wizard)
        local wizard_py="${SCRIPT_DIR}/shared/claw_wizard.py"
        if [ ! -f "${wizard_py}" ]; then
            err "shared/claw_wizard.py not found!"
            exit 1
        fi
        case "${1:-start}" in
            start) python3 "${wizard_py}" --start --port "${2:-9098}" ;;
            stop)  python3 "${wizard_py}" --stop ;;
            *)     python3 "${wizard_py}" --start --port "${1:-9098}" ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Router — Live model router proxy
    # -------------------------------------------------------------------
    router)
        local router_py="${SCRIPT_DIR}/shared/claw_router.py"
        if [ ! -f "${router_py}" ]; then
            err "shared/claw_router.py not found!"
            exit 1
        fi
        local rt_action="${1:-start}"
        shift 2>/dev/null || true
        case "${rt_action}" in
            start)  python3 "${router_py}" --start --port "${1:-9095}" ;;
            stop)   python3 "${router_py}" --stop ;;
            status) python3 "${router_py}" --status ;;
            logs)   python3 "${router_py}" --logs ${1:+--tail "$1"} ;;
            *)      python3 "${router_py}" --start --port "${rt_action:-9095}" ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Orchestrator — Multi-agent orchestration
    # -------------------------------------------------------------------
    orchestrator)
        local orch_py="${SCRIPT_DIR}/shared/claw_orchestrator.py"
        if [ ! -f "${orch_py}" ]; then
            err "shared/claw_orchestrator.py not found!"
            exit 1
        fi
        local orch_action="${1:-status}"
        shift 2>/dev/null || true
        case "${orch_action}" in
            start)      python3 "${orch_py}" --start ${1:+--port "$1"} ;;
            stop)       python3 "${orch_py}" --stop ;;
            status)     python3 "${orch_py}" --status ;;
            agents)     python3 "${orch_py}" --agents ;;
            submit)     python3 "${orch_py}" --submit "$@" ;;
            health)     python3 "${orch_py}" --health-check ;;
            *)          python3 "${orch_py}" --status ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Memory — Conversation memory service
    # -------------------------------------------------------------------
    memory)
        local memory_py="${SCRIPT_DIR}/shared/claw_memory.py"
        if [ ! -f "${memory_py}" ]; then
            err "shared/claw_memory.py not found!"
            exit 1
        fi
        local mem_action="${1:-stats}"
        shift 2>/dev/null || true
        case "${mem_action}" in
            start)  python3 "${memory_py}" --start --port "${1:-9096}" ;;
            stop)   python3 "${memory_py}" --stop ;;
            stats)  python3 "${memory_py}" --stats ;;
            search) python3 "${memory_py}" --search "$1" ;;
            prune)  python3 "${memory_py}" --prune ${1:+--days "$1"} ;;
            *)      python3 "${memory_py}" --stats ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # RAG — Retrieval-augmented generation pipeline
    # -------------------------------------------------------------------
    rag)
        local rag_py="${SCRIPT_DIR}/shared/claw_rag.py"
        if [ ! -f "${rag_py}" ]; then
            err "shared/claw_rag.py not found!"
            exit 1
        fi
        local rag_action="${1:-status}"
        shift 2>/dev/null || true
        case "${rag_action}" in
            start)  python3 "${rag_py}" --start --port "${1:-9097}" ;;
            stop)   python3 "${rag_py}" --stop ;;
            status) python3 "${rag_py}" --status ;;
            ingest) python3 "${rag_py}" --ingest "$1" ${2:+--agent "$2"} ;;
            search) python3 "${rag_py}" --search "$1" ${2:+--agent "$2"} ;;
            clear)  python3 "${rag_py}" --clear ${1:+--agent "$1"} ;;
            *)      python3 "${rag_py}" --status ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Billing — Cost analytics & alerting
    # -------------------------------------------------------------------
    billing)
        local billing_py="${SCRIPT_DIR}/shared/claw_billing.py"
        if [ ! -f "${billing_py}" ]; then
            err "shared/claw_billing.py not found!"
            exit 1
        fi
        local bill_action="${1:-status}"
        shift 2>/dev/null || true
        case "${bill_action}" in
            report)   python3 "${billing_py}" --report "${1:-daily}" ;;
            status)   python3 "${billing_py}" --status ;;
            forecast) python3 "${billing_py}" --forecast ;;
            init)     python3 "${billing_py}" --init-config ;;
            threshold)python3 "${billing_py}" --set-threshold "$1" ;;
            *)        python3 "${billing_py}" --status ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Skills — Skills marketplace
    # -------------------------------------------------------------------
    skills)
        local skills_py="${SCRIPT_DIR}/shared/claw_skills.py"
        if [ ! -f "${skills_py}" ]; then
            err "shared/claw_skills.py not found!"
            exit 1
        fi
        local sk_action="${1:-list}"
        shift 2>/dev/null || true
        case "${sk_action}" in
            list)      python3 "${skills_py}" --list ;;
            search)    python3 "${skills_py}" --search "$1" ;;
            install)   python3 "${skills_py}" --install "$1" --agent "${2:-}" ;;
            uninstall) python3 "${skills_py}" --uninstall "$1" --agent "${2:-}" ;;
            bundle)    python3 "${skills_py}" --bundle "$1" --agent "${2:-}" ;;
            installed) python3 "${skills_py}" --installed ${1:+--agent "$1"} ;;
            info)      python3 "${skills_py}" --info "$1" ;;
            bundles)   python3 "${skills_py}" --bundles ;;
            *)         python3 "${skills_py}" --list ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Adapter — Auto-selection of LoRA adapters
    # -------------------------------------------------------------------
    adapter)
        local adapter_py="${SCRIPT_DIR}/shared/claw_adapter_selector.py"
        if [ ! -f "${adapter_py}" ]; then
            err "shared/claw_adapter_selector.py not found!"
            exit 1
        fi
        local ad_action="${1:-list}"
        shift 2>/dev/null || true
        case "${ad_action}" in
            match)  python3 "${adapter_py}" --use-case "$1" ${2:+--industry "$2"} ;;
            list)   python3 "${adapter_py}" --list ;;
            info)   python3 "${adapter_py}" --info "$1" ;;
            search) python3 "${adapter_py}" --match "$1" ;;
            *)      python3 "${adapter_py}" --list ;;
        esac
        ;;

    # -------------------------------------------------------------------
    # Completions — Shell tab-completion scripts
    # -------------------------------------------------------------------
    completions)
        _comp_action="${1:-}"
        case "${_comp_action}" in
            bash)
                if [ -f "${SCRIPT_DIR}/completions/claw-completion.bash" ]; then
                    cat "${SCRIPT_DIR}/completions/claw-completion.bash"
                else
                    err "Bash completion script not found at completions/claw-completion.bash"
                    exit 1
                fi
                ;;
            zsh)
                if [ -f "${SCRIPT_DIR}/completions/_claw" ]; then
                    cat "${SCRIPT_DIR}/completions/_claw"
                else
                    err "Zsh completion script not found at completions/_claw"
                    exit 1
                fi
                ;;
            install)
                header "Installing shell completions..."
                _os_type="$(uname -s)"

                # --- Bash completions ---
                _bash_installed=false
                if [ -f "${SCRIPT_DIR}/completions/claw-completion.bash" ]; then
                    # Try system-wide bash-completion directory
                    if [ -d "/etc/bash_completion.d" ] && [ -w "/etc/bash_completion.d" ]; then
                        cp "${SCRIPT_DIR}/completions/claw-completion.bash" /etc/bash_completion.d/claw
                        log "Bash: installed to /etc/bash_completion.d/claw"
                        _bash_installed=true
                    elif [ -d "/usr/local/etc/bash_completion.d" ] && [ -w "/usr/local/etc/bash_completion.d" ]; then
                        cp "${SCRIPT_DIR}/completions/claw-completion.bash" /usr/local/etc/bash_completion.d/claw
                        log "Bash: installed to /usr/local/etc/bash_completion.d/claw"
                        _bash_installed=true
                    else
                        # Per-user fallback
                        mkdir -p "${HOME}/.local/share/bash-completion/completions"
                        cp "${SCRIPT_DIR}/completions/claw-completion.bash" \
                           "${HOME}/.local/share/bash-completion/completions/claw.sh"
                        log "Bash: installed to ~/.local/share/bash-completion/completions/claw.sh"
                        _bash_installed=true
                    fi
                else
                    warn "Bash completion script not found — skipping"
                fi

                # --- Zsh completions ---
                _zsh_installed=false
                if [ -f "${SCRIPT_DIR}/completions/_claw" ]; then
                    # Try system-wide zsh site-functions
                    if [ -d "/usr/local/share/zsh/site-functions" ] && [ -w "/usr/local/share/zsh/site-functions" ]; then
                        cp "${SCRIPT_DIR}/completions/_claw" /usr/local/share/zsh/site-functions/_claw
                        log "Zsh: installed to /usr/local/share/zsh/site-functions/_claw"
                        _zsh_installed=true
                    elif [ -d "/usr/share/zsh/site-functions" ] && [ -w "/usr/share/zsh/site-functions" ]; then
                        cp "${SCRIPT_DIR}/completions/_claw" /usr/share/zsh/site-functions/_claw
                        log "Zsh: installed to /usr/share/zsh/site-functions/_claw"
                        _zsh_installed=true
                    else
                        # Per-user fallback
                        mkdir -p "${HOME}/.zsh/completions"
                        cp "${SCRIPT_DIR}/completions/_claw" "${HOME}/.zsh/completions/_claw"
                        log "Zsh: installed to ~/.zsh/completions/_claw"
                        info "Add to .zshrc:  fpath=(~/.zsh/completions \$fpath)"
                        _zsh_installed=true
                    fi
                else
                    warn "Zsh completion script not found — skipping"
                fi

                echo ""
                if [ "${_bash_installed}" = true ] || [ "${_zsh_installed}" = true ]; then
                    log "Installation complete. Restart your shell or run:"
                    if [ "${_bash_installed}" = true ]; then
                        info "  source <(./claw.sh completions bash)   # for current bash session"
                    fi
                    if [ "${_zsh_installed}" = true ]; then
                        info "  autoload -Uz compinit && compinit      # for current zsh session"
                    fi
                else
                    err "No completion scripts were installed."
                    exit 1
                fi
                ;;
            ""|--help|-h)
                echo "Usage: ./claw.sh completions <bash|zsh|install>"
                echo ""
                echo "  bash      Print bash completion script to stdout"
                echo "  zsh       Print zsh completion script to stdout"
                echo "  install   Install completions to system directories"
                echo ""
                echo "Quick setup:"
                echo "  source <(./claw.sh completions bash)   # bash"
                echo "  source <(./claw.sh completions zsh)    # zsh (then compinit)"
                ;;
            *)
                err "Unknown completions action: ${_comp_action}"
                echo "Usage: ./claw.sh completions <bash|zsh|install>"
                exit 1
                ;;
        esac
        ;;

    zeroclaw|nanoclaw|picoclaw|openclaw|parlant)
        AGENT="${COMMAND}"
        METHOD="${1:-docker}"

        case "${METHOD}" in
            docker)
                cmd_start_docker "${AGENT}"
                ;;
            vagrant)
                cmd_start_vagrant "${AGENT}"
                ;;
            destroy)
                cmd_destroy "${AGENT}"
                ;;
            *)
                err "Unknown method: ${METHOD}"
                err "Usage: ./claw.sh ${AGENT} [docker|vagrant|destroy]"
                exit 1
                ;;
        esac
        ;;

    *)
        err "Unknown command: ${COMMAND}"
        echo ""
        print_help
        exit 1
        ;;
esac
