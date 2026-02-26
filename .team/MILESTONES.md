# Milestone Plan — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)

---

## Overview

| # | Milestone | Target | Owner(s) | Status |
|---|-----------|--------|----------|--------|
| M0 | Planning & Architecture | Week 0 | PM | In Progress |
| M1 | Foundation + ZeroClaw | Week 1 | DEVOPS, INFRA | Backlog |
| M2 | NanoClaw + PicoClaw | Week 2 | DEVOPS, INFRA | Backlog |
| M3 | OpenClaw + Multi-Agent | Week 3 | DEVOPS, INFRA | Backlog |
| M4 | Assessment Pipeline | Week 4 | BE, INFRA | Backlog |
| M5a | Dataset Collection & Adapter Scaffolding | Week 5 | BE | Backlog |
| M5b | LoRA/QLoRA Fine-Tuning Pipeline | Week 6 | BE | Backlog |
| M6 | CI/CD + Polish + Docs | Week 7 | INFRA, DEVOPS, BE, PM | Backlog |

---

## M0 — Planning & Architecture

**Target**: Week 0 (2026-02-26)
**Owner**: PM
**Wave**: 1 (Planning)

### Deliverables

| # | Deliverable | File / Artifact |
|---|-------------|-----------------|
| 1 | Project Charter | `.team/PROJECT_CHARTER.md` |
| 2 | Milestone Plan | `.team/MILESTONES.md` |
| 3 | Kanban Board | `.team/KANBAN.md` |
| 4 | Timeline | `.team/TIMELINE.md` |
| 5 | Risk Register | `.team/RISK_REGISTER.md` |
| 6 | GitHub Issues Template | `.team/GITHUB_ISSUES.md` |
| 7 | Commit Log Template | `.team/COMMIT_LOG.md` |
| 8 | Team Status | `.team/TEAM_STATUS.md` |
| 9 | PM Evidence Manifest | `.team/evidence/manifests/PM_manifest.md` |

### Success Criteria
- [ ] All 9 planning artifacts written to `.team/`
- [ ] Every P0 and P1 feature from the strategy appears as a kanban card
- [ ] All 50 use-case datasets and 50 adapter configs are listed as explicit deliverables
- [ ] Risk register covers all 10 known risks from strategy Section 11
- [ ] Timeline maps dependencies between milestones

---

## M1 — Foundation + ZeroClaw

**Target**: Week 1
**Owner**: DEVOPS (primary), INFRA (supporting)
**Wave**: 3 (Engineering)

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | Repository structure scaffold | Full directory tree per strategy Section 4 | P0 |
| 2 | Unified `.env.template` | `.env.template` (all agents + fine-tuning sections) | P0 |
| 3 | `.gitignore` + `.gitattributes` | Root config files | P0 |
| 4 | `claw.sh` unified launcher | `claw.sh` (routes to correct provisioning method) | P0 |
| 5 | ZeroClaw Vagrantfile | `zeroclaw/Vagrantfile` | P0 |
| 6 | ZeroClaw Dockerfile | `zeroclaw/Dockerfile` | P0 |
| 7 | ZeroClaw install script | `zeroclaw/install-zeroclaw.sh` | P0 |
| 8 | ZeroClaw entrypoint | `zeroclaw/entrypoint.sh` | P0 |
| 9 | ZeroClaw config templates | `zeroclaw/config/` | P0 |
| 10 | `provision-base.sh` | `shared/provision-base.sh` | P0 |
| 11 | `docker-compose.yml` (initial, zeroclaw profile) | `docker-compose.yml` | P0 |

### Success Criteria
- [ ] `./claw.sh zeroclaw docker` starts ZeroClaw agent successfully
- [ ] `vagrant up` in `zeroclaw/` provisions a clean Ubuntu 24.04 VM
- [ ] `.env.template` is complete, sectioned, and documented for all agents
- [ ] `claw.sh` accepts `<agent> [vagrant|docker]` and routes correctly
- [ ] Health check (`zeroclaw doctor`) passes after provisioning
- [ ] `shellcheck` clean on all `.sh` files
- [ ] `hadolint` clean on ZeroClaw Dockerfile

