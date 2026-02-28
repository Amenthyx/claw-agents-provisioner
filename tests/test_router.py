"""
Tests for shared/claw_router.py — Live Model Router.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_router import detect_task_type, StrategyManager, TASK_KEYWORDS


class TestTaskTypeDetection:
    """Tests for task type detection from message content."""

    def test_detect_coding_task(self):
        """Messages about code should detect 'coding' task type."""
        messages = [
            {"role": "system", "content": "You are a code review assistant"},
            {"role": "user", "content": "Debug this function and fix the bug"},
        ]
        result = detect_task_type(messages)
        assert result == "coding"

    def test_detect_reasoning_task(self):
        """Messages about math/logic should detect 'reasoning'."""
        messages = [
            {"role": "system", "content": "You are a math tutor"},
            {"role": "user", "content": "Calculate the proof of this theorem"},
        ]
        result = detect_task_type(messages)
        assert result == "reasoning"

    def test_detect_creative_task(self):
        """Messages about writing should detect 'creative'."""
        messages = [
            {"role": "user", "content": "Write a creative story about a dragon"},
        ]
        result = detect_task_type(messages)
        assert result == "creative"

    def test_detect_translation_task(self):
        """Messages about translation should detect 'translation'."""
        messages = [
            {"role": "user", "content": "Translate this text to Spanish"},
        ]
        result = detect_task_type(messages)
        assert result == "translation"

    def test_detect_summarization_task(self):
        """Messages about summarization should detect 'summarization'."""
        messages = [
            {"role": "user", "content": "Summarize this article into key points"},
        ]
        result = detect_task_type(messages)
        assert result == "summarization"

    def test_detect_data_analysis_task(self):
        """Messages about data should detect 'data_analysis'."""
        messages = [
            {"role": "system", "content": "You analyze CSV data and run SQL queries"},
            {"role": "user", "content": "Parse this dataset"},
        ]
        result = detect_task_type(messages)
        assert result == "data_analysis"

    def test_detect_simple_chat_fallback(self):
        """Messages with no keywords should fall back to 'simple_chat'."""
        messages = [
            {"role": "user", "content": "Hello, how are you?"},
        ]
        result = detect_task_type(messages)
        assert result == "simple_chat"

    def test_empty_messages(self):
        """Empty messages list should return 'simple_chat'."""
        result = detect_task_type([])
        assert result == "simple_chat"

    def test_system_prompt_takes_priority(self):
        """System prompt keywords should influence detection."""
        messages = [
            {"role": "system", "content": "You are a programming assistant that debugs code"},
            {"role": "user", "content": "Hi there!"},
        ]
        result = detect_task_type(messages)
        assert result == "coding"


class TestStrategyManager:
    """Tests for StrategyManager loading and routing."""

    def test_load_strategy(self, tmp_path, mock_strategy):
        """StrategyManager should load strategy from a JSON file."""
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            assert mgr.strategy.get("version") == "1.0"
            assert mgr.loaded_at > 0

    def test_get_route(self, tmp_path, mock_strategy):
        """get_route should return the routing config for a task type."""
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            route = mgr.get_route("coding")
            assert route is not None
            assert route["primary"]["model"] == "qwen2.5"

    def test_get_route_missing(self, tmp_path, mock_strategy):
        """get_route for unknown task type should return None."""
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            route = mgr.get_route("nonexistent_task")
            assert route is None

    def test_list_models(self, tmp_path, mock_strategy):
        """list_models should return the models inventory."""
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            models = mgr.list_models()
            assert len(models) == 3

    def test_missing_strategy_file(self, tmp_path):
        """StrategyManager should handle missing strategy.json gracefully."""
        missing_file = tmp_path / "missing.json"

        with patch("claw_router.STRATEGY_FILE", missing_file):
            mgr = StrategyManager()
            assert mgr.strategy == {}
            route = mgr.get_route("coding")
            assert route is None

    def test_reload(self, tmp_path, mock_strategy):
        """reload should re-read the strategy file."""
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            assert len(mgr.list_models()) == 3

            # Update the file
            mock_strategy["models_inventory"].append(
                {"id": "new-model", "provider": "Test", "type": "local"}
            )
            strategy_file.write_text(json.dumps(mock_strategy))

            mgr.reload()
            assert len(mgr.list_models()) == 4


class TestTaskKeywords:
    """Tests for TASK_KEYWORDS constant."""

    def test_all_task_types_have_keywords(self):
        """Every task type in TASK_KEYWORDS should have a non-empty keyword list."""
        for task_type, keywords in TASK_KEYWORDS.items():
            assert len(keywords) > 0, f"Task type {task_type} has no keywords"

    def test_coding_has_relevant_keywords(self):
        """Coding task should include keywords like 'code', 'debug', 'function'."""
        kws = TASK_KEYWORDS["coding"]
        assert "code" in kws
        assert "debug" in kws
        assert "function" in kws
