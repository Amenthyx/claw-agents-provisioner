# Risk Register — Claw Agents Provisioner

> Version: 2.0
> Date: 2026-03-02
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)
> Supersedes: v1.0 (2026-02-26)

---

## Risk Matrix Legend

**Probability**: L (Low, <25%), M (Medium, 25-60%), H (High, >60%)
**Impact**: L (Low — minor inconvenience), M (Medium — delays milestone), H (High — blocks release), C (Critical — project failure)
**Risk Score**: Probability x Impact → color-coded (Green = acceptable, Yellow = monitor, Red = mitigate immediately)

---

## Active Risks

### R01 — NanoClaw No-Config-File Architecture

| Attribute | Value |
|-----------|-------|
| **ID** | R01 |
| **Category** | Technical |
| **Probability** | H (High) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M2 |
| **Owner** | DEVOPS |

**Description**: NanoClaw has no config files — it is designed to be configured by Claude Code modifying source code directly. There is no `onboard` command, no config.json, no config.toml. This makes automated provisioning fundamentally harder than the other 3 agents.

**Mitigation**:
1. Create a wrapper that pre-populates source code templates with `.env` values using `sed`/`envsubst` before build
2. Document the non-standard approach clearly in the agent-specific README section
3. Test the sed/envsubst injection on every supported channel (Telegram, Discord, WhatsApp, Slack)
4. Maintain a list of hardcoded source locations that need patching, version-locked to a specific NanoClaw commit

**Contingency**: If source injection proves too fragile, fall back to a "semi-automated" approach where `claw.sh` clones the repo, generates a checklist of manual edits, and opens the files for the user.

**Status**: Open

---

### R02 — ZeroClaw Rust Build OOM

| Attribute | Value |
|-----------|-------|
| **ID** | R02 |
| **Category** | Technical |
| **Probability** | M (Medium) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M1 |
| **Owner** | DEVOPS |

**Description**: ZeroClaw's Rust compilation requires 4 GB+ RAM. Vagrant VMs with default memory settings (1-2 GB) will OOM during `cargo build`. Docker builds on constrained hosts will also fail.

**Mitigation**:
1. Set Vagrant VM memory to 4096 MB minimum in the Vagrantfile
2. Provide pre-built binary download as fallback in `install-zeroclaw.sh` (skip compilation)
3. Use multi-stage Docker build: build in `rust:slim` (with sufficient memory), copy binary to minimal runtime image
4. Document host RAM requirements prominently (minimum 6 GB free for Vagrant build)

**Contingency**: Default to pre-built binary path; only attempt source build if `--build-from-source` flag is explicitly passed.

**Status**: Open

---

### R03 — Upstream Breaking Changes

| Attribute | Value |
|-----------|-------|
| **ID** | R03 |
| **Category** | External |
| **Probability** | H (High) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M1-M3 |
| **Owner** | DEVOPS |

**Description**: All 4 agents are fast-moving open-source projects (PicoClaw launched Feb 2026). API changes, config format changes, or dependency bumps could break our install scripts and Dockerfiles at any time.

**Mitigation**:
1. Pin to specific release tags or commit hashes in all install scripts and Dockerfiles
2. Document how to update pinned versions in a `UPDATING.md` section
3. CI pipeline tests against pinned versions, not `latest`
4. Set up GitHub Dependabot or manual monthly version check

**Contingency**: If an upstream break is detected, immediately freeze on the last known-good commit and file an issue.

**Status**: Open

---

### R04 — OpenClaw Memory Pressure in Multi-Agent Mode

| Attribute | Value |
|-----------|-------|
| **ID** | R04 |
| **Category** | Technical |
| **Probability** | M (Medium) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M3 |
| **Owner** | DEVOPS |

**Description**: OpenClaw uses ~1.52 GB RAM idle, up to 4 GB active. Running it alongside other agents in multi-agent docker-compose may exhaust host memory on machines with < 8 GB RAM.

**Mitigation**:
1. Set `mem_limit` in docker-compose for each agent profile
2. Document minimum host RAM requirements: 4 GB for single agent, 8 GB+ for multi-agent
3. Warn in `claw.sh` if available RAM is below threshold before starting multi-agent

**Contingency**: If host RAM is insufficient, `claw.sh` will refuse to start multi-agent mode and suggest running agents sequentially.

**Status**: Open

---

### R05 — API Key Sprawl Across Agents

