# Kanban Board -- Claw Agents Provisioner

> Version: 4.0
> Date: 2026-03-02
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Last Updated: 2026-03-02

---

## Legend

- **Priority**: P0 = Must-Have (Launch Blocker), P1 = Should-Have (Important), P2 = Nice-to-Have
- **Owner**: PM, MKT, LEGAL, BE, DEVOPS, INFRA, QA, FE, RM
- **Milestone**: M0-M12
- **Wave**: W1 (Planning), W1.5 (Research), W2 (Engineering), W3 (Dataset Expansion), W4 (QA), W5 (Release), W6 (v2.0 Engineering), W7 (v2.0 QA), W8 (v2.0 Release)

---

## Backlog

### Wave 8 -- v2.0 Release: Deployment (P1 -- M12)

| ID | Card | Description | Priority | Owner | Milestone | Wave |
|----|------|-------------|----------|-------|-----------|------|
| V2-14 | Blue-green deployment support | Zero-downtime agent updates via container swap with health check gate. Agent update completes with zero dropped requests; automatic rollback on failed health check | P1 | DEVOPS | M12 | W8 |

---

## Blocked

(None)

---

## In Progress

(None)

---

## Done

### Wave 1 -- Planning (M0)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| PM-01 | Project Charter | P0 | PM | M0 |
| PM-02 | Milestone Plan | P0 | PM | M0 |
| PM-03 | Kanban Board | P0 | PM | M0 |
| PM-04 | Timeline | P0 | PM | M0 |
| PM-05 | Risk Register | P0 | PM | M0 |
| PM-06 | GitHub Issues Template | P0 | PM | M0 |
| PM-07 | Commit Log Template | P0 | PM | M0 |
| PM-08 | Team Status | P0 | PM | M0 |
| PM-09 | PM Evidence Manifest | P0 | PM | M0 |

### Wave 1.5 -- Research (M0)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| MKT-01 | Competitive Analysis | P0 | MKT | M0 |
| MKT-02 | Market Positioning | P0 | MKT | M0 |
| MKT-03 | Launch Plan | P0 | MKT | M0 |
| LEGAL-01 | Compliance Review | P0 | LEGAL | M0 |
| LEGAL-02 | Data Privacy Assessment | P0 | LEGAL | M0 |
| LEGAL-03 | License Matrix | P0 | LEGAL | M0 |

### Wave 2 -- Engineering: Infrastructure (M1-M3)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| INFRA-01 | Repository structure scaffold | P0 | INFRA | M1 |
| INFRA-02 | Unified `.env.template` | P0 | INFRA | M1 |
| INFRA-03 | `.gitignore` + `.gitattributes` | P0 | INFRA | M1 |
| INFRA-04 | `provision-base.sh` | P0 | INFRA | M1 |
| INFRA-05 | Skills auto-installer | P1 | INFRA | M4 |
| DEVOPS-01 | `claw.sh` unified launcher | P0 | DEVOPS | M1 |
| DEVOPS-02 | ZeroClaw Vagrantfile | P0 | DEVOPS | M1 |
| DEVOPS-03 | ZeroClaw Dockerfile | P0 | DEVOPS | M1 |
| DEVOPS-04 | ZeroClaw install script | P0 | DEVOPS | M1 |
| DEVOPS-05 | ZeroClaw entrypoint | P0 | DEVOPS | M1 |
| DEVOPS-06 | ZeroClaw config templates | P0 | DEVOPS | M1 |
| DEVOPS-07 | `docker-compose.yml` | P0 | DEVOPS | M1 |
| DEVOPS-08 | NanoClaw Vagrantfile | P0 | DEVOPS | M2 |
| DEVOPS-09 | NanoClaw Dockerfile | P0 | DEVOPS | M2 |
| DEVOPS-10 | NanoClaw install script | P0 | DEVOPS | M2 |
| DEVOPS-11 | NanoClaw entrypoint | P0 | DEVOPS | M2 |
| DEVOPS-12 | NanoClaw config templates | P0 | DEVOPS | M2 |
| DEVOPS-13 | PicoClaw Vagrantfile | P0 | DEVOPS | M2 |
| DEVOPS-14 | PicoClaw Dockerfile | P0 | DEVOPS | M2 |
| DEVOPS-15 | PicoClaw install script | P0 | DEVOPS | M2 |
| DEVOPS-16 | PicoClaw entrypoint | P0 | DEVOPS | M2 |
| DEVOPS-17 | PicoClaw config templates | P0 | DEVOPS | M2 |
| DEVOPS-18 | docker-compose profiles updated | P0 | DEVOPS | M2 |
| DEVOPS-19 | OpenClaw Vagrantfile | P0 | DEVOPS | M3 |
| DEVOPS-20 | OpenClaw Dockerfile | P0 | DEVOPS | M3 |
| DEVOPS-21 | OpenClaw install script | P0 | DEVOPS | M3 |
| DEVOPS-22 | OpenClaw entrypoint | P0 | DEVOPS | M3 |
| DEVOPS-23 | OpenClaw config templates | P0 | DEVOPS | M3 |
| DEVOPS-24 | Multi-agent docker-compose profiles | P1 | DEVOPS | M3 |
| DEVOPS-25 | Teardown scripts | P1 | DEVOPS | M3 |
| DEVOPS-26 | Health check script | P1 | DEVOPS | M3 |

