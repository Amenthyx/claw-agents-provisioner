#!/usr/bin/env python3
"""
Claw Agents Provisioner — .env Generator

Takes the resolver output and generates a populated .env file with all
assessment-derived configuration values.

The .env file follows the unified naming convention from .env.template,
and each agent's entrypoint.sh translates to the agent's expected format.

Usage:
    python generate_env.py <assessment-file> [--output <path>]
    python generate_env.py <assessment-file> --stdout
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Import the resolver
sys.path.insert(0, str(Path(__file__).parent))
from resolve import ResolutionResult, load_json, resolve_assessment


ENV_TEMPLATE = """\
# ===================================================================
# CLAW AGENTS PROVISIONER — GENERATED .env
# ===================================================================
# Auto-generated from client assessment on {generation_date}
# Assessment file: {assessment_file}
# ===================================================================
# IMPORTANT: This file contains sensitive configuration.
# DO NOT commit to version control.
# ===================================================================

# ===== LLM PROVIDER API KEYS (fill the ones you use) =====
# Provider selected by assessment: {llm_provider}
ANTHROPIC_API_KEY={anthropic_key}
OPENAI_API_KEY={openai_key}
OPENROUTER_API_KEY={openrouter_key}
DEEPSEEK_API_KEY={deepseek_key}
GEMINI_API_KEY=
GROQ_API_KEY=
HUGGINGFACE_TOKEN={hf_token}

# ===== CHAT CHANNEL TOKENS (fill the ones you use) =====
# Primary channel: {primary_channel}
TELEGRAM_BOT_TOKEN={telegram_token}
DISCORD_BOT_TOKEN={discord_token}
WHATSAPP_SESSION_DATA={whatsapp_session}
SLACK_BOT_TOKEN={slack_token}

# ===== AGENT SELECTION (auto-filled by assessment pipeline) =====
CLAW_AGENT={platform}
CLAW_LLM_PROVIDER={llm_provider}
CLAW_LLM_MODEL={llm_model}

# ===== ASSESSMENT-DERIVED CONFIG =====
CLAW_CLIENT_INDUSTRY={industry}
CLAW_CLIENT_LANGUAGE={language}
CLAW_DATA_SENSITIVITY={sensitivity}
CLAW_STORAGE_PREFERENCE={storage}
CLAW_COMPLIANCE={compliance}
CLAW_SKILLS={skills}

# ===== FINE-TUNING CONFIG =====
CLAW_FINETUNE_ENABLED={ft_enabled}
CLAW_FINETUNE_METHOD={ft_method}
CLAW_FINETUNE_BASE_MODEL={ft_base_model}
CLAW_FINETUNE_RANK={ft_rank}
CLAW_FINETUNE_EPOCHS=3
CLAW_ADAPTER_PATH={adapter_path}
CLAW_SYSTEM_PROMPT_ENRICHMENT={prompt_enrichment}

# ===== AGENT-SPECIFIC OVERRIDES =====
# ZeroClaw
ZEROCLAW_VERSION=latest
ZEROCLAW_EXTRA_TOML=

# NanoClaw
NANOCLAW_CHANNEL={nanoclaw_channel}

# PicoClaw
PICOCLAW_VERSION=latest
PICOCLAW_GATEWAY_HOST=0.0.0.0

