#!/usr/bin/env python3
"""
Claw Agent Stub — Lightweight agent HTTP service for xClaw ecosystem.

Provides OpenAI-compatible /v1/chat/completions proxy and health endpoint.
Used when the full agent binary is not available (e.g. during development
or when upstream packages haven't been built yet).

The stub forwards LLM requests to the configured backend (Ollama, cloud API)
through the xClaw gateway router, ensuring the full pipeline works:
  Client -> Security -> Gateway -> Optimizer -> Agent (this) -> LLM

Usage:
  python3 shared/claw_agent_stub.py --port 3100 --name zeroclaw
  python3 shared/claw_agent_stub.py --port 3400 --name openclaw

Stdlib only — no external dependencies.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict

AGENT_NAME = os.environ.get("CLAW_AGENT", "xclaw-agent")
LLM_ENDPOINT = os.environ.get("CLAW_LOCAL_LLM_ENDPOINT", "http://host.docker.internal:11434/v1")
PROVIDER = os.environ.get("CLAW_LLM_PROVIDER", "local")
START_TIME = time.time()


class AgentHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible agent proxy."""

    server_version = f"ClawAgent/{AGENT_NAME}"

    def _json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path in ("/health", "/api/health"):
            uptime = int(time.time() - START_TIME)
            self._json({
                "status": "healthy",
                "agent": AGENT_NAME,
                "uptime_seconds": uptime,
                "provider": PROVIDER,
                "llm_endpoint": LLM_ENDPOINT,
            })
        elif path == "/v1/models":
            self._json({
                "object": "list",
                "data": [{
                    "id": "claw-agent",
                    "object": "model",
                    "owned_by": "xclaw",
                }],
            })
        elif path in ("/show", "/dashboard"):
            self._serve_dashboard()
        elif path == "/":
            self._json({
                "name": AGENT_NAME,
                "version": "1.0.0",
                "framework": "xclaw-stub",
                "endpoints": ["/health", "/v1/chat/completions", "/v1/models", "/show"],
            })
        else:
            self._json({"error": "Not found"}, 404)

    def _serve_dashboard(self) -> None:
        """Serve a built-in agent dashboard at /show."""
        uptime = int(time.time() - START_TIME)
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h}h {m}m {s}s"
        agent_port = os.environ.get("CLAW_AGENT_PORT", "3100")
        gateway_port = os.environ.get("CLAW_GATEWAY_PORT", "9095")
        optimizer_port = os.environ.get("CLAW_OPTIMIZER_PORT", "9091")
        watchdog_port = os.environ.get("CLAW_WATCHDOG_PORT", "9090")
        storage_engine = os.environ.get("CLAW_STORAGE_ENGINE", "sqlite")
        security_enabled = os.environ.get("CLAW_SECURITY_ENABLED", "true")
        dashboard_port = os.environ.get("CLAW_DASHBOARD_PORT", "9099")
        strategy_opt = os.environ.get("CLAW_STRATEGY_OPTIMIZATION", "balanced")
        models_env = os.environ.get("CLAW_OLLAMA_MODELS", "")
        models_list = [m.strip() for m in models_env.split(",") if m.strip()] if models_env else []

        # Fetch live model list from Ollama
        live_models = []
        try:
            req = urllib.request.urlopen(f"{LLM_ENDPOINT.rsplit('/v1', 1)[0]}/api/tags", timeout=3)
            data = json.loads(req.read())
            live_models = [m["name"] for m in data.get("models", [])]
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, KeyError):
            live_models = models_list or ["(unavailable)"]

        models_html = "".join(f'<span class="badge">{m}</span>' for m in live_models)

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{AGENT_NAME} — XClaw Agent Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}}
.header{{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border-bottom:1px solid #2a2a4a;padding:24px 32px;display:flex;align-items:center;gap:16px}}
.logo{{width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#00d4aa,#00a884);display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;color:#0a0a0f}}
.header h1{{font-size:20px;font-weight:600}} .header .sub{{font-size:13px;color:#a0a0a0;margin-left:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;padding:24px 32px}}
.card{{background:#16213e;border:1px solid #2a2a4a;border-radius:12px;padding:20px}}
.card h2{{font-size:14px;color:#a0a0a0;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px}}
.stat{{font-size:28px;font-weight:700;color:#00d4aa}} .stat-label{{font-size:12px;color:#a0a0a0;margin-top:4px}}
.row{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #1a1a2e}}
.row:last-child{{border:none}}
.row .label{{color:#a0a0a0;font-size:13px}} .row .value{{font-size:13px;font-weight:500}}
.badge{{display:inline-block;background:#1a1a2e;border:1px solid #2a2a4a;border-radius:6px;padding:4px 10px;margin:3px;font-size:12px;font-family:monospace}}
.status{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px}}
.status.ok{{background:#2ed573}} .status.warn{{background:#ffa502}} .status.err{{background:#ff4757}}
.services{{list-style:none}} .services li{{padding:8px 0;border-bottom:1px solid #1a1a2e;font-size:13px;display:flex;align-items:center}}
.services li:last-child{{border:none}}
a{{color:#00d4aa;text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body>
<div class="header">
  <div class="logo">X</div>
  <div><h1>{AGENT_NAME}</h1><p style="font-size:13px;color:#a0a0a0">XClaw Agent Platform</p></div>
  <span class="sub">Uptime: {uptime_str}</span>
</div>
<div class="grid">
  <div class="card">
    <h2>Agent Info</h2>
    <div class="row"><span class="label">Name</span><span class="value">{AGENT_NAME}</span></div>
    <div class="row"><span class="label">Port</span><span class="value">:{agent_port}</span></div>
    <div class="row"><span class="label">Provider</span><span class="value">{PROVIDER}</span></div>
    <div class="row"><span class="label">LLM Endpoint</span><span class="value" style="font-size:11px;font-family:monospace">{LLM_ENDPOINT}</span></div>
    <div class="row"><span class="label">Storage</span><span class="value">{storage_engine}</span></div>
    <div class="row"><span class="label">Security</span><span class="value">{'Active' if security_enabled == 'true' else 'Disabled'}</span></div>
    <div class="row"><span class="label">Strategy</span><span class="value">{strategy_opt}</span></div>
  </div>
  <div class="card">
    <h2>Services</h2>
    <ul class="services" id="svc-list">
      <li><span class="status" id="s-agent"></span>Agent Platform <span style="margin-left:auto;font-family:monospace;font-size:12px">:{agent_port}</span></li>
      <li><span class="status" id="s-gateway"></span>Gateway Router <span style="margin-left:auto;font-family:monospace;font-size:12px">:{gateway_port}</span></li>
      <li><span class="status" id="s-optimizer"></span>Optimizer <span style="margin-left:auto;font-family:monospace;font-size:12px">:{optimizer_port}</span></li>
      <li><span class="status" id="s-watchdog"></span>Watchdog <span style="margin-left:auto;font-family:monospace;font-size:12px">:{watchdog_port}</span></li>
      <li><span class="status" id="s-ollama"></span>LLM Runtime <span style="margin-left:auto;font-family:monospace;font-size:12px">:11434</span></li>
      <li><span class="status" id="s-dashboard"></span>Dashboard <span style="margin-left:auto;font-family:monospace;font-size:12px">:{dashboard_port}</span></li>
    </ul>
  </div>
  <div class="card">
    <h2>Loaded Models</h2>
    <div style="margin-top:8px">{models_html if models_html else '<span style="color:#a0a0a0;font-size:13px">No models loaded</span>'}</div>
  </div>
  <div class="card">
    <h2>Quick Links</h2>
    <div class="row"><span class="label">Health</span><a href="/health">/health</a></div>
    <div class="row"><span class="label">Chat API</span><a href="/v1/chat/completions">/v1/chat/completions</a></div>
    <div class="row"><span class="label">Models</span><a href="/v1/models">/v1/models</a></div>
    <div class="row"><span class="label">Fleet Dashboard</span><a href="http://localhost:{dashboard_port}">:{dashboard_port}</a></div>
    <div class="row"><span class="label">Gateway</span><a href="http://localhost:{gateway_port}/health">:{gateway_port}</a></div>
  </div>
</div>
<script>
async function check(id,port){{try{{const r=await fetch('http://localhost:'+port+'/health',{{mode:'no-cors',signal:AbortSignal.timeout(2000)}});document.getElementById(id).className='status ok'}}catch{{document.getElementById(id).className='status err'}}}}
check('s-agent',{agent_port});check('s-gateway',{gateway_port});check('s-optimizer',{optimizer_port});check('s-watchdog',{watchdog_port});
fetch('http://localhost:11434/api/tags',{{mode:'no-cors',signal:AbortSignal.timeout(2000)}}).then(()=>document.getElementById('s-ollama').className='status ok').catch(()=>document.getElementById('s-ollama').className='status err');
fetch('http://localhost:{dashboard_port}/',{{mode:'no-cors',signal:AbortSignal.timeout(2000)}}).then(()=>document.getElementById('s-dashboard').className='status ok').catch(()=>document.getElementById('s-dashboard').className='status err');
setInterval(()=>{{check('s-agent',{agent_port});check('s-gateway',{gateway_port});check('s-optimizer',{optimizer_port});check('s-watchdog',{watchdog_port})}},10000);
</script></body></html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = self.path.split("?")[0]

        if path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"

            try:
                request = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "Invalid JSON"}, 400)
                return

            # Forward to LLM backend
            try:
                llm_url = f"{LLM_ENDPOINT}/chat/completions"
                req = urllib.request.Request(
                    llm_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                    self._json(result)
            except (urllib.error.URLError, urllib.error.HTTPError, Exception) as exc:
                # Fallback: return a stub response
                model = request.get("model", "claw-agent")
                messages = request.get("messages", [])
                last_msg = messages[-1]["content"] if messages else ""
                self._json({
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"[{AGENT_NAME}] Agent received your message. "
                                       f"LLM backend ({LLM_ENDPOINT}) returned: {exc}. "
                                       f"Please ensure Ollama or your LLM runtime is running.",
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": len(last_msg) // 4, "completion_tokens": 20, "total_tokens": 25},
                })
        else:
            self._json({"error": "Not found"}, 404)

    def log_message(self, fmt, *args) -> None:
        sys.stdout.write(f"[{AGENT_NAME}] {fmt % args}\n")
        sys.stdout.flush()


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    global AGENT_NAME
    parser = argparse.ArgumentParser(description="Claw Agent Stub")
    parser.add_argument("--port", type=int, default=3100)
    parser.add_argument("--name", type=str, default=AGENT_NAME)
    args = parser.parse_args()

    AGENT_NAME = args.name

    server = ThreadedServer(("0.0.0.0", args.port), AgentHandler)
    print(f"[{AGENT_NAME}] Agent stub listening on :{args.port}")
    print(f"[{AGENT_NAME}] LLM endpoint: {LLM_ENDPOINT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{AGENT_NAME}] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
