"""
Tests for shared/claw_audit.py — Structured JSON Audit Logger.
"""

import json
import os
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_audit import AuditLogger, get_audit_logger


# ── Helpers ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the AuditLogger singleton between tests."""
    AuditLogger._instance = None
    yield
    AuditLogger._instance = None


@pytest.fixture
def audit_log_path(tmp_path):
    """Return a temporary audit log path and set the env var."""
    log_file = tmp_path / "audit.log"
    with patch.dict(os.environ, {
        "CLAW_AUDIT_LOG_PATH": str(log_file),
        "CLAW_AUDIT_ENABLED": "true",
    }):
        yield log_file


@pytest.fixture
def disabled_audit():
    """Disable audit logging via env var."""
    with patch.dict(os.environ, {"CLAW_AUDIT_ENABLED": "false"}):
        yield


# ── Singleton Tests ──────────────────────────────────────────────────────

class TestSingleton:
    """Tests for the thread-safe singleton pattern."""

    def test_singleton_returns_same_instance(self, audit_log_path):
        """get_audit_logger() should return the same instance."""
        a = get_audit_logger()
        b = get_audit_logger()
        assert a is b

    def test_singleton_thread_safety(self, audit_log_path):
        """Concurrent calls should all get the same instance."""
        instances = []

        def grab():
            instances.append(get_audit_logger())

        threads = [threading.Thread(target=grab) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 10
        assert all(inst is instances[0] for inst in instances)


# ── Enabled / Disabled Tests ────────────────────────────────────────────

class TestEnabled:
    """Tests for the CLAW_AUDIT_ENABLED flag."""

    def test_enabled_by_default(self, audit_log_path):
        """Audit should be enabled when CLAW_AUDIT_ENABLED=true."""
        audit = get_audit_logger()
        assert audit.enabled is True

    def test_disabled_via_env(self, disabled_audit):
        """Audit should be disabled when CLAW_AUDIT_ENABLED=false."""
        audit = get_audit_logger()
        assert audit.enabled is False

    def test_disabled_no_file_written(self, tmp_path, disabled_audit):
        """When disabled, no log file should be created."""
        log_file = tmp_path / "should_not_exist.log"
        with patch.dict(os.environ, {"CLAW_AUDIT_LOG_PATH": str(log_file)}):
            audit = get_audit_logger()
            audit.log_request(
                action="test",
                resource="/test",
                outcome="success",
            )
        assert not log_file.exists()


# ── Log Entry Format Tests ──────────────────────────────────────────────

class TestLogEntryFormat:
    """Tests for the JSON log entry schema."""

    def test_log_request_creates_valid_json(self, audit_log_path):
        """log_request() should write a valid JSON line."""
        audit = get_audit_logger()
        audit.log_request(
            action="POST /v1/chat/completions",
            resource="/v1/chat/completions",
            outcome="success",
            ip_address="192.168.1.10",
            user="test-token-abc123",
            details={"model": "llama3.2", "status": 200},
        )

        # Flush handlers
        for handler in audit._logger.handlers:
            handler.flush()

        content = audit_log_path.read_text(encoding="utf-8").strip()
        entry = json.loads(content)

        assert entry["event_type"] == "request"
        assert entry["action"] == "POST /v1/chat/completions"
        assert entry["resource"] == "/v1/chat/completions"
        assert entry["outcome"] == "success"
        assert entry["ip_address"] == "192.168.1.10"
        assert entry["details"]["model"] == "llama3.2"
        assert "timestamp" in entry

    def test_log_auth_event_type(self, audit_log_path):
        """log_auth() should set event_type to 'auth'."""
        audit = get_audit_logger()
        audit.log_auth(
            action="login_attempt",
            resource="/auth",
            outcome="failure",
            ip_address="10.0.0.1",
            details={"reason": "bad_password"},
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["event_type"] == "auth"
        assert entry["outcome"] == "failure"

    def test_log_config_change_event_type(self, audit_log_path):
        """log_config_change() should set event_type to 'config_change'."""
        audit = get_audit_logger()
        audit.log_config_change(
            action="reload_strategy",
            resource="strategy.json",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["event_type"] == "config_change"

    def test_log_data_access_event_type(self, audit_log_path):
        """log_data_access() should set event_type to 'data_access'."""
        audit = get_audit_logger()
        audit.log_data_access(
            action="vault_get",
            resource="ANTHROPIC_API_KEY",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["event_type"] == "data_access"

    def test_log_security_event_type(self, audit_log_path):
        """log_security_event() should set event_type to 'security'."""
        audit = get_audit_logger()
        audit.log_security_event(
            action="url_blocked",
            resource="security_checker",
            outcome="failure",
            details={"severity": "warn", "detail": "Blocked domain"},
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["event_type"] == "security"


# ── Token Hashing Tests ────────────────────────────────────────────────

class TestTokenHashing:
    """Tests for token hashing (never log raw tokens)."""

    def test_token_is_hashed(self, audit_log_path):
        """Raw token should never appear in the log."""
        raw_token = "sk-ant-super-secret-token-12345"
        audit = get_audit_logger()
        audit.log_request(
            action="test",
            resource="/test",
            outcome="success",
            user=raw_token,
        )
        for handler in audit._logger.handlers:
            handler.flush()

        content = audit_log_path.read_text(encoding="utf-8")
        assert raw_token not in content

        entry = json.loads(content.strip())
        assert entry["user"] != raw_token
        assert len(entry["user"]) == 16  # truncated SHA-256

    def test_anonymous_when_no_token(self, audit_log_path):
        """User should be 'anonymous' when no token is provided."""
        audit = get_audit_logger()
        audit.log_request(
            action="test",
            resource="/test",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["user"] == "anonymous"

    def test_same_token_same_hash(self, audit_log_path):
        """Same token should produce the same hash consistently."""
        hash1 = AuditLogger._hash_token("my-token")
        hash2 = AuditLogger._hash_token("my-token")
        assert hash1 == hash2

    def test_different_tokens_different_hashes(self, audit_log_path):
        """Different tokens should produce different hashes."""
        hash1 = AuditLogger._hash_token("token-a")
        hash2 = AuditLogger._hash_token("token-b")
        assert hash1 != hash2


# ── ISO 8601 Timestamp Tests ────────────────────────────────────────────

class TestTimestamp:
    """Tests for ISO 8601 timestamp format."""

    def test_timestamp_is_iso8601(self, audit_log_path):
        """Timestamp should be in ISO 8601 UTC format."""
        audit = get_audit_logger()
        audit.log_request(
            action="test",
            resource="/test",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        ts = entry["timestamp"]
        # Should end with Z (UTC) and contain T separator
        assert ts.endswith("Z")
        assert "T" in ts


# ── Default Details Tests ───────────────────────────────────────────────

class TestDefaults:
    """Tests for default values when optional params are omitted."""

    def test_default_details_is_empty_dict(self, audit_log_path):
        """details should default to empty dict when not provided."""
        audit = get_audit_logger()
        audit.log_request(
            action="test",
            resource="/test",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["details"] == {}

    def test_default_ip_is_empty_string(self, audit_log_path):
        """ip_address should default to empty string when not provided."""
        audit = get_audit_logger()
        audit.log_request(
            action="test",
            resource="/test",
            outcome="success",
        )
        for handler in audit._logger.handlers:
            handler.flush()

        entry = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
        assert entry["ip_address"] == ""
