# Configuration Architecture

> How environment variables flow from `.env` through entrypoints to agent-specific configs.

---

## Overview

The Claw Agents Provisioner uses a **unified configuration layer** to abstract away the differences between four agents that each use a different config format. A single `.env` file is the only thing a user fills out; the entrypoint scripts handle all translation.

```
.env.template (reference)
       |
       | cp .env.template .env  (user fills in keys)
       |
       v
    .env (unified, all agents)
       |
       |  Loaded by Docker Compose / sourced by shell
       |
       +----> zeroclaw/entrypoint.sh ----> ~/.zeroclaw/config.toml     (TOML)
       |
       +----> nanoclaw/entrypoint.sh ----> env vars + source patches   (code-driven)
       |                              \--> CLAUDE.md enrichment
       |
       +----> picoclaw/entrypoint.sh ----> ~/.picoclaw/config.json     (JSON)
       |
       +----> openclaw/entrypoint.sh ----> ~/.openclaw/openclaw.json   (JSON5)
                                      \--> ~/.openclaw/.env
```

---

## Design Principles

1. **Single source of truth**: The `.env` file is the only file a user edits. Every agent reads from the same `.env`.

2. **Entrypoint as translator**: Each agent's `entrypoint.sh` is a pure translation layer. It reads unified env vars and produces the agent's native config format.

3. **Idempotent generation**: Config files are regenerated on every container start. This ensures the config always matches the `.env`. Persistent overrides are supported via `*_EXTRA_*` vars.

4. **Graceful degradation**: Missing optional env vars are handled with sensible defaults. Only the primary API key is mandatory.

5. **Assessment-driven**: The assessment pipeline (`./claw.sh deploy --assessment`) auto-populates `.env` from the client intake form — same vars, same flow.

---

## Configuration Flow (Detailed)

### Stage 1: User Configuration

The user copies `.env.template` to `.env` and fills in relevant sections:

```bash
cp .env.template .env
$EDITOR .env
```

The `.env` is organized into clearly labeled sections:

| Section | Purpose | Required? |
|---------|---------|-----------|
| LLM Provider API Keys | API keys for Anthropic, OpenAI, etc. | At least one |
| Chat Channel Tokens | Bot tokens for Telegram, Discord, etc. | At least one |
| Agent Selection | Which agent and LLM to use | Yes |
| Assessment-Derived Config | Industry, language, compliance, skills | Optional |
| Fine-Tuning Config | LoRA/QLoRA parameters | Optional |
| Agent-Specific Overrides | Per-agent settings | Optional |

### Stage 2: Environment Loading

The `.env` is loaded in one of two ways:

- **Docker Compose**: `env_file: .env` directive in `docker-compose.yml`
- **Native/Vagrant**: `source .env` or `set -a; source .env; set +a`

All variables become available as environment variables in the shell.

### Stage 3: Entrypoint Translation

Each agent's `entrypoint.sh` performs the following steps:

