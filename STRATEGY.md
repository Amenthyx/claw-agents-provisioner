# Full-Stack Team — Production Strategy for Claw Agents Provisioner v2.0

> Pre-configured for **Claw Agents Provisioner** — Python + Bash + Docker infrastructure with React wizard UI.
> Activate: `--team fullStack --strategy path/to/STRATEGY.md`

---

## 1. Project Identity

**Project Name**: Claw Agents Provisioner
**One-Line Vision**: One-command deployment of personalized AI agents — from client assessment to production-grade, monitored, secure agent fleet in under 15 minutes.
**Problem Statement**: v1.0 delivered assessment-driven deployment for dev/test environments. Enterprise customers now need production hardening: TLS termination, authenticated APIs, fleet observability, automated testing, disaster recovery, and compliance-grade audit trails — none of which exist in v1.0.
**Desired Outcome**: A production-grade platform where consultants deploy AI agents that enterprise IT teams can confidently run in production with monitoring, security, automated testing, and compliance documentation.
**Project Type**: Extending (v1.0 → v2.0 production hardening)
**Repository**: `Amenthyx/claw-agents-provisioner`

---

## 2. Target Audience

**Primary Users**: Amenthyx consultants deploying agents for enterprise clients
**Secondary Users**: Enterprise IT teams operating deployed agent fleets

| Persona | Role | Pain Points | Goals | Tech Savvy |
|---------|------|-------------|-------|------------|
| Marco | Amenthyx consultant | v1.0 agents lack TLS, monitoring, and audit trails — enterprise clients reject them in security reviews | Deploy production-hardened agents that pass enterprise security audits out of the box | High |
| Kai | Enterprise CTO | Needs SOC2/GDPR evidence, uptime SLAs, centralized monitoring, and incident response playbooks before approving agent deployment | Get compliance-ready agent infrastructure with dashboards and alerts | High (5/5) |
| Lucia | SMB owner (Private package) | Agent goes down at night, no alerting, no auto-recovery, no usage visibility | Reliable agent that self-heals and sends alerts when something breaks | Low (2/5) |
| DevOps Engineer | Client IT staff | No Prometheus metrics, no log aggregation, no health endpoints, manual restart on failures | Integrate agent fleet into existing monitoring stack (Grafana, PagerDuty) | High (5/5) |

**Anti-Users**: Hobbyists running agents locally for personal experimentation (v1.0 is sufficient for them)

---

## 3. Core Features (Prioritized)

### P0 — Must-Have (Launch Blockers)
| # | Feature | Description | Acceptance Criteria | Complexity |
|---|---------|-------------|---------------------|------------|
| 1 | TLS/HTTPS termination | Nginx reverse proxy with Let's Encrypt auto-renewal for all HTTP services (9090-9100) | All services accessible via HTTPS; HTTP redirects to HTTPS; cert auto-renews; zero-downtime renewal | L |
| 2 | End-to-end test suite | Pytest E2E tests covering: assessment → deploy → health check → chat → teardown lifecycle | >= 90% path coverage of deployment pipeline; tests run in CI in < 10 min; all 5 agents tested | XL |
| 3 | Load testing with k6 | k6 scripts for router, memory, RAG, dashboard endpoints under sustained load | P95 < 200ms at 100 req/s for router; P95 < 500ms at 50 req/s for RAG; results saved as CI artifact | M |
| 4 | Integration test suite | Test all service interactions: router→LLM, memory→SQLite, RAG→ingest→search, orchestrator→agent, billing→alerts | >= 80% integration path coverage; all cross-service flows tested; mocked external LLM APIs | L |
| 5 | Database migration system | Versioned SQLite→PostgreSQL migration scripts with rollback support for memory, billing, DAL | Forward + rollback tested for each migration; zero data loss; idempotent migrations | M |
| 6 | Automated backup & restore | Scheduled backup of SQLite DBs, port maps, instance configs; restore script with validation | Daily automated backup; restore tested in CI; backup size < 100 MB; RPO < 24h | M |
| 7 | Production Docker Compose | Hardened compose with TLS proxy, log drivers, restart policies, resource limits, named volumes, secrets management | `docker compose --profile production up` works on a clean Ubuntu 24.04; all services auto-restart on failure | L |
| 8 | CI/CD pipeline hardening | Add E2E tests, integration tests, load tests, security scan, SBOM validation, deployment smoke test to GitHub Actions | All test types run in CI; pipeline completes in < 20 min; blocking on HIGH/CRITICAL findings | M |
| 9 | Runbook & incident response | Operational runbook: service restart procedures, log locations, common failures, escalation matrix, rollback steps | Covers all 8 services; tested by QA; includes troubleshooting decision tree | S |
| 10 | Smoke test on deploy | Post-deployment automated smoke test: health endpoints, chat round-trip, memory write/read, RAG ingest/search | Smoke test runs automatically after `claw.sh deploy`; fails loudly on any check failure | S |

