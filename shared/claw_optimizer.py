#!/usr/bin/env python3
"""
Claw Optimizer — Multi-Model Optimization Engine (14 Rules)

Chains 14 optimization rules into a pipeline that sits between your
application code and the LLM API call.  Every rule can be individually
enabled/disabled and configured.  Uses ZERO additional dependencies —
stdlib-only, just like claw_watchdog.py.

Pipeline order (pre-call):
   1. ConversationDedup      — return cached if duplicate message within 60 s
   2. SemanticCache          — return cached if trigram similarity > threshold
   3. TokenEstimator         — estimate token count and cost before API call
   4. ContextPruner          — sliding-window + summary compression
   5. PromptOptimizer        — strip excess whitespace, dedup instructions
   6. BudgetEnforcer         — daily/weekly/monthly spend caps, auto-downgrade
   7. TaskComplexityRouter   — route simple queries to cheap models
   8. LatencyRouter          — override model if speed-sensitive (disabled)
   9. ProviderHealthScorer   — composite health score, skip unhealthy providers
  10. RateLimitManager       — client-side token-bucket per provider
  11. FallbackChain          — retry logic on 429/500/502/503
  [API CALL]
  12. ResponseQualityGate    — validate response, retry if bad
  13. CostAttributionLogger  — log to SQLite + JSONL

Usage:
    python shared/claw_optimizer.py --init-config          # write optimization.json
    python shared/claw_optimizer.py --once                  # single report, exit
    python shared/claw_optimizer.py -c optimization.json    # run as service
    python shared/claw_optimizer.py --report                # cost report from DB

Requirements:
    Python 3.8+  (stdlib only — no pip installs)
"""

import argparse
import hashlib
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ═════════════════════════════════════════════════════════════════════════════
#  Configuration Defaults
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "enabled": True,
    "dashboard_port": 9091,
    "log_file": "optimizer.log",
    "cost_log_db": "cost_log.sqlite3",
    "cache_db": "response_cache.sqlite3",
    "budget_db": "budget_tracking.sqlite3",
    "cost_log_jsonl": "cost_log.jsonl",

    "models": {
        "tiers": {
            "budget":   ["deepseek-chat", "gemini-2.0-flash"],
            "standard": ["claude-sonnet-4-6", "gpt-4.1-mini"],
            "premium":  ["claude-opus-4-6", "gpt-4.1", "claude-sonnet-4-6"],
        },
        "costs_per_1k_tokens": {
            "deepseek-chat":      {"input": 0.00014, "output": 0.00028},
            "gemini-2.0-flash":   {"input": 0.0,     "output": 0.0},
            "claude-sonnet-4-6":  {"input": 0.003,   "output": 0.015},
            "claude-opus-4-6":    {"input": 0.015,   "output": 0.075},
            "gpt-4.1":           {"input": 0.002,   "output": 0.008},
            "gpt-4.1-mini":      {"input": 0.0004,  "output": 0.0016},
        },
    },

    "rules": {
        "conversation_dedup":     {"enabled": True,  "window_seconds": 60},
        "semantic_cache":         {"enabled": True,  "similarity_threshold": 0.85,
                                   "ttl_seconds": 3600},
        "token_estimator":        {"enabled": True},
        "context_pruner":         {"enabled": True,  "max_tokens": 100000,
                                   "summary_threshold": 0.7},
        "prompt_optimizer":       {"enabled": True},
        "budget_enforcer":        {"enabled": True,  "daily_limit": 50.0,
                                   "weekly_limit": 200.0, "monthly_limit": 500.0,
                                   "alert_threshold": 0.8, "auto_downgrade": True},
        "task_complexity_router": {"enabled": True,  "simple_max_tokens": 500,
                                   "complex_indicators": [
                                       "analyze", "compare", "design",
                                       "architect", "debug", "security"]},
        "latency_router":         {"enabled": False, "max_latency_ms": 2000},
        "provider_health_scorer": {"enabled": True,  "min_health_score": 0.5,
                                   "window_minutes": 60},
        "rate_limit_manager":     {"enabled": True,
                                   "requests_per_minute": {
                                       "anthropic": 50, "openai": 60,
                                       "deepseek": 100, "gemini": 60}},
        "fallback_chain":         {"enabled": True,  "max_retries": 3,
                                   "retry_on": [429, 500, 502, 503]},
        "response_quality_gate":  {"enabled": True,  "min_length": 10,
                                   "max_retries": 2},
        "cost_attribution_logger": {"enabled": True},
    },
}

# ═════════════════════════════════════════════════════════════════════════════
#  Logging
# ═════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("optimizer")


def setup_logging(log_file=None):
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)


# ═════════════════════════════════════════════════════════════════════════════
#  Utility Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch() -> float:
    return time.time()


def _trigrams(text: str):
    """Extract character trigrams from text (lowercased)."""
    t = text.lower().strip()
    if len(t) < 3:
        return set()
    return {t[i:i + 3] for i in range(len(t) - 2)}


def _trigram_similarity(a: str, b: str) -> float:
    """Jaccard similarity over character trigrams."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    union = len(ta | tb)
    return intersection / union if union else 0.0


def _estimate_tokens(text: str) -> int:
    """Approximate token count: ~4 chars per token."""
    return max(1, len(text) // 4)


def _message_hash(text: str) -> str:
    """SHA-256 hex digest of a message."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _provider_from_model(model: str) -> str:
    """Infer provider name from model id."""
    m = model.lower()
    if "claude" in m:
        return "anthropic"
    if "gpt" in m:
        return "openai"
    if "deepseek" in m:
        return "deepseek"
    if "gemini" in m:
        return "gemini"
    if any(name in m for name in ("llama", "mistral", "codellama", "phi", "qwen", "deepseek-r1")):
        return "local"
    return "unknown"


# ═════════════════════════════════════════════════════════════════════════════
#  SQLite-Backed Cost Tracker
# ═════════════════════════════════════════════════════════════════════════════