# OpenClaw
OPENCLAW_VERSION=latest
OPENCLAW_DM_POLICY=pairing
"""


def generate_env(
    assessment: dict[str, Any],
    result: ResolutionResult,
    assessment_file: str,
) -> str:
    """
    Generate a populated .env file from assessment and resolution.

    Args:
        assessment: Parsed client-assessment.json.
        result: Resolution result from resolve.py.
        assessment_file: Original assessment filename (for comments).

    Returns:
        String content of the .env file.
    """
    # Determine which API key placeholder to highlight
    api_key_placeholders = {
        "anthropic_key": "sk-ant-YOUR_KEY_HERE" if result.llm_provider == "anthropic" else "",
        "openai_key": "sk-YOUR_KEY_HERE" if result.llm_provider == "openai" else "",
        "openrouter_key": "sk-or-YOUR_KEY_HERE" if result.llm_provider == "openrouter" else "",
        "deepseek_key": "sk-YOUR_KEY_HERE" if result.llm_provider == "deepseek" else "",
    }

    # Determine channel tokens to highlight
    primary_channel = assessment.get("channels", {}).get("primary_channel", "cli")
    channel_placeholders = {
        "telegram_token": "YOUR_BOT_TOKEN_HERE" if primary_channel == "telegram" else "",
        "discord_token": "YOUR_BOT_TOKEN_HERE" if primary_channel == "discord" else "",
        "whatsapp_session": "YOUR_SESSION_DATA_HERE" if primary_channel == "whatsapp" else "",
        "slack_token": "xoxb-YOUR_TOKEN_HERE" if primary_channel == "slack" else "",
    }

    # Fine-tuning config
    ft_base_model = result.base_model or ""
    adapter_path = ""
    if result.recommended_adapter:
        adapter_path = f"finetune/adapters/{result.recommended_adapter}/"

    # Prompt enrichment is for API-only models
    prompt_enrichment = "true" if result.llm_provider in ("anthropic", "openai", "openrouter") else "false"

    # NanoClaw channel mapping
    nanoclaw_channel = primary_channel if primary_channel in (
        "telegram", "discord", "whatsapp", "slack"
    ) else "telegram"

    # HuggingFace token
    hf_token = "hf_YOUR_TOKEN_HERE" if result.fine_tuning_enabled else ""

    env_content = ENV_TEMPLATE.format(
        generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        assessment_file=assessment_file,
        llm_provider=result.llm_provider,
        platform=result.platform,
        llm_model=result.llm_model,
        industry=result.client_industry,
        language=result.client_language,
        sensitivity=result.data_sensitivity,
        storage=result.storage_preference,
        compliance=",".join(result.compliance_flags) if result.compliance_flags else "none",
        skills=",".join(result.skills),
        ft_enabled=str(result.fine_tuning_enabled).lower(),
        ft_method=result.fine_tuning_method,
        ft_base_model=ft_base_model,
        ft_rank=result.lora_rank,
        adapter_path=adapter_path,
        prompt_enrichment=prompt_enrichment,
        primary_channel=primary_channel,
        nanoclaw_channel=nanoclaw_channel,
        hf_token=hf_token,
        **api_key_placeholders,
        **channel_placeholders,
    )

    return env_content


def main() -> int:
    """CLI entry point for .env generation."""
    if len(sys.argv) < 2:
        print("Usage: python generate_env.py <assessment-file> [--output <path>] [--stdout]")
        return 1

    assessment_path = Path(sys.argv[1])
    output_path = None
    to_stdout = "--stdout" in sys.argv

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])

    try:
        assessment = load_json(assessment_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        return 1

    result = resolve_assessment(assessment)
    env_content = generate_env(assessment, result, assessment_path.name)

    if to_stdout:
        print(env_content)
    else:
        if output_path is None:
            output_path = Path(__file__).parent.parent / ".env"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(env_content)

        print(f"Generated .env at: {output_path}")
        print(f"  Platform:  {result.platform}")
        print(f"  Model:     {result.llm_model}")
        print(f"  Skills:    {', '.join(result.skills)}")
        print()
        print("NEXT STEPS:")
        print(f"  1. Edit {output_path} and fill in your API key(s)")
        print(f"  2. Fill in your {result.llm_provider.upper()} API key")
        if assessment.get("channels", {}).get("primary_channel") not in ("cli", "api-only"):
            channel = assessment["channels"]["primary_channel"]
            print(f"  3. Fill in your {channel.upper()} bot token")

    return 0


if __name__ == "__main__":
    sys.exit(main())
