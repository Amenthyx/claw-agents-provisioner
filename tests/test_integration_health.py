"""
Integration tests for the Health Aggregator — verifies service polling,
status aggregation, and the HealthChecker lifecycle with mocked network.
"""

import json
import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_health import HealthChecker, SERVICES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checker():
    """Create a HealthChecker with a fast interval for testing."""
    hc = HealthChecker(interval=1)
    yield hc
    hc.stop()


# ---------------------------------------------------------------------------
# HealthChecker initialization
# ---------------------------------------------------------------------------

class TestHealthCheckerInit:
    """Tests for HealthChecker initialization and defaults."""

    def test_all_services_initialized_as_unknown(self, checker):
        """All services should start with 'unknown' status."""
        statuses = checker.get_all()
        for svc_id, status in statuses.items():
            assert status["status"] == "unknown"
            assert status["last_checked"] is None
            assert status["response_time_ms"] is None

    def test_all_known_services_present(self, checker):
        """All registered services should appear in the status map."""
        statuses = checker.get_all()
        for svc_id in SERVICES:
            assert svc_id in statuses
            assert "name" in statuses[svc_id]
            assert "port" in statuses[svc_id]

    def test_initial_overall_status(self, checker):
        """Overall status should be 'unhealthy' when all services are unknown."""
        status = checker.get_overall_status()
        assert status in ("unhealthy", "unknown")


# ---------------------------------------------------------------------------
# Individual service check (mocked network)
# ---------------------------------------------------------------------------

class TestServiceCheckMocked:
    """Tests individual service health checks with mocked HTTP."""

    def test_healthy_service(self, checker):
        """A service returning HTTP 200 should be marked healthy."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            checker._check_one("router")

        status = checker.get_one("router")
        assert status is not None
        assert status["status"] == "healthy"
        assert status["response_time_ms"] is not None
        assert status["last_checked"] is not None
        assert status["error"] is None

    def test_unhealthy_service_connection_refused(self, checker):
        """A service that refuses connections should be marked unhealthy."""
        with patch("claw_health.urllib.request.urlopen",
                   side_effect=ConnectionRefusedError("Connection refused")):
            checker._check_one("memory")

        status = checker.get_one("memory")
        assert status is not None
        assert status["status"] == "unhealthy"
        assert status["error"] is not None
        assert "refused" in status["error"].lower()

    def test_degraded_service_http_error(self, checker):
        """A service returning HTTP error should be marked degraded."""
        import urllib.error
        error = urllib.error.HTTPError(
            url="http://localhost:9097/health",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        with patch("claw_health.urllib.request.urlopen", side_effect=error):
            checker._check_one("rag")

        status = checker.get_one("rag")
        assert status is not None
        assert status["status"] == "degraded"
        assert "503" in status["error"]


# ---------------------------------------------------------------------------
# Status aggregation
# ---------------------------------------------------------------------------

class TestStatusAggregation:
    """Tests overall status computation from individual service statuses."""

    def test_all_healthy_gives_healthy(self, checker):
        """When all services are healthy, overall should be healthy."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            for svc_id in SERVICES:
                checker._check_one(svc_id)

        assert checker.get_overall_status() == "healthy"

    def test_all_unhealthy_gives_unhealthy(self, checker):
        """When all services are unhealthy, overall should be unhealthy."""
        with patch("claw_health.urllib.request.urlopen",
                   side_effect=ConnectionRefusedError("refused")):
            for svc_id in SERVICES:
                checker._check_one(svc_id)

        assert checker.get_overall_status() == "unhealthy"

    def test_mixed_status_gives_degraded(self, checker):
        """When some services are healthy and some unhealthy, overall should be degraded."""
        # Make router healthy
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            checker._check_one("router")

        # Make all others unhealthy
        with patch("claw_health.urllib.request.urlopen",
                   side_effect=ConnectionRefusedError("refused")):
            for svc_id in SERVICES:
                if svc_id != "router":
                    checker._check_one(svc_id)

        assert checker.get_overall_status() == "degraded"


# ---------------------------------------------------------------------------
# Get individual service
# ---------------------------------------------------------------------------

class TestGetIndividualService:
    """Tests retrieving individual service status."""

    def test_get_existing_service(self, checker):
        """get_one for a known service should return its status."""
        status = checker.get_one("router")
        assert status is not None
        assert status["name"] == SERVICES["router"]["name"]

    def test_get_nonexistent_service(self, checker):
        """get_one for an unknown service should return None."""
        status = checker.get_one("nonexistent-service")
        assert status is None


# ---------------------------------------------------------------------------
# Uptime tracking
# ---------------------------------------------------------------------------

class TestUptimeTracking:
    """Tests uptime computation."""

    def test_uptime_increases(self, checker):
        """Uptime should be positive and increase over time."""
        uptime_1 = checker.uptime_seconds
        assert uptime_1 >= 0

        time.sleep(0.1)
        uptime_2 = checker.uptime_seconds
        assert uptime_2 >= uptime_1