### P1 — Should-Have
| # | Feature | Description | Acceptance Criteria | Complexity |
|---|---------|-------------|---------------------|------------|
| 1 | Grafana dashboard templates | Pre-built Grafana JSON dashboards consuming Prometheus /metrics from all services | Import-ready; shows request rate, latency, error rate, memory usage per service | M |
| 2 | Log aggregation with Loki | Docker log driver → Loki → Grafana log explorer for all services | Searchable logs by service, severity, time range; 7-day retention default | M |
| 3 | Alerting rules | Prometheus alerting rules: service down > 2 min, error rate > 5%, memory > 90%, disk > 85% | Alerts fire within 3 min of condition; webhook notification to configured URL | S |
| 4 | Blue-green deployment support | Zero-downtime agent updates via container swap with health check gate | Agent update completes with zero dropped requests; automatic rollback on failed health check | L |
| 5 | Secrets rotation automation | Scheduled rotation of API keys, vault passwords, JWT tokens with zero-downtime reload | Rotation completes without service restart; old keys invalidated after grace period | M |

### P2 — Nice-to-Have
| # | Feature | Description |
|---|---------|-------------|
| 1 | Kubernetes Helm charts | K8s deployment for multi-node agent fleets with HPA |
| 2 | Ansible playbooks | Alternative to shell scripts for enterprise provisioning |
| 3 | ARM64 / Apple Silicon support | Verified builds and tests on ARM64 |
| 4 | Distributed tracing (OpenTelemetry) | Request tracing across service boundaries |

---

## 4. Technical Constraints *(configured for Claw Agents Provisioner)*

**Required Tech Stack**:
- **Language**: Python 3.8+ (stdlib only for shared modules), Bash (provisioning)
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 (wizard UI)
- **Database**: SQLite (default), PostgreSQL 16 (optional, via docker compose profile)
- **Containerization**: Docker + Docker Compose v2 with profiles
- **VM**: Vagrant + VirtualBox (Ubuntu 24.04 LTS)
- **Reverse Proxy**: Nginx (TLS termination)
- **Monitoring**: Prometheus (metrics), Grafana (dashboards), Loki (logs)

**Hosting/Infrastructure**:
- **Target**: Self-hosted on client infrastructure (bare metal, VM, or cloud)
- **Deployment**: Docker Compose (primary), Vagrant (secondary), bare metal (tertiary)
- **Domain**: Client-provided or localhost (dev)

