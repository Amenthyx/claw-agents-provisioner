# Timeline — Claw Agents Provisioner

> Version: 2.0
> Date: 2026-03-02
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Supersedes: v1.0 (2026-02-26)

---

## Overview

```
Week 0    Week 1    Week 2    Week 3    Week 4    Week 5    Week 6    Week 7
 W1/W2     W3        W3        W3        W3        W3        W3       W4/W5
  M0       M1        M2        M3        M4       M5a       M5b       M6
Planning  Found.   Nano+Pico  Open+     Assess.  Datasets  FineTune  CI/CD
          +Zero              Multi      Pipeline  +Adapters Pipeline  +Docs
```

**Hard Deadline**: Flexible
**Total Duration**: 8 weeks (Week 0 through Week 7)
**Start Date**: 2026-02-26

---

## Week 0 — Planning & Architecture (Wave 1: Planning + Wave 2: Research)

**Milestone**: M0
**Owner**: PM
**Dates**: 2026-02-26 to 2026-03-04
**Dependencies**: None (kickoff)

| Day | Deliverable | Owner | Status |
|-----|-------------|-------|--------|
| D1 | Project Charter | PM | In Progress |
| D1 | Milestone Plan | PM | In Progress |
| D1 | Kanban Board | PM | In Progress |
| D1 | Timeline | PM | In Progress |
| D1 | Risk Register | PM | In Progress |
| D1 | GitHub Issues Template | PM | In Progress |
| D1 | Commit Log Template | PM | In Progress |
| D1 | Team Status | PM | In Progress |
| D1 | PM Evidence Manifest | PM | In Progress |
| D2-D5 | Research: Agent repo analysis (upstream install flows, config formats, env vars) | ALL | Backlog |
| D2-D5 | Research: Assessment toolkit deep-dive (schema, matrix, skills catalog) | BE | Backlog |
| D2-D5 | Research: LoRA/QLoRA tooling survey (PEFT, bitsandbytes, vLLM) | BE | Backlog |
| D2-D5 | Research: Dataset source identification (all 50 use cases) | BE | Backlog |

**Exit Criteria**: All planning artifacts written. Team understands agent architectures and assessment toolkit.

---

## Week 1 — Foundation + ZeroClaw (Wave 3: Engineering)

**Milestone**: M1
**Owner**: DEVOPS (lead), INFRA (support)
**Dates**: 2026-03-05 to 2026-03-11
**Dependencies**: M0 complete

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1 | Repository structure scaffold | INFRA | M0 |
| D1 | `.gitignore` + `.gitattributes` | INFRA | — |
| D1-D2 | Unified `.env.template` | INFRA | Scaffold |
| D1-D2 | `provision-base.sh` (shared Ubuntu base) | INFRA | Scaffold |
| D2-D3 | `claw.sh` unified launcher (skeleton) | DEVOPS | Scaffold |
| D2-D3 | ZeroClaw install script | DEVOPS | `provision-base.sh` |
| D3-D4 | ZeroClaw Vagrantfile | DEVOPS | Install script |
| D3-D4 | ZeroClaw Dockerfile | DEVOPS | Install script |
| D4-D5 | ZeroClaw entrypoint (`entrypoint.sh`) | DEVOPS | `.env.template` |
| D4-D5 | ZeroClaw config templates | DEVOPS | Entrypoint |
| D5 | `docker-compose.yml` (initial, zeroclaw profile) | DEVOPS | Dockerfile |
| D5 | Verification: `./claw.sh zeroclaw docker` test | DEVOPS | All above |

**Parallel Track (BE — starts early on M4/M5a research)**:
| Day | Deliverable | Owner |
|-----|-------------|-------|
| D1-D5 | Assessment JSON schema draft | BE |
| D1-D5 | Dataset source mapping (identify URLs for all 50) | BE |

**Exit Criteria**: ZeroClaw starts via Docker and Vagrant. `.env.template` is complete. `claw.sh` routes correctly.

