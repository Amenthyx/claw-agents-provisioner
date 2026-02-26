# Compliance Review — Claw Agents Provisioner

> Version: 1.0
> Date: 2026-02-26
> Author: LEGAL (Full-Stack Team, Amenthyx AI Teams v3.0)
> Status: ACTIVE
> Review Cycle: Per milestone + pre-release (M6)

---

## 1. Executive Summary

This compliance review assesses the legal posture of the Claw Agents Provisioner project across four dimensions: (1) dataset license compliance for the 50 open-source datasets committed to the repository, (2) GDPR and privacy implications of client assessment data, (3) intellectual property considerations for code and configurations, and (4) regulatory exposure from domain-specific fine-tuning adapters (healthcare, legal, finance).

**Overall Risk Rating: MEDIUM** — manageable with the mitigations recommended herein.

Key findings:

- The six allowed license categories (Apache 2.0, MIT, CC-BY, CC-BY-SA, CC0, Public Domain) are all compatible with commercial use and public GitHub redistribution, provided attribution requirements are met.
- CC-BY-SA (ShareAlike) datasets impose a copyleft-like obligation: any derivative datasets must be shared under the same or compatible license. This does NOT infect the repository's code license, but it constrains downstream dataset modifications.
- Three use cases (04-Healthcare Triage, 49-Mental Health & Counseling, 05-Legal Document Review) require heightened scrutiny for de-identification, consent, and regulatory compliance even if the data itself is openly licensed.
- Client assessment JSONs contain PII (name, company, industry, contact info). The existing `.gitignore` correctly excludes these files, but additional procedural safeguards are recommended.
- No LICENSE file currently exists for the repository. One must be added before public release.

---

## 2. Dataset License Compliance Analysis

### 2.1 Allowed License Categories

Per the project strategy, only the following license types are permitted for committed datasets:

| License | SPDX Identifier | Commercial Use | Redistribution | Attribution Required | ShareAlike |
|---------|-----------------|:-:|:-:|:-:|:-:|
| Apache License 2.0 | `Apache-2.0` | Y | Y | Y | N |
| MIT License | `MIT` | Y | Y | Y | N |
| Creative Commons Attribution 4.0 | `CC-BY-4.0` | Y | Y | Y | N |
| Creative Commons Attribution-ShareAlike 4.0 | `CC-BY-SA-4.0` | Y | Y | Y | Y |
| Creative Commons Zero 1.0 | `CC0-1.0` | Y | Y | N | N |
| Public Domain | `Public-Domain` | Y | Y | N | N |

### 2.2 Compatibility with Public GitHub Repository

All six license categories permit:
- **Commercial use**: Amenthyx can sell services (Private 1K EUR, Enterprise 5K+, Managed 300/mo) built on top of these datasets without violating the dataset licenses. The datasets themselves remain under their original license.
- **Redistribution**: Committing datasets inside a public GitHub repository constitutes redistribution. All six licenses explicitly permit this.
- **Modification**: Creating JSONL training data from these sources (subsetting, reformatting, instruction-tuning formatting) constitutes modification. All six licenses permit this.

### 2.3 Attribution Obligations

Four of the six license categories (Apache 2.0, MIT, CC-BY, CC-BY-SA) require attribution. The project MUST:

1. Include a `metadata.json` in each dataset folder containing:
   - `license`: SPDX identifier
   - `license_url`: Link to the full license text
   - `source_url`: Link to the original dataset
   - `source_name`: Name of the original dataset
   - `author`: Original author or organization
   - `attribution_notice`: Exact attribution text if specified by the licensor

2. Include a consolidated `finetune/datasets/LICENSES.md` file listing all 50 datasets with their licenses and attribution notices in one place.

3. Ensure the repository README contains a section noting that the `finetune/datasets/` directory contains third-party data under various open licenses, with a pointer to the consolidated license file.

### 2.4 CC-BY-SA (ShareAlike) Special Handling

