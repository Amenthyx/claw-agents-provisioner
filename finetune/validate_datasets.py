#!/usr/bin/env python3
"""
Claw Agents Provisioner — Dataset Validator

Validates all 50 use-case datasets:
    - Checks that all 50 directories exist
    - Verifies data.jsonl exists and has <=10,000 rows
    - Validates metadata.json schema and required fields
    - Confirms license is free/open
    - Reports total repo size for all datasets

Usage:
    python validate_datasets.py              # Validate all 50
    python validate_datasets.py --verbose    # Show per-row validation
    python validate_datasets.py --stats      # Show size and format statistics
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("validate_datasets")

DATASETS_DIR = Path(__file__).parent / "datasets"
MAX_ROWS = 10_000

# All 50 expected dataset IDs
EXPECTED_DATASETS = [
    "01-customer-support",
    "02-real-estate",
    "03-e-commerce",
    "04-healthcare",
    "05-legal",
    "06-personal-finance",
    "07-code-review",
    "08-email-management",
    "09-calendar-scheduling",
    "10-meeting-summarization",
    "11-sales-crm",
    "12-hr-recruitment",
    "13-it-helpdesk",
    "14-content-writing",
    "15-social-media",
    "16-translation-multilingual",
    "17-education-tutoring",
    "18-research-summarization",
    "19-data-analysis",
    "20-project-management",
    "21-accounting-bookkeeping",
    "22-insurance-claims",
    "23-travel-hospitality",
    "24-food-restaurant",
    "25-fitness-wellness",
    "26-automotive-vehicle",
    "27-supply-chain-logistics",
    "28-manufacturing-qa",
    "29-agriculture-farming",
    "30-energy-utilities",
    "31-telecommunications",
    "32-government-public-services",
    "33-nonprofit-fundraising",
    "34-event-planning",
    "35-cybersecurity-threat-intel",
    "36-devops-infrastructure",
    "37-api-integration-webhooks",
    "38-database-administration",
    "39-iot-smart-home",
    "40-chatbot-conversational",
    "41-document-processing",
    "42-knowledge-base-faq",
    "43-compliance-regulatory",
    "44-onboarding-training",
    "45-sentiment-analysis",
    "46-creative-writing",
    "47-music-entertainment",
    "48-gaming-virtual-worlds",
    "49-mental-health-counseling",
    "50-personal-finance-budgeting",
]

# Free/open licenses that we accept
ALLOWED_LICENSES = {
    "Apache-2.0",
    "MIT",
    "CC-BY-4.0",
    "CC-BY-3.0",
    "CC-BY-SA-4.0",
    "CC-BY-SA-3.0",
    "CC-BY-NC-3.0",
    "CC-BY-NC-SA-4.0",
    "CC0-1.0",
    "Public Domain",
    "ODC-By-1.0",
    "ODbL-1.0",
}

# Required fields in metadata.json
REQUIRED_METADATA_FIELDS = [
    "use_case_id",
    "use_case_name",
    "source_url",
    "license",
    "sampled_rows",
    "format",
    "language",
    "recommended_base_model",
    "recommended_lora_rank",
]


def validate_metadata(metadata_path: Path) -> list[str]:
    """Validate a metadata.json file. Returns list of error messages."""
    errors: list[str] = []

    if not metadata_path.exists():
        return ["metadata.json does not exist"]

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        return [f"metadata.json is not valid JSON: {e}"]

    # Check required fields
    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")

    # Check license
    license_val = metadata.get("license", "")
    if license_val and license_val not in ALLOWED_LICENSES:
        errors.append(
            f"License '{license_val}' is not in the allowed free/open licenses list"
        )

    # Check sampled_rows
    sampled = metadata.get("sampled_rows", 0)
    if isinstance(sampled, int) and sampled > MAX_ROWS:
        errors.append(
            f"metadata.sampled_rows ({sampled}) exceeds maximum ({MAX_ROWS})"
        )

    # Check lora_rank is reasonable
    rank = metadata.get("recommended_lora_rank", 0)
    if isinstance(rank, int) and rank not in (8, 16, 32, 64):
        errors.append(
            f"recommended_lora_rank ({rank}) should be one of: 8, 16, 32, 64"
        )

    return errors


def validate_data_file(data_path: Path, verbose: bool = False) -> tuple[int, list[str]]:
    """
    Validate a data.jsonl file.

    Returns:
        Tuple of (row_count, error_messages).
    """
    errors: list[str] = []

    if not data_path.exists():
        return 0, ["data.jsonl does not exist"]

    row_count = 0
    malformed = 0

    with open(data_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            row_count += 1
            try:
                row = json.loads(line)

                # Validate messages format
                if "messages" in row:
                    messages = row["messages"]
                    if not isinstance(messages, list) or len(messages) < 2:
                        if verbose:
                            errors.append(
                                f"Line {line_num}: 'messages' should be a list with >=2 entries"
                            )
                        malformed += 1
                    else:
                        for msg in messages:
                            if "role" not in msg or "content" not in msg:
                                if verbose:
                                    errors.append(
                                        f"Line {line_num}: message missing 'role' or 'content'"
                                    )
                                malformed += 1
                                break
            except json.JSONDecodeError:
                malformed += 1
                if verbose:
                    errors.append(f"Line {line_num}: not valid JSON")

    if row_count > MAX_ROWS:
        errors.append(f"Row count ({row_count}) exceeds maximum ({MAX_ROWS})")

    if row_count == 0:
        errors.append("data.jsonl is empty")

    if malformed > 0 and not verbose:
        errors.append(f"{malformed} malformed rows detected (use --verbose for details)")

    return row_count, errors


def validate_all(verbose: bool = False) -> tuple[int, int, int]:
    """
    Validate all 50 datasets.

    Returns:
        Tuple of (passed, failed, total_rows).
    """
    passed = 0
    failed = 0
    total_rows = 0

    print()
    print(f"{'Dataset':<35} {'Rows':>8} {'Meta':>6} {'Data':>6} {'Status':>8}")
    print("-" * 70)

    for dataset_id in EXPECTED_DATASETS:
        ds_dir = DATASETS_DIR / dataset_id
        data_path = ds_dir / "data.jsonl"
        metadata_path = ds_dir / "metadata.json"

        all_errors: list[str] = []

        # Check directory exists
        if not ds_dir.exists():
            all_errors.append(f"Directory does not exist: {ds_dir}")
            print(f"{dataset_id:<35} {'--':>8} {'--':>6} {'--':>6} {'MISSING':>8}")
            failed += 1
            continue

        # Validate metadata
        meta_errors = validate_metadata(metadata_path)
        meta_status = "OK" if not meta_errors else "FAIL"
        all_errors.extend(meta_errors)

        # Validate data
        row_count, data_errors = validate_data_file(data_path, verbose)
        data_status = "OK" if not data_errors else "FAIL"
        all_errors.extend(data_errors)
        total_rows += row_count

        # Overall status
        if all_errors:
            status = "FAIL"
            failed += 1
        else:
            status = "PASS"
            passed += 1

        print(
            f"{dataset_id:<35} {row_count:>8} {meta_status:>6} {data_status:>6} {status:>8}"
        )

        if all_errors and verbose:
            for error in all_errors:
                print(f"  -> {error}")

    return passed, failed, total_rows


def show_stats() -> None:
    """Show statistics about all datasets."""
    total_size = 0
    total_rows = 0
    formats: dict[str, int] = {}
    licenses: dict[str, int] = {}
    languages: dict[str, int] = {}

    for dataset_id in EXPECTED_DATASETS:
        ds_dir = DATASETS_DIR / dataset_id
        data_path = ds_dir / "data.jsonl"
        metadata_path = ds_dir / "metadata.json"

        if data_path.exists():
            size = data_path.stat().st_size
            total_size += size
            rows = sum(1 for line in open(data_path, "r", encoding="utf-8") if line.strip())
            total_rows += rows

        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            fmt = meta.get("format", "unknown")
            lic = meta.get("license", "unknown")
            lang = meta.get("language", "unknown")
            formats[fmt] = formats.get(fmt, 0) + 1
            licenses[lic] = licenses.get(lic, 0) + 1
            languages[lang] = languages.get(lang, 0) + 1

    print()
    print("=== DATASET STATISTICS ===")
    print(f"Total datasets:    {len(EXPECTED_DATASETS)}")
    print(f"Total rows:        {total_rows:,}")
    print(f"Total size:        {total_size / 1024 / 1024:.1f} MB")
    print(f"Avg rows/dataset:  {total_rows // max(len(EXPECTED_DATASETS), 1):,}")
    print()
    print("Formats:")
    for fmt, count in sorted(formats.items()):
        print(f"  {fmt}: {count}")
    print()
    print("Licenses:")
    for lic, count in sorted(licenses.items()):
        print(f"  {lic}: {count}")
    print()
    print("Languages:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count}")


def main() -> int:
    """CLI entry point."""
    verbose = "--verbose" in sys.argv

    if "--stats" in sys.argv:
        show_stats()
        return 0

    passed, failed, total_rows = validate_all(verbose)

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {total_rows:,} total rows")
    print("=" * 70)

    if failed > 0:
        print(f"VALIDATION FAILED: {failed} dataset(s) have issues.")
        return 1
    else:
        print("ALL 50 DATASETS VALIDATED SUCCESSFULLY")
        return 0


if __name__ == "__main__":
    sys.exit(main())
