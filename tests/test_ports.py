"""
Tests for shared/claw_ports.py -- Centralized Port Management.
"""

import json
import socket
import sys
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

import claw_ports
from claw_ports import (
    SERVICE_PORTS,
    is_port_free,
    find_free_port,
    get_port,
    get_all_ports,
    save_port_map,
    load_port_map,
    get_service_url,
)


class TestIsPortFree:
    """Tests for is_port_free()."""

    def test_free_port_returns_true(self):
        """An unused high port should be detected as free."""
        # Use port 0 trick to get an OS-assigned free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        # Port is now released, should be free
        assert is_port_free(free_port) is True

    def test_busy_port_returns_false(self):
        """A port with an active listener should be detected as busy."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            busy_port = s.getsockname()[1]
            assert is_port_free(busy_port) is False


class TestFindFreePort:
    """Tests for find_free_port()."""

    def test_unknown_service_raises(self):
        """Requesting an unknown service should raise RuntimeError."""
        try:
            find_free_port("nonexistent-service")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "Unknown service" in str(e)

    def test_env_var_override(self):
        """Environment variable should take priority over default."""
        with patch.dict("os.environ", {"CLAW_WATCHDOG_PORT": "19090"}):
            port = find_free_port("watchdog")
            assert port == 19090

    def test_env_var_invalid_falls_back(self):
        """Invalid env var value should fall back to default resolution."""
        with patch.dict("os.environ", {"CLAW_DASHBOARD_PORT": "not-a-number"}):
            with patch("claw_ports.is_port_free", return_value=True):
                port = find_free_port("dashboard")
                assert port == 9099  # falls back to default

    def test_default_port_when_free(self):
        """When default port is free, it should be returned."""
        with patch("claw_ports.is_port_free", return_value=True):
            port = find_free_port("router")
            assert port == 9095

    def test_fallback_when_default_busy(self):
        """When default is busy, should scan range for a free port."""
        call_count = {"n": 0}

        def mock_is_free(p):
            call_count["n"] += 1
            # First call (default port) returns False; second returns True
            if call_count["n"] == 1:
                return False
            return True

        with patch("claw_ports.is_port_free", side_effect=mock_is_free):
            # zeroclaw has range (3100, 3199) — default 3100 busy, 3101 free
            port = find_free_port("zeroclaw")
            assert port == 3101

    def test_no_free_port_in_range_raises(self):
        """When all ports in range are busy, should raise RuntimeError."""
        with patch("claw_ports.is_port_free", return_value=False):
            try:
                find_free_port("dashboard")  # range (9099, 9099) — single port
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "No free port" in str(e)


class TestGetPort:
    """Tests for get_port() caching behavior."""

    def setup_method(self):
        """Clear the port cache before each test."""
        claw_ports._cache.clear()

    def test_caches_result(self):
        """get_port should return the same value on repeated calls."""
        with patch("claw_ports.find_free_port", return_value=9095) as mock_find:
            port1 = get_port("router")
            port2 = get_port("router")
            assert port1 == port2 == 9095
            # find_free_port should only be called once (cached)
            assert mock_find.call_count == 1

    def test_different_services_resolve_independently(self):
        """Each service should resolve and cache its own port."""
        def mock_find(service):
            return SERVICE_PORTS[service]["default"]

        with patch("claw_ports.find_free_port", side_effect=mock_find):
            router_port = get_port("router")
            memory_port = get_port("memory")
            assert router_port == 9095
            assert memory_port == 9096

    def test_thread_safety(self):
        """Concurrent get_port calls should not corrupt the cache."""
        results = []

        def mock_find(service):
            return SERVICE_PORTS[service]["default"]

        with patch("claw_ports.find_free_port", side_effect=mock_find):
            def worker(svc):
                port = get_port(svc)
                results.append((svc, port))

            threads = [
                threading.Thread(target=worker, args=(svc,))
                for svc in list(SERVICE_PORTS)[:5]
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(results) == 5
            for svc, port in results:
                assert port == SERVICE_PORTS[svc]["default"]


class TestGetAllPorts:
    """Tests for get_all_ports()."""

    def setup_method(self):
        claw_ports._cache.clear()

    def test_returns_all_services(self):
        """get_all_ports should return an entry for every registered service."""
        with patch("claw_ports.is_port_free", return_value=True):
            ports = get_all_ports()
            assert set(ports.keys()) == set(SERVICE_PORTS.keys())

    def test_values_are_ints(self):
        """Every resolved port should be an integer."""
        with patch("claw_ports.is_port_free", return_value=True):
            ports = get_all_ports()
            for name, port in ports.items():
                assert isinstance(port, int), f"{name} port is not int: {port!r}"


class TestSaveLoadPortMap:
    """Tests for save_port_map / load_port_map round-trip."""

    def setup_method(self):
        claw_ports._cache.clear()

    def test_round_trip(self, tmp_path):
        """Saving and loading a port map should produce identical data."""
        map_file = str(tmp_path / "port_map.json")

        with patch("claw_ports.is_port_free", return_value=True):
            save_port_map(map_file)
            loaded = load_port_map(map_file)

        expected = {name: SERVICE_PORTS[name]["default"] for name in SERVICE_PORTS}
        assert loaded == expected

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Loading from a non-existent path should return an empty dict."""
        result = load_port_map(str(tmp_path / "does_not_exist.json"))
        assert result == {}

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        """Loading from a corrupt JSON file should return an empty dict."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        result = load_port_map(str(bad_file))
        assert result == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        """save_port_map should create intermediate directories."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "port_map.json")
        with patch("claw_ports.is_port_free", return_value=True):
            save_port_map(deep_path)
        assert Path(deep_path).exists()