**Integrations**:
| Service | Purpose | Auth Method | Rate Limits |
|---------|---------|-------------|-------------|
| Anthropic Claude | Primary LLM (Sonnet 4.6, Opus 4.6, Haiku 4.5) | Bearer API key (env) | Per-plan |
| OpenAI | Secondary LLM (GPT-4.1) | Bearer API key (env) | Per-plan |
| DeepSeek | Budget LLM (free tier) | Bearer API key (env) | 60 req/min |
| Ollama | Local LLM runtime | None (localhost) | N/A |
| PostgreSQL 16 | Production database (optional) | Connection string (env) | Pool max 50 |
| Prometheus | Metrics scraping | None (internal network) | N/A |
| Grafana | Dashboards + alerting | Admin password (env) | N/A |
| Loki | Log aggregation | None (internal network) | N/A |
| Let's Encrypt | TLS certificates | ACME HTTP-01 challenge | 5 certs/week/domain |

**Existing Codebase**: `C:\Users\Software Engineering\Desktop\claw-agents-provisioner` (~41K+ lines, 301+ files)

**Package Manager**: pip (Python), pnpm (wizard UI)

**Monorepo or Polyrepo**: Monorepo

---

## 5. Non-Functional Requirements *(configured for production)*

**Performance**:
- Router API response time P95 < 200ms (excluding LLM latency)
- Dashboard page load < 2s
- RAG search P95 < 500ms for 10K document corpus
- Memory search P95 < 100ms for 100K messages
- Sustained throughput: 100 requests/second on router
- Concurrent agents: 5 without host degradation (16 GB RAM host)

**Security**:
- Authentication: Bearer token (CLAW_API_TOKEN) for all HTTP services (already implemented)
- Authorization: Token-based access (single admin token for v2.0; RBAC deferred to v3.0)
- Data sensitivity: Client PII in assessments (encrypted at rest), API keys in vault
- Compliance: GDPR (EU data residency), HIPAA (PHI encryption), SOC2 (audit trails)
- Encryption: TLS 1.3 in transit (nginx), AES-256 at rest (vault), SQLite WAL mode
- Rate limiting: Sliding window per client (already implemented, configurable via env)
- Audit logging: Structured JSON with rotation (already implemented)
- PII detection: Regex-based scanning in security rules engine (already implemented)

**Scalability**:
- Expected launch deployments: 10-20 enterprise clients
- Expected 6-month deployments: 50-100 clients
- Expected 1-year deployments: 200+ clients
- Scaling strategy: Horizontal via multiple Docker hosts; vertical via PostgreSQL migration

**Availability**:
- Uptime target: 99.9% (8.76 hours downtime/year)
- RTO: 30 minutes (auto-restart via watchdog + Docker restart policies)
- RPO: 24 hours (daily automated backups)
- Multi-region: No (v2.0 is single-host; multi-region deferred to v3.0)

**Observability**:
- Logging: Structured JSON audit logs (claw_audit.py — already implemented)
- Metrics: Prometheus text format on /metrics (claw_metrics.py — already implemented on all 6 services)
- Health: Aggregated health check on port 9094 (claw_health.py — already implemented, 8 services)
- Dashboards: Grafana with pre-built templates (P1 — to be implemented)
- Alerting: Budget threshold alerts (claw_billing.py — already implemented); Prometheus rules (P1)

---

## 6. Testing Requirements *(configured for production readiness)*

**Test Coverage Target**: >= 85% line coverage (Python shared modules), >= 70% (wizard UI components)

**Required Test Types**:
- [x] Unit tests (pytest — already implemented, 16 modules, ~4,167 lines)
- [ ] Integration tests (pytest — cross-service flows, mocked LLM APIs)
- [ ] End-to-end tests (pytest + Docker — full deployment lifecycle)
- [ ] Performance / load tests (k6 — router, memory, RAG, dashboard)
- [x] API contract tests (OpenAPI 3.1.0 spec validation — already implemented, 61 endpoints)
- [ ] Security tests (Trivy container scan — already in CI; Bandit for Python; npm audit for wizard)
- [ ] Smoke tests (post-deployment automated validation)
- [x] Shell script tests (shellcheck — already in CI)
- [x] Dockerfile tests (hadolint — already in CI)
- [x] Python lint (ruff — already in CI)
- [x] Type checking (mypy — already in CI, informational mode)

