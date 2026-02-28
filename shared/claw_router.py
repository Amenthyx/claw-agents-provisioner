#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Live Model Router
=============================================================================
Transparent OpenAI-compatible proxy that routes requests to the best available
model based on task type detection, strategy.json routing, and automatic
failover between local runtimes and cloud providers.

Endpoints:
  POST /v1/chat/completions    — Main proxy (OpenAI-compatible)
  GET  /v1/models              — List available models from strategy
  GET  /api/router/status      — Router status (uptime, requests, backends)
  GET  /api/router/logs        — Recent request logs
  POST /api/router/reload      — Reload strategy.json
  GET  /health                 — Simple health check

Usage:
  python3 shared/claw_router.py --start --port 9095
  python3 shared/claw_router.py --stop
  python3 shared/claw_router.py --status
  python3 shared/claw_router.py --logs [--tail 20]

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
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
STRATEGY_FILE = PROJECT_ROOT / "strategy.json"
PID_DIR = PROJECT_ROOT / "data" / "router"
PID_FILE = PID_DIR / "router.pid"
USAGE_LOG_DIR = PROJECT_ROOT / "data" / "billing"
USAGE_LOG_FILE = USAGE_LOG_DIR / "usage_log.jsonl"

DEFAULT_PORT = 9095

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
    print(f"{GREEN}[router]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[router]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[router]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[router]{NC} {msg}")


# -------------------------------------------------------------------------
# Local runtime endpoints (mirrors claw_strategy.py)
# -------------------------------------------------------------------------
LOCAL_RUNTIMES = {
    "ollama": {"openai_base": "http://localhost:11434/v1", "port": 11434},
    "vllm": {"openai_base": "http://localhost:8000/v1", "port": 8000},
    "llamacpp": {"openai_base": "http://localhost:8080/v1", "port": 8080},
    "ipexllm": {"openai_base": "http://localhost:8010/v1", "port": 8010},
    "sglang": {"openai_base": "http://localhost:30000/v1", "port": 30000},
    "docker_model_runner": {"openai_base": "http://localhost:12434/v1", "port": 12434},
}

# -------------------------------------------------------------------------
# Cloud provider API bases and env-key mapping
# -------------------------------------------------------------------------
CLOUD_APIS = {
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
}

CLOUD_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}

# -------------------------------------------------------------------------
# Task type detection — keyword sets
# -------------------------------------------------------------------------
TASK_KEYWORDS: Dict[str, List[str]] = {
    "coding": ["code", "debug", "programming", "function", "class", "implement",
               "refactor", "compile", "syntax", "algorithm", "bug", "test"],
    "reasoning": ["reason", "math", "logic", "analyze", "proof", "deduce",
                   "calculate", "theorem", "equation", "infer", "evaluate"],
    "creative": ["write", "creative", "story", "poem", "marketing", "essay",
                  "narrative", "fiction", "blog", "slogan", "tagline"],
    "translation": ["translate", "translation", "language", "localize",
                     "multilingual", "interpret"],
    "summarization": ["summarize", "summary", "extract", "key points",
                       "condense", "brief", "tldr", "digest"],
    "data_analysis": ["data", "csv", "json", "table", "chart", "statistics",
                       "dataset", "parse", "aggregate", "query", "sql"],
}


def detect_task_type(messages: List[Dict]) -> str:
    """Detect task type from system prompt keywords.

    Scans the system message (if present) and falls back to scanning the
    last user message.  Returns a task type key that maps to strategy.json
    task_routing entries.
    """
    text = ""
    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            text += " " + msg.get("content", "")
    # Fallback: also consider the last user message
    for msg in reversed(messages):
        if msg.get("role") == "user":
            text += " " + msg.get("content", "")
            break

    text_lower = text.lower()
    scores: Dict[str, int] = {}

    for task_type, keywords in TASK_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[task_type] = score

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return "simple_chat"


