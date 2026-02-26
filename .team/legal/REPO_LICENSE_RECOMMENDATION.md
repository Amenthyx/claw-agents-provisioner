# Repository License Recommendation — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: LEGAL (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: RECOMMENDATION (pending PM/INFRA approval)

---

## 1. Context

The Claw Agents Provisioner repository contains:

| Content Type | Examples | Origin |
|-------------|---------|--------|
| Bash scripts | `claw.sh`, `install-*.sh`, `entrypoint.sh`, `provision-base.sh` | Original (Amenthyx) |
| Python scripts | `resolve.py`, `generate_env.py`, `train_lora.py`, `validate_datasets.py` | Original (Amenthyx) |
| Dockerfiles | Per-agent Dockerfiles, `Dockerfile.finetune` | Original (Amenthyx) |
| Vagrantfiles | Per-agent Vagrantfiles | Original (Amenthyx) |
| Docker Compose | `docker-compose.yml` | Original (Amenthyx) |
| Configuration templates | `.env.template`, agent config templates | Original (Amenthyx) |
| JSON schemas | `assessment-schema.json` | Original (Amenthyx) |
| Example data | `client-assessment.example.json`, example assessments | Original (Amenthyx) |
| System prompts | 50 `system_prompt.txt` files | Original (Amenthyx) |
| Adapter configs | 50 `adapter_config.json` + `training_config.json` files | Original (Amenthyx) |
| Training datasets | 50 datasets in `finetune/datasets/` | Third-party (various open licenses) |
| Documentation | README, guides, `.ai/context_base.md` | Original (Amenthyx) |

The repository is hosted on GitHub under the `Amenthyx` organization and is intended to be **public**.

---

## 2. Requirements for the Repository License

The chosen license must satisfy ALL of the following:

| # | Requirement | Reason |
|---|-------------|--------|
| R1 | Permit commercial use | Amenthyx sells services (Private 1K EUR, Enterprise 5K+, Managed 300/mo) based on this tool |
| R2 | Permit redistribution | Public GitHub repository; community forks and contributions desired |
| R3 | Permit modification | Users need to customize scripts, configs, and adapters for their deployments |
| R4 | Be compatible with Apache-2.0 dataset content | 10 datasets expected under Apache-2.0 |
| R5 | Be compatible with MIT dataset content | Possible MIT-licensed datasets |
| R6 | Be compatible with CC-BY-4.0 dataset content | 12 datasets expected under CC-BY-4.0 |
| R7 | Be compatible with CC-BY-SA-4.0 dataset content | 3 datasets expected under CC-BY-SA-4.0 |
| R8 | Be compatible with CC0/Public Domain dataset content | 24 datasets expected under CC0/Public Domain |
| R9 | Include a patent grant | Enterprise clients (like Kai, the SaaS CTO persona) need patent safety |
| R10 | Be well-understood in the open-source ecosystem | Reduces legal friction for adopters |
| R11 | Not impose copyleft obligations on the code | Amenthyx may offer proprietary add-ons or services |
| R12 | Allow Amenthyx to offer commercial support without license conflict | Core business model |

---

## 3. License Comparison

### 3.1 Candidate Licenses

| License | Commercial | Redistribute | Modify | Patent Grant | Copyleft | CC-BY-SA Compatible | Ecosystem Familiarity |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **Apache-2.0** | Y | Y | Y | Y | N | Y (code + data are separate works) | Very High |
| MIT | Y | Y | Y | N (implicit) | N | Y | Very High |
| BSD-3-Clause | Y | Y | Y | N | N | Y | High |
| ISC | Y | Y | Y | N | N | Y | Medium |
| GPL-3.0 | Y | Y | Y | Y | YES (strong) | Y | Very High |
| AGPL-3.0 | Y | Y | Y | Y | YES (network) | Y | High |
| LGPL-3.0 | Y | Y | Y | Y | YES (weak) | Y | High |
| MPL-2.0 | Y | Y | Y | Y | YES (file-level) | Y | Medium |
| Unlicense | Y | Y | Y | N | N | Y | Medium |

### 3.2 Eliminated Candidates

| License | Reason for Elimination |
|---------|----------------------|
| GPL-3.0 | Strong copyleft would require all derivative works (including client customizations) to be GPL. Incompatible with R11 (no copyleft on code) and R12 (commercial services). |
| AGPL-3.0 | Even more restrictive than GPL; network use triggers copyleft. Would force clients running the agent over a network to open-source their modifications. Incompatible with R11, R12. |
| LGPL-3.0 | Weak copyleft still imposes obligations on modifications to the licensed code itself. Adds unnecessary complexity for a toolkit project. |
| MPL-2.0 | File-level copyleft is better than GPL but still creates confusion for users who modify scripts. Adds unnecessary complexity. |
| Unlicense | No patent grant (fails R9). Limited legal clarity in some jurisdictions (e.g., Germany does not recognize waiver of moral rights). |
| ISC | Functionally identical to MIT but less commonly used. No advantage over MIT; less ecosystem familiarity. |

