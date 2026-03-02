# License Matrix -- Third-Party Dependencies

> Version: 2.0
> Date: 2026-03-02
> Author: Legal/Compliance Attorney (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: ACTIVE
> Supersedes: LICENSE_MATRIX.md v1.0 (2026-02-26, dataset-only coverage)

---

## 1. Purpose

This matrix catalogs ALL third-party dependencies used by the Claw Agents Provisioner, including:
- Python pip packages (fine-tuning pipeline)
- Infrastructure tools (Docker, nginx, monitoring stack)
- Container base images
- Runtime dependencies (LLM providers, databases)
- Testing tools

Each entry is classified by license type, copyleft status, and distribution risk.

**Previous version (v1.0)** covered only dataset licenses. This v2.0 expands to cover the full dependency chain. The dataset license table from v1.0 is retained in Section 5.

---

## 2. License Risk Classification

| Risk Level | Definition | Action Required |
|:----------:|-----------|-----------------|
| NONE | Permissive license (Apache 2.0, MIT, BSD, ISC, PSF) | Attribution only |
| LOW | Weak copyleft or creative commons with conditions | Follow license terms; document |
| MEDIUM | AGPL or strong copyleft; used as external service only | Ensure no modification or embedding; document stance |
| HIGH | GPL/AGPL with modification or redistribution | Requires legal review; consider alternatives |
| BLOCKED | Incompatible with commercial use or project license | Must not use; find alternative |

---

## 3. Python Dependencies (finetune/requirements.txt)

All packages are used exclusively within the fine-tuning pipeline container (`finetune/Dockerfile.finetune`). They are NOT redistributed in the main project -- they are installed at Docker build time from PyPI.

| Package | Version | License | SPDX | Copyleft | Risk | Notes |
|---------|---------|---------|------|:--------:|:----:|-------|
| torch | 2.1.0 | BSD-3-Clause | BSD-3-Clause | NO | NONE | Meta AI; core ML framework |
| torchvision | 0.16.0 | BSD-3-Clause | BSD-3-Clause | NO | NONE | Meta AI; vision utilities |
| transformers | 4.40.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face |
| peft | 0.10.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face; LoRA/QLoRA |
| datasets | 2.19.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face |
| accelerate | 0.29.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face |
| tokenizers | 0.19.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face; Rust-backed tokenizer |
| bitsandbytes | 0.43.0 | MIT | MIT | NO | NONE | Quantization library |
| jsonlines | 4.0.0 | BSD-3-Clause | BSD-3-Clause | NO | NONE | JSONL file handling |
| pandas | 2.2.0 | BSD-3-Clause | BSD-3-Clause | NO | NONE | Data manipulation |
| tqdm | 4.66.0 | MIT + MPL-2.0 | MIT | NO | NONE | Progress bars; dual-licensed |
| rich | 13.7.0 | MIT | MIT | NO | NONE | Terminal UI library |
| jsonschema | 4.21.0 | MIT | MIT | NO | NONE | JSON Schema validation |
| evaluate | 0.4.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face evaluation |
| rouge-score | 0.1.2 | Apache-2.0 | Apache-2.0 | NO | NONE | ROUGE metrics |
| nltk | 3.8.0 | Apache-2.0 | Apache-2.0 | NO | NONE | NLP toolkit |
| tensorboard | 2.16.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Google; training visualization |
| wandb | 0.16.0 | MIT | MIT | NO | NONE | Weights & Biases; experiment tracking |
| requests | 2.31.0 | Apache-2.0 | Apache-2.0 | NO | NONE | HTTP client |
| huggingface-hub | 0.22.0 | Apache-2.0 | Apache-2.0 | NO | NONE | Hugging Face Hub client |
| tomli | 2.0.0 | MIT | MIT | NO | NONE | TOML parser |
| pyyaml | 6.0.0 | MIT | MIT | NO | NONE | YAML parser |

**Summary**: All 22 Python dependencies are under permissive licenses (Apache-2.0, MIT, BSD-3-Clause). No copyleft risk. No action required beyond standard attribution.

---

## 4. Python Shared Module Dependencies

The `shared/*.py` modules use Python 3.8+ stdlib only, with one exception:

| Package | Used By | License | SPDX | Copyleft | Risk | Notes |
|---------|---------|---------|------|:--------:|:----:|-------|
| cryptography | `claw_vault.py` | Apache-2.0 + BSD-3-Clause | Apache-2.0 | NO | NONE | Dual-licensed; Fernet encryption + PBKDF2 |
| Python stdlib | All shared modules | PSF License | PSF-2.0 | NO | NONE | Python Software Foundation License |

**Summary**: No copyleft risk. The `cryptography` package is the only pip dependency required by the core platform (all other shared modules are stdlib-only).

---

## 5. Infrastructure & Monitoring Stack

### 5.1 Core Infrastructure

| Component | Version | License | SPDX | Copyleft | Risk | Distribution Method | Notes |
|-----------|---------|---------|------|:--------:|:----:|-------------------|-------|
| Docker Engine | 24.0+ | Apache-2.0 | Apache-2.0 | NO | NONE | User-installed prerequisite | Not bundled |
| Docker Compose | v2 | Apache-2.0 | Apache-2.0 | NO | NONE | User-installed prerequisite | Not bundled |
| nginx | latest | BSD-2-Clause | BSD-2-Clause | NO | NONE | Docker Hub official image | TLS termination; not modified |
| PostgreSQL | 16-alpine | PostgreSQL License | PostgreSQL | NO | NONE | Docker Hub official image | Optional profile; MIT-like license |
| SQLite | 3.x | Public Domain | Public-Domain | NO | NONE | Python stdlib built-in | Default database engine |
| Vagrant | latest | BSL 1.1 | BSL-1.1 | SPECIAL | LOW | User-installed prerequisite | HashiCorp BSL; free for non-competing use |
| VirtualBox | latest | GPL-2.0 (base) | GPL-2.0 | YES | LOW | User-installed prerequisite | Not distributed by Claw; user installs separately |

### 5.2 Monitoring Stack

| Component | Version | License | SPDX | Copyleft | Risk | Distribution Method | Flagged |
|-----------|---------|---------|------|:--------:|:----:|-------------------|:-------:|
| **Prometheus** | latest | Apache-2.0 | Apache-2.0 | NO | NONE | Docker Hub official image | NO |
| **Grafana** | latest | AGPL-3.0 | AGPL-3.0 | YES (network) | MEDIUM | Docker Hub official image | YES |
| **Loki** | latest | AGPL-3.0 | AGPL-3.0 | YES (network) | MEDIUM | Docker Hub official image | YES |
| **k6** | latest | AGPL-3.0 | AGPL-3.0 | YES (network) | MEDIUM | User-installed test tool | YES |

### 5.3 Testing & CI Tools

| Component | Version | License | SPDX | Copyleft | Risk | Distribution Method | Notes |
|-----------|---------|---------|------|:--------:|:----:|-------------------|-------|
| pytest | latest | MIT | MIT | NO | NONE | pip install (dev dependency) | Test runner |
| shellcheck | latest | GPL-3.0 | GPL-3.0 | YES | LOW | CI-only (GitHub Actions runner) | Not distributed; CI lint tool |
| hadolint | latest | GPL-3.0 | GPL-3.0 | YES | LOW | CI-only (GitHub Actions action) | Not distributed; CI lint tool |
| ruff | latest | MIT | MIT | NO | NONE | pip install (dev dependency) | Python linter |
| mypy | latest | MIT | MIT | NO | NONE | pip install (dev dependency) | Type checker |
| Trivy | latest | Apache-2.0 | Apache-2.0 | NO | NONE | CI-only (GitHub Actions) | Container scanner |

### 5.4 Container Base Images

| Image | Used By | License | Notes |
|-------|---------|---------|-------|
| python:3.11-slim | health-aggregator service | PSF License | Debian-based; PSF + Debian DFSG |
| postgres:16-alpine | PostgreSQL service | PostgreSQL License | Alpine-based |
| Agent-specific base images | zeroclaw, nanoclaw, picoclaw, openclaw, parlant | Varies per agent | Agents are installed from upstream; Claw does not modify agent source |
| nvidia/cuda | finetune container | NVIDIA EULA | Proprietary EULA; free for use; cannot redistribute the CUDA toolkit itself |

---

## 6. Flagged Dependencies -- Copyleft Analysis

### 6.1 Grafana (AGPL-3.0) -- FLAGGED

**License**: GNU Affero General Public License v3.0

**How Claw uses Grafana**:
- Referenced in `docker-compose.yml` production profile (to be added in Wave 2)
- Users pull the official Grafana Docker image from Docker Hub
- Claw provides pre-built JSON dashboard templates (separate works, not Grafana code)
- No Grafana source code is modified, forked, or redistributed

**AGPL Impact Assessment**:
| Question | Answer |
|----------|--------|
| Does Claw modify Grafana source? | NO |
| Does Claw redistribute Grafana? | NO -- users pull from Docker Hub |
| Does Claw embed Grafana code? | NO -- interacts via HTTP API |
| Are Claw's dashboard JSON templates derivative works? | NO -- JSON configs are data, not software |

**Recommendation**: SAFE TO USE. No AGPL obligations arise from using unmodified Grafana as a Docker container. Document this analysis for auditor reference.

**Alternative if concerned**: Grafana Cloud Free tier (hosted by Grafana Labs, no AGPL concern) or replace with Apache-2.0 alternatives (e.g., Apache Superset for dashboards).

### 6.2 Loki (AGPL-3.0) -- FLAGGED

**License**: GNU Affero General Public License v3.0

**How Claw uses Loki**:
- Referenced as Docker log driver target
- Users pull official Loki Docker image
- No source modification or redistribution

**Recommendation**: SAFE TO USE. Same analysis as Grafana. Loki is used as an unmodified external service.

**Alternative if concerned**: Promtail + Elasticsearch (Apache-2.0 via OpenSearch) or Fluentd (Apache-2.0).

### 6.3 k6 (AGPL-3.0) -- FLAGGED

**License**: GNU Affero General Public License v3.0

**How Claw uses k6**:
- Load testing tool run during CI and development
- k6 scripts (JavaScript) written by Claw team are separate works
- k6 binary is NOT distributed with Claw

**Recommendation**: SAFE TO USE. k6 scripts are inputs to the k6 engine, not derivative works of it. The k6 binary is a development tool, not a runtime dependency.

**Alternative if concerned**: Apache Bench (ab), Locust (MIT), or Artillery (MPL-2.0).

### 6.4 shellcheck (GPL-3.0) -- FLAGGED

**License**: GNU General Public License v3.0

**How Claw uses shellcheck**: CI-only linting tool run in GitHub Actions. Not bundled, not redistributed, not a runtime dependency.

**Recommendation**: SAFE TO USE. Using GPL tools in CI does not impose GPL obligations on the project's own code.

### 6.5 hadolint (GPL-3.0) -- FLAGGED

**License**: GNU General Public License v3.0

**How Claw uses hadolint**: CI-only Dockerfile linting tool. Same analysis as shellcheck.

**Recommendation**: SAFE TO USE.

### 6.6 VirtualBox (GPL-2.0) -- FLAGGED

**License**: GNU General Public License v2.0 (base edition)

**How Claw uses VirtualBox**: Optional prerequisite for Vagrant-based deployments. User installs VirtualBox independently. Claw does not bundle, modify, or redistribute VirtualBox.

**Recommendation**: SAFE TO USE. No distribution obligation.

### 6.7 Vagrant (BSL-1.1) -- FLAGGED

**License**: Business Source License 1.1 (HashiCorp)

**How Claw uses Vagrant**: Optional deployment method. Users install Vagrant independently. The BSL restricts competitive use (building a product that competes with Vagrant).

**Impact**: Claw is NOT a Vagrant competitor. Using Vagrant as a provisioning tool is explicitly permitted under the BSL.

**Recommendation**: SAFE TO USE. No license conflict.

### 6.8 NVIDIA CUDA (Proprietary EULA) -- FLAGGED

**License**: NVIDIA CUDA Toolkit End User License Agreement

**How Claw uses CUDA**: The fine-tuning Dockerfile (`Dockerfile.finetune`) uses `nvidia/cuda` base image for GPU training.

**Restrictions**:
- Cannot redistribute the CUDA toolkit binaries outside Docker images
- Cannot reverse-engineer CUDA
- Free to use for any purpose including commercial

**Recommendation**: SAFE TO USE. Docker images referencing `nvidia/cuda` are standard practice. Users pull the base image from NVIDIA's Docker registry.

---

## 7. License Compatibility Matrix

| Claw Component License | Apache-2.0 Deps | MIT Deps | BSD Deps | AGPL Deps | GPL Deps | Proprietary |
|:----------------------:|:----------------:|:--------:|:--------:|:---------:|:--------:|:-----------:|
| **Apache-2.0** (project) | COMPATIBLE | COMPATIBLE | COMPATIBLE | COMPATIBLE (no linking) | COMPATIBLE (no linking) | COMPATIBLE (no redistribution) |

All dependencies are used in ways that are compatible with the project's Apache-2.0 license:
- Permissive deps (Apache, MIT, BSD): fully compatible
- AGPL deps (Grafana, Loki, k6): used as unmodified external services
- GPL deps (shellcheck, hadolint): CI-only tools, not distributed
- Proprietary (NVIDIA CUDA): not redistributed; used in Docker build context

---

## 8. Dataset License Summary

Retained from v1.0 for completeness. See the separate `LICENSE_MATRIX.md` v1.0 or `COMPLIANCE_REVIEW.md` for the full 50-dataset table.

| License | Count | Copyleft | Action |
|---------|:-----:|:--------:|--------|
| CC0-1.0 | 19 | NO | No action |
| CC-BY-4.0 | 12 | NO | Attribution in metadata.json |
| Apache-2.0 | 10 | NO | Attribution in metadata.json |
| Public-Domain | 5 | NO | No action |
| CC-BY-SA-4.0 | 3 | YES (data only) | Modified datasets must stay CC-BY-SA; does not affect code or adapter weights |
| ODC-BY-1.0 | 1 | NO | Attribution in metadata.json |

**All 50 datasets are compatible with the Apache 2.0 project license.**

---

## 9. Recommendations

| # | Recommendation | Priority | Status |
|---|---------------|:--------:|:------:|
| 1 | Maintain this matrix and review on each Wave completion | P0 | ACTIVE |
| 2 | Document "no modification" stance for AGPL components in NOTICE file | P1 | PENDING |
| 3 | Add SBOM generation for Python dependencies (already in CI via CycloneDX) | P0 | DONE |
| 4 | Add npm audit for wizard-ui dependencies when wizard-ui is built | P1 | PENDING |
| 5 | Review NVIDIA CUDA EULA if fine-tuning containers are ever distributed as pre-built images | P2 | N/A |
| 6 | If Vagrant BSL changes terms, evaluate switching to libvirt or Podman | P2 | MONITOR |
| 7 | Pin all Docker base images to specific digests for reproducibility and license traceability | P1 | PENDING |

---

## 10. Approval

| Role | Decision | Date |
|------|----------|------|
| Legal/Compliance Attorney | APPROVED -- no license conflicts identified | 2026-03-02 |

---

*License Matrix v2.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
*Covers: Python packages, infrastructure tools, monitoring stack, container images, testing tools, datasets*
*All claims verified against requirements.txt, docker-compose.yml, and CI workflow as of 2026-03-02*
