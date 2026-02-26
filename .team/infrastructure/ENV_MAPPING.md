# Environment Variable Mapping

> Complete mapping from unified `.env` variable names to each agent's expected format.

---

## LLM Provider API Keys

| Unified Var | ZeroClaw (TOML) | NanoClaw (env) | PicoClaw (JSON) | OpenClaw (JSON5 + .env) |
|-------------|-----------------|----------------|-----------------|-------------------------|
| `ANTHROPIC_API_KEY` | `[llm] api_key` (when provider=anthropic) | `CLAUDE_API_KEY` + `ANTHROPIC_API_KEY` | `PICOCLAW_ANTHROPIC_KEY` + `model_list[].litellm_params.api_key` | `ANTHROPIC_API_KEY` in `~/.openclaw/.env` |
| `OPENAI_API_KEY` | `[llm] api_key` (when provider=openai) | `OPENAI_API_KEY` | `PICOCLAW_OPENAI_KEY` + `model_list[].litellm_params.api_key` | `OPENAI_API_KEY` in `~/.openclaw/.env` |
| `OPENROUTER_API_KEY` | `[llm] api_key` (when provider=openrouter) | `OPENROUTER_API_KEY` | `PICOCLAW_OPENROUTER_KEY` + `model_list[].litellm_params.api_key` | `OPENROUTER_API_KEY` in `~/.openclaw/.env` |
| `DEEPSEEK_API_KEY` | `[llm] api_key` (when provider=deepseek) | `DEEPSEEK_API_KEY` | `PICOCLAW_API_KEY` + `model_list[].litellm_params.api_key` | `DEEPSEEK_API_KEY` in `~/.openclaw/.env` |
| `GEMINI_API_KEY` | `[llm] api_key` (when provider=google) | N/A | `PICOCLAW_GEMINI_KEY` + `model_list[].litellm_params.api_key` | `GOOGLE_API_KEY` in `~/.openclaw/.env` |
| `GROQ_API_KEY` | `[llm] api_key` (when provider=groq) | N/A | `PICOCLAW_GROQ_KEY` + `model_list[].litellm_params.api_key` | `GROQ_API_KEY` in `~/.openclaw/.env` |
| `HUGGINGFACE_TOKEN` | N/A (used by fine-tuning pipeline) | N/A | N/A | N/A |

---

## Chat Channel Tokens

| Unified Var | ZeroClaw (TOML) | NanoClaw (env) | PicoClaw (JSON) | OpenClaw (JSON5 + .env) |
|-------------|-----------------|----------------|-----------------|-------------------------|
| `TELEGRAM_BOT_TOKEN` | `[channels.telegram] bot_token` | `TELEGRAM_TOKEN` | `channels[].bot_token` (type=telegram) | `TELEGRAM_BOT_TOKEN` in `~/.openclaw/.env` |
| `DISCORD_BOT_TOKEN` | `[channels.discord] bot_token` | `DISCORD_TOKEN` | `channels[].bot_token` (type=discord) | `DISCORD_BOT_TOKEN` in `~/.openclaw/.env` |
| `SLACK_BOT_TOKEN` | `[channels.slack] bot_token` | `SLACK_TOKEN` | `channels[].bot_token` (type=slack) | `SLACK_BOT_TOKEN` in `~/.openclaw/.env` |
| `SLACK_APP_TOKEN` | `[channels.slack] app_token` | `SLACK_APP_TOKEN` | N/A | `SLACK_APP_TOKEN` in `~/.openclaw/.env` |
| `WHATSAPP_SESSION_DATA` | N/A | `WA_SESSION` | N/A | Configured in channels block |
| `SIGNAL_PHONE_NUMBER` | N/A | `SIGNAL_PHONE_NUMBER` | N/A | N/A |

---

## Agent Selection

| Unified Var | ZeroClaw | NanoClaw | PicoClaw | OpenClaw |
|-------------|----------|----------|----------|----------|
| `CLAW_AGENT` | N/A (selects which entrypoint runs) | N/A | N/A | N/A |
| `CLAW_LLM_PROVIDER` | `[llm] provider` | Determines which API key to export | `llm.provider` + `model_list[].litellm_params.model` prefix | `llm.provider` |
| `CLAW_LLM_MODEL` | `[llm] model` | sed-patched into source files | `llm.model` + `model_list[].model_name` | `llm.model` |

---

## Assessment-Derived Config

| Unified Var | ZeroClaw (TOML) | NanoClaw | PicoClaw (JSON) | OpenClaw (JSON5) |
|-------------|-----------------|----------|-----------------|------------------|
| `CLAW_CLIENT_NAME` | N/A | Context in CLAUDE.md | N/A | `clientName` |
| `CLAW_CLIENT_INDUSTRY` | `[agent] industry` | Context in CLAUDE.md | `agent.industry` + `agent.name` prefix | `agent.industry` |
| `CLAW_CLIENT_LANGUAGE` | `[agent] language` | Context in CLAUDE.md (if not `en`) | `agent.language` | `agent.language` |
| `CLAW_DATA_SENSITIVITY` | `[agent] data_sensitivity` | N/A | `agent.data_sensitivity` | `agent.dataSensitivity` |
| `CLAW_STORAGE_PREFERENCE` | N/A | N/A | N/A | N/A (future) |
| `CLAW_COMPLIANCE` | `[agent] compliance` (if not `none`) | N/A | `agent.compliance` | `agent.compliance` |
| `CLAW_SKILLS` | N/A (skills installed separately) | Context in CLAUDE.md | `agent.skills[]` | `agent.skills[]` + `skills[]` |

