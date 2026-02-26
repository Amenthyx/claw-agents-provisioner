#!/usr/bin/env python3
"""
Claw Agents Provisioner — Agent Config Generator

Takes the resolver output and generates agent-specific configuration files:
    - ZeroClaw:  config.toml (TOML format)
    - NanoClaw:  source patches via envsubst-ready templates
    - PicoClaw:  config.json (JSON format)
    - OpenClaw:  openclaw.json (JSON5/JSON format)

Usage:
    python generate_config.py <assessment-file> [--output-dir <dir>]
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from resolve import ResolutionResult, load_json, resolve_assessment


def generate_zeroclaw_config(
    assessment: dict[str, Any], result: ResolutionResult
) -> str:
    """Generate ZeroClaw config.toml."""
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")
    tone = persona.get("tone", "professional")
    language = result.client_language

    # Map provider to ZeroClaw model config format
    provider_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "deepseek": "openai-compatible",
        "openrouter": "openrouter",
    }

    model_provider = provider_map.get(result.llm_provider, "anthropic")

    adapter_section = ""
    if result.fine_tuning_enabled and result.recommended_adapter:
        adapter_section = f"""
# ===== FINE-TUNING ADAPTER =====
[adapter]
path = "finetune/adapters/{result.recommended_adapter}/"
enabled = true
method = "{result.fine_tuning_method}"
"""

    compliance_section = ""
    if result.compliance_flags:
        flags = result.compliance_flags
        compliance_section = f"""
# ===== COMPLIANCE =====
[security]
encrypt_config = {"true" if "encryption" in flags else "false"}
audit_logging = {"true" if "audit-logging" in flags else "false"}
container_isolation = {"true" if "container-isolation" in flags else "false"}
"""

    config = f"""\
# ===================================================================
# ZeroClaw Configuration — Auto-generated from client assessment
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Industry: {result.client_industry}
# ===================================================================

[model]
provider = "{model_provider}"
model = "{result.llm_model}"
# API key is read from environment: ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.

[persona]
name = "{persona_name}"
tone = "{tone}"
language = "{language}"
greeting = "{persona.get("greeting_message", f"Hello! I am {persona_name}, your AI assistant.")}"

[skills]
enabled = [{', '.join(f'"{s}"' for s in result.skills)}]

[storage]
preference = "{result.storage_preference}"
sensitivity = "{result.data_sensitivity}"
{adapter_section}{compliance_section}"""

    return config


def generate_picoclaw_config(
    assessment: dict[str, Any], result: ResolutionResult
) -> str:
    """Generate PicoClaw config.json."""
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")
    channels = assessment.get("channels", {})
    primary_channel = channels.get("primary_channel", "cli")

    config = {
        "$schema": "https://picoclaw.dev/config-schema.json",
        "_comment": f"Auto-generated from client assessment on {datetime.now().strftime('%Y-%m-%d')}",
        "agent": {
            "name": persona_name,
            "language": result.client_language,
            "industry": result.client_industry,
        },
        "model": {
            "provider": result.llm_provider,
            "model": result.llm_model,
        },
        "model_list": [
            {
                "model_name": result.llm_model,
                "litellm_params": {
                    "model": f"{result.llm_provider}/{result.llm_model}",
                },
            }
        ],
        "channels": {
            "primary": primary_channel,
        },
        "skills": result.skills,
        "privacy": {
            "sensitivity": result.data_sensitivity,
            "storage": result.storage_preference,
        },
    }

    # Add adapter config if fine-tuning enabled
    if result.fine_tuning_enabled and result.recommended_adapter:
        config["adapter"] = {
            "enabled": True,
            "path": f"finetune/adapters/{result.recommended_adapter}/",
            "method": result.fine_tuning_method,
        }

    return json.dumps(config, indent=2)


def generate_openclaw_config(
    assessment: dict[str, Any], result: ResolutionResult
) -> str:
    """Generate OpenClaw openclaw.json (JSON5-compatible JSON)."""
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")
    channels = assessment.get("channels", {})
    primary_channel = channels.get("primary_channel", "cli")

    # Build channel configs
    channel_config: dict[str, Any] = {}
    if primary_channel == "telegram":
        channel_config["telegram"] = {
            "enabled": True,
            "bot_name": channels.get("channel_specific_config", {})
            .get("telegram", {})
            .get("bot_name", persona_name),
        }
    elif primary_channel == "whatsapp":
        channel_config["whatsapp"] = {
            "enabled": True,
            "business_account": channels.get("channel_specific_config", {})
            .get("whatsapp", {})
            .get("business_account", False),
        }
    elif primary_channel == "discord":
        channel_config["discord"] = {
            "enabled": True,
            "server_id": channels.get("channel_specific_config", {})
            .get("discord", {})
            .get("server_id", ""),
        }
    elif primary_channel == "slack":
        channel_config["slack"] = {
            "enabled": True,
            "workspace": channels.get("channel_specific_config", {})
            .get("slack", {})
            .get("workspace_name", ""),
        }

    config = {
        "$schema": "https://docs.openclaw.ai/schema/config.json",
        "_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent": {
            "name": persona_name,
            "description": persona.get(
                "persona_description",
                f"AI assistant specialized in {result.client_industry}",
            ),
            "language": result.client_language,
            "tone": persona.get("tone", "professional"),
            "verbosity": persona.get("verbosity", "balanced"),
        },
        "model": {
            "provider": result.llm_provider,
            "name": result.llm_model,
        },
        "channels": channel_config,
        "skills": {skill: {"enabled": True} for skill in result.skills},
        "dm_policy": "pairing",
        "privacy": {
            "sensitivity": result.data_sensitivity,
            "storage": result.storage_preference,
            "compliance": result.compliance_flags,
        },
    }

    if result.fine_tuning_enabled and result.recommended_adapter:
        config["adapter"] = {
            "enabled": True,
            "path": f"finetune/adapters/{result.recommended_adapter}/",
            "method": result.fine_tuning_method,
        }

    return json.dumps(config, indent=2)


def generate_nanoclaw_patches(
    assessment: dict[str, Any], result: ResolutionResult
) -> dict[str, str]:
    """
    Generate NanoClaw source patches.

    NanoClaw has no config file — it's configured by modifying source code.
    We generate envsubst-ready template patches and a CLAUDE.md system prompt.

    Returns:
        Dict mapping filename to content.
    """
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")
    channels = assessment.get("channels", {})
    primary_channel = channels.get("primary_channel", "telegram")

    # CLAUDE.md — system prompt for NanoClaw's Claude Code agent
    system_prompt = f"""\