| Attribute | Value |
|-----------|-------|
| **ID** | R05 |
| **Category** | Technical |
| **Probability** | H (High) |
| **Impact** | L (Low) |
| **Risk Score** | GREEN |
| **Milestone** | M1 |
| **Owner** | INFRA |

**Description**: Each agent uses different environment variable names for the same API providers (e.g., `ANTHROPIC_API_KEY` vs `CLAUDE_API_KEY` vs `API_KEY`). Users will be confused about which vars to set.

**Mitigation**:
1. `.env.template` uses a single unified naming convention with clear comments
2. Each agent's `entrypoint.sh` translates unified names to agent-specific names
3. `.env.template` comments explicitly state which agent uses which var

**Contingency**: N/A — low impact, mitigation is straightforward.

**Status**: Open

---

### R06 — LoRA Adapter Quality Varies by Domain

| Attribute | Value |
|-----------|-------|
| **ID** | R06 |
| **Category** | Technical |
| **Probability** | M (Medium) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M5b |
| **Owner** | BE |

**Description**: LoRA/QLoRA adapters for specialized domains (legal, medical, finance) require higher quality datasets and more training data than generic personal assistant use cases. Poor adapters can degrade agent performance rather than improve it.

**Mitigation**:
1. Ship pre-built adapter configs for the top 4 industries as well-tested baselines
2. Provide dataset augmentation guidance in the adapter catalog README
3. Document minimum dataset sizes per domain complexity level
4. Include a quality validation step: compare adapter output to base model output on 10 test questions
5. `--dry-run` flag validates adapter config before committing to training

**Contingency**: For domains where adapter quality is poor, fall back to system prompt enrichment (achieves ~70% of personalization without fine-tuning).

**Status**: Open

---

### R07 — QLoRA Requires GPU — Budget Clients Cannot Fine-Tune Locally

| Attribute | Value |
|-----------|-------|
| **ID** | R07 |
| **Category** | Technical |
| **Probability** | H (High) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M5b |
| **Owner** | BE |

**Description**: QLoRA training requires GPU (minimum 8-16 GB VRAM). Budget clients on Raspberry Pi or low-spec machines cannot fine-tune locally. Enterprise clients may not have GPU access either.

**Mitigation**:
1. Pre-built adapters ship with the repo — no GPU needed to **use** an adapter, only to **train** one
2. Provide `Dockerfile.finetune` for cloud GPU rental (RunPod, Lambda Labs)
3. Document cost per adapter training: ~$5-20 for 1-2 hours on A100
4. System prompt enrichment as a zero-GPU alternative for API-only models

**Contingency**: Offer Amenthyx-hosted training as part of the Enterprise and Managed service packages.

**Status**: Open

---

### R08 — Fine-Tuned Adapter Drift from Base Model Updates

| Attribute | Value |
|-----------|-------|
| **ID** | R08 |
| **Category** | Technical |
| **Probability** | M (Medium) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M5b |
| **Owner** | BE |

**Description**: When base models (Mistral, LLaMA, Phi) release new versions, existing LoRA adapters trained on previous versions may become incompatible or degrade in quality.

**Mitigation**:
1. Version-lock adapter configs to specific base model versions (e.g., `mistralai/Mistral-7B-v0.3`)
2. Document re-training procedure when base model updates
3. `adapter_config.json` includes `base_model_version` field for tracking
4. CI warns if adapter config references a deprecated model version

**Contingency**: Maintain a compatibility matrix of adapter-to-model-version pairs; auto-suggest re-training.

**Status**: Open

---

### R09 — Assessment Form Complexity

| Attribute | Value |
|-----------|-------|
| **ID** | R09 |
| **Category** | Usability |
| **Probability** | M (Medium) |
| **Impact** | L (Low) |
| **Risk Score** | GREEN |
| **Milestone** | M4 |
| **Owner** | BE |

**Description**: The assessment intake form has 8 sections with many fields. Consultants may skip or misunderstand fields, leading to incomplete assessments and incorrect platform/model selection.

**Mitigation**:
1. Provide `client-assessment.example.json` with 3 pre-filled examples (real estate, IoT, DevSecOps)
2. `./claw.sh validate --assessment` gives clear, actionable error messages for missing/invalid fields
3. JSON schema includes `description` fields and `examples` for every property
4. README includes a "filling the assessment" guide

**Contingency**: P2 assessment web form (deferred to v1.3) will eliminate JSON editing entirely.

**Status**: Open

---

### R10 — Client PII Accidental Commit

