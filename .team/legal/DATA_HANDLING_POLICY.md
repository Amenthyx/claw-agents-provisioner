# Data Handling Policy -- Claw Agents Provisioner v2.0

> Version: 1.0
> Date: 2026-03-02
> Author: Legal/Compliance Attorney (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: ACTIVE
> Classification: INTERNAL -- Share with enterprise clients upon request
> Review Cycle: Quarterly + on incident

---

## 1. Purpose and Scope

This policy defines how the Claw Agents Provisioner handles client Personally Identifiable Information (PII) and sensitive data throughout the entire lifecycle: collection, processing, storage, transmission, retention, and deletion.

**Scope**: This policy covers all data processed by:
- The assessment pipeline (`assessment/*.py`)
- The deployment pipeline (`claw.sh deploy`)
- All 6 HTTP services (router, memory, RAG, wizard, dashboard, orchestrator)
- The fine-tuning pipeline (`finetune/*.py`)
- The encrypted vault (`claw_vault.py`)
- Audit and monitoring systems (`claw_audit.py`, `claw_metrics.py`, `claw_health.py`)

**Audience**: Amenthyx consultants, enterprise IT teams, compliance auditors, and data protection officers.

---

## 2. Data Classification

### 2.1 Classification Levels

| Level | Label | Definition | Examples | Handling |
|:-----:|-------|-----------|----------|----------|
| 4 | CRITICAL | Authentication credentials and encryption keys | API keys, vault password, CLAW_API_TOKEN, LLM provider keys | Never log; never commit; encrypt at rest; rotate regularly |
| 3 | HIGH | Direct PII identifying a natural person | Client name, email, phone number in assessment JSON | Never commit; delete after use; encrypt in transit; access restricted |
| 2 | MEDIUM | Indirect PII, business data, or sensitive operational data | Company name, budget, adapter weights, conversation logs, audit trails | Gitignored; accessible to project team; delete per retention policy |
| 1 | LOW | Non-sensitive configuration and documentation | Agent configs, system prompts, example files, public documentation | Committed to repository; no special handling |
| 0 | PUBLIC | Open-source data freely redistributable | Training datasets, adapter configs, documentation | Published in repository under stated license |

### 2.2 Data Inventory

| # | Data Category | Classification | Location | In Git | Encryption |
|---|--------------|:-:|----------|:------:|:----------:|
| D1 | Client assessment JSONs | 3 (HIGH) | `client-assessment*.json` (project root) | NO | At rest: recommended (GPG/disk encryption) |
| D2 | Client `.env` files | 4 (CRITICAL) | `.env`, `.env.local` | NO | At rest: recommended; in vault: AES (Fernet) |
| D3 | Vault secrets | 4 (CRITICAL) | `secrets.vault` (binary) | NO | AES-128-CBC via Fernet, PBKDF2-HMAC-SHA256 key derivation |
| D4 | Conversation memory | 2 (MEDIUM) | SQLite DB (`data/shared/shared.db`, in-memory via claw_memory.py) | NO | At rest: NOT encrypted (plain SQLite) |
| D5 | Audit logs | 2 (MEDIUM) | `logs/audit.log` (+ 5 rotation files) | NO | At rest: NOT encrypted (plaintext JSON) |
| D6 | Training datasets | 0 (PUBLIC) | `finetune/datasets/*/data.jsonl` | YES | N/A (public data) |
| D7 | Adapter weights (client-trained) | 2 (MEDIUM) | `finetune/outputs/<client>/` | NO | At rest: NOT encrypted |
| D8 | Prometheus metrics | 1 (LOW) | In-memory (claw_metrics.py), scraped by Prometheus | NO | N/A (operational data) |
| D9 | Container runtime data | 2 (MEDIUM) | Docker volumes (named volumes per service) | NO | At rest: depends on Docker storage driver |
| D10 | Port map and instance data | 1 (LOW) | `data/port_map.json`, `data/instance.db` | NO | N/A |

---

## 3. PII Data Flow

### 3.1 Assessment Pipeline Flow

```
CLIENT INTAKE                PROCESSING                    DEPLOYMENT                  RUNTIME
==============              ============                  ============               ==========

Consultant fills     -->    validate.py reads JSON   -->  generate_env.py creates   -->  Agent container
assessment form             (schema validation)           .env with derived values       receives only
                                                                                         environment
client-assessment.json      resolve.py matches to         generate_config.py creates     variables
(Contains: name,            deployment profile            agent-specific config          (no raw PII)
 email, phone,              (no PII forwarded)
 company, budget,                                         claw.sh deploy provisions
 use case, channels)                                      container from config

     |                           |                              |                         |
     v                           v                              v                         v
  [HIGH PII]              [No PII emitted]              [CRITICAL secrets             [MEDIUM data]
  Local filesystem         Processing is                 injected via env]             Conversation
  only                     transformation                                              logs may contain
                           only                                                        user messages
```

**Key principle**: PII enters at the assessment stage and is TRANSFORMED into non-PII configuration values during processing. The raw assessment JSON is not copied into containers or transmitted to external services.

### 3.2 Conversation Memory Flow

```
USER MESSAGE --> Agent (container) --> claw_router.py --> LLM API (external)
                                            |
                                            v
                                     claw_memory.py
                                     (SQLite storage)
                                            |
                                            v
                                     Conversation DB
                                     (data/shared/shared.db)
```

**PII risk**: User messages sent to the agent may contain PII. This PII flows through:
1. The agent container (ephemeral)
2. The router (in-memory only, not persisted)
3. The LLM API provider (transmitted to external service)
4. The conversation memory (persisted in SQLite)

**Controls**:
- `claw_security.py` PII detection (8 regex patterns) scans content for: email, phone (US/intl), SSN, credit card, IPv4, passport, IBAN
- `claw_security.py` secret masking (16+ patterns) redacts API keys, tokens, passwords from logs
- `claw_audit.py` hashes tokens before logging (SHA-256 truncated to 16 chars)
- Conversation memory has configurable retention (`--prune --days N`)

### 3.3 Audit Trail Flow

```
ANY HTTP REQUEST --> claw_auth.py (validates token)
                          |
                          v
                    claw_audit.py
                    (structured JSON)
                          |
                          v
                    logs/audit.log
                    (RotatingFileHandler)
                    10MB per file, 5 backups
```

**Data in audit logs**:
- Timestamp (ISO 8601 UTC)
- Event type (request, auth, config_change, data_access, security)
- User (token hash -- NEVER raw token)
- Action (endpoint/operation)
- Resource (target)
- Outcome (success/failure)
- IP address
- Details (context-specific metadata)

**What is NOT in audit logs**:
- Raw API tokens or passwords
- Request/response bodies
- PII from user messages
- Secret values from the vault

---

## 4. Retention Policies

### 4.1 Retention Schedule

| Data Category | Retention Period | Basis | Deletion Method | Automated |
|--------------|-----------------|-------|-----------------|:---------:|
| Client assessment JSONs | 30 days after deployment confirmed | Business necessity + GDPR minimization | `rm` or `claw.sh cleanup --client` | PENDING |
| Client `.env` files | 30 days after deployment confirmed | Business necessity | `rm` or `claw.sh cleanup --client` | PENDING |
| Vault secrets | Active use only; rotated on schedule | Security best practice | `claw_vault.py delete <key>` | Manual |
| Conversation memory | 30 days (configurable via claw_security.py) | GDPR data minimization | `claw_memory.py --prune --days 30` | PENDING |
| Audit logs | 365 days (configurable) | SOC 2 requirement; HIPAA may require 6 years | Log rotation (auto); archive for long-term | PARTIAL |
| PII detected in content | 7 days (per claw_security.py policy) | GDPR data minimization | Automated redaction at detection time | YES |
| Adapter weights (client) | 90 days after delivery | Business necessity (re-training) | `rm -rf finetune/outputs/<client>/` | PENDING |
| Training logs | 90 days | Debugging and QA | `rm -rf finetune/runs/<run>/` | Manual |
| Docker containers/volumes | 7 days after deployment confirmed | Resource management | `docker compose down -v` | Manual |
| Vagrant VMs | 7 days after deployment confirmed | Resource management | `vagrant destroy` | Manual |

### 4.2 Retention Overrides

| Override | Trigger | New Retention | Authority |
|----------|---------|--------------|-----------|
| Legal hold | Active litigation or legal dispute | Indefinite (until hold lifted) | Legal counsel |
| HIPAA override | Healthcare client engagement | Audit logs: 6 years; PHI-related data: per HIPAA | Compliance officer |
| Client request (extend) | Written agreement from client | Per agreement terms | Account manager + Legal |
| Client request (delete) | GDPR Art. 17 right to erasure | Immediate (within 30 days) | Data protection officer |
| Regulatory investigation | Supervisory authority request | Per regulatory requirement | Legal counsel |

### 4.3 Retention Enforcement

**Current state**: Retention policies are defined in `claw_security.py` (data_retention section, lines 332-338) but enforcement is partially automated:

| Control | Automated | Gap |
|---------|:---------:|-----|
| PII redaction at detection time | YES | `claw_security.py` pii_detection with action "redact_and_warn" |
| Secret masking in logs/responses | YES | `claw_security.py` secret_masking replaces with "***REDACTED***" |
| Conversation memory pruning | PARTIAL | `claw_memory.py --prune` exists but is not scheduled |
| Audit log rotation | YES | `RotatingFileHandler` (10MB x 5 files) |
| Assessment file deletion | NO | `claw.sh cleanup --client` not yet implemented |
| Container/VM cleanup | NO | Manual process |

---

## 5. Deletion Procedures

### 5.1 Standard Client Data Deletion

When a client engagement closes, the following deletion procedure applies:

```
STEP 1: Verify deployment is stable and client has confirmed acceptance
STEP 2: Execute deletion commands (see below)
STEP 3: Document deletion in engagement log
STEP 4: Confirm deletion to client (if requested under GDPR Art. 17)
```

**Deletion commands**:

```bash
# Step 1: Delete assessment files
rm -f client-assessment*.json
rm -f assessment/clients/*.json   # if client subfolder was created

# Step 2: Delete environment files
rm -f .env .env.local .env.*.local

# Step 3: Destroy Docker containers and volumes
docker compose -p <client-name> --profile <agent> down -v

# Step 4: Destroy Vagrant VMs (if used)
cd <agent>/ && vagrant destroy -f

# Step 5: Delete client-specific adapter weights
rm -rf finetune/outputs/<client-name>/

# Step 6: Delete training run logs
rm -rf finetune/runs/<client-run-id>/

# Step 7: Prune conversation memory
python3 shared/claw_memory.py --prune --days 0
# Or delete specific conversations:
# curl -X DELETE http://localhost:9096/api/memory/conversations/<id>

# Step 8: Delete client-specific vault secrets (if any)
python3 shared/claw_vault.py delete <CLIENT_API_KEY>

# Step 9: Verify deletion
ls client-assessment*.json 2>/dev/null && echo "WARNING: Assessment files remain" || echo "OK: Assessments deleted"
docker ps -a --filter "name=<client-name>" --format "{{.Names}}" | head -5
```

### 5.2 GDPR Right to Erasure (Art. 17) Procedure

When a data subject exercises their right to erasure:

| Step | Action | Timeline | Owner |
|------|--------|----------|-------|
| 1 | Acknowledge receipt of erasure request | Within 48 hours | Account manager |
| 2 | Identify all data stores containing the subject's data | Within 7 days | Technical lead |
| 3 | Execute standard deletion (Section 5.1) | Within 14 days | Consultant |
| 4 | Verify audit logs contain only hashed identifiers (not raw PII) | Within 14 days | Compliance |
| 5 | Confirm deletion to data subject | Within 30 days (GDPR deadline) | Account manager |
| 6 | Document the erasure in compliance records | Within 30 days | Legal |

**Exemptions** (data that may be retained despite erasure request):
- Audit log entries with hashed tokens (pseudonymous, not identifiable without the original token)
- Data required for legal compliance or defense of legal claims
- Aggregated/anonymized statistics derived from the data

### 5.3 Data Breach Deletion

If client data is accidentally committed to a public repository:

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Force-push to remove the commit from the branch | Within 1 hour |
| 2 | Run BFG Repo-Cleaner to purge from all git history | Within 1 hour |
| 3 | Contact GitHub Support to clear caches | Within 4 hours |
| 4 | Rotate any exposed API keys | Within 1 hour |
| 5 | Assess exposure (clone/fork counts, GitHub traffic analytics) | Within 24 hours |
| 6 | Notify affected client(s) per GDPR Art. 33 | Within 72 hours |
| 7 | Notify supervisory authority if high risk to individuals | Within 72 hours |

---

## 6. Encryption Standards

### 6.1 Encryption at Rest

| Data Store | Encryption Method | Key Management | Standard |
|-----------|------------------|----------------|----------|
| Vault secrets | Fernet (AES-128-CBC) with PBKDF2-HMAC-SHA256 key derivation | Password-derived key; 480,000 PBKDF2 iterations; 16-byte random salt | NIST SP 800-132 compliant |
| Assessment JSONs | Recommended: GPG or filesystem-level encryption (LUKS, BitLocker, FileVault) | User-managed | Advisory; not enforced |
| SQLite databases | NOT ENCRYPTED (plain SQLite with WAL mode) | N/A | Gap: SQLCipher recommended for HIPAA deployments |
| Audit logs | NOT ENCRYPTED (plaintext JSON) | N/A | Gap: consider log encryption for regulated deployments |
| Docker volumes | Depends on Docker storage driver and host filesystem | Host-managed | Advisory: recommend encrypted filesystems |

### 6.2 Encryption in Transit

| Communication Path | Encryption | Protocol | Status |
|-------------------|-----------|----------|:------:|
| Client browser to wizard UI | TLS 1.3 (via nginx) | HTTPS | PENDING (Wave 2) |
| Client browser to dashboard | TLS 1.3 (via nginx) | HTTPS | PENDING (Wave 2) |
| Agent to LLM API provider | TLS 1.2+ | HTTPS | PASS (provider-enforced) |
| Inter-service communication | Plaintext HTTP (localhost) | HTTP | ACCEPTABLE (same-host; Docker network isolation) |
| Consultant to deployment host | SSH | SSH | PASS (standard practice) |
| Health check probes | Plaintext HTTP (localhost) | HTTP | ACCEPTABLE (internal probes) |

### 6.3 Encryption Specifications

**Vault Encryption (claw_vault.py)**:
- Algorithm: AES-128-CBC (via Fernet symmetric encryption)
- Key derivation: PBKDF2-HMAC-SHA256
- Iterations: 480,000
- Salt: 16 bytes (cryptographically random, per-vault)
- Key length: 32 bytes (base64url-encoded for Fernet)
- File format: `CLAWVAULT1` magic header (10 bytes) + salt (16 bytes) + Fernet token (remainder)
- Atomic writes: temp file + rename pattern (prevents corruption on crash)

**Token Hashing (claw_audit.py)**:
- Algorithm: SHA-256
- Output: Truncated to first 16 hex characters
- Purpose: Pseudonymous identification in audit logs
- Raw tokens are NEVER stored in logs

**Constant-Time Token Comparison (claw_auth.py)**:
- XOR-based byte comparison
- Length check does not short-circuit
- Prevents timing-based side-channel attacks

---

## 7. Access Controls

### 7.1 Current Access Model

| Access Level | Who | What They Can Access | Authentication |
|-------------|-----|---------------------|----------------|
| Admin | Amenthyx consultant with CLAW_API_TOKEN | All 6 HTTP services, vault, audit logs, config | Bearer token (single shared token) |
| Unauthenticated | Anyone on the network | Health check endpoint (port 9094) | None required |
| Container | Docker services on internal network | Inter-service APIs (localhost only) | None (trusted network) |

### 7.2 Access Control Gaps

| Gap | Impact | Mitigation | Timeline |
|-----|--------|------------|----------|
| Single shared admin token (no individual accounts) | Cannot attribute actions to specific users | RBAC deferred to v3.0; token hash in audit log provides limited traceability | v3.0 |
| No session timeout on wizard/dashboard | Unattended sessions remain active | Implement idle timeout (15 min for HIPAA) | v2.1 |
| Health endpoint unauthenticated | Service status visible without auth | Low risk: health data is not sensitive; useful for monitoring integration | Accepted risk |

---

## 8. Third-Party Data Sharing

### 8.1 LLM API Providers (Sub-Processors)

When the Claw router forwards prompts to LLM API providers, user message content is transmitted to external services:

| Provider | Jurisdiction | Data Transmitted | DPA Available | BAA Available |
|----------|-------------|-----------------|:-------------:|:-------------:|
| Anthropic (Claude) | USA | Prompt content, system prompts | YES (enterprise) | YES (enterprise) |
| OpenAI (GPT-4.1) | USA | Prompt content, system prompts | YES (enterprise) | YES (enterprise) |
| DeepSeek | China | Prompt content, system prompts | UNKNOWN | UNKNOWN |
| Google (Gemini) | USA | Prompt content, system prompts | YES | YES |
| Ollama (local) | N/A (local) | None transmitted externally | N/A | N/A |

**GDPR Implications**:
- Transmitting prompt content to US providers requires Standard Contractual Clauses (SCCs) or reliance on the EU-US Data Privacy Framework
- Transmitting to China (DeepSeek) requires additional safeguards under GDPR Art. 49
- Local LLM inference (Ollama) eliminates data transfer concerns entirely

**Recommendation for EU clients**: Use Ollama for local inference when prompts may contain PII. If cloud LLMs are required, prefer providers with executed DPAs (Anthropic, OpenAI) and inform clients of the data transfer.

### 8.2 No Other Third-Party Sharing

The Claw Agents Provisioner does NOT share data with any other third parties:
- No analytics services (no Google Analytics, no telemetry)
- No crash reporting services
- No advertising networks
- No data brokers
- Monitoring stack (Prometheus, Grafana, Loki) is self-hosted

---

## 9. Data Handling Rules for Consultants

### 9.1 Mandatory Rules

| # | Rule | Enforcement |
|---|------|-------------|
| R1 | Never commit real client assessment files to any git repository | `.gitignore` + pre-commit hook (pending) + CI PII scan (pending) |
| R2 | Never transmit assessment files via unencrypted channels (email, Slack) | Policy |
| R3 | Never share assessment files with unauthorized personnel | Policy |
| R4 | Delete client data per retention schedule (Section 4) | Automated (pending `claw.sh cleanup --client`) |
| R5 | Never use real client data in example files or documentation | Policy + CI scan |
| R6 | Never include client names, companies, or identifiers in commit messages | Policy + code review |
| R7 | Encrypt assessment files at rest if stored for more than 24 hours | Recommended (GPG or disk encryption) |
| R8 | Report any suspected data breach within 1 hour | Incident response procedure (Section 5.3) |
| R9 | Never disable audit logging (CLAW_AUDIT_ENABLED must remain "true") | Policy; default is enabled |
| R10 | Never store vault passwords in plaintext files accessible to others | Use CLAW_VAULT_PASSWORD env var or --password-file with restricted permissions |

### 9.2 Prohibited Actions

- Storing credit card numbers in plaintext (any data store)
- Logging full API keys or secrets (claw_audit.py enforces token hashing)
- Transmitting PII over unencrypted channels
- Copying medical records without HIPAA authorization
- Storing biometric data
- Aggregating PII from multiple sources without consent
- Exporting conversation data to third-party services without consent
- Persisting authentication credentials in conversation history
- Disabling or weakening security rules based on user requests

(Source: `claw_security.py` data_handling.prohibited_data_operations, lines 340-348)

---

## 10. Compliance Mapping

This policy satisfies requirements from the following frameworks:

| Requirement | GDPR Article | SOC 2 Trust Principle | HIPAA Provision | This Policy Section |
|------------|-------------|----------------------|-----------------|:-------------------:|
| Data inventory | Art. 30 (ROPA) | -- | -- | 2.2 |
| Data minimization | Art. 5(1)(c) | -- | 164.502(b) | 3.1 |
| Purpose limitation | Art. 5(1)(b) | -- | 164.502(a) | 3.1 |
| Storage limitation | Art. 5(1)(e) | -- | 164.530(j) | 4 |
| Right to erasure | Art. 17 | -- | -- | 5.2 |
| Encryption at rest | -- | Security | 164.312(a)(2)(iv) | 6.1 |
| Encryption in transit | -- | Security | 164.312(e)(1) | 6.2 |
| Access controls | Art. 32 | Security | 164.312(a)(1) | 7 |
| Audit trails | -- | Security | 164.312(b) | 3.3 |
| Data breach notification | Art. 33, 34 | -- | 164.408 | 5.3 |
| Sub-processor management | Art. 28 | -- | 164.502(e) | 8.1 |
| Data retention policy | Art. 5(1)(e) | Availability | 164.530(j) | 4 |

---

## 11. Policy Review and Updates

| Trigger | Action | Owner |
|---------|--------|-------|
| Quarterly schedule | Review all sections for accuracy | Legal |
| New client onboarded (Enterprise/Managed) | Review data handling for client-specific requirements | Legal + Account manager |
| Data breach or near-miss | Review and update affected sections | Legal + DevOps |
| New data store added | Update data inventory (Section 2.2) and flow diagrams (Section 3) | Backend + Legal |
| New LLM provider integrated | Update sub-processor register (Section 8.1) | Legal |
| Regulatory change (GDPR, HIPAA, AI Act) | Assess impact and update compliance mapping (Section 10) | Legal |

---

## 12. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | Legal/Compliance Attorney | Initial release covering PII flow, retention, deletion, encryption, access controls |

---

*Data Handling Policy v1.0 -- Claw Agents Provisioner v2.0 -- Amenthyx AI Teams v3.0*
*Verified against source code: claw_audit.py, claw_auth.py, claw_vault.py, claw_security.py, claw_memory.py, claw_ratelimit.py, claw_metrics.py, claw_health.py, docker-compose.yml*