# ---------------------------------------------------------------------------
# Background polling integration
# ---------------------------------------------------------------------------

class TestBackgroundPollingIntegration:
    """Tests that the background polling thread works correctly."""

    def test_start_and_stop(self):
        """HealthChecker should start and stop its background thread cleanly."""
        hc = HealthChecker(interval=60)  # Long interval, won't actually poll
        hc.start()
        assert hc._running is True
        assert hc._thread is not None
        assert hc._thread.is_alive()

        hc.stop()
        assert hc._running is False

    def test_poll_updates_statuses(self):
        """After a poll cycle, all services should have last_checked set."""
        hc = HealthChecker(interval=60)

        # Mock all services as connection refused (fast failure)
        with patch("claw_health.urllib.request.urlopen",
                   side_effect=ConnectionRefusedError("refused")):
            hc._check_all()

        statuses = hc.get_all()
        for svc_id, status in statuses.items():
            assert status["last_checked"] is not None
            assert status["status"] == "unhealthy"

        hc.stop()


# ---------------------------------------------------------------------------
# Service registry integration
# ---------------------------------------------------------------------------

class TestServiceRegistryIntegration:
    """Tests that SERVICES registry has correct configuration."""

    def test_all_services_have_required_fields(self):
        """Every service should have port, name, and health_path."""
        for svc_id, svc_info in SERVICES.items():
            assert "port" in svc_info, f"Service {svc_id} missing 'port'"
            assert "name" in svc_info, f"Service {svc_id} missing 'name'"
            assert "health_path" in svc_info, f"Service {svc_id} missing 'health_path'"
            assert isinstance(svc_info["port"], int)

    def test_no_port_conflicts(self):
        """No two services should share the same default port."""
        ports = [svc["port"] for svc in SERVICES.values()]
        assert len(ports) == len(set(ports)), "Duplicate ports detected in SERVICES"

    def test_expected_services_registered(self):
        """Core services should be registered."""
        expected = {"router", "memory", "rag", "orchestrator", "dashboard", "wizard"}
        registered = set(SERVICES.keys())
        for svc in expected:
            assert svc in registered, f"Expected service '{svc}' not in SERVICES"


# ---------------------------------------------------------------------------
# Port map override integration
# ---------------------------------------------------------------------------

class TestPortMapIntegration:
    """Tests that port_map.json overrides work correctly."""

    def test_port_map_overrides_defaults(self, tmp_path):
        """A port_map.json should override default service ports."""
        port_map = {"router": 19095, "memory": 19096}
        port_map_file = tmp_path / "port_map.json"
        port_map_file.write_text(json.dumps(port_map))

        # Temporarily override PORT_MAP_FILE
        import claw_health
        orig_pmap = claw_health.PORT_MAP_FILE
        orig_services = {k: dict(v) for k, v in claw_health.SERVICES.items()}

        try:
            claw_health.PORT_MAP_FILE = port_map_file
            claw_health._apply_port_map()

            assert claw_health.SERVICES["router"]["port"] == 19095
            assert claw_health.SERVICES["memory"]["port"] == 19096
        finally:
            # Restore original
            claw_health.PORT_MAP_FILE = orig_pmap
            for k, v in orig_services.items():
                claw_health.SERVICES[k] = v

    def test_missing_port_map_no_crash(self, tmp_path):
        """Missing port_map.json should not crash."""
        import claw_health
        orig_pmap = claw_health.PORT_MAP_FILE

        try:
            claw_health.PORT_MAP_FILE = tmp_path / "nonexistent.json"
            # Should not raise
            claw_health._apply_port_map()
        finally:
            claw_health.PORT_MAP_FILE = orig_pmap

    def test_invalid_port_map_no_crash(self, tmp_path):
        """Invalid JSON in port_map.json should not crash."""
        import claw_health
        orig_pmap = claw_health.PORT_MAP_FILE

        bad_file = tmp_path / "bad_port_map.json"
        bad_file.write_text("not valid json {{{")

        try:
            claw_health.PORT_MAP_FILE = bad_file
            # Should not raise, just warn
            claw_health._apply_port_map()
        finally:
            claw_health.PORT_MAP_FILE = orig_pmap


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestHealthCheckerThreadSafety:
    """Tests that concurrent access to HealthChecker is safe."""

    def test_concurrent_reads_during_check(self, checker):
        """Reading status while checking should not deadlock or crash."""
        errors = []

        def reader():
            try:
                for _ in range(20):
                    checker.get_all()
                    checker.get_overall_status()
                    checker.get_one("router")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                with patch("claw_health.urllib.request.urlopen",
                           side_effect=ConnectionRefusedError("refused")):
                    for _ in range(5):
                        checker._check_all()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
