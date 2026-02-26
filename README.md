# Claw Agents Provisioner

One-command deployment of personalized AI agents. Transform a client needs assessment into a fully configured, running AI agent with domain-specific fine-tuning.

```bash
./claw.sh deploy --assessment client-assessment.json
```

## What It Does

1. A consultant fills out a client assessment form (JSON)
2. The system auto-selects the right platform, LLM model, and skills
3. It generates all configuration files and optionally triggers fine-tuning
4. The client gets a running, personalized AI agent in under 15 minutes

## Supported Platforms

| Platform | Language | Best For | Resource Usage |
|----------|----------|----------|---------------|
| **ZeroClaw** | Rust | Efficiency, encryption, multi-provider | 7.8 MB binary |
| **NanoClaw** | TypeScript | Security-critical, container isolation | Claude-native |
| **PicoClaw** | Go | Edge/IoT, Raspberry Pi, budget | 8 MB RAM |
| **OpenClaw** | TypeScript | Maximum integrations, 50+ channels | Full-featured |

## Quick Start

### Prerequisites

- Docker + Docker Compose (or Vagrant + VirtualBox)
- Python 3.11+ (for assessment pipeline)
- Git

### 1. Clone and configure

```bash
git clone https://github.com/Amenthyx/claw-agents-provisioner.git
cd claw-agents-provisioner
cp .env.template .env
# Edit .env with your API keys
```

### 2. Deploy a specific agent

```bash
# Via Docker
./claw.sh zeroclaw docker
./claw.sh nanoclaw docker
./claw.sh picoclaw docker
./claw.sh openclaw docker

# Via Vagrant
./claw.sh zeroclaw vagrant
./claw.sh nanoclaw vagrant
```

### 3. Deploy from assessment

```bash
# Validate the assessment first
./claw.sh validate --assessment client-assessment.json

# Deploy (auto-selects platform, model, skills)
./claw.sh deploy --assessment client-assessment.json
```

## Assessment Pipeline

The assessment pipeline transforms a client intake form into a complete agent configuration:

```
client-assessment.json
    --> validate.py   (schema + business logic validation)
    --> resolve.py    (platform + model + skills selection)
    --> generate_env  (.env file with all settings)
    --> generate_config (agent-specific config files)
    --> claw.sh deploy (Docker or Vagrant provisioning)
```

### Resolution Algorithm

The resolver scores 15 deployment profiles using weighted factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Use case overlap | Highest | Match assessment use cases to profile |
| Budget fit | High | Must be affordable for client |
| Complexity match | Medium | Task difficulty alignment |
| Sensitivity match | Medium | Security requirements |
| Channel match | Medium | Communication channel support |
| Device affinity | Medium | Hardware constraints |
| Regulation match | Medium | Compliance alignment |
| Storage preference | Low | Data residency |

### Model Selection

| Condition | Model |
|-----------|-------|
| $0 budget | DeepSeek V3.2 (free tier) |
| Expert complexity + $100+ budget | Claude Opus 4.6 |
| Maximum context + $50+ budget | GPT-4.1 (1M tokens) |
| Default best value | Claude Sonnet 4.6 |

## Example Walkthroughs

### Real Estate Agent (Lucia)

Lucia runs a real estate agency in Milan. She needs a WhatsApp bot for lead qualification with Italian + English support.

```bash
# Assessment highlights:
# - Industry: real-estate
# - Budget: $25/month
# - Channels: WhatsApp
# - Languages: Italian, English
# - GDPR compliance required

./claw.sh deploy --assessment examples/example-realstate.json
# --> Selects: OpenClaw + Claude Sonnet 4.6
# --> Skills: whatsapp-business, crm-sync, auto-reply, lead-qualifier
# --> Fine-tuning: QLoRA with 02-real-estate dataset
```

### IoT Sensor Monitor (Priya)

Priya deploys sensor monitors on a Raspberry Pi fleet with $0 API budget.

```bash
# Assessment highlights:
# - Industry: iot
# - Budget: $0/month
# - Channels: Telegram
# - Devices: Raspberry Pi

./claw.sh deploy --assessment examples/example-iot.json
# --> Selects: PicoClaw + DeepSeek V3.2 (free)
# --> Skills: sensor-monitor, telegram-alerts
# --> Runs on 8 MB RAM
```

### DevSecOps Agent (Kai)

Kai's SaaS startup needs container-isolated code review with GDPR compliance.

```bash
# Assessment highlights:
# - Industry: software-development
# - Budget: $100+/month
# - Channels: Slack, GitHub
# - High data sensitivity
# - GDPR compliance required

./claw.sh deploy --assessment examples/example-devsecops.json
# --> Selects: NanoClaw + Claude Sonnet 4.6
# --> Skills: code-review, ci-integration, security-scan
# --> Container isolation enabled
```

## Fine-Tuning

### 50 Pre-Built Datasets

All datasets are committed in-repo (250,000 total rows from HuggingFace):

```bash
# List all datasets
./claw.sh datasets --list

# Validate all 50 datasets
./claw.sh datasets --validate

# Train a LoRA adapter
./claw.sh finetune --adapter customer-support

# Train with QLoRA (less VRAM)
python finetune/train_qlora.py --adapter 01-customer-support

# Dry run (validate without training)
./claw.sh finetune --adapter customer-support --dry-run
```

### VRAM Requirements

