#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Enterprise Web Dashboard
=============================================================================
Stdlib-only Python HTTP server serving an embedded SPA for enterprise
multi-agent management.  Provides real-time fleet status, model strategy
view, hardware profile, fine-tuning manager, security dashboard, cost
analytics, and configuration settings — all from a single self-contained
Python file with zero external dependencies.

Features:
  - Agent Fleet Overview   — real-time health, CPU/memory meters, restart tracking
  - Multi-Agent Management — start / stop / restart agents via claw.sh
  - System Monitoring      — live throughput, latency histogram, error rates, cache stats
  - Model Strategy View    — strategy.json routing + router health + provider scoreboard
  - Hardware Profile       — detected CPU, RAM, GPU from hardware_profile.json
  - Fine-Tuning Manager    — browse 50 adapters, view training status
  - Security Dashboard     — real-time events feed, severity summary, compliance cards
  - Cost Analytics         — budget progress bars, cost by provider/agent breakdown
  - Activity Feed          — audit log + alert history timeline
  - Settings               — read-only .env.template values (redacted)

Endpoints:
  GET  /                         → Embedded SPA HTML
  GET  /api/agents               → Agent list + health status
  POST /api/agents/:id/start     → Start agent via claw.sh
  POST /api/agents/:id/stop      → Stop agent via claw.sh
  POST /api/agents/:id/restart   → Restart agent
  GET  /api/hardware             → Hardware profile
  GET  /api/strategy             → Model strategy routing
  POST /api/strategy/generate    → Regenerate strategy.json
  GET  /api/security             → Security rules
  GET  /api/adapters             → Fine-tuning adapter list
  POST /api/finetune             → Trigger fine-tuning
  GET  /api/billing              → Billing reports
  GET  /api/config               → Redacted config
  GET  /api/status               → Overall system status
  GET  /api/monitoring           → Router + Optimizer + DAL metrics composite
  GET  /api/deployments          → Recent deployments from DAL
  GET  /api/logs?agent=X         → Agent log entries from DAL
  GET  /api/router               → Proxy to router status endpoint
  GET  /api/providers            → Provider health + optimization rules
  GET  /api/security/events      → Security events + severity summary
  GET  /api/budgets              → Budget status + spend tracking
  GET  /api/audit                → Audit log + alert history
  GET  /wizard/*                 → Serve wizard-ui/dist/ static files

Usage:
  python3 shared/claw_dashboard.py --start --port 9099
  python3 shared/claw_dashboard.py --stop

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import http.server
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from claw_auth import check_auth
from claw_metrics import MetricsCollector
from claw_ratelimit import RateLimiter

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PID_DIR = PROJECT_ROOT / "data" / "dashboard"
PID_FILE = PID_DIR / "dashboard.pid"
CLAW_SH = PROJECT_ROOT / "claw.sh"
STRATEGY_FILE = PROJECT_ROOT / "strategy.json"
HARDWARE_PROFILE_FILE = PROJECT_ROOT / "hardware_profile.json"
SECURITY_RULES_FILE = SCRIPT_DIR / "security_rules.json"
ADAPTERS_DIR = PROJECT_ROOT / "finetune" / "adapters"
BILLING_DIR = PROJECT_ROOT / "data" / "billing"
ENV_TEMPLATE = PROJECT_ROOT / ".env.template"
WIZARD_DIST = PROJECT_ROOT / "wizard-ui" / "dist"
CLAWS_DIR = PROJECT_ROOT / "data" / "claws"

DEFAULT_PORT = 9099
HEALTH_TIMEOUT = 2  # seconds

# Internal service ports (set by deploy pipeline)
ROUTER_PORT = int(os.environ.get("CLAW_GATEWAY_PORT", "9095"))
WATCHDOG_PORT = int(os.environ.get("CLAW_WATCHDOG_PORT", "9097"))
OPTIMIZER_PORT = int(os.environ.get("CLAW_OPTIMIZER_PORT", "9091"))

# Agent platform definitions
_AGENT_PLATFORMS_BASE: List[Dict[str, Any]] = [
    {"id": "zeroclaw",  "name": "ZeroClaw",  "lang": "Rust",       "port": 3100, "memory": "512 MB"},
    {"id": "nanoclaw",  "name": "NanoClaw",  "lang": "TypeScript", "port": 3200, "memory": "1 GB"},
    {"id": "picoclaw",  "name": "PicoClaw",  "lang": "Go",         "port": 3300, "memory": "128 MB"},
    {"id": "openclaw",  "name": "OpenClaw",  "lang": "Node.js",    "port": 3400, "memory": "4 GB"},
    {"id": "parlant",   "name": "Parlant",   "lang": "Python",     "port": 8800, "memory": "2 GB"},
]

# Override port for the active agent from env (set by deploy pipeline)
_active_agent = os.environ.get("CLAW_AGENT", "")
_active_port_str = os.environ.get("CLAW_AGENT_PORT", "")
AGENT_PLATFORMS: List[Dict[str, Any]] = []
for _ap in _AGENT_PLATFORMS_BASE:
    if _ap["id"] == _active_agent and _active_port_str:
        AGENT_PLATFORMS.append({**_ap, "port": int(_active_port_str)})
    else:
        AGENT_PLATFORMS.append(_ap)

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
    print(f"{GREEN}[dashboard]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[dashboard]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[dashboard]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[dashboard]{NC} {msg}")


# -------------------------------------------------------------------------
# Health Check Utility
# -------------------------------------------------------------------------
def check_agent_health(port: int) -> str:
    """Ping agent health endpoint. Returns 'running' or 'stopped'."""
    try:
        url = f"http://localhost:{port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            if resp.status == 200:
                return "running"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            socket.timeout, ConnectionRefusedError):
        pass
    return "stopped"


def _fetch_internal(port: int, path: str, timeout: int = 3) -> Optional[Dict]:
    """Fetch JSON from an internal service (router/watchdog/optimizer)."""
    try:
        url = f"http://localhost:{port}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _load_deployed_claws() -> List[Dict[str, Any]]:
    """Load deployed claw configs from data/claws/."""
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    claws = []
    for f in sorted(CLAWS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Only include actual claw configs (not port files)
            if "name" in data and "agent_port" in data:
                claws.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return claws


def _check_docker_container(container_name: str) -> str:
    """Check Docker container status. Returns 'running', 'stopped', or 'removed'."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            state = result.stdout.strip()
            return "running" if state in ("running", "restarting") else "stopped"
        return "removed"
    except Exception:
        return "stopped"


def get_all_agents_status() -> List[Dict[str, Any]]:
    """Return status for all agent platforms AND deployed xclaws.

    Combines:
      1. DAL cache (if available)
      2. The 5 default AGENT_PLATFORMS with HTTP health check
      3. Deployed claw configs from data/claws/ — checks Docker or TCP
    Deduplicates by (id, port) so a deployed claw on its default port
    doesn't appear twice.
    """
    # Try DAL for cached agent status
    try:
        from claw_dal import DAL
        dal = DAL.get_instance()
        rows = dal.agents.list_all()
        if rows:
            results = []
            known_ids = {a["id"] for a in AGENT_PLATFORMS}
            for row in rows:
                agent_id = row.get("agent_id", "")
                # Match to platform metadata
                plat = next((a for a in AGENT_PLATFORMS if a["id"] == agent_id), None)
                status = row.get("status", "stopped")
                if status not in ("running", "healthy", "stopped", "error", "degraded", "unhealthy"):
                    status = "stopped"
                if status in ("healthy",):
                    status = "running"
                if status in ("unhealthy", "degraded"):
                    status = "stopped"
                entry = {**(plat or {}), "status": status}
                if not plat:
                    entry.update({"id": agent_id, "name": row.get("name", agent_id), "port": 0})
                results.append(entry)
                known_ids.discard(agent_id)
            # Add platforms not in DAL
            for agent in AGENT_PLATFORMS:
                if agent["id"] in known_ids:
                    results.append({**agent, "status": "stopped"})
            # Also add deployed claws not in DAL
            results = _merge_deployed_claws(results)
            return results
    except Exception:
        pass

    # Fallback: HTTP ping each platform agent
    results = []
    threads: List[Tuple[threading.Thread, Dict[str, Any]]] = []

    def _check(agent: Dict[str, Any], container: Dict[str, Any]) -> None:
        container["status"] = check_agent_health(agent["port"])

    for agent in AGENT_PLATFORMS:
        result: Dict[str, Any] = {**agent, "status": "stopped"}
        t = threading.Thread(target=_check, args=(agent, result))
        threads.append((t, result))
        t.start()

    for t, result in threads:
        t.join(timeout=HEALTH_TIMEOUT + 1)
        results.append(result)

    # Merge deployed claws
    results = _merge_deployed_claws(results)
    return results


def _merge_deployed_claws(platform_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge deployed claw configs into platform results with deduplication."""
    seen_keys: set = set()
    for r in platform_results:
        seen_keys.add((r.get("id", ""), r.get("port", 0)))

    deployed = _load_deployed_claws()
    threads: List[Tuple[threading.Thread, Dict[str, Any]]] = []

    def _check_claw(claw: Dict[str, Any], result: Dict[str, Any]) -> None:
        container_name = claw.get("container_name", "")
        agent_port = claw.get("agent_port", 0)
        detected_status = "stopped"

        # Docker check
        if container_name:
            detected_status = _check_docker_container(container_name)

        # TCP fallback
        if detected_status != "running" and agent_port:
            tcp_status = check_agent_health(agent_port)
            if tcp_status == "running":
                detected_status = "running"

        result["status"] = detected_status

        # Update saved config if status changed
        if detected_status != claw.get("status"):
            claw["status"] = detected_status
            claw_id = claw.get("id", "")
            if claw_id:
                config_path = CLAWS_DIR / f"{claw_id}.json"
                if config_path.exists():
                    try:
                        config_path.write_text(json.dumps(claw, indent=2), encoding="utf-8")
                    except OSError:
                        pass

    for claw in deployed:
        platform_id = claw.get("platform", "xclaw")
        agent_port = claw.get("agent_port", 0)
        key = (platform_id, agent_port)

        # Skip if this matches an existing platform entry
        if key in seen_keys:
            # But update the existing entry if we can provide better info
            for r in platform_results:
                if (r.get("id"), r.get("port")) == key:
                    r.setdefault("container_name", claw.get("container_name"))
                    r.setdefault("agent_name", claw.get("name"))
                    break
            continue

        # Skip dead claws
        if claw.get("status") in ("removed",):
            continue

        seen_keys.add(key)
        plat_meta = next((p for p in AGENT_PLATFORMS if p["id"] == platform_id), {})
        result: Dict[str, Any] = {
            "id": claw.get("id", f"claw_{agent_port}"),
            "name": claw.get("name", f"xclaw-{agent_port}"),
            "lang": plat_meta.get("lang", ""),
            "port": agent_port,
            "memory": plat_meta.get("memory", ""),
            "status": "stopped",
            "container_name": claw.get("container_name", ""),
            "platform": platform_id,
            "gateway_port": claw.get("gateway_port"),
            "optimizer_port": claw.get("optimizer_port"),
            "watchdog_port": claw.get("watchdog_port"),
        }
        t = threading.Thread(target=_check_claw, args=(claw, result))
        threads.append((t, result))
        t.start()

    for t, result in threads:
        t.join(timeout=HEALTH_TIMEOUT + 2)
        platform_results.append(result)

    platform_results.sort(key=lambda x: x.get("port", 0))
    return platform_results


# -------------------------------------------------------------------------
# Real-Time Activity Aggregator
# -------------------------------------------------------------------------
@dataclass
class ActivityEvent:
    """A single event emitted to SSE subscribers."""
    event_type: str   # fleet_snapshot, request_completed, claw_status_change, cost_update
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ActivityAggregator:
    """Background daemon that polls all claw services and emits live events.

    Lazy-init singleton — only starts when the first SSE client connects.
    Uses ThreadPoolExecutor for parallel polling of router/watchdog/DAL.
    """

    _instance: Optional["ActivityAggregator"] = None
    _init_lock = threading.Lock()
    MAX_SUBSCRIBERS = 50
    QUEUE_SIZE = 200
    POLL_INTERVAL = 2.5

    def __init__(self) -> None:
        self._subscribers: List[queue.Queue] = []
        self._sub_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Previous cycle state for delta detection
        self._prev_claw_statuses: Dict[str, str] = {}
        self._prev_request_count: int = 0

    @classmethod
    def get_instance(cls) -> "ActivityAggregator":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = ActivityAggregator()
        return cls._instance

    def subscribe(self) -> queue.Queue:
        """Add a new SSE subscriber. Returns a Queue for the client."""
        q: queue.Queue = queue.Queue(maxsize=self.QUEUE_SIZE)
        with self._sub_lock:
            # Evict oldest subscriber if at capacity
            while len(self._subscribers) >= self.MAX_SUBSCRIBERS:
                old = self._subscribers.pop(0)
                try:
                    old.put_nowait(None)  # sentinel to signal disconnect
                except queue.Full:
                    pass
            self._subscribers.append(q)
        # Lazy start — first subscriber spins up the daemon
        if not self._running:
            self._start()
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        """Remove an SSE subscriber."""
        with self._sub_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def _start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="activity-aggregator")
        self._thread.start()
        log("Activity aggregator started")

    def _broadcast(self, event: ActivityEvent) -> None:
        """Send event to all subscribers, dropping oldest on overflow."""
        with self._sub_lock:
            dead: List[queue.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    # Drop oldest to make room
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        q.put_nowait(event)
                    except queue.Full:
                        dead.append(q)
            for d in dead:
                try:
                    self._subscribers.remove(d)
                except ValueError:
                    pass

    def _run(self) -> None:
        """Main aggregation loop — polls every POLL_INTERVAL seconds."""
        while self._running:
            try:
                self._poll_cycle()
            except Exception as exc:
                try:
                    err(f"Activity aggregator error: {exc}")
                except Exception:
                    pass
            # Check if we still have subscribers
            with self._sub_lock:
                if not self._subscribers:
                    self._running = False
                    log("Activity aggregator stopped (no subscribers)")
                    return
            time.sleep(self.POLL_INTERVAL)

    def _poll_cycle(self) -> None:
        """One polling cycle: gather data from all sources in parallel."""
        # Gather data from router, watchdog, deployed claws in parallel
        router_data: Optional[Dict] = None
        watchdog_data: Optional[Dict] = None
        dal_costs: Optional[Dict] = None
        dal_requests: List[Dict] = []
        dal_conversations: int = 0
        dal_req_count: int = 0

        deployed_claws = _load_deployed_claws()

        def fetch_router():
            return _fetch_internal(ROUTER_PORT, "/api/router/status")

        def fetch_watchdog():
            return _fetch_internal(WATCHDOG_PORT, "/status")

        def fetch_dal_data():
            result: Dict[str, Any] = {}
            try:
                from claw_dal import DAL
                dal = DAL.get_instance()
                result["costs_daily"] = dal.costs.daily_spend()
                result["costs_monthly"] = dal.costs.monthly_spend()
                result["recent_requests"] = dal.llm_requests.get_recent(10)
                result["conversations"] = len(
                    dal.conversations.list_conversations(limit=1000))
                # RPM: requests in the last 60 seconds
                since = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() - 60))
                result["rpm"] = dal.llm_requests.count_since(since)
                # Total request count for delta detection
                total_row = dal.llm_requests._fetchone(
                    "SELECT COUNT(*) AS cnt FROM llm_requests", ())
                result["total_requests"] = total_row["cnt"] if total_row else 0
            except Exception:
                pass
            return result

        # Parallel fetch with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="agg") as executor:
            futures = {
                executor.submit(fetch_router): "router",
                executor.submit(fetch_watchdog): "watchdog",
                executor.submit(fetch_dal_data): "dal",
            }
            # Also check each deployed claw's specific ports
            claw_futures = {}
            for claw in deployed_claws:
                gw_port = claw.get("gateway_port")
                wd_port = claw.get("watchdog_port")
                claw_id = claw.get("id", "")
                if gw_port:
                    f = executor.submit(
                        _fetch_internal, gw_port, "/api/router/status")
                    claw_futures[f] = ("claw_router", claw_id)
                if wd_port:
                    f = executor.submit(
                        _fetch_internal, wd_port, "/status")
                    claw_futures[f] = ("claw_watchdog", claw_id)

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                except Exception:
                    result = None
                if key == "router":
                    router_data = result
                elif key == "watchdog":
                    watchdog_data = result
                elif key == "dal":
                    if result:
                        dal_costs = {
                            "daily": result.get("costs_daily", 0),
                            "monthly": result.get("costs_monthly", 0),
                        }
                        dal_requests = result.get("recent_requests", [])
                        dal_conversations = result.get("conversations", 0)
                        dal_req_count = result.get("total_requests", 0)

            claw_details: Dict[str, Dict] = {}
            for future in as_completed(claw_futures):
                src_type, claw_id = claw_futures[future]
                try:
                    data = future.result()
                except Exception:
                    data = None
                if data and claw_id:
                    if claw_id not in claw_details:
                        claw_details[claw_id] = {}
                    if src_type == "claw_router":
                        claw_details[claw_id]["router"] = data
                    elif src_type == "claw_watchdog":
                        claw_details[claw_id]["watchdog"] = data

        # --- Build fleet snapshot ---
        claws_online = 0
        total_requests = router_data.get("requests_served", 0) if router_data else 0
        total_failed = router_data.get("requests_failed", 0) if router_data else 0
        rpm = dal_costs and dal_req_count or 0

        agents_snapshot: List[Dict[str, Any]] = []
        watchdog_agents = (watchdog_data or {}).get("agents", {})

        for claw in deployed_claws:
            claw_id = claw.get("id", "")
            platform = claw.get("platform", "xclaw")
            agent_port = claw.get("agent_port", 0)
            container = claw.get("container_name", "")
            status = claw.get("status", "stopped")

            # Check if container is running
            if container:
                detected = _check_docker_container(container)
            elif agent_port:
                detected = check_agent_health(agent_port)
            else:
                detected = "stopped"

            if detected == "running":
                claws_online += 1

            # Watchdog resources
            wd_info = watchdog_agents.get(claw_id, {})
            resources = wd_info.get("resources", {})
            # Per-claw router stats
            claw_router = claw_details.get(claw_id, {}).get("router", {})
            claw_wd = claw_details.get(claw_id, {}).get("watchdog", {})

            snapshot_entry: Dict[str, Any] = {
                "id": claw_id,
                "name": claw.get("name", claw_id),
                "platform": platform,
                "port": agent_port,
                "status": detected,
                "cpu_percent": resources.get("cpu_percent", 0),
                "mem_percent": resources.get("mem_percent", 0),
                "requests_served": claw_router.get("requests_served", 0),
                "requests_failed": claw_router.get("requests_failed", 0),
            }
            agents_snapshot.append(snapshot_entry)

            # Delta detection — status change
            prev = self._prev_claw_statuses.get(claw_id, "")
            if prev and prev != detected:
                self._broadcast(ActivityEvent(
                    event_type="claw_status_change",
                    data={
                        "claw_id": claw_id,
                        "name": claw.get("name", claw_id),
                        "old_status": prev,
                        "new_status": detected,
                    },
                ))
            self._prev_claw_statuses[claw_id] = detected

        # Also add base platform agents to snapshot
        for plat in AGENT_PLATFORMS:
            # Don't duplicate if already in deployed claws
            if any(c.get("id") == plat["id"] for c in deployed_claws):
                continue
            plat_status = check_agent_health(plat["port"])
            if plat_status == "running":
                claws_online += 1
            wd_info = watchdog_agents.get(plat["id"], {})
            resources = wd_info.get("resources", {})
            agents_snapshot.append({
                "id": plat["id"],
                "name": plat["name"],
                "platform": plat["id"],
                "port": plat["port"],
                "status": plat_status,
                "cpu_percent": resources.get("cpu_percent", 0),
                "mem_percent": resources.get("mem_percent", 0),
                "requests_served": 0,
                "requests_failed": 0,
            })
            prev = self._prev_claw_statuses.get(plat["id"], "")
            if prev and prev != plat_status:
                self._broadcast(ActivityEvent(
                    event_type="claw_status_change",
                    data={
                        "claw_id": plat["id"],
                        "name": plat["name"],
                        "old_status": prev,
                        "new_status": plat_status,
                    },
                ))
            self._prev_claw_statuses[plat["id"]] = plat_status

        # RPM from DAL
        rpm_val = 0
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            since = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60))
            rpm_val = dal.llm_requests.count_since(since)
        except Exception:
            pass

        # Broadcast fleet snapshot
        self._broadcast(ActivityEvent(
            event_type="fleet_snapshot",
            data={
                "claws_online": claws_online,
                "claws_total": len(agents_snapshot),
                "total_requests": total_requests + total_failed,
                "total_failed": total_failed,
                "rpm": rpm_val,
                "conversations": dal_conversations,
                "claws": agents_snapshot,
            },
        ))

        # Delta detection — new requests completed
        if dal_req_count > self._prev_request_count and self._prev_request_count > 0:
            # Emit individual request events for new requests
            new_count = dal_req_count - self._prev_request_count
            for req in dal_requests[:new_count]:
                self._broadcast(ActivityEvent(
                    event_type="request_completed",
                    data={
                        "model": req.get("model", ""),
                        "provider": req.get("provider", ""),
                        "latency_ms": req.get("latency_ms", 0),
                        "status_code": req.get("status_code", 200),
                        "cost_usd": req.get("cost_usd", 0),
                        "input_tokens": req.get("input_tokens", 0),
                        "output_tokens": req.get("output_tokens", 0),
                        "created_at": req.get("created_at", ""),
                    },
                ))
        self._prev_request_count = dal_req_count

        # Cost update
        if dal_costs:
            self._broadcast(ActivityEvent(
                event_type="cost_update",
                data=dal_costs,
            ))


# -------------------------------------------------------------------------
# File Reading Utilities
# -------------------------------------------------------------------------
def read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Safely read and parse a JSON file."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def read_env_template_redacted() -> Dict[str, str]:
    """Read .env.template and redact secret values."""
    result: Dict[str, str] = {}
    if not ENV_TEMPLATE.exists():
        return result
    try:
        with open(ENV_TEMPLATE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Redact anything that looks like a secret
                    secret_keywords = ("key", "secret", "token", "password",
                                       "credential", "auth")
                    if any(kw in key.lower() for kw in secret_keywords) and value:
                        result[key] = value[:4] + "****" + value[-2:] if len(value) > 6 else "****"
                    else:
                        result[key] = value
    except (IOError, OSError):
        pass
    return result


def list_adapters() -> List[Dict[str, Any]]:
    """List fine-tuning adapters from finetune/adapters/*/adapter_config.json."""
    adapters: List[Dict[str, Any]] = []
    if not ADAPTERS_DIR.exists():
        return adapters
    try:
        for entry in sorted(ADAPTERS_DIR.iterdir()):
            if not entry.is_dir():
                continue
            config_path = entry / "adapter_config.json"
            adapter_info: Dict[str, Any] = {
                "id": entry.name,
                "name": entry.name.replace("-", " ").title(),
                "path": str(entry),
                "has_config": config_path.exists(),
            }
            if config_path.exists():
                config = read_json_file(config_path)
                if config:
                    adapter_info["config"] = config
                    adapter_info["domain"] = config.get("domain", "general")
                    adapter_info["base_model"] = config.get("base_model", "unknown")
                    adapter_info["status"] = config.get("status", "ready")
                else:
                    adapter_info["domain"] = "general"
                    adapter_info["status"] = "ready"
            else:
                adapter_info["domain"] = "general"
                adapter_info["status"] = "no config"
            adapters.append(adapter_info)
    except (IOError, OSError):
        pass
    return adapters


def read_billing_data() -> Dict[str, Any]:
    """Read billing reports from data/billing/.

    Tries DAL first (cached 60s) for fast aggregation, falls back to JSONL files.
    """
    # Try DAL for cost aggregation
    try:
        from claw_dal import DAL
        dal = DAL.get_instance()
        agg = dal.costs.aggregate()
        result = {
            "reports": [],
            "usage_log_exists": True,
            "total_records": agg.get("total_requests", 0),
            "total_cost": agg.get("total_cost", 0),
            "currency": "USD",
        }
        # Read billing config for thresholds
        config_path = BILLING_DIR / "billing_config.json"
        config = read_json_file(config_path)
        if config:
            result["config"] = config
        # Still load report files (they contain generated reports, not raw data)
        reports_dir = BILLING_DIR / "reports"
        if reports_dir.exists():
            try:
                for entry in sorted(reports_dir.iterdir(), reverse=True):
                    if entry.suffix == ".json":
                        report = read_json_file(entry)
                        if report:
                            report["filename"] = entry.name
                            result["reports"].append(report)
                        if len(result["reports"]) >= 10:
                            break
            except (IOError, OSError):
                pass
        return result
    except Exception:
        pass

    # Fallback: read from JSONL files
    result: Dict[str, Any] = {
        "reports": [],
        "usage_log_exists": False,
        "total_records": 0,
    }
    usage_log = BILLING_DIR / "usage_log.jsonl"
    if usage_log.exists():
        result["usage_log_exists"] = True
        try:
            count = 0
            with open(usage_log, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
            result["total_records"] = count
        except (IOError, OSError):
            pass

    reports_dir = BILLING_DIR / "reports"
    if reports_dir.exists():
        try:
            for entry in sorted(reports_dir.iterdir(), reverse=True):
                if entry.suffix == ".json":
                    report = read_json_file(entry)
                    if report:
                        report["filename"] = entry.name
                        result["reports"].append(report)
                    if len(result["reports"]) >= 10:
                        break
        except (IOError, OSError):
            pass

    # Read billing config for thresholds
    config_path = BILLING_DIR / "billing_config.json"
    config = read_json_file(config_path)
    if config:
        result["config"] = config

    return result


# -------------------------------------------------------------------------
# Subprocess Utilities
# -------------------------------------------------------------------------
def run_claw_command(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    """Run a claw.sh command and return result."""
    if not CLAW_SH.exists():
        return {"success": False, "error": "claw.sh not found", "output": ""}
    cmd = ["bash", str(CLAW_SH)] + args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return {
            "success": proc.returncode == 0,
            "output": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else "",
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out", "output": ""}
    except (IOError, OSError) as e:
        return {"success": False, "error": str(e), "output": ""}


def run_strategy_generate(timeout: int = 60) -> Dict[str, Any]:
    """Run claw_strategy.py --generate."""
    strategy_script = SCRIPT_DIR / "claw_strategy.py"
    if not strategy_script.exists():
        return {"success": False, "error": "claw_strategy.py not found"}
    try:
        proc = subprocess.run(
            [sys.executable, str(strategy_script), "--generate"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return {
            "success": proc.returncode == 0,
            "output": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Strategy generation timed out"}
    except (IOError, OSError) as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------------
# Embedded SPA HTML
# -------------------------------------------------------------------------
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XClaw Dashboard</title>
<style>
:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #1a1a2e;
    --bg-card: #16213e;
    --accent: #00d4aa;
    --accent-hover: #00f5c4;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0a0;
    --danger: #ff4757;
    --warning: #ffa502;
    --success: #2ed573;
    --border: #2a2a4a;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary); color: var(--text-primary); display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 220px; background: var(--bg-secondary); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { padding: 20px 16px; border-bottom: 1px solid var(--border); }
.sidebar-header h1 { font-size: 18px; color: var(--accent); letter-spacing: 1px; }
.sidebar-header .subtitle { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
.nav-items { flex: 1; padding: 12px 0; overflow-y: auto; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px;
    cursor: pointer; color: var(--text-secondary); transition: all 0.2s; font-size: 14px; }
.nav-item:hover { background: rgba(0,212,170,0.08); color: var(--text-primary); }
.nav-item.active { background: rgba(0,212,170,0.15); color: var(--accent);
    border-right: 3px solid var(--accent); }
.nav-icon { font-size: 18px; width: 24px; text-align: center; }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border);
    font-size: 11px; color: var(--text-secondary); }

/* Main content */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar { height: 52px; background: var(--bg-secondary); border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between; padding: 0 24px; flex-shrink: 0; }
.topbar-title { font-size: 16px; font-weight: 600; }
.status-indicator { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: var(--success); box-shadow: 0 0 6px var(--success); }
.status-dot.offline { background: var(--danger); }
.content { flex: 1; padding: 24px; overflow-y: auto; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Cards */
.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px;
    transition: border-color 0.2s; }
.card:hover { border-color: var(--accent); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.card-title { font-size: 15px; font-weight: 600; }
.card-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.badge-running { background: rgba(46,213,115,0.2); color: var(--success); }
.badge-stopped { background: rgba(255,71,87,0.2); color: var(--danger); }
.card-body { font-size: 13px; color: var(--text-secondary); }
.card-body .row { display: flex; justify-content: space-between; padding: 4px 0; }
.card-actions { margin-top: 12px; display: flex; gap: 8px; }

/* Buttons */
.btn { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer;
    font-size: 12px; font-weight: 600; transition: all 0.2s; }
.btn-start { background: var(--success); color: #fff; }
.btn-start:hover { background: #28c76f; }
.btn-stop { background: var(--danger); color: #fff; }
.btn-stop:hover { background: #e84040; }
.btn-restart { background: var(--warning); color: #111; }
.btn-restart:hover { background: #e89600; }
.btn-accent { background: var(--accent); color: #0a0a0f; }
.btn-accent:hover { background: var(--accent-hover); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Tables */
.data-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.data-table th, .data-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    font-size: 13px; }
.data-table th { color: var(--accent); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.data-table td { color: var(--text-secondary); }

/* Misc */
.section-title { font-size: 20px; font-weight: 700; margin-bottom: 16px; }
.section-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; }
.hw-stat { text-align: center; }
.hw-stat .value { font-size: 28px; font-weight: 700; color: var(--accent); }
.hw-stat .label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.adapter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.adapter-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px;
    padding: 12px; font-size: 13px; cursor: default; transition: border-color 0.2s; }
.adapter-card:hover { border-color: var(--accent); }
.adapter-id { font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.adapter-domain { color: var(--accent); font-size: 11px; text-transform: uppercase; }
.config-list { list-style: none; }
.config-list li { padding: 8px 12px; border-bottom: 1px solid var(--border); display: flex;
    justify-content: space-between; font-size: 13px; }
.config-key { color: var(--accent); font-family: monospace; }
.config-val { color: var(--text-secondary); font-family: monospace; }
.loading { text-align: center; padding: 40px; color: var(--text-secondary); }
.toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; border-radius: 6px;
    font-size: 13px; z-index: 1000; transition: opacity 0.3s; }
.toast-success { background: var(--success); color: #fff; }
.toast-error { background: var(--danger); color: #fff; }

/* Progress bars */
.progress-bar { background: var(--bg-secondary); border-radius: 6px; height: 14px; overflow: hidden; width: 100%; }
.progress-fill { height: 100%; border-radius: 6px; transition: width 0.4s ease; min-width: 2px; }
.progress-fill.green { background: var(--success); }
.progress-fill.yellow { background: var(--warning); }
.progress-fill.red { background: var(--danger); }
.progress-label { font-size: 11px; color: var(--text-secondary); margin-top: 2px; display: flex; justify-content: space-between; }

/* Severity badges */
.severity { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.severity-critical { background: rgba(255,71,87,0.25); color: #ff4757; }
.severity-high { background: rgba(255,127,80,0.25); color: #ff7f50; }
.severity-medium { background: rgba(255,165,2,0.25); color: #ffa502; }
.severity-low { background: rgba(0,212,170,0.25); color: #00d4aa; }
.severity-info { background: rgba(100,149,237,0.25); color: #6495ed; }

/* Stat cards large */
.stat-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
.stat-card .stat-value { font-size: 32px; font-weight: 700; color: var(--accent); }
.stat-card .stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.stat-card .stat-sub { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }

/* Timeline */
.timeline { position: relative; padding-left: 24px; margin-top: 16px; }
.timeline::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: var(--border); }
.timeline-item { position: relative; padding: 8px 0 16px 16px; font-size: 13px; }
.timeline-item::before { content: ''; position: absolute; left: -20px; top: 12px; width: 10px; height: 10px;
    border-radius: 50%; border: 2px solid var(--border); background: var(--bg-primary); }
.timeline-item.success::before { border-color: var(--success); background: var(--success); }
.timeline-item.failed::before { border-color: var(--danger); background: var(--danger); }
.timeline-item.in_progress::before { border-color: var(--warning); background: var(--warning); }
.timeline-item .tl-header { display: flex; justify-content: space-between; align-items: center; }
.timeline-item .tl-title { font-weight: 600; color: var(--text-primary); }
.timeline-item .tl-time { font-size: 11px; color: var(--text-secondary); }
.timeline-item .tl-detail { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

/* Log viewer */
.log-viewer { background: #0d1117; border: 1px solid var(--border); border-radius: 6px; padding: 12px;
    font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; max-height: 350px; overflow-y: auto;
    line-height: 1.6; }
.log-viewer .log-line { white-space: pre-wrap; word-break: break-all; }
.log-viewer .log-error { color: #ff4757; }
.log-viewer .log-warn { color: #ffa502; }
.log-viewer .log-info { color: #a0a0a0; }
.log-viewer .log-debug { color: #666; }

/* Metric histogram bar */
.metric-bar-container { margin: 6px 0; }
.metric-bar-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 12px; }
.metric-bar-label { width: 80px; text-align: right; color: var(--text-secondary); flex-shrink: 0; }
.metric-bar { flex: 1; height: 20px; background: var(--bg-secondary); border-radius: 4px; overflow: hidden; position: relative; }
.metric-bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.3s; }
.metric-bar-value { width: 60px; font-size: 11px; color: var(--text-secondary); flex-shrink: 0; }

/* Provider cards */
.provider-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 14px;
    transition: border-color 0.2s; }
.provider-card:hover { border-color: var(--accent); }
.provider-card .prov-name { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.provider-card .prov-score { font-size: 24px; font-weight: 700; }
.provider-card .prov-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; color: var(--text-secondary); }

/* Connectivity dots */
.conn-panel { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0; }
.conn-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.conn-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.conn-dot.up { background: var(--success); box-shadow: 0 0 4px var(--success); }
.conn-dot.down { background: var(--danger); }

/* Resource meters inline */
.resource-meters { margin-top: 8px; }
.resource-row { display: flex; align-items: center; gap: 6px; margin: 3px 0; font-size: 11px; color: var(--text-secondary); }
.resource-row .res-label { width: 30px; }
.resource-row .progress-bar { height: 8px; flex: 1; }
.resource-row .progress-fill { height: 100%; }
.resource-row .res-val { width: 40px; text-align: right; }

/* Badge inline */
.badge-inline { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600; margin-left: 4px; }
.badge-warn { background: rgba(255,165,2,0.25); color: var(--warning); }
.badge-danger { background: rgba(255,71,87,0.25); color: var(--danger); }

/* Section panel */
.panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-top: 20px; }
.panel-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.panel-desc { font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }

/* Activity feed */
.activity-item { display: flex; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
.activity-item:last-child { border-bottom: none; }
.activity-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0; background: var(--bg-secondary); }
.activity-body { flex: 1; }
.activity-body .act-title { font-weight: 600; color: var(--text-primary); }
.activity-body .act-detail { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.activity-body .act-time { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }

/* Compliance domain card */
.compliance-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.compliance-card .comp-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.compliance-card .comp-name { font-size: 14px; font-weight: 600; text-transform: uppercase; }
.compliance-card .comp-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.comp-loaded { background: rgba(46,213,115,0.2); color: var(--success); }
.comp-missing { background: rgba(255,71,87,0.2); color: var(--danger); }

/* Modal/expandable */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6);
    z-index: 900; display: flex; align-items: center; justify-content: center; }
.modal-content { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 10px;
    width: 80%; max-width: 900px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { padding: 14px 20px; border-bottom: 1px solid var(--border); display: flex;
    justify-content: space-between; align-items: center; }
.modal-header h3 { font-size: 16px; }
.modal-close { background: none; border: none; color: var(--text-secondary); font-size: 20px; cursor: pointer; }
.modal-body { padding: 16px 20px; overflow-y: auto; flex: 1; }

/* === Real-Time Activity Tab === */

/* SSE connection indicator */
.sse-status { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 13px; }
.sse-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.sse-dot.connected { background: var(--success); box-shadow: 0 0 8px var(--success);
    animation: sse-pulse 2s infinite; }
.sse-dot.disconnected { background: var(--danger); }
.sse-dot.connecting { background: var(--warning); animation: sse-pulse 1s infinite; }
@keyframes sse-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Ticker bar */
.ticker-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.ticker-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px 16px; text-align: center; flex: 1; min-width: 120px; }
.ticker-value { font-size: 24px; font-weight: 700; color: var(--accent);
    transition: all 0.3s ease; }
.ticker-label { font-size: 11px; color: var(--text-secondary); margin-top: 2px;
    text-transform: uppercase; letter-spacing: 0.5px; }

/* Claw mini-cards grid */
.claw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px; }
.claw-mini { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; cursor: pointer; transition: all 0.2s; }
.claw-mini:hover { border-color: var(--accent); transform: translateY(-1px); }
.claw-mini-header { display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 8px; }
.claw-mini-name { font-size: 13px; font-weight: 600; }
.claw-mini-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.claw-mini-dot.running { background: var(--success); box-shadow: 0 0 4px var(--success); }
.claw-mini-dot.stopped { background: var(--danger); }
.claw-mini-metrics { font-size: 11px; color: var(--text-secondary); }
.claw-mini-metrics .metric-row { display: flex; justify-content: space-between; margin: 2px 0; }
.sparkline { display: flex; align-items: flex-end; gap: 1px; height: 20px; margin-top: 6px; }
.sparkline-bar { width: 4px; background: var(--accent); border-radius: 1px;
    transition: height 0.3s; min-height: 1px; }

/* Request feed table */
.feed-table { width: 100%; border-collapse: collapse; font-family: 'Consolas','Monaco',monospace;
    font-size: 12px; }
.feed-table th { text-align: left; padding: 6px 10px; color: var(--accent); font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
.feed-table td { padding: 5px 10px; border-bottom: 1px solid rgba(42,42,74,0.5);
    color: var(--text-secondary); }
.feed-table tr { transition: background 0.2s; }
.feed-table tr.feed-new { animation: feed-flash 1s ease; }
@keyframes feed-flash { 0% { background: rgba(0,212,170,0.15); } 100% { background: none; } }
.latency-fast { color: var(--success); }
.latency-mid { color: var(--warning); }
.latency-slow { color: var(--danger); }

/* Status timeline */
.status-timeline { max-height: 200px; overflow-y: auto; }
.status-entry { display: flex; align-items: center; gap: 10px; padding: 6px 0;
    border-bottom: 1px solid rgba(42,42,74,0.3); font-size: 12px; }
.status-entry-time { color: var(--text-secondary); font-size: 11px; width: 70px; flex-shrink: 0; }
.status-entry-icon { font-size: 14px; }

/* Activity 2-col layout */
.activity-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
@media (max-width: 900px) { .activity-columns { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="sidebar">
    <div class="sidebar-header">
        <h1>XClaw</h1>
        <div class="subtitle">Enterprise Agent Dashboard</div>
    </div>
    <div class="nav-items">
        <div class="nav-item active" data-tab="fleet">
            <span class="nav-icon">&#9881;</span><span>Fleet</span></div>
        <div class="nav-item" data-tab="monitoring">
            <span class="nav-icon">&#9879;</span><span>Monitoring</span></div>
        <div class="nav-item" data-tab="models">
            <span class="nav-icon">&#9733;</span><span>Models</span></div>
        <div class="nav-item" data-tab="hardware">
            <span class="nav-icon">&#9992;</span><span>Hardware</span></div>
        <div class="nav-item" data-tab="finetuning">
            <span class="nav-icon">&#9878;</span><span>Fine-Tuning</span></div>
        <div class="nav-item" data-tab="security">
            <span class="nav-icon">&#9888;</span><span>Security</span></div>
        <div class="nav-item" data-tab="costs">
            <span class="nav-icon">&#9830;</span><span>Costs</span></div>
        <div class="nav-item" data-tab="activity">
            <span class="nav-icon">&#9776;</span><span>Activity</span></div>
        <div class="nav-item" data-tab="settings">
            <span class="nav-icon">&#9881;</span><span>Settings</span></div>
    </div>
    <div class="sidebar-footer">Apache 2.0 &copy; 2026 Amenthyx</div>
</div>

<div class="main">
    <div class="topbar">
        <div class="topbar-title">XClaw Dashboard</div>
        <div class="status-indicator">
            <span id="global-status-text">Checking...</span>
            <span class="status-dot" id="global-status-dot"></span>
        </div>
    </div>
    <div class="content">
        <!-- Fleet Tab -->
        <div class="tab-content active" id="tab-fleet">
            <div class="section-title">Agent Fleet Overview</div>
            <div class="section-desc">Real-time status of all Claw agent platforms. Auto-refreshes every 5 seconds.</div>
            <div class="cards-grid" id="fleet-cards"><div class="loading">Loading fleet status...</div></div>
            <div class="panel" id="fleet-connectivity" style="display:none">
                <div class="panel-title">Connectivity Status</div>
                <div class="conn-panel" id="connectivity-dots"></div>
            </div>
            <div class="panel" id="fleet-deployments" style="display:none">
                <div class="panel-title">Recent Deployments</div>
                <div class="timeline" id="deployment-timeline"></div>
            </div>
        </div>

        <!-- Monitoring Tab -->
        <div class="tab-content" id="tab-monitoring">
            <div class="section-title">System Monitoring</div>
            <div class="section-desc">Real-time throughput, latency, errors, caching and model usage metrics.</div>
            <div class="stat-cards" id="monitoring-stats"><div class="loading">Loading metrics...</div></div>
            <div class="panel" id="panel-latency" style="display:none">
                <div class="panel-title">Latency Distribution</div>
                <div id="latency-histogram"></div>
            </div>
            <div class="panel" id="panel-model-usage" style="display:none">
                <div class="panel-title">Model Usage</div>
                <div id="model-usage-table"></div>
            </div>
            <div class="panel" id="panel-errors" style="display:none">
                <div class="panel-title">Error Rate</div>
                <div id="error-rate-content"></div>
            </div>
            <div class="panel" id="panel-cache" style="display:none">
                <div class="panel-title">Cache Performance</div>
                <div id="cache-content"></div>
            </div>
        </div>

        <!-- Models Tab -->
        <div class="tab-content" id="tab-models">
            <div class="section-title">Model Strategy Routing</div>
            <div class="section-desc">Task routing from strategy.json. Shows which model handles each task type.</div>
            <div class="panel" id="panel-router-health" style="display:none;margin-top:0;margin-bottom:16px">
                <div class="panel-title">Router Health</div>
                <div id="router-health-content"></div>
            </div>
            <button class="btn btn-accent" onclick="regenerateStrategy()" id="btn-regen">Regenerate Strategy</button>
            <div id="models-content"><div class="loading">Loading strategy...</div></div>
            <div class="panel" id="panel-routing-log" style="display:none">
                <div class="panel-title">Live Routing Log <span style="font-size:11px;color:var(--text-secondary);font-weight:400">(last 20 requests)</span></div>
                <div id="routing-log-content"></div>
            </div>
            <div class="panel" id="panel-providers" style="display:none">
                <div class="panel-title">Provider Health Scoreboard</div>
                <div class="cards-grid" id="provider-cards"></div>
            </div>
            <div class="panel" id="panel-opt-rules" style="display:none">
                <div class="panel-title">Optimization Rules Effectiveness</div>
                <div id="opt-rules-content"></div>
            </div>
        </div>

        <!-- Hardware Tab -->
        <div class="tab-content" id="tab-hardware">
            <div class="section-title">Hardware Profile</div>
            <div class="section-desc">Detected hardware capabilities and recommended runtime configuration.</div>
            <div id="hardware-content"><div class="loading">Loading hardware profile...</div></div>
        </div>

        <!-- Fine-Tuning Tab -->
        <div class="tab-content" id="tab-finetuning">
            <div class="section-title">Fine-Tuning Adapters</div>
            <div class="section-desc">Browse all LoRA/QLoRA adapters across 50 enterprise use-case domains.</div>
            <div id="adapters-content"><div class="loading">Loading adapters...</div></div>
        </div>

        <!-- Security Tab -->
        <div class="tab-content" id="tab-security">
            <div class="section-title">Security Dashboard</div>
            <div class="section-desc">Security events, severity overview, and compliance status.</div>
            <div class="stat-cards" id="severity-summary"><div class="loading">Loading security data...</div></div>
            <div class="panel" id="panel-sec-events" style="display:none">
                <div class="panel-title">Security Events Feed</div>
                <div id="security-events-content"></div>
            </div>
            <div class="panel" id="panel-compliance" style="display:none">
                <div class="panel-title">Compliance Domains</div>
                <div class="cards-grid" id="compliance-cards"></div>
            </div>
            <div id="security-content" style="display:none"></div>
        </div>

        <!-- Costs Tab -->
        <div class="tab-content" id="tab-costs">
            <div class="section-title">Cost Analytics</div>
            <div class="section-desc">API usage costs, budget tracking, and provider/agent cost breakdown.</div>
            <div id="costs-content"><div class="loading">Loading billing data...</div></div>
            <div class="panel" id="panel-budgets" style="display:none">
                <div class="panel-title">Budget Progress</div>
                <div id="budget-bars"></div>
            </div>
            <div class="panel" id="panel-cost-provider" style="display:none">
                <div class="panel-title">Cost by Provider</div>
                <div id="cost-provider-table"></div>
            </div>
            <div class="panel" id="panel-cost-agent" style="display:none">
                <div class="panel-title">Cost by Agent</div>
                <div id="cost-agent-table"></div>
            </div>
        </div>

        <!-- Activity Tab (Real-Time) -->
        <div class="tab-content" id="tab-activity">
            <div class="section-title">Real-Time Agent Activity</div>
            <div class="sse-status">
                <span class="sse-dot disconnected" id="sse-dot"></span>
                <span id="sse-status-text">Disconnected</span>
            </div>

            <!-- Ticker Bar -->
            <div class="ticker-bar" id="activity-ticker">
                <div class="ticker-item"><div class="ticker-value" id="tk-online">-</div><div class="ticker-label">Claws Online</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-requests">-</div><div class="ticker-label">Total Requests</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-rpm">-</div><div class="ticker-label">Req/min</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-failed">-</div><div class="ticker-label">Failed</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-conversations">-</div><div class="ticker-label">Conversations</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-daily-cost">-</div><div class="ticker-label">Today's Cost</div></div>
                <div class="ticker-item"><div class="ticker-value" id="tk-monthly-cost">-</div><div class="ticker-label">Monthly Cost</div></div>
            </div>

            <!-- 2-Column Grid -->
            <div class="activity-columns">
                <!-- Left: Fleet Status Mini-Cards -->
                <div class="panel" style="margin-top:0">
                    <div class="panel-title">Fleet Status</div>
                    <div class="claw-grid" id="claw-grid"><div class="loading">Waiting for data...</div></div>
                </div>
                <!-- Right: Live Request Feed -->
                <div class="panel" style="margin-top:0">
                    <div class="panel-title">Live Request Feed</div>
                    <div style="max-height:400px;overflow-y:auto">
                        <table class="feed-table">
                            <thead><tr><th>Time</th><th>Model</th><th>Provider</th><th>Latency</th><th>Status</th><th>Cost</th></tr></thead>
                            <tbody id="feed-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Full-width: Status Changes & Alerts -->
            <div class="panel" style="margin-top:0">
                <div class="panel-title">Status Changes &amp; Alerts</div>
                <div class="status-timeline" id="status-timeline">
                    <div class="loading" style="padding:12px">No status changes yet.</div>
                </div>
            </div>
        </div>

        <!-- Settings Tab -->
        <div class="tab-content" id="tab-settings">
            <div class="section-title">Configuration</div>
            <div class="section-desc">Read-only view of .env.template values. Secrets are redacted.</div>
            <div id="settings-content"><div class="loading">Loading configuration...</div></div>
        </div>
    </div>
</div>

<script>
(function() {
    'use strict';
    let currentTab = 'fleet';
    let fleetInterval = null;

    // --- Tab Navigation ---
    document.querySelectorAll('.nav-item').forEach(function(item) {
        item.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');
            switchTab(tab);
        });
    });

    function switchTab(tab) {
        // Disconnect SSE when leaving activity tab
        if (currentTab === 'activity' && tab !== 'activity') {
            disconnectSSE();
        }

        document.querySelectorAll('.nav-item').forEach(function(el) { el.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
        document.querySelector('[data-tab="' + tab + '"]').classList.add('active');
        document.getElementById('tab-' + tab).classList.add('active');
        currentTab = tab;

        if (tab === 'fleet') loadFleet();
        else if (tab === 'monitoring') loadMonitoring();
        else if (tab === 'models') loadModels();
        else if (tab === 'hardware') loadHardware();
        else if (tab === 'finetuning') loadAdapters();
        else if (tab === 'security') loadSecurity();
        else if (tab === 'costs') loadCosts();
        else if (tab === 'activity') loadActivity();
        else if (tab === 'settings') loadSettings();
    }

    // --- Toast Notifications ---
    function showToast(msg, type) {
        var t = document.createElement('div');
        t.className = 'toast toast-' + (type || 'success');
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(function() { t.style.opacity = '0'; setTimeout(function() { t.remove(); }, 300); }, 3000);
    }

    // --- API Helpers ---
    function apiGet(path) {
        return fetch(path).then(function(r) { return r.json(); });
    }
    function apiPost(path, body) {
        return fetch(path, { method: 'POST', headers: {'Content-Type':'application/json'},
            body: body ? JSON.stringify(body) : '{}' }).then(function(r) { return r.json(); });
    }

    // --- Fleet Tab ---
    function loadFleet() {
        // Fetch agents + watchdog + deployments in parallel
        Promise.all([
            apiGet('/api/agents'),
            apiGet('/api/monitoring').catch(function() { return {}; }),
            apiGet('/api/deployments').catch(function() { return []; })
        ]).then(function(results) {
            var agents = results[0];
            var monData = results[1] || {};
            var deployments = results[2] || [];

            var c = document.getElementById('fleet-cards');
            if (!agents || !agents.length) { c.innerHTML = '<div class="loading">No agents configured.</div>'; return; }
            var running = agents.filter(function(a) { return a.status === 'running'; }).length;
            document.getElementById('global-status-text').textContent = running + '/' + agents.length + ' Online';
            var dot = document.getElementById('global-status-dot');
            dot.className = 'status-dot ' + (running > 0 ? 'online' : 'offline');

            // Get watchdog data for resource meters and connectivity
            var watchdog = monData._watchdog || null;
            var connectivity = monData._connectivity || null;

            var html = '';
            agents.forEach(function(a) {
                var isRunning = a.status === 'running';
                html += '<div class="card">' +
                    '<div class="card-header"><span class="card-title">' + a.name + '</span>' +
                    '<span class="card-badge ' + (isRunning ? 'badge-running' : 'badge-stopped') + '">' +
                    a.status + '</span></div>' +
                    '<div class="card-body">' +
                    '<div class="row"><span>Language</span><span>' + (a.lang || '-') + '</span></div>' +
                    '<div class="row"><span>Port</span><span>' + a.port + '</span></div>' +
                    '<div class="row"><span>Memory</span><span>' + (a.memory || '-') + '</span></div>';

                // Resource meters from watchdog if available
                var res = a.resources || (watchdog && watchdog[a.id] ? watchdog[a.id].resources : null);
                if (res) {
                    var cpuPct = res.cpu_percent || 0;
                    var memPct = res.mem_percent || 0;
                    var cpuColor = cpuPct < 60 ? 'green' : cpuPct < 85 ? 'yellow' : 'red';
                    var memColor = memPct < 60 ? 'green' : memPct < 85 ? 'yellow' : 'red';
                    html += '<div class="resource-meters">' +
                        '<div class="resource-row"><span class="res-label">CPU</span>' +
                        '<div class="progress-bar"><div class="progress-fill ' + cpuColor + '" style="width:' + cpuPct + '%"></div></div>' +
                        '<span class="res-val">' + cpuPct.toFixed(0) + '%</span></div>' +
                        '<div class="resource-row"><span class="res-label">Mem</span>' +
                        '<div class="progress-bar"><div class="progress-fill ' + memColor + '" style="width:' + memPct + '%"></div></div>' +
                        '<span class="res-val">' + memPct.toFixed(0) + '%</span></div></div>';
                }

                // Restart count and failure badges
                var restarts = a.restart_count || (watchdog && watchdog[a.id] ? watchdog[a.id].restart_count : 0);
                var failures = a.consecutive_failures || (watchdog && watchdog[a.id] ? watchdog[a.id].consecutive_failures : 0);
                if (restarts > 0 || failures > 0) {
                    html += '<div style="margin-top:6px">';
                    if (restarts > 0) html += '<span class="badge-inline badge-warn">Restarts: ' + restarts + '</span>';
                    if (failures > 0) html += '<span class="badge-inline badge-danger">Failures: ' + failures + '</span>';
                    html += '</div>';
                }

                html += '</div>' +
                    '<div class="card-actions">' +
                    '<button class="btn btn-start" onclick="agentAction(\'' + a.id + '\',\'start\')"' +
                    (isRunning ? ' disabled' : '') + '>Start</button>' +
                    '<button class="btn btn-stop" onclick="agentAction(\'' + a.id + '\',\'stop\')"' +
                    (!isRunning ? ' disabled' : '') + '>Stop</button>' +
                    '<button class="btn btn-restart" onclick="agentAction(\'' + a.id + '\',\'restart\')">Restart</button>' +
                    '<button class="btn" onclick="showAgentLogs(\'' + a.id + '\',\'' + a.name + '\')" ' +
                    'style="background:var(--bg-secondary);color:var(--text-secondary);border:1px solid var(--border)">Logs</button>' +
                    '</div></div>';
            });
            c.innerHTML = html;

            // Connectivity panel from watchdog
            fetchConnectivity(monData);

            // Deployment timeline
            renderDeployments(deployments);
        }).catch(function(e) {
            document.getElementById('fleet-cards').innerHTML = '<div class="loading">Error loading fleet: ' + e.message + '</div>';
        });
    }

    function fetchConnectivity(data) {
        data = data || {};
        var panel = document.getElementById('fleet-connectivity');
        var dotsEl = document.getElementById('connectivity-dots');
        var items = [];
        // Watchdog connectivity (Telegram, Discord, LLM APIs)
        var conn = data._connectivity || {};
        Object.keys(conn).forEach(function(k) {
            var val = conn[k];
            var up = val === true || val === 'connected' || (typeof val === 'object' && val && val.ok);
            items.push({name: k, up: up});
        });
        // Router and optimizer reachability
        if (data.router) {
            items.push({name: 'Router (Gateway)', up: data.router.ok !== false});
        }
        if (data.optimizer) {
            items.push({name: 'Optimizer', up: true});
        }
        // Provider health from optimizer
        if (data.optimizer && data.optimizer.provider_health) {
            var ph = data.optimizer.provider_health;
            Object.keys(ph).forEach(function(p) {
                items.push({name: p, up: (ph[p].score || 0) > 0.3});
            });
        }
        if (items.length > 0) {
            panel.style.display = 'block';
            var html = '';
            items.forEach(function(it) {
                html += '<div class="conn-item"><span class="conn-dot ' + (it.up ? 'up' : 'down') + '"></span>' +
                    '<span>' + it.name + '</span></div>';
            });
            dotsEl.innerHTML = html;
        }
    }

    function renderDeployments(deployments) {
        var panel = document.getElementById('fleet-deployments');
        var tl = document.getElementById('deployment-timeline');
        if (!deployments || !deployments.length) { panel.style.display = 'none'; return; }
        panel.style.display = 'block';
        var html = '';
        deployments.forEach(function(d) {
            var status = d.status || 'unknown';
            var cssClass = status === 'success' ? 'success' : status === 'failed' ? 'failed' : 'in_progress';
            html += '<div class="timeline-item ' + cssClass + '">' +
                '<div class="tl-header"><span class="tl-title">' + (d.agent_name || d.deploy_id || 'Deploy') + '</span>' +
                '<span class="tl-time">' + (d.started_at || d.timestamp || '') + '</span></div>' +
                '<div class="tl-detail">' + (d.platform || '') + ' — ' +
                '<span class="card-badge ' + (status === 'success' ? 'badge-running' : 'badge-stopped') + '">' +
                status + '</span></div></div>';
        });
        tl.innerHTML = html;
    }

    // Agent log viewer modal
    window.showAgentLogs = function(agentId, agentName) {
        apiGet('/api/logs?agent=' + agentId + '&limit=50').then(function(logs) {
            var overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };
            var html = '<div class="modal-content">' +
                '<div class="modal-header"><h3>Logs: ' + agentName + '</h3>' +
                '<button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()">&times;</button></div>' +
                '<div class="modal-body"><div class="log-viewer">';
            if (!logs || !logs.length) {
                html += '<div class="log-line log-info">No log entries found.</div>';
            } else {
                logs.forEach(function(entry) {
                    var level = (entry.level || 'info').toLowerCase();
                    var cls = level === 'error' ? 'log-error' : level === 'warning' || level === 'warn' ? 'log-warn' :
                              level === 'debug' ? 'log-debug' : 'log-info';
                    var ts = entry.timestamp || '';
                    var msg = entry.message || entry.msg || JSON.stringify(entry);
                    html += '<div class="log-line ' + cls + '">[' + ts + '] [' + level.toUpperCase() + '] ' + escHtml(msg) + '</div>';
                });
            }
            html += '</div></div></div>';
            overlay.innerHTML = html;
            document.body.appendChild(overlay);
        }).catch(function(e) { showToast('Error loading logs: ' + e.message, 'error'); });
    };

    function escHtml(s) {
        var d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }

    window.agentAction = function(id, action) {
        showToast('Sending ' + action + ' to ' + id + '...', 'success');
        apiPost('/api/agents/' + id + '/' + action).then(function(r) {
            if (r.success) showToast(id + ' ' + action + ' successful', 'success');
            else showToast(id + ' ' + action + ' failed: ' + (r.error || 'unknown'), 'error');
            setTimeout(loadFleet, 1500);
        }).catch(function(e) { showToast('Error: ' + e.message, 'error'); });
    };

    // --- Monitoring Tab ---
    function loadMonitoring() {
        apiGet('/api/monitoring').then(function(data) {
            var statsEl = document.getElementById('monitoring-stats');
            var router = data.router || {};
            var optimizer = data.optimizer || {};
            var cache = data.cache || {};
            var logLevels = data.log_levels || {};
            var modelUsage = data.model_usage || [];

            // 1. Live Request Counter + Throughput
            var served = router.requests_served || 0;
            var failed = router.requests_failed || 0;
            var total = served + failed;
            var successRate = total > 0 ? ((served / total) * 100).toFixed(1) : '0.0';
            var uptime = router.uptime_seconds || 1;
            var rpm = total > 0 ? (total / (uptime / 60)).toFixed(1) : '0';

            var html = '<div class="stat-card"><div class="stat-value">' + total + '</div>' +
                '<div class="stat-label">Total Requests</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + failed + '</div>' +
                '<div class="stat-label">Failed Requests</div>' +
                '<div class="stat-sub" style="color:' + (failed > 0 ? 'var(--danger)' : 'var(--success)') + '">' +
                (failed > 0 ? 'Attention needed' : 'All clear') + '</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="color:' +
                (parseFloat(successRate) >= 99 ? 'var(--success)' : parseFloat(successRate) >= 95 ? 'var(--warning)' : 'var(--danger)') +
                '">' + successRate + '%</div><div class="stat-label">Success Rate</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + rpm + '</div>' +
                '<div class="stat-label">Requests/min</div></div>';
            statsEl.innerHTML = html;

            // 2. Latency Histogram
            var latPanel = document.getElementById('panel-latency');
            var recentLogs = router.recent_logs || [];
            if (recentLogs.length > 0) {
                latPanel.style.display = 'block';
                var buckets = {'<100ms': 0, '100-500ms': 0, '500ms-1s': 0, '1-3s': 0, '3s+': 0};
                recentLogs.forEach(function(l) {
                    var ms = l.latency_ms || 0;
                    if (ms < 100) buckets['<100ms']++;
                    else if (ms < 500) buckets['100-500ms']++;
                    else if (ms < 1000) buckets['500ms-1s']++;
                    else if (ms < 3000) buckets['1-3s']++;
                    else buckets['3s+']++;
                });
                var maxCount = Math.max.apply(null, Object.values(buckets).concat([1]));
                var latHtml = '';
                Object.keys(buckets).forEach(function(k) {
                    var count = buckets[k];
                    var pct = (count / maxCount * 100).toFixed(0);
                    var pctOfTotal = recentLogs.length > 0 ? (count / recentLogs.length * 100).toFixed(1) : '0';
                    latHtml += '<div class="metric-bar-row">' +
                        '<span class="metric-bar-label">' + k + '</span>' +
                        '<div class="metric-bar"><div class="metric-bar-fill" style="width:' + pct + '%"></div></div>' +
                        '<span class="metric-bar-value">' + count + ' (' + pctOfTotal + '%)</span></div>';
                });
                document.getElementById('latency-histogram').innerHTML = latHtml;
            } else {
                latPanel.style.display = 'none';
            }

            // 3. Model Usage Distribution
            var muPanel = document.getElementById('panel-model-usage');
            if (modelUsage.length > 0) {
                muPanel.style.display = 'block';
                modelUsage.sort(function(a, b) { return (b.requests || 0) - (a.requests || 0); });
                var muHtml = '<table class="data-table"><thead><tr><th>Model</th><th>Requests</th>' +
                    '<th>Total Cost</th><th>Avg Latency</th></tr></thead><tbody>';
                modelUsage.forEach(function(m, i) {
                    var rowStyle = i === 0 ? ' style="color:var(--accent);font-weight:600"' : '';
                    muHtml += '<tr><td' + rowStyle + '>' + (m.model || '-') + '</td>' +
                        '<td>' + (m.requests || 0) + '</td>' +
                        '<td>$' + (m.total_cost || 0).toFixed(6) + '</td>' +
                        '<td>' + (m.avg_latency || 0).toFixed(0) + 'ms</td></tr>';
                });
                muHtml += '</tbody></table>';
                document.getElementById('model-usage-table').innerHTML = muHtml;
            } else {
                muPanel.style.display = 'none';
            }

            // 4. Error Rate Widget
            var errPanel = document.getElementById('panel-errors');
            var errorRate = total > 0 ? (failed / total * 100) : 0;
            var errColor = errorRate < 1 ? 'var(--success)' : errorRate < 5 ? 'var(--warning)' : 'var(--danger)';
            var errCount = (logLevels.error || logLevels.ERROR || 0);
            var warnCount = (logLevels.warning || logLevels.WARNING || logLevels.warn || logLevels.WARN || 0);
            errPanel.style.display = 'block';
            document.getElementById('error-rate-content').innerHTML =
                '<div class="stat-cards" style="margin-bottom:0">' +
                '<div class="stat-card"><div class="stat-value" style="color:' + errColor + '">' +
                errorRate.toFixed(2) + '%</div><div class="stat-label">Error Rate</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="color:var(--danger)">' + errCount +
                '</div><div class="stat-label">Error Log Entries</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="color:var(--warning)">' + warnCount +
                '</div><div class="stat-label">Warning Log Entries</div></div></div>';

            // 5. Cache Performance Panel
            var cachePanel = document.getElementById('panel-cache');
            if (cache && (cache.total_entries || cache.total_hits)) {
                cachePanel.style.display = 'block';
                var hitRate = cache.total_entries > 0 && cache.total_hits > 0
                    ? (cache.total_hits / (cache.total_hits + cache.total_entries) * 100).toFixed(1) : '0.0';
                var cacheHtml = '<div class="stat-cards" style="margin-bottom:12px">' +
                    '<div class="stat-card"><div class="stat-value">' + hitRate + '%</div>' +
                    '<div class="stat-label">Hit Rate</div></div>' +
                    '<div class="stat-card"><div class="stat-value">' + (cache.tokens_saved || 0) + '</div>' +
                    '<div class="stat-label">Tokens Saved</div></div>' +
                    '<div class="stat-card"><div class="stat-value">$' + (cache.cost_saved || 0).toFixed(4) + '</div>' +
                    '<div class="stat-label">Cost Saved</div></div>' +
                    '<div class="stat-card"><div class="stat-value">' + (cache.total_entries || 0) + '</div>' +
                    '<div class="stat-label">Cache Entries</div></div></div>' +
                    '<div style="max-width:400px"><div class="progress-label"><span>Hit Rate</span><span>' + hitRate + '%</span></div>' +
                    '<div class="progress-bar"><div class="progress-fill green" style="width:' + hitRate + '%"></div></div></div>';
                document.getElementById('cache-content').innerHTML = cacheHtml;
            } else {
                cachePanel.style.display = 'none';
            }
        }).catch(function(e) {
            document.getElementById('monitoring-stats').innerHTML = '<div class="loading">Error loading monitoring: ' + e.message + '</div>';
        });
    }

    // --- Models Tab (supports both wizard rules[] and legacy task_routing{} formats) ---
    var _strategyData = null;
    function loadModels() {
        apiGet('/api/strategy').then(function(data) {
            _strategyData = data;
            var el = document.getElementById('models-content');
            if (!data || data.error) { el.innerHTML = '<div class="loading">No strategy.json found. Click Regenerate.</div>'; return; }

            // New wizard format: { optimization, rules: [{taskCategory, primaryModel, fallbackModel}] }
            var rules = data.rules || [];
            var optimization = data.optimization || 'balanced';
            var html = '';

            if (rules.length > 0) {
                // Optimization preset selector
                html += '<div style="margin-bottom:16px;display:flex;align-items:center;gap:12px">' +
                    '<span style="font-size:13px;color:var(--text-secondary)">Optimization:</span>' +
                    '<select id="opt-select" onchange="updateOptimization(this.value)" ' +
                    'style="background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);padding:6px 12px;border-radius:6px;font-size:13px">' +
                    '<option value="cost"' + (optimization === 'cost' ? ' selected' : '') + '>Cost</option>' +
                    '<option value="speed"' + (optimization === 'speed' ? ' selected' : '') + '>Speed</option>' +
                    '<option value="quality"' + (optimization === 'quality' ? ' selected' : '') + '>Quality</option>' +
                    '<option value="balanced"' + (optimization === 'balanced' ? ' selected' : '') + '>Balanced</option>' +
                    '</select></div>';
                // Editable rules table
                html += '<table class="data-table"><thead><tr><th>Task Category</th><th>Primary Model</th>' +
                    '<th>Fallback Model</th><th></th></tr></thead><tbody>';
                rules.forEach(function(r, i) {
                    html += '<tr>' +
                        '<td style="color:var(--text-primary);font-weight:600">' + (r.taskCategory || '-') + '</td>' +
                        '<td><input type="text" value="' + (r.primaryModel || '') + '" ' +
                        'data-idx="' + i + '" data-field="primaryModel" onchange="updateRule(this)" ' +
                        'style="background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);' +
                        'padding:4px 8px;border-radius:4px;font-size:12px;width:100%;font-family:monospace"></td>' +
                        '<td><input type="text" value="' + (r.fallbackModel || '') + '" ' +
                        'data-idx="' + i + '" data-field="fallbackModel" onchange="updateRule(this)" ' +
                        'style="background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);' +
                        'padding:4px 8px;border-radius:4px;font-size:12px;width:100%;font-family:monospace"></td>' +
                        '<td style="width:40px;text-align:center"><button class="btn" onclick="removeRule(' + i + ')" ' +
                        'style="padding:2px 8px;font-size:11px;color:var(--danger);background:none;border:1px solid var(--danger);border-radius:4px">&times;</button></td></tr>';
                });
                html += '</tbody></table>';
                html += '<div style="margin-top:12px;display:flex;gap:8px">' +
                    '<button class="btn btn-accent" onclick="addRule()" style="font-size:12px;padding:6px 14px">+ Add Rule</button>' +
                    '<button class="btn btn-accent" onclick="saveStrategy()" id="btn-save-strategy" ' +
                    'style="font-size:12px;padding:6px 14px;background:var(--success)">Save Strategy</button></div>';
            } else {
                // Legacy format: task_routing{ task: {primary:{}, fallback:{}} }
                var routing = data.task_routing || {};
                var keys = Object.keys(routing);
                if (!keys.length) { el.innerHTML = '<div class="loading">No task routing configured.</div>'; return; }
                html += '<table class="data-table"><thead><tr><th>Task Type</th><th>Primary Model</th>' +
                    '<th>Provider</th><th>Score</th><th>Fallback</th></tr></thead><tbody>';
                keys.forEach(function(k) {
                    var r = routing[k]; var p = r.primary || {}; var f = r.fallback || {};
                    html += '<tr><td style="color:var(--text-primary);font-weight:600">' + k + '</td>' +
                        '<td>' + (p.model || '-') + '</td><td>' + (p.provider || '-') + '</td>' +
                        '<td>' + (p.score != null ? p.score.toFixed(1) : '-') + '</td>' +
                        '<td>' + (f.model || '-') + '</td></tr>';
                });
                html += '</tbody></table>';
            }

            if (data.monthly_cost_estimate) {
                var c = data.monthly_cost_estimate;
                html += '<div style="margin-top:16px;font-size:13px;color:var(--text-secondary)">' +
                    'Monthly cost estimate: $' + (c.min || 0).toFixed(2) + ' - $' + (c.max || 0).toFixed(2) +
                    ' <span style="color:var(--text-secondary);font-size:11px">(' + (c.note || '') + ')</span></div>';
            }
            el.innerHTML = html;

            // Load router health, routing log, providers, optimization rules
            loadRouterHealth();
            loadProviders();
        }).catch(function(e) {
            document.getElementById('models-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    function loadRouterHealth() {
        apiGet('/api/router').then(function(data) {
            var panel = document.getElementById('panel-router-health');
            if (!data || data.error) { panel.style.display = 'none'; return; }
            panel.style.display = 'block';
            var uptime = data.uptime_seconds || 0;
            var uptimeStr = uptime > 3600 ? (uptime / 3600).toFixed(1) + 'h' :
                            uptime > 60 ? (uptime / 60).toFixed(0) + 'm' : uptime + 's';
            var served = data.requests_served || 0;
            var failed = data.requests_failed || 0;
            var failRate = (served + failed) > 0 ? (failed / (served + failed) * 100).toFixed(2) : '0';
            var strategy = data.strategy || {};
            document.getElementById('router-health-content').innerHTML =
                '<div class="stat-cards" style="margin-bottom:0">' +
                '<div class="stat-card"><div class="stat-value">' + uptimeStr + '</div><div class="stat-label">Uptime</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + served + '</div><div class="stat-label">Requests Served</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="color:' +
                (parseFloat(failRate) < 1 ? 'var(--success)' : 'var(--danger)') + '">' + failRate + '%</div>' +
                '<div class="stat-label">Failure Rate</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="font-size:14px">' +
                (strategy.loaded_at || '-') + '</div><div class="stat-label">Strategy Loaded</div></div></div>';

            // Routing log
            var logs = data.recent_logs || [];
            var logPanel = document.getElementById('panel-routing-log');
            if (logs.length > 0) {
                logPanel.style.display = 'block';
                var logHtml = '<table class="data-table"><thead><tr><th>Time</th><th>Model</th><th>Provider</th>' +
                    '<th>Latency</th><th>Status</th><th>Route</th></tr></thead><tbody>';
                logs.slice(0, 20).forEach(function(l) {
                    var statusColor = (l.status || 200) < 400 ? 'var(--success)' : 'var(--danger)';
                    logHtml += '<tr><td style="font-size:11px">' + (l.timestamp || '-') + '</td>' +
                        '<td>' + (l.model || '-') + '</td><td>' + (l.provider || '-') + '</td>' +
                        '<td>' + (l.latency_ms || 0) + 'ms</td>' +
                        '<td style="color:' + statusColor + '">' + (l.status || '-') + '</td>' +
                        '<td>' + (l.route || '-') + '</td></tr>';
                });
                logHtml += '</tbody></table>';
                document.getElementById('routing-log-content').innerHTML = logHtml;
            } else {
                logPanel.style.display = 'none';
            }
        }).catch(function() { document.getElementById('panel-router-health').style.display = 'none'; });
    }

    function loadProviders() {
        apiGet('/api/providers').then(function(data) {
            // Provider Health Scoreboard
            var ph = data.provider_health || {};
            var provPanel = document.getElementById('panel-providers');
            var provKeys = Object.keys(ph);
            if (provKeys.length > 0) {
                provPanel.style.display = 'block';
                var html = '';
                provKeys.forEach(function(p) {
                    var info = ph[p];
                    var score = info.score || 0;
                    var scoreColor = score >= 0.8 ? 'var(--success)' : score >= 0.5 ? 'var(--warning)' : 'var(--danger)';
                    html += '<div class="provider-card"><div class="prov-name">' + p + '</div>' +
                        '<div class="prov-score" style="color:' + scoreColor + '">' + score.toFixed(2) + '</div>' +
                        '<div class="prov-row"><span>Success Rate</span><span>' +
                        ((info.success_rate || 0) * 100).toFixed(1) + '%</span></div>' +
                        '<div class="prov-row"><span>Avg Latency</span><span>' +
                        (info.avg_latency_ms || 0).toFixed(0) + 'ms</span></div>' +
                        '<div class="prov-row"><span>Total Calls</span><span>' +
                        (info.total_calls || 0) + '</span></div></div>';
                });
                document.getElementById('provider-cards').innerHTML = html;
            } else {
                provPanel.style.display = 'none';
            }

            // Optimization Rules Effectiveness
            var rules = data.rules_status || [];
            var rulesPanel = document.getElementById('panel-opt-rules');
            if (rules.length > 0) {
                rulesPanel.style.display = 'block';
                rules.sort(function(a, b) {
                    var aRate = (a.hits + a.misses) > 0 ? a.hits / (a.hits + a.misses) : 0;
                    var bRate = (b.hits + b.misses) > 0 ? b.hits / (b.hits + b.misses) : 0;
                    return bRate - aRate;
                });
                var rHtml = '<table class="data-table"><thead><tr><th>Rule</th><th>Enabled</th>' +
                    '<th>Hits</th><th>Misses</th><th>Hit Rate</th></tr></thead><tbody>';
                rules.forEach(function(r) {
                    var hitRate = (r.hits + r.misses) > 0 ? (r.hits / (r.hits + r.misses) * 100).toFixed(1) : '0.0';
                    rHtml += '<tr><td style="color:var(--text-primary)">' + (r.name || '-') + '</td>' +
                        '<td><span class="severity ' + (r.enabled ? 'severity-low' : 'severity-medium') + '">' +
                        (r.enabled ? 'Yes' : 'No') + '</span></td>' +
                        '<td>' + (r.hits || 0) + '</td><td>' + (r.misses || 0) + '</td>' +
                        '<td>' + hitRate + '%</td></tr>';
                });
                rHtml += '</tbody></table>';
                document.getElementById('opt-rules-content').innerHTML = rHtml;
            } else {
                rulesPanel.style.display = 'none';
            }
        }).catch(function() {
            document.getElementById('panel-providers').style.display = 'none';
            document.getElementById('panel-opt-rules').style.display = 'none';
        });
    }

    window.updateRule = function(input) {
        var idx = parseInt(input.getAttribute('data-idx'));
        var field = input.getAttribute('data-field');
        if (_strategyData && _strategyData.rules && _strategyData.rules[idx]) {
            _strategyData.rules[idx][field] = input.value;
        }
    };
    window.updateOptimization = function(val) {
        if (_strategyData) _strategyData.optimization = val;
    };
    window.removeRule = function(idx) {
        if (_strategyData && _strategyData.rules) {
            _strategyData.rules.splice(idx, 1);
            loadModels();
        }
    };
    window.addRule = function() {
        if (!_strategyData) _strategyData = {optimization: 'balanced', rules: []};
        if (!_strategyData.rules) _strategyData.rules = [];
        _strategyData.rules.push({taskCategory: 'custom', primaryModel: '', fallbackModel: ''});
        loadModels();
    };
    window.saveStrategy = function() {
        var btn = document.getElementById('btn-save-strategy');
        btn.disabled = true; btn.textContent = 'Saving...';
        apiPost('/api/strategy', _strategyData).then(function(r) {
            btn.disabled = false; btn.textContent = 'Save Strategy';
            if (r.success) showToast('Strategy saved successfully', 'success');
            else showToast('Save failed: ' + (r.error || 'unknown'), 'error');
        }).catch(function(e) {
            btn.disabled = false; btn.textContent = 'Save Strategy';
            showToast('Error: ' + e.message, 'error');
        });
    };

    window.regenerateStrategy = function() {
        var btn = document.getElementById('btn-regen');
        btn.disabled = true; btn.textContent = 'Generating...';
        apiPost('/api/strategy/generate').then(function(r) {
            btn.disabled = false; btn.textContent = 'Regenerate Strategy';
            if (r.success) { showToast('Strategy regenerated', 'success'); loadModels(); }
            else showToast('Failed: ' + (r.error || 'unknown'), 'error');
        }).catch(function(e) {
            btn.disabled = false; btn.textContent = 'Regenerate Strategy';
            showToast('Error: ' + e.message, 'error');
        });
    };

    // --- Hardware Tab ---
    function loadHardware() {
        apiGet('/api/hardware').then(function(data) {
            var el = document.getElementById('hardware-content');
            if (!data || data.error) { el.innerHTML = '<div class="loading">No hardware profile found.</div>'; return; }
            var os = data.os || {};
            var cpu = data.cpu || {};
            var gpus = data.gpus || [];
            var gs = data.gpu_summary || {};

            var html = '<div class="cards-grid">' +
                '<div class="card"><div class="hw-stat"><div class="value">' + (cpu.cores || '?') + '</div>' +
                '<div class="label">CPU Cores</div></div>' +
                '<div class="card-body" style="margin-top:12px">' +
                '<div class="row"><span>Brand</span><span>' + (cpu.brand || 'Unknown') + '</span></div>' +
                '<div class="row"><span>Arch</span><span>' + (cpu.arch || 'Unknown') + '</span></div>' +
                '</div></div>' +
                '<div class="card"><div class="hw-stat"><div class="value">' +
                (data.ram_gb ? data.ram_gb.toFixed(1) : '?') + ' GB</div>' +
                '<div class="label">System RAM</div></div>' +
                '<div class="card-body" style="margin-top:12px">' +
                '<div class="row"><span>OS</span><span>' + (os.name || '?') + ' ' + (os.version || '') + '</span></div>' +
                '<div class="row"><span>Arch</span><span>' + (os.arch || '?') + '</span></div>' +
                '</div></div>';

            if (gpus.length > 0) {
                gpus.forEach(function(g) {
                    html += '<div class="card"><div class="hw-stat"><div class="value">' +
                        (g.vram_gb ? g.vram_gb.toFixed(0) : '?') + ' GB</div>' +
                        '<div class="label">GPU VRAM</div></div>' +
                        '<div class="card-body" style="margin-top:12px">' +
                        '<div class="row"><span>GPU</span><span>' + (g.name || 'Unknown') + '</span></div>' +
                        '<div class="row"><span>Vendor</span><span>' + (g.vendor || '?') + '</span></div>' +
                        '<div class="row"><span>API</span><span>' + (g.api || '?') + '</span></div>' +
                        '</div></div>';
                });
            }

            if (gs.has_gpu) {
                html += '<div class="card"><div class="card-header"><span class="card-title">GPU Summary</span></div>' +
                    '<div class="card-body">' +
                    '<div class="row"><span>Primary Vendor</span><span>' + (gs.primary_vendor || '?') + '</span></div>' +
                    '<div class="row"><span>Primary API</span><span>' + (gs.primary_api || '?') + '</span></div>' +
                    '<div class="row"><span>Total VRAM</span><span>' + (gs.total_vram_gb || 0) + ' GB</span></div>' +
                    '<div class="row"><span>GPU Count</span><span>' + (gs.gpu_count || 0) + '</span></div>' +
                    '</div></div>';
            }
            html += '</div>';
            el.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('hardware-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Fine-Tuning Tab ---
    function loadAdapters() {
        apiGet('/api/adapters').then(function(data) {
            var el = document.getElementById('adapters-content');
            if (!data || !data.length) { el.innerHTML = '<div class="loading">No adapters found.</div>'; return; }
            var html = '<div style="margin-bottom:12px;font-size:13px;color:var(--text-secondary)">' +
                data.length + ' adapters found</div><div class="adapter-grid">';
            data.forEach(function(a) {
                html += '<div class="adapter-card"><div class="adapter-id">' + a.id + '</div>' +
                    '<div class="adapter-domain">' + (a.domain || 'general') + '</div>' +
                    '<div style="margin-top:6px;font-size:11px;color:var(--text-secondary)">' +
                    'Status: ' + (a.status || 'unknown') + '</div></div>';
            });
            html += '</div>';
            el.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('adapters-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Security Tab ---
    function loadSecurity() {
        // Fetch security events + rules in parallel
        Promise.all([
            apiGet('/api/security/events').catch(function() { return {events: [], summary: {}}; }),
            apiGet('/api/security').catch(function() { return null; })
        ]).then(function(results) {
            var evData = results[0] || {};
            var rulesData = results[1];

            var events = evData.events || [];
            var summary = evData.summary || {};

            // 16. Severity Distribution Summary
            var summaryEl = document.getElementById('severity-summary');
            var sevLevels = ['critical', 'high', 'medium', 'low', 'info'];
            var totalEvents = 0;
            sevLevels.forEach(function(s) { totalEvents += (summary[s] || 0); });
            var sevHtml = '';
            sevLevels.forEach(function(s) {
                var count = summary[s] || 0;
                sevHtml += '<div class="stat-card"><div class="stat-value severity severity-' + s + '" style="font-size:28px">' +
                    count + '</div><div class="stat-label">' + s.charAt(0).toUpperCase() + s.slice(1) + '</div></div>';
            });
            sevHtml += '<div class="stat-card"><div class="stat-value">' + totalEvents +
                '</div><div class="stat-label">Total Events</div></div>';
            summaryEl.innerHTML = sevHtml;

            // 15. Security Events Feed
            var evPanel = document.getElementById('panel-sec-events');
            if (events.length > 0) {
                evPanel.style.display = 'block';
                var evHtml = '<table class="data-table"><thead><tr><th>Time</th><th>Severity</th>' +
                    '<th>Type</th><th>Agent</th><th>Details</th><th>Status</th></tr></thead><tbody>';
                events.forEach(function(ev) {
                    var sev = (ev.severity || 'info').toLowerCase();
                    var resolved = ev.resolved || false;
                    var rowStyle = !resolved ? ' style="background:rgba(255,71,87,0.05)"' : '';
                    evHtml += '<tr' + rowStyle + '><td style="font-size:11px">' + (ev.timestamp || '-') + '</td>' +
                        '<td><span class="severity severity-' + sev + '">' + sev + '</span></td>' +
                        '<td>' + (ev.event_type || '-') + '</td>' +
                        '<td>' + (ev.agent_id || '-') + '</td>' +
                        '<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
                        (typeof ev.details === 'string' ? ev.details : JSON.stringify(ev.details || '')) + '</td>' +
                        '<td><span class="severity ' + (resolved ? 'severity-low' : 'severity-high') + '">' +
                        (resolved ? 'Resolved' : 'Open') + '</span></td></tr>';
                });
                evHtml += '</tbody></table>';
                document.getElementById('security-events-content').innerHTML = evHtml;
            } else {
                evPanel.style.display = events.length > 0 ? 'block' : 'none';
            }

            // 17. Compliance Status Cards from security rules
            var compPanel = document.getElementById('panel-compliance');
            if (rulesData && !rulesData.error) {
                compPanel.style.display = 'block';
                var domains = rulesData.domains || rulesData;
                var dKeys = Object.keys(domains);
                var compHtml = '';
                dKeys.forEach(function(k) {
                    var val = domains[k];
                    var count = 0;
                    if (Array.isArray(val)) count = val.length;
                    else if (typeof val === 'object' && val !== null) count = Object.keys(val).length;
                    var loaded = count > 0;
                    compHtml += '<div class="compliance-card"><div class="comp-header">' +
                        '<span class="comp-name">' + k.replace(/_/g, ' ') + '</span>' +
                        '<span class="comp-status ' + (loaded ? 'comp-loaded' : 'comp-missing') + '">' +
                        (loaded ? 'Loaded' : 'Missing') + '</span></div>' +
                        '<div style="font-size:12px;color:var(--text-secondary)">' + count + ' rules configured</div></div>';
                });
                document.getElementById('compliance-cards').innerHTML = compHtml;
            } else {
                compPanel.style.display = 'none';
            }
        }).catch(function(e) {
            document.getElementById('severity-summary').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Costs Tab ---
    function loadCosts() {
        Promise.all([
            apiGet('/api/billing'),
            apiGet('/api/budgets').catch(function() { return {}; })
        ]).then(function(results) {
            var data = results[0];
            var budgetData = results[1] || {};
            var el = document.getElementById('costs-content');
            if (!data) { el.innerHTML = '<div class="loading">No billing data available.</div>'; return; }

            var html = '<div class="cards-grid">';
            html += '<div class="card"><div class="hw-stat"><div class="value">' +
                (data.total_records || 0) + '</div><div class="label">Total Usage Records</div></div></div>';

            if (data.total_cost != null) {
                html += '<div class="card"><div class="hw-stat"><div class="value">$' +
                    (data.total_cost || 0).toFixed(4) + '</div><div class="label">Total Cost (DAL)</div></div></div>';
            }

            var reports = data.reports || [];
            if (reports.length > 0) {
                var latest = reports[0];
                var summary = latest.summary || {};
                var pt = latest.period_totals || {};
                html += '<div class="card"><div class="hw-stat"><div class="value">$' +
                    (pt.daily != null ? pt.daily.toFixed(4) : '0') + '</div>' +
                    '<div class="label">Today</div></div></div>' +
                    '<div class="card"><div class="hw-stat"><div class="value">$' +
                    (pt.weekly != null ? pt.weekly.toFixed(4) : '0') + '</div>' +
                    '<div class="label">This Week</div></div></div>' +
                    '<div class="card"><div class="hw-stat"><div class="value">$' +
                    (pt.monthly != null ? pt.monthly.toFixed(4) : '0') + '</div>' +
                    '<div class="label">This Month</div></div></div>';

                var cbm = summary.cost_by_model || {};
                var models = Object.keys(cbm).sort(function(a,b) { return cbm[b] - cbm[a]; });
                if (models.length > 0) {
                    html += '</div><div style="margin-top:20px"><div class="section-title" style="font-size:16px">' +
                        'Top Models by Cost</div><table class="data-table"><thead><tr><th>Model</th>' +
                        '<th>Cost</th><th>Requests</th></tr></thead><tbody>';
                    models.slice(0, 10).forEach(function(m) {
                        var tokens = (summary.tokens_by_model || {})[m] || {};
                        html += '<tr><td>' + m + '</td><td>$' + cbm[m].toFixed(6) + '</td>' +
                            '<td>' + (tokens.requests || 0) + '</td></tr>';
                    });
                    html += '</tbody></table></div>';
                } else {
                    html += '</div>';
                }
            } else {
                html += '</div><div class="loading" style="margin-top:16px">No reports generated yet. ' +
                    'Run: python3 shared/claw_billing.py --report daily</div>';
            }
            el.innerHTML = html;

            // 18. Budget Progress Bars
            var budgetPanel = document.getElementById('panel-budgets');
            var config = budgetData.config || data.config || {};
            var budgets = config.budgets || config.thresholds || {};
            var dailySpend = budgetData.daily_spend || 0;
            var weeklySpend = budgetData.weekly_spend || 0;
            var monthlySpend = budgetData.monthly_spend || 0;
            var violations = budgetData.violations || [];

            var hasBudgets = budgets.daily || budgets.weekly || budgets.monthly || dailySpend > 0 || weeklySpend > 0 || monthlySpend > 0;
            if (hasBudgets) {
                budgetPanel.style.display = 'block';
                var bHtml = '';
                var periods = [
                    {name: 'Daily', spend: dailySpend, limit: budgets.daily || 0},
                    {name: 'Weekly', spend: weeklySpend, limit: budgets.weekly || 0},
                    {name: 'Monthly', spend: monthlySpend, limit: budgets.monthly || 0}
                ];
                periods.forEach(function(p) {
                    if (p.limit <= 0 && p.spend <= 0) return;
                    var pct = p.limit > 0 ? (p.spend / p.limit * 100) : 0;
                    var color = pct < 75 ? 'green' : pct < 100 ? 'yellow' : 'red';
                    var displayPct = Math.min(pct, 100);
                    bHtml += '<div style="margin-bottom:12px">' +
                        '<div class="progress-label"><span>' + p.name + ': $' + p.spend.toFixed(4) +
                        (p.limit > 0 ? ' / $' + p.limit.toFixed(2) : '') + '</span>' +
                        '<span>' + pct.toFixed(1) + '%</span></div>' +
                        '<div class="progress-bar"><div class="progress-fill ' + color + '" style="width:' + displayPct + '%"></div></div></div>';
                });
                if (violations.length > 0) {
                    bHtml += '<div style="margin-top:8px">';
                    violations.forEach(function(v) {
                        bHtml += '<span class="severity severity-' + (v.level === 'critical' ? 'critical' : 'high') + '" ' +
                            'style="margin-right:6px">' + v.level.toUpperCase() + ': ' + v.period + ' budget ' +
                            v.percent.toFixed(0) + '% used</span>';
                    });
                    bHtml += '</div>';
                }
                document.getElementById('budget-bars').innerHTML = bHtml;
            } else {
                budgetPanel.style.display = 'none';
            }

            // 19. Cost by Provider + Cost by Agent breakdown from DAL aggregate
            var agg = data;
            var costByProvider = agg.cost_by_provider || (agg.reports && agg.reports[0] && agg.reports[0].summary ? agg.reports[0].summary.cost_by_provider : null) || {};
            var costByAgent = agg.cost_by_agent || (agg.reports && agg.reports[0] && agg.reports[0].summary ? agg.reports[0].summary.cost_by_agent : null) || {};

            var cpPanel = document.getElementById('panel-cost-provider');
            var cpKeys = Object.keys(costByProvider).sort(function(a,b) { return costByProvider[b] - costByProvider[a]; });
            if (cpKeys.length > 0) {
                cpPanel.style.display = 'block';
                var cpHtml = '<table class="data-table"><thead><tr><th>Provider</th><th>Total Cost</th></tr></thead><tbody>';
                cpKeys.forEach(function(p) {
                    cpHtml += '<tr><td>' + p + '</td><td>$' + costByProvider[p].toFixed(6) + '</td></tr>';
                });
                cpHtml += '</tbody></table>';
                document.getElementById('cost-provider-table').innerHTML = cpHtml;
            } else {
                cpPanel.style.display = 'none';
            }

            var caPanel = document.getElementById('panel-cost-agent');
            var caKeys = Object.keys(costByAgent).sort(function(a,b) { return costByAgent[b] - costByAgent[a]; });
            if (caKeys.length > 0) {
                caPanel.style.display = 'block';
                var caHtml = '<table class="data-table"><thead><tr><th>Agent</th><th>Total Cost</th></tr></thead><tbody>';
                caKeys.forEach(function(a) {
                    caHtml += '<tr><td>' + a + '</td><td>$' + costByAgent[a].toFixed(6) + '</td></tr>';
                });
                caHtml += '</tbody></table>';
                document.getElementById('cost-agent-table').innerHTML = caHtml;
            } else {
                caPanel.style.display = 'none';
            }
        }).catch(function(e) {
            document.getElementById('costs-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Activity Tab (Real-Time SSE) ---
    var _sseSource = null;
    var _sseRetryDelay = 1000;
    var _sseRetryTimer = null;
    var _clawSparklines = {};  // claw_id -> [req_served_deltas]
    var _prevClawRequests = {};

    function loadActivity() {
        connectSSE();
    }

    function connectSSE() {
        if (_sseSource) return;
        _updateSSEStatus('connecting');

        _sseSource = new EventSource('/api/activity/stream');

        _sseSource.onopen = function() {
            _sseRetryDelay = 1000;  // reset backoff
            _updateSSEStatus('connected');
        };

        _sseSource.onerror = function() {
            disconnectSSE();
            _updateSSEStatus('disconnected');
            // Exponential backoff reconnect
            _sseRetryTimer = setTimeout(function() {
                if (currentTab === 'activity') connectSSE();
            }, _sseRetryDelay);
            _sseRetryDelay = Math.min(_sseRetryDelay * 2, 15000);
        };

        _sseSource.addEventListener('fleet_snapshot', function(e) {
            try {
                var data = JSON.parse(e.data);
                updateTickers(data);
                updateClawGrid(data.claws || []);
            } catch (err) {}
        });

        _sseSource.addEventListener('request_completed', function(e) {
            try {
                var data = JSON.parse(e.data);
                addFeedItem(data);
            } catch (err) {}
        });

        _sseSource.addEventListener('claw_status_change', function(e) {
            try {
                var data = JSON.parse(e.data);
                addStatusChange(data);
            } catch (err) {}
        });

        _sseSource.addEventListener('cost_update', function(e) {
            try {
                var data = JSON.parse(e.data);
                var daily = document.getElementById('tk-daily-cost');
                var monthly = document.getElementById('tk-monthly-cost');
                if (daily) daily.textContent = '$' + (data.daily || 0).toFixed(4);
                if (monthly) monthly.textContent = '$' + (data.monthly || 0).toFixed(4);
            } catch (err) {}
        });
    }

    function disconnectSSE() {
        if (_sseSource) {
            _sseSource.close();
            _sseSource = null;
        }
        if (_sseRetryTimer) {
            clearTimeout(_sseRetryTimer);
            _sseRetryTimer = null;
        }
    }

    function _updateSSEStatus(state) {
        var dot = document.getElementById('sse-dot');
        var text = document.getElementById('sse-status-text');
        if (!dot || !text) return;
        dot.className = 'sse-dot ' + state;
        if (state === 'connected') text.textContent = 'Connected - Live';
        else if (state === 'connecting') text.textContent = 'Connecting...';
        else text.textContent = 'Disconnected - Reconnecting...';
    }

    function updateTickers(data) {
        var fields = {
            'tk-online': data.claws_online + '/' + data.claws_total,
            'tk-requests': data.total_requests || 0,
            'tk-rpm': data.rpm || 0,
            'tk-failed': data.total_failed || 0,
            'tk-conversations': data.conversations || 0
        };
        Object.keys(fields).forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.textContent = fields[id];
        });
        // Color the failed ticker
        var failEl = document.getElementById('tk-failed');
        if (failEl) {
            var val = parseInt(failEl.textContent) || 0;
            failEl.style.color = val > 0 ? 'var(--danger)' : 'var(--success)';
        }
    }

    function updateClawGrid(claws) {
        var grid = document.getElementById('claw-grid');
        if (!grid || !claws.length) {
            if (grid) grid.innerHTML = '<div class="loading">No claws detected.</div>';
            return;
        }
        var html = '';
        claws.forEach(function(c) {
            var isRunning = c.status === 'running';
            // Sparkline data
            var prevReqs = _prevClawRequests[c.id] || 0;
            var delta = (c.requests_served || 0) - prevReqs;
            if (delta < 0) delta = 0;
            _prevClawRequests[c.id] = c.requests_served || 0;
            if (!_clawSparklines[c.id]) _clawSparklines[c.id] = [];
            _clawSparklines[c.id].push(delta);
            if (_clawSparklines[c.id].length > 20) _clawSparklines[c.id].shift();

            var sparkData = _clawSparklines[c.id];
            var maxSpark = Math.max.apply(null, sparkData.concat([1]));

            html += '<div class="claw-mini" onclick="showClawDetail(\'' + c.id + '\')">' +
                '<div class="claw-mini-header">' +
                '<span class="claw-mini-name">' + escHtml(c.name || c.id) + '</span>' +
                '<span class="claw-mini-dot ' + (isRunning ? 'running' : 'stopped') + '"></span></div>' +
                '<div class="claw-mini-metrics">' +
                '<div class="metric-row"><span>CPU</span><span>' + (c.cpu_percent || 0).toFixed(0) + '%</span></div>' +
                '<div class="metric-row"><span>Mem</span><span>' + (c.mem_percent || 0).toFixed(0) + '%</span></div>' +
                '<div class="metric-row"><span>Reqs</span><span>' + (c.requests_served || 0) + '</span></div>' +
                '</div>' +
                '<div class="sparkline">';
            sparkData.forEach(function(v) {
                var h = Math.max(1, Math.round(v / maxSpark * 20));
                html += '<div class="sparkline-bar" style="height:' + h + 'px"></div>';
            });
            html += '</div></div>';
        });
        grid.innerHTML = html;
    }

    function addFeedItem(data) {
        var body = document.getElementById('feed-body');
        if (!body) return;
        var time = (data.created_at || '').split('T')[1] || data.created_at || '';
        if (time.length > 8) time = time.substring(0, 8);
        var latency = data.latency_ms || 0;
        var latClass = latency < 500 ? 'latency-fast' : latency < 2000 ? 'latency-mid' : 'latency-slow';
        var statusOk = (data.status_code || 200) < 400;
        var row = document.createElement('tr');
        row.className = 'feed-new';
        row.innerHTML = '<td>' + time + '</td>' +
            '<td>' + escHtml(data.model || '-') + '</td>' +
            '<td>' + escHtml(data.provider || '-') + '</td>' +
            '<td class="' + latClass + '">' + latency + 'ms</td>' +
            '<td style="color:' + (statusOk ? 'var(--success)' : 'var(--danger)') + '">' +
            (data.status_code || 200) + '</td>' +
            '<td>$' + (data.cost_usd || 0).toFixed(6) + '</td>';
        body.insertBefore(row, body.firstChild);
        // Cap at 100 rows
        while (body.children.length > 100) {
            body.removeChild(body.lastChild);
        }
    }

    function addStatusChange(data) {
        var timeline = document.getElementById('status-timeline');
        if (!timeline) return;
        // Clear placeholder
        var placeholder = timeline.querySelector('.loading');
        if (placeholder) placeholder.remove();
        var now = new Date().toLocaleTimeString();
        var icon = data.new_status === 'running' ? '&#9650;' : '&#9660;';
        var color = data.new_status === 'running' ? 'var(--success)' : 'var(--danger)';
        var entry = document.createElement('div');
        entry.className = 'status-entry';
        entry.innerHTML = '<span class="status-entry-time">' + now + '</span>' +
            '<span class="status-entry-icon" style="color:' + color + '">' + icon + '</span>' +
            '<span><strong>' + escHtml(data.name || data.claw_id) + '</strong> changed from ' +
            '<span style="color:var(--text-secondary)">' + (data.old_status || '?') + '</span> to ' +
            '<span style="color:' + color + '">' + (data.new_status || '?') + '</span></span>';
        timeline.insertBefore(entry, timeline.firstChild);
        // Cap at 50 entries
        while (timeline.children.length > 50) {
            timeline.removeChild(timeline.lastChild);
        }
    }

    window.showClawDetail = function(clawId) {
        apiGet('/api/activity/claw/' + clawId).then(function(data) {
            var overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

            var statusColor = data.status === 'running' ? 'var(--success)' : 'var(--danger)';
            var router = data.router || {};
            var watchdog = data.watchdog || {};
            var wdAgents = watchdog.agents || {};
            var resources = {};
            // Try to find this claw's resources in watchdog
            Object.keys(wdAgents).forEach(function(k) {
                if (wdAgents[k].resources) resources = wdAgents[k].resources;
            });

            var html = '<div class="modal-content">' +
                '<div class="modal-header"><h3>' + escHtml(data.name || data.claw_id) +
                ' <span style="color:' + statusColor + ';font-size:12px">' + (data.status || 'unknown') + '</span></h3>' +
                '<button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()">&times;</button></div>' +
                '<div class="modal-body">';

            // Stats cards
            html += '<div class="stat-cards">' +
                '<div class="stat-card"><div class="stat-value">' + (router.requests_served || 0) +
                '</div><div class="stat-label">Requests Served</div></div>' +
                '<div class="stat-card"><div class="stat-value" style="color:' +
                ((router.requests_failed || 0) > 0 ? 'var(--danger)' : 'var(--success)') + '">' +
                (router.requests_failed || 0) +
                '</div><div class="stat-label">Failed</div></div>' +
                '<div class="stat-card"><div class="stat-value">' +
                (resources.cpu_percent || 0).toFixed(0) + '%</div><div class="stat-label">CPU</div></div>' +
                '<div class="stat-card"><div class="stat-value">' +
                (resources.mem_percent || 0).toFixed(0) + '%</div><div class="stat-label">Memory</div></div>' +
                '</div>';

            // Recent requests from router
            var logs = router.recent_logs || [];
            if (logs.length > 0) {
                html += '<div style="margin-top:16px"><strong>Recent Requests</strong>' +
                    '<table class="data-table"><thead><tr><th>Time</th><th>Model</th><th>Provider</th>' +
                    '<th>Latency</th><th>Status</th></tr></thead><tbody>';
                logs.slice(0, 15).forEach(function(l) {
                    var sColor = (l.status || 200) < 400 ? 'var(--success)' : 'var(--danger)';
                    html += '<tr><td style="font-size:11px">' + (l.timestamp || '-') + '</td>' +
                        '<td>' + (l.model || '-') + '</td><td>' + (l.provider || '-') + '</td>' +
                        '<td>' + (l.latency_ms || 0) + 'ms</td>' +
                        '<td style="color:' + sColor + '">' + (l.status || '-') + '</td></tr>';
                });
                html += '</tbody></table></div>';
            }

            // Conversations
            var convs = data.conversations || [];
            if (convs.length > 0) {
                html += '<div style="margin-top:16px"><strong>Conversations (' + convs.length + ')</strong>' +
                    '<table class="data-table"><thead><tr><th>ID</th><th>Title</th><th>Updated</th>' +
                    '<th>Status</th></tr></thead><tbody>';
                convs.slice(0, 10).forEach(function(cv) {
                    html += '<tr><td style="font-size:11px;font-family:monospace">' +
                        (cv.id || '-').substring(0, 8) + '</td>' +
                        '<td>' + escHtml(cv.title || '(untitled)') + '</td>' +
                        '<td style="font-size:11px">' + (cv.updated_at || '-') + '</td>' +
                        '<td>' + (cv.status || '-') + '</td></tr>';
                });
                html += '</tbody></table></div>';
            }

            html += '</div></div>';
            overlay.innerHTML = html;
            document.body.appendChild(overlay);
        }).catch(function(e) {
            showToast('Error loading claw detail: ' + e.message, 'error');
        });
    };

    // --- Settings Tab ---
    function loadSettings() {
        apiGet('/api/config').then(function(data) {
            var el = document.getElementById('settings-content');
            if (!data || data.error) { el.innerHTML = '<div class="loading">No .env.template found.</div>'; return; }
            var keys = Object.keys(data);
            if (!keys.length) { el.innerHTML = '<div class="loading">Empty configuration.</div>'; return; }
            var html = '<ul class="config-list">';
            keys.forEach(function(k) {
                html += '<li><span class="config-key">' + k + '</span>' +
                    '<span class="config-val">' + (data[k] || '(empty)') + '</span></li>';
            });
            html += '</ul>';
            el.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('settings-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Auto-refresh fleet every 5 seconds (skip activity — uses SSE) ---
    function startPolling() {
        if (fleetInterval) clearInterval(fleetInterval);
        fleetInterval = setInterval(function() {
            if (currentTab === 'activity') return;  // SSE handles this
            if (currentTab === 'fleet') loadFleet();
            else if (currentTab === 'monitoring') loadMonitoring();
        }, 5000);
    }

    // --- Initial load ---
    loadFleet();
    startPolling();
})();
</script>
</body>
</html>"""