**CI/CD Requirements**:
- [x] GitHub Actions (shellcheck, hadolint, ruff, pytest, Docker builds, Trivy, SBOM)
- [ ] Pre-commit hooks (ruff, shellcheck, mypy via pre-commit framework)
- [ ] Branch protection (require PR reviews, passing CI)
- [ ] Integration test stage (Docker Compose up → run tests → tear down)
- [ ] Load test stage (k6 against running services)
- [ ] Deployment smoke test (post-deploy validation)
- [ ] Security scan stage (Bandit + npm audit + Trivy)

**Testing Tools**: pytest, k6, Trivy, Bandit, shellcheck, hadolint, ruff, mypy, npm audit

---

## 7. Timeline & Milestones

**Hard Deadline**: Flexible — quality over speed

**Milestones**:
| # | Milestone | Target Date | Deliverables | Success Criteria |
|---|-----------|-------------|--------------|-----------------|
| M1 | Test Foundation | Week 1 | Integration test suite, E2E test framework, pytest fixtures for all services, test Docker Compose | >= 80% integration coverage; E2E framework runs full deploy cycle; CI passes |
| M2 | Production Infrastructure | Week 2 | Nginx TLS proxy, production Docker Compose, backup/restore, database migrations, secrets rotation | `docker compose --profile production up` on clean Ubuntu; HTTPS works; backup/restore round-trip tested |
| M3 | Load Testing & Performance | Week 3 | k6 test scripts, performance baselines, bottleneck fixes, load test CI stage | P95 targets met; load tests in CI; performance regression detection |
| M4 | Security Hardening | Week 3 | Bandit scan clean, pre-commit hooks, branch protection, security test stage, compliance evidence | Zero HIGH/CRITICAL findings; audit trail complete; GDPR/SOC2 evidence package |
| M5 | Observability Stack | Week 4 | Grafana dashboards, Loki log aggregation, Prometheus alerting rules, operational runbook | Dashboards show all 8 services; alerts fire within 3 min; runbook covers all failure modes |
| M6 | Production Validation | Week 4 | Smoke test suite, blue-green deploy support, final E2E on production compose, release candidate | All tests green; smoke test auto-runs; RC deployed and validated; documentation complete |

