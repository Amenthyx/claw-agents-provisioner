"""
Tests for assessment/resolve.py — Assessment Resolver.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "assessment"))

from resolve import ResolutionResult, score_mapping, select_llm_model


class TestSelectLlmModel:
    """Tests for budget-first LLM model selection."""

    def test_zero_budget_selects_deepseek(self, mock_assessment):
        """$0 budget should select deepseek-chat (free tier)."""
        mock_assessment["budget"]["monthly_api_budget"] = 0
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    def test_expert_high_budget_selects_opus(self, mock_assessment):
        """Expert complexity with $100+ budget should select claude-opus-4-6."""
        mock_assessment["use_cases"]["complexity_level"] = "expert"
        mock_assessment["budget"]["monthly_api_budget"] = 150
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "anthropic"
        assert model == "claude-opus-4-6"

    def test_max_context_selects_gpt4(self, mock_assessment):
        """Maximum context with $50+ budget should select gpt-4.1."""
        mock_assessment["performance_scale"]["max_context_length"] = "maximum"
        mock_assessment["budget"]["monthly_api_budget"] = 75
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "openai"
        assert model == "gpt-4.1"

    def test_mid_budget_selects_sonnet(self, mock_assessment):
        """Budget >= $25 (not expert, not max context) should select claude-sonnet-4-6."""
        mock_assessment["use_cases"]["complexity_level"] = "moderate"
        mock_assessment["budget"]["monthly_api_budget"] = 30
        mock_assessment["performance_scale"]["max_context_length"] = "medium"
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"

    def test_low_budget_selects_deepseek(self, mock_assessment):
        """Budget $10-$24 should select deepseek-chat."""
        mock_assessment["use_cases"]["complexity_level"] = "moderate"
        mock_assessment["budget"]["monthly_api_budget"] = 15
        mock_assessment["performance_scale"]["max_context_length"] = "medium"
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    def test_local_endpoint_uses_local(self, mock_assessment):
        """If local_llm_endpoint is set, should return local provider."""
        mock_assessment["infrastructure"] = {
            "local_llm_endpoint": "http://localhost:11434/v1",
            "local_llm_model": "qwen2.5",
        }
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "local"
        assert model == "qwen2.5"

    def test_local_endpoint_default_model(self, mock_assessment):
        """If local endpoint set but no model specified, should default to llama3.2."""
        mock_assessment["infrastructure"] = {
            "local_llm_endpoint": "http://localhost:11434/v1",
        }
        provider, model = select_llm_model(mock_assessment, {})
        assert provider == "local"
        assert model == "llama3.2"


class TestScoreMapping:
    """Tests for the weighted scoring algorithm."""

    def test_use_case_overlap_increases_score(self, mock_assessment):
        """Overlapping use cases should produce a positive score contribution."""
        mapping = {
            "match_criteria": {
                "use_cases": ["customer-support", "code-review"],
                "budget_range": [0, 100],
                "complexity_level": ["moderate"],
                "sensitivity": ["medium"],
            },
            "weight": 1.0,
        }
        score = score_mapping(mock_assessment, mapping, {})
        assert score > 0

    def test_no_use_case_overlap_penalizes(self, mock_assessment):
        """No matching use cases should penalize the score."""
        mapping = {
            "match_criteria": {
                "use_cases": ["music-entertainment", "gaming-virtual-worlds"],
                "budget_range": [0, 100],
            },
            "weight": 1.0,
        }
        score = score_mapping(mock_assessment, mapping, {})
        # The -5 penalty for no overlap should pull the score down
        score_with_overlap = score_mapping(
            mock_assessment,
            {
                "match_criteria": {
                    "use_cases": ["customer-support"],
                    "budget_range": [0, 100],
                },
                "weight": 1.0,
            },
            {},
        )
        assert score < score_with_overlap

    def test_budget_within_range_gets_bonus(self, mock_assessment):
        """Budget within mapping range should add 5 points."""
        mock_assessment["budget"]["monthly_api_budget"] = 50
        mapping = {
            "match_criteria": {
                "budget_range": [25, 100],
            },
            "weight": 1.0,
        }
        score = score_mapping(mock_assessment, mapping, {})
        assert score >= 5  # At least the budget fit bonus

    def test_weight_multiplier(self, mock_assessment):
        """Higher mapping weight should amplify the score."""
        mapping_low = {
            "match_criteria": {
                "use_cases": ["customer-support"],
                "budget_range": [0, 100],
            },
            "weight": 1.0,
        }
        mapping_high = {
            "match_criteria": {
                "use_cases": ["customer-support"],
                "budget_range": [0, 100],
            },
            "weight": 2.0,
        }
        score_low = score_mapping(mock_assessment, mapping_low, {})
        score_high = score_mapping(mock_assessment, mapping_high, {})
        assert score_high == score_low * 2

    def test_sensitivity_mismatch_penalizes(self, mock_assessment):
        """Assessment with higher sensitivity than mapping supports should penalize."""
        mock_assessment["data_privacy"]["sensitivity"] = "critical"
        mapping = {
            "match_criteria": {
                "sensitivity": ["low"],
                "budget_range": [0, 100],
            },
            "weight": 1.0,
        }
        score = score_mapping(mock_assessment, mapping, {})
        # -3 penalty for assessment needing higher security
        assert score < 5  # Budget bonus alone would be 5


class TestResolutionResult:
    """Tests for the ResolutionResult dataclass."""

    def test_to_dict(self):
        """to_dict should return a serializable dictionary."""
        result = ResolutionResult(
            platform="picoclaw",
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            skills=["web-search"],
            compliance_flags=[],
            monthly_api_cost_estimate=[0, 5],
            recommended_adapter="",
            fine_tuning_enabled=False,
            fine_tuning_method="prompt-only",
            base_model=None,
            lora_rank=32,
        )
        d = result.to_dict()
        assert d["platform"] == "picoclaw"
        assert d["llm_model"] == "deepseek-chat"
        assert isinstance(d["skills"], list)

    def test_enterprise_defaults(self):
        """Enterprise config should properly set fine-tuning fields."""
        result = ResolutionResult(
            platform="openclaw",
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-6",
            skills=["crm-sync"],
            compliance_flags=["encryption"],
            monthly_api_cost_estimate=[25, 50],
            recommended_adapter="02-real-estate",
            fine_tuning_enabled=True,
            fine_tuning_method="qlora",
            base_model="mistralai/Mistral-7B-v0.3",
            lora_rank=32,
            multi_agent=False,
            client_industry="real-estate",
            data_sensitivity="medium",
        )
        d = result.to_dict()
        assert d["fine_tuning_enabled"] is True
        assert d["fine_tuning_method"] == "qlora"
        assert d["base_model"] == "mistralai/Mistral-7B-v0.3"
        assert d["client_industry"] == "real-estate"