| Method | VRAM | Training Time |
|--------|------|---------------|
| LoRA (full precision) | 24+ GB | ~2 hours |
| QLoRA (4-bit) | 8-16 GB | ~1 hour |

### Using System Prompts (API-Only Models)

For models that don't support LoRA (Claude, GPT, DeepSeek), use the enriched system prompts:

```bash
cat finetune/adapters/01-customer-support/system_prompt.txt
```

See [finetune/datasets/README.md](finetune/datasets/README.md) for the full dataset catalog and [finetune/adapters/README.md](finetune/adapters/README.md) for adapter configurations.

## CLI Reference

```bash
# Agent deployment
./claw.sh <agent> docker          # Start agent via Docker
./claw.sh <agent> vagrant         # Start agent via Vagrant
./claw.sh <agent> destroy         # Teardown agent

# Assessment pipeline
./claw.sh validate --assessment <file>   # Validate assessment
./claw.sh deploy --assessment <file>     # Full deployment

# Fine-tuning
./claw.sh finetune --assessment <file>   # Assessment-driven fine-tuning
./claw.sh finetune --adapter <use-case>  # Train specific adapter
./claw.sh finetune --adapter <use-case> --dry-run  # Validate only

# Datasets
./claw.sh datasets --list               # List all 50 datasets
./claw.sh datasets --validate           # Validate datasets
./claw.sh datasets --download-all       # Re-download from HuggingFace
./claw.sh datasets --stats              # Show dataset statistics

# Health
./claw.sh health <agent>                # Run health check
./claw.sh help                          # Show help
```

## Project Structure

```
claw-agents-provisioner/
├── assessment/               # Assessment pipeline (Python)
│   ├── schema/               # JSON Schema for client assessment
│   ├── validate.py           # Schema validator
│   ├── resolve.py            # Platform/model/skills resolver
│   ├── generate_env.py       # .env file generator
│   ├── generate_config.py    # Agent config generator
│   └── needs-mapping-matrix.json
├── finetune/                 # Fine-tuning pipeline
│   ├── datasets/             # 50 datasets (5,000 rows each)
│   ├── adapters/             # 50 adapter configs
│   ├── train_lora.py         # LoRA training
│   ├── train_qlora.py        # QLoRA training
│   ├── merge_adapter.py      # Merge adapter into base model
│   └── Dockerfile.finetune   # GPU training container
├── zeroclaw/                 # ZeroClaw provisioning
├── nanoclaw/                 # NanoClaw provisioning
├── picoclaw/                 # PicoClaw provisioning
├── openclaw/                 # OpenClaw provisioning
├── shared/                   # Shared provisioning scripts
├── claw.sh                   # Unified CLI launcher
├── docker-compose.yml        # Multi-agent Docker Compose
└── .env.template             # Environment variable template
```

## Configuration

### Environment Variables

Copy `.env.template` to `.env` and fill in your API keys:

```bash
cp .env.template .env
```

Key sections in `.env`:
- **LLM Provider Keys**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`
- **Channel Tokens**: `WHATSAPP_TOKEN`, `TELEGRAM_BOT_TOKEN`, `SLACK_BOT_TOKEN`
- **Agent Selection**: `CLAW_PLATFORM`, `CLAW_MODEL`
- **Fine-Tuning**: `FINETUNE_METHOD`, `FINETUNE_BASE_MODEL`, `FINETUNE_LORA_RANK`

### Docker Compose Profiles

Run agents independently or together:

```bash
# Single agent
docker compose --profile zeroclaw up -d

# Multiple agents
docker compose --profile zeroclaw --profile picoclaw up -d

# All agents
docker compose --profile zeroclaw --profile nanoclaw --profile picoclaw --profile openclaw up -d
```

## Troubleshooting

### Docker build fails

```bash
# Verify Docker is running
docker info

# Check available disk space
docker system df

# Clean up unused images
docker system prune
```

### Vagrant VM doesn't start

```bash
# Check VirtualBox is installed
vagrant --version
VBoxManage --version

# Destroy and recreate
./claw.sh <agent> destroy
./claw.sh <agent> vagrant
```

### Assessment validation fails

```bash
# Run with verbose output
python assessment/validate.py client-assessment.json

# Check the example for reference
cat assessment/client-assessment.example.json
```

### Fine-tuning OOM (out of memory)

```bash
# Use QLoRA instead of LoRA (requires less VRAM)
python finetune/train_qlora.py --adapter 01-customer-support

# Reduce batch size
python finetune/train_qlora.py --adapter 01-customer-support --batch-size 2

# Check VRAM estimate in adapter config
cat finetune/adapters/01-customer-support/training_config.json
```

### Dataset issues

```bash
# Validate all datasets
python finetune/validate_datasets.py

# Re-download a specific dataset
python finetune/datasets/download_real_data.py --id 01

# Re-download all datasets
python finetune/datasets/download_real_data.py --all
```

## CI/CD

GitHub Actions runs on every push to `main`:

- **ShellCheck**: Lint all `.sh` files
- **Hadolint**: Lint all Dockerfiles
- **Ruff**: Lint all Python files
- **Docker Build**: Build all 4 agent images
- **Docker Compose**: Validate `docker-compose.yml`
- **Assessment**: Validate example assessment files
- **Datasets**: Validate all 50 datasets
- **Security**: Scan for secrets and PII in tracked files

## License

[Apache License 2.0](LICENSE)

Copyright 2026 Amenthyx
