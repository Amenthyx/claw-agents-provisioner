# Kanban Board — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Last Updated: 2026-02-26

---

## Legend

- **Priority**: P0 = Must-Have (Launch Blocker), P1 = Should-Have (Important), P2 = Nice-to-Have
- **Owner**: PM, BE, DEVOPS, INFRA
- **Milestone**: M0-M6
- **Wave**: W1 (Planning), W2 (Research), W3 (Engineering), W4 (QA), W5 (Release)

---

## Done

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| — | (Nothing done yet) | — | — | — | — |

---

## In Review

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| — | (Nothing in review yet) | — | — | — | — |

---

## Testing

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| — | (Nothing in testing yet) | — | — | — | — |

---

## In Progress

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| PM-01 | Project Charter | P0 | PM | M0 | W1 |
| PM-02 | Milestone Plan | P0 | PM | M0 | W1 |
| PM-03 | Kanban Board | P0 | PM | M0 | W1 |
| PM-04 | Timeline | P0 | PM | M0 | W1 |
| PM-05 | Risk Register | P0 | PM | M0 | W1 |
| PM-06 | GitHub Issues Template | P0 | PM | M0 | W1 |
| PM-07 | Commit Log Template | P0 | PM | M0 | W1 |
| PM-08 | Team Status | P0 | PM | M0 | W1 |
| PM-09 | PM Evidence Manifest | P0 | PM | M0 | W1 |

---

## Sprint Ready

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| — | (Nothing sprint ready yet) | — | — | — | — |

---

## Backlog

### Wave 3 — Engineering: M1 (Foundation + ZeroClaw)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| INFRA-01 | Repository structure scaffold (full directory tree) | P0 | INFRA | M1 | W3 |
| INFRA-02 | Unified `.env.template` (all agents + fine-tuning sections) | P0 | INFRA | M1 | W3 |
| INFRA-03 | `.gitignore` + `.gitattributes` | P0 | INFRA | M1 | W3 |
| DEVOPS-01 | `claw.sh` unified launcher (routes to correct provisioning method) | P0 | DEVOPS | M1 | W3 |
| DEVOPS-02 | ZeroClaw Vagrantfile | P0 | DEVOPS | M1 | W3 |
| DEVOPS-03 | ZeroClaw Dockerfile | P0 | DEVOPS | M1 | W3 |
| DEVOPS-04 | ZeroClaw install script (`install-zeroclaw.sh`) | P0 | DEVOPS | M1 | W3 |
| DEVOPS-05 | ZeroClaw entrypoint (`entrypoint.sh` — env translation) | P0 | DEVOPS | M1 | W3 |
| DEVOPS-06 | ZeroClaw config templates | P0 | DEVOPS | M1 | W3 |
| INFRA-04 | `provision-base.sh` (common Ubuntu base provisioning) | P0 | INFRA | M1 | W3 |
| DEVOPS-07 | `docker-compose.yml` (initial, zeroclaw profile) | P0 | DEVOPS | M1 | W3 |

### Wave 3 — Engineering: M2 (NanoClaw + PicoClaw)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| DEVOPS-08 | NanoClaw Vagrantfile | P0 | DEVOPS | M2 | W3 |
| DEVOPS-09 | NanoClaw Dockerfile | P0 | DEVOPS | M2 | W3 |
| DEVOPS-10 | NanoClaw install script (`install-nanoclaw.sh`) | P0 | DEVOPS | M2 | W3 |
| DEVOPS-11 | NanoClaw entrypoint (`entrypoint.sh` — sed/envsubst injection) | P0 | DEVOPS | M2 | W3 |
| DEVOPS-12 | NanoClaw config templates | P0 | DEVOPS | M2 | W3 |
| DEVOPS-13 | PicoClaw Vagrantfile | P0 | DEVOPS | M2 | W3 |
| DEVOPS-14 | PicoClaw Dockerfile | P0 | DEVOPS | M2 | W3 |
| DEVOPS-15 | PicoClaw install script (`install-picoclaw.sh`) | P0 | DEVOPS | M2 | W3 |
| DEVOPS-16 | PicoClaw entrypoint (`entrypoint.sh`) | P0 | DEVOPS | M2 | W3 |
| DEVOPS-17 | PicoClaw config templates | P0 | DEVOPS | M2 | W3 |
| DEVOPS-18 | `docker-compose.yml` updated (nanoclaw + picoclaw profiles) | P0 | DEVOPS | M2 | W3 |

