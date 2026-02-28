# Claw Agents Provisioner — AI Context

> For AI coding assistants working on this repository.

## Project Overview

**Claw Agents Provisioner** is a one-command deployment system for 5 AI agent platforms (ZeroClaw, NanoClaw, PicoClaw, OpenClaw, Parlant). It transforms a client needs assessment (JSON) into a fully configured, running AI agent with domain-specific fine-tuning. Includes a Model Strategy Engine for optimal local+cloud model routing.

**Repository**: `Amenthyx/claw-agents-provisioner`
**License**: Apache-2.0
**Language mix**: Bash (provisioning), Python (assessment pipeline + fine-tuning), Docker, Vagrant

## Architecture

```
client-assessment.json
        |
        v
  [validate.py] --> schema check
        |
        v
  [resolve.py]  --> platform + model + skills selection
        |
        v
  [generate_env.py] --> .env file
  [generate_config.py] --> agent-specific config
        |
        v
  [claw.sh deploy] --> Docker or Vagrant provisioning
        |
        v
  [optional: train_lora.py / train_qlora.py] --> LoRA adapter
```

## Directory Structure

```
claw-agents-provisioner/
├── assessment/               # Assessment pipeline (Python)
│   ├── schema/               # JSON Schema for client assessment
│   ├── validate.py           # Schema validator
│   ├── resolve.py            # Platform/model/skills resolver
│   ├── generate_env.py       # .env file generator
│   ├── generate_config.py    # Agent config generator
│   └── needs-mapping-matrix.json  # 15 deployment profiles
├── finetune/                 # Fine-tuning pipeline
│   ├── datasets/             # 50 use-case datasets (5,000 rows each)
│   │   ├── 01-customer-support/  # data.jsonl + metadata.json
│   │   ├── ...
│   │   └── 50-personal-finance-budgeting/
│   ├── adapters/             # 50 pre-built adapter configs
│   │   ├── 01-customer-support/  # adapter_config.json + system_prompt.txt + training_config.json
│   │   ├── ...
│   │   └── 50-personal-finance-budgeting/
│   ├── train_lora.py         # Full-precision LoRA training
│   ├── train_qlora.py        # 4-bit quantized QLoRA training
│   ├── merge_adapter.py      # Merge adapter into base model
│   ├── dataset_generator.py  # Assessment-to-dataset converter
│   ├── download_datasets.py  # Dataset registry + downloader
│   ├── validate_datasets.py  # Dataset validation
│   ├── download_real_data.py # Real HuggingFace data downloader
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile.finetune   # GPU training container
├── zeroclaw/                 # ZeroClaw agent (Rust, 7.8 MB)
│   ├── Dockerfile
│   ├── Vagrantfile
│   ├── install-zeroclaw.sh
│   └── entrypoint.sh
├── nanoclaw/                 # NanoClaw agent (TypeScript, Claude-powered)
│   ├── Dockerfile
│   ├── Vagrantfile
│   ├── install-nanoclaw.sh
│   └── entrypoint.sh
├── picoclaw/                 # PicoClaw agent (Go, 8 MB RAM)
│   ├── Dockerfile
│   ├── Vagrantfile
│   ├── install-picoclaw.sh
│   └── entrypoint.sh
├── openclaw/                 # OpenClaw agent (TypeScript, 50+ integrations)
│   ├── Dockerfile
│   ├── Vagrantfile
│   ├── install-openclaw.sh
│   └── entrypoint.sh
├── parlant/                 # Parlant agent (Python, guidelines+MCP)
│   ├── Dockerfile
│   ├── Vagrantfile
│   ├── install-parlant.sh
│   ├── entrypoint.sh
│   └── config/parlant.env
├── shared/                   # Shared provisioning scripts & enterprise modules
│   ├── provision-base.sh
│   ├── healthcheck.sh
│   ├── install-ollama.sh     # Ollama installer
│   ├── install-llamacpp.sh   # llama.cpp installer
│   ├── ollama-models.json    # Local model registry
│   ├── skills-installer.sh
│   ├── skills-catalog.json   # 42 skills, 6 bundles
│   ├── claw_hardware.py      # Hardware detection & runtime recommendation
│   ├── claw_strategy.py      # Model strategy engine
│   ├── claw_security.py      # Security rules engine
│   ├── claw_optimizer.py     # Multi-model cost optimizer
│   ├── claw_vault.py         # Encrypted secrets vault
│   ├── claw_watchdog.py      # Process monitor & auto-restart
│   ├── claw_dashboard.py     # Enterprise web dashboard (:9099)
│   ├── claw_router.py        # OpenAI-compatible model router (:9095)
│   ├── claw_memory.py        # SQLite conversation memory (:9096)
│   ├── claw_rag.py           # Trigram-based RAG pipeline (:9097)
│   ├── claw_wizard.py        # Assessment web wizard (:9098)
│   ├── claw_wizard_api.py    # React wizard backend API
│   ├── claw_orchestrator.py  # Multi-agent task orchestration
│   ├── claw_billing.py       # Cost analytics & alerting
│   ├── claw_skills.py        # Skills marketplace manager
│   └── claw_adapter_selector.py  # Auto LoRA adapter selection
├── tests/                    # Pytest test suite
├── wizard-ui/                # React installation wizard (Vite + TS + Tailwind)
├── data/                     # Runtime data (gitignored except .gitkeep)
├── .team/                    # Project management artifacts
├── .github/workflows/ci.yml  # GitHub Actions CI (shellcheck, hadolint, ruff, pytest)
├── claw.sh                   # Unified CLI launcher
├── install.sh                # Interactive installer (15 steps)
├── docker-compose.yml        # Multi-agent Docker Compose
├── .env.template             # Environment variable template
└── .gitignore
```

