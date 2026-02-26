# Assessment Pipeline — API Contract Documentation

> Backend Engineer (BE) — Claw Agents Provisioner

## Overview

The assessment pipeline transforms a client intake form (JSON) into a fully configured, deployable AI agent. It consists of five sequential stages:

1. **Validate** — Schema check + completeness
2. **Resolve** — Match assessment to needs-mapping-matrix
3. **Generate .env** — Produce populated environment file
4. **Generate Config** — Produce agent-specific configuration
5. **[Optional] Fine-tune** — Generate dataset and train LoRA/QLoRA adapter

---

## 1. Assessment Schema (`assessment/schema/assessment-schema.json`)

### Input Format

The client assessment JSON follows this schema (v3.0) with 8 required sections:

| Section | Required Fields | Description |
|---------|----------------|-------------|
| `client_profile` | company_name, contact_name, industry, company_size, tech_savvy, primary_devices | Client identity and technical profile |
| `use_cases` | primary_use_cases | Selected use cases from 50 categories |
| `communication_preferences` | languages, tone | How the agent should communicate |
| `data_privacy` | sensitivity, storage_preference | Data sensitivity and storage rules |
| `performance_scale` | daily_requests, response_time_target | Expected load and performance |
| `budget` | monthly_api_budget | Monthly API spend tolerance |
| `channels` | primary_channel | Communication channels |
| `compliance` | regulations | Regulatory frameworks |

Optional section: `fine_tuning` (LoRA/QLoRA preferences).

### Example

See `assessment/client-assessment.example.json` for a complete example (Lucia persona, real estate).

---

## 2. Validator (`assessment/validate.py`)

### CLI

```bash
python assessment/validate.py <assessment-file>
python assessment/validate.py --schema-only
```

### Input
- Path to a client-assessment.json file

### Output
- Exit code 0: valid assessment
- Exit code 1: invalid assessment
- Prints categorized errors: `[MISSING]`, `[INVALID VALUE]`, `[WRONG TYPE]`, `[OUT OF RANGE]`, etc.
- Prints business-logic warnings (budget/complexity mismatch, compliance gaps)

### Dependencies
- `jsonschema` (optional, degrades to manual validation)
- `assessment/schema/assessment-schema.json`

---

## 3. Resolver (`assessment/resolve.py`)

### CLI

```bash
python assessment/resolve.py <assessment-file>
python assessment/resolve.py <assessment-file> --json
python assessment/resolve.py <assessment-file> --verbose
```

### Input
- Validated client-assessment.json

### Output — `ResolutionResult`

```json
{
  "platform": "openclaw",
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-6",
  "skills": ["whatsapp-business", "crm-sync", "auto-reply", "lead-qualifier"],
  "compliance_flags": [],
  "monthly_api_cost_estimate": [25, 50],
  "recommended_adapter": "02-real-estate",
  "fine_tuning_enabled": true,
  "fine_tuning_method": "qlora",
  "base_model": "mistralai/Mistral-7B-v0.3",
  "lora_rank": 32,
  "multi_agent": false,
  "secondary_platform": null,
  "client_industry": "real-estate",
  "client_language": "it",
  "data_sensitivity": "medium",
  "storage_preference": "private-cloud",
  "scoring_details": {}
}
```

### Algorithm — Weighted Scoring

For each of the 15 mappings in `needs-mapping-matrix.json`:

| Factor | Max Points | Weight |
|--------|-----------|--------|
| Use case overlap | 10 | Highest priority |
| Budget fit | 5 | Must be affordable |
| Complexity match | 4 | Task difficulty |
| Sensitivity match | 4 | Security requirements |
| Channel match | 3 | Communication channel |
| Device affinity | 3 | Hardware constraints |
| Regulation match | 3 | Compliance alignment |
| Storage preference | 2 | Data residency |

Each mapping has a `weight` multiplier (0.8 - 1.8). The highest-scoring mapping wins.