Datasets licensed under CC-BY-SA-4.0 impose a copyleft obligation:
- Any **adapted material** (modifications, transformations, derivative datasets) must be distributed under CC-BY-SA-4.0 or a compatible license.
- This applies to the **data only**, not to the code or adapter weights. The PEFT/LoRA adapter weights trained on CC-BY-SA data are generally considered a separate work, not a derivative of the dataset, per prevailing legal interpretation (analogous to software compiled using GPL-licensed build tools).
- However, if we subset, reformat, or augment a CC-BY-SA dataset and commit that modified version, the modified version must carry CC-BY-SA-4.0.

**Recommendation**: For each CC-BY-SA dataset, include the CC-BY-SA-4.0 license text in the dataset folder and ensure `metadata.json` clearly states the ShareAlike obligation.

### 2.5 Datasets Requiring Heightened Scrutiny

The following use cases require additional legal review beyond standard license compliance:

#### 2.5.1 Healthcare Data (Use Cases 04, 49)

| Use Case | Dataset | Concern |
|----------|---------|---------|
| 04 — Healthcare Triage | NLM/NIH open data | Even if openly licensed, medical data may contain residual PHI. Must verify HIPAA Safe Harbor de-identification. |
| 49 — Mental Health & Counseling | Open (Anonymized) | Mental health conversations are extremely sensitive. Must verify: (a) IRB approval for original collection, (b) adequate anonymization, (c) no re-identification risk from context. |

**Requirements**:
- Verify that the source data has undergone HIPAA Safe Harbor de-identification (18 identifiers removed) or Expert Determination.
- Document the de-identification method in `metadata.json`.
- Add a `sensitivity: high` field to `metadata.json` for these datasets.
- Include a disclaimer in the dataset folder README that this data is for AI training purposes only and must not be used for clinical diagnosis.
- Consider whether the EU AI Act (effective Aug 2025) classifies healthcare triage as "high-risk AI" — if so, additional documentation requirements apply (see Section 5).

#### 2.5.2 Legal Data (Use Cases 05, 43)

| Use Case | Dataset | Concern |
|----------|---------|---------|
| 05 — Legal Document Review | HF open legal corpus | Court documents are generally public, but may contain party names, addresses, case details. |
| 43 — Compliance & Regulatory | Open Legal sources | Regulatory texts are public domain, but annotated versions may carry their own licenses. |

**Requirements**:
- Verify that legal datasets use publicly available court documents or statutes (inherently public domain in most jurisdictions).
- For annotated datasets, verify that the annotations are separately licensed under an approved license.
- Add disclaimer: fine-tuned adapters do not constitute legal advice.

#### 2.5.3 Financial Data (Use Cases 06, 21, 22, 50)

| Use Case | Dataset | Concern |
|----------|---------|---------|
| 06 — Personal Finance Advisor | HF | May contain synthetic or real financial advice; verify no real account data. |
| 21 — Accounting & Bookkeeping | Kaggle | Verify no real company financial records. |
| 22 — Insurance Claims Processing | Kaggle | Claims data may contain PII (names, policy numbers, medical info). |
| 50 — Personal Finance & Budgeting | Open | Verify anonymization of any real financial data. |

**Requirements**:
- Verify all financial datasets are either synthetic, aggregated, or properly anonymized.
- Add disclaimer: fine-tuned adapters do not constitute financial advice.
- Flag insurance claims dataset (22) for PII review — insurance claims commonly contain names, addresses, SSNs, and medical information.

#### 2.5.4 Communication Data (Use Case 08)

| Use Case | Dataset | Concern |
|----------|---------|---------|
| 08 — Email Management & Drafting | Public (Enron) | The Enron email corpus is widely used in research but contains real names, real email addresses, and potentially sensitive business communications. |

**Requirements**:
- The Enron corpus is considered public record (released during federal investigation). No copyright restriction applies.
- However, it contains real PII (employee names, email addresses, phone numbers, social security numbers in some emails).
- If committing a subset, consider redacting obvious PII (email addresses, phone numbers) from the training data.
- Document in `metadata.json` that this is public-record data with real identifiers.

#### 2.5.5 User-Generated Content (Use Cases 36, 38, 46)

| Use Case | Dataset | Concern |
|----------|---------|---------|
| 36 — DevOps & Infrastructure | StackOverflow | Stack Exchange data is CC-BY-SA-4.0. ShareAlike obligations apply. |
| 38 — Database Administration | StackOverflow | Same as above. |
| 46 — Creative Writing & Storytelling | Reddit (HF) | Reddit data licensing has been contentious since 2023 API changes. Verify the HF copy was obtained before the API restrictions, or that it falls under fair use / the original CC license. |

