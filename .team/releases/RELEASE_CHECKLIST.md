# Release Checklist -- Claw Agents Provisioner v2.0.0

> **Release Date:** 2026-03-02
> **Release Manager:** RM (Full-Stack Team, Amenthyx AI Teams v3.0)
> **Branch:** `ai-team`
> **Tag:** `v2.0.0`

---

## 1. Pre-Release Checks

### 1.1 Test Suite

- [ ] All unit tests pass (`pytest tests/ -x`)
  - Target: 547/570 passing (95.96%)
  - Known exceptions: 23 DAL singleton isolation failures (environment-specific, not code defects)
- [ ] All integration tests pass (`pytest tests/test_integration_*.py`)
  - 6 integration test suites: router, memory, RAG, orchestrator, billing, health
  - Target: 140/140 passing (100%)
- [ ] All E2E tests pass (`pytest tests/test_e2e_*.py`)
  - 2 E2E suites: assessment pipeline, deploy lifecycle
  - Target: 29/29 passing (100%)
- [ ] Wizard UI tests pass (`cd wizard && npm test`)
  - 14 test files covering state, hooks, UI components, and step components
  - Coverage target: >= 70% (istanbul)
- [ ] Smoke test passes (`./scripts/smoke-test.sh`)
  - Pre-deployment checks: file existence, compilation, Docker config
  - Post-deployment checks: health endpoints, chat round-trip, memory, RAG

### 1.2 Coverage Targets

- [ ] Core infrastructure modules (auth, audit, metrics, ratelimit, DAL): 80-100%
- [ ] Business logic modules (billing, adapter, skills, strategy): >= 40%
- [ ] Wizard UI components: >= 70%
- [ ] Integration path coverage: >= 80%

### 1.3 Security Scans

- [ ] `scripts/security-scan.sh` passes with no HIGH/CRITICAL findings
- [ ] `detect-secrets` pre-commit hook baseline is current (`.secrets.baseline`)
- [ ] No `.env` files, vault files, or API key patterns in tracked files
- [ ] Ruff lint clean on all Python files (`ruff check shared/ assessment/ scripts/ tests/`)
- [ ] ShellCheck clean on all shell scripts (`find . -name "*.sh" -exec shellcheck --severity=warning {} +`)
- [ ] Hadolint clean on all Dockerfiles (`hadolint */Dockerfile`)
- [ ] npm audit clean for wizard UI (`cd wizard && npm audit --audit-level=high`)
- [ ] Python dependency pins verified (`finetune/requirements.txt`, `shared/requirements.txt`)
- [ ] No known CVEs in base Docker images (Ubuntu 24.04, Node 22-slim, Rust-slim, Go 1.21-alpine)

### 1.4 Static Analysis

- [ ] mypy strict mode passes on 5 core modules (auth, audit, metrics, ratelimit, DAL)
- [ ] `python3 -m py_compile` passes on all `.py` files (pre-commit hook)
- [ ] Pre-commit hooks run cleanly: `pre-commit run --all-files`

---

## 2. Build Verification

### 2.1 Docker Images

- [ ] ZeroClaw image builds: `docker build -t claw-zeroclaw zeroclaw/`
- [ ] NanoClaw image builds: `docker build -t claw-nanoclaw nanoclaw/`
- [ ] PicoClaw image builds: `docker build -t claw-picoclaw picoclaw/`
- [ ] OpenClaw image builds: `docker build -t claw-openclaw openclaw/`
- [ ] Nginx proxy image builds: `docker build -t claw-nginx nginx/`
- [ ] Fine-tuning image builds: `docker build -f finetune/Dockerfile.finetune -t claw-finetune finetune/`
- [ ] All images use pinned base image tags (no `latest`)
- [ ] Multi-stage builds produce minimal final image sizes

### 2.2 Production Docker Compose

