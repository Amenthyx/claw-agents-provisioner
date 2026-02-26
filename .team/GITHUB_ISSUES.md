# GitHub Issues Tracking — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Note: These are issue TEMPLATES to be created in GitHub when the repo is set up. Do NOT create via CLI yet.

---

## Issue Labels

| Label | Color | Description |
|-------|-------|-------------|
| `P0` | `#d73a4a` | Must-Have — Launch Blocker |
| `P1` | `#e4e669` | Should-Have — Important |
| `P2` | `#0e8a16` | Nice-to-Have |
| `milestone:M1` | `#1d76db` | Foundation + ZeroClaw |
| `milestone:M2` | `#1d76db` | NanoClaw + PicoClaw |
| `milestone:M3` | `#1d76db` | OpenClaw + Multi-Agent |
| `milestone:M4` | `#1d76db` | Assessment Pipeline |
| `milestone:M5a` | `#1d76db` | Datasets + Adapters |
| `milestone:M5b` | `#1d76db` | Fine-Tuning Pipeline |
| `milestone:M6` | `#1d76db` | CI/CD + Docs |
| `role:devops` | `#7057ff` | DevOps Engineer |
| `role:be` | `#7057ff` | Backend Engineer |
| `role:infra` | `#7057ff` | Infrastructure Engineer |
| `role:pm` | `#7057ff` | Project Manager |
| `wave:3` | `#bfd4f2` | Wave 3 — Engineering |
| `wave:4` | `#bfd4f2` | Wave 4 — QA |
| `wave:5` | `#bfd4f2` | Wave 5 — Release |

---

## Milestone M1 — Foundation + ZeroClaw

### Issue #1: Repository structure scaffold
- **Labels**: `P0`, `milestone:M1`, `role:infra`, `wave:3`
- **Assignee**: INFRA
- **Description**: Create the full directory tree per strategy Section 4 monorepo layout. All folders, placeholder READMEs where needed.
- **Acceptance Criteria**:
  - [ ] All directories exist: `assessment/`, `finetune/`, `zeroclaw/`, `nanoclaw/`, `picoclaw/`, `openclaw/`, `shared/`, `.ai/`
  - [ ] `finetune/datasets/` and `finetune/adapters/` subdirectories created
  - [ ] No unnecessary files — only structure

### Issue #2: Unified .env.template
- **Labels**: `P0`, `milestone:M1`, `role:infra`, `wave:3`
- **Assignee**: INFRA
- **Description**: Create `.env.template` with all sections: LLM API keys, chat channel tokens, agent selection, assessment-derived config, fine-tuning config, agent-specific overrides. All values are placeholders with descriptive comments.
- **Acceptance Criteria**:
  - [ ] All env vars from strategy Section 13 present
  - [ ] Sections clearly delimited with comment headers
  - [ ] No real API keys or secrets
  - [ ] Copying to `.env` and filling relevant section works for any agent

### Issue #3: .gitignore and .gitattributes
- **Labels**: `P0`, `milestone:M1`, `role:infra`, `wave:3`
- **Assignee**: INFRA
- **Description**: Configure `.gitignore` to exclude `.env`, `client-assessment*.json` (except examples), `finetune/runs/`, adapter weights. Configure `.gitattributes` for LFS on large files.
- **Acceptance Criteria**:
  - [ ] `.env` ignored, `.env.template` tracked
  - [ ] `client-assessment*.json` ignored, `*.example.json` tracked
  - [ ] `finetune/datasets/` NOT ignored (datasets must be committed)
  - [ ] `*.parquet` and `*.csv` > 10 MB tracked via LFS

### Issue #4: claw.sh unified launcher
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `claw.sh` — the top-level CLI that routes `./claw.sh <agent> [vagrant|docker]` to the correct provisioning method. Skeleton with extensibility for future commands (deploy, validate, finetune, datasets, destroy).
- **Acceptance Criteria**:
  - [ ] `./claw.sh zeroclaw docker` starts ZeroClaw in Docker
  - [ ] `./claw.sh zeroclaw vagrant` starts ZeroClaw in Vagrant
  - [ ] `./claw.sh --help` prints usage
  - [ ] Exits with clear error for unknown agents/methods
  - [ ] `shellcheck` clean

### Issue #5: ZeroClaw Vagrantfile
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `zeroclaw/Vagrantfile` targeting Ubuntu 24.04 (`ubuntu/noble64`), 4096 MB RAM, provisions via `provision-base.sh` + `install-zeroclaw.sh`.
- **Acceptance Criteria**:
  - [ ] `vagrant up` in `zeroclaw/` completes without errors
  - [ ] ZeroClaw binary available inside VM
  - [ ] `zeroclaw doctor` passes inside VM
  - [ ] VM memory set to 4096 MB (R02 mitigation)

