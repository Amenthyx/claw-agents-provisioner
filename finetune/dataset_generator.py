#!/usr/bin/env python3
"""
Claw Agents Provisioner — Fine-Tuning Dataset Generator

Generates a fine-tuning dataset from a client assessment and pre-existing
industry datasets. Outputs JSONL with system/user/assistant message triples.

The dataset is composed of:
    - Industry knowledge Q&A pairs from the pre-built dataset
    - Communication style examples from assessment preferences
    - Domain vocabulary definitions
    - Workflow patterns from use case selections
    - Persona definition examples

Usage:
    python dataset_generator.py <assessment-file> [--output <path>] [--max-rows <n>]
    python dataset_generator.py <assessment-file> --use-case 02-real-estate
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DATASETS_DIR = Path(__file__).parent / "datasets"
ADAPTERS_DIR = Path(__file__).parent / "adapters"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file (one JSON object per line)."""
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_system_prompt(assessment: dict[str, Any]) -> str:
    """
    Build a rich system prompt from the assessment for the training dataset.

    This prompt defines the agent's persona, industry context, and rules.
    """
    persona = assessment.get("communication_preferences", {})
    profile = assessment.get("client_profile", {})
    use_cases = assessment.get("use_cases", {})
    privacy = assessment.get("data_privacy", {})
    compliance = assessment.get("compliance", {})

    persona_name = persona.get("persona_name", "Claw Assistant")
    industry = profile.get("industry", "general")
    language = persona.get("primary_language", "en")
    tone = persona.get("tone", "professional")
    verbosity = persona.get("verbosity", "balanced")

    skills = use_cases.get("primary_use_cases", [])
    regulations = compliance.get("regulations", ["none"])

    prompt_parts = [
        f"You are {persona_name}, an AI assistant specialized in {industry}.",
        f"Your primary language is {language}.",
        f"Communicate in a {tone} tone with {verbosity} detail level.",
    ]

    if persona.get("persona_description"):
        prompt_parts.append(f"About you: {persona['persona_description']}")

    if skills:
        prompt_parts.append(f"Your capabilities include: {', '.join(skills)}.")

    if "none" not in regulations:
        prompt_parts.append(
            f"You must comply with: {', '.join(r.upper() for r in regulations if r != 'none')}."
        )

    sensitivity = privacy.get("sensitivity", "low")
    if sensitivity in ("high", "critical"):
        prompt_parts.append(
            "Handle all personal and sensitive data with extreme care. "
            "Never expose PII unnecessarily."
        )

    if persona.get("greeting_message"):
        prompt_parts.append(
            f"When greeting users, say: \"{persona['greeting_message']}\""
        )

    domain_req = use_cases.get("domain_specific_requirements")
    if domain_req:
        prompt_parts.append(f"Domain-specific requirements: {domain_req}")

    return " ".join(prompt_parts)


def generate_persona_examples(
    assessment: dict[str, Any], system_prompt: str
) -> list[dict[str, Any]]:
    """Generate training examples that establish the agent's persona."""
    persona = assessment.get("communication_preferences", {})
    persona_name = persona.get("persona_name", "Claw Assistant")
    industry = assessment.get("client_profile", {}).get("industry", "general")
    greeting = persona.get("greeting_message", f"Hello! I am {persona_name}.")

    examples = [
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hello, who are you?"},
                {
                    "role": "assistant",
                    "content": greeting,
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What can you help me with?"},
                {
                    "role": "assistant",
                    "content": (
                        f"I specialize in {industry}-related tasks. "
                        f"I can help you with: "
                        f"{', '.join(assessment.get('use_cases', {}).get('primary_use_cases', ['general assistance']))}."
                    ),
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What language do you speak?"},
                {
                    "role": "assistant",
                    "content": (
                        f"I primarily communicate in "
                        f"{persona.get('primary_language', 'English')}. "
                        f"I also support: "
                        f"{', '.join(persona.get('languages', ['en']))}."
                    ),
                },
            ]
        },
    ]

    return examples


def load_use_case_data(
    use_case_id: str, system_prompt: str, max_rows: int = 500
) -> list[dict[str, Any]]:
    """
    Load pre-existing dataset for a use case and wrap with the system prompt.

    Reads from finetune/datasets/<use_case_id>/data.jsonl.
    Each row is expected to have a "messages" field or raw Q&A fields.
    """
    dataset_dir = DATASETS_DIR / use_case_id
    data_path = dataset_dir / "data.jsonl"

    if not data_path.exists():
        return []

    raw_rows = load_jsonl(data_path)
    examples: list[dict[str, Any]] = []

    for row in raw_rows[:max_rows]:
        if "messages" in row:
            # Already in chat format — inject/replace system prompt
            messages = row["messages"]
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = system_prompt
            else:
                messages.insert(0, {"role": "system", "content": system_prompt})
            examples.append({"messages": messages})
        elif "instruction" in row and "response" in row:
            # Q&A format — convert to chat
            examples.append(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": row["instruction"]},
                        {"role": "assistant", "content": row["response"]},
                    ]
                }
            )
        elif "question" in row and "answer" in row:
            examples.append(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": row["question"]},
                        {"role": "assistant", "content": row["answer"]},
                    ]
                }
            )

    return examples


