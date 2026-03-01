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
  - Agent Fleet Overview   — real-time health of all 5 platforms (HTTP ping)
  - Multi-Agent Management — start / stop / restart agents via claw.sh
  - Model Strategy View    — strategy.json routing table + regeneration
  - Hardware Profile       — detected CPU, RAM, GPU from hardware_profile.json
  - Fine-Tuning Manager    — browse 50 adapters, view training status
  - Security Dashboard     — security scan summary, link to run scan
  - Cost Analytics         — billing data from data/billing/
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
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

DEFAULT_PORT = 9099
HEALTH_TIMEOUT = 2  # seconds

# Agent platform definitions
AGENT_PLATFORMS: List[Dict[str, Any]] = [
    {"id": "zeroclaw",  "name": "ZeroClaw",  "lang": "Rust",       "port": 3100, "memory": "512 MB"},
    {"id": "nanoclaw",  "name": "NanoClaw",  "lang": "TypeScript", "port": 3200, "memory": "1 GB"},
    {"id": "picoclaw",  "name": "PicoClaw",  "lang": "Go",         "port": 3300, "memory": "128 MB"},
    {"id": "openclaw",  "name": "OpenClaw",  "lang": "Node.js",    "port": 3400, "memory": "4 GB"},
    {"id": "parlant",   "name": "Parlant",   "lang": "Python",     "port": 8800, "memory": "2 GB"},
]

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


