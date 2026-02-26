# Data Privacy Assessment — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: LEGAL (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: ACTIVE
> Classification: INTERNAL

---

## 1. Purpose

This document assesses personal data and sensitive information risks across the Claw Agents Provisioner project. It identifies data categories, classifies their sensitivity, evaluates current safeguards, and recommends procedural and technical controls to protect privacy.

---

## 2. Data Inventory

### 2.1 Complete Data Map

| # | Data Category | Location(s) | Contains PII | Sensitivity | Tracked in Git | Retention |
|---|--------------|-------------|:-:|:-:|:-:|-----------|
| D1 | Client assessment JSONs | `client-assessment*.json` (root) | YES | HIGH | NO (gitignored) | Until deployment complete |
| D2 | Example assessment JSONs | `client-assessment.example.json`, `assessment/examples/*.json` | NO (fake data) | LOW | YES | Permanent |
| D3 | API keys and secrets | `.env`, `.env.local` | NO (secrets, not PII) | CRITICAL | NO (gitignored) | Active use only |
| D4 | Environment template | `.env.template` | NO | LOW | YES | Permanent |
| D5 | Training datasets | `finetune/datasets/*/data.jsonl` | POSSIBLY | VARIES | YES | Permanent |
| D6 | Dataset metadata | `finetune/datasets/*/metadata.json` | NO | LOW | YES | Permanent |
| D7 | Adapter configs | `finetune/adapters/*/adapter_config.json` | NO | LOW | YES | Permanent |
| D8 | System prompts | `finetune/adapters/*/system_prompt.txt` | NO | LOW | YES | Permanent |
| D9 | Trained adapter weights | `finetune/outputs/` | NO | MEDIUM | NO (gitignored) | Per client engagement |
| D10 | Training logs | `finetune/runs/` | NO | LOW | NO (gitignored) | Per training run |
| D11 | Vagrant VM disk images | `.vagrant/` | POSSIBLY (if assessment data loaded) | MEDIUM | NO (gitignored) | Per VM lifecycle |
| D12 | Docker volumes | Docker host filesystem | POSSIBLY (if assessment data loaded) | MEDIUM | N/A | Per container lifecycle |
| D13 | Agent runtime logs | Inside VMs/containers | POSSIBLY (user messages) | MEDIUM | N/A | Per agent lifecycle |

---

## 3. PII Risk Analysis — Client Assessment Files

### 3.1 PII Fields in Assessment JSON

Based on the project charter and `claw-client-assessment` schema, assessment JSONs contain:

| Field Path | Data Type | PII Category | GDPR Category | Risk if Exposed |
|-----------|-----------|:-:|:-:|:-:|
| `client.name` | Personal name | Direct PII | Art. 4(1) personal data | HIGH |
| `client.company` | Company name | Indirect PII (if sole proprietor) | Potentially personal data | MEDIUM |
| `client.email` | Email address | Direct PII | Art. 4(1) personal data | HIGH |
| `client.phone` | Phone number | Direct PII | Art. 4(1) personal data | HIGH |
| `client.industry` | Industry sector | Non-PII | Not personal data | LOW |
| `client.country` | Country | Indirect PII | Not personal data alone | LOW |
| `client.budget` | Financial information | Indirect PII (business) | Potentially personal data (sole proprietor) | MEDIUM |
| `needs.use_cases[]` | Business requirements | Non-PII | Not personal data | LOW |
| `needs.channels[]` | Communication channels | Non-PII | Not personal data | LOW |
| `needs.model_preference` | Technical preference | Non-PII | Not personal data | LOW |
| `needs.skills[]` | Desired agent skills | Non-PII | Not personal data | LOW |
| `deployment.api_keys.*` | API credentials | Secrets (not PII) | Not personal data | CRITICAL (security) |

### 3.2 Risk Scenarios

