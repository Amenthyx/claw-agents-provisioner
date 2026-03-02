#!/usr/bin/env bash
# =============================================================================
# claw-completion.bash -- Bash tab completion for claw.sh CLI
# =============================================================================
#
# Installation:
#   Option 1: Source directly in your shell:
#     source /path/to/completions/claw-completion.bash
#
#   Option 2: Copy to bash-completion directory:
#     cp claw-completion.bash /etc/bash_completion.d/claw
#     # or for per-user:
#     cp claw-completion.bash ~/.local/share/bash-completion/completions/claw.sh
#
#   Option 3: Use the built-in installer:
#     ./claw.sh completions install
#
# =============================================================================

_claw() {
    local cur prev words cword
    _init_completion || return

    # -------------------------------------------------------------------------
    # Valid agents and deployment methods
    # -------------------------------------------------------------------------
    local agents="zeroclaw nanoclaw picoclaw openclaw parlant"
    local methods="docker vagrant destroy"

    # -------------------------------------------------------------------------
    # All top-level commands (agents handled separately below)
    # -------------------------------------------------------------------------
    local commands="
        deploy validate finetune datasets
        vault security optimizer strategy hardware
        ollama llamacpp
        dashboard wizard router orchestrator
        memory rag
        billing skills adapter
        health logs status help completions
        zeroclaw nanoclaw picoclaw openclaw parlant
    "

    # -------------------------------------------------------------------------
    # Subcommands for each top-level command
    # -------------------------------------------------------------------------
    local vault_cmds="init import-env list get set rotate export-env"
    local security_cmds="init report check-url check-content check-ip generate-prompt validate"
    local optimizer_cmds="init report start"
    local strategy_cmds="scan generate report init benchmark"
    local hardware_cmds="detect report recommend json summary"
    local ollama_cmds="install pull list status"
    local llamacpp_cmds="install start list status"
    local dashboard_cmds="start stop"
    local wizard_cmds="start stop"
    local router_cmds="start stop status logs"
    local orchestrator_cmds="start stop status agents submit health"
    local memory_cmds="start stop stats search prune"
    local rag_cmds="start stop status ingest search clear"
    local billing_cmds="report status forecast init threshold"
    local skills_cmds="list search install uninstall bundle installed info bundles"
    local adapter_cmds="match list info search"
    local completions_cmds="bash zsh install"

    # -------------------------------------------------------------------------
    # Determine completion based on position and previous words
    # -------------------------------------------------------------------------

    # Complete flags that expect a file argument
    case "${prev}" in
        --assessment)
            _filedir 'json'
            return
            ;;
        --adapter)
            # Complete adapter names from the finetune/adapters directory
            local script_dir
            script_dir="$(cd "$(dirname "$(command -v claw.sh 2>/dev/null || echo "${COMP_WORDS[0]}")")" && pwd)"
            local adapter_dir="${script_dir}/finetune/adapters"
            if [[ -d "${adapter_dir}" ]]; then
                local adapters
                adapters=$(ls -1 "${adapter_dir}" 2>/dev/null)
                COMPREPLY=($(compgen -W "${adapters}" -- "${cur}"))
            fi
            return
            ;;
    esac

    # Position 1: top-level command
    if [[ ${cword} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
        return
    fi

    # Position 2+: subcommand / flag completion based on top-level command
    local cmd="${words[1]}"

    case "${cmd}" in

        # -- Agent commands: <agent> [docker|vagrant|destroy] --
        zeroclaw|nanoclaw|picoclaw|openclaw|parlant)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${methods}" -- "${cur}"))
            fi
            return
            ;;

        # -- deploy: --assessment <file> --
        deploy)
            if [[ ${cword} -eq 2 ]] || [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--assessment" -- "${cur}"))
            fi
            return
            ;;

        # -- validate: --assessment <file> --
        validate)
            if [[ ${cword} -eq 2 ]] || [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--assessment" -- "${cur}"))
            fi
            return
            ;;

        # -- finetune: --assessment <file> | --adapter <name> [--dry-run] --
        finetune)
            if [[ "${cur}" == -* ]] || [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--assessment --adapter --dry-run" -- "${cur}"))
            fi
            return
            ;;

        # -- datasets: --list | --validate | --download-all --
        datasets)
            if [[ ${cword} -eq 2 ]] || [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--list --validate --download-all" -- "${cur}"))
            fi
            return
            ;;

        # -- vault: subcommands --
        vault)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${vault_cmds}" -- "${cur}"))
            elif [[ ${cword} -eq 3 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    import-env|export-env)
                        _filedir 'env'
                        ;;
                esac
            fi
            return
            ;;

        # -- security: subcommands --
        security)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${security_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- optimizer: subcommands --
        optimizer)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${optimizer_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- strategy: subcommands --
        strategy)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${strategy_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- hardware: subcommands --
        hardware)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${hardware_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- ollama: subcommands --
        ollama)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${ollama_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- llamacpp: subcommands --
        llamacpp)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${llamacpp_cmds}" -- "${cur}"))
            elif [[ ${cword} -eq 3 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    start)
                        # Complete .gguf model files
                        _filedir 'gguf'
                        ;;
                esac
            fi
            return
            ;;

        # -- dashboard: subcommands --
        dashboard)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${dashboard_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- wizard: subcommands --
        wizard)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${wizard_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- router: subcommands --
        router)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${router_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- orchestrator: subcommands --
        orchestrator)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${orchestrator_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- memory: subcommands --
        memory)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${memory_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- rag: subcommands --
        rag)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${rag_cmds}" -- "${cur}"))
            elif [[ ${cword} -eq 3 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    ingest)
                        # Complete file/directory paths for document ingestion
                        _filedir
                        ;;
                    clear)
                        # Complete agent names
                        COMPREPLY=($(compgen -W "${agents}" -- "${cur}"))
                        ;;
                esac
            fi
            return
            ;;

        # -- billing: subcommands --
        billing)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${billing_cmds}" -- "${cur}"))
            elif [[ ${cword} -eq 3 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    report)
                        COMPREPLY=($(compgen -W "daily weekly monthly" -- "${cur}"))
                        ;;
                esac
            fi
            return
            ;;

        # -- skills: subcommands --
        skills)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${skills_cmds}" -- "${cur}"))
            elif [[ ${cword} -eq 3 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    install|uninstall|bundle)
                        # Third arg for install/uninstall is skill ID, then agent
                        ;;
                    installed)
                        # Optional agent filter
                        COMPREPLY=($(compgen -W "${agents}" -- "${cur}"))
                        ;;
                esac
            elif [[ ${cword} -eq 4 ]]; then
                local subcmd="${words[2]}"
                case "${subcmd}" in
                    install|uninstall|bundle)
                        # Fourth arg is agent name
                        COMPREPLY=($(compgen -W "${agents}" -- "${cur}"))
                        ;;
                esac
            fi
            return
            ;;

        # -- adapter: subcommands --
        adapter)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${adapter_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- health: agent name or "all" --
        health)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${agents} all" -- "${cur}"))
            fi
            return
            ;;

        # -- logs: agent name --
        logs)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${agents}" -- "${cur}"))
            fi
            return
            ;;

        # -- completions: bash | zsh | install --
        completions)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=($(compgen -W "${completions_cmds}" -- "${cur}"))
            fi
            return
            ;;

        # -- help, status: no further completions --
        help|status|-h|--help)
            return
            ;;
    esac
}

# Register the completion function for claw.sh and common aliases
complete -F _claw claw.sh
complete -F _claw claw
complete -F _claw ./claw.sh
