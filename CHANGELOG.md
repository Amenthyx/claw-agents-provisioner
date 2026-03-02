# Changelog

All notable changes to the Claw Agents Provisioner will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] -- 2026-03-02

### Added

#### Testing Infrastructure (Wave 6 -- M7)

- **Integration test suite** with 6 cross-service test files covering router-LLM, memory-SQLite, RAG ingest-search, orchestrator-agent, billing-alerts, and health aggregation (`tests/test_integration_*.py`)
- **E2E test suite** with 2 end-to-end test files covering the full assessment pipeline and deploy lifecycle (`tests/test_e2e_*.py`)
- **Pytest fixtures** with mocked external LLM API responses, DAL singleton bypass for test isolation, and shared test configuration (`tests/conftest.py`)
- **152 new test cases** (140 integration + 29 E2E = 169 total new tests; 547/570 overall passing)
- **Wizard UI test suite** with 14 test files using vitest, React Testing Library, jsdom, and istanbul coverage (`wizard/src/**/*.test.{ts,tsx}`)
  - State tests: reducer, validation, context
  - Hook tests: useDeploy
  - UI component tests: Button, Input, Toggle, Card
  - Step component tests: Welcome, Platform, Deployment, LLM, Security
- **k6 load test scripts** for 4 HTTP services: router, memory, RAG, dashboard (`tests/load/k6-*.js`)
- **Shared k6 config module** with auth token injection, per-service thresholds, custom metrics, and Grafana-compatible tags (`tests/load/k6-config.js`)
- **Sequential load test runner** with JSON output aggregation (`tests/load/run-load-tests.sh`)
- **Enhanced smoke test** with post-deployment live service verification (`scripts/smoke-test.sh --live`)
  - Health endpoint probes for all 6 services
  - Chat round-trip test (router -> LLM)
  - Memory write/read cycle
  - RAG ingest/search cycle
  - Auth token support (`--token` flag)

#### Production Infrastructure (Wave 6 -- M8)

