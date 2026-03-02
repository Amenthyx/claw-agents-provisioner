#!/usr/bin/env python3
"""
Claw Agents Watchdog — Zero-Token Reliability Monitor

Continuously monitors Claw agent containers, channel connectivity,
and LLM API reachability.  Sends Telegram alerts on state changes
and can auto-restart failed containers.  Uses ZERO LLM tokens.

Checks performed (all free / no tokens):
  1. Docker container status  (docker inspect)
  2. Health endpoint response  (existing per-agent health probes)
  3. TCP port reachability     (socket connect)
  4. Channel API connectivity  (Telegram getMe, Discord /gateway, etc.)
  5. LLM API reachability      (TCP handshake only, no auth)
  6. Container resource usage   (docker stats)

Usage:
    python shared/claw_watchdog.py                              # default config
    python shared/claw_watchdog.py -c shared/watchdog.json      # custom config
    python shared/claw_watchdog.py --once                       # single check, exit

Requirements:
    Python 3.8+  (stdlib only — no pip installs)
"""

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ═════════════════════════════════════════════════════════════════════════════
#  Configuration Defaults
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "check_interval": 30,
    "failure_threshold": 3,
    "alert_cooldown": 300,
    "auto_restart": True,
    "dashboard_port": 9090,
    "log_file": None,

    "telegram_alerts": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },

    "agents": [],

    "connectivity": {
        "telegram": {
            "enabled": False,
            "bot_token": "",
        },
        "discord": {
            "enabled": False,
        },
        "llm_endpoints": [],
    },
}

# Agent config example (for reference):
# {
#   "name": "zeroclaw-lucia",
#   "container": "lucia-zeroclaw-1",
#   "port": 3100,
#   "health_url": null,
#   "health_cmd": "docker exec {container} zeroclaw doctor",
#   "auto_restart": true
# }


# ═════════════════════════════════════════════════════════════════════════════
#  Logging
# ═════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("watchdog")


def setup_logging(log_file=None):
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)


# ═════════════════════════════════════════════════════════════════════════════
#  Check Functions  (all zero-cost, no LLM tokens)
# ═════════════════════════════════════════════════════════════════════════════

def check_container_running(container_name: str) -> dict:
    """Check if a Docker container is running via `docker inspect`."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format",
             "{{.State.Status}}|{{.State.Health.Status}}|{{.State.StartedAt}}",
             container_name],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"ok": False, "detail": "container not found"}

        parts = result.stdout.strip().split("|")
        status = parts[0] if len(parts) > 0 else "unknown"
        health = parts[1] if len(parts) > 1 else "none"
        started = parts[2] if len(parts) > 2 else ""

        ok = status == "running"
        return {
            "ok": ok,
            "status": status,
            "health": health,
            "started_at": started,
            "detail": f"{status} (health: {health})" if ok else f"not running: {status}",
        }
    except FileNotFoundError:
        return {"ok": False, "detail": "docker not installed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "docker inspect timed out"}
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        return {"ok": False, "detail": str(e)}


def check_tcp_port(host: str, port: int, timeout: float = 5.0) -> dict:
    """Check if a TCP port is reachable (socket connect)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "detail": f"{host}:{port} reachable"}
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {"ok": False, "detail": f"{host}:{port} — {e}"}


def check_health_url(url: str, timeout: float = 10.0) -> dict:
    """HTTP GET a health endpoint and check for 2xx response."""
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            ok = 200 <= code < 300
            return {"ok": ok, "detail": f"HTTP {code}"}
    except URLError as e:
        return {"ok": False, "detail": str(e.reason)}
    except (OSError, socket.timeout, ValueError) as e:
        return {"ok": False, "detail": str(e)}


def check_health_cmd(cmd: str, timeout: float = 15.0) -> dict:
    """Run a shell command and check exit code 0."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        ok = result.returncode == 0
        detail = result.stdout.strip()[:200] if ok else result.stderr.strip()[:200]
        return {"ok": ok, "detail": detail or ("passed" if ok else "failed")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"command timed out ({timeout}s)"}
    except (subprocess.SubprocessError, OSError) as e:
        return {"ok": False, "detail": str(e)}


def check_container_resources(container_name: str) -> dict:
    """Get CPU/memory usage via `docker stats --no-stream`."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", container_name],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {}

        parts = result.stdout.strip().split("|")
        return {
            "cpu_percent": parts[0].strip() if len(parts) > 0 else "?",
            "mem_usage": parts[1].strip() if len(parts) > 1 else "?",
            "mem_percent": parts[2].strip() if len(parts) > 2 else "?",
        }
    except (subprocess.SubprocessError, OSError, ValueError):
        return {}