## Key Concepts

### 5 Claw Platforms
| Platform | Language | Strengths | Use When |
|----------|----------|-----------|----------|
| ZeroClaw | Rust | 7.8 MB binary, encrypted, multi-provider | Efficiency + encryption needed |
| NanoClaw | TypeScript | Container isolation, Claude-native | Security-critical workloads |
| PicoClaw | Go | 8 MB RAM, edge-ready | Budget/IoT/Raspberry Pi |
| OpenClaw | TypeScript | 50+ integrations, channels | Maximum integrations needed |
| Parlant | Python | Behavioral guidelines, journeys, MCP tools | Guideline-driven conversational AI |

### Assessment Pipeline
The resolver uses weighted scoring across 8 factors (use case overlap, budget, complexity, sensitivity, channel, device, regulation, storage) to match a client assessment to one of 16 deployment profiles in the needs-mapping-matrix.

### Local LLM Support
Supports 6 local LLM runtimes with automatic model discovery and hardware-aware runtime recommendation:
- **Ollama** (:11434) — easiest setup, CPU + GPU (Metal, CUDA, ROCm)
- **vLLM** (:8000) — highest throughput GPU inference (CUDA)
- **llama.cpp** (:8080) — most efficient CPU inference, GGUF models
- **ipex-llm** (:8010) — Intel-optimized with SYCL/AMX acceleration
- **SGLang** (:30000) — fast serving with RadixAttention (CUDA)
- **Docker Model Runner** (:12434) — Docker-native model serving

### Hardware Detection Engine
`claw_hardware.py` auto-detects GPU (NVIDIA/AMD/Intel/Apple Silicon), VRAM, CPU features (AVX-512, AMX), and RAM. Recommends the best runtime per hardware profile. Used by `install.sh` Step 3 and `claw_strategy.py` for hardware-aware model scoring.

### Model Strategy Engine
Auto-discovers local + cloud models and generates `strategy.json` with optimal routing per task type (reasoning, coding, creative, chat, translation, summarization, data analysis). Prefers free local models when quality is comparable to cloud. Includes hardware-aware scoring when hardware profile is available.

### Fine-Tuning
- **LoRA**: Full-precision, 24+ GB VRAM, PEFT library
- **QLoRA**: 4-bit NF4 quantized, 8-16 GB VRAM, paged_adamw_8bit
- **50 datasets**: Real HuggingFace data, 5,000 rows each, chat format
- **Chat format**: `{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}`

### Dataset Format
Each dataset directory contains:
- `data.jsonl` — Training data in chat format (5,000 rows)
- `metadata.json` — Source URL, license, row count, domain tags

### Adapter Config Bundle
Each adapter directory contains:
- `adapter_config.json` — LoRA rank, target modules, base model
- `system_prompt.txt` — Enriched system prompt for API-only models
- `training_config.json` — Hyperparameters, VRAM estimate

## Common Workflows

### Deploy an agent from assessment
```bash
./claw.sh deploy --assessment client-assessment.json
```

### Fine-tune an adapter
```bash
./claw.sh finetune --adapter customer-support
./claw.sh finetune --adapter customer-support --dry-run
```

### Validate datasets
```bash
./claw.sh datasets --validate
./claw.sh datasets --list
```

