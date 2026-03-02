#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Wizard API (React Frontend Backend)
=============================================================================
Lightweight HTTP API that wraps existing CLI commands for the React
installation wizard UI.  Provides JSON endpoints for platform selection,
hardware detection, model/runtime recommendation, adapter listing,
assessment validation, and SSE-streamed deployment.

Can run standalone or be imported by claw_dashboard.py to serve alongside
the monitoring dashboard on the same server.

Endpoints:
  GET  /api/wizard/platforms       -- list 5 platforms with metadata
  GET  /api/wizard/hardware        -- run hardware detection, return JSON
  GET  /api/wizard/models          -- VRAM-filtered model list
  GET  /api/wizard/runtimes        -- available LLM runtimes with status
  GET  /api/wizard/adapters        -- list adapters with brief metadata
  POST /api/wizard/validate        -- validate assessment JSON against schema
  POST /api/wizard/deploy          -- run claw.sh deploy (SSE progress stream)
  GET  /api/wizard/status          -- current deployment status
  GET  /api/wizard/security-rules  -- list security rule categories

Usage:
  python3 shared/claw_wizard_api.py --start --port 9098
  python3 shared/claw_wizard_api.py --stop

Requirements:
  Python 3.8+  (stdlib only -- no pip installs)
=============================================================================
Created by Mauro Tommasi -- linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import argparse
import collections
import hashlib
import json
import os
import re
import signal
import smtplib
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional

# -------------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
HARDWARE_PROFILE_FILE = PROJECT_ROOT / "hardware_profile.json"
SECURITY_RULES_FILE = SCRIPT_DIR / "security_rules.json"
SKILLS_CATALOG_FILE = SCRIPT_DIR / "skills-catalog.json"
CLAW_SH = PROJECT_ROOT / "claw.sh"
PID_DIR = PROJECT_ROOT / "data" / "wizard"
PID_FILE = PID_DIR / "wizard_api.pid"
STRATEGY_FILE = PROJECT_ROOT / "strategy.json"
ENV_TEMPLATE = PROJECT_ROOT / ".env.template"
BILLING_DIR = PROJECT_ROOT / "data" / "billing"
TRIGGERS_FILE = SCRIPT_DIR / "triggers.json"
INSTANCES_FILE = SCRIPT_DIR / "instances.json"
CHANNEL_CONFIG_FILE = SCRIPT_DIR / "channel_config.json"
CLAWS_DIR = PROJECT_ROOT / "data" / "claws"
STORAGE_CONFIG_FILE = PROJECT_ROOT / "data" / "wizard" / "storage_config.json"

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

# -------------------------------------------------------------------------
# Platform metadata
# -------------------------------------------------------------------------
PLATFORMS: List[Dict[str, Any]] = [
    {
        "id": "zeroclaw", "name": "ZeroClaw", "language": "Rust",
        "memory": "512 MB", "port": 3100,
        "description": "High-performance minimal agent", "icon": "bolt",
        "features": ["Minimal footprint", "Rust performance", "512 MB limit"],
    },
    {
        "id": "nanoclaw", "name": "NanoClaw", "language": "TypeScript",
        "memory": "1 GB", "port": 3200,
        "description": "Claude-native with Docker-out-of-Docker", "icon": "code",
        "features": ["Claude-native", "TypeScript", "Docker-in-Docker"],
    },
    {
        "id": "picoclaw", "name": "PicoClaw", "language": "Go",
        "memory": "128 MB", "port": 3300,
        "description": "Ultra-lightweight data agent", "icon": "feather",
        "features": ["8 MB RAM capable", "Go performance", "Data processing"],
    },
    {
        "id": "openclaw", "name": "OpenClaw", "language": "Node.js",
        "memory": "4 GB", "port": 3400,
        "description": "50+ integrations, maximum extensibility", "icon": "puzzle",
        "features": ["50+ integrations", "Plugin system", "Maximum extensibility"],
    },
    {
        "id": "parlant", "name": "Parlant", "language": "Python",
        "memory": "2 GB", "port": 8800,
        "description": "Guidelines-driven with MCP support", "icon": "message",
        "features": ["Guidelines engine", "MCP protocol", "Conversational AI"],
    },
]

# -------------------------------------------------------------------------
# Deployment state (shared across threads)
# -------------------------------------------------------------------------
_deploy_lock = threading.Lock()
_deploy_status: Dict[str, Any] = {"state": "idle", "progress": 0, "message": ""}


def log(msg: str) -> None:
    print(f"{GREEN}[wizard-api]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[wizard-api]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[wizard-api]{NC} {msg}", file=sys.stderr)


# =========================================================================
#  Helper: hardware detection (imports claw_hardware if available)
# =========================================================================
def _detect_hardware() -> Dict[str, Any]:
    """Detect hardware via claw_hardware module or fallback to cached file."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from claw_hardware import HardwareDetector, RuntimeRecommender
        detector = HardwareDetector()
        profile = detector.detect_all()
        recommender = RuntimeRecommender(profile)
        recommendation = recommender.recommend()
        model_rec = recommender.recommend_models()
        return {
            "hardware": profile,
            "recommendation": recommendation,
            "models": model_rec,
        }
    except ImportError:
        warn("claw_hardware not importable, falling back to cached profile")
    except (RuntimeError, OSError, ValueError) as exc:
        warn(f"Hardware detection error: {exc}")

    # Fallback: read cached hardware_profile.json
    if HARDWARE_PROFILE_FILE.exists():
        try:
            with open(HARDWARE_PROFILE_FILE, "r") as fh:
                profile = json.load(fh)
            return {"hardware": profile, "recommendation": None, "models": None}
        except json.JSONDecodeError:
            pass

    return {"hardware": None, "recommendation": None, "models": None}


def _get_models(hardware_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Return VRAM-filtered model list from hardware profile."""
    if hardware_data is None:
        hardware_data = _detect_hardware()
    models = hardware_data.get("models")
    if models:
        return models
    # Minimal fallback when no hardware detected
    return {
        "recommended": [],
        "max_vram_gb": 0,
        "note": "Hardware detection unavailable -- run with --detect first",
    }


def _get_runtimes() -> List[Dict[str, Any]]:
    """List available LLM runtimes with installed/running status."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from claw_hardware import RuntimeRecommender
        runtimes_meta = RuntimeRecommender.RUNTIMES
    except (ImportError, AttributeError):
        runtimes_meta = {}

    results = []
    for rid, meta in runtimes_meta.items():
        entry = {
            "id": rid,
            "name": meta.get("name", rid),
            "port": meta.get("port"),
            "requires_gpu": meta.get("requires_gpu", False),
            "supported_apis": meta.get("supported_apis", []),
            "description": meta.get("description", ""),
            "installed": False,
            "running": False,
        }
        # Quick check: is the runtime process listening?
        port = meta.get("port")
        if port:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            try:
                sock.connect(("127.0.0.1", port))
                entry["running"] = True
                entry["installed"] = True
            except (ConnectionRefusedError, OSError):
                pass
            finally:
                sock.close()
        results.append(entry)
    return results


def _get_adapters() -> List[Dict[str, Any]]:
    """Load adapter/skill list from skills-catalog.json."""
    if SKILLS_CATALOG_FILE.exists():
        try:
            with open(SKILLS_CATALOG_FILE, "r") as fh:
                catalog = json.load(fh)
            return catalog.get("skills", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def _get_security_rule_categories() -> List[Dict[str, str]]:
    """Extract security rule category names and descriptions."""
    if SECURITY_RULES_FILE.exists():
        try:
            with open(SECURITY_RULES_FILE, "r") as fh:
                rules = json.load(fh)
            categories = []
            skip_keys = {"_comment", "_version", "_generated_at"}
            for key, val in rules.items():
                if key in skip_keys or not isinstance(val, dict):
                    continue
                categories.append({
                    "id": key,
                    "comment": val.get("_comment", ""),
                    "enabled": val.get("enabled", True),
                })
            return categories
        except (json.JSONDecodeError, KeyError):
            pass
    return []


CUSTOM_SECURITY_RULES_FILE = PID_DIR / "custom_security_rules.json"
COMPLIANCE_CONFIG_FILE = PID_DIR / "compliance_config.json"


def _get_security_rules_detail() -> Dict[str, Any]:
    """Return the full security_rules.json content for the wizard detail panels."""
    if SECURITY_RULES_FILE.exists():
        try:
            with open(SECURITY_RULES_FILE, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, KeyError):
            pass
    return {"error": "security_rules.json not found"}


def _save_security_rules(body: Dict[str, Any]) -> Dict[str, Any]:
    """Save custom security rule overrides to a JSON file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CUSTOM_SECURITY_RULES_FILE.write_text(json.dumps(body, indent=2), encoding="utf-8")
        log(f"Custom security rules saved to {CUSTOM_SECURITY_RULES_FILE}")
        return {"success": True, "path": str(CUSTOM_SECURITY_RULES_FILE)}
    except (OSError, TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


def _save_compliance(body: Dict[str, Any]) -> Dict[str, Any]:
    """Save compliance configuration to a JSON file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    try:
        COMPLIANCE_CONFIG_FILE.write_text(json.dumps(body, indent=2), encoding="utf-8")
        log(f"Compliance config saved to {COMPLIANCE_CONFIG_FILE}")
        return {"success": True, "path": str(COMPLIANCE_CONFIG_FILE)}
    except (OSError, TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


def _test_channel(channel_id: str, config: Dict[str, str]) -> Dict[str, Any]:
    """Test a communication channel connection with real API validation."""
    import socket
    import ssl
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError

    def _https_get(host: str, path: str, headers: Optional[Dict[str, str]] = None, timeout: int = 8) -> tuple:
        """Make an HTTPS GET request. Returns (status_code, body_text)."""
        url = f"https://{host}{path}"
        req = Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        ctx = ssl.create_default_context()
        resp = urlopen(req, timeout=timeout, context=ctx)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body

    if channel_id == "telegram":
        token = config.get("botToken", "")
        if not token:
            return {"success": False, "message": "Bot token is required"}
        try:
            status, body = _https_get("api.telegram.org", f"/bot{token}/getMe")
            data = json.loads(body)
            if data.get("ok"):
                bot_name = data.get("result", {}).get("username", "unknown")
                return {"success": True, "message": f"Connected to bot @{bot_name}"}
            return {"success": False, "message": f"Telegram rejected token: {data.get('description', 'unknown error')}"}
        except HTTPError as exc:
            if exc.code == 401:
                return {"success": False, "message": "Invalid bot token (401 Unauthorized)"}
            return {"success": False, "message": f"Telegram API error: HTTP {exc.code}"}
        except (URLError, OSError) as exc:
            return {"success": False, "message": f"Cannot reach Telegram API: {exc}"}

    elif channel_id == "slack":
        webhook_url = config.get("webhookUrl", "")
        bot_token = config.get("botToken", "")
        if not webhook_url and not bot_token:
            return {"success": False, "message": "Webhook URL or Bot Token is required"}
        # Prefer bot token auth test
        if bot_token:
            try:
                status, body = _https_get("slack.com", "/api/auth.test",
                                          headers={"Authorization": f"Bearer {bot_token}"})
                data = json.loads(body)
                if data.get("ok"):
                    team = data.get("team", "unknown")
                    return {"success": True, "message": f"Connected to Slack workspace: {team}"}
                return {"success": False, "message": f"Slack auth failed: {data.get('error', 'unknown')}"}
            except (URLError, OSError) as exc:
                return {"success": False, "message": f"Cannot reach Slack API: {exc}"}
        # Webhook URL test — send empty payload to check URL validity
        if webhook_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(webhook_url)
                if not parsed.hostname or "slack.com" not in parsed.hostname:
                    return {"success": False, "message": "Webhook URL doesn't look like a Slack webhook"}
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((parsed.hostname, 443))
                sock.close()
                return {"success": True, "message": "Slack webhook endpoint is reachable"}
            except (socket.timeout, OSError) as exc:
                return {"success": False, "message": f"Cannot reach Slack webhook: {exc}"}
        return {"success": False, "message": "No valid Slack credentials provided"}

    elif channel_id == "discord":
        token = config.get("botToken", "")
        if not token:
            return {"success": False, "message": "Bot token is required"}
        try:
            status, body = _https_get("discord.com", "/api/v10/users/@me",
                                      headers={"Authorization": f"Bot {token}"})
            data = json.loads(body)
            if "username" in data:
                return {"success": True, "message": f"Connected to Discord bot: {data['username']}"}
            if data.get("code") == 0 or "401" in str(data.get("message", "")):
                return {"success": False, "message": "Invalid bot token (401 Unauthorized)"}
            return {"success": False, "message": f"Discord API error: {data.get('message', 'unknown')}"}
        except HTTPError as exc:
            if exc.code == 401:
                return {"success": False, "message": "Invalid bot token (401 Unauthorized)"}
            return {"success": False, "message": f"Discord API error: HTTP {exc.code}"}
        except (URLError, OSError) as exc:
            return {"success": False, "message": f"Cannot reach Discord API: {exc}"}

    elif channel_id == "email":
        host = config.get("host", "")
        port_str = config.get("port", "587")
        if not host:
            return {"success": False, "message": "SMTP host is required"}
        try:
            import smtplib
            port = int(port_str)
            use_tls = config.get("tls", "true").lower() in ("true", "1", "yes")
            if port == 465:
                smtp = smtplib.SMTP_SSL(host, port, timeout=8)
            else:
                smtp = smtplib.SMTP(host, port, timeout=8)
                if use_tls:
                    smtp.starttls()
            username = config.get("username", "")
            password = config.get("password", "")
            if username and password:
                smtp.login(username, password)
                smtp.quit()
                return {"success": True, "message": f"SMTP login successful on {host}:{port}"}
            smtp.quit()
            return {"success": True, "message": f"SMTP server {host}:{port} is reachable (no auth tested)"}
        except smtplib.SMTPAuthenticationError:
            return {"success": False, "message": "SMTP authentication failed — check username/password"}
        except (socket.timeout, OSError, ValueError) as exc:
            return {"success": False, "message": f"Cannot reach SMTP server: {exc}"}

    elif channel_id == "whatsapp":
        phone_id = config.get("phoneNumberId", "")
        access_token = config.get("accessToken", "")
        if not phone_id or not access_token:
            return {"success": False, "message": "Phone Number ID and Access Token are required"}
        try:
            status, body = _https_get("graph.facebook.com", f"/v18.0/{phone_id}",
                                      headers={"Authorization": f"Bearer {access_token}"})
            data = json.loads(body)
            if data.get("id"):
                display = data.get("display_phone_number", phone_id)
                return {"success": True, "message": f"Connected to WhatsApp: {display}"}
            return {"success": False, "message": f"WhatsApp API error: {data.get('error', {}).get('message', 'unknown')}"}
        except HTTPError as exc:
            if exc.code == 401 or exc.code == 190:
                return {"success": False, "message": "Invalid access token"}
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
                err_data = json.loads(err_body)
                err_msg = err_data.get("error", {}).get("message", f"HTTP {exc.code}")
            except (json.JSONDecodeError, KeyError, ValueError):
                err_msg = f"HTTP {exc.code}"
            return {"success": False, "message": f"WhatsApp API error: {err_msg}"}
        except (URLError, OSError) as exc:
            return {"success": False, "message": f"Cannot reach WhatsApp API: {exc}"}

    elif channel_id == "webhook":
        url = config.get("url", "")
        if not url:
            return {"success": False, "message": "Webhook URL is required"}
        if not url.startswith(("http://", "https://")):
            return {"success": False, "message": "URL must start with http:// or https://"}
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.hostname:
                return {"success": False, "message": "Invalid URL — no hostname found"}
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((parsed.hostname, port))
            sock.close()
            return {"success": True, "message": f"Webhook endpoint {parsed.hostname}:{port} is reachable"}
        except (socket.timeout, OSError) as exc:
            return {"success": False, "message": f"Cannot reach webhook endpoint: {exc}"}

    return {"success": False, "message": f"Unknown channel type: {channel_id}"}


# =========================================================================
#  Dashboard Helpers
# =========================================================================

# ── In-memory log ring buffer ───────────────────────────────────────────
_log_buffer: collections.deque = collections.deque(maxlen=500)
_log_buffer_lock = threading.Lock()

_original_log = None  # set in main()


def _append_log(level: str, message: str, source: str = "system") -> None:
    """Append a log entry to the in-memory ring buffer."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "level": level,
        "message": message,
        "source": source,
    }
    with _log_buffer_lock:
        _log_buffer.append(entry)


