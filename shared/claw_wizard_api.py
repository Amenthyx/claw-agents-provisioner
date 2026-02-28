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
import json
import os
import signal
import subprocess
import sys
import threading
import time
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


def _run_deploy(assessment_json: str) -> None:
    """Run claw.sh deploy in a background thread, updating _deploy_status."""
    global _deploy_status

    with _deploy_lock:
        _deploy_status = {"state": "running", "progress": 0, "message": "Starting deployment..."}

    # Write temporary assessment file
    tmp_assessment = PROJECT_ROOT / "data" / "wizard" / "client-assessment.json"
    tmp_assessment.parent.mkdir(parents=True, exist_ok=True)
    tmp_assessment.write_text(assessment_json, encoding="utf-8")

    try:
        cmd = ["bash", str(CLAW_SH), "deploy", "--assessment", str(tmp_assessment)]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT), text=True,
        )

        step_count = 0
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            step_count += 1
            progress = min(95, step_count * 5)
            with _deploy_lock:
                _deploy_status = {"state": "running", "progress": progress, "message": line}

        proc.wait()
        with _deploy_lock:
            if proc.returncode == 0:
                _deploy_status = {"state": "complete", "progress": 100, "message": "Deployment complete"}
            else:
                _deploy_status = {
                    "state": "error", "progress": _deploy_status["progress"],
                    "message": f"Deploy exited with code {proc.returncode}",
                }
    except FileNotFoundError:
        with _deploy_lock:
            _deploy_status = {"state": "error", "progress": 0, "message": "claw.sh not found"}
    except Exception as exc:
        with _deploy_lock:
            _deploy_status = {"state": "error", "progress": 0, "message": str(exc)}


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

            last_msg = ""
            while True:
                with _deploy_lock:
                    status = dict(_deploy_status)
                current_msg = status.get("message", "")
                if current_msg != last_msg:
                    event_data = json.dumps({
                        "step": status["message"],
                        "progress": status["progress"],
                        "status": status["state"],
                    })
                    try:
                        self.wfile.write(f"data: {event_data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    last_msg = current_msg
                if status["state"] in ("complete", "error"):
                    # Send final event
                    final = json.dumps({
                        "status": status["state"],
                        "progress": status["progress"],
                        "message": status["message"],
                    })
                    try:
                        self.wfile.write(f"data: {final}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    break
                time.sleep(0.5)

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

        def _shutdown(signum, frame):
            log("Shutting down...")
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