**Budget Constraints**:
- Infrastructure: $0 (self-hosted, Docker, free GitHub Actions)
- Third-party APIs: $0 repo-side (user-provided keys)
- Monitoring stack: $0 (Prometheus + Grafana + Loki are open source)
- TLS: $0 (Let's Encrypt)

---

## 7.1 Cost Approval & Payment Governance *(pre-configured)*

**Token Budget Tolerance**: < $30 total for full production hardening execution

**Payment Authorization Rules**:
- **Auto-approve threshold**: $0 (always ask)
- **Requires explicit approval**: All card payments, subscriptions, purchases
- **Forbidden without user present**: Any recurring subscription, any payment > $50

**External Service Payments**:
| Service | Expected Cost | Payment Method | Pre-Approved? |
|---------|--------------|----------------|---------------|
| GitHub Actions | $0 (free tier) | N/A | Yes |
| Docker Hub | $0 (public images) | N/A | Yes |
| Let's Encrypt | $0 (free) | N/A | Yes |
| Grafana Cloud | $0 (self-hosted) | N/A | Yes |

**Cost Estimation Detail Level**: Detailed per-wave breakdown

**If costs exceed estimate**: Stop and ask

---

## 8. Success Criteria

**Launch Criteria** (ALL must be true):
- [ ] All P0 features implemented and tested
- [ ] >= 85% backend test coverage (shared/ modules)
- [ ] >= 70% wizard UI test coverage
- [ ] Zero CRITICAL/HIGH security vulnerabilities (Trivy + Bandit clean)
- [ ] E2E tests pass for all 5 agent deployment flows
- [ ] Integration tests pass for all cross-service interactions
- [ ] Load test P95 targets met (router < 200ms, RAG < 500ms)
- [ ] Smoke test auto-runs after every deployment
- [ ] TLS/HTTPS working with auto-renewal
- [ ] Backup/restore tested and documented
- [ ] Database migrations reversible and tested
- [ ] Operational runbook complete and QA-validated
- [ ] OpenAPI spec up to date (61+ endpoints documented)
- [ ] All environment variables documented in .env.template
- [ ] Production Docker Compose validated on clean Ubuntu 24.04
- [ ] CI/CD pipeline completes in < 20 minutes
- [ ] Audit trail captures all API requests, auth events, security violations

**KPIs**:
| Metric | Target | How to Measure |
|--------|--------|----------------|
| Deployment success rate | 100% for Docker, 95% for Vagrant | E2E test pass rate in CI |
| Mean time to recovery (MTTR) | < 5 min (auto-restart) | Watchdog + Docker restart timing |
| API availability | 99.9% uptime | Health aggregator uptime tracking |
| Security scan findings | 0 HIGH/CRITICAL | Trivy + Bandit CI results |
| Test coverage (Python) | >= 85% | pytest-cov report |
| Test coverage (React) | >= 70% | vitest coverage report |
| Load test P95 (router) | < 200ms at 100 req/s | k6 summary output |
| Audit log completeness | 100% of requests logged | Compare request count vs audit entries |
| Backup restore success | 100% | Restore test in CI |

**Definition of Done**: An Amenthyx consultant can deploy a production-grade agent fleet on a client's clean Ubuntu 24.04 server using `docker compose --profile production up`, with HTTPS, monitoring dashboards, automated backups, audit trails, and alerting — all working out of the box with zero manual configuration beyond `.env`.

---

## 9. Reference & Inspiration

**Competitor/Reference Products**:
| Product | What to Learn | What to Avoid |
|---------|--------------|---------------|
| Coolify | Self-hosted PaaS with auto-TLS, health monitoring, one-click deploy | Over-complex UI for CLI-first product |
| Dokku | Git-push deployment, nginx auto-config, Let's Encrypt integration | No multi-service orchestration |
| Portainer | Docker fleet management, monitoring, alerting dashboards | Heavy Java runtime, enterprise-only features |
| n8n | Self-hosted automation with Docker Compose, env-based config, webhook health | Tight coupling to specific workflow engine |

**Design Inspiration**: Coolify's self-hosted deployment UX + Portainer's fleet monitoring

**Technical References**:
- Docker Compose production best practices (https://docs.docker.com/compose/production/)
- Nginx reverse proxy with Let's Encrypt (certbot documentation)
- k6 load testing patterns (https://k6.io/docs/test-types/)
- Prometheus + Grafana + Loki stack (https://grafana.com/docs/loki/)

---

## 10. Out of Scope

**Explicitly NOT building**:
1. Kubernetes / Helm charts (deferred to v3.0)
2. Multi-region deployment or geo-replication
3. Role-based access control (RBAC) beyond single admin token
4. Foundation model training or pre-training
5. Agent source code modifications (agents are installed as-is)
6. Custom domain registration or DNS management
7. Paid monitoring services (Datadog, New Relic)

**Deferred to future versions**:
1. v2.1: ARM64 / Apple Silicon verified support
2. v2.2: Ansible playbook alternatives
3. v3.0: Kubernetes Helm charts, RBAC, multi-region, distributed tracing (OpenTelemetry)

---

## 11. Risk & Constraints

**Known Risks**:
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| TLS cert renewal fails silently | M | H | Certbot cron + health check that verifies cert expiry > 7 days; alert on renewal failure |
| Load test reveals bottleneck in SQLite under concurrency | H | M | PostgreSQL migration path ready; WAL mode enabled; connection pooling via DAL |
| Docker Compose production profile breaks on older Docker versions | M | M | Pin minimum Docker 24.0+; document in README; validate in CI |
| Grafana/Loki adds significant resource overhead | M | L | Optional profile (not required for core functionality); resource limits set |
| E2E tests flaky due to timing-dependent Docker startup | H | M | Health-check gates before test execution; configurable startup timeout; retry with backoff |
| NanoClaw no-config architecture breaks production compose | H | H | Wrapper with sed/envsubst injection; fallback to semi-automated setup |
| Client PII in assessment accidentally committed | H | H | .gitignore patterns; CI PII scan; pre-commit hooks |
| LoRA adapter quality varies by domain | M | H | Pre-built adapters as baselines; quality validation step; system prompt fallback |
| Upstream agent breaking changes | H | M | Pin release tags; CI tests against pinned versions; compatibility matrix |
| Port conflicts on client machines | M | M | claw_ports.py auto-assignment; port_map.json persistence (already implemented) |

**Hard Constraints** (non-negotiable):
- Python shared modules use stdlib only (no pip dependencies except cryptography for vault)
- .env files and client assessments NEVER committed to git
- Each agent independently installable (no cross-agent dependencies)
- Install scripts idempotent (safe to run multiple times)
- All 50 datasets committed in-repo (not downloaded at runtime)
- Conventional commits enforced
- OpenAPI specification required for all REST API endpoints (already exists)

**Soft Constraints** (preferred but negotiable):
- Prefer Docker Compose over raw Docker commands
- Prefer SQLite for dev, PostgreSQL for production
- Prefer shell scripts over Python for provisioning
- Prefer QLoRA over LoRA when VRAM < 24 GB

---

## 11.1 Dynamic Agent Scaling *(pre-configured)*

**Allow PM to spawn extra agents?**: Yes, with TL approval
**Max concurrent agents**: 12

**Scaling triggers**:
- Feature complexity XL and splittable
- Wave falling behind timeline
- QA finds >= 5 blocking bugs

**Agent types the PM may add**:
- [x] Additional Backend Engineer (Python services, assessment pipeline)
- [x] Additional DevOps Engineer (Docker, nginx, monitoring stack)
- [x] Additional QA Engineer (pytest, k6, E2E)
- [x] Database Specialist (SQLite→PostgreSQL migration, query optimization)
- [x] Security Specialist (Bandit, Trivy, compliance evidence)
- [x] Frontend Engineer (React wizard UI testing)

**Scaling constraints**:
- Extra agents MUST appear in `COST_ESTIMATION.md` revision (re-approve if > 20% over)
- PM documents in `.team/SCALING_LOG.md`

---

## 12. Evidence & Proof Requirements *(configured for production)*

**Required evidence**:
- [x] Test coverage report (pytest-cov — HTML + lcov)
- [x] E2E test results (pytest HTML report)
- [x] k6 load test results (summary JSON + HTML)
- [x] OpenAPI specification (validated, up-to-date — already exists)
- [x] Security scan results (Trivy SARIF — already in CI; Bandit JSON)
- [x] Database migration log (all migrations listed, reversibility verified)
- [x] CI/CD pipeline results (all checks green)
- [x] Deployment log (production Docker Compose up evidence)
- [x] Architecture diagram (system components, data flow — already exists)
- [x] Backup/restore test log (round-trip verification)
- [x] TLS certificate validation (HTTPS working, cert details)
- [x] Audit trail sample (structured JSON entries from audit.log)
- [x] Health check evidence (all 8 services healthy screenshot)
- [x] Prometheus metrics sample (/metrics output from all services)
- [x] Runbook QA sign-off (tested by QA engineer)

**Reporting Frequency**: Every wave completion

**Final Deliverable**: PPTX + PDF (both)

---

## 12.1 Data Preservation & Uncertainty Policy *(pre-configured)*

**Data Preservation (No-Delete Rule)**:
- **Files**: archive to `.team/archive/` — NEVER delete
- **Table rows**: add `status: archived` — NEVER remove
- **Documents**: add `[ARCHIVED]` marker — NEVER erase
- **Git history**: NEVER rebase/squash published commits

**Uncertainty Escalation**:
- **Threshold**: < 90% confidence → escalate to TL → user
- **Response time**: Minutes (async via GitHub issue)
- **Format**: Detailed context + options

---

## 13. GitHub Auto-Sync Policy *(pre-configured)*

**Auto-sync frequency**: Every agent completion
**Auto-push enabled?**: Yes
**Branch**: `ai-team` (MANDATORY — all teams use this branch)
**Merge to main**: ONLY after Team Leader receives explicit user approval (hard gate)

**What gets auto-synced**:
- [x] `.team/` planning artifacts
- [x] `.team/evidence/` proof artifacts
- [x] Source code changes
- [x] `.team/COMMIT_LOG.md` updates
- [x] `.team/reports/` PPTX + PDF
- [x] `COST_ESTIMATION.md` and revisions

---

## 14. Additional Context

### Already Implemented (v1.x — do NOT rebuild)
These features are already production-quality and should be leveraged, not reimplemented:

| Feature | Module | Status |
|---------|--------|--------|
| Bearer token auth | `claw_auth.py` | Done — all 6 services |
| Sliding window rate limiting | `claw_ratelimit.py` | Done — all 6 services |
| Prometheus metrics (/metrics) | `claw_metrics.py` | Done — all 6 services |
| Structured audit logging | `claw_audit.py` | Done — router, security, vault |
| Health aggregator (8 services) | `claw_health.py` | Done — port 9094 |
| Budget alerting + webhooks | `claw_billing.py` | Done — 80/90/100% thresholds |
| Centralized port management | `claw_ports.py` | Done — auto-assignment when busy |
| OpenAPI 3.1.0 spec (61 endpoints) | `docs/openapi.yaml` | Done — Swagger UI at /docs |
| CLI autocomplete (bash + zsh) | `completions/` | Done |
| Container scanning (Trivy) | `.github/workflows/ci.yml` | Done — HIGH/CRITICAL blocking |
| SBOM generation (CycloneDX) | `.github/workflows/ci.yml` | Done — 90-day artifact |
| Type hints (5 core modules) | `mypy.ini` | Done — informational CI step |
| Narrowed exception handling | 17 shared modules | Done — specific exception types |
| Pinned Python dependencies | `finetune/requirements.txt` | Done — exact versions |
| Security rules engine | `claw_security.py` | Done — URL/content/PII/IP blocking |
| Encrypted secrets vault | `claw_vault.py` | Done — AES encryption |
| Process watchdog | `claw_watchdog.py` | Done — auto-restart on failure |

### Production Gap Analysis
These are the gaps between current state and production-ready:

| Gap | Priority | Effort | Milestone |
|-----|----------|--------|-----------|
| No TLS/HTTPS | P0 | L | M2 |
| No integration tests | P0 | L | M1 |
| No E2E tests | P0 | XL | M1 |
| No load tests | P0 | M | M3 |
| No database migrations | P0 | M | M2 |
| No backup/restore | P0 | M | M2 |
| No production Docker Compose | P0 | L | M2 |
| No smoke tests | P0 | S | M6 |
| No operational runbook | P0 | S | M5 |
| No pre-commit hooks | P1 | S | M4 |
| No Grafana dashboards | P1 | M | M5 |
| No log aggregation | P1 | M | M5 |
| No alerting rules | P1 | S | M5 |
| No blue-green deploy | P1 | L | M6 |

---

*Claw Agents Provisioner Production Strategy v2.0 — Amenthyx AI Teams*
*Extending v1.0 → v2.0 for production-grade deployment*
*Cost-First | No-Delete | Ask-When-Unsure | ai-team Branch | Merge-Gated | Auto-Synced | Dynamically Scaled | Evidence-Driven*