### Run specific agent via Docker
```bash
./claw.sh zeroclaw docker
./claw.sh nanoclaw docker
./claw.sh picoclaw docker
./claw.sh openclaw docker
./claw.sh parlant docker
```

### Local LLM management
```bash
./claw.sh ollama install
./claw.sh ollama pull llama3.2 qwen2.5
./claw.sh strategy scan
./claw.sh strategy generate
```

### Enterprise Dashboard (:9099)
`claw_dashboard.py` — Stdlib HTTP server serving an embedded SPA. Provides agent fleet management, model strategy view, hardware profile, fine-tuning manager, security dashboard, cost analytics, and settings. Dark-theme UI with auto-polling.

### Live Model Router (:9095)
`claw_router.py` — OpenAI-compatible `/v1/chat/completions` proxy. Routes requests to best available model based on task type detection from system prompts. Load balancing, automatic failover (primary → fallback, local → cloud), rate limiting, request logging.

### Conversation Memory (:9096)
`claw_memory.py` — SQLite-backed conversation memory with per-agent history, cross-agent context sharing, full-text search, auto-summarization, and configurable retention policies.

### RAG Pipeline (:9097)
`claw_rag.py` — Trigram-based retrieval-augmented generation. Document ingestion (.txt, .md, .json, .jsonl), character trigram indexing with Jaccard similarity, per-agent knowledge bases. No vector DB dependency.

### Assessment Wizard (:9098)
`claw_wizard.py` — Web form guiding users through assessment creation: Company Info → Use Case → Requirements → Budget → Review. Generates `client-assessment.json` and optionally triggers deployment.

### Multi-Agent Orchestrator
`claw_orchestrator.py` — SQLite-backed task queue with priority, agent registry, keyword-based task routing, pipeline builder for multi-agent chains, event bus for agent-to-agent communication.

### Cost Analytics
`claw_billing.py` — Tracks API usage costs (cloud per-token pricing, local electricity estimates). Daily/weekly/monthly reports, spend threshold alerts, linear forecast extrapolation.

### Skills Marketplace
`claw_skills.py` + `skills-catalog.json` — 42 skills across 8 categories, 6 pre-built bundles. Per-agent install/uninstall with dependency resolution and platform compatibility checking.

### Adapter Auto-Selection
`claw_adapter_selector.py` — Maps assessment use cases to the best LoRA adapter from 50 available. Scores by keyword match, domain tag overlap, industry aliases, and dataset quality.

### React Installation Wizard
`wizard-ui/` — React 19 + TypeScript + Vite + Tailwind CSS. 9-step wizard (Welcome → Platform → Deployment → LLM → Hardware → Models → Security → Review → Deploy). Served at `/wizard` via dashboard or standalone on :3000.

### Port Map
| Service | Port |
|---------|------|
| Ollama | 11434 |
| vLLM | 8000 |
| llama.cpp | 8080 |
| ipex-llm | 8010 |
| SGLang | 30000 |
| Docker Model Runner | 12434 |
| ZeroClaw | 3100 |
| NanoClaw | 3200 |
| PicoClaw | 3300 |
| OpenClaw | 3400 |
| Parlant | 8800 |
| Router | 9095 |
| Memory | 9096 |
| RAG | 9097 |
| Assessment Wizard | 9098 |
| Dashboard | 9099 |
| Orchestrator | 9100 |
| React Wizard UI | 3000 |

### Enterprise CLI Commands
```bash
./claw.sh dashboard start|stop         # Web dashboard
./claw.sh wizard start|stop            # Assessment wizard
./claw.sh router start|stop|status     # Model router
./claw.sh memory start|stop|stats      # Conversation memory
./claw.sh rag start|stop|ingest|search # RAG pipeline
./claw.sh orchestrator start|stop      # Task orchestration
./claw.sh billing report|status|forecast # Cost analytics
./claw.sh skills list|search|install   # Skills marketplace
./claw.sh adapter match|list|info      # LoRA adapter selection
```

## Important Constraints

- `.env` files and client assessment JSONs are gitignored (no secrets/PII in repo)
- Each agent is independently installable (no cross-agent dependencies)
- Install scripts are idempotent
- All 50 datasets are committed in-repo (not downloaded at runtime)
- Assessment pipeline works offline (except skills installation)
- LoRA adapters are loaded at runtime (no model weight modification)
- All shared Python modules use stdlib only (Python 3.8+, no pip dependencies except cryptography for vault)
- Runtime data stored in `data/` directory (gitignored)
