# k6 Load Test Configuration -- Claw Agents Provisioner v2.0

> Created: 2026-03-02
> Tool: k6 (Grafana) -- JavaScript-based load testing
> Location: `tests/load/`

---

## 1. Test Suite Overview

| Script | Service | Port | Target RPS | P95 Target | Error Rate |
|--------|---------|------|-----------|------------|------------|
| `k6-router.js` | Model Router | 9095 | 100 req/s | < 200ms | < 1% |
| `k6-memory.js` | Conversation Memory | 9096 | 50 req/s | < 100ms | < 1% |
| `k6-rag.js` | RAG Pipeline | 9097 | 50 req/s | < 500ms | < 1% |
| `k6-dashboard.js` | Fleet Dashboard | 9099 | 30 req/s | < 300ms | < 1% |

**Shared config:** `k6-config.js` -- Base URLs, auth tokens, custom metrics, helper functions.
**Runner:** `run-load-tests.sh` -- Sequential execution with JSON output capture.

---

## 2. Load Profiles

### Standard Pattern (all services)

```
Phase 1: Ramp Up     -- 30 seconds  -- 0 to target VUs
Phase 2: Sustained   -- 2 minutes   -- Constant target VUs
Phase 3: Ramp Down   -- 30 seconds  -- Target to 0 VUs

Total duration: 3 minutes per service
```

### VU (Virtual User) Targets

| Service | Peak VUs | Approx RPS | Rationale |
|---------|----------|------------|-----------|
| Router | 100 | ~100 req/s | Primary traffic endpoint, highest load |
| Memory | 50 | ~50 req/s | Write-heavy, persistence layer |
| RAG | 50 | ~50 req/s | Compute-heavy search operations |
| Dashboard | 30 | ~30 req/s | Admin UI, lower traffic |

---

## 3. Endpoint Coverage

### Router (k6-router.js)

| Endpoint | Method | Weight | Description |
|----------|--------|--------|-------------|
| `/v1/chat/completions` | POST | 70% | Core chat completion (OpenAI-compatible) |
| `/health` | GET | 15% | Health check |
| `/v1/models` | GET | 10% | List available models |
| `/api/router/status` | GET | 5% | Router status and metrics |

### Memory (k6-memory.js)

| Endpoint | Method | Weight | Description |
|----------|--------|--------|-------------|
| `/api/memory/conversations` | POST | 40% | Store conversation + messages |
| `/api/memory/conversations` | GET | 25% | Retrieve conversations |
| `/api/memory/search` | POST | 25% | Search across messages |
| `/api/memory/stats` | GET | 5% | Memory statistics |
| `/health` | GET | 5% | Health check |

### RAG (k6-rag.js)

| Endpoint | Method | Weight | Description |
|----------|--------|--------|-------------|
| `/api/rag/ingest` | POST | 30% | Document ingestion |
| `/api/rag/search` | POST | 40% | Semantic search |
| `/v1/search` | POST | 15% | OpenAI-compatible search |
| `/api/rag/status` | GET | 10% | RAG pipeline status |
| `/health` | GET | 5% | Health check |

### Dashboard (k6-dashboard.js)

| Endpoint | Method | Weight | Description |
|----------|--------|--------|-------------|
| `/` | GET | 15% | Dashboard HTML page |
| `/api/status` | GET | 20% | System status summary |
| `/api/agents` | GET | 15% | Agent list |
| `/api/strategy` | GET | 15% | Routing strategy |
| `/api/billing` | GET | 10% | Billing overview |
| `/api/monitoring` | GET | 10% | System metrics |
| `/api/security` | GET | 5% | Security posture |
| `/api/config` | GET | 5% | System configuration |
| `/health` | GET | 5% | Health check |

---

## 4. Thresholds

### Global Thresholds (applied to all tests)

| Metric | Threshold | Action on Breach |
|--------|-----------|-----------------|
| `http_req_duration` | p(95) < service target | Test fails |
| `http_req_failed` | rate < 0.01 (1%) | Test fails |

### Service-Specific Thresholds

