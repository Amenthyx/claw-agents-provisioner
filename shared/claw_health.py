#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Unified Health Check Aggregator
=============================================================================
Stdlib-only Python HTTP server that continuously monitors all Claw platform
services and exposes an aggregated health endpoint.  A background thread
periodically polls each service's /health endpoint and caches the results
so that API responses are instant.

Services monitored (ports resolved via env vars, then port_map.json, then defaults):
  router       — CLAW_GATEWAY_PORT       (default 9095)  Gateway Router
  memory       — CLAW_MEMORY_PORT        (default 9096)  Memory Service
  rag          — CLAW_RAG_PORT           (default 9097)  RAG Service
  wizard       — CLAW_WIZARD_PORT        (default 9098)  Setup Wizard API
  dashboard    — CLAW_DASHBOARD_PORT     (default 9099)  Fleet Dashboard
  orchestrator — CLAW_ORCHESTRATOR_PORT  (default 9100)  Multi-Agent Orchestrator
  watchdog     — CLAW_WATCHDOG_PORT      (default 9090)  Process Watchdog
  optimizer    — CLAW_OPTIMIZER_PORT     (default 9091)  Cost Optimizer

Port resolution order:
  1. data/port_map.json   (dynamic ports written by the deploy pipeline)
  2. Environment variable (CLAW_*_PORT)
  3. Hardcoded default

Endpoints:
  GET  /health                — Aggregated health of all services
  GET  /health/{service}      — Individual service health status
  GET  /health/summary        — One-line overall status + counts

Usage:
  python3 shared/claw_health.py --start --port 9094
  python3 shared/claw_health.py --start --port 9094 --interval 15
  python3 shared/claw_health.py --stop
  python3 shared/claw_health.py --status

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import json
import os
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PID_DIR = PROJECT_ROOT / "data" / "health"
PID_FILE = PID_DIR / "health.pid"

DEFAULT_PORT = 9094
DEFAULT_CHECK_INTERVAL = 30  # seconds
PROBE_TIMEOUT = 3.0  # seconds per health probe

# Check interval from environment (overridable at startup via --interval)
CHECK_INTERVAL = int(os.environ.get("CLAW_HEALTH_CHECK_INTERVAL", str(DEFAULT_CHECK_INTERVAL)))

# -------------------------------------------------------------------------
# Service registry — all platform services to monitor
# -------------------------------------------------------------------------
# Ports are resolved from environment variables with sensible defaults.
# A data/port_map.json file (written by the deploy pipeline) can override
# any port at startup — see _apply_port_map() below.
# -------------------------------------------------------------------------
SERVICES: Dict[str, Dict[str, Any]] = {
    "router":       {"port": int(os.environ.get("CLAW_GATEWAY_PORT", "9095")),       "name": "Gateway Router",           "health_path": "/health"},
    "memory":       {"port": int(os.environ.get("CLAW_MEMORY_PORT", "9096")),        "name": "Memory Service",           "health_path": "/health"},
    "rag":          {"port": int(os.environ.get("CLAW_RAG_PORT", "9097")),            "name": "RAG Service",              "health_path": "/health"},
    "wizard":       {"port": int(os.environ.get("CLAW_WIZARD_PORT", "9098")),        "name": "Setup Wizard API",         "health_path": "/health"},
    "dashboard":    {"port": int(os.environ.get("CLAW_DASHBOARD_PORT", "9099")),     "name": "Fleet Dashboard",          "health_path": "/health"},
    "orchestrator": {"port": int(os.environ.get("CLAW_ORCHESTRATOR_PORT", "9100")),  "name": "Multi-Agent Orchestrator", "health_path": "/health"},
    "watchdog":     {"port": int(os.environ.get("CLAW_WATCHDOG_PORT", "9090")),      "name": "Process Watchdog",         "health_path": "/api/status"},
    "optimizer":    {"port": int(os.environ.get("CLAW_OPTIMIZER_PORT", "9091")),     "name": "Cost Optimizer",           "health_path": "/api/optimizer/status"},
}