def check_telegram_api(bot_token: str) -> dict:
    """Call Telegram getMe (free, returns bot info)."""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    return check_health_url(url, timeout=10.0)


def check_discord_api() -> dict:
    """Call Discord /gateway (public, no auth needed)."""
    url = "https://discord.com/api/v10/gateway"
    return check_health_url(url, timeout=10.0)


def check_llm_endpoint(host: str, port: int = 443) -> dict:
    """TCP handshake to LLM API host (zero tokens, just connectivity)."""
    return check_tcp_port(host, port, timeout=5.0)


# ═════════════════════════════════════════════════════════════════════════════
#  Agent State Tracker
# ═════════════════════════════════════════════════════════════════════════════

class AgentState:
    """Tracks the state of a single monitored agent."""

    def __init__(self, name: str):
        self.name = name
        self.status = "unknown"        # healthy, unhealthy, unknown
        self.consecutive_failures = 0
        self.last_check = None
        self.last_healthy = None
        self.last_alert = None
        self.checks = {}               # check_name → result dict
        self.resources = {}
        self.restart_count = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
            "last_healthy": self.last_healthy,
            "restart_count": self.restart_count,
            "checks": self.checks,
            "resources": self.resources,
        }


# ═════════════════════════════════════════════════════════════════════════════
#  Telegram Alerting  (bot API only — zero LLM tokens)
# ═════════════════════════════════════════════════════════════════════════════