def get_all_agents_status() -> List[Dict[str, Any]]:
    """Return status for all agent platforms.

    Tries DAL first (cached 10s) for fast reads, falls back to HTTP pings.
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
            return results
    except Exception:
        pass

    # Fallback: HTTP ping each agent
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

    return results


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
        </div>

        <!-- Models Tab -->
        <div class="tab-content" id="tab-models">
            <div class="section-title">Model Strategy Routing</div>
            <div class="section-desc">Task routing from strategy.json. Shows which model handles each task type.</div>
            <button class="btn btn-accent" onclick="regenerateStrategy()" id="btn-regen">Regenerate Strategy</button>
            <div id="models-content"><div class="loading">Loading strategy...</div></div>
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
            <div class="section-desc">Security rules and scan results for the agent fleet.</div>
            <div id="security-content"><div class="loading">Loading security data...</div></div>
        </div>

        <!-- Costs Tab -->
        <div class="tab-content" id="tab-costs">
            <div class="section-title">Cost Analytics</div>
            <div class="section-desc">API usage costs across local and cloud models.</div>
            <div id="costs-content"><div class="loading">Loading billing data...</div></div>
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
        document.querySelectorAll('.nav-item').forEach(function(el) { el.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
        document.querySelector('[data-tab="' + tab + '"]').classList.add('active');
        document.getElementById('tab-' + tab).classList.add('active');
        currentTab = tab;

        if (tab === 'fleet') loadFleet();
        else if (tab === 'models') loadModels();
        else if (tab === 'hardware') loadHardware();
        else if (tab === 'finetuning') loadAdapters();
        else if (tab === 'security') loadSecurity();
        else if (tab === 'costs') loadCosts();
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
        apiGet('/api/agents').then(function(agents) {
            var c = document.getElementById('fleet-cards');
            if (!agents || !agents.length) { c.innerHTML = '<div class="loading">No agents configured.</div>'; return; }
            var running = agents.filter(function(a) { return a.status === 'running'; }).length;
            document.getElementById('global-status-text').textContent = running + '/' + agents.length + ' Online';
            var dot = document.getElementById('global-status-dot');
            dot.className = 'status-dot ' + (running > 0 ? 'online' : 'offline');

            var html = '';
            agents.forEach(function(a) {
                var isRunning = a.status === 'running';
                html += '<div class="card">' +
                    '<div class="card-header"><span class="card-title">' + a.name + '</span>' +
                    '<span class="card-badge ' + (isRunning ? 'badge-running' : 'badge-stopped') + '">' +
                    a.status + '</span></div>' +
                    '<div class="card-body">' +
                    '<div class="row"><span>Language</span><span>' + a.lang + '</span></div>' +
                    '<div class="row"><span>Port</span><span>' + a.port + '</span></div>' +
                    '<div class="row"><span>Memory</span><span>' + a.memory + '</span></div>' +
                    '</div>' +
                    '<div class="card-actions">' +
                    '<button class="btn btn-start" onclick="agentAction(\'' + a.id + '\',\'start\')"' +
                    (isRunning ? ' disabled' : '') + '>Start</button>' +
                    '<button class="btn btn-stop" onclick="agentAction(\'' + a.id + '\',\'stop\')"' +
                    (!isRunning ? ' disabled' : '') + '>Stop</button>' +
                    '<button class="btn btn-restart" onclick="agentAction(\'' + a.id + '\',\'restart\')">Restart</button>' +
                    '</div></div>';
            });
            c.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('fleet-cards').innerHTML = '<div class="loading">Error loading fleet: ' + e.message + '</div>';
        });
    }

    window.agentAction = function(id, action) {
        showToast('Sending ' + action + ' to ' + id + '...', 'success');
        apiPost('/api/agents/' + id + '/' + action).then(function(r) {
            if (r.success) showToast(id + ' ' + action + ' successful', 'success');
            else showToast(id + ' ' + action + ' failed: ' + (r.error || 'unknown'), 'error');
            setTimeout(loadFleet, 1500);
        }).catch(function(e) { showToast('Error: ' + e.message, 'error'); });
    };

    // --- Models Tab ---
    function loadModels() {
        apiGet('/api/strategy').then(function(data) {
            var el = document.getElementById('models-content');
            if (!data || data.error) { el.innerHTML = '<div class="loading">No strategy.json found. Click Regenerate.</div>'; return; }
            var routing = data.task_routing || {};
            var keys = Object.keys(routing);
            if (!keys.length) { el.innerHTML = '<div class="loading">No task routing configured.</div>'; return; }

            var html = '<table class="data-table"><thead><tr><th>Task Type</th><th>Primary Model</th>' +
                '<th>Provider</th><th>Type</th><th>Score</th><th>Fallback</th></tr></thead><tbody>';
            keys.forEach(function(k) {
                var r = routing[k];
                var p = r.primary || {};
                var f = r.fallback || {};
                html += '<tr><td style="color:var(--text-primary);font-weight:600">' + k + '</td>' +
                    '<td>' + (p.model || '-') + '</td><td>' + (p.provider || '-') + '</td>' +
                    '<td>' + (p.type || '-') + '</td><td>' + (p.score != null ? p.score.toFixed(1) : '-') + '</td>' +
                    '<td>' + (f.model || '-') + '</td></tr>';
            });
            html += '</tbody></table>';

            if (data.monthly_cost_estimate) {
                var c = data.monthly_cost_estimate;
                html += '<div style="margin-top:16px;font-size:13px;color:var(--text-secondary)">' +
                    'Monthly cost estimate: $' + (c.min || 0).toFixed(2) + ' - $' + (c.max || 0).toFixed(2) +
                    ' <span style="color:var(--text-secondary);font-size:11px">(' + (c.note || '') + ')</span></div>';
            }
            el.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('models-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

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
        apiGet('/api/security').then(function(data) {
            var el = document.getElementById('security-content');
            if (!data || data.error) { el.innerHTML = '<div class="loading">No security rules found.</div>'; return; }
            var domains = data.domains || data;
            var keys = Object.keys(domains);
            var html = '<div class="cards-grid">';
            keys.forEach(function(k) {
                var val = domains[k];
                var count = 0;
                if (Array.isArray(val)) count = val.length;
                else if (typeof val === 'object' && val !== null) count = Object.keys(val).length;
                html += '<div class="card"><div class="card-header"><span class="card-title">' +
                    k.replace(/_/g, ' ').replace(/\\b\\w/g, function(l){ return l.toUpperCase(); }) +
                    '</span><span class="card-badge badge-running">' + count + ' rules</span></div>' +
                    '<div class="card-body"><pre style="font-size:11px;color:var(--text-secondary);' +
                    'max-height:150px;overflow:auto;white-space:pre-wrap">' +
                    JSON.stringify(val, null, 2).substring(0, 500) + '</pre></div></div>';
            });
            html += '</div>';
            el.innerHTML = html;
        }).catch(function(e) {
            document.getElementById('security-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

    // --- Costs Tab ---
    function loadCosts() {
        apiGet('/api/billing').then(function(data) {
            var el = document.getElementById('costs-content');
            if (!data) { el.innerHTML = '<div class="loading">No billing data available.</div>'; return; }

            var html = '<div class="cards-grid">';
            html += '<div class="card"><div class="hw-stat"><div class="value">' +
                (data.total_records || 0) + '</div><div class="label">Total Usage Records</div></div></div>';

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
        }).catch(function(e) {
            document.getElementById('costs-content').innerHTML = '<div class="loading">Error: ' + e.message + '</div>';
        });
    }

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

    // --- Auto-refresh fleet every 5 seconds ---
    function startPolling() {
        if (fleetInterval) clearInterval(fleetInterval);
        fleetInterval = setInterval(function() {
            if (currentTab === 'fleet') loadFleet();
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

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging in favor of custom output."""
        pass

    # ----- Response Helpers -----

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
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

    # ----- GET Routes -----

    def do_GET(self) -> None:
        """Route GET requests."""
        path = self.path.split("?")[0]  # Strip query string

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

        elif path.startswith("/wizard/"):
            self._handle_wizard_static(path)

        else:
            self._send_not_found()

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

    # ----- POST Routes -----

    def do_POST(self) -> None:
        """Route POST requests."""
        path = self.path.split("?")[0]

        if path == "/api/strategy/generate":
            self._handle_post_strategy_generate()

        elif path == "/api/finetune":
            self._handle_post_finetune()

        elif "/api/agents/" in path:
            self._handle_post_agent_action(path)

        else:
            self._send_not_found()

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