### Issue #6: ZeroClaw Dockerfile
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `zeroclaw/Dockerfile` using multi-stage build (build stage: `rust:slim`, runtime stage: minimal image). Pre-built binary download as primary path.
- **Acceptance Criteria**:
  - [ ] `docker build -t claw-zeroclaw zeroclaw/` succeeds
  - [ ] Final image < 200 MB
  - [ ] `hadolint` clean
  - [ ] Agent starts and responds to health check

### Issue #7: ZeroClaw install script
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `zeroclaw/install-zeroclaw.sh` — idempotent Bash script for fresh Ubuntu 24.04. Installs Rust toolchain (if building from source) or downloads pre-built binary.
- **Acceptance Criteria**:
  - [ ] `curl -fsSL .../install-zeroclaw.sh | bash` succeeds on fresh Ubuntu 24.04
  - [ ] Idempotent — running twice produces same result
  - [ ] `shellcheck` clean
  - [ ] Pre-built binary path works without Rust toolchain

### Issue #8: ZeroClaw entrypoint and config templates
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `zeroclaw/entrypoint.sh` that translates unified `.env` vars to ZeroClaw's `config.toml` format. Create config templates in `zeroclaw/config/`.
- **Acceptance Criteria**:
  - [ ] Entrypoint reads `.env` and generates valid `config.toml`
  - [ ] Credential resolution chain: explicit key > provider env > fallback
  - [ ] Config template includes all 22+ provider env vars
  - [ ] `shellcheck` clean

### Issue #9: provision-base.sh
- **Labels**: `P0`, `milestone:M1`, `role:infra`, `wave:3`
- **Assignee**: INFRA
- **Description**: Create `shared/provision-base.sh` — common Ubuntu 24.04 base provisioning (apt update, curl, git, build-essential, etc.) shared by all Vagrantfiles and install scripts.
- **Acceptance Criteria**:
  - [ ] Installs all common dependencies
  - [ ] Idempotent
  - [ ] `shellcheck` clean
  - [ ] Works on Ubuntu 24.04 and Debian 12

### Issue #10: docker-compose.yml (initial)
- **Labels**: `P0`, `milestone:M1`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `docker-compose.yml` with zeroclaw service profile. Env-file-based config. Extensible for additional agents.
- **Acceptance Criteria**:
  - [ ] `docker compose --profile zeroclaw up` starts agent
  - [ ] Env loaded from `.env`
  - [ ] Health check defined
  - [ ] Profile-based — does not start agents unless profile selected

---

## Milestone M2 — NanoClaw + PicoClaw

### Issue #11: NanoClaw full provisioning
- **Labels**: `P0`, `milestone:M2`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create all NanoClaw provisioning files: Vagrantfile, Dockerfile (with DooD for Docker-in-Docker), install script, entrypoint (sed/envsubst injection), config templates.
- **Acceptance Criteria**:
  - [ ] `./claw.sh nanoclaw docker` starts agent
  - [ ] `vagrant up` in `nanoclaw/` provisions VM
  - [ ] sed/envsubst strategy handles no-config architecture (R01 mitigation)
  - [ ] Docker-outside-of-Docker (DooD) approach documented
  - [ ] All channels supported: Telegram, Discord, WhatsApp, Slack
  - [ ] `shellcheck` + `hadolint` clean

### Issue #12: PicoClaw full provisioning
- **Labels**: `P0`, `milestone:M2`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create all PicoClaw provisioning files: Vagrantfile, Dockerfile (minimal, Go binary), install script, entrypoint, config templates. Reference PicoClaw's official docker-compose.
- **Acceptance Criteria**:
  - [ ] `./claw.sh picoclaw docker` starts agent
  - [ ] `vagrant up` in `picoclaw/` provisions VM
  - [ ] Final Docker image < 50 MB (Go binary + minimal runtime)
  - [ ] Agent runs on < 30 MB RAM
  - [ ] `picoclaw onboard` equivalent automated
  - [ ] `shellcheck` + `hadolint` clean

### Issue #13: docker-compose.yml update (nanoclaw + picoclaw profiles)
- **Labels**: `P0`, `milestone:M2`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Add nanoclaw and picoclaw service profiles to `docker-compose.yml`.
- **Acceptance Criteria**:
  - [ ] `docker compose --profile nanoclaw up` works
  - [ ] `docker compose --profile picoclaw up` works
  - [ ] Profiles are independent — selecting one does not start others

---

## Milestone M3 — OpenClaw + Multi-Agent