| # | Scenario | Probability | Impact | Risk Score | Current Mitigation |
|---|----------|:-:|:-:|:-:|-------------------|
| RS1 | Consultant runs `git add .` and commits real assessment JSON | H | H | RED | `.gitignore` excludes pattern |
| RS2 | Consultant copies real data into `client-assessment.example.json` | M | H | RED | Filename exemption in `.gitignore` |
| RS3 | Assessment data persists on consultant's machine after engagement | H | M | YELLOW | No deletion procedure exists |
| RS4 | Assessment data transmitted over insecure channel (email, Slack) | M | H | RED | No transmission policy exists |
| RS5 | Assessment data visible in terminal history / shell logs | M | L | GREEN | Ephemeral; low likelihood of extraction |
| RS6 | Vagrant VM snapshot contains assessment data | L | M | GREEN | `.vagrant/` is gitignored |
| RS7 | Docker image layer contains assessment data | L | H | YELLOW | Assessment data injected at runtime, not build time |
| RS8 | Trained adapter weights encode client-specific PII | L | M | GREEN | LoRA weights are statistical; PII extraction is impractical |

---

## 4. Data Sensitivity Classification

### 4.1 Classification Scheme

| Level | Label | Definition | Handling Requirements |
|-------|-------|------------|----------------------|
| 4 | CRITICAL | API keys, secrets, credentials | Never commit; encrypt at rest; rotate regularly; restrict access to deployment operator |
| 3 | HIGH | Direct PII (names, emails, phone numbers) | Never commit; delete after use; encrypt in transit; access restricted to engagement team |
| 2 | MEDIUM | Indirect PII, business data, adapter weights | Gitignored; accessible to project team; delete on engagement close |
| 1 | LOW | Public data, example files, configs, code | Committed to public repo; no special handling |
| 0 | PUBLIC | Open-source datasets, documentation | Publicly redistributable |

### 4.2 Data Category Classification

| Data Category (from Section 2) | Classification Level | Label |
|-------------------------------|:-:|-------|
| D1 — Client assessment JSONs | 3 | HIGH |
| D2 — Example assessment JSONs | 1 | LOW |
| D3 — API keys and secrets | 4 | CRITICAL |
| D4 — Environment template | 1 | LOW |
| D5 — Training datasets | 0-2 | PUBLIC to MEDIUM (per dataset) |
| D6 — Dataset metadata | 0 | PUBLIC |
| D7 — Adapter configs | 1 | LOW |
| D8 — System prompts | 1 | LOW |
| D9 — Trained adapter weights | 2 | MEDIUM |
| D10 — Training logs | 1 | LOW |
| D11 — Vagrant VM disk images | 2 | MEDIUM |
| D12 — Docker volumes | 2 | MEDIUM |
| D13 — Agent runtime logs | 2 | MEDIUM |

### 4.3 High-Sensitivity Training Datasets

Certain datasets within the committed `finetune/datasets/` folder may contain residual PII or sensitive information even if openly licensed:

| Dataset # | Use Case | Sensitivity | Specific Concern |
|-----------|----------|:-:|-----------------|
| 04 | Healthcare Triage | 2 (MEDIUM) | Possible residual PHI if de-identification is incomplete |
| 08 | Email Management (Enron) | 2 (MEDIUM) | Real names, email addresses, phone numbers in corpus |
| 12 | HR & Recruitment | 2 (MEDIUM) | Possible real candidate names, qualifications |
| 22 | Insurance Claims | 2 (MEDIUM) | Possible policy numbers, medical info, personal details |
| 49 | Mental Health & Counseling | 2 (MEDIUM) | Sensitive health conversations; re-identification risk |

---

## 5. Gitignore Verification

### 5.1 Current `.gitignore` Analysis