### Wave 2 -- Engineering: Assessment Pipeline (M4)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| BE-01 | Assessment JSON schema | P0 | BE | M4 |
| BE-02 | Schema validator | P0 | BE | M4 |
| BE-03 | Platform/model/skills resolver | P0 | BE | M4 |
| BE-04 | Env generator | P0 | BE | M4 |
| BE-05 | Agent config generator | P0 | BE | M4 |
| BE-06 | `claw.sh deploy --assessment` integration | P0 | BE | M4 |
| BE-07 | `claw.sh validate --assessment` command | P0 | BE | M4 |
| BE-08 | Needs mapping matrix (15 profiles) | P0 | BE | M4 |
| BE-09 | Client assessment example (Lucia) | P0 | BE | M4 |
| BE-10 | API contracts documentation | P0 | BE | M4 |

### Wave 2 -- Engineering: Datasets + Adapters (M5a)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| BE-13 | Dataset download script | P1 | BE | M5a |
| BE-14 | Dataset validation script | P1 | BE | M5a |
| BE-15..64 | 50 use-case datasets (5,000 rows each from HuggingFace) | P1 | BE | M5a |
| BE-65 | 50 adapter config bundles | P1 | BE | M5a |
| BE-66 | Dataset catalog README | P1 | BE | M5a |
| BE-67 | Adapter catalog README | P1 | BE | M5a |
| DEVOPS-27..30 | `claw.sh datasets` commands (list, validate, download, stats) | P1 | DEVOPS | M5a |

### Wave 2 -- Engineering: Fine-Tuning Pipeline (M5b)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| BE-68 | Fine-tuning Dockerfile | P1 | BE | M5b |
| BE-69 | Fine-tuning requirements.txt | P1 | BE | M5b |
| BE-70 | Dataset generator (assessment to training data) | P1 | BE | M5b |
| BE-71 | LoRA training script | P1 | BE | M5b |
| BE-72 | QLoRA training script | P1 | BE | M5b |
| BE-73 | Adapter merge script | P1 | BE | M5b |
| DEVOPS-31..37 | `claw.sh finetune` commands + adapter loading in entrypoints | P1 | DEVOPS | M5b |

### Wave 3 -- Dataset Expansion

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| BE-74 | Real HuggingFace data downloader script | P1 | BE | M5a |
| BE-75 | Download + convert all 50 datasets to 5,000 rows | P1 | BE | M5a |

### Wave 4 -- QA (M6)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| QA-01 | Full project audit (50 issues found) | P0 | QA | M6 |
| QA-02 | Fix 5 CRITICAL issues (entrypoint scripts) | P0 | QA | M6 |
| QA-03 | Fix 6 HIGH issues (configs, pipeline, security) | P0 | QA | M6 |
| QA-04 | Dataset validation (50/50 pass, 250K rows) | P0 | QA | M6 |
| QA-05 | Assessment pipeline E2E test | P0 | QA | M6 |
| QA-06 | QA Evidence Manifest | P0 | QA | M6 |