# -------------------------------------------------------------------------
# Strategy loader
# -------------------------------------------------------------------------
class StrategyManager:
    """Loads, caches, and queries strategy.json for routing decisions."""

    def __init__(self) -> None:
        self._strategy: Dict[str, Any] = {}
        self._loaded_at: float = 0.0
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> bool:
        """(Re)load strategy.json from disk.  Returns True on success."""
        with self._lock:
            if not STRATEGY_FILE.exists():
                warn(f"strategy.json not found at {STRATEGY_FILE}")
                self._strategy = {}
                return False
            try:
                with open(STRATEGY_FILE) as f:
                    self._strategy = json.load(f)
                self._loaded_at = time.time()
                log(f"Strategy loaded ({len(self._strategy.get('task_routing', {}))} task routes)")
                return True
            except (json.JSONDecodeError, IOError) as exc:
                err(f"Failed to load strategy.json: {exc}")
                return False

    @property
    def strategy(self) -> Dict[str, Any]:
        return self._strategy

    @property
    def loaded_at(self) -> float:
        return self._loaded_at

    def get_route(self, task_type: str) -> Optional[Dict[str, Any]]:
        """Return the routing entry for *task_type*, or None."""
        with self._lock:
            return self._strategy.get("task_routing", {}).get(task_type)

    def list_models(self) -> List[Dict[str, Any]]:
        """Return the models inventory list from strategy."""
        with self._lock:
            return self._strategy.get("models_inventory", [])


# -------------------------------------------------------------------------
# Health checker for backends
# -------------------------------------------------------------------------
_health_cache: Dict[str, Tuple[bool, float]] = {}
_health_cache_lock = threading.Lock()
HEALTH_CACHE_TTL = 15.0  # seconds


def check_backend_health(base_url: str, timeout: float = 3.0) -> bool:
    """Quick health probe against a backend URL.

    Tries GET /health, then GET /v1/models as a fallback.  Results are
    cached for HEALTH_CACHE_TTL seconds to avoid hammering backends on
    every request.
    """
    now = time.time()
    with _health_cache_lock:
        cached = _health_cache.get(base_url)
        if cached and (now - cached[1]) < HEALTH_CACHE_TTL:
            return cached[0]

    healthy = False
    # Strip trailing /v1 for the health probe
    probe_base = base_url.rstrip("/")
    if probe_base.endswith("/v1"):
        probe_base = probe_base[:-3]

    for path in ["/health", "/v1/models", "/api/tags"]:
        try:
            req = urllib.request.Request(f"{probe_base}{path}", method="GET")
            with urllib.request.urlopen(req, timeout=timeout):
                healthy = True
                break
        except Exception:
            continue

    with _health_cache_lock:
        _health_cache[base_url] = (healthy, now)

    return healthy


def invalidate_health_cache(base_url: Optional[str] = None) -> None:
    """Clear health cache for a specific URL, or all entries."""
    with _health_cache_lock:
        if base_url:
            _health_cache.pop(base_url, None)
        else:
            _health_cache.clear()


# -------------------------------------------------------------------------
# Rate limiter (in-memory, per API key)
# -------------------------------------------------------------------------
class RateLimiter:
    """Simple token-bucket rate limiter keyed by Authorization header."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self._rpm = requests_per_minute
        self._lock = threading.Lock()
        # key -> list of request timestamps
        self._buckets: Dict[str, List[float]] = {}

    def allow(self, key: str) -> bool:
        """Return True if the request is allowed for *key*."""
        now = time.time()
        window = 60.0
        with self._lock:
            timestamps = self._buckets.get(key, [])
            # Evict old entries
            timestamps = [t for t in timestamps if (now - t) < window]
            if len(timestamps) >= self._rpm:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            return True


# -------------------------------------------------------------------------
# Usage logger (append to JSONL)
# -------------------------------------------------------------------------
_log_lock = threading.Lock()
_recent_logs: List[Dict[str, Any]] = []
MAX_RECENT_LOGS = 200


def log_usage(entry: Dict[str, Any]) -> None:
    """Append a usage entry to the JSONL log and in-memory buffer."""
    entry["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # In-memory ring buffer for /api/router/logs
    with _log_lock:
        _recent_logs.append(entry)
        if len(_recent_logs) > MAX_RECENT_LOGS:
            del _recent_logs[: len(_recent_logs) - MAX_RECENT_LOGS]

    # Persist to disk
    try:
        USAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(USAGE_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError:
        pass  # Best-effort logging


def get_recent_logs(tail: int = 20) -> List[Dict[str, Any]]:
    """Return the last *tail* log entries from memory."""
    with _log_lock:
        return list(_recent_logs[-tail:])


# -------------------------------------------------------------------------
# Round-robin load balancer for local runtimes
# -------------------------------------------------------------------------
class LoadBalancer:
    """Simple round-robin across healthy local runtime endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = 0

    def pick(self, endpoints: List[str]) -> Optional[str]:
        """Return the next healthy endpoint, or None if all are down."""
        if not endpoints:
            return None
        with self._lock:
            start = self._index % len(endpoints)
            self._index += 1

        # Try from start, wrapping around
        for i in range(len(endpoints)):
            candidate = endpoints[(start + i) % len(endpoints)]
            if check_backend_health(candidate):
                return candidate
        return None


