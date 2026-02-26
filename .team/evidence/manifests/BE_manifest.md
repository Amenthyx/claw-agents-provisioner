# Backend Engineer (BE) — Evidence Manifest

> Claw Agents Provisioner — Milestone M4 (Assessment Pipeline) + M5a (Datasets & Adapters)

## Deliverables Summary

| # | Deliverable | Status | Files Created |
|---|------------|--------|--------------|
| 1 | Assessment JSON Schema | COMPLETE | `assessment/schema/assessment-schema.json` |
| 2 | Assessment Validator | COMPLETE | `assessment/validate.py` |
| 3 | Assessment Resolver | COMPLETE | `assessment/resolve.py` |
| 4 | .env Generator | COMPLETE | `assessment/generate_env.py` |
| 5 | Config Generator | COMPLETE | `assessment/generate_config.py` |
| 6 | Example Assessment | COMPLETE | `assessment/client-assessment.example.json` |
| 7 | Needs Mapping Matrix | COMPLETE | `assessment/needs-mapping-matrix.json` |
| 8 | Fine-tune Requirements | COMPLETE | `finetune/requirements.txt` |
| 9 | Dataset Generator | COMPLETE | `finetune/dataset_generator.py` |
| 10 | LoRA Training Script | COMPLETE | `finetune/train_lora.py` |
| 11 | QLoRA Training Script | COMPLETE | `finetune/train_qlora.py` |
| 12 | Adapter Merger | COMPLETE | `finetune/merge_adapter.py` |
| 13 | Dataset Downloader | COMPLETE | `finetune/download_datasets.py` |
| 14 | Dataset Validator | COMPLETE | `finetune/validate_datasets.py` |
| 15 | 50 Datasets (seed) | COMPLETE | `finetune/datasets/01-..50-*/data.jsonl + metadata.json` |
| 16 | 50 Adapter Configs | COMPLETE | `finetune/adapters/01-..50-*/adapter_config.json + system_prompt.txt + training_config.json` |
| 17 | API Contracts Doc | COMPLETE | `.team/api-contracts/ASSESSMENT_PIPELINE.md` |
| 18 | Evidence Manifest | COMPLETE | `.team/evidence/manifests/BE_manifest.md` |

## File Counts

| Category | Count | Files per Directory |
|----------|-------|-------------------|
| Assessment pipeline | 7 files | schema, validate, resolve, generate_env, generate_config, example, matrix |
| Fine-tuning pipeline | 6 files | requirements, dataset_generator, train_lora, train_qlora, merge_adapter, download_datasets, validate_datasets |
| Dataset directories | 50 | metadata.json + data.jsonl (seed, 5 rows each) |
| Adapter directories | 50 | adapter_config.json + system_prompt.txt + training_config.json |
| Documentation | 2 files | ASSESSMENT_PIPELINE.md, BE_manifest.md |
| **Total files created** | **~265** | |

## Assessment Pipeline Evidence

### Schema Validation
- JSON Schema v2020-12 with all 8 sections from strategy
- 25 industry enum values, 50 use case enum values
- All fields have type constraints, descriptions, and validation rules
- Optional `fine_tuning` section for LoRA/QLoRA preferences

### Resolver Algorithm
- 15 mappings in needs-mapping-matrix.json (9 from strategy + 6 additional)
- Weighted scoring across 8 factors (use case overlap, budget, complexity, sensitivity, channel, device, regulation, storage)
- Platform selection: NanoClaw for security, PicoClaw for edge, OpenClaw for integrations, ZeroClaw for efficiency
- LLM model selection: budget-first with complexity override
- Auto-enables fine-tuning for enterprise packages

### Config Generation
- ZeroClaw: TOML with model, persona, skills, security sections
- PicoClaw: JSON with model_list, channels, privacy sections
- OpenClaw: JSON5-compatible with channels, skills, adapter sections
- NanoClaw: CLAUDE.md system prompt + env-setup.sh patches
- All platforms get system_prompt.txt for API-only enrichment

### Example Assessment
- Lucia persona (real estate agency owner, Milan)
- Italian + English languages, WhatsApp primary channel
- GDPR compliance, EU data residency
- QLoRA fine-tuning with Mistral 7B base model
- Resolves to: OpenClaw + Claude Sonnet 4.6

## Fine-Tuning Pipeline Evidence

### Training Scripts
- `train_lora.py`: Full-precision LoRA with PEFT + Transformers, 24+ GB VRAM
- `train_qlora.py`: 4-bit NF4 quantized, 8-16 GB VRAM, paged_adamw_8bit optimizer
- Both support: CLI args, training_config.json override, --dry-run validation
- Both produce: adapter weights, tokenizer, training_metadata.json, TensorBoard logs

### Dataset Infrastructure
- `dataset_generator.py`: Assessment to JSONL dataset (system/user/assistant triples)
- `download_datasets.py`: Registry of 50 sources (HuggingFace + synthetic), max 10K rows
- `validate_datasets.py`: Validates all 50 directories, row counts, metadata schema, licenses
- All datasets use free/open licenses (Apache-2.0, MIT, CC-BY, CC0)

## 50 Use-Case Datasets

All 50 directories created under `finetune/datasets/`:
- Each has `metadata.json` with: use_case_id, name, source_url, license, rows, format, language, domain_tags, recommended_base_model, recommended_lora_rank
- Each has `data.jsonl` with 5 seed rows in chat format: `{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}`
- Seed data is realistic, domain-specific, and immediately usable for testing
- Full datasets (10K rows each) to be downloaded via `download_datasets.py`

## 50 Pre-Built Adapter Configs

All 50 directories created under `finetune/adapters/`:
- `adapter_config.json`: base model, LoRA rank (32 or 64), target modules, dataset path reference
- `system_prompt.txt`: Enriched system prompt for API-only models (Claude, GPT, DeepSeek)
- `training_config.json`: epochs, learning rate, batch size, VRAM estimate, warmup steps, output directory

## Code Quality

- All Python files have docstrings and type hints
- Consistent error handling with clear error messages
- CLI entry points with `argparse` or `sys.argv`
- Lazy imports for heavy ML libraries (torch, transformers)
- No hardcoded API keys or credentials
- Assessment JSONs gitignored (only example tracked)

## Dependencies on Other Team Members

| Dependency | From | Status |
|-----------|------|--------|
| `claw.sh` integration | DevOps (DO) | Pending — BE provides CLI entry points |
| Docker GPU support | DevOps (DO) | Pending — `Dockerfile.finetune` needs creation |
| Skills catalog mapping | DevOps (DO) | Pending — `skills-installer.sh` |
| CI pipeline integration | DevOps (DO) | Pending — pytest + ruff + validation |