---

## Week 2 — NanoClaw + PicoClaw (Wave 3: Engineering)

**Milestone**: M2
**Owner**: DEVOPS (lead), INFRA (support)
**Dates**: 2026-03-12 to 2026-03-18
**Dependencies**: M1 complete (foundation, shared scripts)

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1-D2 | NanoClaw install script | DEVOPS | `provision-base.sh` (M1) |
| D1-D2 | NanoClaw entrypoint (sed/envsubst injection strategy) | DEVOPS | `.env.template` (M1) |
| D2-D3 | NanoClaw Dockerfile (Docker-in-Docker / DooD) | DEVOPS | Install script |
| D2-D3 | NanoClaw Vagrantfile | DEVOPS | Install script |
| D3-D4 | PicoClaw install script | DEVOPS | `provision-base.sh` (M1) |
| D3-D4 | PicoClaw entrypoint | DEVOPS | `.env.template` (M1) |
| D4-D5 | PicoClaw Dockerfile | DEVOPS | Install script |
| D4-D5 | PicoClaw Vagrantfile | DEVOPS | Install script |
| D5 | `docker-compose.yml` updated (add nanoclaw + picoclaw profiles) | DEVOPS | Both Dockerfiles |
| D5 | Verification: Both agents start via Docker and Vagrant | DEVOPS | All above |

**Parallel Track (BE — continues M4/M5a prep)**:
| Day | Deliverable | Owner |
|-----|-------------|-------|
| D1-D5 | `validate.py` (schema validator) | BE |
| D1-D5 | `resolve.py` (resolver skeleton) | BE |
| D1-D5 | Begin dataset downloads (first 10 use cases) | BE |

**Exit Criteria**: NanoClaw and PicoClaw both provisionable via Docker and Vagrant. Health checks pass.

---

## Week 3 — OpenClaw + Multi-Agent (Wave 3: Engineering)

**Milestone**: M3
**Owner**: DEVOPS (lead), INFRA (support)
**Dates**: 2026-03-19 to 2026-03-25
**Dependencies**: M2 complete

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1-D2 | OpenClaw install script | DEVOPS | `provision-base.sh` (M1) |
| D1-D2 | OpenClaw entrypoint | DEVOPS | `.env.template` (M1) |
| D2-D3 | OpenClaw Dockerfile (multi-stage, Node.js 22) | DEVOPS | Install script |
| D2-D3 | OpenClaw Vagrantfile | DEVOPS | Install script |
| D3-D4 | OpenClaw config templates | DEVOPS | Entrypoint |
| D3-D4 | Multi-agent docker-compose profiles (final) | DEVOPS | All 4 Dockerfiles |
| D4-D5 | Teardown scripts (`claw.sh <agent> destroy`) | DEVOPS | `claw.sh` (M1) |
| D4-D5 | Unified health check (`shared/healthcheck.sh`) | DEVOPS | All 4 agents |
| D5 | Verification: All 4 agents, multi-agent compose, teardown | DEVOPS | All above |

**Parallel Track (BE — continues M4 pipeline)**:
| Day | Deliverable | Owner |
|-----|-------------|-------|
| D1-D5 | `generate_env.py` | BE |
| D1-D5 | `generate_config.py` | BE |
| D1-D5 | Continue dataset downloads (use cases 11-25) | BE |

**Exit Criteria**: All 4 agents work. Multi-agent compose works. Teardown cleans up. Health checks pass.

---

## Week 4 — Assessment Pipeline (Wave 3: Engineering)