class TestGetServiceUrl:
    """Tests for get_service_url()."""

    def setup_method(self):
        claw_ports._cache.clear()

    def test_basic_url(self):
        """get_service_url should return http://localhost:{port}."""
        with patch("claw_ports.find_free_port", return_value=9095):
            url = get_service_url("router")
            assert url == "http://localhost:9095"

    def test_url_with_path(self):
        """get_service_url with a path should append it correctly."""
        with patch("claw_ports.find_free_port", return_value=9095):
            url = get_service_url("router", "/v1/models")
            assert url == "http://localhost:9095/v1/models"

    def test_url_with_empty_path(self):
        """get_service_url with empty path should have no trailing slash."""
        with patch("claw_ports.find_free_port", return_value=9099):
            url = get_service_url("dashboard", "")
            assert url == "http://localhost:9099"


class TestServicePortsRegistry:
    """Tests for the SERVICE_PORTS registry itself."""

    def test_all_entries_have_required_keys(self):
        """Every entry in SERVICE_PORTS should have default, env, and range."""
        for name, cfg in SERVICE_PORTS.items():
            assert "default" in cfg, f"{name} missing 'default'"
            assert "env" in cfg, f"{name} missing 'env'"
            assert "range" in cfg, f"{name} missing 'range'"

    def test_default_within_range(self):
        """Every default port should fall within its configured range."""
        for name, cfg in SERVICE_PORTS.items():
            lo, hi = cfg["range"]
            default = cfg["default"]
            assert lo <= default <= hi, (
                f"{name}: default {default} outside range ({lo}, {hi})"
            )

    def test_no_duplicate_defaults(self):
        """No two services should share the same default port."""
        defaults = {}
        for name, cfg in SERVICE_PORTS.items():
            port = cfg["default"]
            assert port not in defaults, (
                f"Duplicate default port {port}: {name} and {defaults[port]}"
            )
            defaults[port] = name

    def test_env_var_names_are_unique(self):
        """No two services should share the same environment variable."""
        envs = {}
        for name, cfg in SERVICE_PORTS.items():
            env = cfg["env"]
            assert env not in envs, (
                f"Duplicate env var {env}: {name} and {envs[env]}"
            )
            envs[env] = name