def send_telegram_alert(bot_token: str, chat_id: str, message: str):
    """Send a plain-text Telegram message via Bot API (free)."""
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    try:
        req = Request(url, data=payload, method="POST",
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10):
            pass
    except (URLError, OSError, ValueError) as e:
        logger.warning(f"Failed to send Telegram alert: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  Container Restart
# ═════════════════════════════════════════════════════════════════════════════

def restart_container(container_name: str) -> bool:
    """Restart a Docker container."""
    try:
        result = subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError) as e:
        logger.error(f"Failed to restart {container_name}: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
#  Dashboard HTTP Server
# ═════════════════════════════════════════════════════════════════════════════

class DashboardHandler(BaseHTTPRequestHandler):
    """Serves /status as JSON."""

    watchdog = None  # set by Watchdog before starting server

    def do_GET(self):
        if self.path == "/status" or self.path == "/":
            data = self.watchdog.get_status_json() if self.watchdog else "{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # suppress default HTTP logs


# ═════════════════════════════════════════════════════════════════════════════
#  Main Watchdog
# ═════════════════════════════════════════════════════════════════════════════

class Watchdog:
    """Continuous monitoring loop for Claw agents."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.agents: dict[str, AgentState] = {}
        self.connectivity_state: dict[str, dict] = {}
        self.started_at = None
        self._dal = None

        # Try to initialize DAL for persistence
        try:
            from claw_dal import DAL
            self._dal = DAL.get_instance()
            logger.info("DAL connected — health data will persist")
        except (ImportError, RuntimeError, OSError):
            logger.info("DAL not available — health data in-memory only")

        # Initialize agent states
        for agent_cfg in config.get("agents", []):
            name = agent_cfg["name"]
            self.agents[name] = AgentState(name)

        # Recover previous state from DAL on restart
        if self._dal:
            try:
                for row in self._dal.agents.list_all():
                    name = row.get("name", "")
                    if name in self.agents:
                        prev_status = row.get("status", "unknown")
                        if prev_status in ("healthy", "unhealthy", "degraded"):
                            self.agents[name].status = prev_status
                        self.agents[name].last_healthy = row.get("last_seen")
            except (KeyError, ValueError, RuntimeError) as e:
                logger.debug(f"Could not recover state from DAL: {e}")

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _alert(self, message: str):
        """Send alert via configured channels."""
        tg = self.config.get("telegram_alerts", {})
        if tg.get("enabled"):
            send_telegram_alert(tg["bot_token"], tg["chat_id"], message)

    def _check_agent(self, agent_cfg: dict):
        """Run all checks for a single agent."""
        name = agent_cfg["name"]
        container = agent_cfg.get("container", "")
        port = agent_cfg.get("port")
        health_url = agent_cfg.get("health_url")
        health_cmd = agent_cfg.get("health_cmd", "")
        can_restart = agent_cfg.get("auto_restart",
                                     self.config.get("auto_restart", True))

        state = self.agents[name]
        state.last_check = self._now()
        all_ok = True

        # Check 1: Container running
        if container:
            result = check_container_running(container)
            state.checks["container"] = result
            if not result["ok"]:
                all_ok = False

        # Check 2: TCP port reachable
        if port:
            result = check_tcp_port("localhost", port)
            state.checks["port"] = result
            if not result["ok"]:
                all_ok = False

        # Check 3: Health URL
        if health_url:
            result = check_health_url(health_url)
            state.checks["health_url"] = result
            if not result["ok"]:
                all_ok = False

        # Check 4: Health command
        if health_cmd:
            cmd = health_cmd.replace("{container}", container)
            result = check_health_cmd(cmd)
            state.checks["health_cmd"] = result
            if not result["ok"]:
                all_ok = False

        # Check 5: Resource usage (informational, doesn't affect status)
        if container:
            state.resources = check_container_resources(container)

        # Persist check results to DAL
        if self._dal:
            try:
                health_detail = json.dumps(state.checks)
                self._dal.agents.update_status(
                    name, state.status if state.status != "unknown" else "healthy" if all_ok else "degraded",
                    health_detail=health_detail,
                )
                self._dal.performance.record(
                    "health_check", 1.0 if all_ok else 0.0,
                    tags={"agent": name},
                )
            except (RuntimeError, OSError, KeyError) as e:
                logger.debug(f"DAL persist failed for {name}: {e}")

        # Update state
        previous_status = state.status
        threshold = self.config.get("failure_threshold", 3)
        cooldown = self.config.get("alert_cooldown", 300)

        if all_ok:
            if state.consecutive_failures > 0:
                downtime = ""
                if state.last_healthy:
                    try:
                        dt_last = datetime.fromisoformat(
                            state.last_healthy.replace("Z", "+00:00"))
                        dt_now = datetime.now(timezone.utc)
                        secs = int((dt_now - dt_last).total_seconds())
                        mins, s = divmod(secs, 60)
                        downtime = f"\nDowntime: {mins}m {s}s"
                    except (ValueError, TypeError, AttributeError):
                        pass
                if previous_status == "unhealthy":
                    logger.info(f"RECOVERED  {name}")
                    self._alert(
                        f"*RECOVERED*  `{name}` is back up{downtime}\n"
                        f"Time: `{self._now()}`"
                    )

            state.status = "healthy"
            state.consecutive_failures = 0
            state.last_healthy = self._now()
        else:
            state.consecutive_failures += 1

            if state.consecutive_failures >= threshold:
                state.status = "unhealthy"

                # Alert (with cooldown)
                now_ts = time.time()
                last_alert_ts = 0
                if state.last_alert:
                    try:
                        dt = datetime.fromisoformat(
                            state.last_alert.replace("Z", "+00:00"))
                        last_alert_ts = dt.timestamp()
                    except (ValueError, TypeError, AttributeError):
                        pass

                if now_ts - last_alert_ts > cooldown:
                    failed_checks = [
                        k for k, v in state.checks.items() if not v.get("ok")
                    ]
                    logger.warning(
                        f"ALERT  {name}  failures={state.consecutive_failures}"
                        f"  checks={failed_checks}"
                    )
                    # Log security event for sustained failure
                    if self._dal:
                        try:
                            self._dal.security_events.log_event(
                                agent_id=name,
                                event_type="agent_health_failure",
                                severity="error",
                                details=json.dumps({
                                    "failed_checks": failed_checks,
                                    "consecutive": state.consecutive_failures,
                                }),
                            )
                        except (RuntimeError, OSError, KeyError):
                            pass
                    self._alert(
                        f"*ALERT*  `{name}` is *DOWN*\n"
                        f"Container: `{container}`\n"
                        f"Failed: {', '.join(failed_checks)}\n"
                        f"Consecutive failures: {state.consecutive_failures}\n"
                        f"Time: `{self._now()}`"
                    )
                    state.last_alert = self._now()

                # Auto-restart
                if can_restart and container:
                    if state.consecutive_failures == threshold:
                        logger.info(f"AUTO-RESTART  {name}  ({container})")
                        ok = restart_container(container)
                        state.restart_count += 1
                        self._alert(
                            f"*AUTO-RESTART*  `{name}`\n"
                            f"Container: `{container}`\n"
                            f"Success: {'yes' if ok else 'no'}\n"
                            f"Total restarts: {state.restart_count}"
                        )
            else:
                state.status = "degraded"

    def _check_connectivity(self):
        """Check channel and LLM API connectivity."""
        conn = self.config.get("connectivity", {})

        # Telegram
        tg = conn.get("telegram", {})
        if tg.get("enabled") and tg.get("bot_token"):
            self.connectivity_state["telegram"] = check_telegram_api(
                tg["bot_token"])

        # Discord
        dc = conn.get("discord", {})
        if dc.get("enabled"):
            self.connectivity_state["discord"] = check_discord_api()

        # LLM endpoints (TCP only)
        for endpoint in conn.get("llm_endpoints", []):
            host = endpoint.get("host", "")
            port = endpoint.get("port", 443)
            label = endpoint.get("name", host)
            if host:
                self.connectivity_state[f"llm:{label}"] = check_llm_endpoint(
                    host, port)

    def run_once(self):
        """Execute a single check cycle."""
        for agent_cfg in self.config.get("agents", []):
            try:
                self._check_agent(agent_cfg)
            except (URLError, OSError, subprocess.SubprocessError, KeyError, ValueError) as e:
                logger.error(f"Error checking {agent_cfg.get('name')}: {e}")

        try:
            self._check_connectivity()
        except (URLError, OSError, socket.timeout, ValueError) as e:
            logger.error(f"Error checking connectivity: {e}")

    def get_status_json(self) -> str:
        """Return current status as JSON string."""
        agents_status = {
            name: state.to_dict() for name, state in self.agents.items()
        }
        overall = "healthy"
        for state in self.agents.values():
            if state.status == "unhealthy":
                overall = "unhealthy"
                break
            if state.status == "degraded":
                overall = "degraded"

        return json.dumps({
            "overall": overall,
            "started_at": self.started_at,
            "last_check": self._now(),
            "check_interval": self.config.get("check_interval", 30),
            "agents": agents_status,
            "connectivity": {
                k: v for k, v in self.connectivity_state.items()
            },
        }, indent=2)

    def run(self):
        """Start the continuous monitoring loop."""
        self.running = True
        self.started_at = self._now()
        interval = self.config.get("check_interval", 30)

        agent_count = len(self.config.get("agents", []))
        logger.info(f"Watchdog started  agents={agent_count}"
                     f"  interval={interval}s"
                     f"  dashboard=:{self.config.get('dashboard_port', 9090)}")

        # Start dashboard server in background thread
        port = self.config.get("dashboard_port", 9090)
        if port:
            DashboardHandler.watchdog = self
            try:
                server = HTTPServer(("0.0.0.0", port), DashboardHandler)
                thread = threading.Thread(target=server.serve_forever,
                                          daemon=True)
                thread.start()
                logger.info(f"Dashboard listening on http://0.0.0.0:{port}/status")
            except OSError as e:
                logger.warning(f"Could not start dashboard on port {port}: {e}")

        while self.running:
            self.run_once()

            # Log summary
            statuses = {n: s.status for n, s in self.agents.items()}
            logger.info(f"Check complete  {statuses}")

            # Sleep in small increments so we can stop quickly
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Watchdog stopped")

    def stop(self):
        self.running = False


# ═════════════════════════════════════════════════════════════════════════════
#  Config Loading
# ═════════════════════════════════════════════════════════════════════════════

def load_config(path: str = None) -> dict:
    """Load config from JSON file, falling back to defaults."""
    config = dict(DEFAULT_CONFIG)

    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # Merge (shallow for top-level, deep for nested dicts)
        for key, val in user_config.items():
            if isinstance(val, dict) and isinstance(config.get(key), dict):
                config[key].update(val)
            else:
                config[key] = val
        logger.info(f"Config loaded from: {path}")
    elif path:
        logger.warning(f"Config file not found: {path}  (using defaults)")

    # Also read from env vars (override config)
    if os.environ.get("WATCHDOG_TELEGRAM_TOKEN"):
        config.setdefault("telegram_alerts", {})
        config["telegram_alerts"]["enabled"] = True
        config["telegram_alerts"]["bot_token"] = os.environ[
            "WATCHDOG_TELEGRAM_TOKEN"]
    if os.environ.get("WATCHDOG_TELEGRAM_CHAT_ID"):
        config.setdefault("telegram_alerts", {})
        config["telegram_alerts"]["chat_id"] = os.environ[
            "WATCHDOG_TELEGRAM_CHAT_ID"]
    if os.environ.get("WATCHDOG_INTERVAL"):
        config["check_interval"] = int(os.environ["WATCHDOG_INTERVAL"])
    if os.environ.get("WATCHDOG_PORT"):
        config["dashboard_port"] = int(os.environ["WATCHDOG_PORT"])

    return config


def generate_example_config() -> dict:
    """Generate a documented example config."""
    return {
        "_comment": "Claw Watchdog Configuration — rename to watchdog.json",
        "check_interval": 30,
        "failure_threshold": 3,
        "alert_cooldown": 300,
        "auto_restart": True,
        "dashboard_port": 9090,
        "log_file": "watchdog.log",

        "telegram_alerts": {
            "enabled": True,
            "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "chat_id": "YOUR_CHAT_ID",
        },

        "agents": [
            {
                "name": "zeroclaw-lucia",
                "container": "lucia-zeroclaw-1",
                "port": 3100,
                "health_url": None,
                "health_cmd": "docker exec {container} zeroclaw doctor",
                "auto_restart": True,
            },
            {
                "name": "nanoclaw-priya",
                "container": "priya-nanoclaw-1",
                "port": 3200,
                "health_url": "http://localhost:3200/health",
                "health_cmd": None,
                "auto_restart": True,
            },
            {
                "name": "picoclaw-demo",
                "container": "demo-picoclaw-1",
                "port": 3300,
                "health_url": None,
                "health_cmd": "docker exec {container} picoclaw agent -m ping",
                "auto_restart": True,
            },
            {
                "name": "openclaw-main",
                "container": "main-openclaw-1",
                "port": 3400,
                "health_url": None,
                "health_cmd": "docker exec {container} openclaw doctor",
                "auto_restart": True,
            },
        ],

        "connectivity": {
            "telegram": {
                "enabled": True,
                "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            },
            "discord": {
                "enabled": False,
            },
            "llm_endpoints": [
                {"name": "anthropic", "host": "api.anthropic.com", "port": 443},
                {"name": "deepseek", "host": "api.deepseek.com", "port": 443},
                {"name": "openai", "host": "api.openai.com", "port": 443},
            ],
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Claw Agents Watchdog — Zero-Token Reliability Monitor",
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to watchdog config JSON",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single check cycle and exit",
    )
    parser.add_argument(
        "--init-config", action="store_true",
        help="Generate an example watchdog.json config file and exit",
    )
    args = parser.parse_args()

    # Generate example config
    if args.init_config:
        out_path = Path(__file__).resolve().parent / "watchdog.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(generate_example_config(), f, indent=2)
        print(f"Example config written to: {out_path}")
        print("Edit it with your agent names, container names, and tokens.")
        return

    setup_logging()
    config = load_config(args.config)
    setup_logging(config.get("log_file"))

    if not config.get("agents"):
        logger.error(
            "No agents configured.  Create a config file with:\n"
            "  python shared/claw_watchdog.py --init-config\n"
            "Then edit shared/watchdog.json and run again."
        )
        sys.exit(1)

    watchdog = Watchdog(config)

    # Graceful shutdown
    def _signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        watchdog.stop()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if args.once:
        watchdog.run_once()
        print(watchdog.get_status_json())
    else:
        watchdog.run()


if __name__ == "__main__":
    main()