### Platform Selection Logic

| Condition | Platform |
|-----------|----------|
| High sensitivity + container isolation | NanoClaw (security 9/10) |
| Budget + edge hardware (RPi) | PicoClaw (8 MB RAM) |
| Maximum integrations + channels | OpenClaw (50+ integrations) |
| Efficiency + multi-provider + encryption | ZeroClaw (7.8 MB, encrypted) |

### LLM Model Selection Logic

| Condition | Model |
|-----------|-------|
| $0 budget | DeepSeek V3.2 |
| Expert complexity + $100+ budget | Claude Opus 4.6 |
| Maximum context needed + $50+ | GPT-4.1 (1M tokens) |
| $25+ budget (default best) | Claude Sonnet 4.6 |

---

## 4. Env Generator (`assessment/generate_env.py`)

### CLI

```bash
python assessment/generate_env.py <assessment-file>
python assessment/generate_env.py <assessment-file> --output .env
python assessment/generate_env.py <assessment-file> --stdout
```

### Input
- Validated client-assessment.json

### Output
- `.env` file with all assessment-derived values populated
- API key fields have `YOUR_KEY_HERE` placeholders for the selected provider
- Channel tokens highlighted for the primary channel
- Fine-tuning config pre-filled

---

## 5. Config Generator (`assessment/generate_config.py`)

### CLI

```bash
python assessment/generate_config.py <assessment-file>
python assessment/generate_config.py <assessment-file> --output-dir /path/to/output
```

### Input
- Validated client-assessment.json

### Output (per platform)

| Platform | Config File | Format |
|----------|------------|--------|
| ZeroClaw | `config.toml` | TOML |
| PicoClaw | `config.json` | JSON |
| OpenClaw | `openclaw.json` | JSON5/JSON |
| NanoClaw | `CLAUDE.md` + `env-setup.sh` | Markdown + Bash |

All platforms also get a `system_prompt.txt` for API-only model enrichment.

---

## 6. Needs Mapping Matrix (`assessment/needs-mapping-matrix.json`)

Contains 15 mappings covering all major deployment profiles:

| # | Mapping | Platform | Model |
|---|---------|----------|-------|
| 1 | Basic Personal Assistant | PicoClaw | DeepSeek |
| 2 | WhatsApp Business Bot | OpenClaw | Claude Sonnet |
| 3 | Secure Document Processing | NanoClaw | Claude Opus |
| 4 | Developer Workflow | NanoClaw | Claude Sonnet |
| 5 | Smart Home IoT | PicoClaw | DeepSeek |
| 6 | Marketing Content | OpenClaw | Claude Opus |
| 7 | Legal Document Review | NanoClaw | Claude Opus |
| 8 | Budget RPi Assistant | PicoClaw | DeepSeek |
| 9 | Multi-Agent Research | OpenClaw+NanoClaw | Claude Opus |
| 10 | Healthcare Triage | NanoClaw | Claude Opus |
| 11 | E-Commerce Assistant | OpenClaw | Claude Sonnet |
| 12 | HR Recruitment | OpenClaw | Claude Sonnet |
| 13 | Financial Advisor | ZeroClaw | Claude Sonnet |
| 14 | Education Tutoring | OpenClaw | GPT-4.1 |
| 15 | Cybersecurity SOC | ZeroClaw | Claude Opus |

---

## File Dependencies

```
assessment/
  schema/assessment-schema.json  <-- validate.py reads this
  needs-mapping-matrix.json      <-- resolve.py reads this
  validate.py                    <-- standalone
  resolve.py                     <-- standalone
  generate_env.py                <-- imports resolve.py
  generate_config.py             <-- imports resolve.py
  client-assessment.example.json <-- example input
```

## Error Handling

All scripts exit with code 0 on success, code 1 on failure.
All scripts print human-readable error messages to stdout.
`validate.py` distinguishes between errors (blocking) and warnings (advisory).
