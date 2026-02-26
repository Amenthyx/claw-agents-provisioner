# Project Charter — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: APPROVED

---

## 1. Project Identity

**Project Name**: Claw Agents Provisioner

**One-Line Vision**: One-command fresh installation of any Claw AI agent (ZeroClaw, NanoClaw, PicoClaw, OpenClaw) on a clean machine via Vagrant or Docker, auto-configured from a client assessment and enhanced with LoRA/QLoRA fine-tuned agent personalities.

**Repository**: `Amenthyx/claw-agents-provisioner`

**Assessment Toolkit**: `Amenthyx/claw-client-assessment` (existing — intake forms, needs matrix, benchmarks, skills catalog, service packages)

**Project Type**: Greenfield

---

## 2. Problem Statement

Each Claw agent has different languages (Rust, TypeScript, Go), different runtimes (Node.js 22, Rust toolchain, Go 1.21+), different config formats (TOML, JSON5, JSON, code-driven), and different setup flows (`onboard`, `/setup`, manual). After installation, agents are generic — they don't know the client's industry, use cases, communication style, or operational needs. A consultant who has just completed a client needs assessment (`Amenthyx/claw-client-assessment`) has no automated path from "assessment results" to "personalized, running agent." The gap between assessment and deployment wastes hours of manual configuration and misses the opportunity to fine-tune agent behavior to the client's specific domain.

---

## 3. Desired Outcome

A single repository where:
1. A consultant fills out the client assessment (intake form JSON) during onboarding
2. Running `./claw.sh deploy --assessment client-assessment.json` automatically selects the right platform (via needs-mapping-matrix), configures it from `.env`, installs skills from the skills catalog, and optionally triggers LoRA/QLoRA fine-tuning to create a domain-specialized agent personality
3. The client gets a running, personalized AI agent — tailored to their industry, use cases, and communication preferences — in under 15 minutes

---

## 4. Scope Boundaries

### In Scope (v1.0)

| Area | Deliverables |
|------|--------------|
| **Infrastructure** | Vagrantfile per agent (4), Dockerfile + docker-compose per agent (4), install scripts (4), unified `.env.template`, unified `claw.sh` launcher, teardown scripts |
| **Assessment Pipeline** | Assessment JSON schema + validator, needs-mapping-matrix resolver, env/config generators, skills auto-installer, `claw.sh deploy --assessment` end-to-end |
| **Fine-Tuning** | LoRA/QLoRA training pipeline, dataset generator, 50 use-case datasets (committed in repo, <=10K rows each), 50 pre-built adapter configs, adapter loading in agent entrypoints |
| **Testing & CI** | Health checks / smoke tests, shellcheck / hadolint / ruff linting, GitHub Actions CI pipeline, dataset validation |
| **Documentation** | README, `.ai/context_base.md`, example assessment walkthroughs |

### Out of Scope (v1.0)

| Area | Reason |
|------|--------|
| Foundation model training or pre-training | We only train LoRA/QLoRA adapters on top of existing models |
| Kubernetes / Helm charts / cloud-native orchestration | Single-machine scope only |
| GUI / web dashboard for agent management | CLI and config files only |
| Agent source code modifications or patches | We install upstream releases as-is; adapters loaded at runtime |
| Production hardening (TLS, reverse proxy, rate limiting) | Dev/test scope only |
| Custom LLM API hosting | Agents connect to external APIs |
| ARM64 / Apple Silicon verified support | Deferred to v1.1 |
| Ansible playbook alternatives | Deferred to v1.2 |
| Assessment web form (P2) | Deferred to v1.3 |
| Pre-built adapter marketplace with trained weights | Deferred to v2.0 |

---

## 5. Team Roster & Role Assignments

### Active Roles

| Role | Abbreviation | Responsibility in THIS Project |
|------|-------------|-------------------------------|
| **Project Manager** | PM | Planning artifacts, milestone tracking, kanban, risk register, GitHub issue templates, evidence manifests, team coordination |
| **Backend Engineer** | BE | Python assessment pipeline (`resolve.py`, `generate_env.py`, `generate_config.py`, `validate.py`), fine-tuning pipeline (`dataset_generator.py`, `train_lora.py`, `train_qlora.py`, `merge_adapter.py`), dataset collection scripts (`download_datasets.py`, `validate_datasets.py`), 50 use-case dataset curation |
| **DevOps Engineer** | DEVOPS | Dockerfiles (4 agents + finetune), Vagrantfiles (4 agents), install scripts (4 agents), docker-compose.yml with profiles, `claw.sh` unified launcher, entrypoint scripts, health check scripts, teardown scripts |
| **Infrastructure Engineer** | INFRA | `.env.template` (unified, documented), env variable mapping strategy, provisioning scripts (`provision-base.sh`), skills installer (`skills-installer.sh`), `.gitignore` / `.gitattributes`, security scanning, CI/CD pipeline (GitHub Actions), pre-commit hooks |