**Milestone**: M4
**Owner**: BE (lead), INFRA + DEVOPS (support)
**Dates**: 2026-03-26 to 2026-04-01
**Dependencies**: M3 complete (all agents provisionable)

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1 | Git submodule: `assessment/claw-client-assessment/` | BE | M0 (research) |
| D1-D2 | Assessment JSON schema finalized | BE | Submodule |
| D2-D3 | `resolve.py` — weighted scoring algorithm (all 15 matrix entries) | BE | Schema |
| D3 | `generate_env.py` — assessment to `.env` | BE | Resolver |
| D3-D4 | `generate_config.py` — assessment to agent config (TOML/JSON5/JSON) | BE | Resolver |
| D4 | `claw.sh deploy --assessment` integration | BE + DEVOPS | All generators |
| D4 | `claw.sh validate --assessment` command | BE + DEVOPS | Validator |
| D4-D5 | Skills auto-installer (`shared/skills-installer.sh`) | INFRA | Resolver |
| D5 | Example assessments: Real Estate, IoT, DevSecOps | BE | Pipeline |
| D5 | Client assessment example template | BE | Schema |
| D5 | End-to-end verification: 3 assessment flows | ALL | All above |

**Parallel Track (BE — continues M5a dataset work)**:
| Day | Deliverable | Owner |
|-----|-------------|-------|
| D1-D5 | Continue dataset downloads (use cases 26-40) | BE |

**Exit Criteria**: `deploy --assessment` works end-to-end for 3 industries. All 15 matrix entries resolve correctly. ruff clean.

---

## Week 5 — Dataset Collection & Adapter Scaffolding (Wave 3: Engineering)

**Milestone**: M5a
**Owner**: BE
**Dates**: 2026-04-02 to 2026-04-08
**Dependencies**: M1 (repo structure)

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1-D2 | `download_datasets.py` script (fetch, sample, convert) | BE | M1 (repo structure) |
| D1-D2 | `validate_datasets.py` script (rows, schema, license check) | BE | Download script |
| D1-D3 | Complete remaining dataset downloads (use cases 41-50) | BE | Download script |
| D1-D3 | All 50 `metadata.json` files generated | BE | All downloads |
| D3-D4 | All 50 adapter configs: `adapter_config.json` | BE | Dataset analysis |
| D3-D4 | All 50 adapter configs: `system_prompt.txt` | BE | Dataset analysis |
| D3-D4 | All 50 adapter configs: `training_config.json` | BE | Dataset analysis |
| D4-D5 | `claw.sh datasets --list/--validate/--download-all/--stats` commands | DEVOPS | Scripts ready |
| D5 | Dataset catalog README | BE | All datasets |
| D5 | Adapter catalog README | BE | All adapters |
| D5 | Validation: All 50 datasets present, <=10K rows, free licenses | BE | All above |

**Exit Criteria**: All 50 datasets committed. All 50 adapter configs present. `datasets --validate` passes. Total < 500 MB.

---

## Week 6 — LoRA/QLoRA Fine-Tuning Pipeline (Wave 3: Engineering)

**Milestone**: M5b
**Owner**: BE
**Dates**: 2026-04-09 to 2026-04-15
**Dependencies**: M5a (datasets + adapter configs), M3 (agent entrypoints)

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1 | `finetune/requirements.txt` (torch, transformers, peft, bitsandbytes) | BE | — |
| D1-D2 | `Dockerfile.finetune` (GPU-enabled training container) | BE | Requirements |
| D2-D3 | `dataset_generator.py` (assessment to training dataset) | BE | M4 (assessment pipeline) |
| D3-D4 | `train_lora.py` (LoRA training script with PEFT) | BE | Dataset generator |
| D3-D4 | `train_qlora.py` (QLoRA training with 4-bit quantization) | BE | Dataset generator |
| D4 | `merge_adapter.py` (optional adapter merge) | BE | Training scripts |
| D4-D5 | Adapter loading in all 4 entrypoints | DEVOPS | Training scripts, M3 entrypoints |
| D5 | `claw.sh finetune` commands (--assessment, --adapter, --dry-run) | DEVOPS | All scripts |
| D5 | Validation: Train 2 adapters, verify domain-specific behavior | BE | All above |