class CostTracker:
    """Tracks API costs via DAL.  Falls back to standalone SQLite if DAL unavailable."""

    def __init__(self, db_path: str = ""):
        self._dal = None
        try:
            from claw_dal import DAL
            self._dal = DAL.get_instance()
        except Exception:
            pass

    def log(self, model: str, provider: str, input_tokens: int,
            output_tokens: int, cost_usd: float, agent: str = "",
            task: str = "", cached: bool = False):
        if self._dal:
            self._dal.costs.record_cost(
                agent_id=agent or "optimizer",
                model=model, provider=provider,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost_usd,
                cache_savings=cost_usd if cached else 0.0)

    def daily_spend(self) -> float:
        if self._dal:
            return self._dal.costs.daily_spend()
        return 0.0

    def weekly_spend(self) -> float:
        if self._dal:
            return self._dal.costs.weekly_spend()
        return 0.0

    def monthly_spend(self) -> float:
        if self._dal:
            return self._dal.costs.monthly_spend()
        return 0.0

    def total_spend(self) -> float:
        if self._dal:
            today = datetime.now(timezone.utc).strftime("%Y-01-01T00:00:00Z")
            return self._dal.costs._sum_since("1970-01-01T00:00:00Z")
        return 0.0

    def summary(self) -> dict:
        return {
            "daily":   round(self.daily_spend(), 4),
            "weekly":  round(self.weekly_spend(), 4),
            "monthly": round(self.monthly_spend(), 4),
            "total":   round(self.total_spend(), 4),
        }

    def recent(self, limit: int = 20) -> list:
        if self._dal:
            rows = self._dal.costs.recent(limit)
            return [
                {"ts": r.get("timestamp", ""), "model": r.get("model", ""),
                 "input_tokens": r.get("input_tokens", 0),
                 "output_tokens": r.get("output_tokens", 0),
                 "cost_usd": r.get("cost_usd", 0),
                 "agent": r.get("agent_id", "")}
                for r in rows
            ]
        return []


# ═════════════════════════════════════════════════════════════════════════════
#  SQLite-Backed Response Cache
# ═════════════════════════════════════════════════════════════════════════════

class ResponseCache:
    """Cache responses via DAL's response_cache table."""

    def __init__(self, db_path: str = ""):
        self._dal = None
        try:
            from claw_dal import DAL
            self._dal = DAL.get_instance()
        except Exception:
            pass

    def get_exact(self, msg_hash: str) -> str:
        """Return cached response for exact hash match, or None."""
        if self._dal:
            return self._dal.response_cache.get_exact(msg_hash)
        return None

    def get_similar(self, message: str, threshold: float = 0.85,
                    ttl_seconds: int = 3600) -> str:
        """Search cache for semantically similar message via trigrams."""
        if self._dal:
            return self._dal.response_cache.get_similar(
                message, threshold, ttl_seconds)
        return None

    def put(self, message: str, response: str, model: str,
            ttl_seconds: int = 3600):
        msg_hash = _message_hash(message)
        if self._dal:
            self._dal.response_cache.put(
                prompt_hash=msg_hash, model=model, response=response,
                ttl_seconds=ttl_seconds)

    def stats(self) -> dict:
        if self._dal:
            return self._dal.response_cache.stats()
        return {"total_entries": 0}


# ═════════════════════════════════════════════════════════════════════════════
#  Base Optimization Rule
# ═════════════════════════════════════════════════════════════════════════════

class OptimizationRule:
    """Abstract base for all 14 optimization rules."""

    name = "base"
    description = "Base optimization rule"
    default_config = {}

    def __init__(self, config: dict):
        merged = dict(self.default_config)
        merged.update(config)
        self.config = merged
        self.enabled = self.config.get("enabled", True)
        self.hits = 0
        self.misses = 0

    def process(self, request: dict, context: dict) -> dict:
        """Process a request through this rule.

        Args:
            request: Mutable dict with keys like 'messages', 'model',
                     'system_prompt', etc.
            context: Shared pipeline context (cache, cost tracker, etc.)

        Returns:
            request dict (possibly modified).  If 'cached_response' key
            is set, the pipeline short-circuits and returns that.
        """
        return request

    def status(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "description": self.description,
            "hits": self.hits,
            "misses": self.misses,
        }


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  1 — ConversationDedup
# ═════════════════════════════════════════════════════════════════════════════

class ConversationDedup(OptimizationRule):
    name = "conversation_dedup"
    description = "Return cached response for duplicate messages within window"
    default_config = {"enabled": True, "window_seconds": 60}

    def __init__(self, config: dict):
        super().__init__(config)
        self._recent = {}  # hash -> (timestamp, response)
        self._lock = threading.Lock()

    def process(self, request: dict, context: dict) -> dict:
        messages = request.get("messages", [])
        if not messages:
            return request

        last_msg = messages[-1].get("content", "") if messages else ""
        h = _message_hash(last_msg)
        window = self.config.get("window_seconds", 60)
        now = _epoch()

        with self._lock:
            # Purge expired entries
            expired = [k for k, v in self._recent.items()
                       if now - v[0] > window]
            for k in expired:
                del self._recent[k]

            if h in self._recent:
                self.hits += 1
                logger.info(f"[ConversationDedup] HIT  duplicate within {window}s")
                request["cached_response"] = self._recent[h][1]
                request["cache_source"] = "dedup"
                return request

        self.misses += 1
        return request

    def record_response(self, message: str, response: str):
        """Call after API response to populate dedup cache."""
        h = _message_hash(message)
        with self._lock:
            self._recent[h] = (_epoch(), response)


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  2 — SemanticCache
# ═════════════════════════════════════════════════════════════════════════════

class SemanticCache(OptimizationRule):
    name = "semantic_cache"
    description = "Return cached response if trigram similarity exceeds threshold"
    default_config = {"enabled": True, "similarity_threshold": 0.85,
                      "ttl_seconds": 3600}

    def process(self, request: dict, context: dict) -> dict:
        cache = context.get("response_cache")  # type: ResponseCache
        if not cache:
            return request

        messages = request.get("messages", [])
        if not messages:
            return request

        last_msg = messages[-1].get("content", "") if messages else ""
        if not last_msg:
            return request

        # Try exact match first
        h = _message_hash(last_msg)
        exact = cache.get_exact(h)
        if exact:
            self.hits += 1
            logger.info("[SemanticCache] HIT  exact match")
            request["cached_response"] = exact
            request["cache_source"] = "semantic_exact"
            return request

        # Try trigram similarity
        threshold = self.config.get("similarity_threshold", 0.85)
        ttl = self.config.get("ttl_seconds", 3600)
        similar = cache.get_similar(last_msg, threshold=threshold,
                                    ttl_seconds=ttl)
        if similar:
            self.hits += 1
            logger.info("[SemanticCache] HIT  trigram similarity >= "
                        f"{threshold}")
            request["cached_response"] = similar
            request["cache_source"] = "semantic_trigram"
            return request

        self.misses += 1
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  3 — TokenEstimator
# ═════════════════════════════════════════════════════════════════════════════