# {persona_name} — NanoClaw Agent Configuration

## Identity
You are {persona_name}, an AI assistant specialized in {result.client_industry}.
Your primary language is {result.client_language}.
Your tone is {persona.get("tone", "professional")}.

## Skills
You have the following capabilities enabled:
{chr(10).join(f"- {skill}" for skill in result.skills)}

## Communication Style
- Tone: {persona.get("tone", "professional")}
- Verbosity: {persona.get("verbosity", "balanced")}
- Greeting: {persona.get("greeting_message", f"Hello! I am {persona_name}.")}

## Compliance
{chr(10).join(f"- {flag}" for flag in result.compliance_flags) if result.compliance_flags else "- No special compliance requirements"}

## Data Handling
- Sensitivity: {result.data_sensitivity}
- Storage: {result.storage_preference}
"""

    # Environment setup script
    env_setup = f"""\
#!/bin/bash
# NanoClaw environment setup — auto-generated from assessment
# This script patches the NanoClaw source with assessment-derived values.

export NANOCLAW_CHANNEL="{primary_channel}"
export NANOCLAW_LLM_PROVIDER="{result.llm_provider}"
export NANOCLAW_LLM_MODEL="{result.llm_model}"
export NANOCLAW_PERSONA_NAME="{persona_name}"
export NANOCLAW_LANGUAGE="{result.client_language}"
export NANOCLAW_INDUSTRY="{result.client_industry}"
export NANOCLAW_SKILLS="{",".join(result.skills)}"

echo "NanoClaw environment configured for {result.client_industry} ({primary_channel})"
"""

    return {
        "CLAUDE.md": system_prompt,
        "env-setup.sh": env_setup,
    }


def generate_configs(
    assessment: dict[str, Any],
    result: ResolutionResult,
    output_dir: Path,
) -> list[Path]:
    """
    Generate all config files for the resolved platform.

    Args:
        assessment: Parsed client-assessment.json.
        result: Resolution result from resolve.py.
        output_dir: Directory to write config files.

    Returns:
        List of generated file paths.
    """
    generated: list[Path] = []
    platform_dir = output_dir / result.platform / "config"
    platform_dir.mkdir(parents=True, exist_ok=True)

    if result.platform == "zeroclaw":
        config_path = platform_dir / "config.toml"
        config_path.write_text(
            generate_zeroclaw_config(assessment, result), encoding="utf-8"
        )
        generated.append(config_path)

    elif result.platform == "picoclaw":
        config_path = platform_dir / "config.json"
        config_path.write_text(
            generate_picoclaw_config(assessment, result), encoding="utf-8"
        )
        generated.append(config_path)

    elif result.platform == "openclaw":
        config_path = platform_dir / "openclaw.json"
        config_path.write_text(
            generate_openclaw_config(assessment, result), encoding="utf-8"
        )
        generated.append(config_path)

    elif result.platform == "nanoclaw":
        patches = generate_nanoclaw_patches(assessment, result)
        for filename, content in patches.items():
            file_path = platform_dir / filename
            file_path.write_text(content, encoding="utf-8")
            generated.append(file_path)

    else:
        print(
            f"WARNING: Unknown platform '{result.platform}'. "
            f"Expected one of: zeroclaw, nanoclaw, picoclaw, openclaw.",
            file=sys.stderr,
        )

    # Also generate system_prompt.txt for any platform (useful for API-only models)
    system_prompt_path = platform_dir / "system_prompt.txt"
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")

    system_prompt = (
        f"You are {persona_name}, an AI assistant specialized in "
        f"{result.client_industry}. "
        f"Your primary language is {result.client_language}. "
        f"Respond in a {persona.get('tone', 'professional')} tone. "
        f"Your capabilities include: {', '.join(result.skills)}."
    )
    if persona.get("greeting_message"):
        system_prompt += f"\nWhen greeting users, say: {persona['greeting_message']}"

    system_prompt_path.write_text(system_prompt, encoding="utf-8")
    generated.append(system_prompt_path)

    return generated


def main() -> int:
    """CLI entry point for config generation."""
    if len(sys.argv) < 2:
        print("Usage: python generate_config.py <assessment-file> [--output-dir <dir>]")
        return 1

    assessment_path = Path(sys.argv[1])
    output_dir = Path(__file__).parent.parent

    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])

    try:
        assessment = load_json(assessment_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        return 1

    result = resolve_assessment(assessment)
    generated = generate_configs(assessment, result, output_dir)

    print(f"Generated {len(generated)} config file(s) for {result.platform}:")
    for path in generated:
        print(f"  {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