### Issue #14: OpenClaw full provisioning
- **Labels**: `P0`, `milestone:M3`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create all OpenClaw provisioning files. Node.js 22, pnpm, multi-stage Dockerfile. Handle ~1.52 GB RAM requirement.
- **Acceptance Criteria**:
  - [ ] `./claw.sh openclaw docker` starts agent
  - [ ] `vagrant up` in `openclaw/` provisions VM
  - [ ] `openclaw onboard --install-daemon` equivalent automated
  - [ ] `openclaw doctor` passes
  - [ ] Memory limits set in docker-compose (R04 mitigation)
  - [ ] `shellcheck` + `hadolint` clean

### Issue #15: Multi-agent docker-compose profiles
- **Labels**: `P1`, `milestone:M3`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Finalize docker-compose.yml with all 4 agent profiles. Allow running multiple agents simultaneously.
- **Acceptance Criteria**:
  - [ ] `docker compose --profile zeroclaw --profile picoclaw up` runs both agents
  - [ ] Different ports per agent, no conflicts
  - [ ] Memory limits prevent OOM (R04)
  - [ ] Warning logged if host RAM < 8 GB for multi-agent

### Issue #16: Teardown scripts
- **Labels**: `P1`, `milestone:M3`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Implement `./claw.sh <agent> destroy` to cleanly remove VMs, containers, volumes, configs.
- **Acceptance Criteria**:
  - [ ] `./claw.sh zeroclaw destroy` removes Docker containers, volumes, images
  - [ ] Vagrant teardown removes VM
  - [ ] Generated configs cleaned up
  - [ ] `docker ps` / `vagrant status` shows no remnants

### Issue #17: Unified health check script
- **Labels**: `P1`, `milestone:M3`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Create `shared/healthcheck.sh` that runs the appropriate health check per agent.
- **Acceptance Criteria**:
  - [ ] Runs `zeroclaw doctor`, `openclaw doctor`, `picoclaw agent -m "ping"` as appropriate
  - [ ] Structured pass/fail output per agent
  - [ ] Exit code 0 if all pass, non-zero otherwise
  - [ ] Works inside Docker and Vagrant

---

## Milestone M4 — Assessment Pipeline

### Issue #18: Assessment JSON schema and validator
- **Labels**: `P0`, `milestone:M4`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `assessment/schema/assessment-schema.json` (JSON Schema) and `assessment/validate.py`. Schema covers all 8 sections from the intake form.
- **Acceptance Criteria**:
  - [ ] Schema validates against `client-intake-form.json` structure
  - [ ] `./claw.sh validate --assessment` returns clear errors for missing/invalid fields
  - [ ] `ruff check` clean
  - [ ] Schema includes `description` and `examples` for all properties

### Issue #19: Platform/model/skills resolver
- **Labels**: `P0`, `milestone:M4`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `assessment/resolve.py` implementing the weighted scoring algorithm for platform selection, model selection, skills mapping, and compliance flags.
- **Acceptance Criteria**:
  - [ ] All 15 needs-mapping-matrix entries produce correct platform + model + skills
  - [ ] Budget-aware model selection (DeepSeek for $0, Opus for complex)
  - [ ] Compliance flags (GDPR, HIPAA) detected and surfaced
  - [ ] Automated test for all 15 matrix entries

### Issue #20: Env and config generators
- **Labels**: `P0`, `milestone:M4`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `assessment/generate_env.py` (assessment to `.env`) and `assessment/generate_config.py` (assessment to agent-specific config: TOML, JSON5, JSON, or source patches).
- **Acceptance Criteria**:
  - [ ] Generated `.env` is valid and complete for the selected agent
  - [ ] Config generator produces correct format per agent (ZeroClaw: TOML, PicoClaw: JSON, OpenClaw: JSON5, NanoClaw: source patches)
  - [ ] Works offline

### Issue #21: claw.sh deploy --assessment integration
- **Labels**: `P0`, `milestone:M4`, `role:be`, `role:devops`, `wave:3`
- **Assignee**: BE + DEVOPS
- **Description**: Wire the assessment pipeline into `claw.sh`: validate -> resolve -> generate_env -> generate_config -> install_skills -> deploy.
- **Acceptance Criteria**:
  - [ ] `./claw.sh deploy --assessment example-realstate.json` selects OpenClaw + Claude Sonnet 4.6 + whatsapp-business skills + starts agent
  - [ ] `./claw.sh deploy --assessment example-iot.json` selects PicoClaw + DeepSeek
  - [ ] `./claw.sh deploy --assessment example-devsecops.json` selects NanoClaw + Claude Sonnet 4.6

