#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — API Authentication Module
=============================================================================
Bearer token authentication for all HTTP services.  Validates the
Authorization header against CLAW_API_TOKEN environment variable.

If CLAW_API_TOKEN is not set, authentication is disabled (open access)
to support local development and testing without configuration.

Usage:
  from claw_auth import check_auth

  ok, error_msg = check_auth(self.headers)
  if not ok:
      self._send_json({"error": error_msg}, 401)
      return

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import os
from http.client import HTTPMessage
from typing import Tuple, Union


def _get_token() -> str:
    """Read the expected API token from the environment."""
    return os.environ.get("CLAW_API_TOKEN", "").strip()


def check_auth(headers: Union[HTTPMessage, dict]) -> Tuple[bool, str]:
    """
    Validate Bearer token from the Authorization header.

    Args:
        headers: HTTP request headers (BaseHTTPRequestHandler.headers
                 or a plain dict for testing).

    Returns:
        (ok, error_message)
        - ok:            True if authentication passed (or is disabled)
        - error_message: empty string on success, descriptive error on failure
    """
    expected = _get_token()

    # If no token is configured, auth is disabled (dev mode)
    if not expected:
        return True, ""

    # Extract Authorization header
    if isinstance(headers, dict):
        auth_header = headers.get("Authorization", "")
    else:
        auth_header = headers.get("Authorization", "")

    if not auth_header:
        return False, "Missing Authorization header. Expected: Bearer <token>"

    # Must be Bearer scheme
    if not auth_header.startswith("Bearer "):
        return False, "Invalid Authorization scheme. Expected: Bearer <token>"

    token = auth_header[7:].strip()

    if not token:
        return False, "Empty Bearer token"

    # Constant-time comparison to prevent timing attacks
    if not _constant_time_compare(token, expected):
        return False, "Invalid API token"

    return True, ""


def _constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    Uses XOR comparison on encoded bytes with a length check that
    does not short-circuit.
    """
    a_bytes = a.encode("utf-8")
    b_bytes = b.encode("utf-8")

    if len(a_bytes) != len(b_bytes):
        # Still do work to avoid timing leak on length difference
        result = 1
        for x, y in zip(a_bytes, b_bytes):
            result |= x ^ y
        return False

    result = 0
    for x, y in zip(a_bytes, b_bytes):
        result |= x ^ y

    return result == 0