**Requirements**:
- Stack Exchange data: apply CC-BY-SA-4.0 handling (Section 2.4).
- Reddit data: verify provenance. If sourced from a Hugging Face dataset that was collected pre-2023 under the old Reddit terms, document this. If post-2023, assess whether the specific HF dataset has a valid open license from the original poster or aggregator.

### 2.6 Synthetic Datasets

Use cases 09, 20, 27, 33, 34, 37, 44 use synthetic or partially synthetic data.

**Requirements**:
- Synthetic data generated by the project team can be licensed under any terms (recommend CC0 for maximum flexibility).
- Synthetic data generated by AI models (e.g., GPT, Claude) may carry terms of service restrictions from the model provider. Verify:
  - Anthropic: output is owned by the user (Terms of Service as of 2025).
  - OpenAI: output is owned by the user (Terms of Service as of 2025).
  - DeepSeek: verify output ownership terms.
- Document the generation method in `metadata.json`.

---

## 3. GDPR Implications

### 3.1 Data Categories in the Project

| Data Category | Location | Contains PII | GDPR Relevance |
|---------------|----------|:-:|----------------|
| Client assessment JSONs | `client-assessment*.json` (root) | YES | Direct — client name, company, industry, contact info |
| API keys | `.env` | NO (secrets, not personal data) | Indirect — security concern, not GDPR |
| Training datasets | `finetune/datasets/` | POSSIBLY | Depends on source — see Section 2.5 |
| Adapter weights | `finetune/outputs/` (gitignored) | NO | Adapter weights do not contain extractable PII |
| System prompts | `finetune/adapters/*/system_prompt.txt` | NO | Generic industry prompts, no personal data |

### 3.2 GDPR Applicability

GDPR applies if:
1. The data controller (Amenthyx) is established in the EU, OR
2. The data processing relates to offering goods/services to EU residents, OR
3. The data processing relates to monitoring the behavior of EU residents.

Given that Amenthyx's service packages target EU clients (pricing in EUR) and the project charter mentions EU-based personas (Marco, Lucia), **GDPR applies**.

### 3.3 Lawful Basis for Processing

| Processing Activity | Lawful Basis | Notes |
|---------------------|-------------|-------|
| Collecting client assessment data | Art. 6(1)(b) — Contract performance | Necessary to deliver the contracted service (agent deployment) |
| Storing assessment data locally during deployment | Art. 6(1)(b) — Contract performance | Temporary storage for configuration generation |
| Committing assessment data to a public repo | **NOT PERMITTED** | This would be unlawful disclosure of personal data |
| Using open datasets for fine-tuning | Art. 6(1)(f) — Legitimate interest | Datasets are already public; processing is for product improvement |

### 3.4 GDPR Requirements Checklist

| # | Requirement | Status | Action Needed |
|---|-------------|--------|---------------|
| 1 | Assessment JSONs excluded from git tracking | PASS | `.gitignore` correctly excludes `client-assessment*.json` |
| 2 | Pre-commit hook prevents accidental PII commit | PENDING | Must be implemented in M6 (CI/CD milestone) |
| 3 | CI pipeline scans for PII patterns | PENDING | Must be implemented in M6 |
| 4 | Privacy notice for client assessment intake | MISSING | Must be added to `claw-client-assessment` repo |
| 5 | Data processing agreement (DPA) for service clients | MISSING | Must be drafted for Enterprise and Managed packages |
| 6 | Data retention policy for assessment files | MISSING | See DATA_PRIVACY_ASSESSMENT.md |
| 7 | Right to erasure procedure | MISSING | Must define how client data is deleted post-deployment |
| 8 | Data breach notification procedure | MISSING | Required if assessment data is accidentally exposed |
| 9 | Records of processing activities (ROPA) | MISSING | Required under Art. 30 if Amenthyx has 250+ employees or processes sensitive data regularly |
| 10 | Data Protection Impact Assessment (DPIA) | RECOMMENDED | For healthcare and mental health fine-tuning use cases |