---

## M2 — NanoClaw + PicoClaw

**Target**: Week 2
**Owner**: DEVOPS (primary), INFRA (supporting)
**Wave**: 3 (Engineering)
**Depends on**: M1 (foundation, shared scripts, `.env.template`)

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | NanoClaw Vagrantfile | `nanoclaw/Vagrantfile` | P0 |
| 2 | NanoClaw Dockerfile | `nanoclaw/Dockerfile` | P0 |
| 3 | NanoClaw install script | `nanoclaw/install-nanoclaw.sh` | P0 |
| 4 | NanoClaw entrypoint | `nanoclaw/entrypoint.sh` (sed/envsubst injection) | P0 |
| 5 | NanoClaw config templates | `nanoclaw/config/` | P0 |
| 6 | PicoClaw Vagrantfile | `picoclaw/Vagrantfile` | P0 |
| 7 | PicoClaw Dockerfile | `picoclaw/Dockerfile` | P0 |
| 8 | PicoClaw install script | `picoclaw/install-picoclaw.sh` | P0 |
| 9 | PicoClaw entrypoint | `picoclaw/entrypoint.sh` | P0 |
| 10 | PicoClaw config templates | `picoclaw/config/` | P0 |
| 11 | `docker-compose.yml` updated (nanoclaw + picoclaw profiles) | `docker-compose.yml` | P0 |

### Success Criteria
- [ ] Both agents provisionable via Docker (`./claw.sh nanoclaw docker`, `./claw.sh picoclaw docker`)
- [ ] Both agents provisionable via Vagrant
- [ ] Health checks pass for both agents
- [ ] NanoClaw's no-config-file challenge handled via `sed`/`envsubst` wrapper
- [ ] PicoClaw runs on minimal resources (< 30 MB RAM)
- [ ] `shellcheck` + `hadolint` clean

---

## M3 — OpenClaw + Multi-Agent

**Target**: Week 3
**Owner**: DEVOPS (primary), INFRA (supporting)
**Wave**: 3 (Engineering)
**Depends on**: M2

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | OpenClaw Vagrantfile | `openclaw/Vagrantfile` | P0 |
| 2 | OpenClaw Dockerfile | `openclaw/Dockerfile` | P0 |
| 3 | OpenClaw install script | `openclaw/install-openclaw.sh` | P0 |
| 4 | OpenClaw entrypoint | `openclaw/entrypoint.sh` | P0 |
| 5 | OpenClaw config templates | `openclaw/config/` | P0 |
| 6 | Multi-agent docker-compose profiles | `docker-compose.yml` (final, all 4 agents) | P1 |
| 7 | Teardown scripts | `claw.sh <agent> destroy` functionality | P1 |
| 8 | Health check script (unified) | `shared/healthcheck.sh` | P1 |

### Success Criteria
- [ ] All 4 agents work via Docker and Vagrant
- [ ] Can run 2+ agents simultaneously via `docker compose --profile zeroclaw --profile picoclaw up`
- [ ] `./claw.sh <agent> destroy` cleanly removes VMs, containers, volumes
- [ ] `shared/healthcheck.sh` outputs structured pass/fail for all 4 agents
- [ ] OpenClaw memory limits set in docker-compose (8 GB+ host RAM warning documented)
- [ ] `shellcheck` + `hadolint` clean for all files

---

## M4 — Assessment Pipeline