### Issue #22: Skills auto-installer
- **Labels**: `P1`, `milestone:M4`, `role:infra`, `wave:3`
- **Assignee**: INFRA
- **Description**: Create `shared/skills-installer.sh` that maps assessment use cases to skills catalog entries and installs them.
- **Acceptance Criteria**:
  - [ ] Maps assessment use_cases to skills-catalog.json entries
  - [ ] Filters by platform compatibility
  - [ ] Installs skills correctly for each agent platform
  - [ ] Network-only operation (documented as requiring internet)

### Issue #23: Example assessments and git submodule
- **Labels**: `P0`, `milestone:M4`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Add `claw-client-assessment` as git submodule. Create 3 example assessment files and a client template.
- **Acceptance Criteria**:
  - [ ] Git submodule correctly references `Amenthyx/claw-client-assessment`
  - [ ] 3 example files: real estate, IoT, DevSecOps
  - [ ] `client-assessment.example.json` template in repo root
  - [ ] All examples pass validation

---

## Milestone M5a — Dataset Collection & Adapter Scaffolding

### Issue #24: Dataset download and validation scripts
- **Labels**: `P1`, `milestone:M5a`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `finetune/download_datasets.py` (fetch, sample to <=10K rows, convert to JSONL) and `finetune/validate_datasets.py` (check rows, schema, license, total size).
- **Acceptance Criteria**:
  - [ ] Download script handles HF, Kaggle, direct URL sources
  - [ ] Automatic sampling/truncation to 10K rows
  - [ ] Validation checks: rows <= 10K, metadata.json present, license in allowed list
  - [ ] `ruff check` clean

### Issue #25: 50 use-case datasets collection
- **Labels**: `P1`, `milestone:M5a`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Download, curate, and commit all 50 datasets to `finetune/datasets/`. Each folder: `data.jsonl` (or `.csv`/`.parquet`) + `metadata.json`.
- **Acceptance Criteria**:
  - [ ] All 50 folders present under `finetune/datasets/`
  - [ ] Every dataset <= 10,000 rows
  - [ ] Every `metadata.json` has: use_case_id, source_url, license, sampled_rows, columns, language, domain_tags
  - [ ] All licenses are free/open (Apache 2.0, MIT, CC-BY, CC-BY-SA, CC0, public domain)
  - [ ] Total size < 500 MB
  - [ ] All files tracked in git (not gitignored)

### Issue #26: 50 pre-built adapter config bundles
- **Labels**: `P1`, `milestone:M5a`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create adapter configs for all 50 use cases under `finetune/adapters/`. Each folder: `adapter_config.json`, `system_prompt.txt`, `training_config.json`.
- **Acceptance Criteria**:
  - [ ] All 50 folders present under `finetune/adapters/`
  - [ ] `adapter_config.json`: LoRA rank, target modules, base model, base_model_version
  - [ ] `system_prompt.txt`: enriched system prompt with industry context
  - [ ] `training_config.json`: epochs, lr, batch size, VRAM estimate
  - [ ] Adapter configs reference correct dataset path
  - [ ] `--dry-run` validates all 50

### Issue #27: claw.sh datasets commands
- **Labels**: `P1`, `milestone:M5a`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Add dataset management commands to `claw.sh`: `--list`, `--validate`, `--download-all`, `--stats`.
- **Acceptance Criteria**:
  - [ ] `./claw.sh datasets --list` prints all 50 with status
  - [ ] `./claw.sh datasets --validate` confirms all present and valid
  - [ ] `./claw.sh datasets --download-all` triggers download script
  - [ ] `./claw.sh datasets --stats` shows total rows, size, format breakdown

### Issue #28: Dataset and adapter catalog READMEs
- **Labels**: `P1`, `milestone:M5a`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `finetune/datasets/README.md` (catalog of all 50 datasets with sources, licenses, row counts) and `finetune/adapters/README.md` (adapter catalog with training instructions).
- **Acceptance Criteria**:
  - [ ] Dataset README lists all 50 with source URLs and licenses
  - [ ] Adapter README includes training instructions and hyperparameter guidance
  - [ ] Both include quick-start examples

---

## Milestone M5b — LoRA/QLoRA Fine-Tuning Pipeline

### Issue #29: Fine-tuning Docker and requirements
- **Labels**: `P1`, `milestone:M5b`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `finetune/Dockerfile.finetune` (GPU-enabled container with CUDA) and `finetune/requirements.txt` (torch, transformers, peft, bitsandbytes, datasets).
- **Acceptance Criteria**:
  - [ ] Dockerfile builds successfully with CUDA support
  - [ ] All dependencies install without conflicts
  - [ ] Container can access GPU (nvidia-docker runtime)

