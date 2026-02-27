#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Model Strategy Engine
=============================================================================
Auto-discovers all available models (local + cloud) and generates an optimal
routing strategy based on task type, quality, cost, and latency.

Supports local runtimes:
  - Ollama       (http://localhost:11434)
  - vLLM         (http://localhost:8000)
  - SGLang       (http://localhost:30000)
  - Docker Model Runner (http://localhost:12434)

Supports cloud providers:
  - Anthropic, OpenAI, DeepSeek, Gemini, Groq, OpenRouter

Usage:
  python3 shared/claw_strategy.py --scan            # Discover available models
  python3 shared/claw_strategy.py --generate         # Generate strategy.json
  python3 shared/claw_strategy.py --report           # Print strategy report
  python3 shared/claw_strategy.py --init-config      # Generate config template
  python3 shared/claw_strategy.py --benchmark        # Quick latency benchmark

Output: strategy.json — per-task-type routing recommendations

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STRATEGY_FILE = PROJECT_ROOT / "strategy.json"
STRATEGY_CONFIG = PROJECT_ROOT / "strategy_config.json"
OLLAMA_MODELS_FILE = SCRIPT_DIR / "ollama-models.json"

# Local runtime endpoints (default ports — no conflicts between services)
LOCAL_RUNTIMES = {
    "ollama": {
        "name": "Ollama",
        "api_base": "http://localhost:11434",
        "models_endpoint": "/api/tags",
        "health_endpoint": "/api/tags",
        "openai_base": "http://localhost:11434/v1",
        "default_port": 11434,
    },
    "vllm": {
        "name": "vLLM",
        "api_base": "http://localhost:8000",
        "models_endpoint": "/v1/models",
        "health_endpoint": "/health",
        "openai_base": "http://localhost:8000/v1",
        "default_port": 8000,
    },
    "sglang": {
        "name": "SGLang",
        "api_base": "http://localhost:30000",
        "models_endpoint": "/v1/models",
        "health_endpoint": "/health",
        "openai_base": "http://localhost:30000/v1",
        "default_port": 30000,
    },
    "docker_model_runner": {
        "name": "Docker Model Runner",
        "api_base": "http://localhost:12434",
        "models_endpoint": "/v1/models",
        "health_endpoint": "/v1/models",
        "openai_base": "http://localhost:12434/v1",
        "default_port": 12434,
    },
}

# Cloud provider configs
CLOUD_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            {"id": "claude-opus-4-6", "quality": 10, "cost_input": 15.0, "cost_output": 75.0, "speed": 3},
            {"id": "claude-sonnet-4-6", "quality": 9, "cost_input": 3.0, "cost_output": 15.0, "speed": 7},
            {"id": "claude-haiku-4-5", "quality": 7, "cost_input": 0.80, "cost_output": 4.0, "speed": 10},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "models": [
            {"id": "gpt-4.1", "quality": 9, "cost_input": 2.0, "cost_output": 8.0, "speed": 8},
            {"id": "gpt-4.1-mini", "quality": 7, "cost_input": 0.40, "cost_output": 1.60, "speed": 9},
            {"id": "o3-mini", "quality": 9, "cost_input": 1.10, "cost_output": 4.40, "speed": 6},
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "models": [
            {"id": "deepseek-chat", "quality": 8, "cost_input": 0.14, "cost_output": 0.28, "speed": 7},
            {"id": "deepseek-reasoner", "quality": 9, "cost_input": 0.55, "cost_output": 2.19, "speed": 5},
        ],
    },
    "gemini": {
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "models": [
            {"id": "gemini-2.0-flash", "quality": 8, "cost_input": 0.10, "cost_output": 0.40, "speed": 9},
            {"id": "gemini-2.5-pro", "quality": 9, "cost_input": 1.25, "cost_output": 10.0, "speed": 6},
        ],
    },
    "groq": {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "models": [
            {"id": "llama-3.3-70b-versatile", "quality": 8, "cost_input": 0.59, "cost_output": 0.79, "speed": 10},
            {"id": "mixtral-8x7b-32768", "quality": 7, "cost_input": 0.24, "cost_output": 0.24, "speed": 10},
        ],
    },
}

# Task types and their quality/speed preferences
TASK_TYPES = {
    "reasoning": {"min_quality": 8, "speed_weight": 0.3, "quality_weight": 0.7, "description": "Complex reasoning, math, logic"},
    "coding": {"min_quality": 7, "speed_weight": 0.4, "quality_weight": 0.6, "description": "Code generation, review, debugging"},
    "creative": {"min_quality": 7, "speed_weight": 0.3, "quality_weight": 0.7, "description": "Creative writing, marketing content"},
    "simple_chat": {"min_quality": 5, "speed_weight": 0.7, "quality_weight": 0.3, "description": "Simple Q&A, casual conversation"},
    "translation": {"min_quality": 7, "speed_weight": 0.5, "quality_weight": 0.5, "description": "Language translation"},
    "summarization": {"min_quality": 6, "speed_weight": 0.6, "quality_weight": 0.4, "description": "Text summarization, extraction"},
    "data_analysis": {"min_quality": 8, "speed_weight": 0.3, "quality_weight": 0.7, "description": "Data analysis, structured output"},
}

# Local model quality/speed estimates
LOCAL_MODEL_SPECS = {
    "llama3.2": {"quality": 6, "speed": 8, "specialization": ["general", "chat"]},
    "qwen2.5": {"quality": 8, "speed": 6, "specialization": ["general", "multilingual", "coding"]},
    "deepseek-r1": {"quality": 8, "speed": 5, "specialization": ["reasoning", "math", "coding"]},
    "phi3": {"quality": 6, "speed": 8, "specialization": ["general", "reasoning"]},
    "mistral": {"quality": 7, "speed": 7, "specialization": ["general", "chat", "creative"]},
    "codellama": {"quality": 7, "speed": 6, "specialization": ["coding"]},
    "gemma2": {"quality": 8, "speed": 6, "specialization": ["general", "reasoning", "summarization"]},
}

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
    print(f"{GREEN}[strategy]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[strategy]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[strategy]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[strategy]{NC} {msg}")


# -------------------------------------------------------------------------
# ModelScanner — discovers available models
# -------------------------------------------------------------------------
class ModelScanner:
    """Scans local runtimes and cloud providers for available models."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.local_models: List[Dict] = []
        self.cloud_models: List[Dict] = []
        self.available_runtimes: List[str] = []

    def scan_local_runtime(self, runtime_id: str, runtime_config: Dict) -> List[Dict]:
        """Query a local runtime for available models."""
        models = []
        api_base = self.config.get(f"{runtime_id}_endpoint", runtime_config["api_base"])

        try:
            url = f"{api_base}{runtime_config['models_endpoint']}"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

                # Ollama format: {"models": [{"name": "...", ...}]}
                if "models" in data and isinstance(data["models"], list):
                    for m in data["models"]:
                        name = m.get("name", "").split(":")[0]  # Remove tag
                        specs = LOCAL_MODEL_SPECS.get(name, {"quality": 6, "speed": 6, "specialization": ["general"]})
                        models.append({
                            "id": name,
                            "full_id": m.get("name", name),
                            "provider": "local",
                            "runtime": runtime_id,
                            "runtime_name": runtime_config["name"],
                            "openai_base": runtime_config["openai_base"],
                            "quality": specs["quality"],
                            "speed": specs["speed"],
                            "cost_input": 0.0,
                            "cost_output": 0.0,
                            "specialization": specs.get("specialization", ["general"]),
                        })

                # OpenAI-compatible format: {"data": [{"id": "...", ...}]}
                elif "data" in data and isinstance(data["data"], list):
                    for m in data["data"]:
                        name = m.get("id", "unknown").split("/")[-1]
                        specs = LOCAL_MODEL_SPECS.get(name, {"quality": 6, "speed": 6, "specialization": ["general"]})
                        models.append({
                            "id": name,
                            "full_id": m.get("id", name),
                            "provider": "local",
                            "runtime": runtime_id,
                            "runtime_name": runtime_config["name"],
                            "openai_base": runtime_config["openai_base"],
                            "quality": specs["quality"],
                            "speed": specs["speed"],
                            "cost_input": 0.0,
                            "cost_output": 0.0,
                            "specialization": specs.get("specialization", ["general"]),
                        })

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
            pass  # Runtime not available

        return models

    def scan_cloud_provider(self, provider_id: str, provider_config: Dict) -> List[Dict]:
        """Check if a cloud provider is configured (has API key)."""
        env_key = provider_config["env_key"]
        api_key = os.environ.get(env_key, "")

        if not api_key or api_key.endswith("REPLACE_ME"):
            return []

        models = []
        for m in provider_config["models"]:
            models.append({
                "id": m["id"],
                "full_id": m["id"],
                "provider": provider_id,
                "runtime": "cloud",
                "runtime_name": provider_config["name"],
                "openai_base": None,
                "quality": m["quality"],
                "speed": m["speed"],
                "cost_input": m["cost_input"],
                "cost_output": m["cost_output"],
                "specialization": ["general"],
            })

        return models

    def scan_all(self) -> Dict:
        """Scan all local runtimes and cloud providers."""
        log("Scanning for available models...")
        self.local_models = []
        self.cloud_models = []
        self.available_runtimes = []

        # Scan local runtimes
        for runtime_id, runtime_config in LOCAL_RUNTIMES.items():
            models = self.scan_local_runtime(runtime_id, runtime_config)
            if models:
                self.available_runtimes.append(runtime_id)
                self.local_models.extend(models)
                log(f"  {runtime_config['name']}: {len(models)} model(s) found")
            else:
                info(f"  {runtime_config['name']}: not available (port {runtime_config['default_port']})")

        # Scan cloud providers
        for provider_id, provider_config in CLOUD_PROVIDERS.items():
            models = self.scan_cloud_provider(provider_id, provider_config)
            if models:
                self.cloud_models.extend(models)
                log(f"  {provider_config['name']}: {len(models)} model(s) configured")
            else:
                info(f"  {provider_config['name']}: no API key")

        total = len(self.local_models) + len(self.cloud_models)
        log(f"Scan complete: {total} model(s) available ({len(self.local_models)} local, {len(self.cloud_models)} cloud)")

        return {
            "local_models": self.local_models,
            "cloud_models": self.cloud_models,
            "available_runtimes": self.available_runtimes,
            "total": total,
        }


# -------------------------------------------------------------------------
# StrategyGenerator — builds optimal routing per task type
# -------------------------------------------------------------------------
class StrategyGenerator:
    """Generates a model routing strategy based on available models."""

    def __init__(self, scan_results: Dict, config: Optional[Dict] = None):
        self.config = config or {}
        self.all_models = scan_results.get("local_models", []) + scan_results.get("cloud_models", [])
        self.prefer_local = self.config.get("prefer_local", True)
        self.monthly_budget = self.config.get("monthly_budget", None)

    def score_model(self, model: Dict, task_config: Dict) -> float:
        """Score a model for a specific task type."""
        quality_w = task_config["quality_weight"]
        speed_w = task_config["speed_weight"]

        base_score = (model["quality"] * quality_w + model["speed"] * speed_w) * 10

        # Bonus for local models (free)
        if model["provider"] == "local" and self.prefer_local:
            base_score += 15

        # Bonus for specialization match
        task_name = ""
        for tname, tconf in TASK_TYPES.items():
            if tconf == task_config:
                task_name = tname
                break

        if task_name and any(s in model.get("specialization", []) for s in [task_name, "general"]):
            base_score += 5

        # Penalty for high cost
        total_cost = model["cost_input"] + model["cost_output"]
        if total_cost > 10:
            base_score -= 10
        elif total_cost > 3:
            base_score -= 5

        # Quality floor
        if model["quality"] < task_config["min_quality"]:
            base_score -= 30

        return round(base_score, 2)

    def generate(self) -> Dict:
        """Generate routing strategy for all task types."""
        if not self.all_models:
            err("No models available. Run --scan first.")
            return {}

        strategy = {
            "version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_models": len(self.all_models),
            "prefer_local": self.prefer_local,
            "task_routing": {},
            "models_inventory": [],
            "monthly_cost_estimate": {"min": 0.0, "max": 0.0},
        }

        # Build inventory
        for m in self.all_models:
            strategy["models_inventory"].append({
                "id": m["id"],
                "provider": m.get("runtime_name", m["provider"]),
                "type": "local" if m["provider"] == "local" else "cloud",
                "quality": m["quality"],
                "speed": m["speed"],
                "cost_per_million_input": m["cost_input"],
                "cost_per_million_output": m["cost_output"],
            })

        # Route each task type
        total_min_cost = 0.0
        total_max_cost = 0.0

        for task_name, task_config in TASK_TYPES.items():
            scored = []
            for model in self.all_models:
                score = self.score_model(model, task_config)
                scored.append((score, model))

            scored.sort(key=lambda x: x[0], reverse=True)

            primary = scored[0] if scored else None
            fallback = scored[1] if len(scored) > 1 else None

            route = {
                "description": task_config["description"],
                "min_quality": task_config["min_quality"],
            }

            if primary:
                pm = primary[1]
                route["primary"] = {
                    "model": pm["id"],
                    "provider": pm.get("runtime_name", pm["provider"]),
                    "type": "local" if pm["provider"] == "local" else "cloud",
                    "score": primary[0],
                    "openai_base": pm.get("openai_base"),
                }
                # Estimate cost (assume 100K tokens/month per task type)
                monthly = (pm["cost_input"] + pm["cost_output"]) * 0.1
                total_min_cost += monthly * 0.5
                total_max_cost += monthly * 2.0

            if fallback:
                fm = fallback[1]
                route["fallback"] = {
                    "model": fm["id"],
                    "provider": fm.get("runtime_name", fm["provider"]),
                    "type": "local" if fm["provider"] == "local" else "cloud",
                    "score": fallback[0],
                    "openai_base": fm.get("openai_base"),
                }

            strategy["task_routing"][task_name] = route

        strategy["monthly_cost_estimate"] = {
            "min": round(total_min_cost, 2),
            "max": round(total_max_cost, 2),
            "note": "Estimate based on ~100K tokens/month per task type",
        }

        return strategy


# -------------------------------------------------------------------------
# CLI Output Formatting
# -------------------------------------------------------------------------
def print_scan_report(scan_results: Dict) -> None:
    """Print a formatted scan report."""
    print(f"\n{BOLD}{CYAN}=== Model Strategy Engine — Scan Report ==={NC}\n")

    # Local runtimes
    print(f"{BOLD}Local Runtimes:{NC}")
    for runtime_id, runtime_config in LOCAL_RUNTIMES.items():
        status = f"{GREEN}ACTIVE{NC}" if runtime_id in scan_results.get("available_runtimes", []) else f"{RED}OFFLINE{NC}"
        port = runtime_config["default_port"]
        print(f"  {runtime_config['name']:.<25} {status}  (port {port})")

    print()

    # Local models
    local = scan_results.get("local_models", [])
    if local:
        print(f"{BOLD}Local Models ({len(local)}):{NC}")
        for m in local:
            specs = LOCAL_MODEL_SPECS.get(m["id"], {})
            quality = specs.get("quality", "?")
            speed = specs.get("speed", "?")
            print(f"  {m['id']:.<20} via {m['runtime_name']:<20} quality={quality}/10  speed={speed}/10  cost=$0")
    else:
        print(f"{DIM}No local models found. Install Ollama, vLLM, SGLang, or Docker Model Runner.{NC}")

    print()

    # Cloud providers
    cloud = scan_results.get("cloud_models", [])
    if cloud:
        print(f"{BOLD}Cloud Models ({len(cloud)}):{NC}")
        for m in cloud:
            cost = f"${m['cost_input']:.2f}/{m['cost_output']:.2f}"
            print(f"  {m['id']:.<25} via {m['runtime_name']:<12} quality={m['quality']}/10  speed={m['speed']}/10  cost={cost}/M tok")
    else:
        print(f"{DIM}No cloud API keys configured.{NC}")

    print(f"\n{BOLD}Total: {scan_results.get('total', 0)} model(s) available{NC}\n")


def print_strategy_report(strategy: Dict) -> None:
    """Print a formatted strategy report."""
    print(f"\n{BOLD}{CYAN}=== Model Strategy Engine — Routing Strategy ==={NC}\n")
    print(f"  Generated: {strategy.get('generated_at', 'unknown')}")
    print(f"  Models:    {strategy.get('total_models', 0)}")
    print(f"  Prefer:    {'Local' if strategy.get('prefer_local') else 'Cloud'}")
    print()

    routing = strategy.get("task_routing", {})
    print(f"{BOLD}{'Task Type':<18} {'Primary':<25} {'Type':<8} {'Score':<8} {'Fallback':<25}{NC}")
    print(f"{'─' * 18} {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 25}")

    for task_name, route in routing.items():
        primary = route.get("primary", {})
        fallback = route.get("fallback", {})
        p_name = primary.get("model", "-")
        p_type = primary.get("type", "-")
        p_score = f"{primary.get('score', 0):.1f}"
        f_name = fallback.get("model", "-")

        # Color code local vs cloud
        type_str = f"{GREEN}{p_type}{NC}" if p_type == "local" else f"{BLUE}{p_type}{NC}"
        print(f"  {task_name:<16} {p_name:<25} {type_str:<17} {p_score:<8} {f_name:<25}")

    cost = strategy.get("monthly_cost_estimate", {})
    print(f"\n{BOLD}Monthly Cost Estimate:{NC} ${cost.get('min', 0):.2f} — ${cost.get('max', 0):.2f}")
    print(f"{DIM}  {cost.get('note', '')}{NC}\n")


# -------------------------------------------------------------------------
# Config Management
# -------------------------------------------------------------------------
def init_config() -> None:
    """Generate a default strategy config file."""
    config = {
        "prefer_local": True,
        "monthly_budget": None,
        "ollama_endpoint": "http://localhost:11434",
        "vllm_endpoint": "http://localhost:8000",
        "sglang_endpoint": "http://localhost:30000",
        "docker_model_runner_endpoint": "http://localhost:12434",
        "auto_generate": False,
        "notes": "Edit this file to customize strategy behavior. Run: ./claw.sh strategy generate",
    }

    with open(STRATEGY_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    log(f"Config generated: {STRATEGY_CONFIG}")
    info("Edit it, then run: ./claw.sh strategy generate")


def load_config() -> Dict:
    """Load strategy config, falling back to defaults."""
    if STRATEGY_CONFIG.exists():
        with open(STRATEGY_CONFIG) as f:
            return json.load(f)
    return {}


# -------------------------------------------------------------------------
# Benchmark
# -------------------------------------------------------------------------
def run_benchmark(scan_results: Dict) -> None:
    """Quick latency benchmark for available runtimes."""
    print(f"\n{BOLD}{CYAN}=== Model Strategy Engine — Latency Benchmark ==={NC}\n")

    for runtime_id in scan_results.get("available_runtimes", []):
        runtime_config = LOCAL_RUNTIMES[runtime_id]
        url = f"{runtime_config['api_base']}{runtime_config['health_endpoint']}"

        times = []
        for _ in range(3):
            try:
                start = time.time()
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as _:
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)
            except Exception:
                times.append(-1)

        valid = [t for t in times if t > 0]
        if valid:
            avg = sum(valid) / len(valid)
            print(f"  {runtime_config['name']:.<25} {avg:.0f}ms avg  (3 probes)")
        else:
            print(f"  {runtime_config['name']:.<25} {RED}unreachable{NC}")

    # Cloud providers — just check if key exists
    print()
    for provider_id, provider_config in CLOUD_PROVIDERS.items():
        env_key = provider_config["env_key"]
        has_key = bool(os.environ.get(env_key, "")) and not os.environ.get(env_key, "").endswith("REPLACE_ME")
        status = f"{GREEN}configured{NC}" if has_key else f"{DIM}no key{NC}"
        print(f"  {provider_config['name']:.<25} {status}")

    print()


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 shared/claw_strategy.py [--scan|--generate|--report|--init-config|--benchmark]")
        print()
        print("Commands:")
        print("  --scan          Discover available models (local + cloud)")
        print("  --generate      Generate strategy.json routing recommendations")
        print("  --report        Print current strategy report")
        print("  --init-config   Generate strategy_config.json template")
        print("  --benchmark     Quick latency benchmark for local runtimes")
        sys.exit(1)

    action = sys.argv[1]
    config = load_config()

    if action == "--scan":
        scanner = ModelScanner(config)
        results = scanner.scan_all()
        print_scan_report(results)

    elif action == "--generate":
        scanner = ModelScanner(config)
        results = scanner.scan_all()

        if results["total"] == 0:
            err("No models found. Install a local runtime or configure cloud API keys.")
            sys.exit(1)

        generator = StrategyGenerator(results, config)
        strategy = generator.generate()

        with open(STRATEGY_FILE, "w") as f:
            json.dump(strategy, f, indent=2)

        log(f"Strategy written to: {STRATEGY_FILE}")
        print_strategy_report(strategy)

    elif action == "--report":
        if not STRATEGY_FILE.exists():
            err(f"No strategy.json found. Run --generate first.")
            sys.exit(1)

        with open(STRATEGY_FILE) as f:
            strategy = json.load(f)

        print_strategy_report(strategy)

    elif action == "--init-config":
        init_config()

    elif action == "--benchmark":
        scanner = ModelScanner(config)
        results = scanner.scan_all()
        run_benchmark(results)

    else:
        err(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