| Pattern | Purpose | Effective | Coverage |
|---------|---------|:-:|---------|
| `.env` | API keys | YES | Covers `.env` exactly |
| `.env.local` | Local overrides | YES | Covers local env files |
| `.env.*.local` | Environment-specific local files | YES | Covers patterns like `.env.production.local` |
| `client-assessment*.json` | Client PII | YES | Covers all assessment files |
| `!client-assessment.example.json` | Example file exception | YES | Allows tracking the example |
| `finetune/runs/` | Training logs | YES | Prevents large log commits |
| `finetune/outputs/` | Trained weights | YES | Prevents large weight file commits |
| `*.safetensors` / `*.bin` / `*.pt` / `*.pth` | Model weight files | YES | Belt-and-suspenders for weights |
| `!finetune/datasets/**` | Dataset tracking exception | YES | Ensures datasets ARE committed |
| `!finetune/adapters/**` | Adapter config tracking exception | YES | Ensures adapter configs ARE committed |
| `.vagrant/` | Vagrant state | YES | Covers VM disk images |

### 5.2 Gitignore Gaps

| # | Gap | Risk | Recommendation |
|---|-----|:-:|----------------|
| G1 | No pattern for `assessment/*.json` (only root `client-assessment*.json`) | MEDIUM | If consultants place real assessment files in the `assessment/` directory, they could be committed. Add `assessment/clients/` pattern if a client data subfolder is ever created. |
| G2 | No pattern for backup files (`*.bak`, `*~`, `*.orig`) | LOW | These could contain copies of sensitive files. Add `*.bak`, `*~`, `*.orig` patterns. |
| G3 | No pattern for `*.json.bak` or `*.json.backup` | MEDIUM | Backup copies of assessment files could bypass the gitignore. Add these patterns. |
| G4 | Docker volumes not addressed | LOW | Docker volumes live outside the repo. No gitignore action needed, but document the cleanup procedure. |
| G5 | No `.env.example` exception | LOW | If `.env.template` is renamed to `.env.example`, it would be gitignored by the `.env*` patterns. Currently not an issue since the file is named `.env.template`. |

### 5.3 Recommended `.gitignore` Additions

```gitignore
# Backup files (may contain copies of sensitive data)
*.bak
*~
*.orig
*.backup

# Additional assessment file patterns
assessment/clients/
*-assessment*.json
!*-assessment.example*.json

# Shell history (may contain secrets)
.bash_history
.zsh_history
```

---

## 6. Client Data Handling Procedures

### 6.1 Data Lifecycle

```
COLLECT --> PROCESS --> DEPLOY --> RETAIN (limited) --> DELETE
```

#### Phase 1: COLLECT
- Consultant fills in `client-assessment.json` during client onboarding session.
- Data is entered on the consultant's local machine.
- **Control**: Assessment form should include a privacy notice informing the client what data is collected and why.

#### Phase 2: PROCESS
- `claw.sh deploy --assessment client-assessment.json` reads the JSON.
- `assessment/resolve.py` extracts needs and maps to platform/model/skills.
- `assessment/generate_env.py` generates `.env` with API keys and config values.
- `assessment/generate_config.py` generates agent-specific configuration files.
- **Control**: Processing occurs entirely on the local machine. No data transmitted to external services (assessment pipeline works offline per project charter).

#### Phase 3: DEPLOY
- Agent is provisioned in Docker container or Vagrant VM.
- Assessment data is transformed into environment variables and configuration values.
- Original assessment JSON is no longer needed after deployment.
- **Control**: Assessment data should not be copied into the VM/container. Only derived configuration values should be injected.

#### Phase 4: RETAIN (Limited)
- Consultant may retain the assessment JSON for reference during the engagement.
- **Control**: Define maximum retention period (see Section 7).

#### Phase 5: DELETE
- After engagement closes, consultant must delete:
  - `client-assessment*.json` files
  - `.env` files containing client API keys
  - Any Vagrant VMs or Docker containers containing client configuration
  - Local adapter weights trained on client-specific data
- **Control**: Provide a `claw.sh cleanup --client` command that automates deletion.

### 6.2 Data Handling Rules