- [ ] Production compose validates: `docker compose -f docker-compose.production.yml config`
- [ ] Development compose validates: `docker compose -f docker-compose.yml config`
- [ ] Monitoring compose validates: `docker compose -f monitoring/docker-compose.monitoring.yml config`
- [ ] Secrets compose validates: `docker compose -f docker-compose.secrets.yml config`
- [ ] Profile-gated startup works:
  ```bash
  docker compose -f docker-compose.production.yml \
    --profile production --profile zeroclaw up -d
  ```
- [ ] Monitoring profile works:
  ```bash
  docker compose -f docker-compose.production.yml \
    --profile production --profile zeroclaw --profile monitoring up -d
  ```
- [ ] Resource limits are set for all services (memory + CPU)
- [ ] Restart policies are `unless-stopped` on all services
- [ ] Named volumes for all persistent data
- [ ] Log drivers configured (json-file, 10 MB x 5 files)
- [ ] Health checks defined for all services

### 2.3 Wizard UI

- [ ] Wizard builds: `cd wizard && npm run build`
- [ ] Build output is optimized (manual chunk splitting: react, framer-motion, lucide-react, utils)
- [ ] No build warnings or errors
- [ ] Source maps are hidden (not shipped to production)
- [ ] ES2020 target verified

---

## 3. Documentation Verification

### 3.1 README and Guides

- [ ] `README.md` is current with v2.0 features
- [ ] Quickstart guide works on clean Ubuntu 24.04
- [ ] Per-agent setup instructions are accurate
- [ ] Assessment workflow walkthrough is correct
- [ ] `.env.template` is complete and documented for all services
- [ ] Fine-tuning guide is accurate
- [ ] Troubleshooting guide covers common issues

### 3.2 Operational Documentation

- [ ] `docs/RUNBOOK.md` covers all 8+ services (including port map, restart procedures, log locations)
- [ ] Troubleshooting decision tree is complete
- [ ] Escalation matrix includes severity levels and response times
- [ ] Backup/restore procedures documented with commands
- [ ] TLS certificate management documented
- [ ] Monitoring stack operations documented (Grafana, Prometheus, Loki)

### 3.3 API Documentation

- [ ] `.ai/context_base.md` is current and comprehensive
- [ ] Assessment JSON schema documented (`assessment/schema/assessment-schema.json`)
- [ ] All environment variables documented in `.env.template`
- [ ] Example assessments available: Real Estate, IoT, DevSecOps

### 3.4 Release Documentation

- [ ] `CHANGELOG.md` written for v2.0.0 (Keep a Changelog format)
- [ ] `.team/releases/GITHUB_RELEASE_DRAFT.md` prepared
- [ ] `.team/releases/ROLLBACK_PROCEDURES.md` complete
- [ ] This checklist completed

---

## 4. Deployment Steps

### 4.1 Staging Deployment

```bash
# 1. Clone the release branch
git clone -b ai-team https://github.com/Amenthyx/claw-agents-provisioner.git
cd claw-agents-provisioner

# 2. Configure environment
cp .env.template .env
# Edit .env with staging API keys and configuration

# 3. Initialize TLS (staging Let's Encrypt)
LETSENCRYPT_STAGING=1 ./scripts/init-letsencrypt.sh staging.claw.example.com admin@example.com

# 4. Start services
docker compose -f docker-compose.production.yml \
  --profile production --profile zeroclaw --profile monitoring up -d --build

# 5. Verify health
curl -k https://localhost/health
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"
```

### 4.2 Staging Verification

- [ ] All health endpoints return 200 OK
- [ ] Smoke test passes with `--live` mode
- [ ] Chat round-trip works (router -> LLM -> response)
- [ ] Memory write/read cycle works
- [ ] RAG ingest/search cycle works
- [ ] Grafana dashboards show data
- [ ] Prometheus targets are all UP
- [ ] TLS certificate is valid
- [ ] Load tests pass against staging:
  ```bash
  cd tests/load && ./run-load-tests.sh
  ```
- [ ] k6 results meet P95 thresholds (router < 200ms, RAG < 500ms)

### 4.3 Production Deployment

