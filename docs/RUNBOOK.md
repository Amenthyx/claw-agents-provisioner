# Claw Agents Provisioner -- Operational Runbook

## Table of Contents

1. [Service Architecture](#service-architecture)
2. [Service Restart Procedures](#service-restart-procedures)
3. [Log Locations and Searching](#log-locations-and-searching)
4. [Health Check Verification](#health-check-verification)
5. [Common Failures and Troubleshooting](#common-failures-and-troubleshooting)
6. [Backup and Restore](#backup-and-restore)
7. [TLS Certificate Management](#tls-certificate-management)
8. [Monitoring Stack Operations](#monitoring-stack-operations)
9. [Rollback Procedures](#rollback-procedures)
10. [Escalation Matrix](#escalation-matrix)

---

## Service Architecture

### Port Map

| Service       | Default Port | Environment Variable       | Description                |
|---------------|-------------|---------------------------|----------------------------|
| Watchdog      | 9090        | `CLAW_WATCHDOG_PORT`      | Process health monitor     |
| Optimizer     | 9091        | `CLAW_OPTIMIZER_PORT`     | Cost optimization engine   |
| Health Agg.   | 9094        | `CLAW_HEALTH_PORT`        | Unified health aggregator  |
| Router        | 9095        | `CLAW_GATEWAY_PORT`       | Gateway router             |
| Memory        | 9096        | `CLAW_MEMORY_PORT`        | Memory/storage service     |
| RAG           | 9097        | `CLAW_RAG_PORT`           | Retrieval-augmented gen.   |
| Wizard        | 9098        | `CLAW_WIZARD_PORT`        | Setup wizard API           |
| Dashboard     | 9099        | `CLAW_DASHBOARD_PORT`     | Fleet management dashboard |
| Orchestrator  | 9100        | `CLAW_ORCHESTRATOR_PORT`  | Multi-agent orchestrator   |
| Nginx         | 80/443      | N/A                       | TLS reverse proxy          |
| Prometheus    | 9092        | N/A                       | Metrics (mapped from 9090) |
| Grafana       | 3000        | `GRAFANA_PORT`            | Dashboards                 |
| Loki          | 3100        | N/A                       | Log aggregation            |

### Agent Services

| Agent     | Default Port | Memory Limit | Description            |
|-----------|-------------|-------------|------------------------|
| ZeroClaw  | 3100        | 512 MB      | Rust-based, lightweight |
| NanoClaw  | 3200        | 1 GB        | TypeScript, DooD       |
| PicoClaw  | 3300        | 128 MB      | Go-based, edge/IoT     |
| OpenClaw  | 3400        | 4 GB        | TypeScript, feature-rich|
| Parlant   | 8800        | 2 GB        | Python, conversational  |

---

## Service Restart Procedures

### Restart a Single Service

```bash
# Check current status
docker compose -f docker-compose.production.yml ps

# Restart a specific service (preserves volumes)
docker compose -f docker-compose.production.yml restart <service-name>

# Examples:
docker compose -f docker-compose.production.yml restart nginx-proxy
docker compose -f docker-compose.production.yml restart health-aggregator
docker compose -f docker-compose.production.yml restart zeroclaw
```

### Restart with Recreation (picks up config changes)

```bash
# Recreate a service (pulls new config, rebuilds if needed)
docker compose -f docker-compose.production.yml up -d --force-recreate <service-name>

# Rebuild and recreate (after Dockerfile changes)
docker compose -f docker-compose.production.yml up -d --build <service-name>
```

### Restart All Services

```bash
# Graceful restart (rolling -- one at a time)
docker compose -f docker-compose.production.yml --profile production \
  --profile zeroclaw restart

# Full stop and start (causes downtime)
docker compose -f docker-compose.production.yml --profile production \
  --profile zeroclaw down
docker compose -f docker-compose.production.yml --profile production \
  --profile zeroclaw up -d
```

### Restart Monitoring Stack Only

```bash
docker compose -f docker-compose.production.yml --profile monitoring restart
```

### Emergency: Force-Kill and Restart

```bash
# If a container is unresponsive
docker kill <container-name>
docker compose -f docker-compose.production.yml up -d <service-name>
```

---

## Log Locations and Searching

### Docker Container Logs

```bash
# View recent logs for a service
docker logs claw-nginx --tail 100

# Follow logs in real-time
docker logs -f claw-nginx

# Logs with timestamps
docker logs --timestamps claw-nginx

# Logs since a specific time
docker logs --since 2024-01-15T10:00:00 claw-nginx

# All container logs
docker compose -f docker-compose.production.yml logs
```

### Log Files on Host

| Log              | Location                           | Rotation             |
|------------------|------------------------------------|----------------------|
| Nginx access     | `nginx-logs` volume                | json-file 10MB x 5  |
| Nginx error      | `nginx-logs` volume                | json-file 10MB x 5  |
| Container logs   | `/var/lib/docker/containers/`      | json-file 10MB x 5  |
| Backup cron      | `./logs/backup-cron.log`           | Managed by script    |
| Audit log        | `./logs/audit.log`                 | 10 MB x 5 (Python)  |
| Watchdog         | `./watchdog.log`                   | Application managed  |

### Searching Logs

```bash
# Search container logs for errors
docker logs claw-nginx 2>&1 | grep -i "error"

# Search with context (5 lines before/after)
docker logs claw-nginx 2>&1 | grep -C 5 "502"

# Search across all containers
docker compose -f docker-compose.production.yml logs 2>&1 | grep "ERROR"

# Search Loki via Grafana
# Navigate to Grafana -> Explore -> Loki
# Query: {compose_service="nginx-proxy"} |= "error"
```

### Log Rotation

All production containers use `json-file` log driver with:
- Max size: 10 MB per file
- Max files: 5 (oldest files auto-deleted)
- Total max per container: 50 MB

To manually force rotation:
```bash
# Truncate a specific container's log
truncate -s 0 $(docker inspect --format='{{.LogPath}}' claw-nginx)
```

---

## Health Check Verification

### Quick Health Check

```bash
# Aggregated health (all services)
curl -s http://localhost:9094/health | python3 -m json.tool

# One-line summary
curl -s http://localhost:9094/health/summary

# Individual service
curl -s http://localhost:9094/health/router
curl -s http://localhost:9094/health/memory
curl -s http://localhost:9094/health/wizard
```

### Docker Health Status

```bash
# Container health status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Detailed health check info for a container
docker inspect --format='{{json .State.Health}}' claw-nginx | python3 -m json.tool
```

### Port Availability Check

```bash
# Check which ports are in use
python3 shared/claw_ports.py --check

# Show resolved port assignments
python3 shared/claw_ports.py --show
```

### End-to-End Verification

```bash
# 1. Check nginx is serving HTTPS
curl -k https://localhost/health

# 2. Check each backend through nginx
curl -k https://localhost/api/router/health
curl -k https://localhost/api/wizard/health
curl -k https://localhost/api/memory/health

# 3. Check Prometheus targets
curl -s http://localhost:9092/api/v1/targets | python3 -m json.tool

# 4. Check Grafana
curl -s http://localhost:3000/api/health
```

---

## Common Failures and Troubleshooting

### Decision Tree

```
Service not responding?
|
+-- Is the container running? (docker ps)
|   |
|   +-- NO --> Check exit code: docker inspect <container> --format='{{.State.ExitCode}}'
|   |   |
|   |   +-- Exit 137 --> OOM killed. Increase memory limit in docker-compose.production.yml
|   |   +-- Exit 1   --> Application error. Check logs: docker logs <container> --tail 50
|   |   +-- Exit 0   --> Container stopped normally. Restart: docker compose up -d <service>
|   |
|   +-- YES --> Is health check passing? (docker inspect --format='{{.State.Health.Status}}')
|       |
|       +-- "unhealthy" --> Check health check logs:
|       |                   docker inspect --format='{{json .State.Health}}' <container>
|       |
|       +-- "healthy" --> Port conflict? Check: ss -tlnp | grep <port>
|                         Network issue? Check: docker network inspect <network>
```

### Problem: Container OOM Killed (Exit 137)

**Symptoms:** Container stops unexpectedly. `docker inspect` shows ExitCode 137.

**Resolution:**
1. Check current memory usage: `docker stats --no-stream`
2. Increase memory limit in `docker-compose.production.yml`
3. Restart: `docker compose -f docker-compose.production.yml up -d <service>`

### Problem: Port Already in Use

**Symptoms:** Container fails to start with "bind: address already in use"

**Resolution:**
1. Find what is using the port: `ss -tlnp | grep <port>` (Linux) or `netstat -ano | findstr <port>` (Windows)
2. Either stop the conflicting process or change the port via environment variable
3. Restart the service

### Problem: Nginx 502 Bad Gateway

**Symptoms:** HTTPS requests return 502 error

**Resolution:**
1. Check if backend service is running: `docker ps | grep <service>`
2. Check if backend responds directly: `curl http://localhost:<port>/health`
3. Check nginx error log: `docker logs claw-nginx --tail 50`
4. Verify upstream configuration in `nginx/conf.d/default.conf`
5. Check `host.docker.internal` resolves: `docker exec claw-nginx ping -c 1 host.docker.internal`

### Problem: TLS Certificate Expired

**Symptoms:** Browser shows certificate warning, curl fails with SSL error

**Resolution:**
1. Check cert expiry: `docker exec claw-nginx openssl x509 -in /etc/nginx/ssl/fullchain.pem -noout -enddate`
2. If using Let's Encrypt: `docker exec claw-nginx certbot renew --force-renewal`
3. Reload nginx: `docker exec claw-nginx nginx -s reload`
4. If self-signed: Regenerate with `openssl` or run `scripts/init-letsencrypt.sh`

### Problem: Prometheus Target Down

**Symptoms:** Grafana dashboards show "No data". Prometheus shows target as DOWN.

**Resolution:**
1. Check target in Prometheus UI: `http://localhost:9092/targets`
2. Verify service is running and has `/metrics` endpoint
3. Test metric endpoint directly: `curl http://localhost:<port>/metrics`
4. Check Prometheus config: `docker exec claw-prometheus cat /etc/prometheus/prometheus.yml`
5. Reload Prometheus: `curl -X POST http://localhost:9092/-/reload`

### Problem: Disk Space Full

**Symptoms:** Services fail to write data. Docker cannot create containers.

**Resolution:**
1. Check disk usage: `df -h`
2. Clean Docker resources: `docker system prune -f`
3. Remove old images: `docker image prune -a --filter "until=168h"`
4. Check Prometheus retention: Reduce `--storage.tsdb.retention.time` if needed
5. Clean old backups: `ls -la backups/daily/ | head -20`

### Problem: Database Corruption (SQLite)

**Symptoms:** Service returns database errors. SQLite integrity check fails.

**Resolution:**
1. Stop the affected service
2. Run integrity check: `sqlite3 <db-file> "PRAGMA integrity_check;"`
3. If corrupted, restore from backup: `./scripts/restore.sh <archive> --db-only`
4. Restart the service
5. Verify: `curl http://localhost:<port>/health`

---

## Backup and Restore

### Manual Backup

```bash
# Full backup (databases + config)
./scripts/backup.sh

# Database only
./scripts/backup.sh --db-only

# Config only
./scripts/backup.sh --config-only
```

### Scheduled Backups

Add to crontab:
```bash
# Daily backup at 2:00 AM
0 2 * * * /opt/claw-agents-provisioner/scripts/backup-cron.sh
```

### List Available Backups

```bash
./scripts/restore.sh --list
```

### Restore from Backup

```bash
# Preview what will be restored (dry run)
./scripts/restore.sh backups/daily/claw-backup-20240115-020000.tar.gz --dry-run

# Full restore
./scripts/restore.sh backups/daily/claw-backup-20240115-020000.tar.gz

# Restore databases only
./scripts/restore.sh backups/daily/claw-backup-20240115-020000.tar.gz --db-only
```

### Backup Verification

```bash
# Check backup archive contents
tar -tzf backups/daily/claw-backup-*.tar.gz

# Verify backup manifest
tar -xzf backups/daily/claw-backup-*.tar.gz -O "*/backup-manifest.json" | python3 -m json.tool
```

---

## TLS Certificate Management

### Initial Setup (Let's Encrypt)

```bash
# Generate real certificates
./scripts/init-letsencrypt.sh claw.example.com admin@example.com

# Test with staging (avoids rate limits)
LETSENCRYPT_STAGING=1 ./scripts/init-letsencrypt.sh claw.example.com admin@example.com
```

### Check Certificate Status

```bash
# Expiry date
docker exec claw-nginx openssl x509 -in /etc/nginx/ssl/fullchain.pem -noout -enddate

# Full certificate info
docker exec claw-nginx openssl x509 -in /etc/nginx/ssl/fullchain.pem -noout -text

# Verify certificate chain
docker exec claw-nginx openssl verify -CAfile /etc/nginx/ssl/fullchain.pem /etc/nginx/ssl/fullchain.pem
```

### Manual Renewal

```bash
# Renew via certbot
docker exec claw-nginx certbot renew --force-renewal

# Reload nginx to pick up new cert
docker exec claw-nginx nginx -s reload
```

### Auto-Renewal

Auto-renewal is configured via a daily cron job inside the nginx container. Verify it is working:

```bash
# Check cron is running inside the container
docker exec claw-nginx ps aux | grep cron

# Check renewal log
docker exec claw-nginx cat /var/log/nginx/certbot-renew.log
```

---

## Monitoring Stack Operations

### Access Points

| Service    | URL                        | Credentials              |
|------------|----------------------------|--------------------------|
| Grafana    | http://localhost:3000      | admin / (GRAFANA_ADMIN_PASSWORD or "admin") |
| Prometheus | http://localhost:9092      | No auth                  |
| Loki       | http://localhost:3100      | No auth (internal only)  |

### Start/Stop Monitoring

```bash
# Start monitoring stack
docker compose -f docker-compose.production.yml --profile monitoring up -d

# Stop monitoring only (keeps other services running)
docker compose -f docker-compose.production.yml --profile monitoring stop

# Restart Prometheus (after config change)
docker compose -f docker-compose.production.yml restart prometheus
```

### Reload Prometheus Config

```bash
# Hot reload (no restart needed)
curl -X POST http://localhost:9092/-/reload

# Verify config is valid
docker exec claw-prometheus promtool check config /etc/prometheus/prometheus.yml
```

### Grafana Dashboard Management

Pre-provisioned dashboards:
- **Claw Platform Overview** -- High-level health, request rates, error rates
- **Claw Service Details** -- Per-service drill-down with logs

Dashboards are loaded from `monitoring/grafana/dashboards/*.json` and auto-refreshed every 30 seconds.

### Data Retention

| Component  | Retention | Storage Volume     |
|------------|-----------|-------------------|
| Prometheus | 7 days    | `prometheus-data`  |
| Loki       | 7 days    | `loki-data`        |
| Grafana    | Permanent | `grafana-data`     |

To change retention:
- Prometheus: Edit `--storage.tsdb.retention.time` in `docker-compose.production.yml`
- Loki: Edit `retention_period` in `monitoring/loki/loki-config.yml`

---

## Rollback Procedures

### Rollback to Previous Container Version

```bash
# 1. Stop the current service
docker compose -f docker-compose.production.yml stop <service>

# 2. Check available image tags
docker images | grep <service>

# 3. Update docker-compose.production.yml to pin the previous version
# (or use a git checkout to restore the previous Dockerfile)

# 4. Rebuild and start
docker compose -f docker-compose.production.yml up -d --build <service>
```

### Rollback Configuration Changes

```bash
# 1. Check git history for config files
git log --oneline -10

# 2. Restore specific file from a commit
git checkout <commit-hash> -- <file-path>

# 3. Recreate affected services
docker compose -f docker-compose.production.yml up -d --force-recreate <service>
```

### Rollback Data (Database)

```bash
# 1. Stop affected services
docker compose -f docker-compose.production.yml stop <service>

# 2. Restore from backup
./scripts/restore.sh backups/daily/claw-backup-<timestamp>.tar.gz --db-only

# 3. Start services
docker compose -f docker-compose.production.yml up -d <service>
```

### Full Platform Rollback

```bash
# 1. Stop everything
docker compose -f docker-compose.production.yml --profile production \
  --profile zeroclaw --profile monitoring down

# 2. Checkout known-good commit
git checkout <known-good-commit>

# 3. Restore data
./scripts/restore.sh <backup-archive>

# 4. Rebuild and start
docker compose -f docker-compose.production.yml --profile production \
  --profile zeroclaw --profile monitoring up -d --build
```

---

## Escalation Matrix

### Severity Levels

| Level    | Response Time | Examples                                         |
|----------|--------------|--------------------------------------------------|
| P0 - Critical | 15 min  | All services down, data loss, security breach    |
| P1 - High     | 1 hour  | Core service down, agent not responding          |
| P2 - Medium   | 4 hours | Monitoring gap, backup failure, performance issue|
| P3 - Low      | 24 hours| Dashboard glitch, non-critical alert noise       |

### Escalation Steps

1. **First Responder (On-call)**
   - Check health endpoint: `curl http://localhost:9094/health/summary`
   - Check Grafana dashboards for anomalies
   - Attempt service restart if a single service is down
   - Check this runbook for the specific failure pattern

2. **Level 2 (DevOps)**
   - Analyze container logs and metrics
   - Check resource utilization (memory, disk, CPU)
   - Perform targeted restarts or configuration changes
   - Execute backup/restore if data integrity is impacted

3. **Level 3 (Engineering Lead)**
   - Code-level investigation
   - Architectural decisions (scaling, service replacement)
   - Coordinate rollback to previous known-good state
   - Post-incident review and root cause analysis

### Communication Template

When escalating, include:
```
SEVERITY: P0/P1/P2/P3
SERVICE: [affected service name]
SYMPTOM: [what is observed]
IMPACT: [user/business impact]
STARTED: [when first detected]
ACTIONS TAKEN: [what has been tried]
NEXT STEP: [what needs to happen]
```
