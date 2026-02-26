# Infrastructure Engineer (INFRA) — Evidence Manifest

> Deliverables produced by the Infrastructure Engineer for the Claw Agents Provisioner project.

---

## Role

Infrastructure Engineer (INFRA) — Full-Stack Team, Amenthyx AI Teams v3.0

## Scope

Design the unified configuration architecture, env variable mapping, provisioning base scripts, and entrypoint translation layer that all agents share.

---

## Deliverables

### 1. Unified Environment Template

| Field | Value |
|-------|-------|
| File | `.env.template` |
| Status | Complete |
| Description | Complete unified env template with ALL sections: LLM Provider API Keys (7 providers), Chat Channel Tokens (6 channels), Agent Selection, Assessment-Derived Config (7 fields), Fine-Tuning Config (10 fields), Agent-Specific Overrides (ZeroClaw: 4, NanoClaw: 3, PicoClaw: 4, OpenClaw: 5) |
| Verification | Contains only placeholder values (e.g., `sk-ant-REPLACE_ME`). No real keys. |

### 2. Base Provisioning Script

| Field | Value |
|-------|-------|
| File | `shared/provision-base.sh` |
| Status | Complete |
| Description | Idempotent Ubuntu 24.04 provisioning script. Installs: curl, git, jq, build-essential, Python 3.11+, pip, Docker CE, Docker Compose plugin. Configures Docker group permissions. |
| Verification | `sudo ./shared/provision-base.sh` on fresh Ubuntu 24.04 completes without errors. Running twice produces same result. |

### 3. Unified Health Check Script

| Field | Value |
|-------|-------|
| File | `shared/healthcheck.sh` |
| Status | Complete |
| Description | Accepts agent name as argument. Runs agent-specific health check: ZeroClaw (`zeroclaw doctor`), NanoClaw (container status), PicoClaw (`picoclaw agent -m ping`), OpenClaw (`openclaw doctor`). Outputs structured JSON pass/fail. Supports `all` for checking all agents. |
| Verification | `./shared/healthcheck.sh zeroclaw` returns structured output with pass/fail status. |

### 4. ZeroClaw Entrypoint

| Field | Value |
|-------|-------|
| File | `zeroclaw/entrypoint.sh` |
| Status | Complete |
| Description | Translates unified .env vars to ZeroClaw TOML config (`~/.zeroclaw/config.toml`). Handles: LLM provider mapping (6 providers), channel config (Telegram, Discord, Slack), assessment fields, adapter loading, system prompt enrichment, extra TOML append. |
| Verification | Set `CLAW_LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=test` and run; verify `config.toml` is generated correctly. |

### 5. NanoClaw Entrypoint

| Field | Value |
|-------|-------|
| File | `nanoclaw/entrypoint.sh` |
| Status | Complete |
| Description | Translates unified .env vars for NanoClaw's code-driven approach. Exports translated env var names (`CLAUDE_API_KEY`, `TELEGRAM_TOKEN`, etc.). Patches source files with sed to replace model references. Injects system prompt enrichment into `CLAUDE.md`. Handles 5 channels (Telegram, Discord, WhatsApp, Slack, Signal). |
| Verification | Verify env var exports and CLAUDE.md enrichment after running with test vars. |

### 6. PicoClaw Entrypoint

| Field | Value |
|-------|-------|
| File | `picoclaw/entrypoint.sh` |
| Status | Complete |
| Description | Translates unified .env vars to PicoClaw JSON config (`~/.picoclaw/config.json`). Generates full config with: server (host/port), LLM provider, model_list (with optional local adapter endpoint), channels array, agent metadata, skills array, system prompt enrichment. |
| Verification | Set env vars and run; verify `config.json` is valid JSON with correct mappings. |

### 7. OpenClaw Entrypoint

| Field | Value |
|-------|-------|
| File | `openclaw/entrypoint.sh` |
| Status | Complete |
| Description | Translates unified .env vars to OpenClaw JSON5 config (`~/.openclaw/openclaw.json`) and native env file (`~/.openclaw/.env`). Dual output format. Handles: multi-provider keys, 4 channel types, DM policy, assessment fields, adapter config, system prompt enrichment. Supports multiple fallback start methods (openclaw binary, pnpm, npm, npx). |
| Verification | Set env vars and run; verify both `openclaw.json` and `.env` are generated correctly. |

### 8. Architecture Documentation

| Field | Value |
|-------|-------|
| File | `.team/infrastructure/ARCHITECTURE.md` |
| Status | Complete |
| Description | Documents the complete configuration flow: .env -> entrypoint -> agent config. Covers all 4 agents, assessment pipeline integration, fine-tuning integration, security considerations. |

### 9. Environment Variable Mapping Documentation

| Field | Value |
|-------|-------|
| File | `.team/infrastructure/ENV_MAPPING.md` |
| Status | Complete |
| Description | Complete mapping tables: unified var name to ZeroClaw/NanoClaw/PicoClaw/OpenClaw equivalents. Covers all 7 sections: LLM keys, channel tokens, agent selection, assessment config, fine-tuning config, agent-specific overrides, provider ID mapping. |

---

## Script Quality Checklist

| Criterion | Status |
|-----------|--------|
| All `.sh` files have `#!/usr/bin/env bash` shebang | Pass |
| All scripts use `set -euo pipefail` | Pass |
| All scripts have section comments | Pass |
| Missing optional vars handled gracefully (defaults) | Pass |
| Missing required vars (API key) fail with clear error | Pass |
| No hardcoded secrets or real API keys | Pass |
| Idempotent (safe to run multiple times) | Pass |
| Structured log output with colored prefixes | Pass |

---

## File Inventory

| # | File Path | Type | Lines |
|---|-----------|------|-------|
| 1 | `.env.template` | Config template | ~170 |
| 2 | `shared/provision-base.sh` | Bash script | ~180 |
| 3 | `shared/healthcheck.sh` | Bash script | ~220 |
| 4 | `zeroclaw/entrypoint.sh` | Bash script | ~210 |
| 5 | `nanoclaw/entrypoint.sh` | Bash script | ~240 |
| 6 | `picoclaw/entrypoint.sh` | Bash script | ~250 |
| 7 | `openclaw/entrypoint.sh` | Bash script | ~270 |
| 8 | `.team/infrastructure/ARCHITECTURE.md` | Documentation | ~170 |
| 9 | `.team/infrastructure/ENV_MAPPING.md` | Documentation | ~140 |
| 10 | `.team/evidence/manifests/INFRA_manifest.md` | Evidence manifest | This file |

---

## Dependencies on Other Roles

| Dependency | From Role | Status |
|------------|-----------|--------|
| Dockerfiles that use entrypoint.sh as CMD | DevOps Engineer | Pending |
| Install scripts referenced in entrypoints | DevOps Engineer | Pending |
| Assessment pipeline that populates .env | Backend Engineer | Pending |
| Fine-tuning adapter configs (system_prompt.txt) | ML Engineer | Pending |
| Skills installer (CLAW_SKILLS handling) | Backend Engineer | Pending |

---

## Notes

- NanoClaw is the hardest to automate due to its code-driven config approach. The entrypoint uses env var exports + sed source patching + CLAUDE.md injection as a workaround.
- All entrypoint scripts regenerate config on every start. This is intentional -- the `.env` is the single source of truth.
- The `CLAW_REGENERATE_CONFIG` flag from the original PicoClaw stub is preserved for backwards compatibility but is effectively always true in the new implementation.
- Provider ID mapping differs between agents (e.g., `gemini` in unified -> `google` in ZeroClaw/OpenClaw). The mapping table in ENV_MAPPING.md documents all variations.