### Wave 5 -- Release (M6)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| INFRA-06 | GitHub Actions CI pipeline | P0 | INFRA | M6 |
| INFRA-07..11 | CI: builds, validation, linting, security scan | P0 | INFRA | M6 |
| INFRA-12 | Pre-commit hooks config | P0 | INFRA | M6 |
| PM-10 | README.md | P0 | PM | M6 |
| PM-11 | `.ai/context_base.md` | P0 | PM | M6 |
| PM-12..14 | Example walkthroughs (Real Estate, IoT, DevSecOps) | P0 | PM | M6 |
| PM-15 | Troubleshooting guide | P0 | PM | M6 |
| PM-16 | Fine-tuning guide | P1 | PM | M6 |
| LEGAL-04 | Apache-2.0 LICENSE file | P0 | LEGAL | M6 |
| PM-17 | Final project status update | P0 | PM | M6 |
| PM-18 | Final commit log update | P0 | PM | M6 |

### Wave 6 -- v2.0 Engineering: Test Foundation (M7)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-01 | Integration test suite (6 cross-service test files) | P0 | BE | M7 |
| V2-02 | E2E test suite (2 E2E test files, 29 tests, 100% pass) | P0 | BE | M7 |
| V2-FE-01 | Wizard UI test suite (14 test files, vitest + RTL) | P0 | FE | M7 |
| V2-FE-02 | Accessibility audit (WCAG 2.1 AA, rated B+) | P0 | FE | M7 |
| V2-FE-03 | Build optimization (chunk splitting, ES2020, hidden source maps) | P1 | FE | M7 |

### Wave 6 -- v2.0 Engineering: Production Infrastructure (M8)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-03 | TLS/HTTPS termination (nginx + Let's Encrypt) | P0 | DEVOPS | M8 |
| V2-04 | Production Docker Compose (hardened, profile-gated) | P0 | DEVOPS | M8 |
| V2-05 | Database migration system (migrate.py + migrations/) | P0 | BE | M8 |
| V2-06 | Automated backup & restore (backup.sh, restore.sh, cron) | P0 | DEVOPS | M8 |

### Wave 7 -- v2.0 QA: Load Testing & Performance (M9)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-07 | Load testing with k6 (4 scripts, thresholds, runner) | P0 | QA | M9 |

### Wave 7 -- v2.0 QA: Security Hardening (M10)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-08 | CI/CD pipeline hardening (E2E, integration, security, SBOM) | P0 | INFRA | M10 |

### Wave 7 -- v2.0 QA: Observability Stack (M11)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-09 | Runbook & incident response (591-line runbook, decision tree) | P0 | DEVOPS | M11 |
| V2-11 | Grafana dashboard templates (2 pre-built dashboards) | P1 | DEVOPS | M11 |
| V2-12 | Log aggregation with Loki (Promtail + 7-day retention) | P1 | DEVOPS | M11 |
| V2-13 | Alerting rules (6 Prometheus alert rules) | P1 | INFRA | M11 |

### Wave 8 -- v2.0 Release: Production Validation (M12)

| ID | Card | Priority | Owner | Milestone |
|----|------|----------|-------|-----------|
| V2-10 | Smoke test on deploy (--live mode, auth token, 4 checks) | P0 | QA | M12 |
| V2-15 | Secrets rotation automation (rotate-secrets.sh, zero-downtime) | P1 | INFRA | M12 |
| V2-RM-01 | Release checklist | P0 | RM | M12 |
| V2-RM-02 | Changelog (Keep a Changelog format) | P0 | RM | M12 |
| V2-RM-03 | Rollback procedures | P0 | RM | M12 |
| V2-RM-04 | GitHub release draft | P0 | RM | M12 |

---

## Summary Counts

| Column | Count |
|--------|-------|
| Backlog | 1 |
| Sprint Ready | 0 |
| In Progress | 0 |
| In Review | 0 |
| Testing | 0 |
| Done | 150 |
| Blocked | 0 |
| **Total** | **151** |

---

*Kanban Board v4.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
*Updated 2026-03-02 for v2.0 production hardening completion (V2-01 through V2-15 + RM cards)*