**Exit Criteria**: Fine-tuning pipeline works. At least 2 adapters trained and loaded. TensorBoard logs generated.

---

## Week 7 — CI/CD + Polish + Docs (Wave 4: QA + Wave 5: Release)

**Milestone**: M6
**Owner**: INFRA (lead), ALL (support)
**Dates**: 2026-04-16 to 2026-04-22
**Dependencies**: M1-M5b complete

| Day | Deliverable | Owner | Depends On |
|-----|-------------|-------|------------|
| D1-D2 | GitHub Actions CI pipeline | INFRA | All code complete |
| D1-D2 | CI: Matrix build (4 agents x Docker) | INFRA | CI pipeline |
| D2 | CI: Assessment validation | INFRA | CI pipeline |
| D2 | CI: Dataset validation | INFRA | CI pipeline |
| D2-D3 | CI: Linting (shellcheck, hadolint, ruff) | INFRA | CI pipeline |
| D3 | CI: Security scan (no secrets/PII) | INFRA | CI pipeline |
| D3 | Pre-commit hooks (`.pre-commit-config.yaml`) | INFRA | — |
| D3-D4 | README.md (comprehensive) | PM | All features done |
| D4 | `.ai/context_base.md` | PM | README |
| D4-D5 | 3 example assessment walkthroughs | PM | README |
| D5 | Troubleshooting guide | PM | All testing |
| D5 | Fine-tuning guide | PM | M5b |
| D5 | Final CI green verification | INFRA | All above |
| D5 | Evidence collection: all screenshots + logs | ALL | All above |

**Exit Criteria**: CI green. README complete. All evidence collected. v1.0 ready for release.

---

## Dependency Graph

```
M0 (Planning)
 |
 v
M1 (Foundation + ZeroClaw)
 |
 +---> M2 (NanoClaw + PicoClaw)
 |      |
 |      v
 |     M3 (OpenClaw + Multi-Agent)
 |      |
 |      +---> M4 (Assessment Pipeline)
 |      |      |
 |      |      v
 |      |     M5b (Fine-Tuning Pipeline)
 |      |      |
 |      v      v
 |     M5a (Datasets + Adapters) <-- depends on M1 (structure only)
 |      |
 |      v
 +---> M6 (CI/CD + Docs) <-- depends on ALL of M1-M5b
```

### Critical Path

```
M0 --> M1 --> M2 --> M3 --> M4 --> M5b --> M6
```

M5a runs in parallel (only depends on M1 for repo structure) but must complete before M6.

---

## Parallel Work Streams

| Week | Primary Track (DEVOPS + INFRA) | Secondary Track (BE) |
|------|-------------------------------|----------------------|
| 0 | Planning (PM-led) | Research: agent repos, assessment toolkit, datasets |
| 1 | M1: Foundation + ZeroClaw | M4 prep: schema draft, dataset source mapping |
| 2 | M2: NanoClaw + PicoClaw | M4 prep: validator, resolver skeleton, first 10 datasets |
| 3 | M3: OpenClaw + Multi-Agent | M4: generators, datasets 11-25 |
| 4 | M4 support: claw.sh integration | M4: pipeline, datasets 26-40 |
| 5 | M5a support: claw.sh dataset commands | M5a: remaining datasets 41-50, adapter configs |
| 6 | M5b support: entrypoint updates, claw.sh finetune | M5b: training scripts, adapter validation |
| 7 | M6: CI/CD pipeline | M6 support: docs, evidence |

---

---

## v2.0 Production Hardening Timeline (Weeks 8-11)

### Overview

```
Week 8  [M7 Test Foundation]       BE, QA       ==============================
Week 9  [M8 Prod Infrastructure]   DEVOPS, INFRA ==============================
Week 10 [M9 Load Testing]          QA, BE       ===============
        [M10 Security Hardening]   INFRA, QA                   ===============
Week 11 [M11 Observability]        DEVOPS, INFRA ===============
        [M12 Prod Validation]      QA, PM                      ===============
```

