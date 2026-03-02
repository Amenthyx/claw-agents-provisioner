#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER -- Centralized Port Management
=============================================================================
Single source of truth for all service port assignments.  Resolves ports via
environment variable overrides, default values, and automatic free-port
scanning within a per-service range when the default is busy.

Features:
  - Central registry of every service and its default port
  - Environment variable overrides (reads CLAW_*_PORT vars)
  - Automatic free-port fallback within a configured range
  - Thread-safe caching so each service resolves exactly once
  - JSON port-map persistence for multi-process coordination
  - CLI for operators: --show, --check, --save

Usage:
  python3 shared/claw_ports.py --show          # print port assignment table
  python3 shared/claw_ports.py --check         # check which ports are in use
  python3 shared/claw_ports.py --save          # save resolved map to JSON

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi -- linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

# =========================================================================
#  Constants
# =========================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT_MAP_PATH = str(PROJECT_ROOT / "data" / "port_map.json")

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

# =========================================================================
#  Logging
# =========================================================================

logger = logging.getLogger("claw-ports")

# =========================================================================
#  Service Port Registry
# =========================================================================

SERVICE_PORTS: Dict[str, Dict] = {
    "zeroclaw":     {"default": 3100,  "env": "CLAW_ZEROCLAW_PORT",      "range": (3100, 3199)},
    "nanoclaw":     {"default": 3200,  "env": "CLAW_NANOCLAW_PORT",      "range": (3200, 3299)},
    "picoclaw":     {"default": 3300,  "env": "CLAW_PICOCLAW_PORT",      "range": (3300, 3399)},
    "openclaw":     {"default": 3400,  "env": "CLAW_OPENCLAW_PORT",      "range": (3400, 3499)},
    "parlant":      {"default": 8800,  "env": "CLAW_PARLANT_PORT",       "range": (8800, 8899)},
    "watchdog":     {"default": 9090,  "env": "CLAW_WATCHDOG_PORT",      "range": (9090, 9094)},
    "optimizer":    {"default": 9091,  "env": "CLAW_OPTIMIZER_PORT",     "range": (9091, 9094)},
    "health":       {"default": 9094,  "env": "CLAW_HEALTH_PORT",        "range": (9094, 9094)},
    "router":       {"default": 9095,  "env": "CLAW_GATEWAY_PORT",       "range": (9095, 9095)},
    "memory":       {"default": 9096,  "env": "CLAW_MEMORY_PORT",        "range": (9096, 9096)},
    "rag":          {"default": 9097,  "env": "CLAW_RAG_PORT",           "range": (9097, 9097)},
    "wizard":       {"default": 9098,  "env": "CLAW_WIZARD_PORT",        "range": (9098, 9098)},
    "dashboard":    {"default": 9099,  "env": "CLAW_DASHBOARD_PORT",     "range": (9099, 9099)},
    "orchestrator": {"default": 9100,  "env": "CLAW_ORCHESTRATOR_PORT",  "range": (9100, 9100)},
    "ollama":       {"default": 11434, "env": "CLAW_OLLAMA_PORT",        "range": (11434, 11434)},
}

# =========================================================================
#  Port Resolution
# =========================================================================

_cache: Dict[str, int] = {}
_lock = threading.Lock()