### Issue #30: Dataset generator and training scripts
- **Labels**: `P1`, `milestone:M5b`, `role:be`, `wave:3`
- **Assignee**: BE
- **Description**: Create `finetune/dataset_generator.py` (assessment to training dataset), `finetune/train_lora.py`, `finetune/train_qlora.py`, `finetune/merge_adapter.py`.
- **Acceptance Criteria**:
  - [ ] Dataset generator produces valid JSONL in chat format
  - [ ] LoRA training completes on small test set (< 500 rows, < 30 min)
  - [ ] QLoRA training completes on 16 GB VRAM (< 15 min on test set)
  - [ ] Merge script produces standalone model (optional)
  - [ ] TensorBoard logs generated to `finetune/runs/`
  - [ ] `ruff check` clean

### Issue #31: claw.sh finetune commands
- **Labels**: `P1`, `milestone:M5b`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Add fine-tuning commands to `claw.sh`: `--assessment`, `--adapter <use-case>`, `--adapter <use-case> --dry-run`.
- **Acceptance Criteria**:
  - [ ] `./claw.sh finetune --assessment client-assessment.json` triggers full pipeline
  - [ ] `./claw.sh finetune --adapter customer-support` trains from pre-built config
  - [ ] `--dry-run` validates without training

### Issue #32: Adapter loading in agent entrypoints
- **Labels**: `P1`, `milestone:M5b`, `role:devops`, `wave:3`
- **Assignee**: DEVOPS
- **Description**: Update all 4 agent entrypoints to detect and load LoRA adapters at startup.
- **Acceptance Criteria**:
  - [ ] ZeroClaw: custom model config in TOML pointing to local adapter
  - [ ] OpenClaw: model override in JSON5 config with adapter path
  - [ ] PicoClaw: model_list entry with local adapter endpoint
  - [ ] NanoClaw: injected into CLAUDE.md system prompt + skills
  - [ ] System prompt enrichment for API-only models

---

## Milestone M6 — CI/CD + Polish + Docs

### Issue #33: GitHub Actions CI pipeline
- **Labels**: `P0`, `milestone:M6`, `role:infra`, `wave:4`
- **Assignee**: INFRA
- **Description**: Create `.github/workflows/ci.yml` with: matrix Docker builds (4 agents), assessment validation, dataset validation, linting, security scanning.
- **Acceptance Criteria**:
  - [ ] Matrix build: 4 agents x Docker
  - [ ] Assessment validation: all example assessments pass
  - [ ] Dataset validation: all 50 datasets present and valid
  - [ ] Linting: shellcheck, hadolint, ruff all pass
  - [ ] Security: no secrets or PII in tracked files
  - [ ] Branch protection: require passing CI

### Issue #34: Pre-commit hooks
- **Labels**: `P0`, `milestone:M6`, `role:infra`, `wave:4`
- **Assignee**: INFRA
- **Description**: Create `.pre-commit-config.yaml` with shellcheck, hadolint, ruff, PII pattern detection.
- **Acceptance Criteria**:
  - [ ] Catches shell script issues before commit
  - [ ] Catches Dockerfile issues before commit
  - [ ] Catches Python linting issues before commit
  - [ ] Rejects `client-assessment*.json` files (except examples)

### Issue #35: README and documentation
- **Labels**: `P0`, `milestone:M6`, `role:pm`, `wave:5`
- **Assignee**: PM
- **Description**: Comprehensive README covering: quickstart, per-agent setup, assessment workflow, `.env` configuration, fine-tuning guide, troubleshooting. Plus `.ai/context_base.md`.
- **Acceptance Criteria**:
  - [ ] Quickstart: clone to running agent in < 5 min (Docker)
  - [ ] Per-agent section for all 4 agents
  - [ ] 3 assessment walkthroughs (real estate, IoT, DevSecOps)
  - [ ] Fine-tuning guide with cost estimates
  - [ ] Troubleshooting section
  - [ ] `.ai/context_base.md` present

---

## Issue Count Summary

| Milestone | Issue Count | P0 | P1 |
|-----------|-----------|-----|-----|
| M1 | 10 | 10 | 0 |
| M2 | 3 | 3 | 0 |
| M3 | 4 | 1 | 3 |
| M4 | 6 | 5 | 1 |
| M5a | 5 | 0 | 5 |
| M5b | 4 | 0 | 4 |
| M6 | 3 | 3 | 0 |
| **Total** | **35** | **22** | **13** |

---

*GitHub Issues Tracking v1.0 — Claw Agents Provisioner — Amenthyx AI Teams v3.0*