# -------------------------------------------------------------------------
# Request proxying
# -------------------------------------------------------------------------
def _resolve_openai_base(route_entry: Dict[str, Any]) -> Optional[str]:
    """Determine the OpenAI-compatible base URL for a route entry.

    For local models the base is stored directly.  For cloud models we
    derive it from the provider name.
    """
    if route_entry.get("type") == "local":
        base = route_entry.get("openai_base")
        if base:
            return base
        # Fallback: match provider name to LOCAL_RUNTIMES
        provider_lower = route_entry.get("provider", "").lower()
        for rt_id, rt_cfg in LOCAL_RUNTIMES.items():
            if rt_id in provider_lower or provider_lower in rt_cfg.get("openai_base", ""):
                return rt_cfg["openai_base"]
        return None

    # Cloud
    provider_lower = route_entry.get("provider", "").lower()
    for cloud_id, cloud_base in CLOUD_APIS.items():
        if cloud_id in provider_lower:
            return cloud_base
    return None


def _get_cloud_auth_header(provider: str) -> Optional[str]:
    """Return the Authorization header value for a cloud provider, or None."""
    provider_lower = provider.lower()
    for cloud_id, env_key in CLOUD_ENV_KEYS.items():
        if cloud_id in provider_lower:
            key = os.environ.get(env_key, "")
            if key and not key.endswith("REPLACE_ME"):
                return f"Bearer {key}"
    return None