**Start Date**: 2026-03-02 (immediately following v1.0 completion)
**End Date**: 2026-03-30
**Total v2.0 Duration**: 4 weeks

---

### Week 8 (2026-03-02 -- 2026-03-08): Test Foundation

**Milestone**: M7
**Primary**: BE, QA
**Wave**: 6 (v2.0 Engineering)
**Dependencies**: v1.0 complete (M0-M6)

| Day | Agent | Task | Deliverable |
|-----|-------|------|-------------|
| Mon | BE | Set up pytest fixtures and test Docker Compose | `tests/conftest.py`, `docker-compose.test.yml` |
| Mon | QA | Design E2E test framework architecture | `tests/e2e/` scaffold |
| Tue | BE | Router -> LLM integration tests | `tests/integration/test_router_llm.py` |
| Tue | QA | Mock external LLM API responses | `tests/mocks/` |
| Wed | BE | Memory -> SQLite integration tests | `tests/integration/test_memory_sqlite.py` |
| Wed | QA | E2E: Assessment -> deploy flow tests | `tests/e2e/test_deploy.py` |
| Thu | BE | RAG pipeline + orchestrator integration tests | `tests/integration/test_rag_pipeline.py`, `test_orchestrator.py` |
| Thu | QA | E2E: Health check -> chat -> teardown tests | `tests/e2e/test_lifecycle.py` |
| Fri | BE | Billing -> alerts integration tests | `tests/integration/test_billing_alerts.py` |
| Fri | QA | E2E suite finalization, CI integration | All E2E tests passing in CI |

**Exit Criteria**: >= 80% integration coverage, E2E framework runs full deploy cycle, CI passes

---

### Week 9 (2026-03-09 -- 2026-03-15): Production Infrastructure

**Milestone**: M8
**Primary**: DEVOPS, INFRA
**Wave**: 6 (v2.0 Engineering)
**Dependencies**: M7 (test infrastructure for validation)

| Day | Agent | Task | Deliverable |
|-----|-------|------|-------------|
| Mon | DEVOPS | Nginx reverse proxy configuration | `nginx/nginx.conf`, `nginx/Dockerfile` |
| Mon | BE | Database migration scripts (memory service) | `migrations/001_memory.sql` |
| Tue | DEVOPS | Let's Encrypt / certbot integration | `certbot/`, `nginx/renew-certs.sh` |
| Tue | BE | Database migration scripts (billing, DAL) | `migrations/002_billing.sql`, `003_dal.sql` |
| Wed | DEVOPS | Production Docker Compose (resource limits, restart policies) | `docker-compose.production.yml` |
| Wed | BE | Migration rollback scripts + validation | `migrations/rollback/` |
| Thu | DEVOPS | Automated backup script + cron config | `scripts/backup.sh`, `scripts/backup-cron.conf` |
| Thu | INFRA | Secrets management (Docker secrets) | docker-compose secrets config |
| Fri | DEVOPS | Automated restore script + validation | `scripts/restore.sh` |
| Fri | ALL | Full production stack validation on Ubuntu 24.04 | Evidence: production stack running |

**Exit Criteria**: Production compose works on clean Ubuntu; HTTPS active; backup/restore round-trip tested

---

### Week 10 (2026-03-16 -- 2026-03-22): Load Testing + Security Hardening

**Milestones**: M9 (Mon-Wed), M10 (Thu-Fri)
**Primary**: QA + BE (M9), INFRA + QA (M10)
**Wave**: 7 (v2.0 QA)
**Dependencies**: M8 (production infrastructure to test against and scan)

