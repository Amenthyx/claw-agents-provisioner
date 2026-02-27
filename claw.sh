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
    if ! command -v docker &>/dev/null; then
        err "Docker is not installed. Install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    if ! docker compose version &>/dev/null; then
        err "Docker Compose plugin not found. Install it: https://docs.docker.com/compose/install/"
        exit 1
    fi
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
    echo -e "${BOLD}LOCAL LLM:${NC}"
    echo -e "  ${GREEN}ollama install${NC}               Install Ollama runtime"
    echo -e "  ${GREEN}ollama pull <model>${NC}           Pull a model (e.g., llama3.2, qwen2.5)"
    echo -e "  ${GREEN}ollama list${NC}                  List installed local models"
    echo -e "  ${GREEN}ollama status${NC}                Check Ollama service status"
    echo ""
    echo -e "${BOLD}STRATEGY ENGINE:${NC}"
    echo -e "  ${GREEN}strategy scan${NC}                Discover available models (local + cloud)"
    echo -e "  ${GREEN}strategy generate${NC}            Generate optimal routing strategy"
    echo -e "  ${GREEN}strategy report${NC}              Print current strategy report"
    echo -e "  ${GREEN}strategy init${NC}                Generate strategy config template"
    echo -e "  ${GREEN}strategy benchmark${NC}           Quick latency benchmark"
    echo ""
    echo -e "${BOLD}OPERATIONS:${NC}"
    echo -e "  ${GREEN}health <agent|all>${NC}           Run agent health check"
    echo -e "  ${GREEN}logs <agent>${NC}                 Tail agent logs (Docker)"
    echo -e "  ${GREEN}status${NC}                       Show status of all agents"
    echo -e "  ${GREEN}help${NC}                         Show this help message"
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
    local agent="${1:-all}"
    "${SCRIPT_DIR}/shared/healthcheck.sh" "${agent}"
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