### 3.5 GDPR Risk Rating

| Risk | Probability | Impact | Score |
|------|:-:|:-:|:-:|
| Accidental commit of assessment PII | H | H | RED |
| Residual PII in open training datasets | M | M | YELLOW |
| Missing DPA for service clients | M | H | RED |
| Missing privacy notice | L | M | GREEN |
| DPIA not conducted for health use cases | L | H | YELLOW |

---

## 4. CCPA Considerations

The California Consumer Privacy Act applies if Amenthyx serves California residents and meets threshold criteria (annual gross revenue >$25M, data of 100K+ consumers, or 50%+ revenue from selling data).

**Current Assessment**: Unlikely to apply at current scale (consulting business, not mass data processing). However, if the Managed service package (300 EUR/mo) scales to 100+ California-resident clients, CCPA may trigger.

**Recommendations**:
- Include a generic "US Privacy Rights" section in any privacy notice.
- Do not sell or share client assessment data with third parties.
- Maintain the ability to delete client data upon request (already covered by GDPR requirements).

---

## 5. EU AI Act Considerations

The EU AI Act (Regulation 2024/1689), with provisions entering force through August 2025 and August 2026, classifies AI systems by risk level.

### 5.1 Risk Classification of Fine-Tuned Adapters

| Use Case | AI Act Risk Level | Rationale |
|----------|:-:|-----------|
| 04 — Healthcare Triage | HIGH RISK | AI systems intended for use in healthcare that influence clinical decisions are classified as high-risk (Annex III, Section 5) |
| 05 — Legal Document Review | HIGH RISK | AI systems used for legal interpretation or assisting judicial decisions (Annex III, Section 8) |
| 49 — Mental Health & Counseling | HIGH RISK | AI systems that interact with vulnerable persons in a health context |
| 12 — HR & Recruitment | HIGH RISK | AI systems for recruitment, candidate filtering, or employment decisions (Annex III, Section 4) |
| All others | LIMITED or MINIMAL | General-purpose assistants with no high-risk application domain |

### 5.2 High-Risk Obligations

For use cases classified as HIGH RISK, the deploying organization (the client using the fine-tuned adapter) bears primary compliance obligations. However, as the provider of the fine-tuning pipeline and pre-built adapters, Amenthyx should:

1. **Document the intended purpose** of each adapter clearly in `system_prompt.txt` and `adapter_config.json`.
2. **Include disclaimers** that high-risk adapters require additional compliance steps by the deployer.
3. **Provide transparency documentation** (training data sources, known limitations, bias assessments).
4. **Flag high-risk use cases** in the adapter catalog with a visible warning.

### 5.3 General-Purpose AI (GPAI) Obligations

If the fine-tuned models are considered GPAI systems, additional transparency obligations apply (Art. 53):
- Technical documentation of training data
- Copyright compliance documentation
- Detailed summary of training data content

**Recommendation**: The `metadata.json` files for each dataset already satisfy much of this requirement. Ensure they include a `training_data_summary` field.

---

## 6. Intellectual Property Analysis

### 6.1 Code and Scripts

All Bash scripts, Python code, Dockerfiles, Vagrantfiles, and configuration templates written by the Amenthyx team are original works of authorship owned by Amenthyx. They can be licensed under any terms.

### 6.2 Upstream Agent Code

The four Claw agents (ZeroClaw, NanoClaw, PicoClaw, OpenClaw) are open-source projects. The provisioner does NOT modify or redistribute their source code — it installs them from upstream releases. This is analogous to a package manager and does not create any licensing obligation from the agent licenses onto the provisioner repository.

### 6.3 LoRA Adapter Weights

LoRA/QLoRA adapter weights are small parameter deltas that modify base model behavior. Legal consensus (as of 2026) generally holds that:
- Adapter weights are a **derivative work** of the training data (weak dependency — statistical transformation, not reproduction).
- Adapter weights are NOT a derivative work of the base model (they are independently created parameters that happen to be applied to the model).
- The adapter weights themselves can be independently licensed.

**Recommendation**: Pre-built adapter weights (once trained) should be licensed under Apache 2.0 to match the recommended repository license. Adapter weights trained on CC-BY-SA data should carry a note that the training data was CC-BY-SA, but the weights themselves are Apache 2.0.