**Target**: Week 4
**Owner**: BE (primary), INFRA (supporting)
**Wave**: 3 (Engineering)
**Depends on**: M3 (all agents must be provisionable)

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | Assessment JSON schema | `assessment/schema/assessment-schema.json` | P0 |
| 2 | Schema validator | `assessment/validate.py` | P0 |
| 3 | Platform/model/skills resolver | `assessment/resolve.py` | P0 |
| 4 | Env generator | `assessment/generate_env.py` | P0 |
| 5 | Agent config generator | `assessment/generate_config.py` | P0 |
| 6 | `claw.sh deploy --assessment` integration | `claw.sh` updated | P0 |
| 7 | `claw.sh validate --assessment` command | `claw.sh` updated | P0 |
| 8 | Skills auto-installer | `shared/skills-installer.sh` | P1 |
| 9 | Git submodule for claw-client-assessment | `assessment/claw-client-assessment/` | P0 |
| 10 | Example assessment: Real Estate | `assessment/examples/example-realstate.json` | P0 |
| 11 | Example assessment: IoT / RPi | `assessment/examples/example-iot.json` | P0 |
| 12 | Example assessment: DevSecOps | `assessment/examples/example-devsecops.json` | P0 |
| 13 | Client assessment example template | `client-assessment.example.json` | P0 |

### Success Criteria
- [ ] `./claw.sh validate --assessment example-realstate.json` passes
- [ ] `./claw.sh deploy --assessment example-realstate.json` selects OpenClaw, installs `whatsapp-business` + `lead-qualifier` + `auto-follow-up`, starts agent
- [ ] `./claw.sh deploy --assessment example-iot.json` selects PicoClaw with DeepSeek
- [ ] `./claw.sh deploy --assessment example-devsecops.json` selects NanoClaw with Claude Sonnet 4.6
- [ ] All 15 needs-mapping-matrix entries produce valid configs (automated test)
- [ ] Assessment pipeline works offline (except skills installation)
- [ ] `ruff check` clean on all Python files
- [ ] No client PII in tracked files (CI scan)

---

## M5a — Dataset Collection & Adapter Scaffolding

**Target**: Week 5
**Owner**: BE
**Wave**: 3 (Engineering)
**Depends on**: M1 (repo structure)

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | Dataset download script | `finetune/download_datasets.py` | P1 |
| 2 | Dataset validation script | `finetune/validate_datasets.py` | P1 |
| 3 | 50 use-case datasets (<=10K rows each) | `finetune/datasets/01-customer-support/` through `finetune/datasets/50-personal-finance/` | P1 |
| 4 | 50 metadata.json files | One per dataset folder | P1 |
| 5 | Dataset catalog README | `finetune/datasets/README.md` | P1 |
| 6 | 50 adapter config bundles | `finetune/adapters/01-customer-support/` through `finetune/adapters/50-personal-finance/` | P1 |
| 7 | Adapter catalog README | `finetune/adapters/README.md` | P1 |
| 8 | `claw.sh datasets --list` command | `claw.sh` updated | P1 |
| 9 | `claw.sh datasets --validate` command | `claw.sh` updated | P1 |
| 10 | `claw.sh datasets --download-all` command | `claw.sh` updated | P1 |
| 11 | `claw.sh datasets --stats` command | `claw.sh` updated | P1 |

### Dataset List (All 50)

