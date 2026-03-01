#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Sliding Window Rate Limiter
=============================================================================
In-memory sliding window rate limiter for HTTP services.  Uses stdlib only
(threading + time) with automatic cleanup of expired entries.

Configuration via environment variables:
  CLAW_RATE_LIMIT   — max requests per window (default: 60)
  CLAW_RATE_WINDOW  — window size in seconds (default: 60)

Usage:
  from claw_ratelimit import RateLimiter

  limiter = RateLimiter()
  allowed, remaining, reset_at = limiter.check("client-key")
  if not allowed:
      # Return 429 Too Many Requests
      pass

Thread-safe.  Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import os
import threading
import time
from typing import Dict, List, Tuple


# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
DEFAULT_RATE_LIMIT = 60   # requests per window
DEFAULT_RATE_WINDOW = 60  # seconds


def _env_int(key: str, default: int) -> int:
    """Read an integer from an environment variable with fallback."""
    val = os.environ.get(key, "")
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return default


# -------------------------------------------------------------------------
# SlidingWindowRateLimiter
# -------------------------------------------------------------------------
class RateLimiter:
    """
    Sliding window rate limiter backed by an in-memory dict of timestamps.

    Each client key (IP address or Bearer token) maintains a list of
    request timestamps.  On each check, timestamps outside the current
    window are pruned.  If the remaining count within the window exceeds
    the configured limit, the request is denied.

    Thread-safe via a threading.Lock.
    """

    def __init__(
        self,
        max_requests: int = 0,
        window_seconds: int = 0,
    ) -> None:
        self.max_requests = max_requests or _env_int(
            "CLAW_RATE_LIMIT", DEFAULT_RATE_LIMIT
        )
        self.window_seconds = window_seconds or _env_int(
            "CLAW_RATE_WINDOW", DEFAULT_RATE_WINDOW
        )
        self._entries: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = max(self.window_seconds * 2, 120)

    def check(self, client_key: str) -> Tuple[bool, int, float]:
        """
        Check whether a request from the given client key is allowed.

        Returns:
            (allowed, remaining, reset_at)
            - allowed:   True if the request is within the rate limit
            - remaining: number of requests remaining in the current window
            - reset_at:  epoch timestamp when the oldest entry in the window
                         expires (i.e., when a slot opens up)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Periodic cleanup of stale keys
            if time.monotonic() - self._last_cleanup > self._cleanup_interval:
                self._cleanup(now)

            # Get or create entry list for this client
            timestamps = self._entries.get(client_key, [])

            # Prune timestamps outside the current window
            timestamps = [t for t in timestamps if t > window_start]

            if len(timestamps) < self.max_requests:
                # Allowed — record this request
                timestamps.append(now)
                self._entries[client_key] = timestamps
                remaining = self.max_requests - len(timestamps)
                reset_at = timestamps[0] + self.window_seconds
                return True, remaining, reset_at
            else:
                # Denied — over the limit
                self._entries[client_key] = timestamps
                remaining = 0
                reset_at = timestamps[0] + self.window_seconds
                return False, remaining, reset_at

    def _cleanup(self, now: float) -> None:
        """
        Remove entries for clients whose timestamps have all expired.

        Called periodically under the lock to prevent unbounded memory
        growth from clients that make a few requests and never return.
        """
        window_start = now - self.window_seconds
        stale_keys = []
        for key, timestamps in self._entries.items():
            # Remove expired timestamps
            fresh = [t for t in timestamps if t > window_start]
            if fresh:
                self._entries[key] = fresh
            else:
                stale_keys.append(key)

        for key in stale_keys:
            del self._entries[key]

        self._last_cleanup = time.monotonic()

    def reset(self, client_key: str) -> None:
        """Clear rate limit state for a specific client key."""
        with self._lock:
            self._entries.pop(client_key, None)

    def reset_all(self) -> None:
        """Clear all rate limit state."""
        with self._lock:
            self._entries.clear()
