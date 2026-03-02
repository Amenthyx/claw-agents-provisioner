# Rollback Procedures -- Claw Agents Provisioner v2.0.0

> **Version:** 1.0
> **Date:** 2026-03-02
> **Author:** RM (Full-Stack Team, Amenthyx AI Teams v3.0)
> **Last Updated:** 2026-03-02

---

## Table of Contents

1. [Decision Tree: Rollback vs. Hotfix](#1-decision-tree-rollback-vs-hotfix)
2. [Container Rollback](#2-container-rollback)
3. [Configuration Rollback](#3-configuration-rollback)
4. [Database Rollback](#4-database-rollback)
5. [Partial Rollback (Single Service)](#5-partial-rollback-single-service)
6. [Full Platform Rollback](#6-full-platform-rollback)
7. [Monitoring and Observability Rollback](#7-monitoring-and-observability-rollback)
8. [TLS/Nginx Rollback](#8-tlsnginx-rollback)
9. [Communication Template](#9-communication-template)
10. [Post-Rollback Verification](#10-post-rollback-verification)

---

## 1. Decision Tree: Rollback vs. Hotfix

Use this decision tree to determine whether to rollback or apply a hotfix.

```
Issue detected in production
|
+-- Is the platform completely down (all services)?
|   |
|   +-- YES --> FULL PLATFORM ROLLBACK (Section 6)
|   |           Time estimate: 15-30 minutes
|   |
|   +-- NO  --> Is only ONE service affected?
|       |
|       +-- YES --> Can the issue be isolated and fixed in < 30 min?
|       |   |
|       |   +-- YES --> HOTFIX
|       |   |           1. Fix the code on a hotfix branch
|       |   |           2. Run tests: pytest tests/test_integration_*.py
|       |   |           3. Rebuild: docker compose up -d --build <service>
|       |   |           4. Verify: curl http://localhost:<port>/health
|       |   |
|       |   +-- NO  --> PARTIAL ROLLBACK (Section 5)
|       |               Time estimate: 5-10 minutes
|       |
|       +-- NO  --> Are MULTIPLE services affected?
|           |
|           +-- Is it a configuration issue?
|           |   |
|           |   +-- YES --> CONFIGURATION ROLLBACK (Section 3)
|           |   |           Time estimate: 5-10 minutes
|           |   |
|           |   +-- NO  --> Is it a data/migration issue?
|           |       |
|           |       +-- YES --> DATABASE ROLLBACK (Section 4)
|           |       |           Time estimate: 10-20 minutes
|           |       |
|           |       +-- NO  --> CONTAINER ROLLBACK (Section 2)
|           |                   Time estimate: 10-15 minutes
```

### Quick Decision Matrix

| Scenario | Action | Section | Est. Time |
|----------|--------|---------|-----------|
| All services down after deployment | Full Platform Rollback | 6 | 15-30 min |
| Single service crashes repeatedly | Partial Rollback | 5 | 5-10 min |
| Bad config pushed (env vars, nginx) | Configuration Rollback | 3 | 5-10 min |
| Migration broke database schema | Database Rollback | 4 | 10-20 min |
| Multiple containers failing | Container Rollback | 2 | 10-15 min |
| Minor bug, service still running | Hotfix (no rollback) | N/A | < 30 min |
| Security vulnerability discovered | Full Platform Rollback + patch | 6 | 30-60 min |
| Monitoring stack broken | Monitoring Rollback | 7 | 5-10 min |
| TLS certificates invalid | TLS/Nginx Rollback | 8 | 5-10 min |

---

## 2. Container Rollback

Use when one or more containers are failing after a deployment but configuration and data are intact.

### Prerequisites

- Docker Compose is available
- Previous image layers are cached (or previous commit is available)
- Production compose file: `docker-compose.production.yml`

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Identify the failing service(s)
# ---------------------------------------------------------------
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker compose -f docker-compose.production.yml ps

# Check for crash loops or unhealthy status
docker inspect --format='{{.Name}} {{.State.ExitCode}} {{.State.Status}}' \
  $(docker ps -aq) 2>/dev/null

# ---------------------------------------------------------------
# Step 2: Check available image history
# ---------------------------------------------------------------
# List local images for the failing service
docker images | grep claw

# Check git history for the last known-good Dockerfile
git log --oneline -10 -- <service-dir>/Dockerfile

# ---------------------------------------------------------------
# Step 3: Revert to the previous version
# ---------------------------------------------------------------
# Option A: Checkout previous Dockerfile and rebuild
PREVIOUS_COMMIT=$(git log --oneline -2 -- <service-dir>/Dockerfile | tail -1 | cut -d' ' -f1)
git checkout ${PREVIOUS_COMMIT} -- <service-dir>/Dockerfile <service-dir>/entrypoint.sh

# Rebuild and restart the service
docker compose -f docker-compose.production.yml up -d --build <service-name>

# Option B: If image tags are used, pin to previous tag
# Edit docker-compose.production.yml to use previous image tag
# Then:
docker compose -f docker-compose.production.yml up -d <service-name>

# ---------------------------------------------------------------
# Step 4: Verify the rollback
# ---------------------------------------------------------------
docker ps --filter name=<service-name>
curl -s http://localhost:<port>/health
```

### Known Image Tags

| Service | Current Image | Build Context |
|---------|--------------|---------------|
| ZeroClaw | Built from `zeroclaw/Dockerfile` | `zeroclaw/` |
| NanoClaw | Built from `nanoclaw/Dockerfile` | `nanoclaw/` |
| PicoClaw | Built from `picoclaw/Dockerfile` | `picoclaw/` |
| OpenClaw | Built from `openclaw/Dockerfile` | `openclaw/` |
| Nginx | Built from `nginx/Dockerfile` | `nginx/` |
| Fine-tune | Built from `finetune/Dockerfile.finetune` | `finetune/` |

---

## 3. Configuration Rollback

Use when a configuration change (environment variables, nginx config, Prometheus config) caused the failure.

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Identify the configuration change
# ---------------------------------------------------------------
# Check recent commits for config file changes
git log --oneline -10 -- .env.template docker-compose.production.yml \
  nginx/ monitoring/ scripts/

# Diff against previous version
git diff HEAD~1 -- docker-compose.production.yml nginx/ monitoring/

# ---------------------------------------------------------------
# Step 2: Restore previous configuration
# ---------------------------------------------------------------
# Option A: Restore specific config file(s) from git
PREVIOUS_COMMIT=$(git log --oneline -2 -- <config-file> | tail -1 | cut -d' ' -f1)
git checkout ${PREVIOUS_COMMIT} -- <config-file>

# Common config files to restore:
# - docker-compose.production.yml
# - nginx/conf.d/default.conf
# - nginx/conf.d/ssl.conf
# - nginx/nginx.conf
# - monitoring/prometheus/prometheus.yml
# - monitoring/prometheus/alert.rules.yml
# - monitoring/loki/loki-config.yml
# - monitoring/promtail/promtail-config.yml
# - monitoring/grafana/provisioning/datasources/datasources.yml

# Option B: Restore from backup (if .env was changed)
./scripts/restore.sh <backup-archive> --config-only

# ---------------------------------------------------------------
# Step 3: Apply the restored configuration
# ---------------------------------------------------------------
# Recreate affected services to pick up new config
docker compose -f docker-compose.production.yml up -d --force-recreate <service-name>

# For nginx config changes, a reload may suffice:
docker exec claw-nginx nginx -t  # Validate config first
docker exec claw-nginx nginx -s reload

# For Prometheus config changes:
curl -X POST http://localhost:9092/-/reload

# ---------------------------------------------------------------
# Step 4: Verify
# ---------------------------------------------------------------
curl -s http://localhost:9094/health/summary
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"
```

---

## 4. Database Rollback

Use when a database migration or data change caused the failure.

### Prerequisites

- Migration system is available: `scripts/migrate.py`
- Backup archives are available: `./scripts/restore.sh --list`

### Procedure: Migration Rollback

```bash
# ---------------------------------------------------------------
# Step 1: Check current migration status
# ---------------------------------------------------------------
python3 scripts/migrate.py status

# ---------------------------------------------------------------
# Step 2: Roll back the most recent migration
# ---------------------------------------------------------------
# Roll back the last migration across all databases
python3 scripts/migrate.py down

# Roll back for a specific database only
python3 scripts/migrate.py down --db memory
python3 scripts/migrate.py down --db billing
python3 scripts/migrate.py down --db audit
python3 scripts/migrate.py down --db orchestrator

# Roll back ALL migrations (CAUTION: destroys all schema)
# python3 scripts/migrate.py reset

# ---------------------------------------------------------------
# Step 3: Verify migration state
# ---------------------------------------------------------------
python3 scripts/migrate.py status

# ---------------------------------------------------------------
# Step 4: Restart affected services
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml restart \
  claw-memory claw-billing claw-orchestrator

# ---------------------------------------------------------------
# Step 5: Verify service health
# ---------------------------------------------------------------
curl -s http://localhost:9096/health  # Memory
curl -s http://localhost:9094/health/summary
```

### Procedure: Full Data Restore from Backup

```bash
# ---------------------------------------------------------------
# Step 1: List available backups
# ---------------------------------------------------------------
./scripts/restore.sh --list

# ---------------------------------------------------------------
# Step 2: Preview the restore (dry run)
# ---------------------------------------------------------------
./scripts/restore.sh backups/daily/claw-backup-<timestamp>.tar.gz --dry-run

# ---------------------------------------------------------------
# Step 3: Stop affected services
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml stop \
  claw-memory claw-billing claw-orchestrator

# ---------------------------------------------------------------
# Step 4: Restore databases from backup
# ---------------------------------------------------------------
./scripts/restore.sh backups/daily/claw-backup-<timestamp>.tar.gz --db-only

# ---------------------------------------------------------------
# Step 5: Start services and verify
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml up -d \
  claw-memory claw-billing claw-orchestrator

curl -s http://localhost:9094/health/summary
```

### Database File Locations

| Database | Default Path | Service |
|----------|-------------|---------|
| Memory | `data/memory.db` | Memory Service (9096) |
| Billing | `data/billing.db` | Billing Service |
| Audit | `data/audit.db` | Audit Module |
| Orchestrator | `data/orchestrator.db` | Orchestrator (9100) |
| Port Map | `data/port_map.json` | Port Manager |

---

## 5. Partial Rollback (Single Service)

Use when only one service needs to be rolled back while all others remain running.

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Identify the failing service
# ---------------------------------------------------------------
SERVICE_NAME="claw-router"  # Replace with actual service name
SERVICE_PORT=9095            # Replace with actual port

# Check logs for the failure
docker logs ${SERVICE_NAME} --tail 50

# ---------------------------------------------------------------
# Step 2: Stop only the failing service
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml stop ${SERVICE_NAME}

# ---------------------------------------------------------------
# Step 3: Revert the service's source files
# ---------------------------------------------------------------
# Find the last known-good commit for this service
git log --oneline -5 -- shared/claw_router.py  # Replace with actual file

# Checkout the previous version
GOOD_COMMIT=$(git log --oneline -2 -- shared/claw_router.py | tail -1 | cut -d' ' -f1)
git checkout ${GOOD_COMMIT} -- shared/claw_router.py

# ---------------------------------------------------------------
# Step 4: Rebuild and restart the service
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml up -d --build ${SERVICE_NAME}

# ---------------------------------------------------------------
# Step 5: Verify the service is healthy
# ---------------------------------------------------------------
# Wait for container to start
sleep 5
docker ps --filter name=${SERVICE_NAME}
curl -s http://localhost:${SERVICE_PORT}/health

# Verify it works end-to-end
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"
```

### Service-to-File Mapping

| Service | Container Name | Source File(s) | Port |
|---------|---------------|----------------|------|
| Router | claw-router | `shared/claw_router.py` | 9095 |
| Memory | claw-memory | `shared/claw_memory.py` | 9096 |
| RAG | claw-rag | `shared/claw_rag.py` | 9097 |
| Dashboard | claw-dashboard | `shared/claw_dashboard.py` | 9099 |
| Orchestrator | claw-orchestrator | `shared/claw_orchestrator.py` | 9100 |
| Wizard | claw-wizard | `shared/claw_wizard_api.py` | 9098 |
| Watchdog | claw-watchdog | `shared/claw_agent_stub.py` | 9090 |
| Health | claw-health | `shared/claw_health.py` | 9094 |
| Optimizer | claw-optimizer | `shared/claw_optimizer.py` | 9091 |
| Billing | claw-billing | `shared/claw_billing.py` | N/A (internal) |
| Nginx | claw-nginx | `nginx/` | 80/443 |
| ZeroClaw | claw-zeroclaw | `zeroclaw/` | 3100 |
| NanoClaw | claw-nanoclaw | `nanoclaw/` | 3200 |
| PicoClaw | claw-picoclaw | `picoclaw/` | 3300 |
| OpenClaw | claw-openclaw | `openclaw/` | 3400 |

---

## 6. Full Platform Rollback

Use when the entire platform is down or a critical security vulnerability has been discovered. This is the most disruptive rollback and should be used as a last resort.

### Prerequisites

- Known-good git commit hash or tag (e.g., `v1.0.0`)
- Backup archive available
- At least 30 minutes of maintenance window

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Announce maintenance window
# ---------------------------------------------------------------
# Send communication using template in Section 9

# ---------------------------------------------------------------
# Step 2: Stop all services
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml \
  --profile production --profile zeroclaw --profile monitoring down

# Verify everything is stopped
docker ps  # Should show no claw containers

# ---------------------------------------------------------------
# Step 3: Create a safety backup of current state
# ---------------------------------------------------------------
./scripts/backup.sh
# Note the backup filename for reference

# ---------------------------------------------------------------
# Step 4: Checkout the known-good version
# ---------------------------------------------------------------
# Option A: Rollback to a specific commit
KNOWN_GOOD_COMMIT="<commit-hash>"
git stash  # Save any uncommitted changes
git checkout ${KNOWN_GOOD_COMMIT}

# Option B: Rollback to a tagged release
git checkout v1.0.0

# ---------------------------------------------------------------
# Step 5: Restore data from the last known-good backup
# ---------------------------------------------------------------
# List available backups
./scripts/restore.sh --list

# Preview before restoring
./scripts/restore.sh backups/daily/claw-backup-<timestamp>.tar.gz --dry-run

# Full restore
./scripts/restore.sh backups/daily/claw-backup-<timestamp>.tar.gz

# ---------------------------------------------------------------
# Step 6: Rebuild all images and start services
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml \
  --profile production --profile zeroclaw --profile monitoring \
  up -d --build

# ---------------------------------------------------------------
# Step 7: Run database migrations (if rolling back to v1.x)
# ---------------------------------------------------------------
# If rolling back to v1.0, you may need to roll back migrations first
python3 scripts/migrate.py down  # Run for each migration to undo

# ---------------------------------------------------------------
# Step 8: Verify full platform health
# ---------------------------------------------------------------
# Wait for services to stabilize
sleep 30

# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Health check
curl -s http://localhost:9094/health/summary

# Full smoke test
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"

# Check monitoring
curl -s http://localhost:9092/api/v1/targets | python3 -c \
  "import sys,json; d=json.load(sys.stdin); \
   [print(f'{t[\"labels\"][\"job\"]}: {t[\"health\"]}') \
    for g in d['data']['activeTargets'] for t in [g]]"

# ---------------------------------------------------------------
# Step 9: Announce recovery
# ---------------------------------------------------------------
# Send recovery communication using template in Section 9
```

### Key Git Tags and Commits

| Version | Tag | Commit | Date | Notes |
|---------|-----|--------|------|-------|
| v1.0.0 | `v1.0.0` | See `git log --tags` | 2026-02-26 | Original release, all v1.0 features |
| v2.0.0 | `v2.0.0` | See `git log --tags` | 2026-03-02 | Production hardening release |
| Wave 1 (PM) | N/A | `4ff2104` | 2026-03-02 | Planning artifacts |
| Wave 2 (DEVOPS) | N/A | `9eba016` | 2026-03-02 | Production compose, TLS, monitoring |
| Wave 2 (FE) | N/A | `7c8b945` | 2026-03-02 | Wizard UI tests, accessibility |
| Wave 2 (BE) | N/A | `b3033e5` | 2026-03-02 | Integration tests, E2E tests, migrations |
| Wave 3 (QA) | N/A | `f1db77a` | 2026-03-02 | k6 load tests, QA sign-off |

---

## 7. Monitoring and Observability Rollback

Use when the monitoring stack (Prometheus, Grafana, Loki) is broken but core services are running.

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Stop only the monitoring stack
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml --profile monitoring stop

# ---------------------------------------------------------------
# Step 2: Check for configuration issues
# ---------------------------------------------------------------
# Validate Prometheus config
docker run --rm -v $(pwd)/monitoring/prometheus:/etc/prometheus \
  prom/prometheus:v2.48.0 promtool check config /etc/prometheus/prometheus.yml

# Validate alert rules
docker run --rm -v $(pwd)/monitoring/prometheus:/etc/prometheus \
  prom/prometheus:v2.48.0 promtool check rules /etc/prometheus/alert.rules.yml

# ---------------------------------------------------------------
# Step 3: Restore monitoring config from git
# ---------------------------------------------------------------
git checkout HEAD~1 -- monitoring/prometheus/prometheus.yml
git checkout HEAD~1 -- monitoring/prometheus/alert.rules.yml
git checkout HEAD~1 -- monitoring/loki/loki-config.yml
git checkout HEAD~1 -- monitoring/promtail/promtail-config.yml
git checkout HEAD~1 -- monitoring/grafana/provisioning/

# ---------------------------------------------------------------
# Step 4: Clear monitoring data volumes (if corrupted)
# ---------------------------------------------------------------
# CAUTION: This deletes historical metrics and logs
docker volume rm claw-agents-provisioner_prometheus-data 2>/dev/null
docker volume rm claw-agents-provisioner_loki-data 2>/dev/null
# Grafana data is usually safe to keep (dashboards are provisioned from files)

# ---------------------------------------------------------------
# Step 5: Restart monitoring
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml --profile monitoring up -d

# ---------------------------------------------------------------
# Step 6: Verify
# ---------------------------------------------------------------
curl -s http://localhost:9092/api/v1/targets  # Prometheus
curl -s http://localhost:3000/api/health       # Grafana
```

---

## 8. TLS/Nginx Rollback

Use when TLS certificates are invalid or nginx is misconfigured, causing HTTPS failures.

### Procedure

```bash
# ---------------------------------------------------------------
# Step 1: Diagnose the issue
# ---------------------------------------------------------------
# Check if nginx is running
docker ps --filter name=claw-nginx

# Check nginx error log
docker logs claw-nginx --tail 50

# Test nginx config syntax
docker exec claw-nginx nginx -t

# Check certificate status
docker exec claw-nginx openssl x509 -in /etc/nginx/ssl/fullchain.pem \
  -noout -enddate 2>/dev/null || echo "No certificate found"

# ---------------------------------------------------------------
# Step 2a: Fix certificate issues
# ---------------------------------------------------------------
# Regenerate self-signed certificate (immediate fix)
docker exec claw-nginx openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/privkey.pem \
  -out /etc/nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"

# Reload nginx
docker exec claw-nginx nginx -s reload

# Or re-run Let's Encrypt initialization
./scripts/init-letsencrypt.sh <domain> <email>

# ---------------------------------------------------------------
# Step 2b: Fix nginx config issues
# ---------------------------------------------------------------
# Restore nginx config from git
git checkout HEAD~1 -- nginx/conf.d/default.conf
git checkout HEAD~1 -- nginx/conf.d/ssl.conf
git checkout HEAD~1 -- nginx/nginx.conf

# Rebuild nginx container
docker compose -f docker-compose.production.yml up -d --build nginx-proxy

# ---------------------------------------------------------------
# Step 3: Verify
# ---------------------------------------------------------------
curl -k https://localhost/health
curl -I http://localhost  # Should redirect to HTTPS
```

---

## 9. Communication Template

### Incident Notification (Rollback Initiated)

```
SUBJECT: [INCIDENT] Claw Platform -- Rollback in Progress

SEVERITY: P0/P1/P2/P3
STATUS: ROLLBACK IN PROGRESS
STARTED: <ISO 8601 timestamp>
ESTIMATED RESOLUTION: <time estimate>

AFFECTED SERVICES:
- <list of affected services>

IMPACT:
- <description of user-facing impact>
- <number of users/clients affected, if known>

ROOT CAUSE (preliminary):
- <brief description of what went wrong>

ACTIONS TAKEN:
1. <what was tried before deciding to rollback>
2. Rollback initiated: <type of rollback from Sections 2-8>
3. Rolling back to: <commit hash / tag / backup timestamp>

NEXT UPDATE: <time of next status update>

CONTACT: <on-call engineer name and channel>
```

### Recovery Notification (Rollback Complete)

```
SUBJECT: [RESOLVED] Claw Platform -- Service Restored

SEVERITY: P0/P1/P2/P3
STATUS: RESOLVED
STARTED: <ISO 8601 timestamp>
RESOLVED: <ISO 8601 timestamp>
DURATION: <total incident duration>

RESOLUTION:
- Rollback type: <Section 2-8 type>
- Rolled back to: <commit hash / tag / backup timestamp>
- All services verified healthy via smoke test

IMPACT SUMMARY:
- <total downtime>
- <services affected>
- <data impact, if any: "No data loss" or details>

ROOT CAUSE:
- <description of root cause>

FOLLOW-UP:
- [ ] Post-incident review scheduled for <date>
- [ ] Root cause fix to be deployed in <version/hotfix>
- [ ] Monitoring improvements: <if applicable>

CONTACT: <on-call engineer name and channel>
```

### Scheduled Maintenance Notification (Pre-Rollback)

```
SUBJECT: [MAINTENANCE] Claw Platform -- Planned Rollback

SCHEDULED START: <ISO 8601 timestamp>
ESTIMATED DURATION: <duration>
AFFECTED SERVICES: <list or "all">

REASON:
- <why the rollback is necessary>

EXPECTED IMPACT:
- <downtime estimate>
- <what users should expect>

PREPARATION:
- <any actions users should take before maintenance>

CONTACT: <on-call engineer name and channel>
```

---

## 10. Post-Rollback Verification

After any rollback, run this complete verification checklist.

### Automated Verification

```bash
# 1. Container health
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v NAMES | while read line; do
  echo "CHECK: $line"
done

# 2. Health aggregator
curl -s http://localhost:9094/health/summary
echo ""

# 3. Individual service health
for port in 9090 9091 9094 9095 9096 9097 9098 9099 9100; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${port}/health 2>/dev/null)
  echo "Port ${port}: HTTP ${STATUS}"
done

# 4. Full smoke test
./scripts/smoke-test.sh --live --token "$CLAW_AUTH_TOKEN"

# 5. Monitoring check (if monitoring is running)
PROM_TARGETS=$(curl -s http://localhost:9092/api/v1/targets 2>/dev/null)
if [ $? -eq 0 ]; then
  echo "Prometheus: OK"
else
  echo "Prometheus: NOT RUNNING (non-critical if monitoring rollback)"
fi

# 6. TLS check (if nginx is running)
HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" https://localhost/health 2>/dev/null)
echo "HTTPS: ${HTTPS_STATUS}"

# 7. Database integrity (if database rollback was performed)
for db in data/memory.db data/billing.db data/audit.db data/orchestrator.db; do
  if [ -f "$db" ]; then
    RESULT=$(sqlite3 "$db" "PRAGMA integrity_check;" 2>/dev/null)
    echo "DB ${db}: ${RESULT}"
  fi
done
```

### Manual Verification Checklist

- [ ] All containers show `(healthy)` status in `docker ps`
- [ ] Health aggregator reports all services healthy
- [ ] Smoke test passes completely
- [ ] Grafana dashboards show data (if monitoring is running)
- [ ] No error spikes in Prometheus metrics
- [ ] TLS/HTTPS is working (if nginx is running)
- [ ] Backup cron job is still scheduled: `crontab -l | grep backup`
- [ ] Database integrity checks pass for all SQLite databases
- [ ] Application logs show no recurring errors: `docker compose logs --tail 20`
- [ ] A test chat message completes successfully through the router
- [ ] Memory write and read cycle works
- [ ] RAG ingest and search works

---

*Rollback Procedures v1.0 -- Claw Agents Provisioner v2.0.0 -- Amenthyx AI Teams v3.0*