| Attribute | Value |
|-----------|-------|
| **ID** | R10 |
| **Category** | Security |
| **Probability** | H (High) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M1, M6 |
| **Owner** | INFRA |

**Description**: Client assessment files contain PII (name, company, industry, contact info). Risk of accidental `git add` of real client data.

**Mitigation**:
1. `.gitignore` all `client-assessment*.json` patterns except `*.example.json`
2. `.gitignore` all `.env` files (only `.env.template` tracked)
3. CI pipeline scans tracked files for PII patterns (email, phone, company name patterns)
4. Pre-commit hook rejects files matching `client-assessment*.json` (unless `.example.`)
5. README warns prominently about PII handling

**Contingency**: If PII is accidentally committed, use `git filter-branch` or BFG Repo-Cleaner to remove from history; notify affected client.

**Status**: Open

---

### R11 — Dataset License Compliance

| Attribute | Value |
|-----------|-------|
| **ID** | R11 |
| **Category** | Legal |
| **Probability** | M (Medium) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M5a |
| **Owner** | BE |

**Description**: All 50 datasets must be free/open licensed (Apache 2.0, MIT, CC-BY, CC-BY-SA, CC0, public domain). Accidentally including a commercially-restricted dataset in a public repo could create legal liability.

**Mitigation**:
1. `metadata.json` for each dataset documents the exact license with source URL
2. `validate_datasets.py` checks license field against an allowed-license list
3. CI pipeline runs license validation on every push
4. Dataset download script only pulls from pre-verified sources
5. Manual review of all 50 licenses before first commit of datasets

**Contingency**: If a license issue is discovered post-commit, immediately remove the dataset and replace with an alternative open-licensed source.

**Status**: Open

---

### R12 — Repository Size from Committed Datasets

| Attribute | Value |
|-----------|-------|
| **ID** | R12 |
| **Category** | Technical |
| **Probability** | L (Low) |
| **Impact** | M (Medium) |
| **Risk Score** | GREEN |
| **Milestone** | M5a |
| **Owner** | BE |

**Description**: Committing 50 datasets (each up to 10K rows) directly in the repo could push total size above GitHub's recommended limits. Estimated 200-400 MB total.

**Mitigation**:
1. Cap each dataset at 10K rows maximum (most will be 1-10 MB in JSONL)
2. Target total repo size < 500 MB
3. `.gitattributes` configures LFS for any individual file > 50 MB (safety net)
4. `validate_datasets.py` checks total size and warns if approaching 500 MB
5. Prefer JSONL format over Parquet (smaller for text-heavy data at < 10K rows)

**Contingency**: If total size exceeds 500 MB, reduce row counts for the largest datasets (from 10K to 5K).

**Status**: Open

---

### R13 — TLS Certificate Renewal Failure

| Attribute | Value |
|-----------|-------|
| **ID** | R13 |
| **Category** | Infrastructure |
| **Probability** | M (Medium) |
| **Impact** | H (High) |
| **Risk Score** | RED |
| **Milestone** | M8 |
| **Owner** | DEVOPS |

**Description**: Let's Encrypt TLS certificate renewal may fail silently due to DNS propagation issues, ACME challenge failures, or certbot misconfiguration. Expired certificates cause all HTTPS services to become inaccessible, breaking production deployments for enterprise clients.

