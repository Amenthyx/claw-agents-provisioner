# Claw Agents Provisioner — AI Context

> For AI coding assistants working on this repository.

## Project Overview

**Claw Agents Provisioner** is a one-command deployment system for 4 AI agent platforms (ZeroClaw, NanoClaw, PicoClaw, OpenClaw). It transforms a client needs assessment (JSON) into a fully configured, running AI agent with domain-specific fine-tuning.

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
├── shared/                   # Shared provisioning scripts
│   ├── provision-base.sh
│   ├── healthcheck.sh
│   └── skills-installer.sh
├── .team/                    # Project management artifacts
├── .github/workflows/ci.yml # GitHub Actions CI
├── claw.sh                   # Unified CLI launcher
├── docker-compose.yml        # Multi-agent Docker Compose
├── .env.template             # Environment variable template
└── .gitignore
```

## Key Concepts

### 4 Claw Platforms
| Platform | Language | Strengths | Use When |
|----------|----------|-----------|----------|
| ZeroClaw | Rust | 7.8 MB binary, encrypted, multi-provider | Efficiency + encryption needed |
| NanoClaw | TypeScript | Container isolation, Claude-native | Security-critical workloads |
| PicoClaw | Go | 8 MB RAM, edge-ready | Budget/IoT/Raspberry Pi |
| OpenClaw | TypeScript | 50+ integrations, channels | Maximum integrations needed |

### Assessment Pipeline
The resolver uses weighted scoring across 8 factors (use case overlap, budget, complexity, sensitivity, channel, device, regulation, storage) to match a client assessment to one of 15 deployment profiles in the needs-mapping-matrix.

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
```

## Important Constraints

- `.env` files and client assessment JSONs are gitignored (no secrets/PII in repo)
- Each agent is independently installable (no cross-agent dependencies)
- Install scripts are idempotent
- All 50 datasets are committed in-repo (not downloaded at runtime)
- Assessment pipeline works offline (except skills installation)
- LoRA adapters are loaded at runtime (no model weight modification)
