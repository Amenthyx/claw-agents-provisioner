"""
Tests for shared/claw_adapter_selector.py — Adapter Auto-Selection Engine.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_adapter_selector import AdapterSelector, USE_CASE_MAP, INDUSTRY_ALIASES


class TestAdapterSelectorMatching:
    """Tests for AdapterSelector matching and scoring."""

    def _create_test_adapters(self, tmp_path):
        """Create minimal adapter structure for testing."""
        adapters_dir = tmp_path / "adapters"
        datasets_dir = tmp_path / "datasets"

        # Create adapter 01-customer-support
        adapter_01 = adapters_dir / "01-customer-support"
        adapter_01.mkdir(parents=True)
        (adapter_01 / "adapter_config.json").write_text(json.dumps({
            "base_model_name_or_path": "mistralai/Mistral-7B-v0.3",
            "r": 32,
            "use_case_name": "Customer Support",
        }))
        dataset_01 = datasets_dir / "01-customer-support"
        dataset_01.mkdir(parents=True)
        (dataset_01 / "metadata.json").write_text(json.dumps({
            "use_case_name": "Customer Support",
            "domain_tags": ["customer-support", "helpdesk", "ticketing", "FAQ"],
            "sampled_rows": 5000,
            "original_rows": 15000,
        }))

        # Create adapter 07-code-review
        adapter_07 = adapters_dir / "07-code-review"
        adapter_07.mkdir(parents=True)
        (adapter_07 / "adapter_config.json").write_text(json.dumps({
            "base_model_name_or_path": "mistralai/Mistral-7B-v0.3",
            "r": 32,
            "use_case_name": "Code Review",
        }))
        dataset_07 = datasets_dir / "07-code-review"
        dataset_07.mkdir(parents=True)
        (dataset_07 / "metadata.json").write_text(json.dumps({
            "use_case_name": "Code Review",
            "domain_tags": ["code-review", "programming", "git", "security"],
            "sampled_rows": 8000,
            "original_rows": 20000,
        }))

        return adapters_dir, datasets_dir

    def test_match_customer_support(self, tmp_path):
        """customer_support should match adapter 01."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        results = selector.match("customer_support")
        assert len(results) > 0
        best_score, best_adapter = results[0]
        assert best_adapter["adapter_id"] == "01-customer-support"
        assert best_score > 0

    def test_match_code_review(self, tmp_path):
        """code_review should match adapter 07."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        results = selector.match("code_review")
        assert len(results) > 0
        best_score, best_adapter = results[0]
        assert best_adapter["adapter_id"] == "07-code-review"
        assert best_score > 0

    def test_match_with_industry_context(self, tmp_path):
        """Industry context should boost matching via alias expansion."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        results_without = selector.match("support")
        results_with = selector.match("support", industry="technology")
        # With industry context, code-review might score higher due to tech keywords
        assert len(results_with) > 0
        assert len(results_without) > 0

    def test_list_adapters(self, tmp_path):
        """list_adapters should return all loaded adapters."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        adapters = selector.list_adapters()
        assert len(adapters) == 2

    def test_select_best(self, tmp_path):
        """select_best should return the single best match with score."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        result = selector.select_best("customer_support")
        assert result is not None
        assert "match_score" in result
        assert result["adapter_id"] == "01-customer-support"

    def test_unknown_use_case_fallback(self, tmp_path):
        """Unknown use case should still return results (scored by fuzzy matching)."""
        adapters_dir, datasets_dir = self._create_test_adapters(tmp_path)
        selector = AdapterSelector(adapters_dir=adapters_dir, datasets_dir=datasets_dir)
        results = selector.match("quantum_physics_simulation")
        # Should still return all adapters, just with low scores
        assert len(results) == 2

    def test_empty_adapters_dir(self, tmp_path):
        """No adapters should return empty results."""
        empty_dir = tmp_path / "empty_adapters"
        empty_dir.mkdir()
        selector = AdapterSelector(adapters_dir=empty_dir, datasets_dir=tmp_path / "ds")
        results = selector.match("anything")
        assert len(results) == 0


class TestUseCaseMap:
    """Tests for the USE_CASE_MAP constant."""

    def test_use_case_map_has_50_unique_adapters(self):
        """USE_CASE_MAP should map to 50 unique adapter directories."""
        unique_adapters = set(USE_CASE_MAP.values())
        assert len(unique_adapters) == 50

    def test_customer_support_mapping(self):
        """customer_support should map to 01-customer-support."""
        assert USE_CASE_MAP["customer_support"] == "01-customer-support"

    def test_code_review_mapping(self):
        """code_review should map to 07-code-review."""
        assert USE_CASE_MAP["code_review"] == "07-code-review"


class TestIndustryAliases:
    """Tests for INDUSTRY_ALIASES expansion."""

    def test_healthcare_aliases(self):
        """Healthcare should have relevant medical terms."""
        assert "healthcare" in INDUSTRY_ALIASES
        aliases = INDUSTRY_ALIASES["healthcare"]
        assert "medical" in aliases
        assert "patient" in aliases

    def test_technology_aliases(self):
        """Technology should have relevant tech terms."""
        assert "technology" in INDUSTRY_ALIASES
        aliases = INDUSTRY_ALIASES["technology"]
        assert "code" in aliases
        assert "devops" in aliases