| Service | Custom Metric | Threshold |
|---------|--------------|-----------|
| Router | `router_chat_latency` | p(95) < 200ms |
| Router | `router_chat_errors` | count < 50 |
| Memory | `memory_store_latency` | p(95) < 100ms |
| Memory | `memory_retrieve_latency` | p(95) < 100ms |
| Memory | `memory_search_latency` | p(95) < 150ms |
| RAG | `rag_ingest_latency` | p(95) < 500ms |
| RAG | `rag_search_latency` | p(95) < 500ms |
| Dashboard | `dashboard_status_latency` | p(95) < 300ms |
| Dashboard | `dashboard_agents_latency` | p(95) < 300ms |
| Dashboard | `dashboard_strategy_latency` | p(95) < 300ms |

---

## 5. Custom Metrics (Grafana/Prometheus)

All scripts export custom metrics with tags for dashboard integration:

| Metric | Type | Tags | Description |
|--------|------|------|-------------|
| `custom_errors` | Counter | endpoint | Total errors across checks |
| `custom_response_time` | Trend | endpoint | Response time distribution |
| `{service}_{op}_errors` | Counter | -- | Per-operation error count |
| `{service}_{op}_latency` | Trend | -- | Per-operation latency |

### Tag Structure

```javascript
tags: {
  service: "router|memory|rag|dashboard",
  port: "9095|9096|9097|9099",
  test_type: "load",
  endpoint: "<specific_endpoint>"
}
```

---

## 6. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `K6_BASE_HOST` | `localhost` | Target hostname |
| `K6_AUTH_TOKEN` | `test-token-for-load-testing` | Bearer auth token |
| `K6_ROUTER_PORT` | `9095` | Router service port |
| `K6_MEMORY_PORT` | `9096` | Memory service port |
| `K6_RAG_PORT` | `9097` | RAG service port |
| `K6_DASHBOARD_PORT` | `9099` | Dashboard service port |

---

## 7. Running the Tests

### Individual Service

```bash
# Router load test
k6 run --env K6_AUTH_TOKEN=<token> tests/load/k6-router.js

# With JSON output for post-processing
k6 run --out json=results/router.json tests/load/k6-router.js

# With custom host
k6 run --env K6_BASE_HOST=staging.example.com tests/load/k6-router.js
```

### Full Suite

```bash
# Run all services sequentially
bash tests/load/run-load-tests.sh

# Run single service
bash tests/load/run-load-tests.sh --service router

# Dry-run (validate scripts only, no execution)
bash tests/load/run-load-tests.sh --dry-run
```

### Docker

```bash
# Run via k6 Docker image
docker run --rm -i \
  --network host \
  -v $(pwd)/tests/load:/scripts \
  -e K6_AUTH_TOKEN=<token> \
  grafana/k6 run /scripts/k6-router.js
```

---

## 8. Interpreting Results

### Pass Criteria

A service passes its load test when ALL thresholds are met:
- P95 latency within target
- Error rate below 1%
- Custom error counters below limits

### Common Failure Modes

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| High P95, low error rate | Service under-provisioned (CPU/RAM) | Scale up or optimize |
| Low latency, high error rate | Auth misconfiguration or rate limiting | Check token and rate limits |
| Increasing latency over time | Memory leak or connection exhaustion | Check resource usage |
| All requests fail | Service not running or wrong port | Verify deployment |

---

## 9. Integration with CI/CD

The load tests are designed for integration with the CI pipeline:

1. **Pre-merge:** Run `--dry-run` to validate k6 script syntax
2. **Staging deploy:** Run full suite against staging environment
3. **Production canary:** Run with reduced VUs (10% of target) against canary
4. **Post-deploy:** Smoke test + abbreviated load test (30s sustained)

### GitHub Actions Example

```yaml
- name: k6 Load Test (Staging)
  run: |
    bash tests/load/run-load-tests.sh
  env:
    K6_AUTH_TOKEN: ${{ secrets.STAGING_AUTH_TOKEN }}
    K6_BASE_HOST: staging.internal
```