### Wave 3 — Engineering: M3 (OpenClaw + Multi-Agent)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| DEVOPS-19 | OpenClaw Vagrantfile | P0 | DEVOPS | M3 | W3 |
| DEVOPS-20 | OpenClaw Dockerfile | P0 | DEVOPS | M3 | W3 |
| DEVOPS-21 | OpenClaw install script (`install-openclaw.sh`) | P0 | DEVOPS | M3 | W3 |
| DEVOPS-22 | OpenClaw entrypoint (`entrypoint.sh`) | P0 | DEVOPS | M3 | W3 |
| DEVOPS-23 | OpenClaw config templates | P0 | DEVOPS | M3 | W3 |
| DEVOPS-24 | Multi-agent docker-compose profiles (run 2+ agents) | P1 | DEVOPS | M3 | W3 |
| DEVOPS-25 | Teardown scripts (`claw.sh <agent> destroy`) | P1 | DEVOPS | M3 | W3 |
| DEVOPS-26 | Health check script (`shared/healthcheck.sh`) | P1 | DEVOPS | M3 | W3 |

### Wave 3 — Engineering: M4 (Assessment Pipeline)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| BE-01 | Assessment JSON schema (`assessment-schema.json`) | P0 | BE | M4 | W3 |
| BE-02 | Schema validator (`validate.py`) | P0 | BE | M4 | W3 |
| BE-03 | Platform/model/skills resolver (`resolve.py`) | P0 | BE | M4 | W3 |
| BE-04 | Env generator (`generate_env.py`) | P0 | BE | M4 | W3 |
| BE-05 | Agent config generator (`generate_config.py`) | P0 | BE | M4 | W3 |
| BE-06 | `claw.sh deploy --assessment` integration | P0 | BE + DEVOPS | M4 | W3 |
| BE-07 | `claw.sh validate --assessment` command | P0 | BE + DEVOPS | M4 | W3 |
| INFRA-05 | Skills auto-installer (`shared/skills-installer.sh`) | P1 | INFRA | M4 | W3 |
| BE-08 | Git submodule for claw-client-assessment | P0 | BE | M4 | W3 |
| BE-09 | Example assessment: Real Estate (`example-realstate.json`) | P0 | BE | M4 | W3 |
| BE-10 | Example assessment: IoT / RPi (`example-iot.json`) | P0 | BE | M4 | W3 |
| BE-11 | Example assessment: DevSecOps (`example-devsecops.json`) | P0 | BE | M4 | W3 |
| BE-12 | Client assessment example template | P0 | BE | M4 | W3 |

