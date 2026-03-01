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
        elif path == "/":
            self._json({
                "name": AGENT_NAME,
                "version": "1.0.0",
                "framework": "xclaw-stub",
                "endpoints": ["/health", "/v1/chat/completions", "/v1/models"],
            })
        else:
            self._json({"error": "Not found"}, 404)

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