---

## Fine-Tuning Config

| Unified Var | ZeroClaw (TOML) | NanoClaw | PicoClaw (JSON) | OpenClaw (JSON5) |
|-------------|-----------------|----------|-----------------|------------------|
| `CLAW_FINETUNE_ENABLED` | Log warning if true but no adapter path | N/A | N/A | N/A |
| `CLAW_FINETUNE_METHOD` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_FINETUNE_BASE_MODEL` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_FINETUNE_RANK` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_FINETUNE_EPOCHS` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_FINETUNE_LEARNING_RATE` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_FINETUNE_BATCH_SIZE` | N/A (used by training pipeline) | N/A | N/A | N/A |
| `CLAW_ADAPTER_PATH` | `[adapter] path` | `NANOCLAW_SYSTEM_PROMPT` (from system_prompt.txt) | `model_list[]` (local-adapter entry) + `system_prompt` | `adapter.path` + `OPENCLAW_SYSTEM_PROMPT` |
| `CLAW_FINETUNE_USE_CASE` | System prompt from `finetune/adapters/<id>/` | Enriches CLAUDE.md | `system_prompt` field | `systemPrompt` field |
| `CLAW_SYSTEM_PROMPT_ENRICHMENT` | `[system_prompt] enriched` + `content` | Appends to CLAUDE.md | `system_prompt` field | `systemPrompt` field |

---

## Agent-Specific Overrides

### ZeroClaw

| Unified Var | Maps To |
|-------------|---------|
| `ZEROCLAW_VERSION` | Install script version selection |
| `ZEROCLAW_INSTALL_METHOD` | `binary` or `source` (install script) |
| `ZEROCLAW_EXTRA_TOML` | Appended verbatim to `config.toml` |
| `ZEROCLAW_LOG_LEVEL` | `[general] log_level` |

### NanoClaw

| Unified Var | Maps To |
|-------------|---------|
| `NANOCLAW_CHANNEL` | Determines which channel token to export |
| `NANOCLAW_SANDBOX_RUNTIME` | `docker` or `none` — patches source `useDocker`/`sandbox` |
| `NANOCLAW_MAX_MEMORY_MB` | Container memory limit |

### PicoClaw

| Unified Var | Maps To |
|-------------|---------|
| `PICOCLAW_VERSION` | Install script version selection |
| `PICOCLAW_GATEWAY_HOST` | `server.host` in config.json |
| `PICOCLAW_GATEWAY_PORT` | `server.port` in config.json |
| `PICOCLAW_LOG_LEVEL` | `log_level` in config.json |

### OpenClaw

| Unified Var | Maps To |
|-------------|---------|
| `OPENCLAW_VERSION` | Install script version selection |
| `OPENCLAW_DM_POLICY` | `dm.policy` in openclaw.json |
| `OPENCLAW_PORT` | `server.port` in openclaw.json |
| `OPENCLAW_LOG_LEVEL` | `server.logLevel` in openclaw.json |
| `OPENCLAW_EXTRA_JSON5` | Logged for manual merge (JSON5 merge not trivial in bash) |

---

## Provider ID Mapping

The unified `CLAW_LLM_PROVIDER` value is translated to agent-specific provider identifiers:

| `CLAW_LLM_PROVIDER` | ZeroClaw | NanoClaw | PicoClaw | OpenClaw |
|----------------------|----------|----------|----------|----------|
| `anthropic` | `anthropic` | N/A (uses env var) | `anthropic` | `anthropic` |
| `openai` | `openai` | N/A (uses env var) | `openai` | `openai` |
| `openrouter` | `openrouter` | N/A (uses env var) | `openrouter` | `openrouter` |
| `deepseek` | `deepseek` | N/A (uses env var) | `deepseek` | `deepseek` |
| `gemini` | `google` | N/A | `gemini` | `google` |
| `groq` | `groq` | N/A | `groq` | `groq` |

---

## Config File Locations

| Agent | Config Path | Format | Generated By |
|-------|-------------|--------|--------------|
| ZeroClaw | `~/.zeroclaw/config.toml` | TOML | `zeroclaw/entrypoint.sh` |
| NanoClaw | Source env + CLAUDE.md | Env vars + Markdown | `nanoclaw/entrypoint.sh` |
| PicoClaw | `~/.picoclaw/config.json` | JSON | `picoclaw/entrypoint.sh` |
| OpenClaw | `~/.openclaw/openclaw.json` + `~/.openclaw/.env` | JSON5 + env | `openclaw/entrypoint.sh` |

---

## Regeneration Behavior

All entrypoint scripts regenerate config files on every start. This means:

- Changes to `.env` take effect immediately on next container restart
- Manual edits to agent config files inside containers are lost on restart
- For persistent overrides, use `ZEROCLAW_EXTRA_TOML` or `OPENCLAW_EXTRA_JSON5`
- PicoClaw legacy: respects `CLAW_REGENERATE_CONFIG=true` for backwards compatibility