def generate_dataset(
    assessment: dict[str, Any],
    use_case_override: str | None = None,
    max_rows: int = 2000,
) -> list[dict[str, Any]]:
    """
    Generate a complete fine-tuning dataset from assessment.

    Args:
        assessment: Parsed client-assessment.json.
        use_case_override: If set, use this specific use case dataset instead
                          of deriving from assessment.
        max_rows: Maximum total rows in the output dataset.

    Returns:
        List of training examples in chat format.
    """
    system_prompt = build_system_prompt(assessment)
    all_examples: list[dict[str, Any]] = []

    # 1. Persona examples (always included)
    persona_examples = generate_persona_examples(assessment, system_prompt)
    all_examples.extend(persona_examples)

    # 2. Use-case specific data
    if use_case_override:
        use_cases_to_load = [use_case_override]
    else:
        # Map assessment use cases to dataset IDs
        use_case_map = {
            "customer-support": "01-customer-support",
            "real-estate": "02-real-estate",
            "e-commerce": "03-e-commerce",
            "healthcare": "04-healthcare",
            "legal": "05-legal",
            "personal-finance": "06-personal-finance",
            "code-review": "07-code-review",
            "email-management": "08-email-management",
            "calendar-scheduling": "09-calendar-scheduling",
            "meeting-summarization": "10-meeting-summarization",
            "sales-crm": "11-sales-crm",
            "hr-recruitment": "12-hr-recruitment",
            "it-helpdesk": "13-it-helpdesk",
            "content-writing": "14-content-writing",
            "social-media": "15-social-media",
            "translation-multilingual": "16-translation-multilingual",
            "education-tutoring": "17-education-tutoring",
            "research-summarization": "18-research-summarization",
            "data-analysis": "19-data-analysis",
            "project-management": "20-project-management",
            "accounting-bookkeeping": "21-accounting-bookkeeping",
            "insurance-claims": "22-insurance-claims",
            "travel-hospitality": "23-travel-hospitality",
            "food-restaurant": "24-food-restaurant",
            "fitness-wellness": "25-fitness-wellness",
            "automotive-vehicle": "26-automotive-vehicle",
            "supply-chain-logistics": "27-supply-chain-logistics",
            "manufacturing-qa": "28-manufacturing-qa",
            "agriculture-farming": "29-agriculture-farming",
            "energy-utilities": "30-energy-utilities",
            "telecommunications": "31-telecommunications",
            "government-public-services": "32-government-public-services",
            "nonprofit-fundraising": "33-nonprofit-fundraising",
            "event-planning": "34-event-planning",
            "cybersecurity-threat-intel": "35-cybersecurity-threat-intel",
            "devops-infrastructure": "36-devops-infrastructure",
            "api-integration-webhooks": "37-api-integration-webhooks",
            "database-administration": "38-database-administration",
            "iot-smart-home": "39-iot-smart-home",
            "chatbot-conversational": "40-chatbot-conversational",
            "document-processing": "41-document-processing",
            "knowledge-base-faq": "42-knowledge-base-faq",
            "compliance-regulatory": "43-compliance-regulatory",
            "onboarding-training": "44-onboarding-training",
            "sentiment-analysis": "45-sentiment-analysis",
            "creative-writing": "46-creative-writing",
            "music-entertainment": "47-music-entertainment",
            "gaming-virtual-worlds": "48-gaming-virtual-worlds",
            "mental-health-counseling": "49-mental-health-counseling",
            "personal-finance-budgeting": "50-personal-finance-budgeting",
        }

        primary_use_cases = assessment.get("use_cases", {}).get(
            "primary_use_cases", []
        )
        use_cases_to_load = [
            use_case_map[uc]
            for uc in primary_use_cases
            if uc in use_case_map
        ]

    # Distribute rows evenly across use cases
    rows_per_use_case = max(
        50, (max_rows - len(all_examples)) // max(len(use_cases_to_load), 1)
    )

    for uc_id in use_cases_to_load:
        uc_examples = load_use_case_data(uc_id, system_prompt, rows_per_use_case)
        all_examples.extend(uc_examples)

    # Truncate to max_rows
    return all_examples[:max_rows]


def save_jsonl(data: list[dict[str, Any]], path: Path) -> None:
    """Save a list of dicts as JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    """CLI entry point for dataset generation."""
    if len(sys.argv) < 2:
        print("Usage: python dataset_generator.py <assessment-file> [--output <path>] [--max-rows <n>] [--use-case <id>]")
        return 1

    assessment_path = Path(sys.argv[1])
    output_path = Path("finetune/output/training_data.jsonl")
    max_rows = 2000
    use_case_override = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])

    if "--max-rows" in sys.argv:
        idx = sys.argv.index("--max-rows")
        if idx + 1 < len(sys.argv):
            max_rows = int(sys.argv[idx + 1])

    if "--use-case" in sys.argv:
        idx = sys.argv.index("--use-case")
        if idx + 1 < len(sys.argv):
            use_case_override = sys.argv[idx + 1]

    try:
        assessment = load_json(assessment_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        return 1

    dataset = generate_dataset(assessment, use_case_override, max_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_jsonl(dataset, output_path)

    print(f"Generated {len(dataset)} training examples")
    print(f"Output: {output_path}")
    print(f"Format: JSONL (system/user/assistant message triples)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