| Rule | Description | Enforcement |
|------|-------------|-------------|
| R1 | Never commit real client assessment files to any git repository | `.gitignore` + pre-commit hook + CI scan |
| R2 | Never transmit assessment files via unencrypted channels | Policy (documented in onboarding guide) |
| R3 | Never share assessment files with unauthorized personnel | Policy (access restricted to engagement team) |
| R4 | Delete client data after engagement closes | Automated via `claw.sh cleanup` + policy |
| R5 | Do not use real client data in example files | Policy + CI scan for PII patterns |
| R6 | Encrypt assessment files at rest if stored for more than 24 hours | Recommended — use GPG or system-level encryption |
| R7 | Never include client names or companies in commit messages | Policy + code review |

---

## 7. Data Retention Policy

### 7.1 Retention Periods

| Data Category | Retention Period | Justification | Deletion Method |
|---------------|-----------------|---------------|-----------------|
| Client assessment JSONs | 30 days after deployment confirmed | Needed for troubleshooting during initial setup | `rm` or `claw.sh cleanup --client` |
| Client `.env` files | 30 days after deployment confirmed | Needed for reconfiguration during initial setup | `rm` or `claw.sh cleanup --client` |
| Client-specific adapter weights | 90 days after delivery OR engagement end | Client may request re-training; weights are large but not PII | `rm -rf finetune/outputs/<client>/` |
| Vagrant VMs with client config | 7 days after deployment confirmed | VMs consume significant disk space | `vagrant destroy` or `claw.sh <agent> destroy` |
| Docker containers with client config | 7 days after deployment confirmed | Containers consume resources | `docker compose down -v` |
| Training logs | 90 days | Debugging and quality assurance | `rm -rf finetune/runs/<run>/` |
| Agent runtime logs (inside containers) | Destroyed with container | Ephemeral by design | Container removal |

### 7.2 Retention Exceptions

- **Legal hold**: If a client engagement is subject to legal dispute, all related data must be preserved until the hold is lifted.
- **Regulatory requirement**: If a client is in a regulated industry (healthcare, finance), retention may need to be extended per industry regulations.
- **Client request**: Clients may request earlier deletion (right to erasure under GDPR Art. 17) or extended retention (by written agreement).

### 7.3 Automated Cleanup Command

**Recommendation**: Implement `claw.sh cleanup --client` with the following behavior:

```bash
claw.sh cleanup --client
# 1. Deletes all client-assessment*.json files (except .example.json)
# 2. Deletes .env and .env.local files
# 3. Destroys all Vagrant VMs (vagrant destroy -f in each agent dir)
# 4. Removes all Docker containers and volumes (docker compose down -v)
# 5. Deletes finetune/outputs/ contents
# 6. Deletes finetune/runs/ contents
# 7. Prints confirmation of what was deleted
```

---

## 8. Training Dataset Privacy Assessment

### 8.1 PII Scan Requirements for Committed Datasets

Before any dataset is committed to the repository, it must pass a PII scan. The `validate_datasets.py` script should include:

| Check | Method | Action on Failure |
|-------|--------|-------------------|
| Email addresses | Regex: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | Flag and report; require manual review |
| Phone numbers | Regex: common phone patterns (US, EU, international) | Flag and report; require manual review |
| Social Security Numbers | Regex: `\d{3}-\d{2}-\d{4}` and variants | BLOCK commit; require redaction |
| Credit card numbers | Regex: Luhn-validated 13-19 digit sequences | BLOCK commit; require redaction |
| IP addresses | Regex: IPv4 and IPv6 patterns | Flag if in personal data context |
| Names (heuristic) | NER model or dictionary lookup | Flag for datasets marked `sensitivity: high` |
| Medical record numbers | Regex: common MRN patterns | BLOCK commit for healthcare datasets |
| Dates of birth | Regex: date patterns in personal data context | Flag for healthcare/insurance datasets |

### 8.2 Per-Dataset Privacy Classification

