#!/usr/bin/env python3
"""
Claw Audit — Structured JSON Audit Logging for Claw Agents Provisioner

Provides a thread-safe, singleton audit logger that writes structured JSON
log entries to a rotating log file.  Every security-relevant action in the
system (API requests, auth events, config changes, data access, security
violations) is captured with a consistent schema.

Log entry schema:
    {
        "timestamp":   ISO 8601 UTC,
        "event_type":  request | auth | config_change | data_access | security,
        "user":        token hash (never raw token),
        "action":      string describing the operation,
        "resource":    target resource / endpoint,
        "outcome":     "success" | "failure",
        "ip_address":  client IP,
        "details":     {} arbitrary context
    }

Configuration (environment variables):
    CLAW_AUDIT_ENABLED    — "true" (default) or "false"
    CLAW_AUDIT_LOG_PATH   — path to audit log (default: ./logs/audit.log)

Usage:
    from claw_audit import get_audit_logger

    audit = get_audit_logger()
    audit.log_request(action="POST /v1/chat/completions", resource="/v1/chat/completions",
                      outcome="success", ip_address="127.0.0.1",
                      user="abc123", details={"model": "llama3.2"})

Requirements:
    Python 3.8+  (stdlib only — no pip installs)
"""

import hashlib
import json
import logging
import logging.handlers
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_AUDIT_LOG_PATH = "./logs/audit.log"
MAX_BYTES = 10 * 1024 * 1024   # 10 MB per file
BACKUP_COUNT = 5


# ═══════════════════════════════════════════════════════════════════════════════
#  JSON Formatter
# ═══════════════════════════════════════════════════════════════════════════════

class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        # The audit entry dict is stored in record.msg by AuditLogger
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, default=str)
        return json.dumps({"message": str(record.msg)}, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditLogger  --  Thread-safe singleton
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLogger:
    """
    Structured JSON audit logger with rotating file output.

    Thread-safe singleton — only one instance exists per process.
    Disabled gracefully when CLAW_AUDIT_ENABLED=false.
    """

    _instance: Optional["AuditLogger"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AuditLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.enabled = os.environ.get(
            "CLAW_AUDIT_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

        self._logger = logging.getLogger("claw-audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if self.enabled:
            self._setup_handler()

    # ── Handler setup ─────────────────────────────────────────────────────

    def _setup_handler(self) -> None:
        """Attach a RotatingFileHandler with JSON formatting."""
        log_path = Path(
            os.environ.get("CLAW_AUDIT_LOG_PATH", DEFAULT_AUDIT_LOG_PATH)
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(_JSONFormatter())
        self._logger.addHandler(handler)

    # ── Token hashing (never log raw tokens) ──────────────────────────────

    @staticmethod
    def _hash_token(token: Optional[str]) -> str:
        """Return a truncated SHA-256 hex digest.  Never stores raw tokens."""
        if not token:
            return "anonymous"
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]

    # ── Core log writer ───────────────────────────────────────────────────

    def _write(
        self,
        event_type: str,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write a single structured audit entry."""
        if not self.enabled:
            return

        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "event_type": event_type,
            "user": self._hash_token(user),
            "action": action,
            "resource": resource,
            "outcome": outcome,
            "ip_address": ip_address,
            "details": details or {},
        }
        self._logger.info(entry)

    # ── Public API ────────────────────────────────────────────────────────

    def log_request(
        self,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an API request (e.g. POST /v1/chat/completions)."""
        self._write("request", action, resource, outcome, ip_address, user, details)

    def log_auth(
        self,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an authentication / authorization event."""
        self._write("auth", action, resource, outcome, ip_address, user, details)

    def log_config_change(
        self,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a configuration change (e.g. strategy reload)."""
        self._write("config_change", action, resource, outcome, ip_address, user, details)

    def log_data_access(
        self,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a data access event (e.g. vault secret retrieval)."""
        self._write("data_access", action, resource, outcome, ip_address, user, details)

    def log_security_event(
        self,
        action: str,
        resource: str,
        outcome: str,
        ip_address: str = "",
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a security event (e.g. rule violation, blocked URL)."""
        self._write("security", action, resource, outcome, ip_address, user, details)


# ═══════════════════════════════════════════════════════════════════════════════
#  Factory
# ═══════════════════════════════════════════════════════════════════════════════

def get_audit_logger() -> AuditLogger:
    """Return the process-wide AuditLogger singleton."""
    return AuditLogger()