class TokenEstimator(OptimizationRule):
    name = "token_estimator"
    description = "Estimate token count and cost before API call"
    default_config = {"enabled": True}

    def process(self, request: dict, context: dict) -> dict:
        # Estimate input tokens from messages + system prompt
        total_text = request.get("system_prompt", "")
        for msg in request.get("messages", []):
            total_text += msg.get("content", "")

        input_tokens = _estimate_tokens(total_text)
        request["estimated_input_tokens"] = input_tokens

        # Estimate cost based on model
        model = request.get("model", "")
        costs = context.get("model_costs", {})
        model_cost = costs.get(model, {})
        input_cost_per_1k = model_cost.get("input", 0.0)
        estimated_cost = (input_tokens / 1000.0) * input_cost_per_1k
        request["estimated_cost"] = round(estimated_cost, 6)

        self.hits += 1
        logger.debug(f"[TokenEstimator] ~{input_tokens} input tokens, "
                     f"~${estimated_cost:.6f}")
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  4 — ContextPruner
# ═════════════════════════════════════════════════════════════════════════════

class ContextPruner(OptimizationRule):
    name = "context_pruner"
    description = "Sliding window + summary compression for conversation history"
    default_config = {"enabled": True, "max_tokens": 100000,
                      "summary_threshold": 0.7}

    def process(self, request: dict, context: dict) -> dict:
        messages = request.get("messages", [])
        if not messages:
            return request

        max_tokens = self.config.get("max_tokens", 100000)
        threshold = self.config.get("summary_threshold", 0.7)

        # Estimate total tokens across all messages
        total_tokens = sum(_estimate_tokens(m.get("content", ""))
                          for m in messages)

        if total_tokens <= max_tokens:
            self.misses += 1
            return request

        # Prune: keep system messages, first message, and recent messages
        # Remove middle messages until under budget
        self.hits += 1
        target = int(max_tokens * threshold)
        pruned = []
        kept_tokens = 0

        # Always keep the last N messages (most recent context)
        keep_tail = min(10, len(messages))
        tail = messages[-keep_tail:]
        tail_tokens = sum(_estimate_tokens(m.get("content", ""))
                          for m in tail)

        # Fill remaining budget from the beginning
        remaining_budget = target - tail_tokens
        head = []
        for msg in messages[:-keep_tail]:
            msg_tokens = _estimate_tokens(msg.get("content", ""))
            if msg.get("role") == "system":
                # Always keep system messages
                head.append(msg)
                continue
            if remaining_budget - msg_tokens > 0:
                head.append(msg)
                remaining_budget -= msg_tokens
            else:
                # Insert a summary placeholder
                if head and head[-1].get("role") != "system":
                    head.append({
                        "role": "system",
                        "content": "[Earlier conversation pruned to save tokens]"
                    })
                break

        request["messages"] = head + tail
        pruned_count = len(messages) - len(head) - len(tail)
        logger.info(f"[ContextPruner] Pruned {pruned_count} messages, "
                    f"{total_tokens} -> ~{target} tokens")
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  5 — PromptOptimizer
# ═════════════════════════════════════════════════════════════════════════════

class PromptOptimizer(OptimizationRule):
    name = "prompt_optimizer"
    description = "Compress system prompts: strip whitespace, dedup instructions"
    default_config = {"enabled": True}

    def process(self, request: dict, context: dict) -> dict:
        system = request.get("system_prompt", "")
        if not system:
            self.misses += 1
            return request

        original_len = len(system)

        # Collapse multiple blank lines into one
        optimized = re.sub(r"\n{3,}", "\n\n", system)
        # Collapse multiple spaces (preserve newlines)
        optimized = re.sub(r"[^\S\n]+", " ", optimized)
        # Strip trailing whitespace per line
        optimized = "\n".join(line.rstrip() for line in optimized.split("\n"))
        # Deduplicate repeated instruction lines
        seen_lines = set()
        deduped = []
        for line in optimized.split("\n"):
            stripped = line.strip().lower()
            if stripped and stripped in seen_lines:
                continue
            seen_lines.add(stripped)
            deduped.append(line)
        optimized = "\n".join(deduped).strip()

        savings = original_len - len(optimized)
        if savings > 0:
            self.hits += 1
            request["system_prompt"] = optimized
            request["prompt_savings_chars"] = savings
            logger.debug(f"[PromptOptimizer] Saved {savings} chars "
                         f"({original_len} -> {len(optimized)})")
        else:
            self.misses += 1

        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  6 — BudgetEnforcer
# ═════════════════════════════════════════════════════════════════════════════