def _check_agent_health(port: int, host: str = "127.0.0.1") -> Dict[str, Any]:
    """HTTP GET to :port/health with 2s timeout."""
    try:
        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=2)
        data = json.loads(resp.read().decode())
        return {"reachable": True, "status": "running", "data": data}
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        pass
    # Fallback: TCP check
    import socket as _sock
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((host, port))
        return {"reachable": True, "status": "running", "data": None}
    except (ConnectionRefusedError, OSError):
        return {"reachable": False, "status": "stopped", "data": None}
    finally:
        s.close()


def _get_all_agents_status(host: str = "127.0.0.1") -> List[Dict[str, Any]]:
    """Multi-threaded health check for hardcoded platforms AND deployed xclaws.

    Combines:
      1. The 5 default PLATFORMS (docker-compose based) with health check
      2. All deployed claw configs from data/claws/ — checks Docker or TCP
    Deduplicates by (platform_id + port) so a deployed claw on its default
    port doesn't appear twice.
    """
    results = []
    seen_keys: set = set()  # (id, port) for dedup

    # --- 1. Check hardcoded platforms (docker-compose agents) ----------------
    def _check_platform(plat: Dict[str, Any]) -> Dict[str, Any]:
        health = _check_agent_health(plat["port"], host)
        return {
            "id": plat["id"],
            "name": plat["name"],
            "status": health["status"],
            "port": plat["port"],
            "language": plat["language"],
            "memory": plat["memory"],
            "features": plat.get("features", []),
            "description": plat.get("description", ""),
            "source": "platform",
        }

    # --- 2. Check deployed claws from saved configs --------------------------
    def _check_claw(claw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        container_name = claw.get("container_name", "")
        agent_port = claw.get("agent_port", 0)
        claw_status = claw.get("status", "unknown")

        # Determine liveness
        is_alive = False
        detected_status = "stopped"

        if container_name:
            # Docker-based: inspect container state
            try:
                rc, out, _ = _run_cmd(
                    ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                    timeout=5,
                )
                if rc == 0:
                    state = out.strip()
                    if state == "running":
                        is_alive = True
                        detected_status = "running"
                    elif state in ("paused", "restarting"):
                        detected_status = state
                    else:
                        detected_status = "stopped"
                else:
                    detected_status = "removed"
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                detected_status = "stopped"

        # Fallback / non-docker: TCP port probe
        if not is_alive and agent_port:
            if _check_port(agent_port, host):
                is_alive = True
                detected_status = "running"

        # Update saved config if status changed
        if detected_status != claw_status:
            claw["status"] = detected_status
            claw_id = claw.get("id", "")
            if claw_id:
                config_path = CLAWS_DIR / f"{claw_id}.json"
                if config_path.exists():
                    try:
                        config_path.write_text(json.dumps(claw, indent=2), encoding="utf-8")
                    except OSError:
                        pass

        platform_id = claw.get("platform", "xclaw")
        plat_meta = {p["id"]: p for p in PLATFORMS}.get(platform_id, {})

        return {
            "id": claw.get("id", f"claw_{agent_port}"),
            "name": claw.get("name", container_name or f"xclaw-{agent_port}"),
            "status": detected_status,
            "port": agent_port,
            "language": plat_meta.get("language", ""),
            "memory": plat_meta.get("memory", ""),
            "features": plat_meta.get("features", []),
            "description": plat_meta.get("description", ""),
            "source": "deployed",
            "container_name": container_name,
            "container_id": claw.get("container_id", ""),
            "platform": platform_id,
            "gateway_port": claw.get("gateway_port"),
            "optimizer_port": claw.get("optimizer_port"),
            "watchdog_port": claw.get("watchdog_port"),
        }

    # --- Execute checks in parallel ------------------------------------------
    claws = _load_claws()
    # Filter to actual claw configs (not port files — they lack "name" key)
    claw_configs = [c for c in claws if "name" in c and "agent_port" in c]

    max_workers = max(5, len(claw_configs) + len(PLATFORMS))
    with ThreadPoolExecutor(max_workers=min(max_workers, 20)) as pool:
        # Submit platform checks
        plat_futures = {pool.submit(_check_platform, p): p for p in PLATFORMS}
        # Submit claw checks
        claw_futures = {pool.submit(_check_claw, c): c for c in claw_configs}

        # Collect platform results first
        for f in as_completed(plat_futures):
            try:
                result = f.result()
                key = (result["id"], result["port"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append(result)
            except Exception:  # Broad catch: futures re-raise arbitrary exceptions from workers
                p = plat_futures[f]
                key = (p["id"], p["port"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append({
                        "id": p["id"], "name": p["name"], "status": "error",
                        "port": p["port"], "language": p["language"],
                        "memory": p["memory"], "features": p.get("features", []),
                        "source": "platform",
                    })

        # Collect deployed claw results — deduplicate against platforms
        for f in as_completed(claw_futures):
            try:
                result = f.result()
                if result is None:
                    continue
                # Dedup: if a claw matches an existing platform on the same port, merge
                key = (result.get("platform", result["id"]), result["port"])
                if key in seen_keys:
                    # Update the existing platform entry if the claw is more authoritative
                    for existing in results:
                        if (existing["id"], existing["port"]) == key:
                            if result["status"] == "running" and existing["status"] != "running":
                                existing["status"] = result["status"]
                            existing.setdefault("container_name", result.get("container_name"))
                            existing.setdefault("container_id", result.get("container_id"))
                            break
                    continue
                seen_keys.add(key)
                results.append(result)
            except Exception:  # Broad catch: futures re-raise arbitrary exceptions from workers
                pass

    results.sort(key=lambda x: x.get("port", 0))
    return results


def _read_json_file(path: Path) -> Optional[Dict]:
    """Safe JSON file reader."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _read_env_redacted() -> Dict[str, str]:
    """Read .env.template, redact secrets."""
    config = {}
    target = PROJECT_ROOT / ".env"
    if not target.exists():
        target = ENV_TEMPLATE
    if not target.exists():
        return config
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if re.search(r"key|token|secret|password|api_key", key, re.IGNORECASE) and val:
                    config[key] = val[:4] + "***" + val[-2:] if len(val) > 6 else "***"
                else:
                    config[key] = val
    except OSError:
        pass
    return config


def _read_billing_data() -> Dict[str, Any]:
    """Read billing reports from data/billing/.

    Tries DAL first (cached 60s), falls back to JSONL files.
    """
    # Try DAL for fast aggregation
    try:
        from claw_dal import DAL
        dal = DAL.get_instance()
        agg = dal.costs.aggregate()
        reports = []
        BILLING_DIR.mkdir(parents=True, exist_ok=True)
        reports_dir = BILLING_DIR / "reports"
        if reports_dir.exists():
            for f in sorted(reports_dir.glob("*.json")):
                try:
                    reports.append(json.loads(f.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass
        return {
            "reports": reports,
            "total_cost": round(agg.get("total_cost", 0), 4),
            "total_requests": agg.get("total_requests", 0),
            "currency": "USD",
        }
    except (ImportError, RuntimeError, OSError, KeyError):
        pass

    # Fallback: read from JSONL files
    reports = []
    BILLING_DIR.mkdir(parents=True, exist_ok=True)
    reports_dir = BILLING_DIR / "reports"
    if reports_dir.exists():
        for f in sorted(reports_dir.glob("*.json")):
            try:
                reports.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
    cost_log = BILLING_DIR / "cost_log.jsonl"
    total_cost = 0.0
    total_requests = 0
    if cost_log.exists():
        try:
            for line in cost_log.read_text(encoding="utf-8").splitlines()[-100:]:
                try:
                    entry = json.loads(line)
                    total_cost += entry.get("cost", 0.0)
                    total_requests += 1
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass
    return {
        "reports": reports,
        "total_cost": round(total_cost, 4),
        "total_requests": total_requests,
        "currency": "USD",
    }


# ── Trigger System ──────────────────────────────────────────────────────
_triggers_lock = threading.Lock()


def _load_triggers() -> Dict[str, Any]:
    """Load triggers from triggers.json."""
    with _triggers_lock:
        data = _read_json_file(TRIGGERS_FILE)
    if data:
        return data
    return {
        "triggers": [],
        "condition_types": [
            "agent_status", "memory_threshold", "cpu_threshold",
            "response_time", "cost_limit", "model_pull_failure", "custom_http",
        ],
        "action_types": [
            "alert", "restart_container", "switch_model",
            "scale_down", "webhook", "log",
        ],
    }


def _save_triggers(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save triggers to triggers.json."""
    with _triggers_lock:
        try:
            TRIGGERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return {"success": True}
        except (OSError, TypeError, ValueError) as exc:
            return {"success": False, "error": str(exc)}


def _evaluate_trigger(trigger: Dict[str, Any]) -> bool:
    """Test a trigger condition against live state."""
    cond = trigger.get("condition", {})
    ctype = cond.get("type", "")
    if ctype == "agent_status":
        agent_id = cond.get("agent_id", "")
        expected = cond.get("expected", "running")
        plat = next((p for p in PLATFORMS if p["id"] == agent_id), None)
        if plat:
            health = _check_agent_health(plat["port"])
            return health["status"] != expected
    elif ctype == "cost_limit":
        billing = _read_billing_data()
        limit = cond.get("limit", 50.0)
        return billing["total_cost"] >= limit
    elif ctype == "custom_http":
        url = cond.get("url", "")
        expect_status = cond.get("expect_status", 200)
        if url:
            try:
                resp = urllib.request.urlopen(url, timeout=5)
                return resp.status != expect_status
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                return True
    return False


def _send_alert_to_channel(channel_id: str, message: str, config: Dict[str, str]) -> bool:
    """Route alert to Telegram/Slack/Discord/Email/Webhook."""
    try:
        if channel_id == "telegram":
            token = config.get("bot_token", "")
            chat_id = config.get("chat_id", "")
            if token and chat_id:
                payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=10)
                return True
        elif channel_id == "slack":
            webhook_url = config.get("webhook_url", "")
            if webhook_url:
                payload = json.dumps({"text": message}).encode()
                req = urllib.request.Request(
                    webhook_url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=10)
                return True
        elif channel_id == "discord":
            webhook_url = config.get("webhook_url", "")
            if webhook_url:
                payload = json.dumps({"content": message}).encode()
                req = urllib.request.Request(
                    webhook_url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=10)
                return True
        elif channel_id == "email":
            host = config.get("smtp_host", "")
            port = int(config.get("smtp_port", "587"))
            user = config.get("smtp_user", "")
            pwd = config.get("smtp_pass", "")
            to_addr = config.get("to", "")
            if host and to_addr:
                msg = MIMEText(message)
                msg["Subject"] = "[XClaw Alert] Trigger Fired"
                msg["From"] = config.get("from", user)
                msg["To"] = to_addr
                with smtplib.SMTP(host, port, timeout=10) as s:
                    s.starttls()
                    if user and pwd:
                        s.login(user, pwd)
                    s.sendmail(msg["From"], [to_addr], msg.as_string())
                return True
        elif channel_id == "webhook":
            url = config.get("url", "")
            if url:
                payload = json.dumps({
                    "event": "trigger_fired",
                    "message": message,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }).encode()
                req = urllib.request.Request(
                    url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=10)
                return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        _append_log("error", f"Alert to {channel_id} failed: {exc}", "triggers")
    return False


def _execute_trigger_action(trigger: Dict[str, Any], context: str = "") -> Dict[str, Any]:
    """Multi-channel alert dispatcher for trigger actions."""
    actions = trigger.get("actions", [])
    results = []
    for action in actions:
        atype = action.get("type", "")
        if atype == "alert":
            channels = action.get("channels", [])
            msg = f"[XClaw Trigger] {trigger.get('name', 'Unknown')}: {context}"
            for ch in channels:
                ch_config = action.get("channel_config", {}).get(ch, {})
                sent = _send_alert_to_channel(ch, msg, ch_config)
                results.append({"channel": ch, "sent": sent})
        elif atype == "restart_container":
            agent_id = trigger.get("condition", {}).get("agent_id", "")
            if agent_id:
                _agent_action(agent_id, "restart")
                results.append({"action": "restart", "agent": agent_id, "done": True})
        elif atype == "log":
            _append_log("warn", f"Trigger fired: {trigger.get('name', '')} — {context}", "triggers")
            results.append({"action": "log", "done": True})
        elif atype == "webhook":
            url = action.get("url", "")
            if url:
                _send_alert_to_channel("webhook", context, {"url": url})
                results.append({"action": "webhook", "url": url, "done": True})
    return {"results": results}


class TriggerEngine:
    """Background thread that evaluates triggers periodically."""

    def __init__(self, interval: int = 30):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _append_log("info", f"Trigger engine started (interval={self.interval}s)", "triggers")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                data = _load_triggers()
                for trigger in data.get("triggers", []):
                    if not trigger.get("enabled", True):
                        continue
                    # Check cooldown
                    cooldown = trigger.get("cooldown", 300)
                    last_fired = trigger.get("last_fired", 0)
                    if time.time() - last_fired < cooldown:
                        continue
                    if _evaluate_trigger(trigger):
                        trigger["last_fired"] = time.time()
                        trigger["fire_count"] = trigger.get("fire_count", 0) + 1
                        _execute_trigger_action(trigger, f"Condition met: {trigger.get('condition', {}).get('type', '')}")
                        _append_log("warn", f"Trigger '{trigger.get('name', '')}' fired (#{trigger['fire_count']})", "triggers")
                _save_triggers(data)
            except (KeyError, ValueError, OSError, RuntimeError) as exc:
                _append_log("error", f"Trigger engine error: {exc}", "triggers")
            self._stop_event.wait(self.interval)


_trigger_engine: Optional[TriggerEngine] = None

# ── Instance / Cluster Management ───────────────────────────────────────
_instances_lock = threading.Lock()


def _load_instances() -> Dict[str, Any]:
    """Load instances from instances.json."""
    with _instances_lock:
        data = _read_json_file(INSTANCES_FILE)
    if data:
        return data
    return {
        "instances": [{
            "id": "inst_local",
            "name": "Local Dev",
            "host": "localhost",
            "wizard_port": 9098,
            "watchdog_port": 9090,
            "agent_ports": {p["id"]: p["port"] for p in PLATFORMS},
            "is_self": True,
        }],
        "shared_resources": {
            "ollama": {"host": "localhost", "port": 11434, "shared": True},
            "api_keys": {"shared": True, "source": ".env"},
        },
    }


def _save_instances(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save instances to instances.json."""
    with _instances_lock:
        try:
            INSTANCES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return {"success": True}
        except (OSError, TypeError, ValueError) as exc:
            return {"success": False, "error": str(exc)}


def _check_instance_health(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Probe remote wizard API + watchdog."""
    host = instance.get("host", "localhost")
    wiz_port = instance.get("wizard_port", 9098)
    wd_port = instance.get("watchdog_port", 9090)

    wizard_ok = _check_port(wiz_port, host)
    watchdog_ok = _check_port(wd_port, host)

    # Check agents on this instance
    agent_ports = instance.get("agent_ports", {})
    agents_running = 0
    agents_total = len(agent_ports)
    agent_details = []
    for aid, aport in agent_ports.items():
        alive = _check_port(aport, host)
        if alive:
            agents_running += 1
        agent_details.append({"id": aid, "port": aport, "status": "running" if alive else "stopped"})

    status = "healthy"
    if not wizard_ok:
        status = "unreachable"
    elif agents_running == 0:
        status = "degraded"
    elif agents_running < agents_total:
        status = "partial"

    return {
        "id": instance.get("id", ""),
        "name": instance.get("name", ""),
        "host": host,
        "status": status,
        "wizard": wizard_ok,
        "watchdog": watchdog_ok,
        "agents_running": agents_running,
        "agents_total": agents_total,
        "agents": agent_details,
    }


# ── Claw Creation (deploy new agent from dashboard) ────────────────────
_claws_lock = threading.Lock()


def _load_claws() -> List[Dict[str, Any]]:
    """Load deployed claw configs."""
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    claws = []
    for f in sorted(CLAWS_DIR.glob("*.json")):
        try:
            claws.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return claws


def _save_claw(claw: Dict[str, Any]) -> Dict[str, Any]:
    """Save a claw config."""
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    claw_id = claw.get("id", f"claw_{int(time.time())}")
    claw["id"] = claw_id
    claw["created_at"] = claw.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        (CLAWS_DIR / f"{claw_id}.json").write_text(json.dumps(claw, indent=2), encoding="utf-8")
        return {"success": True, "id": claw_id}
    except (OSError, TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


def _delete_claw(claw_id: str) -> Dict[str, Any]:
    """Delete a claw config."""
    path = CLAWS_DIR / f"{claw_id}.json"
    if path.exists():
        path.unlink()
        return {"success": True}
    return {"success": False, "error": "Not found"}


# ── Agent Start/Stop/Restart ────────────────────────────────────────────
def _agent_action(agent_id: str, action: str) -> Dict[str, Any]:
    """Start/stop/restart an agent platform."""
    valid_ids = {p["id"] for p in PLATFORMS}
    if agent_id not in valid_ids:
        return {"success": False, "error": f"Unknown agent: {agent_id}"}

    plat = next(p for p in PLATFORMS if p["id"] == agent_id)
    port = plat["port"]

    if action == "stop":
        # Try docker compose down
        rc, out, stderr = _run_cmd(
            ["docker", "compose", "-f", "docker-compose.yml", "--profile", agent_id, "down"],
            timeout=30,
        )
        # Also kill any stub
        if f"agent-{agent_id}" in _service_procs:
            try:
                _service_procs[f"agent-{agent_id}"].terminate()
                del _service_procs[f"agent-{agent_id}"]
            except (OSError, KeyError):
                pass
        _append_log("info", f"Agent {agent_id} stopped", "agents")
        return {"success": True, "action": "stop", "agent": agent_id}

    elif action == "start":
        if _check_port(port):
            return {"success": True, "action": "start", "agent": agent_id, "note": "Already running"}
        # Try docker compose up
        rc, out, stderr = _run_cmd(
            ["docker", "compose", "-f", "docker-compose.yml", "--profile", agent_id, "up", "-d"],
            timeout=60,
        )
        if rc == 0 and _check_port(port):
            _append_log("info", f"Agent {agent_id} started via Docker on :{port}", "agents")
            return {"success": True, "action": "start", "agent": agent_id}
        # Fallback to stub
        stub_script = SCRIPT_DIR / "claw_agent_stub.py"
        if stub_script.exists():
            try:
                proc = subprocess.Popen(
                    ["python", str(stub_script), "--port", str(port), "--name", agent_id],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=str(PROJECT_ROOT),
                )
                _service_procs[f"agent-{agent_id}"] = proc
                time.sleep(2)
                _append_log("info", f"Agent {agent_id} started via stub on :{port}", "agents")
                return {"success": True, "action": "start", "agent": agent_id, "mode": "stub"}
            except (subprocess.SubprocessError, OSError) as exc:
                return {"success": False, "error": str(exc)}
        return {"success": False, "error": "No Docker or stub available"}

    elif action == "restart":
        _agent_action(agent_id, "stop")
        time.sleep(1)
        return _agent_action(agent_id, "start")

    return {"success": False, "error": f"Unknown action: {action}"}


# ── Channel Config ──────────────────────────────────────────────────────
def _load_channel_config() -> Dict[str, Any]:
    """Load channel configuration."""
    data = _read_json_file(CHANNEL_CONFIG_FILE)
    if data:
        return data
    return {
        "channels": {},
        "fallback_chain": ["telegram", "slack", "discord", "email", "webhook"],
        "routing_rules": {},
    }


def _save_channel_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save channel configuration."""
    try:
        CHANNEL_CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"success": True}
    except (OSError, TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


# ── Metrics Aggregation ─────────────────────────────────────────────────
def _get_dashboard_metrics() -> Dict[str, Any]:
    """Aggregate watchdog + billing + trigger data.

    Uses DAL for agent list when available (cached 10s).
    """
    # Try DAL for agent status (cached, avoids HTTP pings)
    agents = None
    try:
        from claw_dal import DAL
        dal = DAL.get_instance()
        rows = dal.agents.list_all()
        if rows:
            agents = []
            for row in rows:
                status = row.get("status", "stopped")
                if status == "healthy":
                    status = "running"
                elif status in ("unhealthy", "degraded"):
                    status = "stopped"
                agents.append({
                    "id": row.get("agent_id", ""),
                    "name": row.get("name", ""),
                    "status": status,
                    "port": 0,
                })
    except (ImportError, RuntimeError, OSError, KeyError):
        pass
    if agents is None:
        agents = _get_all_agents_status()
    running = sum(1 for a in agents if a["status"] == "running")
    billing = _read_billing_data()
    triggers_data = _load_triggers()
    active_triggers = sum(1 for t in triggers_data.get("triggers", []) if t.get("enabled", True))
    instances = _load_instances()

    # Try to get watchdog metrics
    watchdog_data = None
    if _check_port(9090):
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:9090/api/status", timeout=3)
            watchdog_data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
            pass

    return {
        "agents_total": len(agents),
        "agents_running": running,
        "agents": agents,
        "cost_today": billing.get("total_cost", 0),
        "total_requests": billing.get("total_requests", 0),
        "active_triggers": active_triggers,
        "total_triggers": len(triggers_data.get("triggers", [])),
        "instances_total": len(instances.get("instances", [])),
        "watchdog": watchdog_data,
        "services": {
            "gateway": _check_port(9095),
            "optimizer": _check_port(9091),
            "watchdog": _check_port(9090),
            "wizard": True,
            "ollama": _check_port(11434),
        },
    }


# ── Security Rule Toggle ───────────────────────────────────────────────
def _toggle_security_rule(rule_id: str, enabled: bool) -> Dict[str, Any]:
    """Toggle a security rule category on/off in security_rules.json."""
    if not SECURITY_RULES_FILE.exists():
        return {"success": False, "error": "security_rules.json not found"}
    try:
        rules = json.loads(SECURITY_RULES_FILE.read_text(encoding="utf-8"))
        if rule_id not in rules or not isinstance(rules[rule_id], dict):
            return {"success": False, "error": f"Rule category '{rule_id}' not found"}
        rules[rule_id]["enabled"] = enabled
        SECURITY_RULES_FILE.write_text(json.dumps(rules, indent=2), encoding="utf-8")
        _append_log("info", f"Security rule '{rule_id}' {'enabled' if enabled else 'disabled'}", "security")
        return {"success": True, "rule_id": rule_id, "enabled": enabled}
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
        return {"success": False, "error": str(exc)}


REQUIRED_ASSESSMENT_FIELDS = ["platform", "agent_name"]


def _validate_assessment(body: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an assessment JSON payload."""
    errors: List[str] = []
    warnings: List[str] = []

    for field in REQUIRED_ASSESSMENT_FIELDS:
        if field not in body:
            errors.append(f"Missing required field: {field}")

    platform_id = body.get("platform", "")
    valid_ids = {p["id"] for p in PLATFORMS}
    if platform_id and platform_id not in valid_ids:
        errors.append(f"Unknown platform: {platform_id}. Must be one of: {', '.join(sorted(valid_ids))}")

    if "security_rules" in body and not isinstance(body["security_rules"], list):
        errors.append("security_rules must be a list")

    if not body.get("agent_name", "").strip():
        errors.append("agent_name must be a non-empty string")

    if body.get("port") is not None:
        try:
            port = int(body["port"])
            if not (1024 <= port <= 65535):
                warnings.append("Port outside recommended range 1024-65535")
        except (ValueError, TypeError):
            errors.append("port must be an integer")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _run_cmd(cmd: List[str], timeout: int = 120, env: Optional[Dict[str, str]] = None) -> tuple:
    """Run a command and return (returncode, stdout, stderr). Works on Windows + WSL."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT), env=env,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except (subprocess.SubprocessError, OSError) as exc:
        return -1, "", str(exc)


def _check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is reachable."""
    import socket as _sock
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((host, port))
        return True
    except (ConnectionRefusedError, OSError):
        return False
    finally:
        s.close()


def _detect_pkg_manager() -> str:
    """Detect the Linux package manager available on this system."""
    for mgr in ["apt-get", "dnf", "yum", "pacman", "zypper", "apk"]:
        rc, _, _ = _run_cmd(["which", mgr])
        if rc == 0:
            return mgr
    return "unknown"


# ---------------------------------------------------------------------------
#  Auto-install / auto-launch helpers  (Docker, WSL, Git, LLM runtimes)
# ---------------------------------------------------------------------------

def _auto_docker(os_name: str, log_fn=None) -> tuple:
    """Core Docker auto-install / auto-launch logic.
    Returns (ok: bool, message: str).  *log_fn* is an optional
    callback ``log_fn(msg)`` used to emit progress messages; when
    ``None`` messages are silently discarded."""
    import platform as _plat
    if not os_name:
        os_name = _plat.system()

    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)

    # 1. Already running?
    rc, _, _ = _run_cmd(["docker", "info"], timeout=15)
    if rc == 0:
        _log("Docker is running")
        return True, "Docker is running"

    # 2. Installed but not running?
    rc_ver, _, _ = _run_cmd(["docker", "--version"])
    if rc_ver != 0:
        # 3. Not installed — install per OS
        _log("Docker not found — installing...")
        if os_name == "Windows":
            _run_cmd(["winget", "install", "-e", "--id", "Docker.DockerDesktop",
                       "--accept-package-agreements", "--accept-source-agreements"],
                      timeout=300)
        elif os_name == "Darwin":
            _run_cmd(["brew", "install", "--cask", "docker"], timeout=300)
        else:
            # Linux: official convenience script
            _run_cmd(["bash", "-c", "curl -fsSL https://get.docker.com | sh"],
                      timeout=300)
        # Verify install
        rc_ver, _, _ = _run_cmd(["docker", "--version"])
        if rc_ver != 0:
            _log("Docker installation failed — please install manually")
            return False, "Docker installation failed — please install manually"
        _log("Docker installed successfully")

    # 4. Launch the daemon
    _log("Starting Docker...")
    if os_name == "Windows":
        _run_cmd(["powershell", "-Command",
                   "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'"],
                  timeout=30)
        max_wait, interval = 60, 3
    elif os_name == "Darwin":
        _run_cmd(["open", "-a", "Docker"], timeout=15)
        max_wait, interval = 60, 3
    else:
        _run_cmd(["systemctl", "start", "docker"], timeout=30)
        max_wait, interval = 30, 2

    # 5. Poll until ready
    for i in range(1, max_wait // interval + 1):
        time.sleep(interval)
        rc, _, _ = _run_cmd(["docker", "info"], timeout=10)
        if rc == 0:
            msg = f"Docker started (ready after {i * interval}s)"
            _log(msg)
            return True, msg
    _log("Docker started — may need more time to initialize")
    return True, "Docker started — may need more time to initialize"  # optimistic


def _ensure_docker(os_name: str) -> bool:
    """Deploy-pipeline wrapper: ensures Docker via _auto_docker with deploy logging."""
    def _deploy_log(msg: str) -> None:
        _update_deploy(4, f"[Pre-check] {msg}")
    ok, _ = _auto_docker(os_name, log_fn=_deploy_log)
    return ok


def _ensure_wsl() -> None:
    """Windows-only: ensure WSL is installed (non-blocking, advisory)."""
    rc, _, _ = _run_cmd(["wsl", "--status"])
    if rc == 0:
        _update_deploy(3, "[Pre-check] WSL2 installed and available")
        return
    _update_deploy(3, "[Pre-check] WSL not found — attempting install...")
    _run_cmd(["wsl", "--install", "--no-distribution"], timeout=120)
    _update_deploy(3, "[Pre-check] WSL install requested — a reboot may be needed")
    _update_deploy(3, "[Pre-check] Docker Desktop can use Hyper-V backend in the meantime")


def _ensure_git(os_name: str) -> None:
    """Ensure Git is installed. Auto-installs if needed."""
    rc, _, _ = _run_cmd(["git", "--version"])
    if rc == 0:
        _update_deploy(6, "[Pre-check] Git is installed")
        return
    _update_deploy(6, "[Pre-check] Git not found — installing...")
    if os_name == "Windows":
        _run_cmd(["winget", "install", "-e", "--id", "Git.Git",
                   "--accept-package-agreements", "--accept-source-agreements"],
                  timeout=300)
    elif os_name == "Darwin":
        _run_cmd(["xcode-select", "--install"], timeout=300)
    else:
        pkg = _detect_pkg_manager()
        if pkg in ("apt-get", "dnf", "yum", "zypper"):
            _run_cmd(["sudo", pkg, "install", "-y", "git"], timeout=120)
        elif pkg == "pacman":
            _run_cmd(["sudo", "pacman", "-S", "--noconfirm", "git"], timeout=120)
        elif pkg == "apk":
            _run_cmd(["sudo", "apk", "add", "git"], timeout=120)
    rc2, _, _ = _run_cmd(["git", "--version"])
    if rc2 == 0:
        _update_deploy(6, "[Pre-check] Git installed successfully")
    else:
        _update_deploy(6, "[Pre-check] Git installation failed — some features may not work")


def _ensure_runtime(runtime: str, os_name: str) -> bool:
    """Ensure the selected LLM runtime is installed natively (bare metal) and running.
    All runtimes install directly on the host for full GPU access.
    Dispatches to per-runtime logic. Returns True when the runtime is ready."""

    if runtime == "ollama":
        return _ensure_ollama(os_name)
    elif runtime == "vllm":
        return _ensure_vllm(os_name)
    elif runtime in ("llama-cpp", "llamacpp"):
        return _ensure_llamacpp(os_name)
    elif runtime in ("ipex-llm", "ipexllm"):
        return _ensure_ipexllm(os_name)
    elif runtime == "sglang":
        return _ensure_sglang(os_name)
    else:
        _update_deploy(6, f"[Pre-check] Unknown runtime '{runtime}' — skipping auto-setup")
        return False


def _ensure_ollama(os_name: str) -> bool:
    """Ensure Ollama is installed and serving on port 11434."""
    # Already running?
    if _check_port(11434):
        _update_deploy(6, "[Pre-check] Ollama is running on :11434")
        return True
    # Installed?
    rc, _, _ = _run_cmd(["ollama", "--version"])
    if rc != 0:
        _update_deploy(6, "[Pre-check] Ollama not found — installing...")
        if os_name == "Windows":
            _run_cmd(["winget", "install", "-e", "--id", "Ollama.Ollama",
                       "--accept-package-agreements", "--accept-source-agreements"],
                      timeout=300)
        elif os_name == "Darwin":
            rc_brew, _, _ = _run_cmd(["brew", "install", "ollama"], timeout=300)
            if rc_brew != 0:
                _run_cmd(["bash", "-c",
                           "curl -fsSL https://ollama.com/install.sh | sh"],
                          timeout=300)
        else:
            _run_cmd(["bash", "-c",
                       "curl -fsSL https://ollama.com/install.sh | sh"],
                      timeout=300)
        rc2, _, _ = _run_cmd(["ollama", "--version"])
        if rc2 != 0:
            _update_deploy(6, "[Pre-check] Ollama installation failed")
            return False
        _update_deploy(6, "[Pre-check] Ollama installed successfully")

    # Launch
    _update_deploy(6, "[Pre-check] Starting Ollama...")
    try:
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        _service_procs["ollama"] = proc
    except (subprocess.SubprocessError, OSError) as exc:
        _update_deploy(6, f"[Pre-check] Ollama start error: {exc}")
        return False
    for i in range(1, 16):
        time.sleep(1)
        if _check_port(11434):
            _update_deploy(6, f"[Pre-check] Ollama started on :11434 (ready after {i}s)")
            return True
    _update_deploy(6, "[Pre-check] Ollama process started — may need more time")
    return True


def _ensure_vllm(os_name: str) -> bool:
    """Ensure vLLM is installed and ready on port 8000."""
    if _check_port(8000):
        _update_deploy(6, "[Pre-check] vLLM is running on :8000")
        return True
    # Check import
    rc, _, _ = _run_cmd(["python", "-c", "import vllm"])
    if rc != 0:
        _update_deploy(6, "[Pre-check] vLLM not found — installing...")
        # Pre-deps: CUDA check on Linux
        if os_name == "Linux":
            rc_nv, _, _ = _run_cmd(["nvidia-smi"])
            if rc_nv != 0:
                _update_deploy(6, "[Pre-check] WARNING: nvidia-smi not found — vLLM requires CUDA")
                pkg = _detect_pkg_manager()
                if pkg == "apt-get":
                    _run_cmd(["sudo", "apt-get", "install", "-y", "nvidia-cuda-toolkit"],
                              timeout=300)
                elif pkg in ("dnf", "yum"):
                    _run_cmd(["sudo", pkg, "install", "-y", "cuda"], timeout=300)
        _run_cmd(["pip", "install", "vllm"], timeout=600)
        rc2, _, _ = _run_cmd(["python", "-c", "import vllm"])
        if rc2 != 0:
            _update_deploy(6, "[Pre-check] vLLM installation failed — CUDA GPU required")
            return False
        _update_deploy(6, "[Pre-check] vLLM installed successfully")
    # Launch
    _update_deploy(6, "[Pre-check] Starting vLLM server on :8000...")
    try:
        proc = subprocess.Popen(
            ["python", "-m", "vllm.entrypoints.openai.api_server", "--port", "8000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        _service_procs["vllm"] = proc
    except (subprocess.SubprocessError, OSError) as exc:
        _update_deploy(6, f"[Pre-check] vLLM start error: {exc}")
        return False
    for i in range(1, 31):
        time.sleep(1)
        if _check_port(8000):
            _update_deploy(6, f"[Pre-check] vLLM started on :8000 (ready after {i}s)")
            return True
    _update_deploy(6, "[Pre-check] vLLM process started — may need more time to load model")
    return True


def _ensure_llamacpp(os_name: str) -> bool:
    """Ensure llama.cpp (llama-server) is installed and ready on port 8080."""
    if _check_port(8080):
        _update_deploy(6, "[Pre-check] llama-server is running on :8080")
        return True
    # Installed?
    rc, _, _ = _run_cmd(["llama-server", "--version"])
    if rc != 0:
        _update_deploy(6, "[Pre-check] llama-server not found — installing...")
        if os_name == "Darwin":
            _run_cmd(["brew", "install", "llama.cpp"], timeout=300)
        elif os_name == "Windows":
            _update_deploy(6, "[Pre-check] Downloading llama.cpp for Windows...")
            _run_cmd(["powershell", "-Command",
                       "Invoke-WebRequest -Uri "
                       "'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-server-windows-amd64.zip'"
                       " -OutFile llama-server.zip; "
                       "Expand-Archive -Path llama-server.zip -DestinationPath $env:LOCALAPPDATA\\llama-cpp -Force; "
                       "Remove-Item llama-server.zip"],
                      timeout=300)
        else:
            # Linux: use install script if present, else download binary
            install_sh = PROJECT_ROOT / "shared" / "install-llamacpp.sh"
            if install_sh.exists():
                _run_cmd(["bash", str(install_sh)], timeout=300)
            else:
                import platform as _plat
                arch = _plat.machine()
                arch_suffix = "aarch64" if "aarch64" in arch or "arm" in arch else "x86_64"
                _run_cmd(["bash", "-c",
                           f"curl -fsSL https://github.com/ggerganov/llama.cpp/releases/latest/download/"
                           f"llama-server-linux-{arch_suffix}.tar.gz | sudo tar -xz -C /usr/local/bin/"],
                          timeout=300)
        rc2, _, _ = _run_cmd(["llama-server", "--version"])
        if rc2 != 0:
            _update_deploy(6, "[Pre-check] llama-server installation failed")
            return False
        _update_deploy(6, "[Pre-check] llama-server installed successfully")
    # Launch — note: llama.cpp needs a GGUF model to actually serve
    _update_deploy(6, "[Pre-check] Starting llama-server on :8080...")
    _update_deploy(6, "[Pre-check] WARNING: llama-server needs a --model <path.gguf> to serve requests")
    try:
        proc = subprocess.Popen(
            ["llama-server", "--port", "8080", "--host", "0.0.0.0"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        _service_procs["llamacpp"] = proc
    except (subprocess.SubprocessError, OSError) as exc:
        _update_deploy(6, f"[Pre-check] llama-server start error: {exc}")
        return False
    for i in range(1, 16):
        time.sleep(1)
        if _check_port(8080):
            _update_deploy(6, f"[Pre-check] llama-server started on :8080 (ready after {i}s)")
            return True
    _update_deploy(6, "[Pre-check] llama-server process started — may need more time")
    return True


def _ensure_ipexllm(os_name: str) -> bool:
    """Ensure ipex-llm is installed and serving on port 8010."""
    if _check_port(8010):
        _update_deploy(6, "[Pre-check] ipex-llm is running on :8010")
        return True
    rc, _, _ = _run_cmd(["python", "-c", "import ipex_llm"])
    if rc != 0:
        _update_deploy(6, "[Pre-check] ipex-llm not found — installing...")
        if os_name == "Linux":
            # Intel GPU pre-deps
            rc_sycl, _, _ = _run_cmd(["sycl-ls"])
            if rc_sycl != 0:
                _update_deploy(6, "[Pre-check] WARNING: sycl-ls not found — Intel GPU drivers may be missing")
        _run_cmd(["pip", "install", "ipex-llm[serving]"], timeout=600)
        rc2, _, _ = _run_cmd(["python", "-c", "import ipex_llm"])
        if rc2 != 0:
            _update_deploy(6, "[Pre-check] ipex-llm installation failed — Intel GPU may be required")
            return False
        _update_deploy(6, "[Pre-check] ipex-llm installed successfully")
    # Launch
    _update_deploy(6, "[Pre-check] Starting ipex-llm server on :8010...")
    try:
        proc = subprocess.Popen(
            ["python", "-m", "ipex_llm.serving.fastapi", "--port", "8010"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        _service_procs["ipexllm"] = proc
    except (subprocess.SubprocessError, OSError) as exc:
        _update_deploy(6, f"[Pre-check] ipex-llm start error: {exc}")
        return False
    for i in range(1, 31):
        time.sleep(1)
        if _check_port(8010):
            _update_deploy(6, f"[Pre-check] ipex-llm started on :8010 (ready after {i}s)")
            return True
    _update_deploy(6, "[Pre-check] ipex-llm process started — may need more time")
    return True


def _ensure_sglang(os_name: str) -> bool:
    """Ensure SGLang is installed and serving on port 30000."""
    if _check_port(30000):
        _update_deploy(6, "[Pre-check] SGLang is running on :30000")
        return True
    rc, _, _ = _run_cmd(["python", "-c", "import sglang"])
    if rc != 0:
        _update_deploy(6, "[Pre-check] SGLang not found — installing...")
        # CUDA pre-deps (same as vLLM)
        if os_name == "Linux":
            rc_nv, _, _ = _run_cmd(["nvidia-smi"])
            if rc_nv != 0:
                _update_deploy(6, "[Pre-check] WARNING: nvidia-smi not found — SGLang requires CUDA")
                pkg = _detect_pkg_manager()
                if pkg == "apt-get":
                    _run_cmd(["sudo", "apt-get", "install", "-y", "nvidia-cuda-toolkit"],
                              timeout=300)
                elif pkg in ("dnf", "yum"):
                    _run_cmd(["sudo", pkg, "install", "-y", "cuda"], timeout=300)
        _run_cmd(["pip", "install", "sglang[all]"], timeout=600)
        rc2, _, _ = _run_cmd(["python", "-c", "import sglang"])
        if rc2 != 0:
            _update_deploy(6, "[Pre-check] SGLang installation failed — CUDA GPU required")
            return False
        _update_deploy(6, "[Pre-check] SGLang installed successfully")
    # Launch
    _update_deploy(6, "[Pre-check] Starting SGLang server on :30000...")
    try:
        proc = subprocess.Popen(
            ["python", "-m", "sglang.launch_server", "--port", "30000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        _service_procs["sglang"] = proc
    except (subprocess.SubprocessError, OSError) as exc:
        _update_deploy(6, f"[Pre-check] SGLang start error: {exc}")
        return False
    for i in range(1, 31):
        time.sleep(1)
        if _check_port(30000):
            _update_deploy(6, f"[Pre-check] SGLang started on :30000 (ready after {i}s)")
            return True
    _update_deploy(6, "[Pre-check] SGLang process started — may need more time to load model")
    return True


# Track child service processes so we can clean up
_service_procs: Dict[str, subprocess.Popen] = {}


def _update_deploy(progress: int, message: str, state: str = "running",
                    extra: Optional[Dict] = None) -> None:
    """Thread-safe deploy status update.  Appends to a log queue."""
    global _deploy_status
    with _deploy_lock:
        if "logs" not in _deploy_status or _deploy_status.get("state") != "running":
            _deploy_status = {"state": state, "progress": progress,
                              "message": message, "logs": []}
        _deploy_status["state"] = state
        _deploy_status["progress"] = progress
        _deploy_status["message"] = message
        _deploy_status["logs"].append(message)
        if extra:
            _deploy_status.update(extra)


def _run_deploy(assessment_json: str) -> None:
    """Full xClaw ecosystem deployment — builds and runs an isolated Docker container
    with the complete XClaw stack (agent, security, optimizer, router, watchdog, wizard API).
    Ollama runs on the host and is shared across all containers."""
    global _deploy_status

    _update_deploy(0, "=== xClaw Docker Deployment Pipeline ===")

    try:
        _run_deploy_inner(assessment_json)
    except Exception as exc:  # Broad catch: top-level deploy thread must report all errors
        import traceback
        tb = traceback.format_exc()
        _update_deploy(0, f"FATAL: Unhandled exception in deploy thread: {exc}", state="error")
        _update_deploy(0, tb, state="error")


def _run_deploy_inner(assessment_json: str) -> None:
    """Inner deploy logic — called by _run_deploy with exception safety."""
    # Parse assessment
    try:
        config = json.loads(assessment_json)
    except json.JSONDecodeError:
        _update_deploy(0, "ERROR: Invalid assessment JSON", state="error")
        return

    platform = config.get("platform", "zeroclaw")
    llm_provider = config.get("llm_provider", "hybrid")
    runtime = config.get("runtime", "ollama")
    sec = config.get("security", {})
    security_enabled = sec.get("enabled", True) if isinstance(sec, dict) else config.get("security_enabled", True)
    security_config = sec.get("config", {}) if isinstance(sec, dict) else {}
    security_features = sec.get("features", []) if isinstance(sec, dict) else []
    compliance_config = sec.get("compliance", {}) if isinstance(sec, dict) else {}
    selected_models = config.get("selected_models", [])
    strategy_cfg = config.get("strategy", {})
    agent_name = config.get("agent_name", "xclaw-agent")
    gateway_cfg = config.get("gateway", {})
    api_keys = config.get("api_keys", {})
    cloud_providers = config.get("cloud_providers", [])
    channels_cfg = config.get("channels", {})

    # Write assessment file (the FULL config — container reads this at startup)
    tmp_assessment = PROJECT_ROOT / "data" / "wizard" / f"{agent_name}-assessment.json"
    tmp_assessment.parent.mkdir(parents=True, exist_ok=True)
    tmp_assessment.write_text(assessment_json, encoding="utf-8")
    _update_deploy(1, f"Assessment saved to {tmp_assessment}")

    PLATFORM_META = {p["id"]: p for p in PLATFORMS}
    plat_info = PLATFORM_META.get(platform, {})

    # Port allocation — use manual ports if specified, otherwise auto-detect
    port_config = config.get("port_config", {})
    storage_config = config.get("storage", {})
    storage_engine = storage_config.get("engine", "sqlite")

    # Ensure unique instance_db.path per claw deployment (avoid shared default)
    # Deferred: agent_port resolved below, so we set instance_db.path later.

    if port_config.get("mode") == "manual" and port_config.get("agentPort"):
        agent_port = port_config["agentPort"]
    else:
        allocated = _allocate_ports_for_claw(platform)
        agent_port = allocated["agent"]

    # Resolve all service ports from wizard config (not hardcoded)
    gateway_port = int(port_config.get("gatewayPort") or gateway_cfg.get("port") or 9095)
    optimizer_port = int(port_config.get("optimizerPort") or 9091)
    watchdog_port = int(port_config.get("watchdogPort") or 9090)

    # Generate a unique container name from the agent name + timestamp hash.
    # Format: xclaw-{agent_name}-{4-hex-suffix}  e.g. xclaw-my-agent-a3f1
    _name_base = f"xclaw-{agent_name}".lower().replace(" ", "-")
    _unique_seed = f"{agent_name}-{time.time_ns()}"
    _suffix = hashlib.sha256(_unique_seed.encode()).hexdigest()[:4]
    container_name = f"{_name_base}-{_suffix}"
    image_name = f"xclaw:{platform}"

    # Set unique instance_db.path per claw to avoid all claws sharing one DB
    if storage_engine == "sqlite":
        if "instance_db" not in storage_config:
            storage_config["instance_db"] = {"engine": "sqlite", "path": ""}
        inst_db = storage_config["instance_db"]
        if not inst_db.get("path"):
            inst_db["path"] = f"./data/instance_{container_name}.db"
            log(f"Set unique instance_db.path: {inst_db['path']}")

    # ── Step 1/10: Pre-flight checks + auto-install ─────────────────
    _update_deploy(2, "")
    _update_deploy(2, "━━━ Step 1/10: Pre-flight checks ━━━")

    import platform as plat
    os_name = plat.system()
    _update_deploy(2, f"[Pre-check] OS: {os_name} {plat.release()}")

    # 1a. Docker (required for all deployments)
    if not _ensure_docker(os_name):
        _update_deploy(6, "Deployment aborted — Docker unavailable", state="error")
        return

    # 1b. WSL (Windows only, advisory)
    if os_name == "Windows":
        _ensure_wsl()

    # 1c. Git
    _ensure_git(os_name)

    # 1d. Dockerfile.xclaw
    dockerfile = PROJECT_ROOT / "Dockerfile.xclaw"
    if not dockerfile.exists():
        _update_deploy(6, "ERROR: Dockerfile.xclaw not found in project root", state="error")
        return
    _update_deploy(6, "[Pre-check] Dockerfile.xclaw found")

    # 1e. LLM runtime (if local/hybrid)
    if llm_provider in ("local", "hybrid"):
        _ensure_runtime(runtime, os_name)

    # ── Step 2/10: Validate + Create .env ───────────────────────────
    _update_deploy(8, "")
    _update_deploy(8, "━━━ Step 2/10: Validating configuration ━━━")
    _update_deploy(8, f"  Agent name:    {agent_name}")
    _update_deploy(8, f"  Container:     {container_name}")
    _update_deploy(8, f"  Image:         {image_name}")
    _update_deploy(9, f"  Platform:      {platform} ({plat_info.get('language', '?')}, {plat_info.get('memory', '?')})")
    _update_deploy(9, f"  LLM provider:  {llm_provider}")
    _update_deploy(9, f"  Runtime:       {runtime}")
    _update_deploy(10, f"  Security:      {'enabled' if security_enabled else 'disabled'}")
    _update_deploy(10, f"  Models:        {', '.join(selected_models) if selected_models else 'none selected'}")

    env_file = PROJECT_ROOT / ".env"
    env_template = PROJECT_ROOT / ".env.template"
    if not env_file.exists() and env_template.exists():
        import shutil
        shutil.copy2(str(env_template), str(env_file))
        _update_deploy(11, "  Created .env from .env.template")
    elif env_file.exists():
        _update_deploy(11, "  .env file already exists")

    # Patch .env
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
        patches = {
            # Core
            "CLAW_AGENT=": f"CLAW_AGENT={platform}",
            "CLAW_AGENT_NAME=": f"CLAW_AGENT_NAME={agent_name}",
            "CLAW_AGENT_PORT=": f"CLAW_AGENT_PORT={agent_port}",
            "CLAW_LLM_PROVIDER=": f"CLAW_LLM_PROVIDER={llm_provider}",
            "CLAW_LLM_RUNTIME=": f"CLAW_LLM_RUNTIME={runtime}",
            "CLAW_STORAGE_ENGINE=": f"CLAW_STORAGE_ENGINE={storage_engine}",
            # Ports (from wizard config, not hardcoded)
            "CLAW_GATEWAY_PORT=": f"CLAW_GATEWAY_PORT={gateway_port}",
            "CLAW_OPTIMIZER_PORT=": f"CLAW_OPTIMIZER_PORT={optimizer_port}",
            "CLAW_WATCHDOG_PORT=": f"CLAW_WATCHDOG_PORT={watchdog_port}",
            # Security
            "CLAW_SECURITY_ENABLED=": f"CLAW_SECURITY_ENABLED={'true' if security_enabled else 'false'}",
        }
        # LLM models
        if selected_models:
            patches["CLAW_OLLAMA_MODELS="] = f"CLAW_OLLAMA_MODELS={','.join(selected_models)}"
        if llm_provider in ("local", "hybrid"):
            # Inside container, LLM runtime runs on host — use host.docker.internal
            rt_port_for_env = {"ollama": 11434, "vllm": 8000, "llama-cpp": 8080,
                               "llamacpp": 8080, "ipex-llm": 8010, "ipexllm": 8010,
                               "sglang": 30000, "localai": 8080}.get(runtime, 11434)
            custom_endpoint = gateway_cfg.get("customLocalEndpoint")
            if custom_endpoint:
                patches["CLAW_LOCAL_LLM_ENDPOINT="] = f"CLAW_LOCAL_LLM_ENDPOINT={custom_endpoint}"
            else:
                patches["CLAW_LOCAL_LLM_ENDPOINT="] = f"CLAW_LOCAL_LLM_ENDPOINT=http://host.docker.internal:{rt_port_for_env}/v1"
        # Cloud provider API keys
        for provider_id, key_val in api_keys.items():
            if key_val and not key_val.startswith("sk-****"):  # skip masked placeholders
                env_var = f"{provider_id.upper()}_API_KEY="
                patches[env_var] = f"{env_var}{key_val}"
        if cloud_providers:
            patches["CLAW_CLOUD_PROVIDERS="] = f"CLAW_CLOUD_PROVIDERS={','.join(cloud_providers)}"
        # LLM strategy (optimization + task routing)
        if strategy_cfg and strategy_cfg.get("rules"):
            patches["CLAW_STRATEGY_OPTIMIZATION="] = f"CLAW_STRATEGY_OPTIMIZATION={strategy_cfg.get('optimization', 'balanced')}"
            # Save full strategy to strategy.json for the gateway/router
            strategy_file = PROJECT_ROOT / "strategy.json"
            strategy_file.write_text(json.dumps(strategy_cfg, indent=2), encoding="utf-8")
            _update_deploy(32, f"  Strategy config saved ({len(strategy_cfg['rules'])} task routing rules)")
        # Gateway config
        gw_rate_limit = gateway_cfg.get("rate_limit") or gateway_cfg.get("rateLimit")
        if gw_rate_limit:
            patches["CLAW_GATEWAY_RATE_LIMIT="] = f"CLAW_GATEWAY_RATE_LIMIT={gw_rate_limit}"
        gw_failover = gateway_cfg.get("failover")
        if gw_failover:
            patches["CLAW_GATEWAY_FAILOVER="] = f"CLAW_GATEWAY_FAILOVER={gw_failover}"
        gw_routing = gateway_cfg.get("routing")
        if gw_routing:
            patches["CLAW_GATEWAY_ROUTING="] = f"CLAW_GATEWAY_ROUTING={gw_routing}"
        # Security features
        if security_features:
            patches["CLAW_SECURITY_FEATURES="] = f"CLAW_SECURITY_FEATURES={','.join(security_features)}"
        # Storage details (PostgreSQL)
        inst_db = storage_config.get("instance_db") or storage_config.get("instanceDb", {})
        if storage_engine == "postgresql" and inst_db:
            pg = inst_db.get("postgresql", inst_db)
            if pg.get("host"):
                patches["CLAW_POSTGRES_HOST="] = f"CLAW_POSTGRES_HOST={pg['host']}"
            if pg.get("port"):
                patches["CLAW_POSTGRES_PORT="] = f"CLAW_POSTGRES_PORT={pg['port']}"
            if pg.get("user"):
                patches["CLAW_POSTGRES_USER="] = f"CLAW_POSTGRES_USER={pg['user']}"
            if pg.get("password"):
                patches["CLAW_POSTGRES_PASSWORD="] = f"CLAW_POSTGRES_PASSWORD={pg['password']}"
            if pg.get("dbname"):
                patches["CLAW_POSTGRES_DB="] = f"CLAW_POSTGRES_DB={pg['dbname']}"
        # Channel tokens — support both formats:
        #   Format A: { enabled: true, config: { token: "..." } }
        #   Format B: { botToken: "...", chatId: "..." }  (direct)
        for ch_id, ch_cfg in channels_cfg.items():
            if not isinstance(ch_cfg, dict):
                continue
            # Extract token: try nested config first, then direct keys
            ch_conf = ch_cfg.get("config", {})
            token = (ch_conf.get("token") or ch_cfg.get("botToken")
                     or ch_cfg.get("token") or ch_cfg.get("bot_token") or "")
            chat_id = (ch_conf.get("chatId") or ch_cfg.get("chatId")
                       or ch_cfg.get("chat_id") or "")
            # Accept if token present (either format)
            if not token:
                continue
            if ch_id == "telegram":
                patches["TELEGRAM_BOT_TOKEN="] = f"TELEGRAM_BOT_TOKEN={token}"
                if chat_id:
                    patches["TELEGRAM_CHAT_ID="] = f"TELEGRAM_CHAT_ID={chat_id}"
            elif ch_id == "discord":
                patches["DISCORD_BOT_TOKEN="] = f"DISCORD_BOT_TOKEN={token}"
            elif ch_id == "slack":
                patches["SLACK_BOT_TOKEN="] = f"SLACK_BOT_TOKEN={token}"
            elif ch_id == "whatsapp":
                patches["WHATSAPP_TOKEN="] = f"WHATSAPP_TOKEN={token}"
        for prefix, new_line in patches.items():
            lines = env_content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith(prefix):
                    lines[i] = new_line
                    break
            else:
                lines.append(new_line)
            env_content = "\n".join(lines)
        env_file.write_text(env_content, encoding="utf-8")
        _update_deploy(12, f"  Patched .env: agent={platform}, name={agent_name}, provider={llm_provider}")
    _update_deploy(13, "  Configuration validated successfully")

    # ── Step 3/10: Docker network ───────────────────────────────────
    _update_deploy(15, "")
    _update_deploy(15, "━━━ Step 3/10: Creating Docker bridge network ━━━")
    _update_deploy(15, "  $ docker network create --driver bridge xclaw-net")
    rc, out, stderr = _run_cmd(["docker", "network", "create", "--driver", "bridge", "xclaw-net"])
    if rc == 0:
        _update_deploy(17, "  Network 'xclaw-net' created (bridge mode)")
        _update_deploy(17, "  DNS resolution enabled for inter-container communication")
    elif "already exists" in (stderr + out):
        _update_deploy(17, "  Network 'xclaw-net' already exists — reusing")
    else:
        _update_deploy(17, f"  Network warning: {(stderr or out)[:120]}")

    # ── Step 4/10: Remove old container if exists ───────────────────
    _update_deploy(19, "")
    _update_deploy(19, "━━━ Step 4/10: Cleaning up old containers ━━━")
    rc, out, _ = _run_cmd(["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.ID}}"])
    if rc == 0 and out.strip():
        _update_deploy(19, f"  Found existing container '{container_name}' — removing...")
        _run_cmd(["docker", "stop", container_name], timeout=30)
        _run_cmd(["docker", "rm", "-f", container_name], timeout=10)
        _update_deploy(20, f"  Old container removed")
    else:
        _update_deploy(20, f"  No existing container '{container_name}' found")

    # ── Step 5/10: Build Docker image ───────────────────────────────
    _update_deploy(22, "")
    _update_deploy(22, "━━━ Step 5/10: Building XClaw Docker image ━━━")
    _update_deploy(22, f"  $ docker build -f Dockerfile.xclaw \\")
    _update_deploy(22, f"      --build-arg CLAW_AGENT={platform} \\")
    _update_deploy(22, f"      --build-arg CLAW_AGENT_PORT={agent_port} \\")
    _update_deploy(22, f"      --build-arg CLAW_AGENT_NAME={agent_name} \\")
    _update_deploy(22, f"      --build-arg CLAW_LLM_PROVIDER={llm_provider} \\")
    _update_deploy(22, f"      --build-arg CLAW_STORAGE_ENGINE={storage_engine} \\")
    _update_deploy(22, f"      -t {image_name} .")
    _update_deploy(23, "  Building image (this may take a minute)...")

    # Save storage config for the container to pick up
    if storage_config:
        _save_storage_config(storage_config)
        _update_deploy(23, f"  Storage config saved (engine={storage_engine})")

    build_cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "--build-arg", f"CLAW_AGENT={platform}",
        "--build-arg", f"CLAW_AGENT_PORT={agent_port}",
        "--build-arg", f"CLAW_AGENT_NAME={agent_name}",
        "--build-arg", f"CLAW_LLM_PROVIDER={llm_provider}",
        "--build-arg", f"CLAW_STORAGE_ENGINE={storage_engine}",
        "-t", image_name,
        str(PROJECT_ROOT),
    ]

    # Stream build output for real-time progress
    try:
        build_proc = subprocess.Popen(
            build_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
        )
        step_count = 0
        for raw_line in iter(build_proc.stdout.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            # Show key build steps
            if line.startswith("#") or "Step" in line or "COPY" in line or "RUN" in line:
                step_count += 1
                # Throttle output — show every 3rd step or important ones
                if step_count % 3 == 0 or any(kw in line for kw in ["COPY", "RUN", "FROM", "Successfully"]):
                    clean = line[:120]
                    _update_deploy(24 + min(step_count // 3, 10), f"  {clean}")
            elif "successfully" in line.lower() or "tagged" in line.lower():
                _update_deploy(35, f"  {line[:120]}")
        build_proc.wait()

        if build_proc.returncode != 0:
            _update_deploy(36, f"ERROR: Docker build failed (exit code {build_proc.returncode})")
            _update_deploy(36, "  Check Dockerfile.xclaw and build context")
            _update_deploy(36, "Deployment aborted", state="error")
            return
    except FileNotFoundError:
        _update_deploy(36, "'docker' command lost from PATH — re-running auto-install...")
        if not _ensure_docker(os_name):
            _update_deploy(36, "Deployment aborted — Docker unavailable after retry", state="error")
            return
        _update_deploy(36, "Docker recovered — please retry deployment")
        _update_deploy(36, "Deployment aborted", state="error")
        return
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        _update_deploy(36, f"ERROR: Build failed: {exc}")
        _update_deploy(36, "Deployment aborted", state="error")
        return

    _update_deploy(37, f"  Image '{image_name}' built successfully")

    # Check image size
    rc2, out2, _ = _run_cmd(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}  {{.Size}}", image_name])
    if rc2 == 0 and out2.strip():
        _update_deploy(38, f"  Image size: {out2.strip().split()[-1] if out2 else 'unknown'}")

    # ── Step 6/10: LLM Runtime (host-side shared) ───────────────────
    _update_deploy(40, "")
    _update_deploy(40, f"━━━ Step 6/10: LLM runtime ({llm_provider}) — host-side shared ━━━")
    if llm_provider in ("local", "hybrid"):
        rt_port_map = {"ollama": 11434, "vllm": 8000, "llama-cpp": 8080,
                       "llamacpp": 8080, "localai": 8080, "ipex-llm": 8010,
                       "ipexllm": 8010, "sglang": 30000}
        rt_port = rt_port_map.get(runtime, 11434)
        _update_deploy(40, f"  Runtime:   {runtime} (native bare-metal install — full GPU access)")
        _update_deploy(40, f"  Port:      :{rt_port}")
        _update_deploy(41, f"  Container access via: host.docker.internal:{rt_port}")
        if llm_provider == "hybrid":
            _update_deploy(41, f"  Mode: hybrid (local primary + cloud fallback via R11 FallbackChain)")

        # Verify runtime is still up (second-chance — Step 1 did initial setup)
        if not _check_port(rt_port):
            _update_deploy(42, f"  Runtime {runtime} not responding on :{rt_port} — retrying setup...")
            _ensure_runtime(runtime, os_name)

        if runtime == "ollama":
            # Gather existing models
            existing = []
            if _check_port(11434):
                _update_deploy(42, "  Ollama daemon running on :11434")
                try:
                    resp = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5)
                    tags = json.loads(resp.read())
                    existing = [m["name"] for m in tags.get("models", [])]
                    _update_deploy(42, f"  Installed models: {', '.join(existing) if existing else 'none'}")
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
                    pass

            # Pull selected models with real-time progress
            if selected_models and _check_port(11434):
                total_models = len(selected_models)
                for idx, model_id in enumerate(selected_models):
                    model_num = idx + 1
                    if model_id in existing:
                        _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — already downloaded")
                        continue

                    _update_deploy(44 + idx, f"  [{model_num}/{total_models}] Pulling {model_id}...")
                    try:
                        pull_proc = subprocess.Popen(
                            ["ollama", "pull", model_id],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=str(PROJECT_ROOT),
                        )
                        last_pct = ""
                        for raw_line in iter(pull_proc.stdout.readline, b""):
                            line = raw_line.decode("utf-8", errors="replace").rstrip()
                            line = line.rstrip()
                            if not line:
                                continue
                            pct_match = re.search(r'(\d+)%', line)
                            if pct_match:
                                pct = pct_match.group(1)
                                if pct != last_pct and (int(pct) % 10 == 0 or int(pct) >= 99):
                                    _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id}: {pct}% downloaded")
                                    last_pct = pct
                            elif any(kw in line.lower() for kw in ["pulling manifest", "verifying", "writing manifest", "success"]):
                                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line).strip()
                                _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id}: {clean}")
                        pull_proc.wait()
                        if pull_proc.returncode == 0:
                            try:
                                resp = urllib.request.urlopen("http://127.0.0.1:11434/api/show", timeout=5,
                                    data=json.dumps({"name": model_id}).encode())
                                minfo = json.loads(resp.read())
                                params = minfo.get("details", {}).get("parameter_size", "?")
                                quant = minfo.get("details", {}).get("quantization_level", "?")
                                _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} ready — {params}, {quant}")
                            except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
                                _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} downloaded")
                        else:
                            _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — pull finished (code {pull_proc.returncode})")
                    except FileNotFoundError:
                        # Second-chance: try to install ollama and retry
                        _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — 'ollama' not found, retrying install...")
                        _ensure_runtime(runtime, os_name)
                    except (subprocess.SubprocessError, OSError) as exc:
                        _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — error: {exc}")
            elif not selected_models:
                _update_deploy(44, "  No models selected — skipping model pull")
        else:
            # Non-Ollama runtimes: verify port is reachable
            if _check_port(rt_port):
                _update_deploy(42, f"  {runtime} is running on :{rt_port}")
            else:
                _update_deploy(42, f"  WARNING: {runtime} not responding on :{rt_port}")
                _update_deploy(42, f"  The runtime was started in Step 1 — it may still be loading a model")
    else:
        _update_deploy(41, "  Cloud-only mode — no local LLM runtime needed")
        cloud_providers = config.get("cloud_providers", [])
        if cloud_providers:
            _update_deploy(42, f"  Cloud providers: {', '.join(cloud_providers)}")
        _update_deploy(42, "  Requests will be routed to cloud APIs via gateway")
    _update_deploy(55, "  LLM runtime configured")

    # ── Step 7/10: Run Docker container ─────────────────────────────
    _update_deploy(58, "")
    _update_deploy(58, "━━━ Step 7/10: Starting XClaw container ━━━")
    _update_deploy(58, f"  Container: {container_name}")
    _update_deploy(58, f"  Image:     {image_name}")

    # Build port mappings (from wizard config)
    # Skip ports already in use on the host to avoid "port already allocated"
    # Note: Fleet Dashboard (9099) runs on the host, not inside the container
    port_mappings = []
    for hp, cp in [
        (agent_port, agent_port),
        (gateway_port, gateway_port),
        (optimizer_port, optimizer_port),
        (watchdog_port, watchdog_port),
    ]:
        if not _check_port(hp):
            port_mappings.extend(["-p", f"{hp}:{cp}"])
        else:
            _update_deploy(58, f"  Note: host port {hp} already in use — skipping mapping")

    # Build run command
    run_cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--network", "xclaw-net",
        "--restart", "unless-stopped",
    ]
    # Add port mappings
    run_cmd.extend(port_mappings)

    # Pass env file if it exists
    if env_file.exists():
        run_cmd.extend(["--env-file", str(env_file)])

    # Add extra-host for Ollama access from inside container
    if llm_provider in ("local", "hybrid"):
        run_cmd.extend(["--add-host", "host.docker.internal:host-gateway"])

    # Add labels for management
    run_cmd.extend([
        "--label", f"xclaw.agent={platform}",
        "--label", f"xclaw.name={agent_name}",
        "--label", "xclaw.managed=true",
    ])

    run_cmd.append(image_name)

    # Show the actual port mappings being used
    mapped_ports = " ".join(f"-p {p}" for p in
        [pm for i, pm in enumerate(port_mappings) if i % 2 == 1])
    _update_deploy(60, f"  $ docker run -d --name {container_name} \\")
    _update_deploy(60, f"      --network xclaw-net --restart unless-stopped \\")
    _update_deploy(60, f"      {mapped_ports} \\")
    _update_deploy(61, f"      --env-file .env {image_name}")

    rc, out, stderr = _run_cmd(run_cmd, timeout=30)
    if rc != 0:
        _update_deploy(63, f"ERROR: Failed to start container: {(stderr or out)[:200]}")
        _update_deploy(63, "Deployment aborted", state="error")
        return

    container_id = out.strip()[:12] if out.strip() else "unknown"
    _update_deploy(63, f"  Container started: {container_id}")
    _update_deploy(64, f"  Waiting for services to initialize...")

    # Wait for container to be healthy
    for wait_sec in range(1, 21):
        time.sleep(2)
        rc, out, _ = _run_cmd(["docker", "inspect", "--format", "{{.State.Status}}", container_name])
        status = out.strip() if rc == 0 else "unknown"
        if status == "running":
            # Check if agent port is reachable
            if _check_port(agent_port):
                _update_deploy(66, f"  Container running and agent responding (after {wait_sec * 2}s)")
                break
            elif wait_sec % 3 == 0:
                _update_deploy(65, f"  Container running, waiting for agent on :{agent_port}... ({wait_sec * 2}s)")
        elif status == "exited":
            # Get logs if container exited
            _, logs_out, _ = _run_cmd(["docker", "logs", "--tail", "20", container_name])
            _update_deploy(66, f"  WARNING: Container exited — last logs:")
            for log_line in (logs_out or "").split("\n")[-5:]:
                if log_line.strip():
                    _update_deploy(66, f"    {log_line.strip()[:120]}")
            break
    else:
        _update_deploy(66, f"  Container may still be initializing — continuing...")

    # ── Step 8/10: Security configuration ───────────────────────────
    _update_deploy(70, "")
    _update_deploy(70, "━━━ Step 8/10: Security configuration ━━━")
    if security_enabled:
        _update_deploy(70, "  Security gate is ACTIVE inside container:")
        _update_deploy(71, "  Inbound pipeline:")
        _update_deploy(71, "    check_url() -> check_content() -> detect_pii()")
        _update_deploy(72, "    8 URL patterns | 6 injection detectors | 8 PII patterns")
        _update_deploy(72, "    16 secret masks | 15 CIDR blocked ranges")
        _update_deploy(73, "    Rate limits: 120 RPM global, 60 RPM per user")
        _update_deploy(73, "  Outbound pipeline:")
        _update_deploy(74, "    mask_secrets() -> detect_pii() -> check_content()")
        _update_deploy(74, "    Action on match: replace with ***REDACTED***")
        sec_features = sec.get("features", []) if isinstance(sec, dict) else []
        if sec_features:
            _update_deploy(75, f"  Active features: {', '.join(sec_features)}")
    else:
        _update_deploy(71, "  Security is DISABLED inside container")
        _update_deploy(71, "  WARNING: All traffic passes without scanning")

    # ── Step 9/10: Health checks ────────────────────────────────────
    _update_deploy(78, "")
    _update_deploy(78, "━━━ Step 9/10: Running health checks ━━━")

    # Check container status
    rc, out, _ = _run_cmd(["docker", "inspect", "--format", "{{.State.Status}}", container_name])
    container_status = out.strip() if rc == 0 else "unknown"
    _update_deploy(79, f"  Container status: {container_status}")

    # Check exposed ports (only services inside the container)
    service_checks = {
        f"Agent ({platform})": agent_port,
        "Gateway Router": gateway_port,
        "Optimizer": optimizer_port,
        "Watchdog": watchdog_port,
    }
    if llm_provider in ("local", "hybrid"):
        rt_ports_map = {"ollama": 11434, "vllm": 8000, "llama-cpp": 8080,
                        "llamacpp": 8080, "localai": 8080, "ipex-llm": 8010,
                        "ipexllm": 8010, "sglang": 30000}
        service_checks["LLM Runtime (host)"] = rt_ports_map.get(runtime, 11434)

    health_results = {}
    for svc_idx, (svc, port) in enumerate(service_checks.items()):
        alive = _check_port(port)
        health_results[svc] = "healthy" if alive else "starting"
        icon = "OK" if alive else "WAIT"
        _update_deploy(
            80 + svc_idx,
            f"  [{icon}] {svc:25s} :{port}  {'healthy' if alive else 'initializing'}",
        )

    healthy_count = sum(1 for s in health_results.values() if s == "healthy")
    total_count = len(health_results)
    _update_deploy(90, "")
    _update_deploy(90, f"  Result: {healthy_count}/{total_count} services responding")
    if healthy_count < total_count:
        _update_deploy(91, "  Note: Some services may still be starting inside the container")

    # ── Step 10/10: Save claw config + summary ──────────────────────
    _update_deploy(93, "")
    _update_deploy(93, "━━━ Step 10/10: Deployment summary ━━━")

    # Save claw config for cluster management
    claw_config = {
        "id": f"claw_{platform}_{int(time.time())}",
        "name": agent_name,
        "platform": platform,
        "container_name": container_name,
        "container_id": container_id,
        "image": image_name,
        "agent_port": agent_port,
        "gateway_port": gateway_port,
        "optimizer_port": optimizer_port,
        "watchdog_port": watchdog_port,
        "llm_provider": llm_provider,
        "runtime": runtime,
        "security_enabled": security_enabled,
        "security_features": security_features,
        "selected_models": selected_models,
        "strategy": strategy_cfg if strategy_cfg else None,
        "cloud_providers": cloud_providers,
        "gateway": gateway_cfg,
        "storage": storage_config,
        "channels": channels_cfg,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "running" if container_status == "running" else container_status,
    }
    _save_claw(claw_config)
    _update_deploy(94, f"  Claw config saved to data/claws/{claw_config['id']}.json")

    # Build endpoint list (use actual allocated ports, not defaults)
    endpoints = {
        f"Agent ({platform})": f"http://localhost:{agent_port}",
        "Agent Dashboard": f"http://localhost:{agent_port}/show",
        "Gateway Router": f"http://localhost:{gateway_port}",
        "Optimizer": f"http://localhost:{optimizer_port}",
        "Watchdog": f"http://localhost:{watchdog_port}",
    }
    if llm_provider in ("local", "hybrid"):
        endpoints["LLM Runtime"] = f"http://localhost:{rt_ports_map.get(runtime, 11434)}"

    _update_deploy(95, f"  Container:   {container_name} ({container_id})")
    _update_deploy(95, f"  Image:       {image_name}")
    _update_deploy(95, f"  Network:     xclaw-net")
    _update_deploy(96, f"  Agent:       {agent_name} ({platform}) on :{agent_port}")
    _update_deploy(96, f"  Services:    {healthy_count}/{total_count} healthy")
    if security_enabled:
        _update_deploy(97, f"  Security:    inbound + outbound ACTIVE")
    _update_deploy(97, f"  Optimizer:   11 pre-call + 2 post-call rules")
    _update_deploy(98, f"  Flow: Client -> Security -> Gateway(:{gateway_port}) -> Optimizer(:{optimizer_port})")
    _update_deploy(98, f"        -> Agent(:{agent_port}) -> LLM -> Optimizer(post) -> Security(out) -> Client")
    _update_deploy(99, "")
    _update_deploy(99, f"  docker logs -f {container_name}")
    _update_deploy(99, f"  docker exec -it {container_name} bash")
    _update_deploy(99, f"  curl http://localhost:{agent_port}/health")
    _update_deploy(
        100,
        f"Deployment complete — container '{container_name}' running with {healthy_count}/{total_count} services",
        state="complete",
        extra={"health": health_results, "endpoints": endpoints, "container": container_name, "container_id": container_id},
    )


# =========================================================================
#  Storage / Data Management helpers
# =========================================================================
_storage_manager = None
_dal_instance = None


def _get_dal():
    """Lazy-initialize the DAL singleton (preferred over raw StorageManager)."""
    global _dal_instance
    if _dal_instance is None:
        try:
            from claw_dal import DAL
            _dal_instance = DAL.get_instance()
        except (ImportError, RuntimeError, OSError):
            pass
    return _dal_instance


def _get_storage_manager():
    """Lazy-initialize the StorageManager singleton."""
    global _storage_manager
    if _storage_manager is None:
        try:
            from claw_storage import StorageManager
            _storage_manager = StorageManager()
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _storage_manager = mod.StorageManager()
    return _storage_manager


def _load_storage_config() -> Dict[str, Any]:
    """Load storage configuration from disk."""
    if STORAGE_CONFIG_FILE.exists():
        try:
            return json.loads(STORAGE_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "engine": "sqlite",
        "instance_db": {"engine": "sqlite", "path": str(PROJECT_ROOT / "data" / "instance.db")},
        "shared_db": {"enabled": False, "engine": "sqlite", "path": str(PROJECT_ROOT / "data" / "shared" / "shared.db")},
    }


def _save_storage_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Save storage configuration to disk."""
    STORAGE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    STORAGE_CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    global _storage_manager
    _storage_manager = None  # reset so next access reloads config
    return {"success": True, "message": "Storage config saved"}


def _test_storage_connection(config: Dict[str, Any]) -> Dict[str, Any]:
    """Test a storage connection and return result."""
    try:
        mgr = _get_storage_manager()
        return mgr.test_connection(config)
    except (ImportError, RuntimeError, OSError, ValueError, KeyError) as e:
        return {"success": False, "message": str(e), "latency_ms": 0}


def _check_postgres_readiness(config: Dict[str, Any]) -> Dict[str, Any]:
    """Full readiness check for PostgreSQL:
      1) Is psycopg2 installed (or can it be auto-installed)?
      2) Is a PostgreSQL server reachable at the configured host:port?
      3) Can we actually connect with the given credentials?
    Returns a structured result the frontend can act on."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    host = config.get("host", "localhost")
    port = int(config.get("port", 5432))

    # 1) psycopg2
    driver_ok = mod.ensure_psycopg2()

    # 2) Server reachable
    server_ok = mod.check_postgres_server(host, port)

    # 3) Credential test (only if driver + server both OK)
    connect_ok = False
    connect_msg = ""
    db_exists = False
    if driver_ok and server_ok:
        try:
            result = mod.StorageManager.test_connection(config)
            connect_ok = result.get("success", False)
            connect_msg = result.get("message", "")
            db_exists = result.get("db_exists", connect_ok)
        except (OSError, RuntimeError, ImportError) as e:
            connect_msg = str(e)

    # Check Docker availability (passive — auto-install happens in _setup_postgres_docker)
    docker_available = False
    try:
        rc, _, _ = _run_cmd(["docker", "info"], timeout=5)
        docker_available = rc == 0
    except (subprocess.SubprocessError, OSError):
        pass

    return {
        "driver_installed": driver_ok,
        "server_reachable": server_ok,
        "connection_ok": connect_ok,
        "connection_message": connect_msg,
        "db_exists": db_exists,
        "docker_available": docker_available,
        "host": host,
        "port": port,
        "ready": driver_ok and server_ok and connect_ok,
    }


def _setup_postgres_docker(config: Dict[str, Any]) -> Dict[str, Any]:
    """Start a PostgreSQL container using the docker-compose postgres profile."""
    user = config.get("user", "xclaw")
    password = config.get("password", "xclaw")
    dbname = config.get("dbname", "xclaw")
    port = int(config.get("port", 5432))

    # Ensure Docker is installed and running (auto-install/launch if needed)
    import platform as _plat
    docker_msgs: List[str] = []
    docker_ok, docker_summary = _auto_docker(
        _plat.system(), log_fn=lambda m: docker_msgs.append(m)
    )
    if not docker_ok:
        return {
            "success": False,
            "message": f"Docker unavailable: {docker_summary}",
            "docker_log": docker_msgs,
        }

    compose_file = PROJECT_ROOT / "docker-compose.yml"
    if not compose_file.exists():
        return {"success": False, "message": "docker-compose.yml not found in project root."}

    # Set env vars for the postgres service
    env = os.environ.copy()
    env["CLAW_POSTGRES_USER"] = user
    env["CLAW_POSTGRES_PASSWORD"] = password
    env["CLAW_POSTGRES_DB"] = dbname
    env["CLAW_POSTGRES_PORT"] = str(port)

    log(f"Starting PostgreSQL container (port {port}, user={user}, db={dbname})...")

    # docker compose --profile postgres up -d
    rc, out, stderr = _run_cmd(
        ["docker", "compose", "-f", str(compose_file), "--profile", "postgres", "up", "-d"],
        timeout=120,
        env=env,
    )
    if rc != 0:
        # Try older docker-compose command
        rc, out, stderr = _run_cmd(
            ["docker-compose", "-f", str(compose_file), "--profile", "postgres", "up", "-d"],
            timeout=120,
            env=env,
        )

    if rc != 0:
        return {
            "success": False,
            "message": f"Failed to start PostgreSQL container: {stderr or out}",
        }

    # Wait for it to become healthy (up to 30 seconds)
    import importlib.util
    spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for attempt in range(15):
        time.sleep(2)
        if mod.check_postgres_server("localhost", port):
            # Give it another second for auth to be ready
            time.sleep(1)
            log(f"PostgreSQL container is ready on :{port}")
            return {
                "success": True,
                "message": f"PostgreSQL started via Docker on port {port}",
                "host": "localhost",
                "port": port,
                "user": user,
                "dbname": dbname,
            }

    return {
        "success": False,
        "message": "PostgreSQL container started but is not responding yet. Check `docker logs` for details.",
    }


def _create_postgres_database(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a PostgreSQL database if it doesn't exist.
    Connects to the 'postgres' maintenance DB to issue CREATE DATABASE."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not mod.ensure_psycopg2():
        return {"success": False, "message": "psycopg2 driver not available"}

    host = config.get("host", "localhost")
    port = int(config.get("port", 5432))
    user = config.get("user", "xclaw")
    password = config.get("password", "")
    dbname = config.get("dbname", "xclaw")

    try:
        import psycopg2
        # Connect to the default 'postgres' maintenance database
        conn = psycopg2.connect(host=host, port=port, dbname="postgres", user=user, password=password)
        conn.autocommit = True
        cur = conn.cursor()

        # Check if database already exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone():
            conn.close()
            return {"success": True, "message": f"Database '{dbname}' already exists"}

        # Create the database
        cur.execute(f'CREATE DATABASE "{dbname}" OWNER "{user}"')
        conn.close()
        log(f"Created PostgreSQL database '{dbname}' on {host}:{port}")
        return {"success": True, "message": f"Database '{dbname}' created successfully"}
    except Exception as e:  # Broad catch: psycopg2 exception types not importable at module level
        return {"success": False, "message": str(e)}


def _get_data_overview() -> Dict[str, Any]:
    """Get metadata for all configured databases."""
    try:
        mgr = _get_storage_manager()
        dbs = mgr.get_all_databases_info()
        total_tables = sum(d.get("table_count", 0) for d in dbs)
        total_size = sum(
            d.get("health", {}).get("size_bytes", 0) for d in dbs if "health" in d
        )
        return {
            "databases": dbs,
            "total_databases": len(dbs),
            "total_tables": total_tables,
            "total_size_bytes": total_size,
        }
    except (ImportError, RuntimeError, OSError) as e:
        return {"databases": [], "error": str(e)}


def _get_data_tables(db_name: str) -> Dict[str, Any]:
    """List tables in a specific database."""
    try:
        mgr = _get_storage_manager()
        if db_name == "shared":
            db = mgr.get_shared_db()
            if db is None:
                return {"tables": [], "error": "Shared database is disabled"}
        else:
            db = mgr.get_instance_db()

        tables = db.get_tables()
        table_details = []
        for t in tables:
            cols = db.table_info(t)
            count_row = db.fetchone(f"SELECT count(*) AS cnt FROM {t}")
            row_count = count_row["cnt"] if count_row else 0
            table_details.append({
                "name": t,
                "columns": cols,
                "row_count": row_count,
            })
        return {"tables": table_details, "db": db_name}
    except (ImportError, RuntimeError, OSError, KeyError) as e:
        return {"tables": [], "error": str(e)}


def _query_data(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a safe read-only SELECT query with validation."""
    db_name = params.get("db", "instance")
    table = params.get("table", "")
    limit = min(int(params.get("limit", 50)), 500)
    offset = int(params.get("offset", 0))
    search = params.get("search", "")

    try:
        mgr = _get_storage_manager()
        if db_name == "shared":
            db = mgr.get_shared_db()
            if db is None:
                return {"rows": [], "error": "Shared database is disabled"}
        else:
            db = mgr.get_instance_db()

        # Validate table name against actual tables
        valid_tables = db.get_tables()
        if table not in valid_tables:
            return {"rows": [], "error": f"Table '{table}' not found"}

        # Build safe parameterized query
        if search:
            # Search across all text columns
            cols = db.table_info(table)
            text_cols = [c["name"] for c in cols if "text" in c.get("type", "").lower() or "char" in c.get("type", "").lower()]
            if text_cols:
                conditions = " OR ".join(f"{c} LIKE ?" for c in text_cols)
                search_param = f"%{search}%"
                sql = f"SELECT * FROM {table} WHERE {conditions} LIMIT ? OFFSET ?"
                query_params = tuple([search_param] * len(text_cols) + [limit, offset])
            else:
                sql = f"SELECT * FROM {table} LIMIT ? OFFSET ?"
                query_params = (limit, offset)
        else:
            sql = f"SELECT * FROM {table} LIMIT ? OFFSET ?"
            query_params = (limit, offset)

        rows = db.fetchall(sql, query_params)
        count_row = db.fetchone(f"SELECT count(*) AS cnt FROM {table}")
        total = count_row["cnt"] if count_row else 0

        return {"rows": rows, "total": total, "table": table, "db": db_name}
    except (ImportError, RuntimeError, OSError, KeyError, ValueError) as e:
        return {"rows": [], "error": str(e)}


def _get_data_health() -> Dict[str, Any]:
    """Get health metrics for all databases."""
    try:
        mgr = _get_storage_manager()
        return mgr.get_health_all()
    except (ImportError, RuntimeError, OSError) as e:
        return {"error": str(e)}


def _get_rbac() -> Dict[str, Any]:
    """Get RBAC configuration."""
    try:
        mgr = _get_storage_manager()
        db = mgr.get_shared_db()
        if db is None:
            return {"roles": [], "assignments": [], "enabled": False}

        from claw_storage import RBACManager
        rbac = RBACManager(db)
        return {
            "enabled": True,
            "roles": rbac.list_roles(),
            "assignments": rbac.list_assignments(),
        }
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mgr = _get_storage_manager()
        db = mgr.get_shared_db()
        if db is None:
            return {"roles": [], "assignments": [], "enabled": False}
        rbac = mod.RBACManager(db)
        return {
            "enabled": True,
            "roles": rbac.list_roles(),
            "assignments": rbac.list_assignments(),
        }
    except (RuntimeError, OSError, AttributeError) as e:
        return {"roles": [], "assignments": [], "error": str(e)}


def _save_rbac(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update RBAC assignments."""
    try:
        mgr = _get_storage_manager()
        db = mgr.get_shared_db()
        if db is None:
            return {"success": False, "error": "Shared database is disabled"}

        import importlib.util
        spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rbac = mod.RBACManager(db)

        agent_id = data.get("agent_id", "")
        role_id = data.get("role_id", "")
        if not agent_id or not role_id:
            return {"success": False, "error": "agent_id and role_id are required"}

        result = rbac.assign_role(agent_id, role_id, data.get("assigned_by", "dashboard"))
        return result
    except (ImportError, RuntimeError, OSError, KeyError) as e:
        return {"success": False, "error": str(e)}


def _export_database(db_name: str) -> Optional[str]:
    """Export a database as JSON string."""
    try:
        mgr = _get_storage_manager()
        if db_name == "shared":
            db = mgr.get_shared_db()
            if db is None:
                return None
        else:
            db = mgr.get_instance_db()

        tables = db.get_tables()
        export_data: Dict[str, Any] = {"exported_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
        for t in tables:
            rows = db.fetchall(f"SELECT * FROM {t}")
            export_data["tables"][t] = rows
        return json.dumps(export_data, indent=2, default=str)
    except (ImportError, RuntimeError, OSError, KeyError):
        return None


# Port management helpers

def _get_docker_occupied_ports() -> set:
    """Query Docker for all host-mapped ports from running containers."""
    occupied = set()
    try:
        rc, out, _ = _run_cmd(
            ["docker", "ps", "--format", "{{.Ports}}"],
            timeout=10,
        )
        if rc == 0 and out:
            # Format examples: "0.0.0.0:3121->3100/tcp, :::3121->3100/tcp"
            for line in out.strip().splitlines():
                for mapping in line.split(","):
                    mapping = mapping.strip()
                    # Extract host port from "host:port->container/proto"
                    m = re.search(r":(\d+)->", mapping)
                    if m:
                        occupied.add(int(m.group(1)))
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return occupied


def _get_config_occupied_ports() -> set:
    """Read all saved claw configs and extract their declared ports."""
    occupied = set()
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    for f in CLAWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Skip configs marked as removed/stopped — their ports are reclaimable
            status = data.get("status", "")
            if status in ("removed", "stopped"):
                continue
            for key in ("agent_port", "gateway_port", "optimizer_port", "watchdog_port",
                        "agent", "gateway", "optimizer", "watchdog"):
                val = data.get(key)
                if isinstance(val, int) and val > 0:
                    occupied.add(val)
        except (json.JSONDecodeError, OSError):
            pass
    return occupied


def _get_all_occupied_ports() -> set:
    """Gather all in-use ports from Docker, TCP probes on known ranges, and saved configs."""
    occupied = set()

    # 1. Docker container port mappings
    occupied |= _get_docker_occupied_ports()

    # 2. Saved claw configs (for non-docker / remote deploys)
    occupied |= _get_config_occupied_ports()

    # 3. TCP probe on the common port ranges (agent 3100-3199, gateway 9095-9195,
    #    optimizer 9091-9191, watchdog 9090-9190, parlant 8800-8899)
    #    Only probe a focused set to keep startup fast.
    probe_ranges = list(range(3100, 3200)) + list(range(8800, 8900)) + list(range(9090, 9200))
    for port in probe_ranges:
        if port in occupied:
            continue
        if _check_port(port):
            occupied.add(port)

    return occupied


def _cleanup_stale_claws() -> int:
    """Mark dead claw configs as removed/stopped so their ports can be reclaimed.
    Returns the number of configs updated."""
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    updated = 0

    # Get set of actually running Docker containers
    running_containers: set = set()
    try:
        rc, out, _ = _run_cmd(
            ["docker", "ps", "--format", "{{.Names}}"],
            timeout=10,
        )
        if rc == 0 and out:
            running_containers = {name.strip() for name in out.strip().splitlines() if name.strip()}
    except (subprocess.SubprocessError, OSError):
        pass

    for f in sorted(CLAWS_DIR.glob("*.json")):
        fname = f.name
        # Skip port-allocation files (e.g. zeroclaw_0_ports.json)
        if fname.endswith("_ports.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Already marked dead — skip
        if data.get("status") in ("removed", "stopped"):
            continue

        container_name = data.get("container_name", "")
        agent_port = data.get("agent_port", 0)

        is_alive = False
        if container_name:
            # Check if Docker container exists and is running
            if container_name in running_containers:
                is_alive = True
            else:
                # Double-check via docker inspect (container may be paused/restarting)
                try:
                    rc, out, _ = _run_cmd(
                        ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                        timeout=5,
                    )
                    if rc == 0 and out.strip() in ("running", "restarting", "paused"):
                        is_alive = True
                except (subprocess.SubprocessError, OSError):
                    pass

        # For non-docker or as fallback: TCP port probe
        if not is_alive and agent_port:
            is_alive = _check_port(agent_port)

        if not is_alive:
            old_status = data.get("status", "unknown")
            if container_name and container_name not in running_containers:
                # Check if container exists at all (exited vs truly removed)
                try:
                    rc2, out2, _ = _run_cmd(
                        ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                        timeout=5,
                    )
                    if rc2 != 0:
                        data["status"] = "removed"
                    else:
                        data["status"] = "stopped"
                except (subprocess.SubprocessError, OSError):
                    data["status"] = "stopped"
            else:
                data["status"] = "stopped"

            if data["status"] != old_status:
                f.write_text(json.dumps(data, indent=2), encoding="utf-8")
                updated += 1
                log(f"Stale claw '{data.get('name', fname)}' marked as {data['status']}")

    # Clean up orphan port files whose corresponding claw config no longer exists
    # or whose claw is dead
    active_claw_ids = set()
    for f in CLAWS_DIR.glob("claw_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") not in ("removed", "stopped"):
                active_claw_ids.add(data.get("platform", "") + "_" + str(data.get("id", "")))
        except (json.JSONDecodeError, OSError):
            pass

    for pf in CLAWS_DIR.glob("*_ports.json"):
        # Port files like "zeroclaw_5_ports.json" — check if any active claw references these ports
        try:
            port_data = json.loads(pf.read_text(encoding="utf-8"))
            agent_p = port_data.get("agent", 0)
            # If this agent port isn't occupied by a running service, the port file is stale
            if agent_p and not _check_port(agent_p):
                pf.unlink()
                updated += 1
                log(f"Removed stale port file: {pf.name}")
        except (json.JSONDecodeError, OSError):
            pass

    return updated


def _find_free_port(preferred: int, range_start: int, range_end: int) -> int:
    """Find a free port, starting with preferred, then scanning the range."""
    for port in [preferred] + list(range(range_start, range_end)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result != 0:  # port is free
                return port
        except OSError:
            pass
        finally:
            sock.close()
    return preferred  # fallback


def _allocate_ports_for_claw(platform: str) -> Dict[str, int]:
    """Allocate unique ports for a new claw instance.

    Smart allocation: scans Docker containers, TCP ports, and saved configs
    to find the first truly-free port in each range.  Dead containers' ports
    are automatically reclaimed after stale-config cleanup.
    """
    # Clean up stale configs first so dead ports are reclaimable
    cleaned = _cleanup_stale_claws()
    if cleaned:
        log(f"Cleaned up {cleaned} stale claw config(s) / port file(s)")

    # Gather every port that is actually in use right now
    occupied = _get_all_occupied_ports()
    log(f"Port scan: {len(occupied)} ports in use")

    platform_defaults = {
        "zeroclaw": 3100, "nanoclaw": 3200, "picoclaw": 3300,
        "openclaw": 3400, "parlant": 8800,
    }
    base_port = platform_defaults.get(platform, 3100)

    def _first_free(range_start: int, range_end: int) -> int:
        """Return the first port in [range_start, range_end) not in occupied."""
        for p in range(range_start, range_end):
            if p not in occupied:
                return p
        # Fallback: use _find_free_port which does live TCP probe
        return _find_free_port(range_start, range_start, range_end)

    agent_port = _first_free(base_port, base_port + 100)
    gateway_port = _first_free(9095, 9195)
    optimizer_port = _first_free(9091, 9191)
    watchdog_port = _first_free(9090, 9190)

    # Mark these as occupied immediately so concurrent deploys don't collide
    occupied.update({agent_port, gateway_port, optimizer_port, watchdog_port})

    ports = {
        "agent": agent_port,
        "gateway": gateway_port,
        "optimizer": optimizer_port,
        "watchdog": watchdog_port,
    }

    # Save port allocation (use agent_port as unique key instead of stale offset)
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    port_file = CLAWS_DIR / f"{platform}_{agent_port}_ports.json"
    port_file.write_text(json.dumps(ports, indent=2), encoding="utf-8")
    log(f"Allocated ports for {platform}: agent={agent_port}, gw={gateway_port}, opt={optimizer_port}, wd={watchdog_port}")

    return ports


# =========================================================================
#  HTTP Request Handler
# =========================================================================
class WizardAPIHandler(BaseHTTPRequestHandler):
    """Handles JSON API requests for the React wizard frontend."""

    server_version = "ClawWizardAPI/1.0"

    # ----- helpers --------------------------------------------------------

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def log_message(self, fmt, *args) -> None:  # noqa: N802
        log(f"{self.client_address[0]} {fmt % args}")

    # ----- OPTIONS (CORS preflight) ---------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ----- GET routes -----------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/api/wizard/platforms":
            self._json_response({"platforms": PLATFORMS})

        elif path == "/api/wizard/hardware":
            self._json_response(_detect_hardware())

        elif path == "/api/wizard/models":
            self._json_response(_get_models())

        elif path == "/api/wizard/runtimes":
            self._json_response({"runtimes": _get_runtimes()})

        elif path == "/api/wizard/adapters":
            self._json_response({"adapters": _get_adapters()})

        elif path == "/api/wizard/status":
            with _deploy_lock:
                status = dict(_deploy_status)
            self._json_response(status)

        elif path == "/api/wizard/security-rules":
            self._json_response({"categories": _get_security_rule_categories()})

        elif path == "/api/wizard/security-rules/detail":
            self._json_response(_get_security_rules_detail())

        # ── Dashboard GET routes ──────────────────────────────────
        elif path == "/api/dashboard/agents":
            self._json_response({"agents": _get_all_agents_status()})

        elif path == "/api/dashboard/status":
            agents = _get_all_agents_status()
            running = sum(1 for a in agents if a["status"] == "running")
            self._json_response({
                "agents_total": len(agents),
                "agents_running": running,
                "agents": agents,
                "services": {
                    "gateway": _check_port(9095),
                    "optimizer": _check_port(9091),
                    "watchdog": _check_port(9090),
                    "wizard": True,
                },
            })

        elif path == "/api/dashboard/strategy":
            data = _read_json_file(STRATEGY_FILE)
            if data:
                self._json_response(data)
            else:
                self._json_response({"routes": [], "note": "strategy.json not found"})

        elif path == "/api/dashboard/security":
            self._json_response({"categories": _get_security_rule_categories()})

        elif path == "/api/dashboard/config":
            self._json_response({"config": _read_env_redacted()})

        elif path == "/api/dashboard/hardware":
            self._json_response(_detect_hardware())

        elif path == "/api/dashboard/costs":
            self._json_response(_read_billing_data())

        elif path == "/api/dashboard/triggers":
            self._json_response(_load_triggers())

        elif path == "/api/dashboard/instances":
            self._json_response(_load_instances())

        elif path.startswith("/api/dashboard/instances/") and path.endswith("/status"):
            inst_id = path.split("/")[4]
            instances = _load_instances()
            inst = next((i for i in instances.get("instances", []) if i.get("id") == inst_id), None)
            if inst:
                self._json_response(_check_instance_health(inst))
            else:
                self._json_response({"error": "Instance not found"}, status=404)

        elif path == "/api/dashboard/metrics":
            self._json_response(_get_dashboard_metrics())

        elif path == "/api/dashboard/logs":
            with _log_buffer_lock:
                entries = list(_log_buffer)
            self._json_response({"logs": entries})

        elif path == "/api/dashboard/claws":
            self._json_response({"claws": _load_claws()})

        # ── Storage / Data Management GET routes ──────────────────
        elif path == "/api/wizard/storage":
            self._json_response(_load_storage_config())

        elif path == "/api/wizard/storage/check-postgres":
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            pg_config = {
                "engine": "postgresql",
                "host": qs.get("host", ["localhost"])[0],
                "port": int(qs.get("port", ["5432"])[0]),
                "dbname": qs.get("dbname", ["xclaw"])[0],
                "user": qs.get("user", ["xclaw"])[0],
                "password": qs.get("password", [""])[0],
            }
            self._json_response(_check_postgres_readiness(pg_config))

        elif path == "/api/dashboard/data":
            self._json_response(_get_data_overview())

        elif path.startswith("/api/dashboard/data/tables"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            db_name = qs.get("db", ["instance"])[0]
            self._json_response(_get_data_tables(db_name))

        elif path == "/api/dashboard/data/health":
            self._json_response(_get_data_health())

        elif path == "/api/dashboard/data/rbac":
            self._json_response(_get_rbac())

        else:
            self._json_response({"error": "Not found", "path": path}, status=404)

    # ----- POST routes ----------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/api/wizard/validate":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"valid": False, "errors": ["Invalid JSON"]}, status=400)
                return
            self._json_response(_validate_assessment(body))

        elif path == "/api/wizard/channels/test":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "message": "Invalid JSON"}, status=400)
                return
            channel_id = body.get("channel", "")
            config = body.get("config", {})
            result = _test_channel(channel_id, config)
            status_code = 200 if result.get("success") else 400
            self._json_response(result, status=status_code)

        elif path == "/api/wizard/security-rules":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_security_rules(body))

        elif path == "/api/wizard/compliance":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_compliance(body))

        elif path == "/api/wizard/deploy":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"error": "Invalid JSON"}, status=400)
                return

            # Validate first
            validation = _validate_assessment(body)
            if not validation["valid"]:
                self._json_response({"error": "Validation failed", "details": validation}, status=400)
                return

            # Check not already running
            with _deploy_lock:
                if _deploy_status.get("state") == "running":
                    self._json_response({"error": "Deployment already in progress"}, status=409)
                    return

            # Start deploy in background, stream SSE
            assessment_json = json.dumps(body, indent=2)
            thread = threading.Thread(target=_run_deploy, args=(assessment_json,), daemon=True)
            thread.start()

            # SSE response
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self._cors_headers()
            self.end_headers()

            log_cursor = 0
            while True:
                with _deploy_lock:
                    status = dict(_deploy_status)
                    all_logs = list(status.get("logs", []))

                # Send every new log line as a separate SSE event
                new_logs = all_logs[log_cursor:]
                if new_logs:
                    for log_line in new_logs:
                        event_data = {
                            "step": log_line,
                            "progress": status["progress"],
                            "status": status["state"],
                        }
                        if "health" in status:
                            event_data["health"] = status["health"]
                        if "endpoints" in status:
                            event_data["endpoints"] = status["endpoints"]
                        try:
                            self.wfile.write(f"data: {json.dumps(event_data)}\n\n".encode("utf-8"))
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            break
                    log_cursor = len(all_logs)

                # Detect dead deploy thread (crashed despite try/except wrapper)
                if not thread.is_alive() and status["state"] == "running":
                    status["state"] = "error"
                    status["message"] = "Deploy thread died unexpectedly"
                    with _deploy_lock:
                        _deploy_status["state"] = "error"
                        _deploy_status["message"] = status["message"]

                if status["state"] in ("complete", "error"):
                    final = {
                        "status": status["state"],
                        "progress": status["progress"],
                        "message": status["message"],
                    }
                    if "health" in status:
                        final["health"] = status["health"]
                    if "endpoints" in status:
                        final["endpoints"] = status["endpoints"]
                    try:
                        self.wfile.write(f"data: {json.dumps(final)}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    break
                time.sleep(0.3)

        # ── Dashboard POST routes ─────────────────────────────────
        elif path.startswith("/api/dashboard/agents/"):
            # POST /api/dashboard/agents/{id}/{start|stop|restart}
            parts = path.rstrip("/").split("/")
            if len(parts) >= 6:
                agent_id = parts[4]
                action = parts[5]
                if action in ("start", "stop", "restart"):
                    result = _agent_action(agent_id, action)
                    self._json_response(result, status=200 if result.get("success") else 400)
                else:
                    self._json_response({"error": f"Unknown action: {action}"}, status=400)
            else:
                self._json_response({"error": "Invalid path"}, status=400)

        elif path == "/api/dashboard/triggers":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_triggers(body))

        elif path == "/api/dashboard/triggers/test":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            fired = _evaluate_trigger(body)
            result = {}
            if fired:
                result = _execute_trigger_action(body, "Manual test fire")
            self._json_response({"fired": fired, "result": result})

        elif path == "/api/dashboard/instances":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_instances(body))

        elif path.startswith("/api/dashboard/instances/") and path.endswith("/delete"):
            inst_id = path.split("/")[4]
            instances = _load_instances()
            instances["instances"] = [i for i in instances.get("instances", []) if i.get("id") != inst_id]
            self._json_response(_save_instances(instances))

        elif path == "/api/dashboard/channels/status":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            ch_config = _load_channel_config()
            results = {}
            for ch_id, ch_data in ch_config.get("channels", {}).items():
                test_result = _test_channel(ch_id, ch_data)
                results[ch_id] = {
                    "configured": True,
                    "status": "connected" if test_result.get("success") else "error",
                    "message": test_result.get("message", ""),
                }
            self._json_response({"channels": results, "fallback_chain": ch_config.get("fallback_chain", [])})

        elif path == "/api/dashboard/channels/config":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_channel_config(body))

        elif path == "/api/dashboard/security/toggle":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            rule_id = body.get("rule_id", "")
            enabled = body.get("enabled", True)
            self._json_response(_toggle_security_rule(rule_id, enabled))

        elif path == "/api/dashboard/claws":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_claw(body))

        elif path.startswith("/api/dashboard/claws/") and path.endswith("/delete"):
            claw_id = path.split("/")[4]
            self._json_response(_delete_claw(claw_id))

        # ── Storage / Data Management POST routes ─────────────────
        elif path == "/api/wizard/storage":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_storage_config(body))

        elif path == "/api/wizard/storage/test":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_test_storage_connection(body))

        elif path == "/api/wizard/storage/setup-postgres":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            mode = body.get("mode", "docker")
            pg_config = body.get("config", {})
            if mode == "docker":
                self._json_response(_setup_postgres_docker(pg_config))
            else:
                # Local install — we only auto-install the driver
                import importlib.util
                spec = importlib.util.spec_from_file_location("claw_storage", SCRIPT_DIR / "claw_storage.py")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                driver_ok = mod.ensure_psycopg2()
                if driver_ok:
                    self._json_response({
                        "success": True,
                        "message": "psycopg2 driver installed. Please install and start PostgreSQL on your system, then test the connection.",
                        "driver_installed": True,
                    })
                else:
                    self._json_response({
                        "success": False,
                        "message": "Could not install psycopg2 driver automatically. Run: pip install psycopg2-binary",
                        "driver_installed": False,
                    })

        elif path == "/api/wizard/storage/create-database":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_create_postgres_database(body))

        elif path == "/api/dashboard/data/query":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_query_data(body))

        elif path == "/api/dashboard/data/rbac":
            raw = self._read_body()
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._json_response({"success": False, "error": "Invalid JSON"}, status=400)
                return
            self._json_response(_save_rbac(body))

        elif path.startswith("/api/dashboard/data/export"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            db_name = qs.get("db", ["instance"])[0]
            export_str = _export_database(db_name)
            if export_str:
                body_bytes = export_str.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Disposition", f'attachment; filename="{db_name}_export.json"')
                self._cors_headers()
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)
            else:
                self._json_response({"error": "Export failed or database not found"}, status=404)

        else:
            self._json_response({"error": "Not found", "path": path}, status=404)