# -------------------------------------------------------------------------
# Dynamic port discovery — data/port_map.json
# -------------------------------------------------------------------------
PORT_MAP_FILE = PROJECT_ROOT / "data" / "port_map.json"


def _apply_port_map() -> None:
    """Override SERVICES ports from data/port_map.json if the file exists.

    Expected format (service-id → port number):
        {
            "router": 9095,
            "memory": 9096,
            ...
        }

    Unknown keys are silently ignored; missing keys keep their current value.
    """
    if not PORT_MAP_FILE.exists():
        return

    try:
        with open(PORT_MAP_FILE) as f:
            port_map: Dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, IOError) as exc:
        # Log but do not crash — fall back to env / defaults
        print(f"\033[1;33m[health]\033[0m WARNING: could not read {PORT_MAP_FILE}: {exc}",
              file=sys.stderr)
        return

    applied = 0
    for svc_id, port_value in port_map.items():
        if svc_id in SERVICES:
            try:
                SERVICES[svc_id]["port"] = int(port_value)
                applied += 1
            except (ValueError, TypeError):
                pass  # skip non-integer entries

    if applied:
        print(f"\033[0;32m[health]\033[0m Loaded {applied} port(s) from {PORT_MAP_FILE}")


# Apply port map overrides at import time
_apply_port_map()

# -------------------------------------------------------------------------
# Colors (for terminal output)
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[health]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[health]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[health]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[health]{NC} {msg}")


# -------------------------------------------------------------------------
# Health Checker — background poller
# -------------------------------------------------------------------------
class HealthChecker:
    """Background health checker that periodically polls all services.

    Stores the latest status for each service in a thread-safe dict so
    that HTTP handler responses are instantaneous.
    """

    def __init__(self, interval: int = DEFAULT_CHECK_INTERVAL) -> None:
        self._interval = interval
        self._lock = threading.Lock()
        self._statuses: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()

        # Initialize all services as unknown
        for svc_id, svc_info in SERVICES.items():
            self._statuses[svc_id] = {
                "name": svc_info["name"],
                "port": svc_info["port"],
                "status": "unknown",
                "response_time_ms": None,
                "last_checked": None,
                "error": None,
            }

    def start(self) -> None:
        """Start the background polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        log(f"Background health checker started (interval: {self._interval}s)")

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 2)
        log("Background health checker stopped.")

    def _poll_loop(self) -> None:
        """Main polling loop — runs in a daemon thread."""
        # Run an initial check immediately
        self._check_all()

        while self._running:
            time.sleep(self._interval)
            if self._running:
                self._check_all()

    def _check_all(self) -> None:
        """Check all services concurrently using threads."""
        threads: List[Tuple[threading.Thread, str]] = []

        for svc_id in SERVICES:
            t = threading.Thread(target=self._check_one, args=(svc_id,))
            threads.append((t, svc_id))
            t.start()

        for t, _ in threads:
            t.join(timeout=PROBE_TIMEOUT + 2)

    def _check_one(self, svc_id: str) -> None:
        """Probe a single service and update its cached status."""
        svc_info = SERVICES[svc_id]
        port = svc_info["port"]
        health_path = svc_info["health_path"]
        url = f"http://localhost:{port}{health_path}"

        status = "unhealthy"
        response_time_ms: Optional[float] = None
        error_msg: Optional[str] = None

        start = time.time()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
                elapsed = (time.time() - start) * 1000
                response_time_ms = round(elapsed, 1)
                if resp.status == 200:
                    status = "healthy"
                else:
                    status = "degraded"
                    error_msg = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            elapsed = (time.time() - start) * 1000
            response_time_ms = round(elapsed, 1)
            status = "degraded"
            error_msg = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, socket.timeout,
                ConnectionRefusedError) as exc:
            elapsed = (time.time() - start) * 1000
            response_time_ms = round(elapsed, 1)
            status = "unhealthy"
            error_msg = str(exc)
        except Exception as exc:  # Catch-all for unexpected HTTP probe errors
            elapsed = (time.time() - start) * 1000
            response_time_ms = round(elapsed, 1)
            status = "unhealthy"
            error_msg = str(exc)

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        with self._lock:
            self._statuses[svc_id] = {
                "name": svc_info["name"],
                "port": port,
                "status": status,
                "response_time_ms": response_time_ms,
                "last_checked": now,
                "error": error_msg,
            }

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return a snapshot of all service statuses."""
        with self._lock:
            return {k: dict(v) for k, v in self._statuses.items()}

    def get_one(self, svc_id: str) -> Optional[Dict[str, Any]]:
        """Return the status of a single service, or None if unknown."""
        with self._lock:
            entry = self._statuses.get(svc_id)
            return dict(entry) if entry else None

    def get_overall_status(self) -> str:
        """Compute overall platform health.

        - healthy:   all services are healthy
        - degraded:  at least one service is degraded or unhealthy, but not all
        - unhealthy: all services are unhealthy or unknown
        """
        with self._lock:
            statuses = [v["status"] for v in self._statuses.values()]

        if all(s == "healthy" for s in statuses):
            return "healthy"
        if all(s in ("unhealthy", "unknown") for s in statuses):
            return "unhealthy"
        return "degraded"

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self._start_time)