### 3.3 Final Candidates: Apache-2.0 vs. MIT vs. BSD-3-Clause

| Criterion | Apache-2.0 | MIT | BSD-3-Clause |
|-----------|:-:|:-:|:-:|
| Explicit patent grant | YES (Section 3) | NO | NO |
| Trademark protection | YES (Section 6 — does not grant trademark rights) | NO | NO |
| Contributor license terms | YES (implicit via Section 5) | NO | NO |
| Attribution requirement | YES (NOTICE file + license header) | YES (license text) | YES (license text) |
| Length and complexity | Moderate (3 pages) | Minimal (1 paragraph) | Minimal (1 paragraph) |
| Enterprise acceptance | Excellent | Excellent | Good |
| Foundation preference (CNCF, ASF) | Preferred | Accepted | Accepted |
| Compatibility with CC-BY-SA-4.0 data | YES (separate works) | YES (separate works) | YES (separate works) |

---

## 4. Recommendation: Apache License 2.0

### 4.1 Rationale

**Apache-2.0** is the recommended license for the Claw Agents Provisioner repository for the following reasons:

1. **Patent Grant (R9)**: Apache-2.0 Section 3 provides an explicit patent license from each contributor. This is critical for enterprise clients who need assurance that using the provisioner does not expose them to patent claims. MIT and BSD-3-Clause provide no explicit patent protection.

2. **Trademark Protection**: Apache-2.0 Section 6 explicitly states that the license does not grant permission to use the licensor's trademarks. This protects the "Amenthyx" and "Claw" brand names from unauthorized use by third parties who fork the project.

3. **Contributor Clarity**: Apache-2.0 Section 5 defines the terms under which contributions are accepted, providing legal clarity for open-source contributors without requiring a separate Contributor License Agreement (CLA).

4. **No Copyleft (R11)**: Apache-2.0 is a permissive license. Users can modify, redistribute, and use the code commercially without being required to open-source their changes. This supports Amenthyx's commercial service model (R12).

5. **Full Compatibility with Dataset Licenses (R4-R8)**:
   - Apache-2.0 code + Apache-2.0 data: Fully compatible (same license).
   - Apache-2.0 code + MIT data: Fully compatible (MIT is more permissive).
   - Apache-2.0 code + CC-BY-4.0 data: Compatible. CC-BY applies to the data; Apache-2.0 applies to the code. They are separate works.
   - Apache-2.0 code + CC-BY-SA-4.0 data: Compatible. The ShareAlike obligation applies to the dataset (derivative data), NOT to the code. Apache-2.0 code that merely reads or processes CC-BY-SA data is not a derivative of the data.
   - Apache-2.0 code + CC0/Public Domain data: Fully compatible (no restrictions on data).

6. **Enterprise Ecosystem (R10)**: Apache-2.0 is the standard license for enterprise open-source projects (Kubernetes, TensorFlow, Apache ecosystem, Hugging Face Transformers). Enterprise legal departments are comfortable with it.

### 4.2 Why NOT MIT

While MIT is simpler and more popular by raw count, it lacks:
- Explicit patent grant (critical for enterprise adoption)
- Trademark protection (critical for brand protection)
- Contributor license terms (creates ambiguity for PRs)

For a project that targets enterprise clients (5K+ EUR packages) and includes fine-tuning technology (potential patent exposure), the patent grant alone justifies Apache-2.0 over MIT.

### 4.3 CC-BY-SA Interaction — Detailed Analysis

The 3 CC-BY-SA-4.0 datasets (19-WikiSQL/Spider, 36-DevOps/StackOverflow, 38-DBA/StackOverflow) deserve specific attention:

**Question**: Does including CC-BY-SA data in an Apache-2.0 repository "infect" the code with ShareAlike?

**Answer**: No. The CC-BY-SA-4.0 license defines "Adapted Material" as material that is "derived from or based upon the Licensed Material." The Apache-2.0 code (scripts, Dockerfiles, Python files) is NOT derived from the datasets. The code processes the data but does not incorporate it. They are independent works distributed in the same repository.

The CC-BY-SA obligation attaches only to:
- The dataset files themselves (if modified, the modified version must be CC-BY-SA)
- Any new datasets created by transforming the CC-BY-SA data

It does NOT attach to:
- The repository license
- Other datasets under different licenses
- Code that reads or processes the data
- LoRA adapter weights trained on the data (prevailing view: statistical transformation, not adaptation)

**Mitigation**: To make this crystal clear, the repository NOTICE file should state:

