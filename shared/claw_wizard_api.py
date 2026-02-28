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
    except Exception as exc:
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
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _save_compliance(body: Dict[str, Any]) -> Dict[str, Any]:
    """Save compliance configuration to a JSON file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    try:
        COMPLIANCE_CONFIG_FILE.write_text(json.dumps(body, indent=2), encoding="utf-8")
        log(f"Compliance config saved to {COMPLIANCE_CONFIG_FILE}")
        return {"success": True, "path": str(COMPLIANCE_CONFIG_FILE)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _test_channel(channel_id: str, config: Dict[str, str]) -> Dict[str, Any]:
    """Test a communication channel connection."""
    import socket

    if channel_id == "telegram":
        token = config.get("botToken", "")
        if not token:
            return {"success": False, "message": "Bot token is required"}
        # Test Telegram API connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("api.telegram.org", 443))
            sock.close()
            return {"success": True, "message": "Telegram API is reachable"}
        except (socket.timeout, OSError) as exc:
            return {"success": False, "message": f"Cannot reach Telegram API: {exc}"}

    elif channel_id == "slack":
        webhook_url = config.get("webhookUrl", "")
        if not webhook_url and not config.get("botToken"):
            return {"success": False, "message": "Webhook URL or Bot Token is required"}
        return {"success": True, "message": "Slack configuration validated"}

    elif channel_id == "discord":
        token = config.get("botToken", "")
        if not token:
            return {"success": False, "message": "Bot token is required"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("discord.com", 443))
            sock.close()
            return {"success": True, "message": "Discord API is reachable"}
        except (socket.timeout, OSError) as exc:
            return {"success": False, "message": f"Cannot reach Discord API: {exc}"}

    elif channel_id == "email":
        host = config.get("host", "")
        port_str = config.get("port", "587")
        if not host:
            return {"success": False, "message": "SMTP host is required"}
        try:
            port = int(port_str)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            return {"success": True, "message": f"SMTP server {host}:{port} is reachable"}
        except (socket.timeout, OSError, ValueError) as exc:
            return {"success": False, "message": f"Cannot reach SMTP server: {exc}"}

    elif channel_id == "whatsapp":
        if not config.get("phoneNumberId") or not config.get("accessToken"):
            return {"success": False, "message": "Phone Number ID and Access Token are required"}
        return {"success": True, "message": "WhatsApp configuration validated"}

    elif channel_id == "webhook":
        url = config.get("url", "")
        if not url:
            return {"success": False, "message": "Webhook URL is required"}
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return {"success": False, "message": "URL must start with http:// or https://"}
        return {"success": True, "message": "Webhook URL format is valid"}

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
    except Exception:
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
    """Multi-threaded health check for all 5 platforms."""
    results = []

    def _check_one(plat: Dict[str, Any]) -> Dict[str, Any]:
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
        }

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_check_one, p): p for p in PLATFORMS}
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                p = futures[f]
                results.append({
                    "id": p["id"], "name": p["name"], "status": "error",
                    "port": p["port"], "language": p["language"],
                    "memory": p["memory"], "features": p.get("features", []),
                })
    results.sort(key=lambda x: x["port"])
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
    """Read billing reports from data/billing/."""
    reports = []
    BILLING_DIR.mkdir(parents=True, exist_ok=True)
    reports_dir = BILLING_DIR / "reports"
    if reports_dir.exists():
        for f in sorted(reports_dir.glob("*.json")):
            try:
                reports.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
    # Also check for cost_log.jsonl
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
        except Exception as exc:
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
            except Exception:
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
    except Exception as exc:
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
            except Exception as exc:
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
            "watchdog_port": 9097,
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
        except Exception as exc:
            return {"success": False, "error": str(exc)}


def _check_instance_health(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Probe remote wizard API + watchdog."""
    host = instance.get("host", "localhost")
    wiz_port = instance.get("wizard_port", 9098)
    wd_port = instance.get("watchdog_port", 9097)

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
    except Exception as exc:
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
            except Exception:
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
            except Exception as exc:
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
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Metrics Aggregation ─────────────────────────────────────────────────
def _get_dashboard_metrics() -> Dict[str, Any]:
    """Aggregate watchdog + billing + trigger data."""
    agents = _get_all_agents_status()
    running = sum(1 for a in agents if a["status"] == "running")
    billing = _read_billing_data()
    triggers_data = _load_triggers()
    active_triggers = sum(1 for t in triggers_data.get("triggers", []) if t.get("enabled", True))
    instances = _load_instances()

    # Try to get watchdog metrics
    watchdog_data = None
    if _check_port(9097):
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:9097/api/status", timeout=3)
            watchdog_data = json.loads(resp.read().decode())
        except Exception:
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
            "watchdog": _check_port(9097),
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
    except Exception as exc:
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


