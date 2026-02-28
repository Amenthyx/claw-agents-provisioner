"""
Tests for assessment/validate.py — Assessment Validator.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "assessment"))

from validate import (
    load_json,
    validate_manual,
    validate_business_rules,
    validate_with_jsonschema,
)

SCHEMA_PATH = Path(__file__).parent.parent / "assessment" / "schema" / "assessment-schema.json"


def _load_schema():
    """Helper to load the real assessment schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestLoadJson:
    """Tests for the load_json helper."""

    def test_load_valid_json(self, tmp_path):
        """load_json should parse a valid JSON file."""
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"key": "value"}))
        result = load_json(f)
        assert result == {"key": "value"}

    def test_load_missing_file(self, tmp_path):
        """load_json should raise FileNotFoundError for missing files."""
        missing = tmp_path / "missing.json"
        try:
            load_json(missing)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_load_invalid_json(self, tmp_path):
        """load_json should raise ValueError for malformed JSON."""
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        try:
            load_json(f)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid JSON" in str(e)


class TestValidateManual:
    """Tests for manual (fallback) validation."""

    def test_valid_assessment_passes(self, mock_assessment):
        """A complete assessment should produce no errors."""
        schema = _load_schema()
        errors = validate_manual(mock_assessment, schema)
        assert errors == []

    def test_missing_required_section(self, mock_assessment):
        """Removing a required section should produce an error."""
        schema = _load_schema()
        del mock_assessment["client_profile"]
        errors = validate_manual(mock_assessment, schema)
        assert any("client_profile" in e for e in errors)

    def test_missing_required_field_in_section(self, mock_assessment):
        """Removing a required field within a section should produce an error."""
        schema = _load_schema()
        del mock_assessment["client_profile"]["company_name"]
        errors = validate_manual(mock_assessment, schema)
        assert any("company_name" in e for e in errors)

    def test_wrong_type_for_section(self, mock_assessment):
        """Passing a non-dict for a section should produce a WRONG TYPE error."""
        schema = _load_schema()
        mock_assessment["budget"] = "not-a-dict"
        errors = validate_manual(mock_assessment, schema)
        assert any("WRONG TYPE" in e for e in errors)


class TestValidateBusinessRules:
    """Tests for business rule warnings."""

    def test_no_warnings_on_good_assessment(self, mock_assessment):
        """A well-configured assessment should produce no business warnings."""
        warnings = validate_business_rules(mock_assessment)
        assert warnings == []

    def test_complex_with_low_budget(self, mock_assessment):
        """Complex use cases with budget < $25 should warn."""
        mock_assessment["use_cases"]["complexity_level"] = "complex"
        mock_assessment["budget"]["monthly_api_budget"] = 10
        warnings = validate_business_rules(mock_assessment)
        assert any("Complex use cases" in w for w in warnings)

    def test_zero_budget_expert_warning(self, mock_assessment):
        """$0 budget with expert complexity should produce a specific warning."""
        mock_assessment["use_cases"]["complexity_level"] = "expert"
        mock_assessment["budget"]["monthly_api_budget"] = 0
        warnings = validate_business_rules(mock_assessment)
        assert any("$0 budget" in w for w in warnings)

    def test_hipaa_with_any_cloud(self, mock_assessment):
        """HIPAA compliance with any-cloud storage should warn."""
        mock_assessment["compliance"]["regulations"] = ["hipaa"]
        mock_assessment["data_privacy"]["storage_preference"] = "any-cloud"
        warnings = validate_business_rules(mock_assessment)
        assert any("HIPAA" in w for w in warnings)

    def test_gdpr_without_residency(self, mock_assessment):
        """GDPR with no data_residency should warn."""
        mock_assessment["compliance"]["regulations"] = ["gdpr"]
        # Ensure data_residency is not set
        mock_assessment["data_privacy"].pop("data_residency", None)
        warnings = validate_business_rules(mock_assessment)
        assert any("GDPR" in w for w in warnings)

    def test_high_sensitivity_no_encryption(self, mock_assessment):
        """High sensitivity without encryption should warn."""
        mock_assessment["data_privacy"]["sensitivity"] = "high"
        mock_assessment["data_privacy"]["encryption_required"] = False
        warnings = validate_business_rules(mock_assessment)
        assert any("encryption" in w.lower() for w in warnings)

    def test_lora_fine_tuning_low_budget(self, mock_assessment):
        """LoRA fine-tuning with budget < $5 should warn."""
        mock_assessment["fine_tuning"] = {
            "enabled": True,
            "method": "lora",
        }
        mock_assessment["budget"]["fine_tuning_budget"] = 2
        warnings = validate_business_rules(mock_assessment)
        assert any("LoRA" in w for w in warnings)