# =========================================================================
#  Threaded HTTP Server
# =========================================================================
class ThreadedWizardServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrency."""
    daemon_threads = True
    allow_reuse_address = True


# =========================================================================
#  Start / Stop helpers
# =========================================================================
def start_server(port: int = 9098) -> ThreadedWizardServer:
    """Start the wizard API server and write PID file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadedWizardServer(("0.0.0.0", port), WizardAPIHandler)
    pid = os.getpid()
    PID_FILE.write_text(str(pid), encoding="utf-8")

    log(f"{BOLD}Wizard API server starting on port {port}{NC}")
    log(f"PID {pid} written to {PID_FILE}")
    log(f"Endpoints available at {CYAN}http://localhost:{port}/api/wizard/*{NC}")
    return server


def stop_server() -> None:
    """Stop a running wizard API server by reading its PID file."""
    if not PID_FILE.exists():
        err("No PID file found -- server may not be running")
        sys.exit(1)

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        err("Invalid PID file")
        sys.exit(1)

    try:
        os.kill(pid, signal.SIGTERM)
        log(f"Sent SIGTERM to PID {pid}")
    except ProcessLookupError:
        warn(f"Process {pid} not found -- already stopped?")
    except PermissionError:
        err(f"Permission denied sending signal to PID {pid}")
        sys.exit(1)
    finally:
        try:
            PID_FILE.unlink()
        except OSError:
            pass


# =========================================================================
#  CLI Entry Point
# =========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claw Wizard API -- React frontend backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", action="store_true", help="Start the API server")
    parser.add_argument("--stop", action="store_true", help="Stop a running API server")
    parser.add_argument("--port", type=int, default=9098, help="Server port (default: 9098)")
    args = parser.parse_args()

    if args.stop:
        stop_server()
        return

    if args.start:
        server = start_server(port=args.port)

        # Start trigger engine
        global _trigger_engine
        _trigger_engine = TriggerEngine(interval=30)
        _trigger_engine.start()

        # Seed initial log entries
        _append_log("info", "Wizard API started", "system")
        _append_log("info", "Dashboard endpoints available at /api/dashboard/*", "system")
        _append_log("info", "Trigger engine started (30s interval)", "triggers")

        def _shutdown(signum, frame):
            log("Shutting down...")
            if _trigger_engine:
                _trigger_engine.stop()
            server.shutdown()
            try:
                PID_FILE.unlink()
            except OSError:
                pass
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            _shutdown(None, None)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