### Wave 3 — Engineering: M5a (Dataset Collection & Adapter Scaffolding)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| BE-13 | Dataset download script (`download_datasets.py`) | P1 | BE | M5a | W3 |
| BE-14 | Dataset validation script (`validate_datasets.py`) | P1 | BE | M5a | W3 |
| BE-15 | Dataset: 01-customer-support (<=10K rows + metadata.json) | P1 | BE | M5a | W3 |
| BE-16 | Dataset: 02-real-estate | P1 | BE | M5a | W3 |
| BE-17 | Dataset: 03-e-commerce | P1 | BE | M5a | W3 |
| BE-18 | Dataset: 04-healthcare | P1 | BE | M5a | W3 |
| BE-19 | Dataset: 05-legal | P1 | BE | M5a | W3 |
| BE-20 | Dataset: 06-personal-finance-advisor | P1 | BE | M5a | W3 |
| BE-21 | Dataset: 07-code-review | P1 | BE | M5a | W3 |
| BE-22 | Dataset: 08-email-management | P1 | BE | M5a | W3 |
| BE-23 | Dataset: 09-calendar-scheduling | P1 | BE | M5a | W3 |
| BE-24 | Dataset: 10-meeting-summarization | P1 | BE | M5a | W3 |
| BE-25 | Dataset: 11-sales-crm | P1 | BE | M5a | W3 |
| BE-26 | Dataset: 12-hr-recruitment | P1 | BE | M5a | W3 |
| BE-27 | Dataset: 13-it-helpdesk | P1 | BE | M5a | W3 |
| BE-28 | Dataset: 14-content-writing | P1 | BE | M5a | W3 |
| BE-29 | Dataset: 15-social-media | P1 | BE | M5a | W3 |
| BE-30 | Dataset: 16-translation | P1 | BE | M5a | W3 |
| BE-31 | Dataset: 17-education-tutoring | P1 | BE | M5a | W3 |
| BE-32 | Dataset: 18-research-summarization | P1 | BE | M5a | W3 |
| BE-33 | Dataset: 19-data-analysis | P1 | BE | M5a | W3 |
| BE-34 | Dataset: 20-project-management | P1 | BE | M5a | W3 |
| BE-35 | Dataset: 21-accounting | P1 | BE | M5a | W3 |
| BE-36 | Dataset: 22-insurance | P1 | BE | M5a | W3 |
| BE-37 | Dataset: 23-travel-hospitality | P1 | BE | M5a | W3 |
| BE-38 | Dataset: 24-food-restaurant | P1 | BE | M5a | W3 |
| BE-39 | Dataset: 25-fitness-wellness | P1 | BE | M5a | W3 |
| BE-40 | Dataset: 26-automotive | P1 | BE | M5a | W3 |
| BE-41 | Dataset: 27-supply-chain | P1 | BE | M5a | W3 |
| BE-42 | Dataset: 28-manufacturing | P1 | BE | M5a | W3 |
| BE-43 | Dataset: 29-agriculture | P1 | BE | M5a | W3 |
| BE-44 | Dataset: 30-energy-utilities | P1 | BE | M5a | W3 |
| BE-45 | Dataset: 31-telecommunications | P1 | BE | M5a | W3 |
| BE-46 | Dataset: 32-government | P1 | BE | M5a | W3 |
| BE-47 | Dataset: 33-nonprofit | P1 | BE | M5a | W3 |
| BE-48 | Dataset: 34-event-planning | P1 | BE | M5a | W3 |
| BE-49 | Dataset: 35-cybersecurity | P1 | BE | M5a | W3 |
| BE-50 | Dataset: 36-devops-infrastructure | P1 | BE | M5a | W3 |
| BE-51 | Dataset: 37-api-integration | P1 | BE | M5a | W3 |
| BE-52 | Dataset: 38-database-admin | P1 | BE | M5a | W3 |
| BE-53 | Dataset: 39-iot-smart-home | P1 | BE | M5a | W3 |
| BE-54 | Dataset: 40-chatbot-conversational | P1 | BE | M5a | W3 |
| BE-55 | Dataset: 41-document-processing | P1 | BE | M5a | W3 |
| BE-56 | Dataset: 42-knowledge-base-faq | P1 | BE | M5a | W3 |
| BE-57 | Dataset: 43-compliance-regulatory | P1 | BE | M5a | W3 |
| BE-58 | Dataset: 44-onboarding-training | P1 | BE | M5a | W3 |
| BE-59 | Dataset: 45-sentiment-analysis | P1 | BE | M5a | W3 |
| BE-60 | Dataset: 46-creative-writing | P1 | BE | M5a | W3 |
| BE-61 | Dataset: 47-music-entertainment | P1 | BE | M5a | W3 |
| BE-62 | Dataset: 48-gaming | P1 | BE | M5a | W3 |
| BE-63 | Dataset: 49-mental-health | P1 | BE | M5a | W3 |
| BE-64 | Dataset: 50-personal-finance-budgeting | P1 | BE | M5a | W3 |
| BE-65 | 50 adapter config bundles (adapter_config.json + system_prompt.txt + training_config.json) | P1 | BE | M5a | W3 |
| BE-66 | Dataset catalog README (`finetune/datasets/README.md`) | P1 | BE | M5a | W3 |
| BE-67 | Adapter catalog README (`finetune/adapters/README.md`) | P1 | BE | M5a | W3 |
| DEVOPS-27 | `claw.sh datasets --list` command | P1 | DEVOPS | M5a | W3 |
| DEVOPS-28 | `claw.sh datasets --validate` command | P1 | DEVOPS | M5a | W3 |
| DEVOPS-29 | `claw.sh datasets --download-all` command | P1 | DEVOPS | M5a | W3 |
| DEVOPS-30 | `claw.sh datasets --stats` command | P1 | DEVOPS | M5a | W3 |