### Inactive Roles (Not Applicable for v1.0)

| Role | Reason |
|------|--------|
| **Frontend Engineer** (FE) | No web UI in v1.0; P2 assessment web form is deferred to v1.3 |
| **Mobile Engineer** (MOB) | No mobile component; agents are server-side services |

---

## 6. Target Audience

| Persona | Role | Pain Points | Goals | Tech Savvy |
|---------|------|-------------|-------|------------|
| Marco | Amenthyx consultant | Completed client assessment, now must manually pick platform, configure APIs, install skills, customize personality — takes 4-8 hours per client | Run one command with the assessment JSON, get a personalized agent deployed in 15 min | High |
| Lucia | Real estate agency owner (Private package client) | Uses WhatsApp for leads, needs auto-replies and property matching; can't configure technical tools; budget: < $25/month API costs | Fill in a simple form, get a WhatsApp bot that knows real estate and speaks her language | Low (2/5) |
| Kai | SaaS startup CTO (Enterprise package client) | Needs Slack + GitHub automation for 20-person dev team; wants container isolation (NanoClaw); needs GDPR compliance; will self-host on AWS | Get a fully provisioned, security-hardened agent with code review and CI/CD skills tuned to their stack | High (5/5) |
| Priya | IoT engineer (Budget client) | Runs sensors on Raspberry Pi fleet; needs PicoClaw for edge monitoring + alerting; budget: $0 API (DeepSeek free tier) | `curl \| bash` on a Pi, agent monitors sensors and sends Telegram alerts | High (4/5) |

---

## 7. Technical Constraints

### Hard Constraints (Non-Negotiable)
- `.env` files and client assessment JSONs MUST be `.gitignore`d — zero secrets or PII in repo, ever
- Each agent MUST be installable independently — no cross-agent dependencies
- Install scripts MUST be idempotent — running twice produces the same result
- Base OS for Vagrant: Ubuntu 24.04 LTS (`ubuntu/noble64`)
- Docker base images: official minimal images (rust:slim, node:22-slim, golang:1.21-alpine, ubuntu:24.04)
- LoRA adapters MUST be loadable at runtime — no model weight modification required
- All 50 use-case datasets MUST be committed inside the GitHub repository (`finetune/datasets/`) — NOT gitignored, NOT downloaded at runtime
- Assessment pipeline MUST work offline (except skills installation)

### Soft Constraints (Preferred)
- Prefer multi-stage Docker builds to minimize final image size
- Prefer shell scripts over Python/Ruby for provisioning (fewer host dependencies)
- Prefer `docker compose` profiles over separate compose files per agent
- Prefer QLoRA over full LoRA when VRAM < 24 GB
- Prefer Hugging Face PEFT library for adapter training

---

## 8. Budget

| Category | Budget | Notes |
|----------|--------|-------|
| Infrastructure | $0 | Local VMs + Docker; CI uses GitHub Actions free tier |
| Fine-tuning compute | ~$5-20 per adapter | RunPod/Lambda (1-2 hrs A100); $0 if using local GPU |
| Third-party APIs | $0 (repo-side) | User-provided keys only; free tiers available for all LLM providers |
| Domains/SSL | N/A | No web hosting |

---

## 9. Success Criteria (Definition of Done)

A consultant can:
1. Clone the repo
2. Fill in `client-assessment.json` from their intake session
3. Fill `.env` with API keys
4. Run `./claw.sh deploy --assessment client-assessment.json`

The system auto-selects the correct platform, installs the right skills, configures everything, and starts a personalized agent. The agent responds to a test message with domain-appropriate behavior.

### KPIs

| Metric | Target |
|--------|--------|
| Time to first agent running (Docker, no assessment) | < 5 min from `git clone` |
| Time to first agent running (Vagrant, no assessment) | < 15 min from `git clone` |
| Time from assessment to running personalized agent | < 15 min (excl. fine-tuning) |
| Assessment-to-platform accuracy | 100% match with needs-mapping-matrix |
| Manual steps required (assessment flow) | 3 (clone + fill assessment + fill `.env`) |
| Agent coverage | 4/4 agents |
| Pre-built adapter coverage | 50/50 use cases |
| Dataset completeness | 50/50 datasets present and validated |

---

## 10. Approvals

| Role | Name | Status | Date |
|------|------|--------|------|
| PM | Project Manager | APPROVED | 2026-02-26 |
| BE | Backend Engineer | PENDING | — |
| DEVOPS | DevOps Engineer | PENDING | — |
| INFRA | Infrastructure Engineer | PENDING | — |

---

*Project Charter v1.0 — Claw Agents Provisioner — Amenthyx AI Teams v3.0*