> The code in this repository is licensed under Apache License 2.0.
> Training datasets in `finetune/datasets/` are licensed under their individual
> licenses as documented in each dataset's `metadata.json` file. See
> `finetune/datasets/LICENSES.md` for a consolidated list.

---

## 5. Implementation

### 5.1 Required Files

| File | Content | Location |
|------|---------|----------|
| `LICENSE` | Full text of Apache License 2.0 | Repository root |
| `NOTICE` | Project name, copyright notice, third-party attribution summary | Repository root |
| `finetune/datasets/LICENSES.md` | Consolidated dataset license/attribution table | Datasets directory |

### 5.2 LICENSE File Content

The `LICENSE` file should contain the standard Apache License 2.0 text, obtainable from:
https://www.apache.org/licenses/LICENSE-2.0.txt

### 5.3 NOTICE File Content

```
Claw Agents Provisioner
Copyright 2026 Amenthyx

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

THIRD-PARTY DATASETS

This repository includes training datasets in the finetune/datasets/
directory that are licensed under various open-source and open-data
licenses (Apache 2.0, MIT, CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0,
Public Domain, ODC-BY-1.0). These datasets are NOT covered by the
Apache License 2.0 — they retain their original licenses.

See finetune/datasets/LICENSES.md for the complete list of datasets,
their sources, and their individual license terms.

Datasets licensed under CC-BY-SA-4.0 (datasets 19, 36, 38) are
subject to the ShareAlike condition: any adapted versions of these
specific datasets must be distributed under CC-BY-SA-4.0 or a
compatible license.
```

### 5.4 Source File Headers (Recommended)

For Python and Bash files authored by Amenthyx, include a standard header:

```python
# Copyright 2026 Amenthyx
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

For Bash scripts:

```bash
#!/usr/bin/env bash
# Copyright 2026 Amenthyx
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

### 5.5 Dockerfile and Vagrantfile Headers

Dockerfiles and Vagrantfiles should include the same header using `#` comments.

### 5.6 JSON/TOML Config Files

Configuration files (JSON, TOML) typically cannot contain comments. For these, the license coverage is provided by the root `LICENSE` file. No per-file header is needed.

---

## 6. Alternative Considered: Dual Licensing

An alternative approach would be dual licensing:
- **Apache-2.0** for the code (scripts, Dockerfiles, configs)
- **CC-BY-4.0** for the documentation and original datasets

This was considered but rejected because:
1. It adds complexity for users who must determine which license applies to which files.
2. Apache-2.0 already covers documentation and creative works adequately.
3. The NOTICE file approach (Section 5.3) achieves the same clarity without dual licensing.
4. Third-party datasets already have their own licenses regardless of the repo license.

---

## 7. Downstream Implications

### 7.1 For Amenthyx Consultants

- Consultants can freely use, modify, and deploy the provisioner for client engagements.
- Client-specific customizations (assessment files, `.env` files, custom adapter configs) are NOT required to be open-sourced.
- Pre-built adapters shipped with the repo are Apache-2.0 (no obligation to share client-trained adapters).

### 7.2 For Open-Source Community

- Anyone can fork, modify, and redistribute.
- Attribution is required (NOTICE file must be preserved).
- Patent grant extends to all users.
- No obligation to contribute changes back (but encouraged).

### 7.3 For Enterprise Clients

- Enterprise clients can deploy internally without legal review concerns (Apache-2.0 is pre-approved at most large organizations).
- Patent grant provides IP safety.
- No obligation to open-source their internal customizations.

### 7.4 For Competitors

- Competitors can fork and use the code. This is intentional — open-source strategy builds ecosystem trust and adoption.
- Competitors CANNOT use the "Amenthyx" or "Claw" trademarks (Apache-2.0 Section 6).
- Competitors MUST include the NOTICE file and LICENSE in their forks.

---

## 8. Action Items

| # | Action | Owner | Milestone | Priority |
|---|--------|-------|-----------|----------|
| 1 | Create `LICENSE` file with Apache-2.0 full text | INFRA | M1 | P0 |
| 2 | Create `NOTICE` file with copyright and third-party notice | INFRA | M1 | P0 |
| 3 | Add Apache-2.0 headers to all Bash scripts | DEVOPS | M1 | P1 |
| 4 | Add Apache-2.0 headers to all Python scripts | BE | M4 | P1 |
| 5 | Add Apache-2.0 headers to all Dockerfiles | DEVOPS | M1 | P1 |
| 6 | Create `finetune/datasets/LICENSES.md` | BE/LEGAL | M5a | P0 |
| 7 | Verify NOTICE file is complete before public release | LEGAL | M6 | P0 |

---

## 9. Approval

| Role | Decision | Date |
|------|----------|------|
| LEGAL | RECOMMENDED: Apache License 2.0 | 2026-02-26 |
| PM | PENDING | -- |
| INFRA | PENDING | -- |

---

*Repository License Recommendation v1.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