# -------------------------------------------------------------------------
# MIME Types for Static File Serving
# -------------------------------------------------------------------------
MIME_TYPES: Dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json",
}


# -------------------------------------------------------------------------
# Request Handler
# -------------------------------------------------------------------------
class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard API and embedded SPA."""

    server_version = "XClawDashboard/1.0"
    metrics: Optional[MetricsCollector] = None
    rate_limiter: RateLimiter = RateLimiter()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging in favor of custom output."""
        pass

    def _get_client_key(self) -> str:
        """Derive a rate-limit key from Bearer token or client IP."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return self.client_address[0]

    def _check_middleware(self) -> bool:
        """
        Run auth + rate-limit checks before request handling.

        Returns True if the request should proceed, False if a response
        has already been sent (401 or 429).
        """
        ok, error_msg = check_auth(self.headers)
        if not ok:
            self._send_json({"error": error_msg}, 401)
            return False

        client_key = self._get_client_key()
        allowed, remaining, reset_at = self.rate_limiter.check(client_key)
        self._rl_remaining = remaining
        self._rl_reset_at = reset_at

        if not allowed:
            body = json.dumps({"error": "Rate limit exceeded. Try again later."}, default=str).encode("utf-8")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
            self.send_header("X-RateLimit-Remaining", str(remaining))
            self.send_header("X-RateLimit-Reset", str(int(reset_at)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return False

        return True

    # ----- Response Helpers -----

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        # Rate-limit headers
        self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
        if hasattr(self, "_rl_remaining"):
            self.send_header("X-RateLimit-Remaining", str(self._rl_remaining))
        if hasattr(self, "_rl_reset_at"):
            self.send_header("X-RateLimit-Reset", str(int(self._rl_reset_at)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        """Send an HTML response."""
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path) -> None:
        """Send a static file with appropriate MIME type."""
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "Not found"}, 404)
            return
        ext = file_path.suffix.lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        try:
            with open(file_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError):
            self._send_json({"error": "Could not read file"}, 500)

    def _send_not_found(self) -> None:
        """Send a 404 response."""
        self._send_json({"error": "Not found"}, 404)

    def _read_body(self) -> Dict[str, Any]:
        """Read and parse JSON request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _extract_agent_id(self) -> Optional[str]:
        """Extract agent ID from path like /api/agents/:id/action."""
        parts = self.path.strip("/").split("/")
        # Expected: api / agents / <id> / <action>
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "agents":
            agent_id = parts[2]
            valid_ids = {a["id"] for a in AGENT_PLATFORMS}
            if agent_id in valid_ids:
                return agent_id
        return None

    # ----- Metrics Endpoint -----

    def _send_metrics(self) -> None:
        """GET /metrics — Prometheus text exposition."""
        if not self.metrics:
            self._send_json({"error": "Metrics not initialized"}, 503)
            return
        body = self.metrics.metrics_handler().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ----- GET Routes -----

    def do_GET(self) -> None:
        """Route GET requests."""
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        path = self.path.split("?")[0]  # Strip query string
        status = 200

        try:
            # Health and metrics bypass auth + rate limiting
            if path == "/metrics":
                self._send_metrics()
                return

            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            if path == "/" or path == "/index.html":
                self._send_html(DASHBOARD_HTML)

            elif path == "/api/agents":
                self._handle_get_agents()

            elif path == "/api/hardware":
                self._handle_get_hardware()

            elif path == "/api/strategy":
                self._handle_get_strategy()

            elif path == "/api/security":
                self._handle_get_security()

            elif path == "/api/adapters":
                self._handle_get_adapters()

            elif path == "/api/billing":
                self._handle_get_billing()

            elif path == "/api/config":
                self._handle_get_config()

            elif path == "/api/status":
                self._handle_get_status()

            elif path == "/api/monitoring":
                self._handle_get_monitoring()

            elif path == "/api/deployments":
                self._handle_get_deployments()

            elif path.startswith("/api/logs"):
                self._handle_get_logs()

            elif path == "/api/router":
                self._handle_get_router()

            elif path == "/api/providers":
                self._handle_get_providers()

            elif path == "/api/security/events":
                self._handle_get_security_events()

            elif path == "/api/budgets":
                self._handle_get_budgets()

            elif path == "/api/audit":
                self._handle_get_audit()

            elif path == "/api/activity/stream":
                self._handle_activity_stream()

            elif path.startswith("/api/activity/claw/"):
                self._handle_activity_claw_detail(path)

            elif path == "/api/activity/requests":
                self._handle_activity_requests()

            elif path.startswith("/wizard/"):
                self._handle_wizard_static(path)

            else:
                status = 404
                self._send_not_found()
        except Exception:
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("GET", path, status, time.time() - start)

    def _handle_get_agents(self) -> None:
        """GET /api/agents — list all agents with health status."""
        agents = get_all_agents_status()
        self._send_json(agents)

    def _handle_get_hardware(self) -> None:
        """GET /api/hardware — read hardware_profile.json."""
        data = read_json_file(HARDWARE_PROFILE_FILE)
        if data is None:
            self._send_json({"error": "hardware_profile.json not found"}, 404)
        else:
            self._send_json(data)

    def _handle_get_strategy(self) -> None:
        """GET /api/strategy — read strategy.json."""
        data = read_json_file(STRATEGY_FILE)
        if data is None:
            self._send_json({"error": "strategy.json not found"}, 404)
        else:
            self._send_json(data)

    def _handle_get_security(self) -> None:
        """GET /api/security — read security_rules.json."""
        data = read_json_file(SECURITY_RULES_FILE)
        if data is None:
            self._send_json({"error": "security_rules.json not found"}, 404)
        else:
            self._send_json(data)

    def _handle_get_adapters(self) -> None:
        """GET /api/adapters — list fine-tuning adapters."""
        adapters = list_adapters()
        self._send_json(adapters)

    def _handle_get_billing(self) -> None:
        """GET /api/billing — read billing data."""
        data = read_billing_data()
        self._send_json(data)

    def _handle_get_config(self) -> None:
        """GET /api/config — read .env.template (redacted)."""
        data = read_env_template_redacted()
        if not data:
            self._send_json({"error": ".env.template not found or empty"}, 404)
        else:
            self._send_json(data)

    def _handle_get_status(self) -> None:
        """GET /api/status — overall system status."""
        agents = get_all_agents_status()
        running = sum(1 for a in agents if a["status"] == "running")
        has_strategy = STRATEGY_FILE.exists()
        has_hardware = HARDWARE_PROFILE_FILE.exists()
        has_security = SECURITY_RULES_FILE.exists()
        adapter_count = len(list_adapters())

        self._send_json({
            "agents_total": len(agents),
            "agents_running": running,
            "strategy_configured": has_strategy,
            "hardware_detected": has_hardware,
            "security_configured": has_security,
            "adapter_count": adapter_count,
            "dashboard_port": DEFAULT_PORT,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    # ----- New Enterprise Endpoints -----

    def _handle_get_monitoring(self) -> None:
        """GET /api/monitoring — composite metrics from Router + Optimizer + Watchdog + DAL."""
        result: Dict[str, Any] = {
            "router": None, "optimizer": None, "_watchdog": None,
            "model_usage": [], "log_levels": {}, "cache": {},
        }
        # Router status
        router = _fetch_internal(ROUTER_PORT, "/api/router/status")
        if router:
            result["router"] = {
                "ok": router.get("ok", False),
                "uptime_seconds": router.get("uptime_seconds", 0),
                "requests_served": router.get("requests_served", 0),
                "requests_failed": router.get("requests_failed", 0),
                "recent_logs": router.get("recent_logs", []),
            }
        # Optimizer status
        optimizer = _fetch_internal(OPTIMIZER_PORT, "/status")
        if optimizer:
            result["optimizer"] = {
                "rules_status": optimizer.get("rules_status", []),
                "cache_stats": optimizer.get("cache_stats", {}),
                "provider_health": optimizer.get("provider_health", {}),
                "cost_tracker_summary": optimizer.get("cost_tracker_summary", {}),
            }
        # Watchdog status (agent resources, connectivity)
        watchdog = _fetch_internal(WATCHDOG_PORT, "/status")
        if watchdog:
            agents_wd = watchdog.get("agents", {})
            result["_watchdog"] = agents_wd
            result["_connectivity"] = watchdog.get("connectivity", {})
        # DAL metrics
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            result["model_usage"] = dal.llm_requests.aggregate_by_model()
            result["log_levels"] = dal.local_logs.count_by_level()
            result["cache"] = dal.response_cache.stats()
        except Exception:
            pass
        self._send_json(result)

    def _handle_get_deployments(self) -> None:
        """GET /api/deployments — recent deployments from DAL."""
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            deployments = dal.deployments.get_recent(10)
            self._send_json(deployments)
        except Exception:
            self._send_json([])

    def _handle_get_logs(self) -> None:
        """GET /api/logs?agent=X&limit=N — recent log entries from DAL."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        agent = params.get("agent", [None])[0]
        limit = 50
        try:
            limit = int(params.get("limit", ["50"])[0])
        except (ValueError, IndexError):
            pass
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            logs = dal.local_logs.query(component=agent, limit=limit)
            self._send_json(logs)
        except Exception:
            self._send_json([])

    def _handle_get_router(self) -> None:
        """GET /api/router — proxy to router status endpoint."""
        data = _fetch_internal(ROUTER_PORT, "/api/router/status")
        if data:
            self._send_json(data)
        else:
            self._send_json({"error": "Router not reachable", "ok": False})

    def _handle_get_providers(self) -> None:
        """GET /api/providers — proxy to optimizer, extract provider_health."""
        data = _fetch_internal(OPTIMIZER_PORT, "/status")
        if data:
            self._send_json({
                "provider_health": data.get("provider_health", {}),
                "rules_status": data.get("rules_status", []),
            })
        else:
            self._send_json({"error": "Optimizer not reachable", "provider_health": {}})

    def _handle_get_security_events(self) -> None:
        """GET /api/security/events — security events + summary from DAL."""
        result: Dict[str, Any] = {"events": [], "summary": {}}
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            result["events"] = dal.security_events.get_recent(50)
            result["summary"] = dal.security_events.get_summary()
        except Exception:
            pass
        self._send_json(result)

    def _handle_get_budgets(self) -> None:
        """GET /api/budgets — budget status from DAL."""
        result: Dict[str, Any] = {
            "violations": [], "daily_spend": 0, "weekly_spend": 0, "monthly_spend": 0,
            "config": None,
        }
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            result["violations"] = dal.costs.check_budgets()
            result["daily_spend"] = dal.costs.daily_spend()
            result["weekly_spend"] = dal.costs.weekly_spend()
            result["monthly_spend"] = dal.costs.monthly_spend()
        except Exception:
            pass
        # Read billing config for budget limits
        config = read_json_file(BILLING_DIR / "billing_config.json")
        if config:
            result["config"] = config
        self._send_json(result)

    def _handle_get_audit(self) -> None:
        """GET /api/audit — audit log entries + alert history."""
        result: Dict[str, Any] = {"audit": [], "alerts": []}
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            result["audit"] = dal.audit.query(limit=30)
            result["alerts"] = dal.alerts.get_history(20)
        except Exception:
            pass
        self._send_json(result)

    def _handle_wizard_static(self, path: str) -> None:
        """GET /wizard/* — serve wizard-ui/dist/ static files."""
        if not WIZARD_DIST.exists():
            self._send_json({"error": "wizard-ui/dist/ not found"}, 404)
            return
        # Strip /wizard/ prefix and resolve relative to dist
        relative = path[len("/wizard/"):]
        if not relative:
            relative = "index.html"
        # Prevent path traversal
        try:
            target = (WIZARD_DIST / relative).resolve()
            if not str(target).startswith(str(WIZARD_DIST.resolve())):
                self._send_not_found()
                return
        except (ValueError, OSError):
            self._send_not_found()
            return
        self._send_file(target)

    # ----- Activity Stream (SSE) -----

    def _handle_activity_stream(self) -> None:
        """GET /api/activity/stream — Server-Sent Events for live activity."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        aggregator = ActivityAggregator.get_instance()
        sub_queue = aggregator.subscribe()
        try:
            while True:
                try:
                    event = sub_queue.get(timeout=15)
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    try:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError,
                            ConnectionAbortedError, OSError):
                        break
                    continue

                if event is None:
                    # Sentinel — evicted
                    break

                # Format SSE
                try:
                    line = json.dumps(event.data, default=str)
                    payload = (f"event: {event.event_type}\n"
                               f"data: {line}\n\n")
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError,
                        ConnectionAbortedError, OSError):
                    break
        finally:
            aggregator.unsubscribe(sub_queue)

    def _handle_activity_claw_detail(self, path: str) -> None:
        """GET /api/activity/claw/<claw_id> — per-claw drill-down."""
        # Extract claw_id from path
        parts = path.strip("/").split("/")
        claw_id = parts[3] if len(parts) > 3 else ""
        if not claw_id:
            self._send_json({"error": "Missing claw_id"}, 400)
            return

        result: Dict[str, Any] = {
            "claw_id": claw_id,
            "status": "unknown",
            "router": None,
            "watchdog": None,
            "conversations": [],
            "recent_requests": [],
        }

        # Find claw config
        deployed = _load_deployed_claws()
        claw_config = next((c for c in deployed if c.get("id") == claw_id), None)

        # Also check base platforms
        plat_config = next((p for p in AGENT_PLATFORMS if p["id"] == claw_id), None)

        if claw_config:
            gw_port = claw_config.get("gateway_port")
            wd_port = claw_config.get("watchdog_port")
            agent_port = claw_config.get("agent_port", 0)
            result["name"] = claw_config.get("name", claw_id)
            result["platform"] = claw_config.get("platform", "")
            result["port"] = agent_port

            # Check status
            container = claw_config.get("container_name", "")
            if container:
                result["status"] = _check_docker_container(container)
            elif agent_port:
                result["status"] = check_agent_health(agent_port)

            # Router stats
            if gw_port:
                result["router"] = _fetch_internal(gw_port, "/api/router/status")

            # Watchdog resources
            if wd_port:
                result["watchdog"] = _fetch_internal(wd_port, "/status")
        elif plat_config:
            result["name"] = plat_config["name"]
            result["platform"] = plat_config["id"]
            result["port"] = plat_config["port"]
            result["status"] = check_agent_health(plat_config["port"])

        # DAL data
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            result["conversations"] = dal.conversations.list_conversations(
                agent_id=claw_id, limit=20)
            result["recent_requests"] = dal.llm_requests.get_recent(20)
        except Exception:
            pass

        self._send_json(result)

    def _handle_activity_requests(self) -> None:
        """GET /api/activity/requests — recent 50 LLM requests."""
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            requests = dal.llm_requests.get_recent(50)
            self._send_json(requests)
        except Exception:
            self._send_json([])

    # ----- POST Routes -----

    def do_POST(self) -> None:
        """Route POST requests."""
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        path = self.path.split("?")[0]
        status = 200

        try:
            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            if path == "/api/strategy":
                self._handle_post_strategy_save()

            elif path == "/api/strategy/generate":
                self._handle_post_strategy_generate()

            elif path == "/api/finetune":
                self._handle_post_finetune()

            elif "/api/agents/" in path:
                self._handle_post_agent_action(path)

            else:
                status = 404
                self._send_not_found()
        except Exception:
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("POST", path, status, time.time() - start)

    def _handle_post_agent_action(self, path: str) -> None:
        """POST /api/agents/:id/(start|stop|restart)."""
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._send_json({"error": "Invalid path"}, 400)
            return

        agent_id = parts[2]
        action = parts[3]

        valid_ids = {a["id"] for a in AGENT_PLATFORMS}
        if agent_id not in valid_ids:
            self._send_json({"error": f"Unknown agent: {agent_id}"}, 404)
            return

        if action not in ("start", "stop", "restart"):
            self._send_json({"error": f"Unknown action: {action}"}, 400)
            return

        if action == "start":
            result = run_claw_command([agent_id, "docker"])
            self._send_json(result)

        elif action == "stop":
            result = run_claw_command([agent_id, "destroy"])
            self._send_json(result)

        elif action == "restart":
            stop_result = run_claw_command([agent_id, "destroy"])
            if not stop_result.get("success"):
                warn(f"Stop failed for {agent_id}, attempting start anyway")
            start_result = run_claw_command([agent_id, "docker"])
            self._send_json({
                "success": start_result.get("success", False),
                "stop_result": stop_result,
                "start_result": start_result,
            })

    def _handle_post_strategy_save(self) -> None:
        """POST /api/strategy — save strategy.json (edit from dashboard)."""
        body = self._read_body()
        if not body:
            self._send_json({"success": False, "error": "Empty body"}, 400)
            return
        # Validate basic structure
        if "rules" not in body and "task_routing" not in body and "optimization" not in body:
            self._send_json({"success": False, "error": "Must contain 'rules' or 'optimization'"}, 400)
            return
        try:
            STRATEGY_FILE.write_text(json.dumps(body, indent=2), encoding="utf-8")
            self._send_json({"success": True, "message": "Strategy saved"})
        except Exception as exc:
            self._send_json({"success": False, "error": str(exc)}, 500)

    def _handle_post_strategy_generate(self) -> None:
        """POST /api/strategy/generate — regenerate strategy.json."""
        result = run_strategy_generate()
        self._send_json(result)

    def _handle_post_finetune(self) -> None:
        """POST /api/finetune — trigger fine-tuning for an adapter."""
        body = self._read_body()
        adapter_id = body.get("adapter_id", "")
        if not adapter_id:
            self._send_json({"error": "adapter_id required"}, 400)
            return
        result = run_claw_command(["finetune", "--adapter", adapter_id], timeout=120)
        self._send_json(result)

    # ----- OPTIONS for CORS -----

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# -------------------------------------------------------------------------
# Threaded Server
# -------------------------------------------------------------------------
class DashboardServer(http.server.ThreadingHTTPServer):
    """Threaded HTTP server for concurrent dashboard requests."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        super().__init__(("0.0.0.0", port), DashboardHandler)


# -------------------------------------------------------------------------
# PID File Management
# -------------------------------------------------------------------------
def _ensure_pid_dir() -> None:
    """Create data/dashboard/ directory if needed."""
    PID_DIR.mkdir(parents=True, exist_ok=True)


def write_pid(pid: int) -> None:
    """Write the server PID to the PID file."""
    _ensure_pid_dir()
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def read_pid() -> Optional[int]:
    """Read the server PID from the PID file."""
    if not PID_FILE.exists():
        return None
    try:
        with open(PID_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError, OSError):
        return None


def remove_pid() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except (IOError, OSError):
        pass


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in proc.stdout
        except (subprocess.TimeoutExpired, IOError, OSError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
        except OSError:
            return False


# -------------------------------------------------------------------------
# Server Lifecycle
# -------------------------------------------------------------------------
def start_server(port: int = DEFAULT_PORT) -> None:
    """Start the dashboard server."""
    # Check for existing instance
    existing_pid = read_pid()
    if existing_pid and is_process_running(existing_pid):
        err(f"Dashboard already running (PID {existing_pid})")
        err(f"Run: python3 shared/claw_dashboard.py --stop")
        sys.exit(1)

    # Clean up stale PID
    if existing_pid:
        remove_pid()

    # Write our PID
    write_pid(os.getpid())

    # Handle graceful shutdown
    def _shutdown(signum: int, frame: Any) -> None:
        log("Shutting down dashboard server...")
        remove_pid()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start server
    DashboardHandler.metrics = MetricsCollector(service="claw-dashboard")
    try:
        server = DashboardServer(port)
    except OSError as e:
        err(f"Cannot bind to port {port}: {e}")
        remove_pid()
        sys.exit(1)

    print(f"\n{BOLD}{CYAN}=== XClaw Enterprise Dashboard ==={NC}\n")
    log(f"Server started on port {port}")
    log(f"Dashboard URL: {BOLD}http://localhost:{port}{NC}")
    log(f"PID file: {PID_FILE}")
    log(f"Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        remove_pid()
        log("Dashboard server stopped.")


def stop_server() -> None:
    """Stop a running dashboard server."""
    pid = read_pid()
    if pid is None:
        err("No PID file found. Dashboard may not be running.")
        return

    if not is_process_running(pid):
        warn(f"Process {pid} not found. Cleaning up PID file.")
        remove_pid()
        return

    log(f"Stopping dashboard server (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, timeout=10,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            # Wait briefly for graceful shutdown
            for _ in range(10):
                time.sleep(0.5)
                if not is_process_running(pid):
                    break
            else:
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError) as e:
        err(f"Could not stop process {pid}: {e}")
    except subprocess.TimeoutExpired:
        err(f"Timeout stopping process {pid}")

    remove_pid()
    log("Dashboard server stopped.")


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------
def _print_usage() -> None:
    """Print CLI usage."""
    print(
        f"Usage: python3 shared/claw_dashboard.py [command]\n"
        f"\n"
        f"Commands:\n"
        f"  --start [--port PORT]   Start the dashboard server (default port: {DEFAULT_PORT})\n"
        f"  --stop                  Stop a running dashboard server\n"
        f"  --status                Check if dashboard is running\n"
    )


def main() -> None:
    args = sys.argv[1:]

    if not args:
        _print_usage()
        sys.exit(1)

    action = args[0]

    if action == "--start":
        port = DEFAULT_PORT
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 < len(args):
                try:
                    port = int(args[idx + 1])
                except ValueError:
                    err(f"Invalid port: {args[idx + 1]}")
                    sys.exit(1)
        start_server(port)

    elif action == "--stop":
        stop_server()

    elif action == "--status":
        pid = read_pid()
        if pid and is_process_running(pid):
            log(f"Dashboard is running (PID {pid})")
            log(f"URL: http://localhost:{DEFAULT_PORT}")
        elif pid:
            warn(f"PID file exists ({pid}) but process is not running.")
            warn("Run --stop to clean up, then --start.")
        else:
            info("Dashboard is not running.")

    else:
        err(f"Unknown command: {action}")
        _print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