### 6.4 System Prompts

System prompts in `finetune/adapters/*/system_prompt.txt` are original creative works by Amenthyx. They can be freely licensed. No third-party IP concerns.

---

## 7. Repository License Recommendation

See `REPO_LICENSE_RECOMMENDATION.md` for the detailed analysis. Summary: **Apache License 2.0** is recommended for the repository.

Rationale:
- Compatible with all six allowed dataset licenses
- Provides patent grant (important for enterprise clients)
- Permissive — allows commercial use by clients
- Well-understood in the open-source ecosystem
- Does not conflict with CC-BY-SA dataset obligations (code and data are separate works)

---

## 8. Service Package Compliance

### 8.1 Private Package (1K EUR)

| Obligation | Status |
|------------|--------|
| Client data handling | Must be covered by privacy notice + DPA |
| Adapter training on client data | Client retains ownership of custom adapter weights |
| Data deletion post-delivery | Must define retention period |

### 8.2 Enterprise Package (5K+ EUR)

| Obligation | Status |
|------------|--------|
| All Private package obligations | Same |
| GDPR compliance documentation | Must provide processing records |
| Security assessment | Must provide security posture documentation |
| High-risk AI use case disclosure | Must flag if deployment is healthcare/legal/HR |

### 8.3 Managed Package (300 EUR/mo)

| Obligation | Status |
|------------|--------|
| All Enterprise obligations | Same |
| Ongoing data processing | Requires DPA for continuous processing |
| Data breach notification | Must notify within 72 hours per GDPR Art. 33 |
| Regular security audits | Recommended annually |
| Data portability | Must support client data export on termination |

---

## 9. Action Items

| # | Action | Priority | Owner | Milestone | Status |
|---|--------|----------|-------|-----------|--------|
| 1 | Add `LICENSE` file (Apache 2.0) to repository root | P0 | LEGAL/INFRA | M1 | PENDING |
| 2 | Create `finetune/datasets/LICENSES.md` consolidated attribution file | P0 | BE/LEGAL | M5a | PENDING |
| 3 | Add `metadata.json` schema with required license/attribution fields | P0 | BE | M5a | PENDING |
| 4 | Implement `validate_datasets.py` license allowlist check | P0 | BE | M5a | PENDING |
| 5 | Add pre-commit hook to reject `client-assessment*.json` commits | P0 | INFRA | M6 | PENDING |
| 6 | Add CI PII pattern scanner | P0 | INFRA | M6 | PENDING |
| 7 | Draft privacy notice for client assessment intake | P1 | LEGAL | M4 | PENDING |
| 8 | Draft DPA template for Enterprise/Managed clients | P1 | LEGAL | M6 | PENDING |
| 9 | Flag high-risk AI use cases (04, 05, 12, 49) in adapter catalog | P1 | BE/LEGAL | M5a | PENDING |
| 10 | Verify Enron corpus PII redaction (use case 08) | P1 | BE | M5a | PENDING |
| 11 | Verify healthcare dataset de-identification (use cases 04, 49) | P1 | BE | M5a | PENDING |
| 12 | Verify Reddit data provenance (use case 46) | P1 | BE | M5a | PENDING |
| 13 | Add EU AI Act high-risk disclaimers to relevant adapter READMEs | P1 | LEGAL/BE | M5a | PENDING |
| 14 | Define data retention policy | P1 | LEGAL | M6 | PENDING |
| 15 | Add financial/legal/medical disclaimers to relevant adapters | P1 | LEGAL/BE | M5a | PENDING |

---

## 10. Review Schedule

| Event | Trigger | Reviewer |
|-------|---------|----------|
| Initial review | This document (M0) | LEGAL |
| Dataset license audit | Each dataset committed (M5a) | BE + LEGAL |
| Pre-release compliance sign-off | M6 | LEGAL |
| Quarterly review | Every 3 months post-release | LEGAL |
| Incident-triggered review | PII breach, DMCA notice, or legal inquiry | LEGAL |

---

*Compliance Review v1.0 -- Claw Agents Provisioner -- Amenthyx AI Teams v3.0*