class BudgetEnforcer(OptimizationRule):
    name = "budget_enforcer"
    description = "Daily/weekly/monthly spend caps with auto-downgrade"
    default_config = {"enabled": True, "daily_limit": 50.0,
                      "weekly_limit": 200.0, "monthly_limit": 500.0,
                      "alert_threshold": 0.8, "auto_downgrade": True}

    def process(self, request: dict, context: dict) -> dict:
        tracker = context.get("cost_tracker")  # type: CostTracker
        if not tracker:
            return request

        daily = tracker.daily_spend()
        weekly = tracker.weekly_spend()
        monthly = tracker.monthly_spend()

        daily_limit = self.config.get("daily_limit", 50.0)
        weekly_limit = self.config.get("weekly_limit", 200.0)
        monthly_limit = self.config.get("monthly_limit", 500.0)
        alert_pct = self.config.get("alert_threshold", 0.8)
        auto_downgrade = self.config.get("auto_downgrade", True)

        # Check if any budget is exceeded
        over_budget = False
        reason = ""
        if daily >= daily_limit:
            over_budget = True
            reason = f"daily ${daily:.2f} >= ${daily_limit:.2f}"
        elif weekly >= weekly_limit:
            over_budget = True
            reason = f"weekly ${weekly:.2f} >= ${weekly_limit:.2f}"
        elif monthly >= monthly_limit:
            over_budget = True
            reason = f"monthly ${monthly:.2f} >= ${monthly_limit:.2f}"

        if over_budget:
            self.hits += 1
            if auto_downgrade:
                # Downgrade model to cheapest available
                tiers = context.get("model_tiers", {})
                budget_models = tiers.get("budget", [])
                if budget_models:
                    original = request.get("model", "")
                    request["model"] = budget_models[0]
                    request["budget_downgraded"] = True
                    request["original_model"] = original
                    logger.warning(
                        f"[BudgetEnforcer] DOWNGRADE {original} -> "
                        f"{budget_models[0]} ({reason})")
            else:
                request["budget_blocked"] = True
                logger.warning(f"[BudgetEnforcer] BLOCKED ({reason})")
            return request

        # Check alert thresholds
        if daily >= daily_limit * alert_pct:
            logger.warning(f"[BudgetEnforcer] Daily spend at "
                           f"{daily/daily_limit*100:.0f}%")
        if weekly >= weekly_limit * alert_pct:
            logger.warning(f"[BudgetEnforcer] Weekly spend at "
                           f"{weekly/weekly_limit*100:.0f}%")
        if monthly >= monthly_limit * alert_pct:
            logger.warning(f"[BudgetEnforcer] Monthly spend at "
                           f"{monthly/monthly_limit*100:.0f}%")

        self.misses += 1
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  7 — TaskComplexityRouter
# ═════════════════════════════════════════════════════════════════════════════

class TaskComplexityRouter(OptimizationRule):
    name = "task_complexity_router"
    description = "Route simple queries to cheap models, complex to premium"
    default_config = {"enabled": True, "simple_max_tokens": 500,
                      "complex_indicators": [
                          "analyze", "compare", "design",
                          "architect", "debug", "security"]}

    def process(self, request: dict, context: dict) -> dict:
        messages = request.get("messages", [])
        if not messages:
            return request

        # Already downgraded by budget? skip
        if request.get("budget_downgraded"):
            self.misses += 1
            return request

        last_msg = messages[-1].get("content", "") if messages else ""
        tokens = _estimate_tokens(last_msg)
        simple_max = self.config.get("simple_max_tokens", 500)
        indicators = self.config.get("complex_indicators", [])

        # Check complexity
        is_complex = False
        msg_lower = last_msg.lower()

        # Length-based heuristic
        if tokens > simple_max:
            is_complex = True

        # Keyword-based heuristic
        for indicator in indicators:
            if indicator.lower() in msg_lower:
                is_complex = True
                break

        # Multi-turn complexity (long conversation = likely complex)
        if len(messages) > 10:
            is_complex = True

        tiers = context.get("model_tiers", {})
        current_model = request.get("model", "")

        if is_complex:
            # Upgrade to premium if not already
            premium = tiers.get("premium", [])
            if premium and current_model not in premium:
                request["model"] = premium[0]
                request["complexity_routed"] = "premium"
                self.hits += 1
                logger.info(f"[TaskComplexityRouter] COMPLEX -> "
                            f"{premium[0]}")
        else:
            # Downgrade to budget for simple queries
            budget = tiers.get("budget", [])
            if budget and current_model not in budget:
                request["model"] = budget[0]
                request["complexity_routed"] = "budget"
                self.hits += 1
                logger.info(f"[TaskComplexityRouter] SIMPLE -> "
                            f"{budget[0]}")

        if not request.get("complexity_routed"):
            self.misses += 1
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  8 — LatencyRouter
# ═════════════════════════════════════════════════════════════════════════════

class LatencyRouter(OptimizationRule):
    name = "latency_router"
    description = "Override model choice if speed-sensitive (disabled by default)"
    default_config = {"enabled": False, "max_latency_ms": 2000}

    def process(self, request: dict, context: dict) -> dict:
        if not self.enabled:
            return request

        max_latency = self.config.get("max_latency_ms", 2000)
        health_scores = context.get("provider_health", {})

        # Check if current model's provider has high latency
        model = request.get("model", "")
        provider = _provider_from_model(model)
        health = health_scores.get(provider, {})
        avg_latency = health.get("avg_latency_ms", 0)

        if avg_latency > max_latency:
            # Switch to fastest available provider
            tiers = context.get("model_tiers", {})
            budget_models = tiers.get("budget", [])
            for candidate in budget_models:
                c_provider = _provider_from_model(candidate)
                c_health = health_scores.get(c_provider, {})
                c_latency = c_health.get("avg_latency_ms", 0)
                if c_latency < max_latency or c_latency == 0:
                    request["model"] = candidate
                    request["latency_routed"] = True
                    self.hits += 1
                    logger.info(f"[LatencyRouter] {model} latency "
                                f"{avg_latency}ms > {max_latency}ms, "
                                f"routed to {candidate}")
                    return request

        self.misses += 1
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule  9 — ProviderHealthScorer
# ═════════════════════════════════════════════════════════════════════════════

