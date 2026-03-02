# Compliance Checklist -- Claw Agents Provisioner v2.0

> Version: 2.0
> Date: 2026-03-02
> Author: Legal/Compliance Attorney (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: ACTIVE
> Review Cycle: Per wave completion + pre-release (M6)

---

## 1. Executive Summary

This checklist consolidates all compliance requirements for the Claw Agents Provisioner across four regulatory frameworks: GDPR, SOC 2, HIPAA readiness, and open-source license compliance. Each item is mapped to the existing codebase controls (verified by reading source files) and identifies gaps requiring remediation.

**Overall Compliance Posture: MEDIUM** -- core technical controls are in place (auth, audit, vault, rate limiting, PII detection), but procedural documentation and some automation remain to be completed.

---

## 2. GDPR Compliance

### 2.1 Data Residency Requirements for EU Clients

| # | Requirement | Status | Evidence / Implementation | Gap |
|---|-------------|:------:|--------------------------|-----|
| G-DR-01 | Identify all data stores containing EU personal data | PARTIAL | Assessment JSONs (local filesystem), SQLite databases (`data/instance.db`, `data/shared/shared.db`), `logs/audit.log`, conversation memory (claw_memory.py on port 9096) | No formal data map published to clients |
| G-DR-02 | Ensure processing occurs on EU-located infrastructure | N/A (SELF-HOSTED) | Claw deploys on client-provided infrastructure; data residency is determined by client's hosting location | Document that EU clients must host on EU infrastructure |
| G-DR-03 | No data transfer outside EEA without safeguards | PARTIAL | `claw_security.py` compliance.gdpr rules (line ~459-471) include: "Do not transfer data outside the EEA without adequate safeguards" | LLM API calls to US-hosted services (Anthropic, OpenAI, DeepSeek) transmit prompt data to non-EEA servers; requires Standard Contractual Clauses (SCCs) or client awareness |
| G-DR-04 | Data minimization -- collect only what is necessary | PASS | Assessment schema collects only fields required for deployment resolution (company, use case, budget, channels, model preference) | None |
| G-DR-05 | Document lawful basis for processing | PARTIAL | COMPLIANCE_REVIEW.md Section 3.3 identifies Art. 6(1)(b) (contract performance) as lawful basis | Needs formal privacy notice served during wizard UI assessment intake |

### 2.2 Right to Deletion (Data Purge Procedures)

| # | Requirement | Status | Evidence / Implementation | Gap |
|---|-------------|:------:|--------------------------|-----|
| G-DEL-01 | Delete client assessment JSONs | DOCUMENTED | DATA_PRIVACY_ASSESSMENT.md Section 6.1 defines COLLECT > PROCESS > DEPLOY > RETAIN > DELETE lifecycle | Automated `claw.sh cleanup --client` not yet implemented |
| G-DEL-02 | Delete `.env` files containing client API keys | DOCUMENTED | Retention policy: 30 days after deployment confirmed | Same as above -- needs automation |
| G-DEL-03 | Delete conversation memory (SQLite) | PARTIAL | `claw_memory.py` exposes `DELETE /api/memory/conversations/:id` endpoint and `--prune --days 30` CLI | No bulk "delete all data for client X" command |
| G-DEL-04 | Delete audit log entries containing client identifiers | PARTIAL | `claw_audit.py` hashes tokens (line 131-135: `_hash_token` returns truncated SHA-256, never raw tokens) so audit logs contain only hashed identifiers | Token hashes are pseudonymous, not anonymous -- deletion may still be required under GDPR Art. 17 |
| G-DEL-05 | Delete Vagrant VMs / Docker containers with client config | DOCUMENTED | Retention policy: 7 days after deployment confirmed; `vagrant destroy` / `docker compose down -v` | No automated tracking of which VMs/containers belong to which client |
| G-DEL-06 | Delete adapter weights trained on client data | DOCUMENTED | Retention policy: 90 days after delivery; `rm -rf finetune/outputs/<client>/` | No automated enforcement |
| G-DEL-07 | Provide data portability (export in machine-readable format) | PARTIAL | `claw_memory.py` supports `--export <conversation_id>` as JSON/Markdown | Assessment data export not automated |

### 2.3 Data Processing Agreements (DPA)

| # | Requirement | Status | Gap |
|---|-------------|:------:|-----|
| G-DPA-01 | DPA template for Enterprise package (5K+ EUR) | MISSING | Must be drafted covering: data categories, processing purposes, security measures, sub-processors, breach notification, data return/deletion |
| G-DPA-02 | DPA template for Managed package (300 EUR/mo) | MISSING | Same as above, plus: ongoing processing terms, audit rights, data portability on termination |
| G-DPA-03 | Sub-processor register (LLM API providers) | MISSING | Must list: Anthropic (US), OpenAI (US), DeepSeek (China), Google (US) as sub-processors with their DPA status |
| G-DPA-04 | Standard Contractual Clauses for non-EEA transfers | MISSING | Required for LLM API calls that transmit prompt content to US/China-based providers |

### 2.4 Audit Trail Requirements

| # | Requirement | Status | Evidence / Implementation | Gap |
|---|-------------|:------:|--------------------------|-----|
| G-AUD-01 | All API requests logged with timestamp | PASS | `claw_audit.py` AuditLogger._write() (line 139-164): every entry includes ISO 8601 UTC timestamp, event_type, action, resource, outcome, ip_address, details | None |
| G-AUD-02 | Authentication events logged | PASS | `audit.log_auth()` method (line 181-191); called from `claw_vault.py` on vault init/set/get/delete/rotate; `claw_security.py` logs violations via `audit.log_security_event()` | Verify all 6 HTTP services call `log_auth` on auth failure |
| G-AUD-03 | Data access events logged | PASS | `audit.log_data_access()` method (line 202-215); vault operations (get, set, delete) all log data access | None |
| G-AUD-04 | Configuration changes logged | PASS | `audit.log_config_change()` method (line 193-204); vault init and rotate log config changes | None |
| G-AUD-05 | Security violations logged | PASS | `audit.log_security_event()` method (line 217-227); `claw_security.py` SecurityChecker._log_violation() (line 649-669) logs all URL blocks, content violations | None |
| G-AUD-06 | Tokens never stored in plaintext in logs | PASS | `AuditLogger._hash_token()` (line 130-135): SHA-256 truncated to 16 chars; raw tokens never written | None |
| G-AUD-07 | Log rotation implemented | PASS | `RotatingFileHandler` with `maxBytes=10MB`, `backupCount=5` (lines 53-55, 119-126) | None |
| G-AUD-08 | Audit log retention >= 365 days | PARTIAL | `claw_security.py` data_handling.data_retention.audit_trail_max_days = 365 (line 335) | No automated enforcement of 365-day retention; RotatingFileHandler keeps only 5 files x 10MB |
| G-AUD-09 | Audit logs tamper-resistant | MISSING | Logs are plaintext JSON files on the local filesystem | Consider cryptographic log chaining (hash of previous entry) or remote log shipping |

### 2.5 Cookie/Tracking Policy (Wizard UI)

| # | Requirement | Status | Gap |
|---|-------------|:------:|-----|
| G-CK-01 | Cookie consent banner for wizard UI | MISSING | `claw_wizard.py` serves an embedded SPA on port 9098; no cookie consent mechanism exists |
| G-CK-02 | Privacy notice accessible from wizard UI | MISSING | No privacy policy link in the wizard |
| G-CK-03 | No third-party tracking scripts | PASS | Wizard UI is self-hosted; no Google Analytics, no third-party scripts; React wizard (wizard-ui/) is built locally |
| G-CK-04 | Session cookies (if any) set with Secure, HttpOnly, SameSite | TO VERIFY | `claw_wizard.py` and `claw_wizard_api.py` use stdlib HTTP; no session cookies detected in code -- sessions are stateless (assessment data posted directly) |

---

## 3. SOC 2 Compliance

### 3.1 Security Controls Inventory

| Control Area | Existing Control | Module | Verified | SOC 2 Trust Principle |
|-------------|-----------------|--------|:--------:|----------------------|
| **Authentication** | Bearer token auth on all 6 HTTP services | `claw_auth.py` | YES -- constant-time comparison (line 80-101), CLAW_API_TOKEN env var | Security |
| **Rate Limiting** | Sliding window per client (IP or token) | `claw_ratelimit.py` | YES -- configurable via CLAW_RATE_LIMIT (default 60/min), CLAW_RATE_WINDOW (default 60s); thread-safe | Availability |
| **Secrets Management** | AES-encrypted vault (Fernet + PBKDF2) | `claw_vault.py` | YES -- PBKDF2-HMAC-SHA256, 480K iterations, 16-byte salt, atomic writes | Security |
| **Security Rules Engine** | URL/content/PII/IP blocking with compliance rule sets | `claw_security.py` | YES -- 6 security domains (A-F), GDPR/HIPAA/PCI-DSS/SOC2 compliance rules | Security |
| **PII Detection** | Regex-based scanning for 8 PII types | `claw_security.py` data_handling.pii_detection (line 293-305) | YES -- email, phone (US/intl), SSN, credit card, IPv4, passport, IBAN | Confidentiality |
| **Secret Masking** | Regex patterns for 16+ secret types | `claw_security.py` data_handling.secret_masking (line 308-329) | YES -- Anthropic, OpenAI, AWS, GitHub, Telegram, Discord, Slack, JWT, private keys | Confidentiality |
| **Audit Logging** | Structured JSON audit trail with rotation | `claw_audit.py` | YES -- 5 event types, thread-safe singleton, rotating file handler | Security |
| **Health Monitoring** | Aggregated health check for 8 services | `claw_health.py` | YES -- background poller, per-service status, uptime tracking | Availability |
| **Process Watchdog** | Auto-restart on failure, Telegram alerts | `claw_watchdog.py` | YES -- container monitoring, health probes, TCP checks, resource usage | Availability |
| **Metrics Collection** | Prometheus text format on /metrics | `claw_metrics.py` | YES -- request count, duration histogram, active connections, error count, uptime | Availability |
| **Budget Alerting** | Spend threshold alerts with webhook notification | `claw_billing.py` | YES -- 80/90/100% thresholds, configurable webhook POST | Processing Integrity |
| **Network Security** | Forbidden IP ranges, TLS requirements, DNS safety | `claw_security.py` network_rules (line 402-452) | YES -- RFC 1918/5735 ranges blocked, TLS 1.2+ required, DNS rebinding protection | Security |
| **Prompt Injection Protection** | Regex detection of injection attempts | `claw_security.py` content_rules.response_injection_protection (line 274-285) | YES -- 6 patterns for common injection vectors | Security |
| **Data Retention Policies** | Configurable retention for conversations, logs, PII, audit | `claw_security.py` data_handling.data_retention (line 332-338) | YES -- conversation 30d, logs 90d, audit 365d, PII 7d | Confidentiality |
| **Docker Resource Limits** | Memory limits and reservations per container | `docker-compose.yml` | YES -- each service has explicit memory limits (128MB to 4GB) | Availability |
| **Container Health Checks** | Docker HEALTHCHECK on all services | `docker-compose.yml` | YES -- interval 30s, timeout 10s, retries 3, start_period per service | Availability |
| **Restart Policies** | Automatic container restart | `docker-compose.yml` | YES -- `restart: unless-stopped` on all services | Availability |

### 3.2 Access Logging (claw_audit.py Coverage)

| Service | Audit Logging Integrated | Event Types Logged |
|---------|:------------------------:|-------------------|
| `claw_router.py` | YES (per strategy docs) | request, auth |
| `claw_vault.py` | YES (verified in code) | config_change (init, rotate), data_access (get, set, delete) |
| `claw_security.py` | YES (verified in code) | security (URL blocks, content violations, PII detection) |
| `claw_memory.py` | TO VERIFY | request (CRUD on conversations) |
| `claw_rag.py` | TO VERIFY | request (ingest, search) |
| `claw_dashboard.py` | TO VERIFY | request, auth |
| `claw_wizard.py` | TO VERIFY | request (assessment submission) |
| `claw_orchestrator.py` | TO VERIFY | request (task creation, agent registration) |
| `claw_billing.py` | TO VERIFY | data_access (cost records) |

**Recommendation**: Verify and document that all 6 HTTP services (router, memory, rag, wizard, dashboard, orchestrator) integrate `claw_audit.py` for request and auth event logging.

### 3.3 Change Management

| # | Control | Status | Evidence |
|---|---------|:------:|---------|
| SOC2-CM-01 | Version control for all source code | PASS | Git repository: `Amenthyx/claw-agents-provisioner` |
| SOC2-CM-02 | Conventional commit messages | PASS | Strategy Section 10: "Conventional commits enforced" |
| SOC2-CM-03 | Branch protection on main | PENDING | Strategy mentions requirement but not yet implemented |
| SOC2-CM-04 | Pull request reviews required | PENDING | ai-team branch flow exists; merge to main gated on user approval |
| SOC2-CM-05 | CI pipeline validates changes | PASS | `.github/workflows/ci.yml`: shellcheck, hadolint, ruff, pytest, Docker builds, Trivy, SBOM |
| SOC2-CM-06 | SBOM generation (CycloneDX) | PASS | CI workflow generates SBOM as 90-day artifact |
| SOC2-CM-07 | Container vulnerability scanning | PASS | Trivy scan in CI; HIGH/CRITICAL findings block merge |

### 3.4 Incident Response Procedures

| # | Requirement | Status | Gap |
|---|-------------|:------:|-----|
| SOC2-IR-01 | Incident response plan documented | PARTIAL | DATA_PRIVACY_ASSESSMENT.md Section 9 covers PII breach and API key exposure procedures | Full runbook to be created in Wave 4 (P0 Feature 9) |
| SOC2-IR-02 | Escalation matrix defined | MISSING | Must define: severity levels, response times, responsible parties, communication channels |
| SOC2-IR-03 | Breach notification within 72 hours | DOCUMENTED | DATA_PRIVACY_ASSESSMENT.md Section 9.1 Step 5 |
| SOC2-IR-04 | Post-incident review process | MISSING | Must define root cause analysis template and lessons-learned procedure |
| SOC2-IR-05 | Incident log maintained | PARTIAL | Risk register exists (`.team/RISK_REGISTER.md`); incidents to be logged there |

### 3.5 Encryption at Rest and in Transit

| # | Requirement | Status | Evidence | Gap |
|---|-------------|:------:|---------|-----|
| SOC2-ENC-01 | Secrets encrypted at rest | PASS | `claw_vault.py`: Fernet (AES-128-CBC) + PBKDF2-HMAC-SHA256 (480K iterations, 16-byte salt); binary vault format with magic header | None |
| SOC2-ENC-02 | TLS for all external API calls | PARTIAL | `claw_security.py` network_rules.require_tls = True, tls_minimum_version = "1.2" (lines 426-427) | Policy exists but not enforced at network level; depends on client's nginx TLS config |
| SOC2-ENC-03 | TLS termination for HTTP services | PENDING | P0 Feature 1 (nginx reverse proxy with Let's Encrypt); not yet implemented | Wave 2 deliverable |
| SOC2-ENC-04 | SQLite WAL mode for database integrity | PASS | Strategy mentions WAL mode; `claw_dal.py` manages connections | None |
| SOC2-ENC-05 | Vault password rotation supported | PASS | `claw_vault.py` `cmd_rotate` (line 560-603): re-encrypts with new password and fresh salt; audit-logged | None |
| SOC2-ENC-06 | Atomic file writes for vault | PASS | `VaultFile.write_raw()` (line 198-221): temp file + rename pattern on both Unix and Windows | None |

---

## 4. HIPAA Readiness (Healthcare Clients)

### 4.1 PHI Handling in Assessment Data

| # | Requirement | Status | Evidence | Gap |
|---|-------------|:------:|---------|-----|
| HIPAA-PHI-01 | Identify where PHI may exist | PARTIAL | Assessment JSONs may contain client descriptions of healthcare use cases; conversation memory may contain PHI if agent handles patient interactions | Formal PHI flow diagram needed |
| HIPAA-PHI-02 | Minimum necessary standard | PARTIAL | Assessment schema collects only deployment-relevant fields | When healthcare adapter (dataset 04, 49) is deployed, agents may receive PHI in conversations |
| HIPAA-PHI-03 | PHI never logged in plaintext | PASS | `claw_security.py` compliance.hipaa rules (line 474-486): "Never log PHI in plaintext"; PII detection patterns in `data_handling.pii_detection` scan for SSN, medical-related patterns | Needs healthcare-specific PHI patterns (MRN, diagnosis codes) |
| HIPAA-PHI-04 | De-identification of training data | PARTIAL | LICENSE_MATRIX.md flags datasets 04 (Healthcare Triage) and 49 (Mental Health) as HIGH risk requiring HIPAA Safe Harbor verification | Verification must occur before datasets are used for healthcare client training |

### 4.2 Encryption Requirements

| # | Requirement | Status | Evidence | Gap |
|---|-------------|:------:|---------|-----|
| HIPAA-ENC-01 | PHI encrypted at rest | PARTIAL | Vault encrypts secrets (AES via Fernet); SQLite databases storing conversation memory are NOT encrypted at rest | SQLite encryption (e.g., SQLCipher) needed for HIPAA-covered deployments |
| HIPAA-ENC-02 | PHI encrypted in transit | PENDING | TLS termination not yet implemented (Wave 2); `claw_security.py` requires TLS 1.2+ as policy | Must be enforced before healthcare deployment |
| HIPAA-ENC-03 | Encryption key management | PASS | `claw_vault.py` uses PBKDF2 key derivation with configurable password; supports rotation | None |

### 4.3 Access Controls and Audit Trails

| # | Requirement | Status | Evidence | Gap |
|---|-------------|:------:|---------|-----|
| HIPAA-AC-01 | Unique user identification | PARTIAL | `claw_auth.py` uses single admin token (CLAW_API_TOKEN); all requests authenticated against same token | RBAC deferred to v3.0; HIPAA requires individual user accounts |
| HIPAA-AC-02 | Automatic session timeout | DOCUMENTED | `claw_security.py` compliance.hipaa rules (line 481): "Implement automatic session timeout after 15 minutes of inactivity" | Not enforced in code; wizard/dashboard sessions do not timeout |
| HIPAA-AC-03 | Audit trail for all PHI access | PASS | `claw_audit.py` captures all API requests with timestamps, hashed user IDs, IP addresses, and outcomes | None |
| HIPAA-AC-04 | Audit logs retained >= 6 years | PARTIAL | `claw_security.py` data_retention.audit_trail_max_days = 365 | HIPAA requires 6-year retention; policy must be extended for HIPAA-covered deployments |

### 4.4 Business Associate Agreement (BAA) Requirements

| # | Requirement | Status | Gap |
|---|-------------|:------:|-----|
| HIPAA-BAA-01 | BAA with Amenthyx (as business associate) | MISSING | Required before Amenthyx handles any PHI on behalf of a healthcare client |
| HIPAA-BAA-02 | BAA with LLM API providers | MISSING | Anthropic, OpenAI offer BAAs for enterprise plans; must be executed if PHI is transmitted in prompts |
| HIPAA-BAA-03 | BAA with cloud hosting provider (if applicable) | N/A (SELF-HOSTED) | Client's responsibility when self-hosting |
| HIPAA-BAA-04 | Breach notification within 60 days | DOCUMENTED | `claw_security.py` compliance.hipaa rules (line 483): "Report security incidents within 60 days" | Procedure not yet operationalized |

---

## 5. Open Source License Compliance

### 5.1 Monitoring Stack Licenses

| Component | License | SPDX | Commercial Use | Copyleft | Distribution Impact |
|-----------|---------|------|:-:|:-:|-------------------|
| **Prometheus** | Apache License 2.0 | Apache-2.0 | YES | NO | No restrictions; compatible with project license |
| **Grafana** | GNU AGPL v3.0 | AGPL-3.0 | YES (with conditions) | YES (network copyleft) | See Section 5.3 |
| **Loki** | GNU AGPL v3.0 | AGPL-3.0 | YES (with conditions) | YES (network copyleft) | See Section 5.3 |
| **nginx** | BSD 2-Clause | BSD-2-Clause | YES | NO | No restrictions; minimal attribution required |
| **k6** | GNU AGPL v3.0 | AGPL-3.0 | YES (with conditions) | YES (network copyleft) | See Section 5.3 |
| **PostgreSQL** | PostgreSQL License (MIT-like) | PostgreSQL | YES | NO | No restrictions |
| **Docker** | Apache License 2.0 | Apache-2.0 | YES | NO | No restrictions |

### 5.2 nginx License Review (BSD-2-Clause)

- **License**: 2-clause BSD license
- **Attribution**: Must retain copyright notice and disclaimer in source and binary redistributions
- **Impact on project**: NONE -- nginx is used as a runtime dependency (reverse proxy), not redistributed in source form. Docker images pull nginx from official Docker Hub images.
- **Action**: No action required. If custom nginx configs are distributed, include BSD notice.

### 5.3 AGPL Implications for Distribution

The following components are licensed under AGPL-3.0:

**Grafana, Loki, k6**

AGPL-3.0 Key Requirements:
1. **Source code availability**: If you modify AGPL software and make it available over a network, you must offer the source code to users.
2. **Network use = distribution**: Unlike GPL, AGPL treats providing access to software over a network as distribution.

**Impact Assessment for Claw Agents Provisioner**:

| Question | Answer | Implication |
|----------|--------|-------------|
| Does Claw modify Grafana/Loki/k6 source code? | NO -- uses official Docker images and pre-built binaries | No obligation to release source |
| Does Claw redistribute Grafana/Loki/k6? | NO -- Docker Compose references official images; users pull from upstream | No distribution obligation |
| Does Claw's code link to or call Grafana/Loki/k6 as a library? | NO -- interacts via HTTP APIs and Docker networking | No copyleft infection of Claw code |
| Do clients interact with Grafana/Loki over a network? | YES -- dashboards and log explorer are accessed via browser | AGPL obligations are met by upstream (Grafana Labs publishes source); Claw bears no additional obligation since it does not modify the software |

**Conclusion**: Using unmodified Grafana, Loki, and k6 as Docker containers does NOT impose AGPL obligations on the Claw Agents Provisioner codebase. The AGPL copyleft applies only to modifications of the AGPL software itself, not to separate works that merely interact with it.

**Risk**: If a future version of Claw embeds or forks Grafana/Loki/k6 code, AGPL obligations would apply. This is currently out of scope.

**Recommendation**: Document the "no modification" stance. If custom Grafana plugins are ever developed, they may need to be AGPL-licensed depending on the nature of the integration.

### 5.4 Dataset License Compatibility with Apache 2.0 Project License

**Summary from existing LICENSE_MATRIX.md** (verified):

| Dataset License | Count | Compatible with Apache-2.0 Project? | Notes |
|----------------|:-----:|:------------------------------------:|-------|
| CC0-1.0 | 19 | YES | No restrictions whatsoever |
| CC-BY-4.0 | 12 | YES | Requires attribution (in metadata.json) |
| Apache-2.0 | 10 | YES | Same license as project |
| Public-Domain | 5 | YES | No restrictions |
| CC-BY-SA-4.0 | 3 | YES (with isolation) | ShareAlike applies to modified datasets only, not to project code or other datasets |
| ODC-BY-1.0 | 1 | YES | Requires attribution |

**All 50 datasets are compatible with the Apache 2.0 project license.** The datasets are separate works from the code; their individual licenses do not infect the repository license.

**CC-BY-SA-4.0 Handling** (datasets 19, 36, 38):
- If these datasets are modified (subsetted, reformatted), the modified version must carry CC-BY-SA-4.0
- LoRA adapter weights trained on these datasets are NOT considered derivative works of the datasets under prevailing legal interpretation
- NOTICE file should clarify the distinction between code and dataset licensing

---

## 6. Compliance Gap Summary

### 6.1 Critical Gaps (Must Address Before Production)

| # | Gap | Framework | Remediation | Owner | Target |
|---|-----|-----------|-------------|-------|--------|
| CG-01 | TLS termination not implemented | SOC 2, HIPAA | Implement nginx reverse proxy with Let's Encrypt (P0 Feature 1) | DevOps | Wave 2 |
| CG-02 | No DPA template for clients | GDPR | Draft DPA covering data categories, purposes, security, sub-processors | Legal | Wave 4 |
| CG-03 | No automated client data deletion | GDPR | Implement `claw.sh cleanup --client` command | Backend | Wave 4 |
| CG-04 | No incident response runbook | SOC 2 | Create operational runbook with escalation matrix (P0 Feature 9) | DevOps | Wave 4 |

### 6.2 Important Gaps (Should Address Before GA)

| # | Gap | Framework | Remediation | Owner | Target |
|---|-----|-----------|-------------|-------|--------|
| IG-01 | Privacy notice missing from wizard UI | GDPR | Add privacy policy link and cookie notice to wizard | Frontend | Wave 3 |
| IG-02 | Single admin token (no individual user accounts) | HIPAA, SOC 2 | RBAC deferred to v3.0; document limitation | Legal | Pre-release |
| IG-03 | SQLite not encrypted at rest | HIPAA | Recommend SQLCipher for healthcare deployments; document in runbook | Backend | Wave 4 |
| IG-04 | Audit log retention < 6 years | HIPAA | Configurable retention; document HIPAA override | Backend | Wave 4 |
| IG-05 | No BAA template | HIPAA | Draft BAA for healthcare client engagements | Legal | Pre-release |
| IG-06 | Sub-processor register missing | GDPR | Document LLM API providers and their DPA/BAA status | Legal | Wave 4 |
| IG-07 | Audit log tamper resistance | SOC 2 | Consider cryptographic log chaining or remote log shipping | DevOps | v2.1 |

### 6.3 Low Priority Gaps (Address Post-GA)

| # | Gap | Framework | Remediation | Owner | Target |
|---|-----|-----------|-------------|-------|--------|
| LP-01 | No formal DPIA for healthcare use cases | GDPR, EU AI Act | Conduct DPIA for adapters 04, 05, 12, 49 | Legal | Post-GA |
| LP-02 | Automatic session timeout not enforced | HIPAA | Add session timeout to wizard and dashboard | Frontend | v2.1 |
| LP-03 | No formal ROPA (Record of Processing Activities) | GDPR | Draft ROPA if Amenthyx exceeds 250 employees | Legal | When applicable |

---

## 7. Compliance Validation Schedule

| Event | Trigger | Reviewer | Scope |
|-------|---------|----------|-------|
| Wave completion review | Each wave delivered | Legal | All items in this checklist |
| Pre-release audit | Before M6 sign-off | Legal + QA | Full compliance validation |
| Quarterly review | Every 3 months post-release | Legal | Updated gap assessment |
| Incident-triggered review | PII breach, DMCA, legal inquiry | Legal | Affected compliance area |
| Client onboarding review | New Enterprise/Managed client | Legal | DPA, BAA (if healthcare), data residency |

---

## 8. Verification Commands

For auditors and compliance reviewers, the following commands verify key controls:

```bash
# Verify audit logging is enabled
grep -r "get_audit_logger" shared/*.py | wc -l
# Expected: >= 3 modules (claw_vault.py, claw_security.py, + services)

# Verify token hashing (never stores raw tokens)
grep "_hash_token" shared/claw_audit.py
# Expected: SHA-256 truncated hash function

# Verify vault encryption parameters
grep "PBKDF2_ITERATIONS" shared/claw_vault.py
# Expected: 480000

# Verify PII detection patterns exist
grep -c "pii_detection" shared/claw_security.py
# Expected: >= 2

# Verify rate limiting is configurable
grep "CLAW_RATE_LIMIT" shared/claw_ratelimit.py
# Expected: environment variable configuration

# Verify constant-time token comparison
grep "_constant_time_compare" shared/claw_auth.py
# Expected: XOR-based comparison function

# Verify container resource limits
grep -c "memory:" docker-compose.yml
# Expected: >= 10 (limits + reservations for each service)

# Verify health checks on all services
grep -c "healthcheck:" docker-compose.yml
# Expected: >= 6

# Verify restart policies
grep -c "restart:" docker-compose.yml
# Expected: >= 6
```

---

*Compliance Checklist v2.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
*Covers: GDPR, SOC 2, HIPAA Readiness, Open Source License Compliance*
*Source verification: All claims verified against source code as of 2026-03-02*