| Dataset # | Use Case | PII Risk | Scan Priority | Notes |
|-----------|----------|:-:|:-:|-------|
| 01 | Customer Support | LOW | Standard | Typically synthetic or anonymized |
| 02 | Real Estate | LOW | Standard | Property data, not personal |
| 03 | E-Commerce | LOW | Standard | Product/order data |
| 04 | Healthcare Triage | HIGH | Priority | Must verify HIPAA de-identification |
| 05 | Legal Document Review | MEDIUM | Priority | Court docs may contain party names |
| 06 | Personal Finance | MEDIUM | Priority | Verify no real account data |
| 07 | Code Review | LOW | Standard | Code snippets, not personal |
| 08 | Email (Enron) | HIGH | Priority | Known to contain real PII |
| 09 | Calendar & Scheduling | LOW | Standard | Synthetic data |
| 10 | Meeting Summarization | LOW | Standard | Research corpus, anonymized |
| 11 | Sales & CRM | MEDIUM | Standard | Verify no real customer data |
| 12 | HR & Recruitment | HIGH | Priority | May contain candidate PII |
| 13 | IT Helpdesk | LOW | Standard | Technical tickets |
| 14 | Content Writing | LOW | Standard | Creative content |
| 15 | Social Media | LOW | Standard | Public posts |
| 16 | Translation | LOW | Standard | Parallel text corpora |
| 17 | Education & Tutoring | LOW | Standard | Academic content |
| 18 | Research & Summarization | LOW | Standard | Academic papers |
| 19 | Data Analysis | LOW | Standard | SQL/query data |
| 20 | Project Management | LOW | Standard | Synthetic |
| 21 | Accounting | MEDIUM | Standard | Verify no real financial records |
| 22 | Insurance Claims | HIGH | Priority | Claims contain PII by nature |
| 23 | Travel & Hospitality | LOW | Standard | Review/booking data |
| 24 | Food & Restaurant | LOW | Standard | Menu/review data |
| 25 | Fitness & Wellness | LOW | Standard | Exercise data |
| 26 | Automotive | LOW | Standard | Vehicle specs |
| 27 | Supply Chain | LOW | Standard | Logistics data |
| 28 | Manufacturing | LOW | Standard | QA metrics |
| 29 | Agriculture | LOW | Standard | Crop/weather data |
| 30 | Energy & Utilities | LOW | Standard | Consumption data |
| 31 | Telecommunications | LOW | Standard | Network data |
| 32 | Government & Public Services | LOW | Standard | Public records |
| 33 | Nonprofit | LOW | Standard | Synthetic |
| 34 | Event Planning | LOW | Standard | Synthetic |
| 35 | Cybersecurity | LOW | Standard | CVE/vulnerability data |
| 36 | DevOps | LOW | Standard | Technical Q&A |
| 37 | API Integration | LOW | Standard | Synthetic |
| 38 | Database Admin | LOW | Standard | Technical Q&A |
| 39 | IoT & Smart Home | LOW | Standard | Sensor data |
| 40 | Chatbot | LOW | Standard | Conversational data |
| 41 | Document Processing | LOW | Standard | Document images/text |
| 42 | Knowledge Base & FAQ | LOW | Standard | FAQ pairs |
| 43 | Compliance & Regulatory | LOW | Standard | Regulatory text |
| 44 | Onboarding & Training | LOW | Standard | Synthetic |
| 45 | Sentiment Analysis | LOW | Standard | Product reviews |
| 46 | Creative Writing | LOW | Standard | Fiction/stories |
| 47 | Music & Entertainment | LOW | Standard | Metadata |
| 48 | Gaming | LOW | Standard | Game data |
| 49 | Mental Health | HIGH | Priority | Sensitive health conversations |
| 50 | Personal Finance | MEDIUM | Priority | Verify no real financial data |

**Summary**: 5 HIGH priority datasets, 5 MEDIUM priority datasets, 40 LOW/Standard datasets.

---

## 9. Incident Response — Data Breach Procedure

### 9.1 If Client PII is Accidentally Committed to Public Repo