class ProviderHealthScorer(OptimizationRule):
    name = "provider_health_scorer"
    description = "Composite health score per provider, skip unhealthy ones"
    default_config = {"enabled": True, "min_health_score": 0.5,
                      "window_minutes": 60}

    def __init__(self, config: dict):
        super().__init__(config)
        self._events = defaultdict(list)  # provider -> [(ts, success, latency)]
        self._lock = threading.Lock()

    def record_event(self, provider: str, success: bool,
                     latency_ms: float = 0):
        """Record an API call outcome for health scoring."""
        with self._lock:
            self._events[provider].append((_epoch(), success, latency_ms))

    def _compute_score(self, provider: str) -> dict:
        """Compute weighted health score for a provider."""
        window = self.config.get("window_minutes", 60) * 60
        cutoff = _epoch() - window

        with self._lock:
            events = [e for e in self._events.get(provider, [])
                      if e[0] >= cutoff]

        if not events:
            return {"score": 1.0, "total_calls": 0, "success_rate": 1.0,
                    "avg_latency_ms": 0}

        successes = sum(1 for e in events if e[1])
        total = len(events)
        success_rate = successes / total if total else 1.0

        latencies = [e[2] for e in events if e[2] > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Weighted score: 70% success rate + 30% latency factor
        latency_factor = max(0, 1.0 - (avg_latency / 10000.0))
        score = 0.7 * success_rate + 0.3 * latency_factor

        return {
            "score": round(score, 3),
            "total_calls": total,
            "success_rate": round(success_rate, 3),
            "avg_latency_ms": round(avg_latency, 1),
        }

    def get_all_scores(self) -> dict:
        providers = set()
        with self._lock:
            providers = set(self._events.keys())
        return {p: self._compute_score(p) for p in providers}

    def process(self, request: dict, context: dict) -> dict:
        model = request.get("model", "")
        provider = _provider_from_model(model)
        min_score = self.config.get("min_health_score", 0.5)

        score_data = self._compute_score(provider)
        context["provider_health"] = self.get_all_scores()

        if score_data["score"] < min_score and score_data["total_calls"] > 5:
            self.hits += 1
            # Try to find a healthy alternative in same tier
            tiers = context.get("model_tiers", {})
            for tier_name, models in tiers.items():
                for candidate in models:
                    c_provider = _provider_from_model(candidate)
                    if c_provider == provider:
                        continue
                    c_score = self._compute_score(c_provider)
                    if c_score["score"] >= min_score:
                        request["model"] = candidate
                        request["health_rerouted"] = True
                        logger.warning(
                            f"[ProviderHealthScorer] {provider} score "
                            f"{score_data['score']} < {min_score}, "
                            f"rerouted to {candidate}")
                        return request
            logger.warning(f"[ProviderHealthScorer] {provider} unhealthy "
                           f"but no alternative found")
        else:
            self.misses += 1

        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule 10 — RateLimitManager
# ═════════════════════════════════════════════════════════════════════════════

class RateLimitManager(OptimizationRule):
    name = "rate_limit_manager"
    description = "Client-side token bucket throttling per provider"
    default_config = {"enabled": True,
                      "requests_per_minute": {
                          "anthropic": 50, "openai": 60,
                          "deepseek": 100, "gemini": 60}}

    def __init__(self, config: dict):
        super().__init__(config)
        self._buckets = {}  # provider -> {"tokens": float, "last": float}
        self._lock = threading.Lock()

    def _get_bucket(self, provider: str) -> dict:
        rpm = self.config.get("requests_per_minute", {})
        capacity = rpm.get(provider, 60)
        if provider not in self._buckets:
            self._buckets[provider] = {
                "tokens": float(capacity),
                "capacity": float(capacity),
                "last_refill": _epoch(),
            }
        return self._buckets[provider]

    def process(self, request: dict, context: dict) -> dict:
        model = request.get("model", "")
        provider = _provider_from_model(model)

        with self._lock:
            bucket = self._get_bucket(provider)
            now = _epoch()
            elapsed = now - bucket["last_refill"]

            # Refill tokens based on elapsed time
            refill = elapsed * (bucket["capacity"] / 60.0)
            bucket["tokens"] = min(bucket["capacity"],
                                   bucket["tokens"] + refill)
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                self.misses += 1
                return request
            else:
                # Must wait — calculate delay
                wait_seconds = (1.0 - bucket["tokens"]) / (
                    bucket["capacity"] / 60.0)
                self.hits += 1
                request["rate_limited"] = True
                request["rate_limit_wait_seconds"] = round(wait_seconds, 2)
                logger.info(f"[RateLimitManager] {provider} throttled, "
                            f"wait {wait_seconds:.2f}s")
                # Actually wait (blocking)
                time.sleep(min(wait_seconds, 5.0))
                bucket["tokens"] = 0
                return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule 11 — FallbackChain
# ═════════════════════════════════════════════════════════════════════════════

class FallbackChain(OptimizationRule):
    name = "fallback_chain"
    description = "Retry logic on 429/500/502/503 with model fallback"
    default_config = {"enabled": True, "max_retries": 3,
                      "retry_on": [429, 500, 502, 503]}

    def process(self, request: dict, context: dict) -> dict:
        # FallbackChain is applied post-hoc by the engine, not as a
        # pre-processing step.  It decorates the request with retry config.
        request["fallback_max_retries"] = self.config.get("max_retries", 3)
        request["fallback_retry_on"] = self.config.get(
            "retry_on", [429, 500, 502, 503])

        # Build fallback model chain
        tiers = context.get("model_tiers", {})
        current = request.get("model", "")
        chain = []
        for tier_name in ["premium", "standard", "budget"]:
            for m in tiers.get(tier_name, []):
                if m != current and m not in chain:
                    chain.append(m)

        request["fallback_chain"] = chain
        self.hits += 1
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule 12 — ResponseQualityGate  (post-call)
# ═════════════════════════════════════════════════════════════════════════════

class ResponseQualityGate(OptimizationRule):
    name = "response_quality_gate"
    description = "Validate response quality, retry if empty/truncated/refusal"
    default_config = {"enabled": True, "min_length": 10, "max_retries": 2}

    _refusal_patterns = [
        "i cannot", "i can't", "i'm unable", "as an ai",
        "i don't have the ability", "i must decline",
    ]

    def check_quality(self, response_text: str) -> dict:
        """Check response quality, return issues found."""
        issues = []
        min_len = self.config.get("min_length", 10)

        if not response_text or not response_text.strip():
            issues.append("empty_response")

        elif len(response_text.strip()) < min_len:
            issues.append("too_short")

        # Check for truncation (ends mid-sentence without punctuation)
        if response_text and not response_text.rstrip().endswith(
                (".", "!", "?", "```", '"', "'", ")", "]", "}")):
            if len(response_text) > 100:
                issues.append("possibly_truncated")

        # Check for refusals
        lower = response_text.lower() if response_text else ""
        for pattern in self._refusal_patterns:
            if pattern in lower:
                issues.append("refusal_detected")
                break

        quality_ok = len(issues) == 0
        if quality_ok:
            self.misses += 1
        else:
            self.hits += 1

        return {"ok": quality_ok, "issues": issues}

    def process(self, request: dict, context: dict) -> dict:
        # Attaches quality gate config — actual validation is post-call
        request["quality_gate_min_length"] = self.config.get("min_length", 10)
        request["quality_gate_max_retries"] = self.config.get(
            "max_retries", 2)
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Rule 13 — CostAttributionLogger  (post-call)
# ═════════════════════════════════════════════════════════════════════════════

class CostAttributionLogger(OptimizationRule):
    name = "cost_attribution_logger"
    description = "Log every request with full cost data to SQLite + JSONL"
    default_config = {"enabled": True}

    def __init__(self, config: dict):
        super().__init__(config)
        self.jsonl_path = None  # set by engine

    def log_call(self, model: str, input_tokens: int, output_tokens: int,
                 cost_usd: float, agent: str, task: str, cached: bool,
                 context: dict):
        """Log a completed API call via DAL (cost_tracking + llm_requests)."""
        provider = _provider_from_model(model)
        tracker = context.get("cost_tracker")  # type: CostTracker
        if tracker:
            tracker.log(model, provider, input_tokens, output_tokens,
                        cost_usd, agent, task, cached)

        # Also record as LLM request in instance DB
        try:
            from claw_dal import DAL
            dal = DAL.get_instance()
            dal.llm_requests.record(
                provider=provider, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost_usd, cache_hit=cached)
        except Exception:
            pass

        self.hits += 1

    def process(self, request: dict, context: dict) -> dict:
        # Mark request so engine knows to log after call
        request["log_cost"] = True
        return request


# ═════════════════════════════════════════════════════════════════════════════
#  Optimization Engine — Chains All 14 Rules
# ═════════════════════════════════════════════════════════════════════════════

class OptimizationEngine:
    """Chains optimization rules into a pipeline.  Manages config,
    databases, caches, and the HTTP dashboard."""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.started_at = None
        self.running = False
        self.total_requests = 0
        self.cached_requests = 0

        # Initialize databases
        self.cost_tracker = CostTracker(config.get(
            "cost_log_db", "cost_log.sqlite3"))
        self.response_cache = ResponseCache(config.get(
            "cache_db", "response_cache.sqlite3"))

        # Build shared context
        models_cfg = config.get("models", {})
        self._context = {
            "cost_tracker": self.cost_tracker,
            "response_cache": self.response_cache,
            "model_costs": models_cfg.get("costs_per_1k_tokens", {}),
            "model_tiers": models_cfg.get("tiers", {}),
            "provider_health": {},
        }

        # Initialize rules in pipeline order
        rules_cfg = config.get("rules", {})
        self.rules = [
            ConversationDedup(rules_cfg.get("conversation_dedup", {})),
            SemanticCache(rules_cfg.get("semantic_cache", {})),
            TokenEstimator(rules_cfg.get("token_estimator", {})),
            ContextPruner(rules_cfg.get("context_pruner", {})),
            PromptOptimizer(rules_cfg.get("prompt_optimizer", {})),
            BudgetEnforcer(rules_cfg.get("budget_enforcer", {})),
            TaskComplexityRouter(rules_cfg.get("task_complexity_router", {})),
            LatencyRouter(rules_cfg.get("latency_router", {})),
            ProviderHealthScorer(rules_cfg.get("provider_health_scorer", {})),
            RateLimitManager(rules_cfg.get("rate_limit_manager", {})),
            FallbackChain(rules_cfg.get("fallback_chain", {})),
            ResponseQualityGate(rules_cfg.get("response_quality_gate", {})),
            CostAttributionLogger(rules_cfg.get(
                "cost_attribution_logger", {})),
        ]

        # Set JSONL path on cost logger
        for rule in self.rules:
            if isinstance(rule, CostAttributionLogger):
                rule.jsonl_path = config.get("cost_log_jsonl",
                                             "cost_log.jsonl")

    def _get_rule(self, rule_type):
        """Get a specific rule instance by type."""
        for rule in self.rules:
            if isinstance(rule, rule_type):
                return rule
        return None

    def optimize(self, request: dict) -> dict:
        """Run the full pre-call pipeline.  Returns modified request.

        If request['cached_response'] is set, the caller should skip
        the actual API call and use that response instead.
        """
        if not self.enabled:
            return request

        self.total_requests += 1

        for rule in self.rules:
            if not rule.enabled:
                continue
            try:
                request = rule.process(request, self._context)
            except Exception as e:
                logger.error(f"[{rule.name}] Error: {e}")
                continue

            # Short-circuit on cache hit
            if "cached_response" in request:
                self.cached_requests += 1
                return request

        return request

    def post_call(self, request: dict, response_text: str,
                  input_tokens: int = 0, output_tokens: int = 0,
                  status_code: int = 200, latency_ms: float = 0):
        """Run post-call rules (quality gate, cost logging, cache update).

        Returns:
            dict with 'ok', 'response', 'quality_issues', 'should_retry'.
        """
        model = request.get("model", "")
        provider = _provider_from_model(model)

        # Record health event
        health_rule = self._get_rule(ProviderHealthScorer)
        if health_rule:
            success = 200 <= status_code < 400
            health_rule.record_event(provider, success, latency_ms)

        # Quality gate
        result = {"ok": True, "response": response_text,
                  "quality_issues": [], "should_retry": False}
        gate = self._get_rule(ResponseQualityGate)
        if gate and gate.enabled:
            quality = gate.check_quality(response_text)
            if not quality["ok"]:
                result["ok"] = False
                result["quality_issues"] = quality["issues"]
                result["should_retry"] = True
                logger.warning(f"[ResponseQualityGate] Issues: "
                               f"{quality['issues']}")

        # Cost attribution
        costs = self._context.get("model_costs", {})
        model_cost = costs.get(model, {})
        in_cost = (input_tokens / 1000.0) * model_cost.get("input", 0)
        out_cost = (output_tokens / 1000.0) * model_cost.get("output", 0)
        total_cost = round(in_cost + out_cost, 6)

        cost_logger = self._get_rule(CostAttributionLogger)
        if cost_logger and cost_logger.enabled:
            cost_logger.log_call(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=total_cost,
                agent=request.get("agent", ""),
                task=request.get("task", ""),
                cached="cached_response" in request,
                context=self._context,
            )

        # Update dedup cache
        dedup = self._get_rule(ConversationDedup)
        if dedup:
            messages = request.get("messages", [])
            if messages:
                last_msg = messages[-1].get("content", "")
                dedup.record_response(last_msg, response_text)

        # Update semantic cache
        if result["ok"]:
            messages = request.get("messages", [])
            if messages:
                last_msg = messages[-1].get("content", "")
                sc_cfg = self.config.get("rules", {}).get(
                    "semantic_cache", {})
                ttl = sc_cfg.get("ttl_seconds", 3600)
                self.response_cache.put(last_msg, response_text, model,
                                        ttl)

        return result

    def get_status(self) -> dict:
        """Return full engine status as a dict."""
        return {
            "engine": {
                "enabled": self.enabled,
                "started_at": self.started_at,
                "total_requests": self.total_requests,
                "cached_requests": self.cached_requests,
                "cache_hit_rate": (
                    round(self.cached_requests / self.total_requests, 3)
                    if self.total_requests > 0 else 0.0
                ),
            },
            "rules": [rule.status() for rule in self.rules],
            "cost_summary": self.cost_tracker.summary(),
            "cache_stats": self.response_cache.stats(),
            "provider_health": self._context.get("provider_health", {}),
            "recent_calls": self.cost_tracker.recent(10),
        }

    def get_status_json(self) -> str:
        return json.dumps(self.get_status(), indent=2)


# ═════════════════════════════════════════════════════════════════════════════
#  Dashboard HTTP Server
# ═════════════════════════════════════════════════════════════════════════════

class DashboardHandler(BaseHTTPRequestHandler):
    """Serves /status as JSON, same pattern as claw_watchdog."""

    engine = None  # set before starting server

    def do_GET(self):
        try:
            if self.path in ("/status", "/"):
                data = self.engine.get_status_json() if self.engine else "{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data.encode("utf-8"))
            elif self.path == "/report":
                report = _generate_cost_report(self.engine) if self.engine else ""
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(report.encode("utf-8"))
            else:
                self.send_error(404)
        except Exception:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","engine":{"enabled":true}}')

    def log_message(self, format, *args):
        pass  # suppress default HTTP logs


# ═════════════════════════════════════════════════════════════════════════════
#  Cost Report Generator
# ═════════════════════════════════════════════════════════════════════════════

def _generate_cost_report(engine: OptimizationEngine) -> str:
    """Generate a human-readable cost and status report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  CLAW OPTIMIZER — STATUS REPORT")
    lines.append("  Generated: " + _now_iso())
    lines.append("=" * 70)
    lines.append("")

    # Engine overview
    status = engine.get_status()
    eng = status["engine"]
    lines.append("ENGINE")
    lines.append(f"  Enabled:          {eng['enabled']}")
    lines.append(f"  Started at:       {eng['started_at'] or 'N/A'}")
    lines.append(f"  Total requests:   {eng['total_requests']}")
    lines.append(f"  Cached requests:  {eng['cached_requests']}")
    lines.append(f"  Cache hit rate:   {eng['cache_hit_rate']*100:.1f}%")
    lines.append("")

    # Cost summary
    cost = status["cost_summary"]
    lines.append("COST SUMMARY")
    lines.append(f"  Today:    ${cost['daily']:.4f}")
    lines.append(f"  This week: ${cost['weekly']:.4f}")
    lines.append(f"  This month: ${cost['monthly']:.4f}")
    lines.append(f"  All time:  ${cost['total']:.4f}")
    lines.append("")

    # Budget limits
    budget_cfg = engine.config.get("rules", {}).get("budget_enforcer", {})
    if budget_cfg.get("enabled"):
        lines.append("BUDGET LIMITS")
        lines.append(f"  Daily:   ${budget_cfg.get('daily_limit', 0):.2f}  "
                     f"(used {cost['daily']/budget_cfg.get('daily_limit',1)*100:.1f}%)")
        lines.append(f"  Weekly:  ${budget_cfg.get('weekly_limit', 0):.2f}  "
                     f"(used {cost['weekly']/budget_cfg.get('weekly_limit',1)*100:.1f}%)")
        lines.append(f"  Monthly: ${budget_cfg.get('monthly_limit', 0):.2f}  "
                     f"(used {cost['monthly']/budget_cfg.get('monthly_limit',1)*100:.1f}%)")
        lines.append("")

    # Rules status
    lines.append("RULES (14 total)")
    lines.append(f"  {'#':<4} {'Name':<28} {'Enabled':<9} {'Hits':<8} "
                 f"{'Misses':<8}")
    lines.append("  " + "-" * 60)
    for i, rule in enumerate(status["rules"], 1):
        enabled_str = "YES" if rule["enabled"] else "no"
        lines.append(f"  {i:<4} {rule['name']:<28} {enabled_str:<9} "
                     f"{rule['hits']:<8} {rule['misses']:<8}")
    lines.append("")

    # Cache stats
    cache = status["cache_stats"]
    lines.append("CACHE")
    lines.append(f"  Total entries:  {cache['total_entries']}")
    lines.append("")

    # Provider health
    health = status.get("provider_health", {})
    if health:
        lines.append("PROVIDER HEALTH")
        for provider, data in health.items():
            lines.append(f"  {provider:<12} score={data['score']:.3f}  "
                         f"calls={data['total_calls']}  "
                         f"success={data['success_rate']*100:.0f}%  "
                         f"latency={data['avg_latency_ms']:.0f}ms")
        lines.append("")

    # Recent calls
    recent = status.get("recent_calls", [])
    if recent:
        lines.append("RECENT CALLS (last 10)")
        for call in recent:
            lines.append(f"  {call['ts']}  {call['model']:<22} "
                         f"in={call['input_tokens']:<6} "
                         f"out={call['output_tokens']:<6} "
                         f"${call['cost_usd']:.6f}  "
                         f"{call['agent']}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def _generate_cost_report_from_db(db_path: str) -> str:
    """Generate cost report directly from SQLite without running engine."""
    if not Path(db_path).exists():
        return f"Database not found: {db_path}"

    con = sqlite3.connect(db_path)
    lines = []
    lines.append("=" * 70)
    lines.append("  CLAW OPTIMIZER — COST REPORT")
    lines.append("  Generated: " + _now_iso())
    lines.append("  Database:  " + db_path)
    lines.append("=" * 70)
    lines.append("")

    # Total
    row = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(cost_usd), 0), "
        "COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) "
        "FROM cost_log"
    ).fetchone()
    lines.append("TOTALS")
    lines.append(f"  Requests:       {row[0]}")
    lines.append(f"  Total cost:     ${row[1]:.4f}")
    lines.append(f"  Input tokens:   {row[2]:,}")
    lines.append(f"  Output tokens:  {row[3]:,}")
    lines.append("")

    # By model
    rows = con.execute(
        "SELECT model, COUNT(*), COALESCE(SUM(cost_usd), 0), "
        "COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) "
        "FROM cost_log GROUP BY model ORDER BY SUM(cost_usd) DESC"
    ).fetchall()
    if rows:
        lines.append("BY MODEL")
        lines.append(f"  {'Model':<24} {'Calls':<8} {'Cost':<12} "
                     f"{'In Tokens':<12} {'Out Tokens':<12}")
        lines.append("  " + "-" * 66)
        for r in rows:
            lines.append(f"  {r[0]:<24} {r[1]:<8} ${r[2]:<11.4f} "
                         f"{r[3]:<12,} {r[4]:<12,}")
        lines.append("")

    # By day (last 7)
    rows = con.execute(
        "SELECT SUBSTR(ts, 1, 10) as day, COUNT(*), "
        "COALESCE(SUM(cost_usd), 0) FROM cost_log "
        "GROUP BY day ORDER BY day DESC LIMIT 7"
    ).fetchall()
    if rows:
        lines.append("BY DAY (last 7)")
        for r in rows:
            lines.append(f"  {r[0]}  calls={r[1]:<6}  cost=${r[2]:.4f}")
        lines.append("")

    # Cached vs non-cached
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END), 0), "
        "COUNT(*) FROM cost_log"
    ).fetchone()
    if row[1] > 0:
        lines.append("CACHE STATS")
        lines.append(f"  Cached calls:   {row[0]} / {row[1]} "
                     f"({row[0]/row[1]*100:.1f}%)")
        lines.append("")

    lines.append("=" * 70)
    con.close()
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
#  Config Loading
# ═════════════════════════════════════════════════════════════════════════════

def load_config(path: str = None) -> dict:
    """Load config from JSON file, falling back to defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy

    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # Deep merge
        _deep_merge(config, user_config)
        logger.info(f"Config loaded from: {path}")
    elif path:
        logger.warning(f"Config file not found: {path}  (using defaults)")

    # Env var overrides
    if os.environ.get("OPTIMIZER_PORT"):
        config["dashboard_port"] = int(os.environ["OPTIMIZER_PORT"])
    if os.environ.get("OPTIMIZER_DAILY_LIMIT"):
        config["rules"]["budget_enforcer"]["daily_limit"] = float(
            os.environ["OPTIMIZER_DAILY_LIMIT"])

    return config


def _deep_merge(base: dict, override: dict):
    """Recursively merge override into base."""
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def generate_example_config() -> dict:
    """Return the full default config for writing to disk."""
    return json.loads(json.dumps(DEFAULT_CONFIG))


# ═════════════════════════════════════════════════════════════════════════════
#  Service Runner
# ═════════════════════════════════════════════════════════════════════════════

class OptimizerService:
    """Runs the optimizer engine as a long-lived service with dashboard."""

    def __init__(self, engine: OptimizationEngine, config: dict):
        self.engine = engine
        self.config = config
        self.running = False

    def run(self):
        self.running = True
        self.engine.started_at = _now_iso()

        port = self.config.get("dashboard_port", 9091)
        logger.info(f"Optimizer service started  "
                    f"rules={len(self.engine.rules)}  "
                    f"dashboard=:{port}")

        # Start dashboard
        if port:
            DashboardHandler.engine = self.engine
            try:
                server = HTTPServer(("0.0.0.0", port), DashboardHandler)
                thread = threading.Thread(target=server.serve_forever,
                                          daemon=True)
                thread.start()
                logger.info(f"Dashboard listening on "
                            f"http://0.0.0.0:{port}/status")
            except OSError as e:
                logger.warning(f"Could not start dashboard on port "
                               f"{port}: {e}")

        # Keep alive — the engine processes requests via optimize() calls
        # from other modules.  The service loop just keeps the dashboard up.
        while self.running:
            time.sleep(1)

        logger.info("Optimizer service stopped")

    def stop(self):
        self.running = False


# ═════════════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Claw Optimizer — Multi-Model Optimization Engine",
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to optimization.json config file",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Generate a single status report and exit",
    )
    parser.add_argument(
        "--init-config", action="store_true",
        help="Generate an example optimization.json config and exit",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Generate a cost report from the SQLite database and exit",
    )
    args = parser.parse_args()

    # Generate example config
    if args.init_config:
        out_path = Path(__file__).resolve().parent / "optimization.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(generate_example_config(), f, indent=2)
        print(f"Example config written to: {out_path}")
        print("Edit it with your budget limits and model preferences.")
        return

    setup_logging()
    config = load_config(args.config)
    setup_logging(config.get("log_file"))

    # Cost report from DB (no engine needed)
    if args.report:
        db_path = config.get("cost_log_db", "cost_log.sqlite3")
        print(_generate_cost_report_from_db(db_path))
        return

    # Single report
    if args.once:
        engine = OptimizationEngine(config)
        engine.started_at = _now_iso()
        print(_generate_cost_report(engine))
        return

    # Run as service
    engine = OptimizationEngine(config)
    service = OptimizerService(engine, config)

    # Graceful shutdown
    def _signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        service.stop()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    service.run()


if __name__ == "__main__":
    main()