| # | Use Case | Max Rows | Source Type |
|---|----------|----------|-------------|
| 01 | Customer Support & Helpdesk | 10,000 | HF |
| 02 | Real Estate Agent | 10,000 | Kaggle |
| 03 | E-Commerce Assistant | 10,000 | HF |
| 04 | Healthcare Triage | 10,000 | NLM/NIH |
| 05 | Legal Document Review | 10,000 | HF |
| 06 | Personal Finance Advisor | 10,000 | HF |
| 07 | Code Review & Dev Workflow | 10,000 | HF |
| 08 | Email Management & Drafting | 10,000 | Public (Enron) |
| 09 | Calendar & Scheduling | 10,000 | Synthetic |
| 10 | Meeting Summarization | 10,000 | AMI/ICSI |
| 11 | Sales & CRM Assistant | 10,000 | Kaggle |
| 12 | HR & Recruitment | 10,000 | Kaggle |
| 13 | IT Helpdesk & Troubleshooting | 10,000 | HF |
| 14 | Content Writing & Marketing | 10,000 | HF |
| 15 | Social Media Management | 10,000 | HF |
| 16 | Translation & Multilingual | 10,000 | OPUS |
| 17 | Education & Tutoring | 10,000 | HF (CC) |
| 18 | Research & Summarization | 10,000 | S2ORC |
| 19 | Data Analysis & Reporting | 10,000 | WikiSQL/Spider |
| 20 | Project Management | 10,000 | Synthetic + GH |
| 21 | Accounting & Bookkeeping | 10,000 | Kaggle |
| 22 | Insurance Claims Processing | 10,000 | Kaggle |
| 23 | Travel & Hospitality | 10,000 | HF |
| 24 | Food & Restaurant | 10,000 | Kaggle |
| 25 | Fitness & Wellness | 10,000 | Kaggle |
| 26 | Automotive & Vehicle | 10,000 | Kaggle |
| 27 | Supply Chain & Logistics | 10,000 | Synthetic + Kaggle |
| 28 | Manufacturing & QA | 10,000 | Kaggle |
| 29 | Agriculture & Farming | 10,000 | Kaggle |
| 30 | Energy & Utilities | 10,000 | Open |
| 31 | Telecommunications | 10,000 | Kaggle |
| 32 | Government & Public Services | 10,000 | Open Gov |
| 33 | Nonprofit & Fundraising | 10,000 | Synthetic + Open |
| 34 | Event Planning & Coordination | 10,000 | Synthetic |
| 35 | Cybersecurity & Threat Intel | 10,000 | NVD |
| 36 | DevOps & Infrastructure | 10,000 | StackOverflow |
| 37 | API Integration & Webhooks | 10,000 | Synthetic + Open |
| 38 | Database Administration | 10,000 | StackOverflow |
| 39 | IoT & Smart Home | 10,000 | HF/Kaggle |
| 40 | Chatbot & Conversational AI | 10,000 | DailyDialog (HF) |
| 41 | Document Processing & OCR | 10,000 | DocVQA (HF) |
| 42 | Knowledge Base & FAQ | 10,000 | HF/Kaggle |
| 43 | Compliance & Regulatory | 10,000 | Open Legal |
| 44 | Onboarding & Training | 10,000 | Synthetic |
| 45 | Sentiment Analysis & Feedback | 10,000 | HF |
| 46 | Creative Writing & Storytelling | 10,000 | Reddit (HF) |
| 47 | Music & Entertainment | 10,000 | Kaggle |
| 48 | Gaming & Virtual Worlds | 10,000 | Open Game |
| 49 | Mental Health & Counseling | 10,000 | Open (Anonymized) |
| 50 | Personal Finance & Budgeting | 10,000 | Open |

### Adapter Config Bundle (per use case)

Each of the 50 adapter folders contains:
- `adapter_config.json` — LoRA rank, target modules, base model
- `system_prompt.txt` — Enriched prompt for API-only models (Claude, GPT, DeepSeek)
- `training_config.json` — Epochs, learning rate, batch size, VRAM estimate

### Success Criteria
- [ ] All 50 `finetune/datasets/<use-case>/` folders contain `data.jsonl` (or `.csv`/`.parquet`) with <=10,000 rows
- [ ] All 50 `finetune/datasets/<use-case>/metadata.json` files present with source URL, license, row count, schema
- [ ] All 50 licenses are free/open (Apache 2.0, MIT, CC-BY, CC-BY-SA, CC0, or public domain)
- [ ] All 50 `finetune/adapters/<use-case>/` folders contain `adapter_config.json`, `system_prompt.txt`, `training_config.json`
- [ ] `./claw.sh datasets --list` prints all 50 with status
- [ ] `./claw.sh datasets --validate` passes for all 50
- [ ] Total repo size < 500 MB for all 50 datasets combined
- [ ] `git ls-files finetune/datasets/` shows all 50 dataset files tracked (not gitignored)

---

## M5b — LoRA/QLoRA Fine-Tuning Pipeline