| Step | Action | Timeline | Owner |
|------|--------|----------|-------|
| 1 | Immediately force-push to remove the commit from the branch | Within 1 hour | DEVOPS/INFRA |
| 2 | Use BFG Repo-Cleaner to purge the file from all git history | Within 1 hour | DEVOPS/INFRA |
| 3 | Invalidate any GitHub caches (contact GitHub Support if needed) | Within 4 hours | INFRA |
| 4 | Assess whether the data was accessed (check clone/fork counts, GitHub traffic) | Within 24 hours | LEGAL/PM |
| 5 | Notify affected client(s) with details of exposure and remediation | Within 72 hours (GDPR Art. 33) | LEGAL/PM |
| 6 | If high risk to individual rights, notify supervisory authority | Within 72 hours (GDPR Art. 33) | LEGAL |
| 7 | Document the incident in the risk register | Within 7 days | PM |
| 8 | Implement additional preventive controls | Within 14 days | INFRA |

### 9.2 If API Keys are Accidentally Committed

| Step | Action | Timeline | Owner |
|------|--------|----------|-------|
| 1 | Immediately rotate all exposed API keys | Within 1 hour | Consultant + Client |
| 2 | Force-push and BFG Repo-Cleaner to remove from history | Within 1 hour | DEVOPS/INFRA |
| 3 | Verify no unauthorized API usage occurred | Within 24 hours | Consultant |
| 4 | Document the incident | Within 7 days | PM |

---

## 10. Recommendations Summary

| # | Recommendation | Priority | Effort | Impact |
|---|---------------|:-:|:-:|:-:|
| 1 | Implement `claw.sh cleanup --client` automated deletion command | P0 | Medium | HIGH |
| 2 | Add pre-commit hook rejecting `client-assessment*.json` (except `.example.`) | P0 | Low | HIGH |
| 3 | Add CI PII pattern scanner for all tracked files | P0 | Medium | HIGH |
| 4 | Update `.gitignore` with gaps identified in Section 5.3 | P0 | Low | MEDIUM |
| 5 | Add PII scan to `validate_datasets.py` for HIGH-priority datasets | P1 | Medium | HIGH |
| 6 | Draft privacy notice template for client assessment intake | P1 | Low | MEDIUM |
| 7 | Draft DPA template for Enterprise and Managed service packages | P1 | Medium | HIGH |
| 8 | Define and document data retention policy (Section 7) in README | P1 | Low | MEDIUM |
| 9 | Implement encryption-at-rest recommendation for assessment files | P2 | Medium | MEDIUM |
| 10 | Add incident response runbook to `.team/` documentation | P2 | Low | MEDIUM |
| 11 | Conduct DPIA for healthcare and mental health use cases | P2 | High | HIGH |

---

## 11. Compliance Sign-Off Checklist

This checklist must be completed before each milestone release:

| # | Check | M1 | M2 | M3 | M4 | M5a | M5b | M6 |
|---|-------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 | No PII in tracked files (CI scan) | -- | -- | -- | REQ | REQ | REQ | REQ |
| 2 | No API keys in tracked files (CI scan) | REQ | REQ | REQ | REQ | REQ | REQ | REQ |
| 3 | `.gitignore` covers all sensitive patterns | REQ | -- | -- | -- | -- | -- | REQ |
| 4 | Dataset licenses verified against allowlist | -- | -- | -- | -- | REQ | -- | REQ |
| 5 | HIGH-priority datasets PII-scanned | -- | -- | -- | -- | REQ | -- | REQ |
| 6 | Privacy notice drafted | -- | -- | -- | REQ | -- | -- | REQ |
| 7 | `LICENSE` file present in repo root | REQ | -- | -- | -- | -- | -- | REQ |
| 8 | Data retention policy documented | -- | -- | -- | -- | -- | -- | REQ |

Legend: REQ = Required for this milestone, `--` = Not applicable

---

*Data Privacy Assessment v1.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