- **Production Docker Compose** (`docker-compose.production.yml`) with:
  - TLS reverse proxy (nginx with Let's Encrypt)
  - Log drivers with rotation (json-file, 10 MB x 5 files per container)
  - Restart policies (`unless-stopped` on all services)
  - Resource limits (memory + CPU reservations per service)
  - Named volumes for persistent data
  - Health checks on all services
  - Profile-gated service groups (`--profile production`, `--profile monitoring`)
  - Secrets management via env files with vault override
- **Nginx TLS reverse proxy** (`nginx/`) with:
  - Let's Encrypt auto-renewal via certbot with daily cron
  - TLS 1.2+ enforcement with modern cipher suite
  - HTTP-to-HTTPS redirect
  - Reverse proxy to all 8 backend services
  - Rate limiting per IP
  - Security headers: HSTS, X-Frame-Options, CSP, X-Content-Type-Options
  - Custom Dockerfile based on nginx:1.25-alpine
- **TLS initialization script** (`scripts/init-letsencrypt.sh`) with staging/production modes
- **Database migration system** (`scripts/migrate.py`, `migrations/`) with:
  - Versioned migration scripts with `up()` and `down()` functions
  - Forward and rollback support for memory, billing, audit, orchestrator databases
  - Status reporting, reset command, and per-database targeting
  - Idempotent execution (safe to run multiple times)
  - Initial schema migration (`migrations/001_initial_schema.py`)
- **Automated backup system** (`scripts/backup.sh`) with:
  - Timestamped archives for SQLite databases, configs, and port maps
  - Selective backup (`--db-only`, `--config-only`)
  - Rotation policy: 7 daily + 4 weekly backups retained
- **Automated restore** (`scripts/restore.sh`) with:
  - Validation of archive integrity before restore
  - Selective restore (`--db-only`)
  - Dry-run support (`--dry-run`)
  - Backup listing (`--list`)
- **Backup cron wrapper** (`scripts/backup-cron.sh`) with:
  - Lock files to prevent concurrent backups
  - Webhook failure notifications
  - Daily scheduling at 02:00

#### Monitoring and Observability (Wave 6/7 -- M11)

- **Prometheus monitoring** (`monitoring/prometheus/`) with:
  - Service discovery scraping all `/metrics` endpoints (15-second interval)
  - Alert rules: service down > 2 min, error rate > 5%, P95 latency exceeded, memory > 90%, disk > 85%, billing budget exceeded
  - Configuration for all 8 platform services
- **Grafana dashboards** (`monitoring/grafana/dashboards/`) with:
  - "Claw Platform Overview" -- high-level health, request rates, error rates
  - "Claw Service Details" -- per-service drill-down with logs integration
  - Auto-provisioned Prometheus + Loki datasources
  - Import-ready JSON dashboard definitions
- **Loki log aggregation** (`monitoring/loki/`) with:
  - 7-day retention policy
  - Searchable logs by service, severity, and time range
  - Promtail Docker log collector (`monitoring/promtail/`)
- **Monitoring Docker Compose** (`monitoring/docker-compose.monitoring.yml`) as standalone stack

#### Operations (Wave 7 -- M11)

- **Operational runbook** (`docs/RUNBOOK.md`) covering:
  - Service architecture with full port map (13 services)
  - Service restart procedures (single, all, monitoring, emergency)
  - Log locations and searching (Docker logs, host files, Loki)
  - Health check verification (quick, Docker, port, end-to-end)
  - Troubleshooting decision tree for 7 common failure patterns
  - Backup and restore operations with commands
  - TLS certificate management (setup, check, renew, auto-renew)
  - Monitoring stack operations (start, stop, reload, retention)
  - Rollback procedures (container, config, data, full platform)
  - Escalation matrix with 4 severity levels and communication template

#### QA and Evidence (Wave 7 -- M9/M10)

- **QA test report** (`.team/evidence/tests/qa-test-report.md`) with full test pyramid results
- **QA sign-off document** (`.team/qa/QA_SIGNOFF.md`) -- CONDITIONAL PASS, 547/570 tests passing
- **Load test configuration documentation** (`.team/evidence/tests/load-test-config.md`)
- **Bug report** for DAL singleton test isolation issue (`.team/qa/BUG_REPORT.md`)
- **Accessibility audit** (`.team/evidence/validation/accessibility-audit.md`) -- WCAG 2.1 AA assessment, rated B+

#### Release Management (Wave 8 -- M12)

- **Release checklist** (`.team/releases/RELEASE_CHECKLIST.md`)
- **Rollback procedures** (`.team/releases/ROLLBACK_PROCEDURES.md`)
- **GitHub release draft** (`.team/releases/GITHUB_RELEASE_DRAFT.md`)
- **Changelog** (`CHANGELOG.md`) -- this file

### Changed

- **CI/CD pipeline** (`.github/workflows/ci.yml`) enhanced with:
  - Integration test stage
  - E2E test stage
  - Wizard UI test stage
  - Security scan stage (detect-secrets, API key patterns)
  - SBOM validation
  - Deployment smoke test stage
  - Concurrency control (cancel-in-progress for same branch)
- **Pre-commit hooks** (`.pre-commit-config.yaml`) hardened with:
  - pre-commit-hooks v4.6.0: trailing whitespace, YAML/JSON/TOML checks, merge conflict detection, private key detection, large file blocking (5 MB), branch protection (no direct commits to main), shebang validation
  - ShellCheck v0.10.0 with `--severity=warning`
  - Hadolint v2.12.0 with `--failure-threshold=warning`
  - Ruff v0.8.0 with `--fix` auto-correction and format checking
  - detect-secrets v1.5.0 with baseline file
  - Custom local hooks: `.env` file blocker, API key pattern scanner, vault file blocker, Python compile check
- **Vault module** (`shared/claw_vault.py`) enhanced with secrets rotation support
- **Secrets rotation script** (`scripts/rotate-secrets.sh`) added for zero-downtime API key, vault password, and JWT token rotation
- **Smoke test** (`scripts/smoke-test.sh`) enhanced with post-deployment live verification mode
- **`.gitignore`** updated for test artifacts, coverage reports, and monitoring data volumes

### Security

- **Bandit scanning** configured for Python security analysis via `scripts/security-scan.sh`
- **Dependency pinning** enforced in `finetune/requirements.txt` and wizard `package.json`
- **SBOM generation** integrated into CI pipeline
- **TLS 1.2+ enforcement** with modern cipher suite (ECDHE-ECDSA-AES128-GCM-SHA256, etc.)
- **Security headers** on all HTTPS responses: HSTS (max-age=31536000), X-Frame-Options (SAMEORIGIN), X-Content-Type-Options (nosniff), Content-Security-Policy, Referrer-Policy
- **Rate limiting** per IP via nginx (`limit_req_zone`)
- **detect-secrets** pre-commit hook with baseline to prevent secret leakage
- **API key pattern scanner** blocks commits containing `sk-ant-`, `sk-or-`, `xoxb-`, `hf_` patterns
- **Vault file blocker** prevents `.vault` files from being committed
- **Branch protection** via `no-commit-to-branch` hook (blocks direct commits to `main`)

### Documentation

- **Operational runbook** (`docs/RUNBOOK.md`) -- 591 lines covering all services, troubleshooting, and escalation
- **Accessibility audit** (`.team/evidence/validation/accessibility-audit.md`) -- WCAG 2.1 AA compliance report
- **QA sign-off** (`.team/qa/QA_SIGNOFF.md`) -- formal sign-off with conditions
- **Load test documentation** (`.team/evidence/tests/load-test-config.md`)
- **Release checklist** (`.team/releases/RELEASE_CHECKLIST.md`)
- **Rollback procedures** (`.team/releases/ROLLBACK_PROCEDURES.md`)

---

## [1.0.0] -- 2026-02-26

### Added

#### Agent Platforms (Waves 2-3 -- M1-M3)

- **ZeroClaw** provisioner (Rust-based, lightweight, 512 MB memory limit)
  - Vagrantfile, Dockerfile, install script, entrypoint, config templates
  - Ubuntu 24.04 base, rust:slim Docker image
- **NanoClaw** provisioner (TypeScript, Docker-outside-of-Docker, 1 GB memory limit)
  - Vagrantfile, Dockerfile, install script, entrypoint with `sed`/`envsubst` config injection
  - Node.js 22-slim Docker image
- **PicoClaw** provisioner (Go-based, edge/IoT, 128 MB memory limit)
  - Vagrantfile, Dockerfile, install script, entrypoint
  - golang:1.21-alpine Docker image, < 30 MB RAM target
- **OpenClaw** provisioner (TypeScript, feature-rich, 4 GB memory limit)
  - Vagrantfile, Dockerfile, install script, entrypoint
  - Node.js 22-slim Docker image, 8 GB+ host RAM warning
- **Parlant** provisioner (Python, conversational, 2 GB memory limit)
  - Configuration templates and entrypoint

#### Unified Launcher

- `claw.sh` unified CLI launcher routing to correct provisioning method
- `claw.sh <agent> [vagrant|docker]` syntax for all agents
- `claw.sh deploy --assessment <file>` for automated deployment from assessment
- `claw.sh validate --assessment <file>` for assessment validation
- `claw.sh datasets [--list|--validate|--download-all|--stats]` commands
- `claw.sh finetune [--assessment|--adapter <use-case>|--dry-run]` commands
- `claw.sh <agent> destroy` teardown functionality

#### Infrastructure

- Unified `.env.template` with all agent + service + fine-tuning configuration sections
- `shared/provision-base.sh` base provisioning script
- `shared/healthcheck.sh` unified health check for all agents
- `docker-compose.yml` with profile-gated multi-agent support
- `docker-compose.secrets.yml` for Docker secrets integration
- Smart port management with auto-assignment (`shared/claw_ports.py`)
- `install.sh` interactive installer for full project setup

#### Assessment Pipeline (Wave 2 -- M4)

- Assessment JSON schema (`assessment/schema/assessment-schema.json`)
- Schema validator (`assessment/validate.py`)
- Platform/model/skills resolver (`assessment/resolve.py`)
- Environment variable generator (`assessment/generate_env.py`)
- Agent config generator (`assessment/generate_config.py`)
- Needs-mapping-matrix with 15 client profiles
- 3 example assessments: Real Estate, IoT/RPi, DevSecOps
- Skills auto-installer (`shared/skills-installer.sh`)

#### Fine-Tuning Pipeline (Wave 2 -- M5b)

- LoRA training script (`finetune/train_lora.py`)
- QLoRA training script (`finetune/train_qlora.py`)
- Adapter merge script (`finetune/merge_adapter.py`)
- Dataset generator from assessment (`finetune/dataset_generator.py`)
- Fine-tuning Dockerfile (`finetune/Dockerfile.finetune`)
- Adapter loading in all 4 agent entrypoints
- TensorBoard training log integration

#### Datasets (Waves 2-3 -- M5a)

- **50 use-case datasets** with real HuggingFace data (5,000 rows each, 250,000 total)
- Dataset download script (`finetune/download_datasets.py`)
- Dataset validation script (`finetune/validate_datasets.py`)
- **50 adapter config bundles** (adapter_config.json, system_prompt.txt, training_config.json per use case)
- Dataset catalog README (`finetune/datasets/README.md`)
- Adapter catalog README (`finetune/adapters/README.md`)
- All datasets committed in-repo (no external downloads required)

#### Enterprise Services

- **Gateway Router** (`shared/claw_router.py`) -- multi-model routing with fallback chains
- **Memory Service** (`shared/claw_memory.py`) -- persistent conversation memory with SQLite
- **RAG Service** (`shared/claw_rag.py`) -- document ingestion and semantic search
- **Dashboard** (`shared/claw_dashboard.py`) -- fleet management and monitoring
- **Orchestrator** (`shared/claw_orchestrator.py`) -- multi-agent coordination
- **Billing Service** (`shared/claw_billing.py`) -- usage tracking, budget alerts, cost optimization
- **Optimizer** (`shared/claw_optimizer.py`) -- multi-model cost optimization engine
- **Wizard API** (`shared/claw_wizard_api.py`) -- guided setup wizard backend
- **Health Aggregator** (`shared/claw_health.py`) -- unified health status for all services
- **Watchdog** (`shared/claw_agent_stub.py`) -- zero-token process reliability monitor
- **Data Access Layer** (`shared/claw_dal.py`) -- connection pooling and query caching
- **Security Module** (`shared/claw_security.py`) -- vault, rules engine, multi-model optimizer
- **Auth Module** (`shared/claw_auth.py`) -- Bearer token authentication
- **Rate Limiter** (`shared/claw_ratelimit.py`) -- sliding window rate limiting
- **Audit Module** (`shared/claw_audit.py`) -- request and event logging
- **Metrics Module** (`shared/claw_metrics.py`) -- Prometheus-compatible metrics
- **Storage Layer** (`shared/claw_storage.py`) -- shared database and file storage
- **Hardware Detection** (`shared/claw_hardware.py`) -- hardware-aware LLM runtime recommendation
- **Adapter Selector** (`shared/claw_adapter_selector.py`) -- dynamic adapter selection

#### Wizard UI

- React wizard UI with cyberpunk visual theme (framer-motion animations)
- Gateway configuration step
- Post-deploy health checks in wizard
- Responsive layout with Lucide React icons

#### CI/CD (Wave 5 -- M6)

- GitHub Actions CI pipeline (`.github/workflows/ci.yml`)
- ShellCheck, Hadolint, Ruff linting in CI
- Assessment pipeline validation in CI
- Dataset validation (50 datasets) in CI
- Security scan (no secrets/PII) in CI
- Pre-commit hooks configuration (`.pre-commit-config.yaml`)

#### Documentation

- Comprehensive `README.md` with quickstart, per-agent setup, assessment workflow, fine-tuning guide
- `.ai/context_base.md` for AI agent context
- 3 end-to-end assessment walkthroughs (Real Estate, IoT, DevSecOps)
- Troubleshooting guide
- Apache-2.0 LICENSE

#### QA (Wave 4 -- M6)

- 50-item full project audit
- 5 CRITICAL issue fixes (entrypoint scripts)
- 6 HIGH issue fixes (configs, pipeline, security)
- Dataset validation (50/50 pass, 250K rows)
- Assessment pipeline E2E test

### Changed

- Port management centralized with auto-assignment (watchdog 9097 -> 9090)
- Unified Data Access Layer replaces per-service database handling

### Security

- Bearer token authentication on all HTTP services
- Sliding window rate limiting on all endpoints
- Security vault with encrypted credential storage
- Trivy container scanning in CI
- Python dependency pinning
- `.gitignore` blocks `.env`, `.vault`, and credential files

---

## [0.1.0] -- 2026-02-26

### Added

- Initial project scaffold and strategy document (`STRATEGY.md`)
- Planning artifacts: Project Charter, Milestones, Kanban, Timeline, Risk Register
- Team structure and role assignments
- Competitive analysis, market positioning, launch plan
- Compliance review, data privacy assessment, license matrix
- Cost estimation for v2.0 production hardening

---

*Changelog -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
