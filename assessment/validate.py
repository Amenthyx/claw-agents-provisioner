#!/usr/bin/env python3
"""
Claw Agents Provisioner — Assessment Validator

Validates a client-assessment.json file against the assessment JSON schema.
Provides clear, actionable error messages for missing or invalid fields.

Usage:
    python validate.py <assessment-file>
    python validate.py --schema-only  # Print schema and exit
"""

import json
import sys
from pathlib import Path
from typing import Any

# jsonschema is a lightweight dependency; fallback to manual validation if unavailable
try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


SCHEMA_PATH = Path(__file__).parent / "schema" / "assessment-schema.json"


def load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file with clear error reporting."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in {path.name}: {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e


def load_schema() -> dict[str, Any]:
    """Load the assessment JSON schema."""
    return load_json(SCHEMA_PATH)


def validate_with_jsonschema(
    assessment: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Validate assessment against schema using the jsonschema library."""
    validator = Draft202012Validator(schema)
    errors: list[str] = []

    for error in sorted(validator.iter_errors(assessment), key=lambda e: list(e.path)):
        path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
        if error.validator == "required":
            missing = error.message
            errors.append(f"[MISSING] {path}: {missing}")
        elif error.validator == "enum":
            errors.append(
                f"[INVALID VALUE] {path}: got '{error.instance}', "
                f"expected one of: {error.schema.get('enum', [])}"
            )
        elif error.validator == "type":
            errors.append(
                f"[WRONG TYPE] {path}: expected {error.schema.get('type')}, "
                f"got {type(error.instance).__name__}"
            )
        elif error.validator == "minimum":
            errors.append(
                f"[OUT OF RANGE] {path}: value {error.instance} is below "
                f"minimum {error.schema.get('minimum')}"
            )
        elif error.validator == "maximum":
            errors.append(
                f"[OUT OF RANGE] {path}: value {error.instance} is above "
                f"maximum {error.schema.get('maximum')}"
            )
        elif error.validator == "minItems":
            errors.append(
                f"[EMPTY ARRAY] {path}: requires at least "
                f"{error.schema.get('minItems')} item(s)"
            )
        elif error.validator == "minLength":
            errors.append(f"[EMPTY STRING] {path}: must not be empty")
        elif error.validator == "format":
            errors.append(
                f"[BAD FORMAT] {path}: '{error.instance}' is not a valid "
                f"{error.schema.get('format')}"
            )
        elif error.validator == "pattern":
            errors.append(
                f"[BAD PATTERN] {path}: '{error.instance}' does not match "
                f"pattern {error.schema.get('pattern')}"
            )
        elif error.validator == "additionalProperties":
            errors.append(f"[EXTRA FIELD] {path}: {error.message}")
        else:
            errors.append(f"[{error.validator.upper()}] {path}: {error.message}")

    return errors


def validate_manual(
    assessment: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Fallback validation without jsonschema library. Checks required fields only."""
    errors: list[str] = []

    required_sections = schema.get("required", [])
    for section in required_sections:
        if section not in assessment:
            errors.append(f"[MISSING] (root): Missing required section '{section}'")
            continue

        section_schema = schema.get("properties", {}).get(section, {})
        section_data = assessment[section]

        if not isinstance(section_data, dict):
            errors.append(
                f"[WRONG TYPE] {section}: expected object, got {type(section_data).__name__}"
            )
            continue

        section_required = section_schema.get("required", [])
        for field in section_required:
            if field not in section_data:
                errors.append(
                    f"[MISSING] {section}: Missing required field '{field}'"
                )

    return errors


def validate_business_rules(assessment: dict[str, Any]) -> list[str]:
    """Additional business-logic validations beyond schema structure."""
    warnings: list[str] = []

    # Check budget consistency
    budget = assessment.get("budget", {})
    use_cases = assessment.get("use_cases", {})
    data_privacy = assessment.get("data_privacy", {})
    compliance = assessment.get("compliance", {})

    monthly_budget = budget.get("monthly_api_budget", 0)
    complexity = use_cases.get("complexity_level", "simple")

    if complexity in ("complex", "expert") and monthly_budget < 25:
        warnings.append(
            f"[WARNING] Complex use cases with budget ${monthly_budget}/mo may require "
            "a more capable (and expensive) LLM. Consider raising budget to $25+."
        )

    if monthly_budget == 0 and complexity == "expert":
        warnings.append(
            "[WARNING] $0 budget with expert-level complexity. Only DeepSeek free tier "
            "is available, which may not meet quality expectations."
        )

    # Check HIPAA + storage
    regulations = compliance.get("regulations", [])
    storage = data_privacy.get("storage_preference", "any-cloud")

    if "hipaa" in regulations and storage == "any-cloud":
        warnings.append(
            "[WARNING] HIPAA compliance selected but storage is 'any-cloud'. "
            "Consider 'local-only' or 'private-cloud' for PHI data."
        )

    # Check GDPR + data residency
    if "gdpr" in regulations and not data_privacy.get("data_residency"):
        warnings.append(
            "[WARNING] GDPR compliance selected but no data_residency specified. "
            "Consider setting data_residency to 'EU'."
        )

    # Check high sensitivity + encryption
    sensitivity = data_privacy.get("sensitivity", "low")
    encryption = data_privacy.get("encryption_required", False)

    if sensitivity in ("high", "critical") and not encryption:
        warnings.append(
            f"[WARNING] Data sensitivity is '{sensitivity}' but encryption_required "
            "is false. Strongly recommend enabling encryption."
        )

    # Check fine-tuning feasibility
    fine_tuning = assessment.get("fine_tuning", {})
    if fine_tuning.get("enabled") and fine_tuning.get("method") == "lora":
        ft_budget = budget.get("fine_tuning_budget", 0)
        if ft_budget < 5:
            warnings.append(
                "[WARNING] LoRA fine-tuning enabled but fine_tuning_budget is "
                f"${ft_budget}. LoRA typically costs $5-20 per training run on cloud GPU."
            )

    return warnings


def validate_assessment(assessment_path: Path) -> tuple[bool, list[str], list[str]]:
    """
    Validate a client assessment file.

    Args:
        assessment_path: Path to the client-assessment.json file.

    Returns:
        Tuple of (is_valid, errors, warnings).
    """
    schema = load_schema()
    assessment = load_json(assessment_path)

    if HAS_JSONSCHEMA:
        errors = validate_with_jsonschema(assessment, schema)
    else:
        errors = validate_manual(assessment, schema)

    warnings = validate_business_rules(assessment)

    return len(errors) == 0, errors, warnings


def main() -> int:
    """CLI entry point for assessment validation."""
    if len(sys.argv) < 2:
        print("Usage: python validate.py <assessment-file>")
        print("       python validate.py --schema-only")
        return 1

    if sys.argv[1] == "--schema-only":
        schema = load_schema()
        print(json.dumps(schema, indent=2))
        return 0

    assessment_path = Path(sys.argv[1])

    try:
        is_valid, errors, warnings = validate_assessment(assessment_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    # Print results
    if is_valid:
        print(f"PASS: {assessment_path.name} is a valid assessment.")
    else:
        print(f"FAIL: {assessment_path.name} has {len(errors)} validation error(s):")
        for error in errors:
            print(f"  {error}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  {warning}")

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
