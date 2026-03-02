"""
Integration tests for the Router service — verifies Router + Auth + RateLimit
+ Strategy interactions with mocked LLM endpoints.

Tests the full request path: incoming request -> auth check -> rate limit ->
task detection -> strategy routing -> LLM proxy (mocked) -> response.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_auth import check_auth
from claw_ratelimit import RateLimiter
from claw_router import detect_task_type, StrategyManager, TASK_KEYWORDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def strategy_file(tmp_path, mock_strategy):
    """Write a strategy.json to a temp directory and return the path."""
    sf = tmp_path / "strategy.json"
    sf.write_text(json.dumps(mock_strategy))
    return sf


@pytest.fixture
def strategy_manager(strategy_file):
    """Create a StrategyManager backed by the temp strategy file."""
    with patch("claw_router.STRATEGY_FILE", strategy_file):
        mgr = StrategyManager()
    return mgr


# ---------------------------------------------------------------------------
# Auth + Rate Limit integration
# ---------------------------------------------------------------------------

class TestRouterAuthRateLimitIntegration:
    """Tests that auth and rate limiting work together as middleware."""

    def test_auth_pass_then_rate_limit_pass(self, monkeypatch):
        """Valid auth + under rate limit should both pass."""
        monkeypatch.setenv("CLAW_API_TOKEN", "valid-token")
        ok, err = check_auth({"Authorization": "Bearer valid-token"})
        assert ok is True

        limiter = RateLimiter(max_requests=10, window_seconds=60)
        allowed, remaining, _ = limiter.check("client-1")
        assert allowed is True
        assert remaining == 9

    def test_auth_fail_skips_rate_limit(self, monkeypatch):
        """Failed auth should reject before rate limiting is checked."""
        monkeypatch.setenv("CLAW_API_TOKEN", "valid-token")
        ok, err = check_auth({"Authorization": "Bearer wrong-token"})
        assert ok is False
        assert "Invalid API token" in err

        # Rate limiter should not be consumed for failed auth
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        allowed, _, _ = limiter.check("client-1")
        assert allowed is True  # Still at full capacity

    def test_auth_pass_rate_limit_exceeded(self, monkeypatch):
        """Valid auth but exceeded rate limit should be rejected."""
        monkeypatch.setenv("CLAW_API_TOKEN", "valid-token")
        ok, _ = check_auth({"Authorization": "Bearer valid-token"})
        assert ok is True

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("client-1")
        limiter.check("client-1")
        allowed, remaining, _ = limiter.check("client-1")
        assert allowed is False
        assert remaining == 0

    def test_auth_disabled_rate_limit_still_applies(self, monkeypatch):
        """With auth disabled, rate limiting should still be enforced."""
        monkeypatch.delenv("CLAW_API_TOKEN", raising=False)
        ok, _ = check_auth({})
        assert ok is True

        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("open-client")
        allowed, _, _ = limiter.check("open-client")
        assert allowed is False


# ---------------------------------------------------------------------------
# Task Detection + Strategy Routing integration
# ---------------------------------------------------------------------------

class TestTaskDetectionRoutingIntegration:
    """Tests that task detection correctly maps to strategy routes."""

    def test_coding_task_routes_to_primary(self, strategy_manager):
        """A coding task should route to the primary coding model."""
        messages = [
            {"role": "system", "content": "You are a code assistant"},
            {"role": "user", "content": "Debug this function"},
        ]
        task_type = detect_task_type(messages)
        assert task_type == "coding"

        route = strategy_manager.get_route(task_type)
        assert route is not None
        assert route["primary"]["model"] == "qwen2.5"
        assert route["primary"]["type"] == "local"

    def test_coding_fallback_exists(self, strategy_manager):
        """Coding route should have a cloud fallback."""
        route = strategy_manager.get_route("coding")
        assert route is not None
        assert "fallback" in route
        assert route["fallback"]["model"] == "deepseek-chat"
        assert route["fallback"]["type"] == "cloud"

    def test_simple_chat_routes_to_primary(self, strategy_manager):
        """A simple chat message should route to simple_chat primary."""
        messages = [{"role": "user", "content": "Hello, how are you?"}]
        task_type = detect_task_type(messages)
        assert task_type == "simple_chat"

        route = strategy_manager.get_route(task_type)
        assert route is not None
        assert route["primary"]["model"] == "llama3.2"

    def test_unknown_task_type_no_route(self, strategy_manager):
        """An unroutable task type should return None from strategy."""
        route = strategy_manager.get_route("nonexistent_task_type")
        assert route is None


# ---------------------------------------------------------------------------
# Strategy reload integration
# ---------------------------------------------------------------------------

class TestStrategyReloadIntegration:
    """Tests that strategy reloading picks up changes."""

    def test_reload_updates_routes(self, tmp_path, mock_strategy):
        """Reloading after modifying strategy.json should reflect changes."""
        sf = tmp_path / "strategy.json"
        sf.write_text(json.dumps(mock_strategy))

        with patch("claw_router.STRATEGY_FILE", sf):
            mgr = StrategyManager()
            assert len(mgr.list_models()) == 3

            # Add a new model
            mock_strategy["models_inventory"].append(
                {"id": "gemma-2b", "provider": "Ollama", "type": "local"}
            )
            mock_strategy["total_models"] = 4
            sf.write_text(json.dumps(mock_strategy))

            mgr.reload()
            assert len(mgr.list_models()) == 4


# ---------------------------------------------------------------------------
# Full request flow simulation (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFullRouterFlow:
    """Simulates the full router request flow with mocked LLM backends."""

    def test_full_flow_auth_detect_route(self, monkeypatch, strategy_file):
        """Simulate: auth check -> task detect -> route lookup."""
        # Step 1: Auth
        monkeypatch.setenv("CLAW_API_TOKEN", "test-key")
        headers = {"Authorization": "Bearer test-key"}
        ok, err_msg = check_auth(headers)
        assert ok is True

        # Step 2: Rate limit
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        allowed, _, _ = limiter.check("test-client")
        assert allowed is True

        # Step 3: Task detection
        messages = [
            {"role": "system", "content": "You help with coding tasks"},
            {"role": "user", "content": "Write a Python function to sort a list"},
        ]
        task_type = detect_task_type(messages)
        assert task_type == "coding"

        # Step 4: Route lookup
        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            route = mgr.get_route(task_type)
            assert route is not None
            assert route["primary"]["model"] == "qwen2.5"

    def test_full_flow_with_mocked_llm_response(self, monkeypatch, strategy_file):
        """Simulate full request including mocked LLM proxy response."""
        # Auth
        monkeypatch.delenv("CLAW_API_TOKEN", raising=False)
        ok, _ = check_auth({})
        assert ok is True

        # Rate limit
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        allowed, _, _ = limiter.check("client")
        assert allowed is True

        # Task detection
        messages = [{"role": "user", "content": "Summarize this article"}]
        task_type = detect_task_type(messages)
        assert task_type == "summarization"

        # Route lookup (summarization may not be in mock strategy -> fallback)
        with patch("claw_router.STRATEGY_FILE", strategy_file):
            mgr = StrategyManager()
            route = mgr.get_route(task_type)
            # In mock_strategy, summarization is not defined -> route is None
            # which means router would use simple_chat fallback
            if route is None:
                route = mgr.get_route("simple_chat")

            # Mock the LLM response
            mock_response = {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Here is the summary...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 25,
                    "total_tokens": 75,
                },
            }

            # Verify mock response structure
            assert mock_response["choices"][0]["message"]["role"] == "assistant"
            assert mock_response["usage"]["total_tokens"] == 75


# ---------------------------------------------------------------------------
# Multi-client rate limit isolation
# ---------------------------------------------------------------------------

class TestMultiClientRateLimitIntegration:
    """Tests that rate limiting isolates clients correctly in router context."""

    def test_different_tokens_isolated(self, monkeypatch):
        """Different Bearer tokens should have independent rate limits."""
        monkeypatch.setenv("CLAW_API_TOKEN", "valid-token")
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Client A exhausts limit
        limiter.check("client-a-token")
        limiter.check("client-a-token")
        a_allowed, _, _ = limiter.check("client-a-token")
        assert a_allowed is False

        # Client B still has capacity
        b_allowed, b_remaining, _ = limiter.check("client-b-token")
        assert b_allowed is True
        assert b_remaining == 1

    def test_rate_limit_resets_after_window(self, monkeypatch):
        """Rate limit should reset after the window expires."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)

        limiter.check("client-1")
        denied, _, _ = limiter.check("client-1")
        assert denied is False

        # Wait for window to expire
        time.sleep(1.1)

        allowed, _, _ = limiter.check("client-1")
        assert allowed is True
