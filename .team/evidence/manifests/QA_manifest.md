# QA Engineer — Evidence Manifest

> Claw Agents Provisioner — Wave 3 (Quality Assurance)

## QA Audit Summary

| Category | Tested | Passed | Issues Found | Issues Fixed |
|----------|--------|--------|-------------|-------------|
| Python syntax (11 scripts) | 11 | 11 | 0 | 0 |
| Shell syntax (5 scripts) | 5 | 5 | 0 after fixes | 5 |
| Assessment pipeline E2E | 4 stages | 4 | 0 | 0 |
| Dataset validation (50) | 50 | 50 | 1 (license string) | 1 |
| Config directory existence | 4 agents | 4 | 4 missing | 4 created |
| Security (eval injection) | 1 | 1 | 1 | 1 |
| **Total** | **75** | **75** | **11** | **11** |

## Issues Found and Fixed

### CRITICAL (5 fixed)

| # | Issue | File | Fix Applied |
|---|-------|------|-------------|
| 1 | ZeroClaw TOML escaping broken | `zeroclaw/entrypoint.sh:236` | Replaced broken sed chain with working `sed 's/$/\\n/' | tr -d '\n'` |
| 2 | PicoClaw config not validated | `picoclaw/entrypoint.sh:265` | Added JSON validation after generation |
| 3 | OpenClaw exec fallback undefined | `openclaw/entrypoint.sh:337` | Consolidated into `start_openclaw()` function with clear error |
| 4 | NanoClaw sed patches unverified | `nanoclaw/entrypoint.sh:187` | Added grep verification after patching |
| 5 | NanoClaw CLAUDE.md logic error | `nanoclaw/entrypoint.sh:255` | Extended condition to check individual env vars |

### HIGH (6 fixed)

| # | Issue | File | Fix Applied |
|---|-------|------|-------------|
| 6 | Missing config/ directories | All 4 agents | Created placeholder configs for Docker COPY |
| 7 | resolve.py empty mappings crash | `assessment/resolve.py:240` | Added early exit if mappings array empty |
| 8 | claw.sh eval injection risk | `claw.sh:266` | Replaced `eval` with safe JSON parsing via `--json` flag |
| 9 | claw.sh silent script failures | `claw.sh:254` | Added mandatory script existence check |
| 10 | generate_config.py silent on unknown platform | `assessment/generate_config.py:335` | Added warning for unknown platforms |
| 11 | Dataset 35 license validation | `finetune/datasets/35-*/metadata.json` | Fixed `Public-Domain` to `Public Domain` |

## Validation Results

### Python Scripts (11/11 pass)

```
validate.py: OK
resolve.py: OK
generate_env.py: OK
generate_config.py: OK
dataset_generator.py: OK
train_lora.py: OK
train_qlora.py: OK
merge_adapter.py: OK
download_datasets.py: OK
validate_datasets.py: OK
download_real_data.py: OK
```

### Shell Scripts (5/5 pass)

```
claw.sh: OK
zeroclaw/entrypoint.sh: OK
nanoclaw/entrypoint.sh: OK
picoclaw/entrypoint.sh: OK
openclaw/entrypoint.sh: OK
```

### Assessment Pipeline E2E

```
Input: assessment/client-assessment.example.json (Lucia, real estate)
Step 1 - validate.py: PASS
Step 2 - resolve.py: platform=openclaw, model=claude-sonnet-4-6
Step 3 - generate_env.py: .env generated with all sections
Step 4 - generate_config.py: openclaw.json + system_prompt.txt generated
```

### Dataset Validation

```
50 passed, 0 failed, 250,000 total rows
ALL 50 DATASETS VALIDATED SUCCESSFULLY
```

## Files Modified

| File | Change |
|------|--------|
| `zeroclaw/entrypoint.sh` | Fixed TOML escaping |
| `nanoclaw/entrypoint.sh` | Added sed verification, fixed CLAUDE.md logic, added binary checks |
| `picoclaw/entrypoint.sh` | Added JSON validation, improved startup logs |
| `openclaw/entrypoint.sh` | Consolidated exec fallbacks into function |
| `assessment/resolve.py` | Added empty mappings guard |
| `assessment/generate_config.py` | Added unknown platform warning |
| `claw.sh` | Replaced eval with JSON parsing, added script validation |
| `finetune/datasets/35-cybersecurity-threat-intel/metadata.json` | Fixed license string |

## Files Created

| File | Purpose |
|------|---------|
| `zeroclaw/config/config.toml` | Placeholder TOML config for Docker COPY |
| `nanoclaw/config/CLAUDE.md` | Placeholder system prompt for Docker COPY |
| `picoclaw/config/config.json` | Placeholder JSON config for Docker COPY |
| `openclaw/config/openclaw.json` | Placeholder JSON config for Docker COPY |
| `.team/evidence/manifests/QA_manifest.md` | This manifest |

## Known Remaining Issues (MEDIUM/LOW — accepted for v1.0)

| # | Issue | Severity | Rationale for Acceptance |
|---|-------|----------|-------------------------|
| 1 | Health check endpoints may not exist on agents | MEDIUM | Agents are upstream — health checks are best-effort |
| 2 | Vagrantfile synced_folder may not work on Windows | MEDIUM | Vagrant on Windows is edge case; Docker is primary |
| 3 | Colors not disabled in non-interactive shells | LOW | Cosmetic only |
| 4 | Date format non-portable (Linux only) | LOW | Entrypoints run in Linux containers |
| 5 | CI doesn't test actual deployment | LOW | Docker builds verify images; runtime test needs infrastructure |
