"""
Tests for shared/claw_ratelimit.py — Sliding Window Rate Limiter.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_ratelimit import RateLimiter


class TestRateLimiterBasic:
    """Basic rate limiter functionality."""

    def test_allows_requests_under_limit(self):
        """Requests under the limit should be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            allowed, remaining, reset_at = limiter.check("client-1")
            assert allowed is True
            assert remaining == 5 - i - 1

    def test_denies_requests_over_limit(self):
        """Requests over the limit should be denied."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        # Use up the limit
        for _ in range(3):
            limiter.check("client-1")

        # Next request should be denied
        allowed, remaining, reset_at = limiter.check("client-1")
        assert allowed is False
        assert remaining == 0

    def test_returns_reset_timestamp(self):
        """reset_at should be a future epoch timestamp."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        allowed, remaining, reset_at = limiter.check("client-1")
        assert reset_at > time.time()


class TestRateLimiterClientIsolation:
    """Tests for per-client isolation."""

    def test_different_clients_independent(self):
        """Different client keys should have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Client A uses both slots
        limiter.check("client-a")
        limiter.check("client-a")
        allowed_a, _, _ = limiter.check("client-a")
        assert allowed_a is False

        # Client B should still have all slots
        allowed_b, remaining_b, _ = limiter.check("client-b")
        assert allowed_b is True
        assert remaining_b == 1

    def test_client_key_exact_match(self):
        """Client keys should be exact matches."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("192.168.1.1")
        allowed, _, _ = limiter.check("192.168.1.1")
        assert allowed is False

        # Slightly different key should be independent
        allowed2, _, _ = limiter.check("192.168.1.2")
        assert allowed2 is True


class TestRateLimiterSlidingWindow:
    """Tests for sliding window behavior."""

    def test_window_expiry_allows_new_requests(self):
        """After the window expires, new requests should be allowed."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Use up the limit
        limiter.check("client-1")
        limiter.check("client-1")
        allowed, _, _ = limiter.check("client-1")
        assert allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, remaining, _ = limiter.check("client-1")
        assert allowed is True
        assert remaining == 1

    def test_remaining_count_accurate(self):
        """Remaining count should decrease with each request."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for expected_remaining in [4, 3, 2, 1, 0]:
            allowed, remaining, _ = limiter.check("client-1")
            assert allowed is True
            assert remaining == expected_remaining


class TestRateLimiterReset:
    """Tests for reset functionality."""

    def test_reset_client(self):
        """reset() should clear state for a specific client."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("client-1")

        # Should be denied
        allowed, _, _ = limiter.check("client-1")
        assert allowed is False

        # Reset client
        limiter.reset("client-1")

        # Should be allowed again
        allowed, _, _ = limiter.check("client-1")
        assert allowed is True

    def test_reset_all(self):
        """reset_all() should clear state for all clients."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("client-1")
        limiter.check("client-2")

        limiter.reset_all()

        allowed1, _, _ = limiter.check("client-1")
        allowed2, _, _ = limiter.check("client-2")
        assert allowed1 is True
        assert allowed2 is True

    def test_reset_nonexistent_client(self):
        """reset() for a nonexistent client should not raise."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.reset("nonexistent-client")  # Should not raise


class TestRateLimiterEnvConfig:
    """Tests for environment variable configuration."""

    def test_env_rate_limit(self, monkeypatch):
        """CLAW_RATE_LIMIT should override default max_requests."""
        monkeypatch.setenv("CLAW_RATE_LIMIT", "10")
        monkeypatch.setenv("CLAW_RATE_WINDOW", "30")
        limiter = RateLimiter()
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 30

    def test_env_invalid_fallback(self, monkeypatch):
        """Invalid env values should fall back to defaults."""
        monkeypatch.setenv("CLAW_RATE_LIMIT", "not-a-number")
        monkeypatch.setenv("CLAW_RATE_WINDOW", "")
        limiter = RateLimiter()
        assert limiter.max_requests == 60
        assert limiter.window_seconds == 60

    def test_explicit_params_override_env(self, monkeypatch):
        """Explicit constructor params should override env vars."""
        monkeypatch.setenv("CLAW_RATE_LIMIT", "100")
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 10


class TestRateLimiterThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_requests(self):
        """Concurrent requests from multiple threads should be safe."""
        import threading

        limiter = RateLimiter(max_requests=100, window_seconds=60)
        results = []
        errors = []

        def make_requests():
            try:
                for _ in range(20):
                    allowed, remaining, reset_at = limiter.check("shared-client")
                    results.append(allowed)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100
        # First 100 should be allowed (limit is 100)
        assert all(r is True for r in results)
