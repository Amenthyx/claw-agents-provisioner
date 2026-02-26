#!/usr/bin/env python3
"""
Convert a filled Claw assessment PDF form into the JSON format expected
by the assessment-to-deployment pipeline (validate.py -> resolve.py -> ...).

Reads AcroForm field values from the PDF and maps them to the
assessment JSON schema v3.0.

Usage:
    python assessment/pdf_to_json.py filled-form.pdf
    python assessment/pdf_to_json.py filled-form.pdf -o client-assessment.json
    python assessment/pdf_to_json.py filled-form.pdf --validate

Requirements:
    pip install pypdf
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("ERROR: pypdf is required. Install it with: pip install pypdf", file=sys.stderr)
        sys.exit(1)


# ── Field name → JSON path mapping ──────────────────────────────────────────

# Checkbox field name prefixes and their use-case/enum values
USE_CASE_PREFIX = "uc_"
DEVICE_PREFIX = "cp_device_"
CHANNEL_SEC_PREFIX = "ch_sec_"
REGULATION_PREFIX = "comp_reg_"
FORMAT_PREFIX = "comm_fmt_"

# All 50 use case enum values (must match generate_pdf_form.py)
ALL_USE_CASES = [
    "customer-support", "real-estate", "e-commerce", "healthcare", "legal",
    "personal-finance", "code-review", "email-management", "calendar-scheduling",
    "meeting-summarization", "sales-crm", "hr-recruitment", "it-helpdesk",
    "content-writing", "social-media", "translation-multilingual",
    "education-tutoring", "research-summarization", "data-analysis",
    "project-management", "accounting-bookkeeping", "insurance-claims",
    "travel-hospitality", "food-restaurant", "fitness-wellness",
    "automotive-vehicle", "supply-chain-logistics", "manufacturing-qa",
    "agriculture-farming", "energy-utilities", "telecommunications",
    "government-public-services", "nonprofit-fundraising", "event-planning",
    "cybersecurity-threat-intel", "devops-infrastructure",
    "api-integration-webhooks", "database-administration", "iot-smart-home",
    "chatbot-conversational", "document-processing", "knowledge-base-faq",
    "compliance-regulatory", "onboarding-training", "sentiment-analysis",
    "creative-writing", "music-entertainment", "gaming-virtual-worlds",
    "mental-health-counseling", "personal-finance-budgeting"
]

ALL_DEVICES = ["desktop", "laptop", "mobile", "tablet", "raspberry-pi", "server", "iot-device"]
ALL_CHANNELS = ["telegram", "whatsapp", "discord", "slack", "web-chat", "email", "sms", "api-only", "cli"]
ALL_REGULATIONS = ["none", "gdpr", "hipaa", "soc2", "pci-dss", "ccpa", "ferpa", "iso27001"]
ALL_FORMATS = ["plain-text", "markdown", "html", "bullet-points", "numbered-lists", "tables"]


def extract_fields(pdf_path: str) -> dict:
    """Extract all AcroForm field values from a PDF."""
    reader = PdfReader(pdf_path)
    fields = {}

    if reader.get_fields():
        for name, field in reader.get_fields().items():
            value = field.get("/V", "")
            if value:
                # pypdf returns values as strings or Name objects
                val = str(value)
                # Strip leading / from PDF name objects
                if val.startswith("/"):
                    val = val[1:]
                fields[name] = val
            else:
                fields[name] = ""
    else:
        # Fallback: iterate page annotations
        for page in reader.pages:
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    obj = annot.get_object()
                    if "/T" in obj:
                        name = str(obj["/T"])
                        value = str(obj.get("/V", ""))
                        if value.startswith("/"):
                            value = value[1:]
                        fields[name] = value

    return fields


def is_checked(fields: dict, field_name: str) -> bool:
    """Check if a checkbox field is checked."""
    val = fields.get(field_name, "")
    return val.lower() in ("yes", "on", "true", "/yes", "/on", "1")


def get_text(fields: dict, field_name: str) -> str:
    """Get a text field value, stripped."""
    return fields.get(field_name, "").strip()


def get_number(fields: dict, field_name: str, as_float: bool = False):
    """Get a numeric field value."""
    val = get_text(fields, field_name)
    if not val:
        return None
    try:
        return float(val) if as_float else int(float(val))
    except ValueError:
        return None


def get_checked_items(fields: dict, prefix: str, all_items: list) -> list:
    """Get list of checked items from checkbox grid fields."""
    checked = []
    for item in all_items:
        field_name = f"{prefix}{item.replace('-', '_')}"
        if is_checked(fields, field_name):
            checked.append(item)
    return checked


def fields_to_json(fields: dict) -> dict:
    """Convert PDF form field values to assessment JSON structure."""
    result = {
        "assessment_version": "3.0",
    }

    # ── Meta fields ──────────────────────────────────────────────────────
    date_val = get_text(fields, "assessment_date")
    if date_val:
        result["assessment_date"] = date_val

    consultant = get_text(fields, "consultant_id")
    if consultant:
        result["consultant_id"] = consultant

    # ── Section 1: Client Profile ────────────────────────────────────────
    cp = {}
    for key, field in [
        ("company_name", "cp_company_name"),
        ("contact_name", "cp_contact_name"),
        ("contact_email", "cp_contact_email"),
        ("industry", "cp_industry"),
        ("industry_other", "cp_industry_other"),
        ("company_size", "cp_company_size"),
        ("operating_system", "cp_operating_system"),
        ("service_package", "cp_service_package"),
    ]:
        val = get_text(fields, field)
        if val:
            cp[key] = val

    tech_savvy = get_number(fields, "cp_tech_savvy")
    if tech_savvy is not None:
        cp["tech_savvy"] = tech_savvy

    devices = get_checked_items(fields, DEVICE_PREFIX, ALL_DEVICES)
    if devices:
        cp["primary_devices"] = devices

    if cp:
        result["client_profile"] = cp

    # ── Section 2: Use Cases ─────────────────────────────────────────────
    uc = {}
    primary = get_checked_items(fields, USE_CASE_PREFIX, ALL_USE_CASES)
    if primary:
        uc["primary_use_cases"] = primary

    secondary_text = get_text(fields, "uc_secondary")
    if secondary_text:
        uc["secondary_use_cases"] = [s.strip() for s in secondary_text.split(",") if s.strip()]

    for key, field in [
        ("use_case_priority", "uc_priority"),
        ("complexity_level", "uc_complexity"),
        ("domain_specific_requirements", "uc_domain_requirements"),
    ]:
        val = get_text(fields, field)
        if val:
            uc[key] = val

    if uc:
        result["use_cases"] = uc

    # ── Section 3: Communication Preferences ─────────────────────────────
    comm = {}
    languages_text = get_text(fields, "comm_languages")
    if languages_text:
        comm["languages"] = [l.strip() for l in languages_text.split(",") if l.strip()]

    for key, field in [
        ("primary_language", "comm_primary_language"),
        ("tone", "comm_tone"),
        ("verbosity", "comm_verbosity"),
        ("persona_name", "comm_persona_name"),
        ("persona_description", "comm_persona_description"),
        ("greeting_message", "comm_greeting"),
    ]:
        val = get_text(fields, field)
        if val:
            comm[key] = val

    formats = get_checked_items(fields, FORMAT_PREFIX, ALL_FORMATS)
    if formats:
        comm["response_format_preferences"] = formats

    if comm:
        result["communication_preferences"] = comm

    # ── Section 4: Data Privacy ──────────────────────────────────────────
    dp = {}
    for key, field in [
        ("sensitivity", "dp_sensitivity"),
        ("storage_preference", "dp_storage"),
        ("pii_handling", "dp_pii"),
        ("data_residency", "dp_residency"),
    ]:
        val = get_text(fields, field)
        if val:
            dp[key] = val

    retention = get_number(fields, "dp_retention_days")
    if retention is not None:
        dp["data_retention_days"] = retention

    if is_checked(fields, "dp_encryption"):
        dp["encryption_required"] = True
    if is_checked(fields, "dp_audit_logging"):
        dp["audit_logging_required"] = True

    if dp:
        result["data_privacy"] = dp

    # ── Section 5: Performance & Scale ───────────────────────────────────
    ps = {}
    daily = get_number(fields, "ps_daily_requests")
    if daily is not None:
        ps["daily_requests"] = daily

    peak = get_number(fields, "ps_peak_users")
    if peak is not None:
        ps["peak_concurrent_users"] = peak

    for key, field in [
        ("response_time_target", "ps_response_time"),
        ("availability_target", "ps_availability"),
        ("max_context_length", "ps_context_length"),
    ]:
        val = get_text(fields, field)
        if val:
            ps[key] = val

    if ps:
        result["performance_scale"] = ps

    # ── Section 6: Budget ────────────────────────────────────────────────
    bgt = {}
    for key, field, is_float in [
        ("monthly_api_budget", "bgt_monthly_api", True),
        ("infrastructure_budget", "bgt_infrastructure", True),
        ("one_time_setup_budget", "bgt_setup", True),
        ("fine_tuning_budget", "bgt_finetune", True),
    ]:
        val = get_number(fields, field, as_float=is_float)
        if val is not None:
            bgt[key] = val

    cost_prio = get_text(fields, "bgt_cost_priority")
    if cost_prio:
        bgt["cost_optimization_priority"] = cost_prio

    if bgt:
        result["budget"] = bgt

    # ── Section 7: Channels ──────────────────────────────────────────────
    ch = {}
    primary_ch = get_text(fields, "ch_primary")
    if primary_ch:
        ch["primary_channel"] = primary_ch

    sec_channels = get_checked_items(fields, CHANNEL_SEC_PREFIX, ALL_CHANNELS)
    if sec_channels:
        ch["secondary_channels"] = sec_channels

    # Channel-specific config
    ch_config = {}

    # WhatsApp
    wa_config = {}
    if is_checked(fields, "ch_wa_business"):
        wa_config["business_account"] = True
    wa_phone = get_text(fields, "ch_wa_phone")
    if wa_phone:
        wa_config["phone_number"] = wa_phone
    if wa_config:
        ch_config["whatsapp"] = wa_config

    # Telegram
    tg_config = {}
    tg_name = get_text(fields, "ch_tg_bot_name")
    if tg_name:
        tg_config["bot_name"] = tg_name
    if is_checked(fields, "ch_tg_group_mode"):
        tg_config["group_mode"] = True
    else:
        tg_config["group_mode"] = False
    if tg_name:  # Only add telegram config if bot name is set
        ch_config["telegram"] = tg_config

    # Discord
    discord_id = get_text(fields, "ch_discord_server")
    if discord_id:
        ch_config["discord"] = {"server_id": discord_id}

    # Slack
    slack_ws = get_text(fields, "ch_slack_workspace")
    if slack_ws:
        ch_config["slack"] = {"workspace_name": slack_ws}

    if ch_config:
        ch["channel_specific_config"] = ch_config

    if ch:
        result["channels"] = ch

    # ── Section 8: Compliance ────────────────────────────────────────────
    comp = {}
    regulations = get_checked_items(fields, REGULATION_PREFIX, ALL_REGULATIONS)
    if regulations:
        comp["regulations"] = regulations

    if is_checked(fields, "comp_dpa"):
        comp["data_processing_agreement_required"] = True
    if is_checked(fields, "comp_right_deletion"):
        comp["right_to_deletion"] = True
    if is_checked(fields, "comp_consent"):
        comp["consent_management"] = True
    if is_checked(fields, "comp_audit_trail"):
        comp["audit_trail_required"] = True

    notes = get_text(fields, "comp_notes")
    if notes:
        comp["custom_compliance_notes"] = notes

    if comp:
        result["compliance"] = comp

    # ── Fine-Tuning (Optional) ───────────────────────────────────────────
    ft = {}
    if is_checked(fields, "ft_enabled"):
        ft["enabled"] = True

    for key, field in [
        ("method", "ft_method"),
        ("base_model", "ft_base_model"),
        ("adapter_use_case", "ft_adapter_use_case"),
        ("custom_training_data_path", "ft_custom_data"),
    ]:
        val = get_text(fields, field)
        if val:
            ft[key] = val

    if is_checked(fields, "ft_prebuilt"):
        ft["use_pre_built_adapter"] = True

    lora_rank = get_number(fields, "ft_lora_rank")
    if lora_rank is not None:
        ft["lora_rank"] = lora_rank

    epochs = get_number(fields, "ft_epochs")
    if epochs is not None:
        ft["training_epochs"] = epochs

    if ft:
        result["fine_tuning"] = ft

    return result


def detect_tier(fields: dict) -> str:
    """Detect assessment tier from PDF fields.

    Enterprise PDFs contain a ft_enabled checkbox field; Private PDFs do not.
    """
    return "enterprise" if "ft_enabled" in fields else "private"


def apply_private_defaults(result: dict) -> dict:
    """Apply sensible defaults for fields not present in Private tier PDFs.

    Private forms omit technical fields (fine-tuning, PII handling, context
    length, etc.).  This function fills them with safe defaults so the output
    JSON validates against the full assessment schema.
    """
    # Meta
    result.setdefault("assessment_date", date.today().isoformat())
    result.setdefault("consultant_id", "auto")

    # Client profile
    cp = result.setdefault("client_profile", {})
    cp.setdefault("service_package", "private")
    cp.setdefault("tech_savvy", 3)
    cp.setdefault("operating_system", "any")

    # Communication
    comm = result.setdefault("communication_preferences", {})
    comm.setdefault("response_format_preferences", ["plain-text", "markdown"])

    # Data privacy
    dp = result.setdefault("data_privacy", {})
    dp.setdefault("pii_handling", "encrypt")
    dp.setdefault("data_retention_days", 365)
    dp.setdefault("encryption_required", True)
    if "audit_logging_required" not in dp:
        dp["audit_logging_required"] = False

    # Performance
    ps = result.setdefault("performance_scale", {})
    ps.setdefault("max_context_length", "medium")

    # Fine-tuning
    if "fine_tuning" not in result:
        result["fine_tuning"] = {"enabled": False}

    return result


def validate_output(assessment: dict) -> list:
    """Run basic validation on the generated JSON."""
    errors = []
    warnings = []

    # Required sections
    required_sections = [
        "client_profile", "use_cases", "communication_preferences",
        "data_privacy", "performance_scale", "budget", "channels", "compliance"
    ]
    for section in required_sections:
        if section not in assessment:
            errors.append(f"[MISSING] Required section: {section}")

    # Required fields within sections
    cp = assessment.get("client_profile", {})
    if not cp.get("company_name"):
        errors.append("[MISSING] client_profile.company_name is required")
    if not cp.get("contact_name"):
        errors.append("[MISSING] client_profile.contact_name is required")
    if not cp.get("industry"):
        errors.append("[MISSING] client_profile.industry is required")
    if not cp.get("company_size"):
        errors.append("[MISSING] client_profile.company_size is required")
    if not cp.get("tech_savvy"):
        errors.append("[MISSING] client_profile.tech_savvy is required")
    if not cp.get("primary_devices"):
        errors.append("[MISSING] client_profile.primary_devices is required (check at least one)")

    uc = assessment.get("use_cases", {})
    if not uc.get("primary_use_cases"):
        errors.append("[MISSING] use_cases.primary_use_cases is required (check at least one)")

    comm = assessment.get("communication_preferences", {})
    if not comm.get("languages"):
        errors.append("[MISSING] communication_preferences.languages is required")
    if not comm.get("tone"):
        errors.append("[MISSING] communication_preferences.tone is required")

    dp = assessment.get("data_privacy", {})
    if not dp.get("sensitivity"):
        errors.append("[MISSING] data_privacy.sensitivity is required")
    if not dp.get("storage_preference"):
        errors.append("[MISSING] data_privacy.storage_preference is required")

    ps = assessment.get("performance_scale", {})
    if not ps.get("daily_requests"):
        errors.append("[MISSING] performance_scale.daily_requests is required")
    if not ps.get("response_time_target"):
        errors.append("[MISSING] performance_scale.response_time_target is required")

    bgt = assessment.get("budget", {})
    if bgt.get("monthly_api_budget") is None:
        errors.append("[MISSING] budget.monthly_api_budget is required")

    ch = assessment.get("channels", {})
    if not ch.get("primary_channel"):
        errors.append("[MISSING] channels.primary_channel is required")

    comp = assessment.get("compliance", {})
    if not comp.get("regulations"):
        errors.append("[MISSING] compliance.regulations is required (check at least one)")

    # Business rule warnings
    budget_val = bgt.get("monthly_api_budget", 0)
    complexity = uc.get("complexity_level", "")
    if complexity in ("complex", "expert") and budget_val < 25:
        warnings.append(
            f"[WARN] Complex use cases with ${budget_val}/mo budget may limit model quality"
        )

    regs = comp.get("regulations", [])
    storage = dp.get("storage_preference", "")
    if "hipaa" in regs and storage == "any-cloud":
        warnings.append("[WARN] HIPAA compliance with 'any-cloud' storage is risky")
    if "gdpr" in regs and not dp.get("data_residency"):
        warnings.append("[WARN] GDPR selected but no data_residency specified")

    return errors, warnings


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert a filled Claw assessment PDF form to JSON"
    )
    parser.add_argument("pdf_path", help="Path to the filled PDF form")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON path (default: stdout)"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate the output against required fields"
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-print JSON output (default: True)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show raw PDF field names and values"
    )
    args = parser.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Extract raw fields
    fields = extract_fields(args.pdf_path)

    if args.debug:
        print("=== Raw PDF Fields ===", file=sys.stderr)
        for name, value in sorted(fields.items()):
            print(f"  {name}: {repr(value)}", file=sys.stderr)
        print(f"  Total: {len(fields)} fields", file=sys.stderr)
        print("======================", file=sys.stderr)

    # Convert to JSON
    assessment = fields_to_json(fields)

    # Detect tier and apply defaults for Private
    tier = detect_tier(fields)
    if tier == "private":
        assessment = apply_private_defaults(assessment)
    print(f"Detected tier: {tier}", file=sys.stderr)

    # Validate if requested
    if args.validate:
        errors, warnings = validate_output(assessment)
        if errors:
            print(f"\n{len(errors)} validation error(s):", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
        if warnings:
            print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
            for w in warnings:
                print(f"  {w}", file=sys.stderr)
        if not errors and not warnings:
            print("Validation passed: all required fields present.", file=sys.stderr)
        if errors:
            print("\nJSON generated but has validation errors. Fix the PDF and re-convert.",
                  file=sys.stderr)

    # Output
    indent = 2 if args.pretty else None
    json_str = json.dumps(assessment, indent=indent, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")
        print(f"Assessment JSON written to: {args.output}", file=sys.stderr)
        if args.validate:
            errors, _ = validate_output(assessment)
            if not errors:
                print(f"  Ready for: python assessment/validate.py {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