1. **Read unified vars** using `env_or_default()` helper (with fallbacks)
2. **Map provider** — translate `CLAW_LLM_PROVIDER` to agent-specific provider ID
3. **Map API key** — route `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / etc. to the agent's expected var name
4. **Map channels** — translate `TELEGRAM_BOT_TOKEN` to agent-specific channel config
5. **Generate config file** — write the agent's native format (TOML, JSON, JSON5)
6. **Apply enrichment** — inject system prompt from adapter configs if enabled
7. **Start agent** — `exec` the agent binary/runtime

### Stage 4: Agent Startup

The agent reads its native config file and starts. From the agent's perspective, it was configured normally — it does not know about the unified `.env`.

---

## Per-Agent Architecture

### ZeroClaw (Rust / TOML)

```
.env vars --> zeroclaw/entrypoint.sh --> ~/.zeroclaw/config.toml
```

- Config format: TOML with sections `[llm]`, `[channels.*]`, `[agent]`, `[adapter]`
- Credential resolution: ZeroClaw has its own fallback chain; we set the most specific key
- Extra config: `ZEROCLAW_EXTRA_TOML` is appended verbatim to config.toml
- Start command: `zeroclaw start`

### NanoClaw (TypeScript / Code-Driven)

```
.env vars --> nanoclaw/entrypoint.sh --> env var exports + sed patches + CLAUDE.md
```

- No config file: NanoClaw reads env vars directly and is configured via source code
- Translation: `ANTHROPIC_API_KEY` -> `CLAUDE_API_KEY` (NanoClaw's expected name)
- Source patching: `sed` replaces hardcoded model names in `.ts`/`.js` files
- System prompt: injected into `CLAUDE.md` (NanoClaw's agent instructions file)
- Start command: `pnpm run start` or `node src/index.js`

### PicoClaw (Go / JSON)

```
.env vars --> picoclaw/entrypoint.sh --> ~/.picoclaw/config.json
```

- Config format: JSON with `server`, `llm`, `model_list`, `channels`, `agent` objects
- Model list: supports multiple models including local adapter endpoints
- Gateway: configurable host/port via `PICOCLAW_GATEWAY_HOST/PORT`
- Start command: `picoclaw serve --config ~/.picoclaw/config.json`

### OpenClaw (TypeScript / JSON5)

```
.env vars --> openclaw/entrypoint.sh --> ~/.openclaw/openclaw.json + ~/.openclaw/.env
```

- Config format: JSON5 (supports comments, trailing commas)
- Dual output: both a JSON5 config file and a native `.env` file
- Multi-provider: OpenClaw supports multiple LLM providers simultaneously
- 13+ channels: each configured as a block in the channels section
- Start command: `openclaw start`

---

## Assessment Pipeline Integration

When the assessment pipeline runs (`./claw.sh deploy --assessment client.json`), it:

1. Reads the client intake form JSON
2. Runs `resolve.py` to determine platform, model, and skills
3. Runs `generate_env.py` to produce a populated `.env`
4. The same entrypoint flow then handles the rest

The assessment-derived fields in `.env` include:

```bash
CLAW_AGENT=openclaw              # From resolver
CLAW_LLM_PROVIDER=anthropic      # From resolver + budget
CLAW_LLM_MODEL=claude-sonnet-4-6 # From resolver
CLAW_CLIENT_INDUSTRY=real-estate  # From intake form
CLAW_CLIENT_LANGUAGE=en           # From intake form
CLAW_COMPLIANCE=gdpr              # From intake form
CLAW_SKILLS=whatsapp-business,lead-qualifier  # From resolver
```

---

## Fine-Tuning Integration

When fine-tuning is enabled (`CLAW_FINETUNE_ENABLED=true`):

1. The fine-tuning pipeline produces an adapter at `CLAW_ADAPTER_PATH`
2. For **local models** (Mistral, LLaMA, Phi): the adapter is loaded via a local model endpoint (vLLM/llama.cpp sidecar)
3. For **API models** (Claude, GPT, DeepSeek): the `system_prompt.txt` from the adapter config is injected into the agent's config

System prompt enrichment flow:

```
finetune/adapters/<use-case>/system_prompt.txt
       |
       v
entrypoint.sh reads CLAW_SYSTEM_PROMPT_ENRICHMENT=true
       |
       +-- ZeroClaw: [system_prompt] section in config.toml
       +-- NanoClaw: appended to CLAUDE.md
       +-- PicoClaw: "system_prompt" field in config.json
       +-- OpenClaw: "systemPrompt" field in openclaw.json
```

---

## Security Considerations

- `.env` is **never committed** to git (listed in `.gitignore`)
- `.env.template` contains **only placeholder values** (e.g., `sk-ant-REPLACE_ME`)
- Generated config files live inside containers or VMs — not in the repo
- API keys are written to agent config files with restricted permissions
- The entrypoint scripts fail fast if no API key is provided

---

## File Reference

| File | Purpose |
|------|---------|
| `.env.template` | Unified env template — copy to `.env` and fill |
| `shared/provision-base.sh` | Base Ubuntu 24.04 provisioning (apt, Docker, Python) |
| `shared/healthcheck.sh` | Unified health check — pass/fail for any agent |
| `zeroclaw/entrypoint.sh` | Env -> TOML translator + ZeroClaw starter |
| `nanoclaw/entrypoint.sh` | Env -> source patches + CLAUDE.md enrichment + NanoClaw starter |
| `picoclaw/entrypoint.sh` | Env -> JSON translator + PicoClaw starter |
| `openclaw/entrypoint.sh` | Env -> JSON5 + .env translator + OpenClaw starter |
