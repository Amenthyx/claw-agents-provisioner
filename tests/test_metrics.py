"""
Tests for shared/claw_metrics.py — Prometheus Metrics Collector.
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_metrics import MetricsCollector, DEFAULT_BUCKETS


class TestMetricsCollectorInit:
    """Tests for MetricsCollector initialization."""

    def test_default_service_name(self):
        """MetricsCollector should accept a service name."""
        collector = MetricsCollector(service="test-service")
        output = collector.metrics_handler()
        assert "test_service_request_count" in output

    def test_default_buckets(self):
        """MetricsCollector should use DEFAULT_BUCKETS by default."""
        collector = MetricsCollector(service="test")
        assert collector._buckets == DEFAULT_BUCKETS

    def test_custom_buckets(self):
        """MetricsCollector should accept custom histogram buckets."""
        buckets = (0.1, 0.5, 1.0)
        collector = MetricsCollector(service="test", buckets=buckets)
        assert collector._buckets == buckets

    def test_initial_state_empty(self):
        """New collector should have no requests tracked."""
        collector = MetricsCollector(service="test")
        stats = collector.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["active_connections"] == 0


class TestTrackRequest:
    """Tests for request tracking."""

    def test_track_single_request(self):
        """track_request should increment the request counter."""
        collector = MetricsCollector(service="test")
        collector.track_request("GET", "/health", 200, 0.005)
        stats = collector.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_errors"] == 0

    def test_track_multiple_requests(self):
        """Multiple requests should accumulate correctly."""
        collector = MetricsCollector(service="test")
        collector.track_request("GET", "/health", 200, 0.003)
        collector.track_request("POST", "/api/data", 201, 0.012)
        collector.track_request("GET", "/health", 200, 0.002)
        stats = collector.get_stats()
        assert stats["total_requests"] == 3

    def test_track_error_request(self):
        """4xx and 5xx responses should increment the error counter."""
        collector = MetricsCollector(service="test")
        collector.track_request("GET", "/missing", 404, 0.001)
        collector.track_request("POST", "/api/fail", 500, 0.100)
        collector.track_request("GET", "/health", 200, 0.002)
        stats = collector.get_stats()
        assert stats["total_requests"] == 3
        assert stats["total_errors"] == 2

    def test_track_400_is_error(self):
        """400 status should count as an error."""
        collector = MetricsCollector(service="test")
        collector.track_request("POST", "/api/data", 400, 0.001)
        stats = collector.get_stats()
        assert stats["total_errors"] == 1

    def test_track_399_is_not_error(self):
        """399 status should not count as an error."""
        collector = MetricsCollector(service="test")
        collector.track_request("GET", "/redirect", 301, 0.001)
        stats = collector.get_stats()
        assert stats["total_errors"] == 0


class TestActiveConnections:
    """Tests for the active connections gauge."""

    def test_increment_decrement(self):
        """Active connections should track inc/dec correctly."""
        collector = MetricsCollector(service="test")
        collector.inc_active_connections()
        collector.inc_active_connections()
        assert collector.get_stats()["active_connections"] == 2

        collector.dec_active_connections()
        assert collector.get_stats()["active_connections"] == 1

    def test_decrement_below_zero(self):
        """Active connections should not go below zero."""
        collector = MetricsCollector(service="test")
        collector.dec_active_connections()
        collector.dec_active_connections()
        assert collector.get_stats()["active_connections"] == 0


class TestMetricsHandler:
    """Tests for Prometheus text exposition output."""

    def test_output_contains_help_lines(self):
        """Output should contain HELP comments for all metric types."""
        collector = MetricsCollector(service="myapp")
        collector.track_request("GET", "/health", 200, 0.003)
        output = collector.metrics_handler()

        assert "# HELP myapp_request_count" in output
        assert "# HELP myapp_request_duration_seconds" in output
        assert "# HELP myapp_active_connections" in output
        assert "# HELP myapp_error_count" in output
        assert "# HELP myapp_uptime_seconds" in output

    def test_output_contains_type_lines(self):
        """Output should contain TYPE annotations for all metric types."""
        collector = MetricsCollector(service="myapp")
        collector.track_request("GET", "/health", 200, 0.003)
        output = collector.metrics_handler()

        assert "# TYPE myapp_request_count counter" in output
        assert "# TYPE myapp_request_duration_seconds histogram" in output
        assert "# TYPE myapp_active_connections gauge" in output
        assert "# TYPE myapp_error_count counter" in output
        assert "# TYPE myapp_uptime_seconds gauge" in output

    def test_request_count_labels(self):
        """Request count should include method, path, and status labels."""
        collector = MetricsCollector(service="myapp")
        collector.track_request("GET", "/health", 200, 0.003)
        output = collector.metrics_handler()

        assert 'myapp_request_count{method="GET",path="/health",status="200"} 1' in output

    def test_histogram_buckets(self):
        """Histogram output should include bucket boundaries."""
        collector = MetricsCollector(service="myapp")
        collector.track_request("GET", "/health", 200, 0.003)
        output = collector.metrics_handler()

        # Should have le="0.005" bucket (request at 0.003 falls in it)
        assert 'le="0.005"' in output
        # Should have le="+Inf" bucket
        assert 'le="+Inf"' in output
        # Should have _sum and _count
        assert "myapp_request_duration_seconds_sum" in output
        assert "myapp_request_duration_seconds_count" in output

    def test_histogram_cumulative_counts(self):
        """Histogram buckets should be cumulative."""
        buckets = (0.01, 0.1, 1.0)
        collector = MetricsCollector(service="myapp", buckets=buckets)
        # Request at 0.005s falls in the 0.01 bucket
        collector.track_request("GET", "/fast", 200, 0.005)
        # Request at 0.05s falls in the 0.1 bucket
        collector.track_request("GET", "/fast", 200, 0.05)
        output = collector.metrics_handler()

        # le=0.01 should have 1 (only the 0.005 request)
        assert 'le="0.01"} 1' in output
        # le=0.1 should have 2 (cumulative: 0.005 + 0.05)
        assert 'le="0.1"} 2' in output
        # le=1.0 should have 2
        assert 'le="1.0"} 2' in output
        # le=+Inf should have 2
        assert 'le="+Inf"} 2' in output

    def test_error_count_labels(self):
        """Error count should include method, path, and status labels."""
        collector = MetricsCollector(service="myapp")
        collector.track_request("POST", "/api/fail", 500, 0.050)
        output = collector.metrics_handler()

        assert 'myapp_error_count{method="POST",path="/api/fail",status="500"} 1' in output

    def test_active_connections_in_output(self):
        """Active connections gauge should appear in output."""
        collector = MetricsCollector(service="myapp")
        collector.inc_active_connections()
        collector.inc_active_connections()
        collector.inc_active_connections()
        output = collector.metrics_handler()

        assert "myapp_active_connections 3" in output

    def test_uptime_in_output(self):
        """Uptime gauge should appear in output and be positive."""
        collector = MetricsCollector(service="myapp")
        output = collector.metrics_handler()

        assert "myapp_uptime_seconds" in output
        # Parse the uptime value
        for line in output.splitlines():
            if line.startswith("myapp_uptime_seconds") and not line.startswith("#"):
                value = float(line.split()[-1])
                assert value >= 0.0

    def test_service_name_sanitization(self):
        """Hyphens in service name should be replaced with underscores."""
        collector = MetricsCollector(service="claw-router")
        collector.track_request("GET", "/health", 200, 0.001)
        output = collector.metrics_handler()

        assert "claw_router_request_count" in output
        assert "claw-router" not in output.split("{")[0]  # Prefix should not have hyphen

    def test_empty_metrics(self):
        """Output should be valid even with no requests tracked."""
        collector = MetricsCollector(service="myapp")
        output = collector.metrics_handler()

        # Should still have the metric type declarations
        assert "# HELP myapp_request_count" in output
        assert "# TYPE myapp_active_connections gauge" in output
        assert "myapp_active_connections 0" in output

    def test_trailing_newline(self):
        """Output should end with a newline."""
        collector = MetricsCollector(service="myapp")
        output = collector.metrics_handler()
        assert output.endswith("\n")


class TestGetStats:
    """Tests for the get_stats() summary method."""

    def test_stats_structure(self):
        """get_stats should return the expected keys."""
        collector = MetricsCollector(service="test")
        stats = collector.get_stats()
        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "active_connections" in stats
        assert "uptime_seconds" in stats

    def test_stats_uptime_positive(self):
        """Uptime should be a non-negative number."""
        collector = MetricsCollector(service="test")
        stats = collector.get_stats()
        assert stats["uptime_seconds"] >= 0.0


class TestReset:
    """Tests for the reset() method."""

    def test_reset_clears_all(self):
        """reset should clear all counters and gauges."""
        collector = MetricsCollector(service="test")
        collector.track_request("GET", "/health", 200, 0.003)
        collector.track_request("POST", "/api/fail", 500, 0.100)
        collector.inc_active_connections()

        collector.reset()

        stats = collector.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["active_connections"] == 0


class TestThreadSafety:
    """Tests for thread safety of MetricsCollector."""

    def test_concurrent_tracking(self):
        """Multiple threads tracking requests should not corrupt state."""
        collector = MetricsCollector(service="test")
        num_threads = 10
        requests_per_thread = 100

        def track_requests():
            for _ in range(requests_per_thread):
                collector.track_request("GET", "/health", 200, 0.001)

        threads = [threading.Thread(target=track_requests) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = collector.get_stats()
        assert stats["total_requests"] == num_threads * requests_per_thread

    def test_concurrent_connections(self):
        """Concurrent inc/dec of active connections should be consistent."""
        collector = MetricsCollector(service="test")
        num_threads = 50

        def simulate_connection():
            collector.inc_active_connections()
            time.sleep(0.001)
            collector.dec_active_connections()

        threads = [threading.Thread(target=simulate_connection) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all connections complete, active should be 0
        assert collector.get_stats()["active_connections"] == 0
