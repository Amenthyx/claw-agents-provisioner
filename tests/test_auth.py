"""
Tests for shared/claw_auth.py — API Authentication Module.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_auth import check_auth, _constant_time_compare


class TestAuthDisabled:
    """Tests for authentication when CLAW_API_TOKEN is not set."""

    def test_auth_disabled_when_no_token(self, monkeypatch):
        """When CLAW_API_TOKEN is unset, all requests should pass."""
        monkeypatch.delenv("CLAW_API_TOKEN", raising=False)
        ok, error = check_auth({})
        assert ok is True
        assert error == ""

    def test_auth_disabled_when_empty_token(self, monkeypatch):
        """When CLAW_API_TOKEN is empty, all requests should pass."""
        monkeypatch.setenv("CLAW_API_TOKEN", "")
        ok, error = check_auth({})
        assert ok is True
        assert error == ""

    def test_auth_disabled_when_whitespace_token(self, monkeypatch):
        """When CLAW_API_TOKEN is whitespace-only, all requests should pass."""
        monkeypatch.setenv("CLAW_API_TOKEN", "   ")
        ok, error = check_auth({})
        assert ok is True
        assert error == ""


class TestAuthEnabled:
    """Tests for authentication when CLAW_API_TOKEN is set."""

    def test_valid_bearer_token(self, monkeypatch):
        """Valid Bearer token should pass authentication."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({"Authorization": "Bearer secret-token-123"})
        assert ok is True
        assert error == ""

    def test_missing_authorization_header(self, monkeypatch):
        """Missing Authorization header should return 401-style error."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({})
        assert ok is False
        assert "Missing Authorization header" in error

    def test_wrong_token(self, monkeypatch):
        """Wrong Bearer token should fail."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({"Authorization": "Bearer wrong-token"})
        assert ok is False
        assert "Invalid API token" in error

    def test_wrong_scheme(self, monkeypatch):
        """Non-Bearer scheme should fail."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({"Authorization": "Basic dXNlcjpwYXNz"})
        assert ok is False
        assert "Invalid Authorization scheme" in error

    def test_empty_bearer_value(self, monkeypatch):
        """Bearer with empty value should fail."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({"Authorization": "Bearer "})
        assert ok is False
        assert "Empty Bearer token" in error

    def test_bearer_with_extra_whitespace(self, monkeypatch):
        """Bearer token with surrounding whitespace should still match."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret-token-123")
        ok, error = check_auth({"Authorization": "Bearer  secret-token-123 "})
        assert ok is True
        assert error == ""


class TestConstantTimeCompare:
    """Tests for the constant-time string comparison function."""

    def test_equal_strings(self):
        """Identical strings should return True."""
        assert _constant_time_compare("hello", "hello") is True

    def test_different_strings(self):
        """Different strings should return False."""
        assert _constant_time_compare("hello", "world") is False

    def test_different_lengths(self):
        """Strings of different lengths should return False."""
        assert _constant_time_compare("short", "much-longer-string") is False

    def test_empty_strings(self):
        """Two empty strings should be equal."""
        assert _constant_time_compare("", "") is True

    def test_one_empty(self):
        """One empty, one non-empty should return False."""
        assert _constant_time_compare("", "notempty") is False

    def test_unicode_strings(self):
        """Unicode strings should compare correctly."""
        assert _constant_time_compare("caf\u00e9", "caf\u00e9") is True
        assert _constant_time_compare("caf\u00e9", "cafe") is False
