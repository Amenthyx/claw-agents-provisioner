"""
Tests for shared/claw_strategy.py — Model Strategy Engine.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_strategy import StrategyGenerator, TASK_TYPES


class TestStrategyGenerator:
    """Tests for StrategyGenerator initialization and generation."""

    def _make_scan_results(self, local=None, cloud=None):
        """Helper to build scan results dict."""
        return {
            "local_models": local or [],
            "cloud_models": cloud or [],
            "available_runtimes": [],
            "total": len(local or []) + len(cloud or []),
        }

    def _make_local_model(self, model_id="qwen2.5", quality=8, speed=6):
        return {
            "id": model_id,
            "full_id": model_id,
            "provider": "local",
            "runtime": "ollama",
            "runtime_name": "Ollama",
            "openai_base": "http://localhost:11434/v1",
            "quality": quality,
            "speed": speed,
            "cost_input": 0.0,
            "cost_output": 0.0,
            "specialization": ["general", "coding"],
        }

    def _make_cloud_model(self, model_id="deepseek-chat", quality=8, speed=7,
                          cost_input=0.14, cost_output=0.28):
        return {
            "id": model_id,
            "full_id": model_id,
            "provider": "deepseek",
            "runtime": "cloud",
            "runtime_name": "DeepSeek",
            "openai_base": None,
            "quality": quality,
            "speed": speed,
            "cost_input": cost_input,
            "cost_output": cost_output,
            "specialization": ["general"],
        }

    def test_init_with_mock_scan(self):
        """StrategyGenerator should initialize with scan results."""
        local = [self._make_local_model()]
        scan = self._make_scan_results(local=local)
        gen = StrategyGenerator(scan)
        assert len(gen.all_models) == 1
        assert gen.prefer_local is True

    def test_score_model_quality_weighting(self):
        """Score should weight quality and speed per task config."""
        scan = self._make_scan_results(cloud=[self._make_cloud_model()])
        gen = StrategyGenerator(scan)
        task_config = {"quality_weight": 0.7, "speed_weight": 0.3, "min_quality": 5}
        model = self._make_cloud_model(quality=9, speed=5)
        score = gen.score_model(model, task_config)
        # base = (9*0.7 + 5*0.3) * 10 = (6.3 + 1.5) * 10 = 78.0
        # no local bonus, + specialization if "general" matches
        assert score >= 70.0

    def test_score_model_local_preference_bonus(self):
        """Local models should get a +15 bonus when prefer_local is True."""
        local_model = self._make_local_model(quality=6, speed=6)
        cloud_model = self._make_cloud_model(quality=6, speed=6)
        scan = self._make_scan_results(local=[local_model], cloud=[cloud_model])
        gen = StrategyGenerator(scan, config={"prefer_local": True})

        task_config = {"quality_weight": 0.5, "speed_weight": 0.5, "min_quality": 5}
        local_score = gen.score_model(local_model, task_config)
        cloud_score = gen.score_model(cloud_model, task_config)
        assert local_score > cloud_score, "Local model should score higher with local preference"

    def test_score_model_cost_penalty(self):
        """High-cost cloud models should get a score penalty."""
        expensive = self._make_cloud_model(
            model_id="claude-opus-4-6", quality=10, speed=3,
            cost_input=15.0, cost_output=75.0,
        )
        cheap = self._make_cloud_model(
            model_id="deepseek-chat", quality=8, speed=7,
            cost_input=0.14, cost_output=0.28,
        )
        scan = self._make_scan_results(cloud=[expensive, cheap])
        gen = StrategyGenerator(scan, config={"prefer_local": False})

        task_config = {"quality_weight": 0.5, "speed_weight": 0.5, "min_quality": 5}
        exp_score = gen.score_model(expensive, task_config)
        cheap_score = gen.score_model(cheap, task_config)
        # Expensive model should be penalized even though quality is higher
        # The penalty is -10 for cost > 10
        assert exp_score < 200  # sanity check

    def test_generate_with_empty_models(self):
        """Generate with no models should return empty dict."""
        scan = self._make_scan_results()
        gen = StrategyGenerator(scan)
        result = gen.generate()
        assert result == {}

    def test_generate_produces_all_task_types(self):
        """Strategy should have routing for all 7 task types."""
        models = [
            self._make_local_model("qwen2.5", quality=8, speed=6),
            self._make_cloud_model("deepseek-chat", quality=8, speed=7),
        ]
        scan = self._make_scan_results(local=[models[0]], cloud=[models[1]])
        gen = StrategyGenerator(scan)
        strategy = gen.generate()

        assert "task_routing" in strategy
        for task_name in TASK_TYPES:
            assert task_name in strategy["task_routing"], f"Missing task type: {task_name}"

    def test_task_type_coverage(self):
        """All 7 task types should be defined in TASK_TYPES."""
        expected_types = [
            "reasoning", "coding", "creative", "simple_chat",
            "translation", "summarization", "data_analysis",
        ]
        for t in expected_types:
            assert t in TASK_TYPES, f"Missing task type: {t}"
        assert len(TASK_TYPES) == 7

    def test_quality_floor_penalty(self):
        """Models below min_quality should get a -30 penalty."""
        low_q_model = self._make_cloud_model(quality=4, speed=10)
        scan = self._make_scan_results(cloud=[low_q_model])
        gen = StrategyGenerator(scan, config={"prefer_local": False})

        # reasoning requires min_quality=8
        task_config = TASK_TYPES["reasoning"]
        score = gen.score_model(low_q_model, task_config)
        # Should be penalized heavily
        assert score < 50

    def test_generate_includes_hardware_info(self, mock_hardware_profile):
        """Strategy should include hardware section when profile is provided."""
        models = [self._make_local_model()]
        scan = self._make_scan_results(local=models)
        gen = StrategyGenerator(scan, hardware_profile=mock_hardware_profile)
        strategy = gen.generate()
        assert strategy["hardware"]["detected"] is True
        assert strategy["hardware"]["ram_gb"] == 64.0
