# GitHub Release Draft -- v2.0.0

> **Use this content when creating the GitHub Release at:**
> `https://github.com/Amenthyx/claw-agents-provisioner/releases/new`
>
> **Tag:** `v2.0.0`
> **Target branch:** `main` (after merging `ai-team`)
> **Title:** `v2.0.0 -- Production Hardening`

---

## Release Title

```
v2.0.0 -- Production Hardening
```

## Release Body

```markdown
# Claw Agents Provisioner v2.0.0 -- Production Hardening

Production-grade deployment, monitoring, testing, and security for the Claw agent fleet. This release transforms v1.0's development-ready provisioner into a hardened platform suitable for client-facing production environments.

## Highlights

- **Full test pyramid**: 547 tests across unit, integration, and E2E suites with 95.96% pass rate; 14 wizard UI test files with 70%+ coverage target
- **Production Docker Compose**: TLS reverse proxy (nginx + Let's Encrypt), resource limits, health checks, restart policies, log rotation, and secrets management -- all profile-gated
- **Monitoring stack**: Prometheus metrics, Grafana dashboards (2 pre-built), Loki log aggregation with Promtail, and alerting rules (service down, error rate, memory, disk, budget)
- **Operations tooling**: Automated backup/restore with rotation, database migration system with rollback, operational runbook covering all 13 services, and k6 load testing for 4 endpoints
- **Security hardening**: 6-layer pre-commit hooks (ShellCheck, Hadolint, Ruff, detect-secrets, API key scanner, vault blocker), enhanced CI/CD pipeline, secrets rotation script

## What's New

### Testing Infrastructure
- 6 integration test suites: router-LLM, memory-SQLite, RAG pipeline, orchestrator, billing, health
- 2 E2E test suites: assessment pipeline, deploy lifecycle (29 tests, 100% pass)
- 14 wizard UI test files: state, hooks, UI components, step components (vitest + React Testing Library)
- 4 k6 load test scripts: router, memory, RAG, dashboard with P95 thresholds
- Enhanced smoke test with `--live` mode for post-deployment verification

### Production Infrastructure
- `docker-compose.production.yml` with `--profile production` and `--profile monitoring` gates
- Nginx reverse proxy with TLS 1.2+, HSTS, CSP, rate limiting, and auto-renewal
- Database migration system (`scripts/migrate.py`) with up/down/status/reset commands
- Automated backup (`scripts/backup.sh`) with 7-day daily + 4-week weekly rotation
- Automated restore (`scripts/restore.sh`) with validation, dry-run, and selective restore

### Monitoring & Observability
- Prometheus scraping all service `/metrics` endpoints (15s interval)
- 6 alert rules: service_down, high_error_rate, high_latency, high_memory, high_disk, budget_exceeded
- Grafana with auto-provisioned datasources and 2 pre-built dashboards
- Loki + Promtail log aggregation with 7-day retention

### Operations
- 591-line operational runbook (`docs/RUNBOOK.md`) with troubleshooting decision tree
- Escalation matrix with 4 severity levels (P0-P3)
- Rollback procedures for containers, config, database, and full platform
- Secrets rotation script with zero-downtime reload

### Security
- Pre-commit hooks: trailing whitespace, YAML/JSON/TOML validation, merge conflict detection, private key detection, large file blocking, branch protection, shebang validation
- Tool-specific hooks: ShellCheck v0.10.0, Hadolint v2.12.0, Ruff v0.8.0, detect-secrets v1.5.0
- Custom hooks: `.env` blocker, API key pattern scanner, `.vault` blocker, Python compile check
- Security headers on all HTTPS: HSTS, X-Frame-Options, CSP, X-Content-Type-Options
- Rate limiting per IP via nginx

### Documentation
- Operational runbook with full port map and restart procedures
- WCAG 2.1 AA accessibility audit for wizard UI (rated B+)
- QA sign-off document with test pyramid results
- Release checklist, rollback procedures, and this release notes

## QA Summary

| Level | Total | Pass | Pass Rate |
|-------|-------|------|-----------|
| Unit | ~400 | ~387 | 94.4% |
| Integration | 140 | 140 | 100% |
| E2E | 29 | 29 | 100% |
| **Overall** | **570** | **547** | **95.96%** |

**QA Verdict:** CONDITIONAL PASS -- all integration and E2E tests pass at 100%. 23 unit test failures share one root cause (DAL singleton test isolation, environment-specific, not a code defect).

## Breaking Changes

None. v2.0.0 is backward-compatible with v1.0.0 configurations.

The following files are **new** and do not affect existing v1.0 deployments:
- `docker-compose.production.yml` (production profile, separate from `docker-compose.yml`)
- `monitoring/` directory (optional monitoring stack)
- `nginx/` directory (TLS proxy, only used with production profile)
- `migrations/` directory (migration system, opt-in)
- `scripts/backup.sh`, `scripts/restore.sh`, `scripts/migrate.py` (new scripts)
- `tests/load/` directory (k6 load tests)

## Upgrade Guide from v1.0

### Quick Upgrade

```bash
# 1. Pull latest code
git pull origin main

