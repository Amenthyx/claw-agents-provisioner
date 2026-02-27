#!/usr/bin/env python3
"""
Claw Agents Provisioner — Assessment Resolver

Reads a validated client-assessment.json, matches against the needs-mapping-matrix,
and outputs the optimal: platform, LLM model, skills list, and compliance flags.

Uses a weighted scoring algorithm per the strategy:
    1. Platform selection — security, integrations, resource efficiency, device affinity
    2. LLM model selection — budget, complexity, context needs
    3. Skills selection — direct mapping from use_cases to skills catalog
    4. Compliance flags — regulations -> auto-configure encryption, audit, etc.

Usage:
    python resolve.py <assessment-file>
    python resolve.py <assessment-file> --json     # Output as JSON
    python resolve.py <assessment-file> --verbose  # Show scoring details
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

MATRIX_PATH = Path(__file__).parent / "needs-mapping-matrix.json"


@dataclass
class ResolutionResult:
    """Output of the assessment resolver."""

    platform: str
    llm_provider: str
    llm_model: str
    skills: list[str]
    compliance_flags: list[str]
    monthly_api_cost_estimate: list[int]
    recommended_adapter: str
    fine_tuning_enabled: bool
    fine_tuning_method: str
    base_model: str | None
    lora_rank: int
    multi_agent: bool = False
    secondary_platform: str | None = None
    client_industry: str = ""
    client_language: str = "en"
    data_sensitivity: str = "low"
    storage_preference: str = "any-cloud"
    scoring_details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_matrix() -> dict[str, Any]:
    """Load the needs-mapping-matrix."""
    return load_json(MATRIX_PATH)


def score_mapping(
    assessment: dict[str, Any],
    mapping: dict[str, Any],
    platform_scores: dict[str, dict[str, int]],
) -> float:
    """
    Score a mapping against the assessment using weighted criteria.

    Higher score = better match. Score components:
    - use_case_overlap: How many assessment use cases match the mapping
    - budget_fit: Whether the budget falls within the mapping's range
    - sensitivity_match: Whether data sensitivity aligns
    - complexity_match: Whether complexity level aligns
    - channel_match: Whether primary channel matches (if specified)
    - device_match: Whether primary devices align
    - regulation_match: Whether compliance regulations align

    Returns:
        Weighted score (float). Higher = better match.
    """
    criteria = mapping.get("match_criteria", {})
    weight = mapping.get("weight", 1.0)
    score = 0.0

    # --- Use case overlap (0-10 points, most important) ---
    assessment_use_cases = set(
        assessment.get("use_cases", {}).get("primary_use_cases", [])
    )
    mapping_use_cases = set(criteria.get("use_cases", []))
    if mapping_use_cases:
        overlap = len(assessment_use_cases & mapping_use_cases)
        if overlap > 0:
            score += (overlap / len(mapping_use_cases)) * 10
        else:
            # No overlap = strong negative signal
            score -= 5

    # --- Budget fit (0-5 points) ---
    monthly_budget = assessment.get("budget", {}).get("monthly_api_budget", 0)
    budget_range = criteria.get("budget_range", [0, 1000])
    if budget_range[0] <= monthly_budget <= budget_range[1]:
        score += 5
    elif monthly_budget < budget_range[0]:
        # Budget too low — penalty proportional to gap
        gap = budget_range[0] - monthly_budget
        score -= min(gap / 50, 3)
    else:
        # Budget higher than needed — slight bonus (can afford it)
        score += 2

    # --- Complexity match (0-4 points) ---
    assessment_complexity = (
        assessment.get("use_cases", {}).get("complexity_level", "moderate")
    )
    mapping_complexity = criteria.get("complexity_level", [])
    if assessment_complexity in mapping_complexity:
        score += 4
    elif mapping_complexity:
        score -= 1

    # --- Data sensitivity match (0-4 points) ---
    assessment_sensitivity = (
        assessment.get("data_privacy", {}).get("sensitivity", "low")
    )
    mapping_sensitivity = criteria.get("sensitivity", [])
    if assessment_sensitivity in mapping_sensitivity:
        score += 4
    elif mapping_sensitivity:
        # Mismatch — big penalty if assessment is MORE sensitive than mapping supports
        sensitivity_order = ["low", "medium", "high", "critical"]
        assessment_idx = sensitivity_order.index(assessment_sensitivity)
        max_mapping_idx = max(
            (sensitivity_order.index(s) for s in mapping_sensitivity), default=0
        )
        if assessment_idx > max_mapping_idx:
            score -= 3  # Assessment needs higher security than mapping provides
        else:
            score -= 1

    # --- Channel match (0-3 points) ---
    primary_channel = (
        assessment.get("channels", {}).get("primary_channel", "")
    )
    mapping_channel = criteria.get("primary_channel", "")
    if mapping_channel and primary_channel == mapping_channel:
        score += 3
    elif mapping_channel and primary_channel != mapping_channel:
        score -= 1

    # --- Device affinity (0-3 points) ---
    assessment_devices = set(
        assessment.get("client_profile", {}).get("primary_devices", [])
    )
    mapping_devices = set(criteria.get("device_affinity", []))
    if mapping_devices:
        device_overlap = len(assessment_devices & mapping_devices)
        if device_overlap > 0:
            score += 3
        else:
            score -= 1

    # --- Regulation match (0-3 points) ---
    assessment_regulations = set(
        assessment.get("compliance", {}).get("regulations", [])
    )
    mapping_regulations = set(criteria.get("regulations", []))
    if mapping_regulations:
        reg_overlap = len(assessment_regulations & mapping_regulations)
        if reg_overlap > 0:
            score += 3
        elif assessment_regulations - {"none"}:
            score -= 2  # Assessment has regulations mapping doesn't cover

    # --- Storage preference match (0-2 points) ---
    storage_pref = (
        assessment.get("data_privacy", {}).get("storage_preference", "any-cloud")
    )
    mapping_storage = criteria.get("storage_preference", [])
    if mapping_storage and storage_pref in mapping_storage:
        score += 2

    # Apply mapping weight
    return score * weight


def select_llm_model(
    assessment: dict[str, Any],
    llm_models: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    """
    Select the best LLM model based on budget and complexity.

    Returns:
        Tuple of (llm_provider, llm_model).
    """
    monthly_budget = assessment.get("budget", {}).get("monthly_api_budget", 0)
    complexity = assessment.get("use_cases", {}).get("complexity_level", "moderate")
    max_context = assessment.get("performance_scale", {}).get("max_context_length", "medium")

    # Local LLM — zero cost, no API key required
    local_endpoint = assessment.get("infrastructure", {}).get("local_llm_endpoint", "")
    if local_endpoint:
        local_model = assessment.get("infrastructure", {}).get("local_llm_model", "llama3.2")
        return "local", local_model

    # Budget-first selection
    if monthly_budget == 0:
        return "deepseek", "deepseek-chat"

    if complexity == "expert" and monthly_budget >= 100:
        return "anthropic", "claude-opus-4-6"

    if max_context == "maximum" and monthly_budget >= 50:
        return "openai", "gpt-4.1"

    if monthly_budget >= 25:
        return "anthropic", "claude-sonnet-4-6"

    if monthly_budget >= 10:
        return "deepseek", "deepseek-chat"

    return "deepseek", "deepseek-chat"


def resolve_assessment(
    assessment: dict[str, Any], verbose: bool = False
) -> ResolutionResult:
    """
    Resolve a client assessment into deployment configuration.

    Args:
        assessment: Parsed client-assessment.json.
        verbose: Include scoring details in the result.

    Returns:
        ResolutionResult with platform, model, skills, and compliance config.
    """
    matrix = load_matrix()
    mappings = matrix.get("mappings", [])
    platform_scores = matrix.get("platform_scores", {})
    llm_models = matrix.get("llm_models", {})

    if not mappings:
        print("ERROR: needs-mapping-matrix.json contains no mappings", file=sys.stderr)
        sys.exit(1)

    # Score all mappings
    scored: list[tuple[float, dict[str, Any]]] = []
    for mapping in mappings:
        score = score_mapping(assessment, mapping, platform_scores)
        scored.append((score, mapping))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] < 0:
        # No good match — fall back to basic assistant
        best_mapping = mappings[0]  # basic-personal-assistant
    else:
        best_mapping = scored[0][1]

    resolution = best_mapping.get("resolution", {})

    # Override LLM model based on budget if the mapping's default is too expensive
    monthly_budget = assessment.get("budget", {}).get("monthly_api_budget", 0)
    cost_estimate = resolution.get("monthly_api_cost_estimate", [0, 50])
    if monthly_budget < cost_estimate[0]:
        llm_provider, llm_model = select_llm_model(assessment, llm_models)
    else:
        llm_provider = resolution.get("llm_provider", "deepseek")
        llm_model = resolution.get("llm_model", "deepseek-chat")

    # Determine fine-tuning settings
    ft_config = assessment.get("fine_tuning", {})
    ft_enabled = ft_config.get("enabled", False)
    ft_method = ft_config.get("method", "prompt-only")
    ft_base_model = ft_config.get("base_model")
    ft_rank = ft_config.get("lora_rank", 32)

    # Auto-recommend fine-tuning for enterprise packages
    service_package = assessment.get("client_profile", {}).get("service_package")
    if service_package == "enterprise" and not ft_enabled:
        ft_enabled = True
        ft_method = "qlora"

    # Default base model if fine-tuning enabled but none specified
    if ft_enabled and not ft_base_model:
        ft_base_model = "mistralai/Mistral-7B-v0.3"

    # Extract client metadata
    client_industry = assessment.get("client_profile", {}).get("industry", "other")
    languages = assessment.get("communication_preferences", {}).get("languages", ["en"])
    primary_language = assessment.get("communication_preferences", {}).get(
        "primary_language", languages[0] if languages else "en"
    )
    data_sensitivity = assessment.get("data_privacy", {}).get("sensitivity", "low")
    storage_preference = assessment.get("data_privacy", {}).get(
        "storage_preference", "any-cloud"
    )

    # Build scoring details
    scoring_details = {}
    if verbose:
        scoring_details = {
            "all_scores": [
                {
                    "mapping_id": m.get("id"),
                    "mapping_name": m.get("name"),
                    "score": round(s, 2),
                }
                for s, m in scored
            ],
            "winner": best_mapping.get("id"),
            "winner_score": round(scored[0][0], 2) if scored else 0,
        }

    return ResolutionResult(
        platform=resolution.get("platform", "picoclaw"),
        llm_provider=llm_provider,
        llm_model=llm_model,
        skills=resolution.get("skills", []),
        compliance_flags=resolution.get("compliance_flags", []),
        monthly_api_cost_estimate=resolution.get("monthly_api_cost_estimate", [0, 50]),
        recommended_adapter=resolution.get("recommended_adapter", ""),
        fine_tuning_enabled=ft_enabled,
        fine_tuning_method=ft_method,
        base_model=ft_base_model,
        lora_rank=ft_rank,
        multi_agent=resolution.get("multi_agent", False),
        secondary_platform=resolution.get("secondary_platform"),
        client_industry=client_industry,
        client_language=primary_language,
        data_sensitivity=data_sensitivity,
        storage_preference=storage_preference,
        scoring_details=scoring_details,
    )


def main() -> int:
    """CLI entry point for assessment resolution."""
    if len(sys.argv) < 2:
        print("Usage: python resolve.py <assessment-file> [--json] [--verbose]")
        return 1

    assessment_path = Path(sys.argv[1])
    output_json = "--json" in sys.argv
    verbose = "--verbose" in sys.argv

    try:
        assessment = load_json(assessment_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        return 1

    result = resolve_assessment(assessment, verbose=verbose)

    if output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("  CLAW AGENTS PROVISIONER — ASSESSMENT RESOLUTION")
        print("=" * 60)
        print()
        print(f"  Platform:         {result.platform}")
        print(f"  LLM Provider:     {result.llm_provider}")
        print(f"  LLM Model:        {result.llm_model}")
        print(f"  Skills:           {', '.join(result.skills)}")
        print(f"  Compliance:       {', '.join(result.compliance_flags) or 'none'}")
        print(f"  API Cost Est:     ${result.monthly_api_cost_estimate[0]}-${result.monthly_api_cost_estimate[1]}/mo")
        print(f"  Adapter:          {result.recommended_adapter}")
        print()
        print(f"  Fine-Tuning:      {'enabled' if result.fine_tuning_enabled else 'disabled'}")
        if result.fine_tuning_enabled:
            print(f"  FT Method:        {result.fine_tuning_method}")
            print(f"  Base Model:       {result.base_model}")
            print(f"  LoRA Rank:        {result.lora_rank}")
        print()
        print(f"  Industry:         {result.client_industry}")
        print(f"  Language:         {result.client_language}")
        print(f"  Sensitivity:      {result.data_sensitivity}")
        print(f"  Storage:          {result.storage_preference}")

        if result.multi_agent:
            print()
            print(f"  Multi-Agent:      YES")
            print(f"  Secondary:        {result.secondary_platform}")

        if verbose and result.scoring_details:
            print()
            print("  --- Scoring Details ---")
            for entry in result.scoring_details.get("all_scores", []):
                marker = " <-- WINNER" if entry["mapping_id"] == result.scoring_details["winner"] else ""
                print(f"  {entry['score']:>6.1f}  {entry['mapping_name']}{marker}")

        print()
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