def proxy_request(
    body: bytes,
    route_entry: Dict[str, Any],
    request_model: Optional[str] = None,
) -> Tuple[int, Dict[str, str], bytes]:
    """Forward *body* to the backend described by *route_entry*.

    Returns (status_code, response_headers_dict, response_body).
    """
    base_url = _resolve_openai_base(route_entry)
    if not base_url:
        return 502, {}, json.dumps({"error": "No backend URL resolved"}).encode()

    # Build target URL
    target = f"{base_url}/chat/completions"
    if not target.startswith("http"):
        target = f"http://{target}"

    # Rewrite the model field in the request body to match the target
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    target_model = route_entry.get("model", payload.get("model", ""))
    if target_model:
        payload["model"] = target_model

    encoded_body = json.dumps(payload).encode("utf-8")

    # Build request
    req = urllib.request.Request(target, data=encoded_body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    # Auth for cloud providers
    if route_entry.get("type") == "cloud":
        auth = _get_cloud_auth_header(route_entry.get("provider", ""))
        if auth:
            req.add_header("Authorization", auth)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_body = resp.read()
            resp_headers = dict(resp.getheaders())
            return resp.status, resp_headers, resp_body
    except urllib.error.HTTPError as exc:
        resp_body = exc.read() if exc.fp else b""
        return exc.code, {}, resp_body
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        error_msg = json.dumps({
            "error": {
                "message": f"Backend unreachable: {exc}",
                "type": "proxy_error",
            }
        }).encode()
        return 502, {}, error_msg


# -------------------------------------------------------------------------
# Router core — picks route + failover
# -------------------------------------------------------------------------
class Router:
    """Central router: task detection -> strategy lookup -> proxy + failover."""

    def __init__(self, strategy_mgr: StrategyManager) -> None:
        self.strategy = strategy_mgr
        self.balancer = LoadBalancer()
        self.rate_limiter = RateLimiter(requests_per_minute=120)
        self._requests_served = 0
        self._requests_failed = 0
        self._start_time = time.time()
        self._lock = threading.Lock()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    @property
    def requests_served(self) -> int:
        with self._lock:
            return self._requests_served

    @property
    def requests_failed(self) -> int:
        with self._lock:
            return self._requests_failed

    def _inc_served(self) -> None:
        with self._lock:
            self._requests_served += 1

    def _inc_failed(self) -> None:
        with self._lock:
            self._requests_failed += 1

    def handle_chat_completions(
        self,
        body: bytes,
        auth_key: str,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """Route a /v1/chat/completions request.

        1. Parse body, detect task type
        2. Look up strategy route
        3. Health-check primary backend
        4. Failover to fallback if primary is down
        5. Proxy and log
        """
        # Rate limit
        if not self.rate_limiter.allow(auth_key or "__anonymous__"):
            self._inc_failed()
            return 429, {}, json.dumps({
                "error": {
                    "message": "Rate limit exceeded. Try again later.",
                    "type": "rate_limit_error",
                }
            }).encode()

        # Parse request
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._inc_failed()
            return 400, {}, json.dumps({
                "error": {"message": "Invalid JSON body", "type": "invalid_request_error"}
            }).encode()

        messages = payload.get("messages", [])
        requested_model = payload.get("model", "")

        # Detect task type
        task_type = detect_task_type(messages)

        # Look up strategy route
        route = self.strategy.get_route(task_type)
        if not route:
            # If no route for detected task, try simple_chat as default
            route = self.strategy.get_route("simple_chat")
        if not route:
            # No strategy loaded at all — try to forward to requested model directly
            self._inc_failed()
            return 503, {}, json.dumps({
                "error": {
                    "message": "No routing strategy loaded. POST /api/router/reload to load strategy.json.",
                    "type": "service_unavailable",
                }
            }).encode()

        primary = route.get("primary", {})
        fallback = route.get("fallback", {})

        # If client specified a model hint, check if it matches a known model
        # and override routing to respect the explicit request.
        chosen_route = primary
        route_label = "primary"

        if requested_model and primary.get("model") != requested_model:
            # Check if fallback matches
            if fallback.get("model") == requested_model:
                chosen_route = fallback
                route_label = "fallback (model hint)"

        # Health check primary
        primary_base = _resolve_openai_base(chosen_route)
        if primary_base and chosen_route.get("type") == "local":
            if not check_backend_health(primary_base):
                # Failover
                alt = fallback if chosen_route is primary else primary
                alt_base = _resolve_openai_base(alt)
                if alt_base and check_backend_health(alt_base):
                    chosen_route = alt
                    route_label = "failover"
                    warn(f"Primary down, failing over to {alt.get('model', '?')}")
                else:
                    # Both down
                    self._inc_failed()
                    log_usage({
                        "task_type": task_type,
                        "model": chosen_route.get("model", "?"),
                        "route": "failed",
                        "status": 502,
                        "error": "All backends unreachable",
                    })
                    return 502, {}, json.dumps({
                        "error": {
                            "message": "All backends are unreachable.",
                            "type": "proxy_error",
                        }
                    }).encode()

        # Proxy the request
        t0 = time.time()
        status, headers, resp_body = proxy_request(body, chosen_route, requested_model)
        elapsed_ms = (time.time() - t0) * 1000

        # If primary proxy failed with a connection/server error, try failover
        if status >= 500 and route_label != "failover":
            alt = fallback if chosen_route is primary else primary
            if alt and alt.get("model"):
                warn(f"Primary returned {status}, trying failover to {alt.get('model', '?')}")
                invalidate_health_cache(primary_base)
                status, headers, resp_body = proxy_request(body, alt, requested_model)
                elapsed_ms = (time.time() - t0) * 1000
                chosen_route = alt
                route_label = "failover"

        if status < 400:
            self._inc_served()
        else:
            self._inc_failed()

        # Log usage
        log_usage({
            "task_type": task_type,
            "model": chosen_route.get("model", "?"),
            "provider": chosen_route.get("provider", "?"),
            "route": route_label,
            "status": status,
            "latency_ms": round(elapsed_ms, 1),
            "input_messages": len(messages),
        })

        return status, headers, resp_body


# -------------------------------------------------------------------------
# HTTP Request Handler
# -------------------------------------------------------------------------
class RouterRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the router server."""

    # Class-level references set by the server
    router: Optional[Router] = None
    strategy_mgr: Optional[StrategyManager] = None

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

    def _send_raw(self, status: int, headers: Dict[str, str], body: bytes) -> None:
        """Send a raw proxied response."""
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        # Forward content-type from upstream
        ct = headers.get("Content-Type", headers.get("content-type", "application/json"))
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """Read the full request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length)
        return b""

    def _get_auth_key(self) -> str:
        """Extract bearer token or use client IP as key."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return self.client_address[0]

    # --- CORS preflight ---
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # --- GET routes ---
    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            self._handle_health()
        elif path == "/v1/models":
            self._handle_list_models()
        elif path == "/api/router/status":
            self._handle_status()
        elif path == "/api/router/logs":
            self._handle_logs()
        else:
            self._send_json(404, {"error": "Not found"})

    # --- POST routes ---
    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/v1/chat/completions":
            self._handle_chat_completions()
        elif path == "/api/router/reload":
            self._handle_reload()
        else:
            self._send_json(404, {"error": "Not found"})

    # --- Endpoint handlers ---

    def _handle_health(self) -> None:
        self._send_json(200, {
            "status": "ok",
            "service": "claw-router",
            "version": "1.0.0",
        })

    def _handle_list_models(self) -> None:
        if not self.strategy_mgr:
            self._send_json(503, {"error": "Strategy not loaded"})
            return

        models = self.strategy_mgr.list_models()
        # Format as OpenAI-compatible /v1/models response
        data = []
        for m in models:
            data.append({
                "id": m.get("id", "unknown"),
                "object": "model",
                "created": int(self.strategy_mgr.loaded_at),
                "owned_by": m.get("provider", "unknown"),
            })

        self._send_json(200, {
            "object": "list",
            "data": data,
        })

    def _handle_status(self) -> None:
        if not self.router:
            self._send_json(503, {"error": "Router not initialized"})
            return

        uptime = self.router.uptime_seconds
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        # Gather backend statuses
        backends = []
        for rt_id, rt_cfg in LOCAL_RUNTIMES.items():
            base = rt_cfg["openai_base"]
            healthy = check_backend_health(base, timeout=2.0)
            backends.append({
                "runtime": rt_id,
                "base_url": base,
                "healthy": healthy,
            })

        strategy_info = {}
        if self.strategy_mgr and self.strategy_mgr.strategy:
            s = self.strategy_mgr.strategy
            strategy_info = {
                "loaded": True,
                "version": s.get("version", "?"),
                "generated_at": s.get("generated_at", "?"),
                "total_models": s.get("total_models", 0),
                "task_routes": len(s.get("task_routing", {})),
            }
        else:
            strategy_info = {"loaded": False}

        self._send_json(200, {
            "status": "running",
            "uptime": f"{hours}h {minutes}m {seconds}s",
            "uptime_seconds": round(uptime, 1),
            "requests_served": self.router.requests_served,
            "requests_failed": self.router.requests_failed,
            "strategy": strategy_info,
            "backends": backends,
        })

    def _handle_logs(self) -> None:
        # Parse ?tail=N from query string
        tail = 20
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for param in qs.split("&"):
                if param.startswith("tail="):
                    try:
                        tail = int(param.split("=", 1)[1])
                    except ValueError:
                        pass

        logs = get_recent_logs(tail)
        self._send_json(200, {
            "count": len(logs),
            "logs": logs,
        })

    def _handle_reload(self) -> None:
        if not self.strategy_mgr:
            self._send_json(503, {"error": "Strategy manager not initialized"})
            return

        invalidate_health_cache()
        success = self.strategy_mgr.reload()
        if success:
            self._send_json(200, {
                "status": "reloaded",
                "task_routes": len(self.strategy_mgr.strategy.get("task_routing", {})),
                "total_models": self.strategy_mgr.strategy.get("total_models", 0),
            })
        else:
            self._send_json(500, {
                "status": "failed",
                "error": "Could not reload strategy.json",
            })

    def _handle_chat_completions(self) -> None:
        if not self.router:
            self._send_json(503, {
                "error": {
                    "message": "Router not initialized",
                    "type": "service_unavailable",
                }
            })
            return

        body = self._read_body()
        auth_key = self._get_auth_key()

        status, headers, resp_body = self.router.handle_chat_completions(body, auth_key)
        self._send_raw(status, headers, resp_body)


# -------------------------------------------------------------------------
# Threaded HTTP server
# -------------------------------------------------------------------------
class ThreadedRouterServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for concurrent request handling."""
    allow_reuse_address = True
    daemon_threads = True


# -------------------------------------------------------------------------
# Server lifecycle
# -------------------------------------------------------------------------
def _ensure_dirs() -> None:
    """Create required data directories."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    USAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)


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


def start_server(port: int = DEFAULT_PORT) -> None:
    """Start the router server in the foreground."""
    _ensure_dirs()

    # Check for existing instance
    existing_pid = _read_pid()
    if existing_pid and _is_process_alive(existing_pid):
        err(f"Router already running (PID {existing_pid}). Use --stop first.")
        sys.exit(1)

    if _is_port_in_use(port):
        err(f"Port {port} is already in use.")
        sys.exit(1)

    # Load strategy
    strategy_mgr = StrategyManager()
    router = Router(strategy_mgr)

    # Attach to handler class
    RouterRequestHandler.router = router
    RouterRequestHandler.strategy_mgr = strategy_mgr

    # Create server
    server = ThreadedRouterServer(("0.0.0.0", port), RouterRequestHandler)

    # Write PID
    _write_pid(os.getpid())

    # Graceful shutdown on signals
    def shutdown_handler(signum: int, frame: Any) -> None:
        log("Shutting down...")
        _remove_pid()
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print()
    print(f"  {BOLD}{CYAN}=== CLAW Live Model Router ==={NC}")
    print()
    print(f"  {BOLD}Listening:{NC}  http://0.0.0.0:{port}")
    print(f"  {BOLD}PID:{NC}        {os.getpid()}")
    print(f"  {BOLD}Strategy:{NC}   {'loaded' if strategy_mgr.strategy else 'not found'}")
    print(f"  {BOLD}Log file:{NC}   {USAGE_LOG_FILE}")
    print()
    print(f"  {DIM}Endpoints:{NC}")
    print(f"    POST /v1/chat/completions    {DIM}— OpenAI-compatible proxy{NC}")
    print(f"    GET  /v1/models              {DIM}— list available models{NC}")
    print(f"    GET  /api/router/status      {DIM}— router status & metrics{NC}")
    print(f"    GET  /api/router/logs        {DIM}— recent request logs{NC}")
    print(f"    POST /api/router/reload      {DIM}— reload strategy.json{NC}")
    print(f"    GET  /health                 {DIM}— health check{NC}")
    print()
    log(f"Router started on port {port}. Press Ctrl+C to stop.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _remove_pid()
        log("Router stopped.")


def stop_server() -> None:
    """Stop a running router server via its PID file."""
    pid = _read_pid()
    if not pid:
        info("No PID file found. Router may not be running.")
        return

    if not _is_process_alive(pid):
        info(f"Process {pid} is not running. Cleaning up stale PID file.")
        _remove_pid()
        return

    log(f"Stopping router (PID {pid})...")
    try:
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
    log("Router stopped.")


def show_status() -> None:
    """Print the current router status."""
    pid = _read_pid()

    print()
    print(f"  {BOLD}{CYAN}=== CLAW Router Status ==={NC}")
    print()

    if pid and _is_process_alive(pid):
        print(f"  {BOLD}Status:{NC}  {GREEN}RUNNING{NC}")
        print(f"  {BOLD}PID:{NC}     {pid}")
    elif pid:
        print(f"  {BOLD}Status:{NC}  {YELLOW}STALE PID{NC} (process {pid} not found)")
        _remove_pid()
    else:
        print(f"  {BOLD}Status:{NC}  {RED}STOPPED{NC}")
        print()
        return

    # Try to reach the status endpoint
    try:
        req = urllib.request.Request(
            f"http://localhost:{DEFAULT_PORT}/api/router/status",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"  {BOLD}Uptime:{NC}  {data.get('uptime', '?')}")
            print(f"  {BOLD}Served:{NC}  {data.get('requests_served', 0)}")
            print(f"  {BOLD}Failed:{NC}  {data.get('requests_failed', 0)}")

            strat = data.get("strategy", {})
            if strat.get("loaded"):
                print(f"  {BOLD}Strategy:{NC} v{strat.get('version', '?')} — "
                      f"{strat.get('total_models', 0)} models, "
                      f"{strat.get('task_routes', 0)} routes")
            else:
                print(f"  {BOLD}Strategy:{NC} {YELLOW}not loaded{NC}")

            backends = data.get("backends", [])
            if backends:
                print()
                print(f"  {BOLD}Backends:{NC}")
                for b in backends:
                    status_str = f"{GREEN}healthy{NC}" if b["healthy"] else f"{RED}down{NC}"
                    print(f"    {b['runtime']:.<22} {status_str}  ({b['base_url']})")
    except Exception:
        print(f"  {YELLOW}Could not reach router at localhost:{DEFAULT_PORT}{NC}")

    print()


def show_logs(tail: int = 20) -> None:
    """Print recent request logs."""
    print()
    print(f"  {BOLD}{CYAN}=== CLAW Router — Recent Logs ==={NC}")
    print()

    # Try the live endpoint first
    pid = _read_pid()
    if pid and _is_process_alive(pid):
        try:
            req = urllib.request.Request(
                f"http://localhost:{DEFAULT_PORT}/api/router/logs?tail={tail}",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                logs = data.get("logs", [])
                if logs:
                    for entry in logs:
                        ts = entry.get("timestamp", "?")
                        task = entry.get("task_type", "?")
                        model = entry.get("model", "?")
                        route = entry.get("route", "?")
                        status = entry.get("status", "?")
                        latency = entry.get("latency_ms", "?")
                        print(f"  {DIM}{ts}{NC}  {task:<16} {model:<25} "
                              f"route={route:<12} status={status}  {latency}ms")
                else:
                    info("No logs yet.")
                print()
                return
        except Exception:
            pass

    # Fallback: read from file
    if not USAGE_LOG_FILE.exists():
        info("No log file found.")
        print()
        return

    try:
        with open(USAGE_LOG_FILE) as f:
            lines = f.readlines()

        recent = lines[-tail:] if len(lines) > tail else lines
        for line in recent:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", "?")
                task = entry.get("task_type", "?")
                model = entry.get("model", "?")
                route = entry.get("route", "?")
                status = entry.get("status", "?")
                latency = entry.get("latency_ms", "?")
                print(f"  {DIM}{ts}{NC}  {task:<16} {model:<25} "
                      f"route={route:<12} status={status}  {latency}ms")
            except json.JSONDecodeError:
                continue
    except IOError:
        err("Could not read log file.")

    print()


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 shared/claw_router.py [--start|--stop|--status|--logs]")
        print()
        print("Commands:")
        print("  --start [--port 9095]   Start the model router server")
        print("  --stop                  Stop a running router server")
        print("  --status                Show router status and backends")
        print("  --logs [--tail 20]      Show recent request logs")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--start":
        port = DEFAULT_PORT
        if "--port" in sys.argv:
            try:
                idx = sys.argv.index("--port")
                port = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                err("Invalid --port value. Using default 9095.")
        start_server(port)

    elif action == "--stop":
        stop_server()

    elif action == "--status":
        show_status()

    elif action == "--logs":
        tail = 20
        if "--tail" in sys.argv:
            try:
                idx = sys.argv.index("--tail")
                tail = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                pass
        show_logs(tail)

    else:
        err(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