def is_port_free(port: int) -> bool:
    """Check if a TCP port is available on localhost.

    Attempts to connect to the port.  If the connection is refused (nobody
    listening) the port is free.  A successful connection means something is
    already bound there.  This approach works reliably across platforms
    (Windows SO_REUSEADDR allows re-bind, making bind-based checks
    unreliable).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex(("127.0.0.1", port))
            # 0 means connection succeeded -> port is in use
            return result != 0
    except OSError:
        # Any OS-level error means we cannot connect -> treat as free
        return True


def find_free_port(service: str) -> int:
    """Resolve a port for *service* without caching.

    Resolution order:
      1. Environment variable override (e.g. CLAW_WATCHDOG_PORT=9092)
      2. Default port if it is currently free
      3. First free port in the configured range

    Raises ``RuntimeError`` if the service is unknown or no free port is
    found within the allowed range.
    """
    if service not in SERVICE_PORTS:
        raise RuntimeError(f"Unknown service: {service!r}")

    cfg = SERVICE_PORTS[service]

    # 1. Env-var override (trust operator, return as-is)
    env_val = os.environ.get(cfg["env"])
    if env_val is not None:
        try:
            return int(env_val)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid port in %s=%r, falling back to default",
                cfg["env"], env_val,
            )

    # 2. Default port
    default = cfg["default"]
    if is_port_free(default):
        return default

    # 3. Range scan
    lo, hi = cfg["range"]
    for port in range(lo, hi + 1):
        if port == default:
            continue  # already checked
        if is_port_free(port):
            logger.info(
                "Default port %d for %s is busy, using %d instead",
                default, service, port,
            )
            return port

    raise RuntimeError(
        f"No free port for {service!r} in range {lo}-{hi} "
        f"(default {default} also busy)"
    )


def get_port(service: str) -> int:
    """Return a resolved port for *service*, caching the result.

    Thread-safe: the first caller resolves; subsequent callers receive the
    cached value.
    """
    # Fast path (no lock)
    cached = _cache.get(service)
    if cached is not None:
        return cached

    with _lock:
        # Re-check inside the lock (another thread may have resolved)
        cached = _cache.get(service)
        if cached is not None:
            return cached

        port = find_free_port(service)
        _cache[service] = port
        return port


def get_all_ports() -> Dict[str, int]:
    """Return resolved ports for every registered service."""
    return {name: get_port(name) for name in SERVICE_PORTS}


# =========================================================================
#  Persistence
# =========================================================================

def save_port_map(path: str = DEFAULT_PORT_MAP_PATH) -> None:
    """Save the current resolved port assignments to a JSON file.

    Parent directories are created automatically.
    """
    port_map = get_all_ports()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(port_map, f, indent=2, sort_keys=True)
    logger.info("Port map saved to %s", out)


def load_port_map(path: str = DEFAULT_PORT_MAP_PATH) -> Dict[str, int]:
    """Load a previously saved port map from a JSON file.

    Returns an empty dict if the file does not exist or is unreadable.
    """
    out = Path(path)
    if not out.exists():
        return {}
    try:
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {k: int(v) for k, v in data.items()}
        return {}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failed to load port map from %s: %s", path, e)
        return {}


# =========================================================================
#  URL Helper
# =========================================================================

def get_service_url(service: str, path: str = "") -> str:
    """Return the HTTP URL for *service*.

    Example::

        get_service_url("router", "/v1/models")
        # -> "http://localhost:9095/v1/models"
    """
    port = get_port(service)
    return f"http://localhost:{port}{path}"


# =========================================================================
#  CLI
# =========================================================================

def _cli_show() -> None:
    """Print a formatted table of all port assignments."""
    print()
    print(f"  {BOLD}{'Service':<15} {'Default':>7}  {'Env Var':<28} {'Range':<14} {'Resolved':>8}{NC}")
    print(f"  {'=' * 78}")

    for name in sorted(SERVICE_PORTS):
        cfg = SERVICE_PORTS[name]
        lo, hi = cfg["range"]
        rng = f"{lo}-{hi}" if lo != hi else str(lo)

        try:
            resolved = get_port(name)
            color = GREEN if resolved == cfg["default"] else YELLOW
            resolved_str = f"{color}{resolved:>8}{NC}"
        except RuntimeError:
            resolved_str = f"{RED}{'BUSY':>8}{NC}"

        print(
            f"  {name:<15} {cfg['default']:>7}  {cfg['env']:<28} {rng:<14} "
            f"{resolved_str}"
        )

    print()


def _cli_check() -> None:
    """Check which registered ports are currently in use."""
    print()
    print(f"  {BOLD}{'Service':<15} {'Port':>7}  {'Status':<12}{NC}")
    print(f"  {'=' * 40}")

    for name in sorted(SERVICE_PORTS):
        cfg = SERVICE_PORTS[name]
        try:
            port = get_port(name)
            free = is_port_free(port)
            status = f"{GREEN}free{NC}" if free else f"{RED}in use{NC}"
            print(f"  {name:<15} {port:>7}  {status}")
        except RuntimeError:
            print(f"  {name:<15} {cfg['default']:>7}  {RED}all ports busy{NC}")

    print()


def _cli_save(path: Optional[str]) -> None:
    """Save port map to disk."""
    target = path or DEFAULT_PORT_MAP_PATH
    save_port_map(target)
    print(f"  {GREEN}Port map saved to:{NC} {target}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claw_ports",
        description="Claw Agents Provisioner -- Centralized Port Management",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print port assignment table",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check which ports are currently in use",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save resolved port map to JSON",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help=f"Output path for --save (default: {DEFAULT_PORT_MAP_PATH})",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.show:
        _cli_show()
    elif args.check:
        _cli_check()
    elif args.save:
        _cli_save(args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
