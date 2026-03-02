#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Prometheus Metrics Collector
=============================================================================
Stdlib-only Prometheus metrics collection for all Claw HTTP services.
Provides counters, gauges, and histograms in Prometheus text exposition
format (text/plain; version=0.0.4) without requiring the prometheus_client
library.

Metric types:
  - request_count        (counter)   — Total requests by method, path, status
  - request_duration_seconds (histogram) — Request latency distribution
  - active_connections   (gauge)     — Currently active HTTP connections
  - error_count          (counter)   — Total error responses (4xx/5xx)

Usage:
  from claw_metrics import MetricsCollector

  collector = MetricsCollector(service="claw-router")

  # In request handler:
  collector.track_request("GET", "/health", 200, 0.003)

  # GET /metrics endpoint:
  body = collector.metrics_handler()  # Returns Prometheus text format

Thread-safe via threading.Lock on all mutating operations.

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import threading
import time
from typing import Any, Dict, List, Optional, Tuple


# -------------------------------------------------------------------------
# Histogram bucket boundaries (seconds) — Prometheus default
# -------------------------------------------------------------------------
DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


# =========================================================================
#  MetricsCollector
# =========================================================================
class MetricsCollector:
    """
    Thread-safe Prometheus metrics collector for Claw HTTP services.

    Collects request counts, duration histograms, active connection gauges,
    and error counters.  Renders metrics in Prometheus text exposition
    format via ``metrics_handler()``.
    """

    def __init__(self, service: str = "claw",
                 buckets: Tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        self._service = service
        self._buckets = buckets
        self._lock = threading.Lock()

        # Counter: {(method, path, status): count}
        self._request_counts: Dict[Tuple[str, str, int], int] = {}

        # Histogram: {(method, path): {bucket_le: count, "sum": float, "count": int}}
        self._request_durations: Dict[Tuple[str, str], Dict[str, Any]] = {}

        # Gauge: active connections
        self._active_connections: int = 0

        # Counter: {(method, path, status): count} — only 4xx/5xx
        self._error_counts: Dict[Tuple[str, str, int], int] = {}

        # Start time for uptime metric
        self._start_time: float = time.time()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def track_request(self, method: str, path: str,
                      status: int, duration: float) -> None:
        """
        Record a completed HTTP request.

        Args:
            method:   HTTP method (GET, POST, etc.)
            path:     Request path (normalized)
            status:   HTTP response status code
            duration: Request duration in seconds
        """
        key = (method, path, status)
        duration_key = (method, path)

        with self._lock:
            # Increment request counter
            self._request_counts[key] = self._request_counts.get(key, 0) + 1

            # Update duration histogram — record in smallest qualifying bucket
            if duration_key not in self._request_durations:
                self._request_durations[duration_key] = self._init_histogram()
            hist = self._request_durations[duration_key]
            placed = False
            for b in self._buckets:
                if not placed and duration <= b:
                    hist[b] = hist.get(b, 0) + 1
                    placed = True
            hist["+Inf"] = hist.get("+Inf", 0) + 1
            hist["sum"] = hist.get("sum", 0.0) + duration
            hist["count"] = hist.get("count", 0) + 1

            # Increment error counter for 4xx/5xx
            if status >= 400:
                self._error_counts[key] = self._error_counts.get(key, 0) + 1

    def inc_active_connections(self) -> None:
        """Increment the active connections gauge."""
        with self._lock:
            self._active_connections += 1

    def dec_active_connections(self) -> None:
        """Decrement the active connections gauge."""
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)

    def metrics_handler(self) -> str:
        """
        Render all collected metrics in Prometheus text exposition format.

        Returns:
            A string in ``text/plain; version=0.0.4; charset=utf-8`` format.
        """
        lines: List[str] = []
        prefix = self._service.replace("-", "_")

        with self._lock:
            # --- request_count (counter) ---
            lines.append(f"# HELP {prefix}_request_count Total HTTP requests.")
            lines.append(f"# TYPE {prefix}_request_count counter")
            for (method, path, status), count in sorted(self._request_counts.items()):
                lines.append(
                    f'{prefix}_request_count{{method="{method}",path="{path}",'
                    f'status="{status}"}} {count}'
                )

            # --- request_duration_seconds (histogram) ---
            lines.append(
                f"# HELP {prefix}_request_duration_seconds "
                f"Request duration in seconds."
            )
            lines.append(f"# TYPE {prefix}_request_duration_seconds histogram")
            for (method, path), hist in sorted(self._request_durations.items()):
                labels = f'method="{method}",path="{path}"'
                cumulative = 0
                for b in self._buckets:
                    cumulative += hist.get(b, 0)
                    lines.append(
                        f"{prefix}_request_duration_seconds_bucket"
                        f'{{{labels},le="{b}"}} {cumulative}'
                    )
                cumulative += hist.get("+Inf", 0) - cumulative
                lines.append(
                    f"{prefix}_request_duration_seconds_bucket"
                    f'{{{labels},le="+Inf"}} {hist.get("+Inf", 0)}'
                )
                lines.append(
                    f"{prefix}_request_duration_seconds_sum"
                    f'{{{labels}}} {hist.get("sum", 0.0):.6f}'
                )
                lines.append(
                    f"{prefix}_request_duration_seconds_count"
                    f'{{{labels}}} {hist.get("count", 0)}'
                )

            # --- active_connections (gauge) ---
            lines.append(
                f"# HELP {prefix}_active_connections "
                f"Currently active HTTP connections."
            )
            lines.append(f"# TYPE {prefix}_active_connections gauge")
            lines.append(
                f"{prefix}_active_connections {self._active_connections}"
            )

            # --- error_count (counter) ---
            lines.append(f"# HELP {prefix}_error_count Total HTTP error responses (4xx/5xx).")
            lines.append(f"# TYPE {prefix}_error_count counter")
            for (method, path, status), count in sorted(self._error_counts.items()):
                lines.append(
                    f'{prefix}_error_count{{method="{method}",path="{path}",'
                    f'status="{status}"}} {count}'
                )

            # --- uptime_seconds (gauge) ---
            uptime = time.time() - self._start_time
            lines.append(f"# HELP {prefix}_uptime_seconds Service uptime in seconds.")
            lines.append(f"# TYPE {prefix}_uptime_seconds gauge")
            lines.append(f"{prefix}_uptime_seconds {uptime:.1f}")

        lines.append("")  # Trailing newline
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """
        Return a dict summary of current metrics (for JSON status endpoints).
        """
        with self._lock:
            total_requests = sum(self._request_counts.values())
            total_errors = sum(self._error_counts.values())
            return {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "active_connections": self._active_connections,
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }

    def reset(self) -> None:
        """Reset all metrics to zero (useful for testing)."""
        with self._lock:
            self._request_counts.clear()
            self._request_durations.clear()
            self._error_counts.clear()
            self._active_connections = 0
            self._start_time = time.time()

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _init_histogram(self) -> Dict[str, Any]:
        """Create an empty histogram bucket dict."""
        hist: Dict[str, Any] = {}
        for b in self._buckets:
            hist[b] = 0
        hist["+Inf"] = 0
        hist["sum"] = 0.0
        hist["count"] = 0
        return hist