**Target**: Week 6
**Owner**: BE
**Wave**: 3 (Engineering)
**Depends on**: M5a (datasets and adapter configs), M3 (agent entrypoints for adapter loading)

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | Fine-tuning Dockerfile | `finetune/Dockerfile.finetune` | P1 |
| 2 | Fine-tuning requirements | `finetune/requirements.txt` | P1 |
| 3 | Dataset generator (assessment-to-training-data) | `finetune/dataset_generator.py` | P1 |
| 4 | LoRA training script | `finetune/train_lora.py` | P1 |
| 5 | QLoRA training script | `finetune/train_qlora.py` | P1 |
| 6 | Adapter merge script | `finetune/merge_adapter.py` | P1 |
| 7 | `claw.sh finetune --assessment` command | `claw.sh` updated | P1 |
| 8 | `claw.sh finetune --adapter <use-case>` command | `claw.sh` updated | P1 |
| 9 | `claw.sh finetune --adapter <use-case> --dry-run` command | `claw.sh` updated | P1 |
| 10 | Adapter loading in ZeroClaw entrypoint | `zeroclaw/entrypoint.sh` updated | P1 |
| 11 | Adapter loading in NanoClaw entrypoint | `nanoclaw/entrypoint.sh` updated | P1 |
| 12 | Adapter loading in PicoClaw entrypoint | `picoclaw/entrypoint.sh` updated | P1 |
| 13 | Adapter loading in OpenClaw entrypoint | `openclaw/entrypoint.sh` updated | P1 |

### Success Criteria
- [ ] `./claw.sh finetune --adapter customer-support` produces adapter from raw dataset
- [ ] LoRA training completes on a small test set (< 500 rows) within 30 minutes on consumer GPU
- [ ] QLoRA training completes within 15 minutes on 16 GB VRAM
- [ ] Agent loads adapter at startup and shows domain-specific behavior
- [ ] TensorBoard training logs saved to `finetune/runs/`
- [ ] `--dry-run` validates adapter config without training
- [ ] `ruff check` clean on all Python files
- [ ] System prompt enrichment works for API-only models (Claude, GPT)

---

## M6 — CI/CD + Polish + Docs

**Target**: Week 7
**Owner**: INFRA (primary), DEVOPS + BE + PM (supporting)
**Wave**: 4 (QA) + 5 (Release)
**Depends on**: M1-M5b

### Deliverables

| # | Deliverable | File / Artifact | Priority |
|---|-------------|-----------------|----------|
| 1 | GitHub Actions CI pipeline | `.github/workflows/ci.yml` | P0 |
| 2 | CI: Matrix build (4 agents x Docker) | CI config | P0 |
| 3 | CI: Assessment pipeline validation | CI config | P0 |
| 4 | CI: Dataset validation (50 datasets) | CI config | P1 |
| 5 | CI: Linting (shellcheck, hadolint, ruff) | CI config | P0 |
| 6 | CI: Security scan (no secrets/PII in tracked files) | CI config | P0 |
| 7 | Pre-commit hooks config | `.pre-commit-config.yaml` | P0 |
| 8 | README | `README.md` | P0 |
| 9 | AI context file | `.ai/context_base.md` | P0 |
| 10 | Example assessment walkthrough: Real Estate | In README | P0 |
| 11 | Example assessment walkthrough: IoT | In README | P0 |
| 12 | Example assessment walkthrough: DevSecOps | In README | P0 |
| 13 | Troubleshooting guide | In README | P0 |
| 14 | Fine-tuning guide | In README | P1 |

### Success Criteria
- [ ] CI green for all Docker builds + assessment validation + dataset validation
- [ ] Pre-commit hooks catch issues before commit
- [ ] README covers: quickstart, per-agent setup, assessment workflow, `.env` configuration, fine-tuning guide, troubleshooting
- [ ] `.ai/context_base.md` present and comprehensive
- [ ] 3 end-to-end assessment walkthroughs documented
- [ ] Zero secrets or PII committed (verified by CI)
- [ ] `git log --oneline` shows atomic commits per feature

---

*Milestone Plan v1.0 — Claw Agents Provisioner — Amenthyx AI Teams v3.0*