**Mitigation**:
1. Health check script verifies certificate expiry > 7 days; alerts if approaching expiry
2. Certbot cron job runs twice daily (standard Let's Encrypt recommendation)
3. Nginx reload after successful renewal (zero-downtime)
4. Prometheus alert rule for cert expiry < 14 days
5. Document manual renewal procedure in operational runbook

**Contingency**: If automated renewal fails, runbook includes manual certbot command sequence. Self-signed certificate fallback for emergency access.

**Status**: Open

---

### R14 — E2E Test Flakiness

| Attribute | Value |
|-----------|-------|
| **ID** | R14 |
| **Category** | Testing |
| **Probability** | H (High) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M7 |
| **Owner** | QA |

**Description**: E2E tests that depend on Docker container startup, network readiness, and service health checks are inherently timing-dependent. Flaky tests erode CI confidence and slow down development velocity.

**Mitigation**:
1. Health-check gates before test execution (wait for all services healthy before running tests)
2. Configurable startup timeout with sensible defaults (30s per service, 120s total)
3. Retry with exponential backoff for transient failures (max 3 retries)
4. Separate flaky tests into a quarantine suite (non-blocking in CI)
5. Track flakiness rate per test; auto-quarantine tests failing > 5% of runs

**Contingency**: If flakiness rate exceeds 10% overall, refactor to use contract testing for cross-service flows and reserve E2E for critical path only.

**Status**: Open

---

### R15 — Grafana/Loki Resource Overhead

| Attribute | Value |
|-----------|-------|
| **ID** | R15 |
| **Category** | Infrastructure |
| **Probability** | M (Medium) |
| **Impact** | L (Low) |
| **Risk Score** | GREEN |
| **Milestone** | M11 |
| **Owner** | DEVOPS |

**Description**: Adding Grafana, Loki, and Prometheus to the Docker Compose stack increases host resource consumption. On resource-constrained hosts (8 GB RAM, 2 CPU cores), the monitoring stack may compete with agent services for resources, degrading performance.

**Mitigation**:
1. Monitoring stack deployed as optional Docker Compose profile (`--profile monitoring`), not required for core operation
2. Resource limits set in docker-compose: Grafana (256 MB), Loki (512 MB), Prometheus (256 MB)
3. Loki retention set to 7 days by default (configurable via env)
4. Document minimum host requirements: 4 GB for agents-only, 8 GB for agents + monitoring
5. Health aggregator still works without monitoring stack (port 9094 is standalone)

**Contingency**: If host resources are insufficient, monitoring stack can be deployed on a separate host and pointed at the agent host's /metrics endpoints remotely.

**Status**: Open

---

### R16 — Load Test Reveals SQLite Bottleneck

| Attribute | Value |
|-----------|-------|
| **ID** | R16 |
| **Category** | Performance |
| **Probability** | H (High) |
| **Impact** | M (Medium) |
| **Risk Score** | YELLOW |
| **Milestone** | M9 |
| **Owner** | BE |

**Description**: Under sustained load (100 req/s), SQLite's write-lock contention may cause P95 latency to exceed targets for memory and billing services. SQLite is single-writer, and concurrent writes from multiple agent instances will serialize.

**Mitigation**:
1. WAL (Write-Ahead Logging) mode already enabled on all SQLite databases
2. Connection pooling via DAL (Data Access Layer) already implemented
3. PostgreSQL migration path ready (M8 deliverable) as production alternative
4. k6 load tests specifically target SQLite-backed endpoints to identify bottleneck threshold
5. Read replicas pattern: separate read and write connections for memory service

**Contingency**: If SQLite P95 exceeds targets under load, recommend PostgreSQL for production deployments. Document the SQLite concurrency limit (expected: ~50 write req/s) in production guide.

**Status**: Open

---

## Risk Summary Matrix

| ID | Risk | Prob | Impact | Score | Status |
|----|------|------|--------|-------|--------|
| R01 | NanoClaw no-config architecture | H | H | RED | Open |
| R02 | ZeroClaw Rust build OOM | M | H | RED | Open |
| R03 | Upstream breaking changes | H | M | YELLOW | Open |
| R04 | OpenClaw memory pressure | M | M | YELLOW | Open |
| R05 | API key sprawl | H | L | GREEN | Open |
| R06 | LoRA adapter quality by domain | M | H | RED | Open |
| R07 | QLoRA requires GPU | H | M | YELLOW | Open |
| R08 | Adapter drift from model updates | M | M | YELLOW | Open |
| R09 | Assessment form complexity | M | L | GREEN | Open |
| R10 | Client PII accidental commit | H | H | RED | Open |
| R11 | Dataset license compliance | M | H | RED | Open |
| R12 | Repository size from datasets | L | M | GREEN | Open |
| R13 | TLS certificate renewal failure | M | H | RED | Open |
| R14 | E2E test flakiness | H | M | YELLOW | Open |
| R15 | Grafana/Loki resource overhead | M | L | GREEN | Open |
| R16 | Load test reveals SQLite bottleneck | H | M | YELLOW | Open |

### Risk Distribution

| Score | Count | IDs |
|-------|-------|-----|
| RED (immediate action) | 6 | R01, R02, R06, R10, R11, R13 |
| YELLOW (monitor closely) | 6 | R03, R04, R07, R08, R14, R16 |
| GREEN (acceptable) | 4 | R05, R09, R12, R15 |

---

## Review Schedule

- **Weekly**: Review all RED risks; update mitigation status
- **Per-milestone**: Full risk register review; identify new risks
- **Pre-release (M6)**: Final risk sign-off; confirm all RED risks mitigated or accepted

---

*Risk Register v2.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
*Updated 2026-03-02 for v2.0 production-specific risks (R13-R16)*