### Wave 3 — Engineering: M5b (LoRA/QLoRA Fine-Tuning Pipeline)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| BE-68 | Fine-tuning Dockerfile (`Dockerfile.finetune`) | P1 | BE | M5b | W3 |
| BE-69 | Fine-tuning requirements (`requirements.txt`) | P1 | BE | M5b | W3 |
| BE-70 | Dataset generator (`dataset_generator.py` — assessment to training data) | P1 | BE | M5b | W3 |
| BE-71 | LoRA training script (`train_lora.py`) | P1 | BE | M5b | W3 |
| BE-72 | QLoRA training script (`train_qlora.py`) | P1 | BE | M5b | W3 |
| BE-73 | Adapter merge script (`merge_adapter.py`) | P1 | BE | M5b | W3 |
| DEVOPS-31 | `claw.sh finetune --assessment` command | P1 | DEVOPS | M5b | W3 |
| DEVOPS-32 | `claw.sh finetune --adapter <use-case>` command | P1 | DEVOPS | M5b | W3 |
| DEVOPS-33 | `claw.sh finetune --adapter <use-case> --dry-run` command | P1 | DEVOPS | M5b | W3 |
| DEVOPS-34 | Adapter loading: ZeroClaw entrypoint update | P1 | DEVOPS | M5b | W3 |
| DEVOPS-35 | Adapter loading: NanoClaw entrypoint update | P1 | DEVOPS | M5b | W3 |
| DEVOPS-36 | Adapter loading: PicoClaw entrypoint update | P1 | DEVOPS | M5b | W3 |
| DEVOPS-37 | Adapter loading: OpenClaw entrypoint update | P1 | DEVOPS | M5b | W3 |

### Wave 4 — QA + Wave 5 — Release: M6 (CI/CD + Polish + Docs)

| ID | Card | Priority | Owner | Milestone | Wave |
|----|------|----------|-------|-----------|------|
| INFRA-06 | GitHub Actions CI pipeline (`.github/workflows/ci.yml`) | P0 | INFRA | M6 | W4 |
| INFRA-07 | CI: Matrix build (4 agents x Docker) | P0 | INFRA | M6 | W4 |
| INFRA-08 | CI: Assessment pipeline validation | P0 | INFRA | M6 | W4 |
| INFRA-09 | CI: Dataset validation (50 datasets) | P1 | INFRA | M6 | W4 |
| INFRA-10 | CI: Linting (shellcheck, hadolint, ruff) | P0 | INFRA | M6 | W4 |
| INFRA-11 | CI: Security scan (no secrets/PII in tracked files) | P0 | INFRA | M6 | W4 |
| INFRA-12 | Pre-commit hooks config (`.pre-commit-config.yaml`) | P0 | INFRA | M6 | W4 |
| PM-10 | README.md (quickstart, per-agent, assessment, fine-tuning, troubleshooting) | P0 | PM | M6 | W5 |
| PM-11 | `.ai/context_base.md` | P0 | PM | M6 | W5 |
| PM-12 | Example walkthrough: Real Estate | P0 | PM | M6 | W5 |
| PM-13 | Example walkthrough: IoT / RPi | P0 | PM | M6 | W5 |
| PM-14 | Example walkthrough: DevSecOps | P0 | PM | M6 | W5 |
| PM-15 | Troubleshooting guide (in README) | P0 | PM | M6 | W5 |
| PM-16 | Fine-tuning guide (in README) | P1 | PM | M6 | W5 |

---

## Blocked

| ID | Card | Priority | Owner | Milestone | Wave | Blocked By |
|----|------|----------|-------|-----------|------|------------|
| — | (Nothing blocked yet) | — | — | — | — | — |

---

## Summary Counts

| Column | Count |
|--------|-------|
| Backlog | 113 |
| Sprint Ready | 0 |
| In Progress | 9 |
| In Review | 0 |
| Testing | 0 |
| Done | 0 |
| Blocked | 0 |
| **Total** | **122** |

### By Priority

| Priority | Count |
|----------|-------|
| P0 | 55 |
| P1 | 67 |
| **Total** | **122** |

### By Owner

| Owner | Count |
|-------|-------|
| PM | 16 |
| BE | 67 |
| DEVOPS | 37 |
| INFRA | 12 |
| BE + DEVOPS (shared) | 2 |

### By Milestone

| Milestone | Count |
|-----------|-------|
| M0 (Planning) | 9 |
| M1 (Foundation + ZeroClaw) | 11 |
| M2 (NanoClaw + PicoClaw) | 11 |
| M3 (OpenClaw + Multi-Agent) | 8 |
| M4 (Assessment Pipeline) | 13 |
| M5a (Datasets + Adapters) | 56 |
| M5b (Fine-Tuning Pipeline) | 13 |
| M6 (CI/CD + Docs) | 14 |

---

*Kanban Board v1.0 — Claw Agents Provisioner — Amenthyx AI Teams v3.0*
*Updated: 2026-02-26*