# -------------------------------------------------------------------------
# HTTP Request Handler
# -------------------------------------------------------------------------
class HealthRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the health aggregator."""

    # Class-level reference set by the server
    checker: Optional[HealthChecker] = None

    # Suppress default stderr logging
    def log_message(self, format: str, *args: Any) -> None:
        pass  # Silenced — we use our own logging

    def _send_json(self, status: int, data: Any) -> None:
        """Helper to send a JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    # --- CORS preflight ---
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # --- GET routes ---
    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path in ("", "/"):
            self._handle_root()
        elif path == "/health":
            self._handle_health_all()
        elif path == "/health/summary":
            self._handle_summary()
        elif path.startswith("/health/"):
            service_name = path.split("/health/", 1)[1]
            self._handle_health_one(service_name)
        else:
            self._send_json(404, {"error": "Not found"})

    # --- Endpoint handlers ---

    def _handle_root(self) -> None:
        self._send_json(200, {
            "service": "claw-health-aggregator",
            "version": "1.0.0",
            "description": "Unified health check aggregator for all Claw platform services",
            "endpoints": {
                "GET  /health": "Aggregated health status of all services",
                "GET  /health/{service}": "Individual service health status",
                "GET  /health/summary": "One-line overall status with counts",
            },
        })

    def _handle_health_all(self) -> None:
        if not self.checker:
            self._send_json(503, {"error": "Health checker not initialized"})
            return

        services = self.checker.get_all()
        overall = self.checker.get_overall_status()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Count statuses
        counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}
        for svc in services.values():
            s = svc.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1

        self._send_json(200, {
            "status": overall,
            "services": services,
            "counts": counts,
            "total_services": len(services),
            "uptime_seconds": self.checker.uptime_seconds,
            "timestamp": now,
        })

    def _handle_health_one(self, service_name: str) -> None:
        if not self.checker:
            self._send_json(503, {"error": "Health checker not initialized"})
            return

        # Handle "summary" separately (already handled in do_GET, but safety)
        if service_name == "summary":
            self._handle_summary()
            return

        svc = self.checker.get_one(service_name)
        if svc is None:
            valid = ", ".join(sorted(SERVICES.keys()))
            self._send_json(404, {
                "error": f"Unknown service: {service_name}",
                "valid_services": valid,
            })
            return

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._send_json(200, {
            "service": service_name,
            **svc,
            "timestamp": now,
        })

    def _handle_summary(self) -> None:
        if not self.checker:
            self._send_json(503, {"error": "Health checker not initialized"})
            return

        services = self.checker.get_all()
        overall = self.checker.get_overall_status()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        healthy = sum(1 for s in services.values() if s["status"] == "healthy")
        total = len(services)

        self._send_json(200, {
            "status": overall,
            "healthy": healthy,
            "total": total,
            "summary": f"{healthy}/{total} services healthy",
            "timestamp": now,
        })