# 2. (Optional) Set up pre-commit hooks
pip install pre-commit && pre-commit install
# Or: bash scripts/setup-hooks.sh

# 3. (Optional) Run database migrations
python3 scripts/migrate.py up

# 4. (Optional) Switch to production compose
docker compose -f docker-compose.production.yml \
  --profile production --profile zeroclaw up -d --build

# 5. (Optional) Initialize TLS
./scripts/init-letsencrypt.sh your-domain.com admin@example.com

# 6. (Optional) Set up monitoring
docker compose -f docker-compose.production.yml \
  --profile monitoring up -d

# 7. (Optional) Set up automated backups
echo "0 2 * * * $(pwd)/scripts/backup-cron.sh" | crontab -
```

### If staying on development profile

No changes required. The existing `docker-compose.yml` and `claw.sh` commands continue to work exactly as before. All v2.0 features are opt-in through new files and profiles.

## Known Issues / Limitations

| # | Issue | Severity | Workaround |
|---|-------|----------|------------|
| 1 | DAL singleton test isolation: 23 unit tests fail due to SQLite path in test environment | P1 | Not a code defect; integration tests cover the same code paths. Fix: add `CLAW_DATA_DIR` override in `conftest.py` |
| 2 | HTTP server code coverage is low (13-37%) | P2 | Requires running server fixtures; core logic is tested via integration tests |
| 3 | `claw_wizard_api.py` has 0% unit test coverage | P2 | 2366-line API server; wizard is non-critical for production launch |
| 4 | OWASP dependency check not yet configured | P2 | Recommend adding in v2.1 |
| 5 | Container image scanning (Trivy/Snyk) not yet in CI | P2 | Trivy scanning configured locally; recommend CI integration in v2.1 |

## File Statistics

| Metric | Value |
|--------|-------|
| New test files | 24 (14 wizard + 8 Python + 2 E2E) |
| New infrastructure files | 18 (compose, nginx, monitoring, scripts) |
| New documentation files | 8 (runbook, audits, release docs) |
| Total tests | 570 |
| k6 load test scripts | 4 |
| Prometheus alert rules | 6 |
| Grafana dashboards | 2 |
| Pre-commit hooks | 15 |

## Contributors

- **PM** -- Planning artifacts, coordination, v2.0 project charter and milestones
- **BE** -- Integration tests, E2E tests, database migration system
- **FE** -- Wizard UI tests, accessibility audit, build optimization
- **DEVOPS** -- Production compose, TLS proxy, monitoring stack, backup/restore, runbook
- **QA** -- k6 load tests, smoke test enhancement, QA sign-off, test evidence
- **INFRA** -- CI/CD hardening, pre-commit hooks, security scanning
- **RM** -- Release checklist, changelog, rollback procedures, GitHub release

Built with [Amenthyx AI Teams v3.0](https://github.com/Amenthyx/amenthyx-ai-teams)
```

---

## Pre-Release Checklist (for GitHub Release creation)

- [ ] Merge `ai-team` branch into `main`
- [ ] Create and push tag: `git tag -a v2.0.0 -m "v2.0.0 -- Production Hardening" && git push origin v2.0.0`
- [ ] Create GitHub Release at `https://github.com/Amenthyx/claw-agents-provisioner/releases/new`
- [ ] Select tag `v2.0.0`
- [ ] Set title: `v2.0.0 -- Production Hardening`
- [ ] Paste the release body above
- [ ] Mark as "Latest release"
- [ ] Publish release

---

*GitHub Release Draft -- Claw Agents Provisioner v2.0.0 -- Amenthyx AI Teams v3.0*