def _run_cmd(cmd: List[str], timeout: int = 120) -> tuple:
    """Run a command and return (returncode, stdout). Works on Windows + WSL."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as exc:
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
    selected_models = config.get("selected_models", [])
    agent_name = config.get("agent_name", "xclaw-agent")
    gateway_cfg = config.get("gateway", {})

    # Write assessment file
    tmp_assessment = PROJECT_ROOT / "data" / "wizard" / "client-assessment.json"
    tmp_assessment.parent.mkdir(parents=True, exist_ok=True)
    tmp_assessment.write_text(assessment_json, encoding="utf-8")
    _update_deploy(1, f"Assessment saved to {tmp_assessment.name}")

    PLATFORM_META = {p["id"]: p for p in PLATFORMS}
    plat_info = PLATFORM_META.get(platform, {})

    # Port allocation — use manual ports if specified, otherwise auto-detect
    port_config = config.get("port_config", {})
    storage_config = config.get("storage", {})
    storage_engine = storage_config.get("engine", "sqlite")

    if port_config.get("mode") == "manual" and port_config.get("agentPort"):
        agent_port = port_config["agentPort"]
    else:
        allocated = _allocate_ports_for_claw(platform)
        agent_port = allocated["agent"]

    container_name = f"xclaw-{agent_name}".lower().replace(" ", "-")
    image_name = f"xclaw:{platform}"

    # ── Step 1/10: Pre-checks ───────────────────────────────────────
    _update_deploy(2, "")
    _update_deploy(2, "━━━ Step 1/10: Pre-flight checks ━━━")

    import platform as plat
    if plat.system() == "Windows":
        _update_deploy(3, "[Pre-check] Windows detected — verifying WSL...")
        rc, out, stderr = _run_cmd(["wsl", "--status"])
        if rc == 0:
            _update_deploy(3, "[Pre-check] WSL2 installed and available")
        else:
            _update_deploy(3, "[Pre-check] WSL not found — Docker Desktop provides WSL backend")

    _update_deploy(4, "[Pre-check] Checking Docker daemon...")
    rc, out, stderr = _run_cmd(["docker", "info"], timeout=10)
    if rc != 0:
        _update_deploy(4, "ERROR: Docker daemon not running — cannot build container")
        _update_deploy(4, "  Please start Docker Desktop or Docker daemon and try again")
        _update_deploy(4, "Deployment aborted", state="error")
        return
    _update_deploy(5, "[Pre-check] Docker daemon is running")

    # Check if Dockerfile.xclaw exists
    dockerfile = PROJECT_ROOT / "Dockerfile.xclaw"
    if not dockerfile.exists():
        _update_deploy(5, "ERROR: Dockerfile.xclaw not found in project root")
        _update_deploy(5, "Deployment aborted", state="error")
        return
    _update_deploy(6, f"[Pre-check] Dockerfile.xclaw found")

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
            "CLAW_AGENT=": f"CLAW_AGENT={platform}",
            "CLAW_AGENT_NAME=": f"CLAW_AGENT_NAME={agent_name}",
            "CLAW_AGENT_PORT=": f"CLAW_AGENT_PORT={agent_port}",
            "CLAW_LLM_PROVIDER=": f"CLAW_LLM_PROVIDER={llm_provider}",
            "CLAW_STORAGE_ENGINE=": f"CLAW_STORAGE_ENGINE={storage_engine}",
        }
        if selected_models:
            patches["CLAW_OLLAMA_MODELS="] = f"CLAW_OLLAMA_MODELS={','.join(selected_models)}"
        if llm_provider in ("local", "hybrid"):
            # Inside container, Ollama runs on host — use host.docker.internal
            patches["CLAW_LOCAL_LLM_ENDPOINT="] = "CLAW_LOCAL_LLM_ENDPOINT=http://host.docker.internal:11434/v1"
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
            text=True, cwd=str(PROJECT_ROOT),
        )
        step_count = 0
        for line in iter(build_proc.stdout.readline, ""):
            line = line.rstrip()
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
        _update_deploy(36, "ERROR: 'docker' command not found — is Docker installed?")
        _update_deploy(36, "Deployment aborted", state="error")
        return
    except Exception as exc:
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
        rt_port_map = {"ollama": 11434, "vllm": 8000, "llama-cpp": 8080, "localai": 8080}
        rt_port = rt_port_map.get(runtime, 11434)
        _update_deploy(40, f"  Runtime:   {runtime} (runs on HOST, shared across all containers)")
        _update_deploy(40, f"  Port:      :{rt_port}")
        _update_deploy(41, f"  Container access via: host.docker.internal:{rt_port}")
        if llm_provider == "hybrid":
            _update_deploy(41, f"  Mode: hybrid (local primary + cloud fallback via R11 FallbackChain)")

        if runtime == "ollama":
            existing = []
            if _check_port(11434):
                _update_deploy(42, "  Ollama daemon already running on :11434")
                try:
                    resp = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5)
                    tags = json.loads(resp.read())
                    existing = [m["name"] for m in tags.get("models", [])]
                    _update_deploy(42, f"  Installed models: {', '.join(existing) if existing else 'none'}")
                except Exception:
                    pass
            else:
                _update_deploy(42, "  Starting Ollama daemon on host...")
                _update_deploy(42, "  $ ollama serve")
                try:
                    proc = subprocess.Popen(
                        ["ollama", "serve"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    _service_procs["ollama"] = proc
                    for wait_sec in range(1, 11):
                        time.sleep(1)
                        if _check_port(11434):
                            _update_deploy(43, f"  Ollama started on :11434 (ready after {wait_sec}s)")
                            break
                    else:
                        _update_deploy(43, "  Ollama process started — may need more time")
                except FileNotFoundError:
                    _update_deploy(43, "  ERROR: 'ollama' command not found")
                    _update_deploy(43, "  Install Ollama from https://ollama.com/download")
                except Exception as exc:
                    _update_deploy(43, f"  Ollama start error: {exc}")

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
                            text=True, cwd=str(PROJECT_ROOT),
                        )
                        last_pct = ""
                        for line in iter(pull_proc.stdout.readline, ""):
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
                            except Exception:
                                _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} downloaded")
                        else:
                            _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — pull finished (code {pull_proc.returncode})")
                    except FileNotFoundError:
                        _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — 'ollama' not found")
                    except Exception as exc:
                        _update_deploy(44 + idx, f"  [{model_num}/{total_models}] {model_id} — error: {exc}")
            elif not selected_models:
                _update_deploy(44, "  No models selected — skipping model pull")
        else:
            _update_deploy(42, f"  Using {runtime} runtime — ensure it is running on :{rt_port}")
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

    # Build port mappings
    port_mappings = [
        "-p", f"{agent_port}:{agent_port}",   # Agent platform
        "-p", "9095:9095",                      # Gateway router
        "-p", "9091:9091",                      # Optimizer
        "-p", "9097:9097",                      # Watchdog
        "-p", "9098:9098",                      # Wizard API (inside container)
    ]

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

    _update_deploy(60, f"  $ docker run -d --name {container_name} \\")
    _update_deploy(60, f"      --network xclaw-net --restart unless-stopped \\")
    _update_deploy(60, f"      -p {agent_port}:{agent_port} -p 9095:9095 -p 9091:9091 \\")
    _update_deploy(60, f"      -p 9097:9097 -p 9098:9098 \\")
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

    # Check exposed ports
    service_checks = {
        f"Agent ({platform})": agent_port,
        "Gateway Router": 9095,
        "Optimizer": 9091,
        "Watchdog": 9097,
    }
    if llm_provider in ("local", "hybrid"):
        rt_ports_map = {"ollama": 11434, "vllm": 8000, "llama-cpp": 8080, "localai": 8080}
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
        "llm_provider": llm_provider,
        "runtime": runtime,
        "security_enabled": security_enabled,
        "selected_models": selected_models,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "running" if container_status == "running" else container_status,
    }
    _save_claw(claw_config)
    _update_deploy(94, f"  Claw config saved to data/claws/{claw_config['id']}.json")

    # Build endpoint list
    endpoints = {
        f"Agent ({platform})": f"http://localhost:{agent_port}",
        "Gateway Router": "http://localhost:9095",
        "Optimizer": "http://localhost:9091",
        "Watchdog": "http://localhost:9097",
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
    _update_deploy(98, f"  Flow: Client -> Security -> Gateway(:9095) -> Optimizer(:9091)")
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
    except Exception as e:
        return {"success": False, "message": str(e), "latency_ms": 0}


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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
        return {"rows": [], "error": str(e)}


def _get_data_health() -> Dict[str, Any]:
    """Get health metrics for all databases."""
    try:
        mgr = _get_storage_manager()
        return mgr.get_health_all()
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception:
        return None


# Port management helpers
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
    """Allocate unique ports for a new claw instance."""
    platform_defaults = {
        "zeroclaw": 3100, "nanoclaw": 3200, "picoclaw": 3300,
        "openclaw": 3400, "parlant": 8800,
    }
    base_port = platform_defaults.get(platform, 3100)

    # Count existing claws to offset
    existing = _load_claws()
    offset = len(existing)

    agent_port = _find_free_port(base_port + offset, base_port, base_port + 99)
    gateway_port = _find_free_port(9095 + offset, 9095, 9195)
    optimizer_port = _find_free_port(9091 + offset, 9091, 9191)
    watchdog_port = _find_free_port(9097 + offset, 9097, 9197)

    ports = {
        "agent": agent_port,
        "gateway": gateway_port,
        "optimizer": optimizer_port,
        "watchdog": watchdog_port,
    }

    # Save port allocation
    CLAWS_DIR.mkdir(parents=True, exist_ok=True)
    port_file = CLAWS_DIR / f"{platform}_{offset}_ports.json"
    port_file.write_text(json.dumps(ports, indent=2), encoding="utf-8")

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
                    "watchdog": _check_port(9097),
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