# -------------------------------------------------------------------------
# Threaded HTTP server
# -------------------------------------------------------------------------
class ThreadedHealthServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for concurrent request handling."""
    allow_reuse_address = True
    daemon_threads = True


# -------------------------------------------------------------------------
# PID File Management
# -------------------------------------------------------------------------
def _ensure_dirs() -> None:
    """Create required data directories."""
    PID_DIR.mkdir(parents=True, exist_ok=True)


def _write_pid(pid: int) -> None:
    """Write the server PID to the PID file."""
    _ensure_dirs()
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def _read_pid() -> Optional[int]:
    """Read the server PID from the PID file, or None."""
    if not PID_FILE.exists():
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None


def _remove_pid() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except (OSError, TypeError):
        # missing_ok not available on Python 3.7
        if PID_FILE.exists():
            PID_FILE.unlink()


def _is_process_alive(pid: int) -> bool:
    """Check if a process with *pid* is running."""
    if sys.platform == "win32":
        try:
            import subprocess
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in proc.stdout
        except (subprocess.SubprocessError, OSError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, PermissionError):
            return False


def _is_port_in_use(port: int) -> bool:
    """Check if *port* is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


# -------------------------------------------------------------------------
# Server Lifecycle
# -------------------------------------------------------------------------
def start_server(port: int = DEFAULT_PORT, interval: int = CHECK_INTERVAL) -> None:
    """Start the health aggregator server in the foreground."""
    _ensure_dirs()

    # Check for existing instance
    existing_pid = _read_pid()
    if existing_pid and _is_process_alive(existing_pid):
        err(f"Health aggregator already running (PID {existing_pid}). Use --stop first.")
        sys.exit(1)

    # Clean up stale PID
    if existing_pid:
        _remove_pid()

    if _is_port_in_use(port):
        err(f"Port {port} is already in use.")
        sys.exit(1)

    # Create health checker
    checker = HealthChecker(interval=interval)

    # Attach to handler class
    HealthRequestHandler.checker = checker

    # Create server
    server = ThreadedHealthServer(("0.0.0.0", port), HealthRequestHandler)

    # Write PID
    _write_pid(os.getpid())

    # Start background poller
    checker.start()

    # Graceful shutdown on signals
    def shutdown_handler(signum: int, frame: Any) -> None:
        log("Shutting down...")
        checker.stop()
        _remove_pid()
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print()
    print(f"  {BOLD}{CYAN}=== CLAW Health Check Aggregator ==={NC}")
    print()
    print(f"  {BOLD}Listening:{NC}    http://0.0.0.0:{port}")
    print(f"  {BOLD}PID:{NC}          {os.getpid()}")
    print(f"  {BOLD}Interval:{NC}     {interval}s")
    print(f"  {BOLD}Services:{NC}     {len(SERVICES)}")
    print()
    print(f"  {DIM}Monitored services:{NC}")
    for svc_id, svc_info in SERVICES.items():
        print(f"    {svc_id:<14} :{svc_info['port']}  {DIM}— {svc_info['name']}{NC}")
    print()
    print(f"  {DIM}Endpoints:{NC}")
    print(f"    GET  /health              {DIM}— aggregated health status{NC}")
    print(f"    GET  /health/{{service}}    {DIM}— individual service status{NC}")
    print(f"    GET  /health/summary      {DIM}— one-line status summary{NC}")
    print()
    log(f"Health aggregator started on port {port}. Press Ctrl+C to stop.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        checker.stop()
        server.server_close()
        _remove_pid()
        log("Health aggregator stopped.")


def stop_server() -> None:
    """Stop a running health aggregator server via its PID file."""
    pid = _read_pid()
    if not pid:
        info("No PID file found. Health aggregator may not be running.")
        return

    if not _is_process_alive(pid):
        info(f"Process {pid} is not running. Cleaning up stale PID file.")
        _remove_pid()
        return

    log(f"Stopping health aggregator (PID {pid})...")
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, timeout=10,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            # Wait for process to exit
            for _ in range(30):
                if not _is_process_alive(pid):
                    break
                time.sleep(0.1)
            else:
                warn(f"Process {pid} did not exit gracefully. Sending SIGKILL.")
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
    except (OSError, PermissionError) as exc:
        err(f"Failed to stop process {pid}: {exc}")

    _remove_pid()
    log("Health aggregator stopped.")


def show_status() -> None:
    """Print the current health aggregator status."""
    pid = _read_pid()

    print()
    print(f"  {BOLD}{CYAN}=== CLAW Health Aggregator Status ==={NC}")
    print()

    if pid and _is_process_alive(pid):
        print(f"  {BOLD}Status:{NC}  {GREEN}RUNNING{NC}")
        print(f"  {BOLD}PID:{NC}     {pid}")
    elif pid:
        print(f"  {BOLD}Status:{NC}  {YELLOW}STALE PID{NC} (process {pid} not found)")
        _remove_pid()
        print()
        return
    else:
        print(f"  {BOLD}Status:{NC}  {RED}STOPPED{NC}")
        print()
        return

    # Try to reach the health endpoint
    try:
        req = urllib.request.Request(
            f"http://localhost:{DEFAULT_PORT}/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            overall = data.get("status", "unknown")
            counts = data.get("counts", {})
            uptime = data.get("uptime_seconds", 0)

            color = GREEN if overall == "healthy" else (YELLOW if overall == "degraded" else RED)
            print(f"  {BOLD}Overall:{NC} {color}{overall.upper()}{NC}")
            print(f"  {BOLD}Uptime:{NC}  {uptime}s")
            print()

            services = data.get("services", {})
            if services:
                print(f"  {BOLD}Services:{NC}")
                for svc_id, svc in sorted(services.items()):
                    s = svc.get("status", "unknown")
                    sc = GREEN if s == "healthy" else (YELLOW if s == "degraded" else RED)
                    rt = svc.get("response_time_ms")
                    rt_str = f"{rt}ms" if rt is not None else "n/a"
                    p = svc.get("port", "?")
                    print(f"    {svc_id:<14} :{p:<6} {sc}{s:<10}{NC}  {DIM}{rt_str}{NC}")
            print()

            h = counts.get("healthy", 0)
            t = data.get("total_services", 0)
            print(f"  {BOLD}Summary:{NC}  {h}/{t} services healthy")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, KeyError):
        print(f"  {YELLOW}Could not reach health aggregator at localhost:{DEFAULT_PORT}{NC}")

    print()


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 shared/claw_health.py [--start|--stop|--status]")
        print()
        print("Commands:")
        print(f"  --start [--port {DEFAULT_PORT}] [--interval {DEFAULT_CHECK_INTERVAL}]")
        print("                          Start the health aggregator server")
        print("  --stop                  Stop a running health aggregator server")
        print("  --status                Show aggregator status and service health")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--start":
        port = DEFAULT_PORT
        interval = CHECK_INTERVAL

        if "--port" in sys.argv:
            try:
                idx = sys.argv.index("--port")
                port = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                err(f"Invalid --port value. Using default {DEFAULT_PORT}.")

        if "--interval" in sys.argv:
            try:
                idx = sys.argv.index("--interval")
                interval = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                err(f"Invalid --interval value. Using default {DEFAULT_CHECK_INTERVAL}s.")

        start_server(port, interval)

    elif action == "--stop":
        stop_server()

    elif action == "--status":
        show_status()

    else:
        err(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