| Day | Agent | Task | Deliverable |
|-----|-------|------|-------------|
| Mon | QA | k6 scripts for router + memory endpoints | `tests/load/router.js`, `tests/load/memory.js` |
| Mon | BE | Performance baseline measurements | `tests/load/BASELINES.md` |
| Tue | QA | k6 scripts for RAG + dashboard endpoints | `tests/load/rag.js`, `tests/load/dashboard.js` |
| Tue | BE | Bottleneck analysis and fixes | Perf improvement commits |
| Wed | QA | Load test CI stage + regression detection | `.github/workflows/load-test.yml` |
| Thu | INFRA | Bandit scan + npm audit integration | CI security stage |
| Thu | QA | Pre-commit hooks configuration | `.pre-commit-config.yaml` |
| Fri | INFRA | Branch protection rules + SBOM validation | GitHub settings, CI update |
| Fri | QA | GDPR/SOC2 compliance evidence assembly | `.team/evidence/compliance/` |

**Exit Criteria**: P95 targets met; zero HIGH/CRITICAL findings; compliance evidence assembled

---

### Week 11 (2026-03-23 -- 2026-03-30): Observability + Production Validation

**Milestones**: M11 (Mon-Wed), M12 (Thu-Fri)
**Primary**: DEVOPS + INFRA (M11), QA + DEVOPS + PM (M12)
**Waves**: 7 (M11), 8 (M12 -- v2.0 Release)
**Dependencies**: M7-M10 (all prior v2.0 milestones)

| Day | Agent | Task | Deliverable |
|-----|-------|------|-------------|
| Mon | DEVOPS | Grafana dashboard templates | `monitoring/grafana/dashboards/` |
| Mon | INFRA | Prometheus alerting rules | `monitoring/prometheus/alerts/` |
| Tue | DEVOPS | Loki log aggregation configuration | `monitoring/loki/` |
| Tue | DEVOPS | Operational runbook | `docs/RUNBOOK.md` |
| Wed | DEVOPS | Incident response playbook | `docs/INCIDENT_RESPONSE.md` |
| Wed | QA | Runbook QA sign-off | Evidence: QA-validated runbook |
| Thu | QA | Smoke test suite (post-deployment) | `tests/smoke/` |
| Thu | DEVOPS | Blue-green deployment support | `scripts/blue-green-deploy.sh` |
| Fri | QA | Final E2E on production compose | Test evidence |
| Fri | PM | Release candidate preparation + docs review | Tagged RC, all docs updated |

**Exit Criteria**: Dashboards showing all 8 services; alerts firing; smoke test auto-runs; RC deployed and validated

---

### v2.0 Dependency Graph

```
v1.0 Complete (M0-M6)
  |
  v
M7 Test Foundation (Week 8)
  |
  v
M8 Production Infrastructure (Week 9)
  |
  +----------+---------+
  |          |         |
  v          v         v
M9 Load    M10       M11 Observability
Testing    Security  (Week 11)
(Week 10)  (Week 10)
  |          |         |
  +----------+---------+
             |
             v
M12 Production Validation (Week 11)
             |
             v
         v2.0 RC
```

### v2.0 Critical Path

```
M7 --> M8 --> M11 --> M12 (v2.0 RC)
```

M9 and M10 run in parallel during Week 10, providing 2 days of slack if either overruns.

---

### v2.0 Agent Workload Summary

| Agent | Week 8 | Week 9 | Week 10 | Week 11 | Total Days |
|-------|--------|--------|---------|---------|------------|
| BE | M7 (5d) | M8 (4d) | M9 (2d) | -- | 11 |
| QA | M7 (5d) | -- | M9 (3d) + M10 (2d) | M12 (3d) | 13 |
| DEVOPS | -- | M8 (5d) | -- | M11 (4d) + M12 (1d) | 10 |
| INFRA | -- | M8 (1d) | M10 (2d) | M11 (1d) | 4 |
| PM | -- | -- | -- | M12 (1d) | 1 |

---

*Timeline v2.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
*Updated 2026-03-02 for v2.0 production hardening timeline (Weeks 8-11)*