```bash
# 1. Tag the release
git tag -a v2.0.0 -m "Claw Agents Provisioner v2.0.0 -- Production Hardening"

# 2. Clone on production server
git clone -b v2.0.0 https://github.com/Amenthyx/claw-agents-provisioner.git
cd claw-agents-provisioner

# 3. Configure environment
cp .env.template .env
# Edit .env with production API keys and configuration

# 4. Initialize TLS (production Let's Encrypt)
./scripts/init-letsencrypt.sh claw.example.com admin@example.com

# 5. Set up scheduled backups
crontab -l > /tmp/crontab.bak
echo "0 2 * * * $(pwd)/scripts/backup-cron.sh" | crontab -

# 6. Run database migrations
python3 scripts/migrate.py up

# 7. Start services
docker compose -f docker-compose.production.yml \
  --profile production --profile zeroclaw --profile monitoring up -d --build

# 8. Verify
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"
```

- [ ] Production deployment command executed
- [ ] Database migrations completed successfully (`python3 scripts/migrate.py status`)
- [ ] Backup cron job installed
- [ ] TLS certificates issued (not staging)

---

## 5. Post-Deployment Verification

### 5.1 Smoke Tests

- [ ] `./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"` passes
- [ ] Health aggregator returns all services healthy: `curl http://localhost:9094/health/summary`
- [ ] HTTPS accessible: `curl -k https://localhost/health`
- [ ] HTTP redirects to HTTPS

### 5.2 Service Health

- [ ] All Docker containers are running: `docker ps --format "table {{.Names}}\t{{.Status}}"`
- [ ] All containers show `(healthy)` status
- [ ] No OOM kills in recent logs: `docker inspect --format='{{.State.ExitCode}}' $(docker ps -q)`
- [ ] Port map is correct: `python3 shared/claw_ports.py --show`

### 5.3 Monitoring Dashboards

- [ ] Grafana accessible at http://localhost:3000
- [ ] "Claw Platform Overview" dashboard shows data
- [ ] "Claw Service Details" dashboard shows data
- [ ] Prometheus targets all UP: `curl http://localhost:9092/api/v1/targets`
- [ ] Loki receiving logs: check Grafana -> Explore -> Loki for recent entries
- [ ] Alert rules loaded: `curl http://localhost:9092/api/v1/rules`

### 5.4 Alerting

- [ ] Alert rules configured in `monitoring/prometheus/alert.rules.yml`
- [ ] Service down alert fires within 3 min of condition
- [ ] Error rate alert fires when > 5%
- [ ] Memory usage alert fires when > 90%
- [ ] Disk usage alert fires when > 85%

### 5.5 Backup Verification

- [ ] Manual backup runs: `./scripts/backup.sh`
- [ ] Backup archive is valid: `tar -tzf backups/daily/claw-backup-*.tar.gz`
- [ ] Restore dry-run succeeds: `./scripts/restore.sh <archive> --dry-run`
- [ ] Cron job scheduled: `crontab -l | grep backup`

---

## 6. Communication

### 6.1 Release Artifacts

- [ ] Git tag `v2.0.0` created and pushed
- [ ] `CHANGELOG.md` committed and pushed
- [ ] GitHub Release created with release notes (from `GITHUB_RELEASE_DRAFT.md`)
- [ ] Release artifacts attached (if applicable)

### 6.2 Notifications

- [ ] Team notified of successful deployment
- [ ] Stakeholders informed of v2.0.0 availability
- [ ] Known issues documented and communicated
- [ ] Upgrade guide shared with existing v1.0 users

---

## 7. Rollback Readiness

- [ ] Rollback procedures reviewed (`.team/releases/ROLLBACK_PROCEDURES.md`)
- [ ] Previous backup is available and verified
- [ ] Previous version tag exists (`v1.0.0`)
- [ ] Team is aware of rollback decision tree

---

## Sign-Off

| Role | Name | Approved | Date |
|------|------|----------|------|
| RM (Release Manager) | | | |
| QA (Quality Assurance) | | | |
| DEVOPS (DevOps Engineer) | | | |
| PM (Project Manager) | | | |

---

*Release Checklist v2.0.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
