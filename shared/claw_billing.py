#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Cost Analytics & Alerting
=============================================================================
Tracks API usage costs across local and cloud models.  Parses usage records,
calculates per-request and aggregate costs, generates reports, and emits
console alerts when configurable spend thresholds are exceeded.

Features:
  - Usage Tracking:   Append-only JSONL log of every inference request
  - Cost Calculation:  Cloud API pricing (per-token) + local electricity estimates
  - Reports:          Daily / weekly / monthly cost summaries
  - Alerts:           Configurable spend thresholds with console warnings
  - Forecasting:      Linear extrapolation of current spend rate
  - Budget Alerts:    Env-var-driven budget limits with INFO/WARNING/CRITICAL levels
  - Webhook Notify:   Optional webhook POST when budget thresholds are crossed

Data files:
  data/billing/usage_log.jsonl       — per-request usage records (append-only)
  data/billing/billing_config.json   — pricing overrides, thresholds, settings
  data/billing/reports/              — generated report snapshots (JSON)

Usage:
  python3 shared/claw_billing.py --report [daily|weekly|monthly]
  python3 shared/claw_billing.py --forecast
  python3 shared/claw_billing.py --set-threshold 100.00
  python3 shared/claw_billing.py --status
  python3 shared/claw_billing.py --log --model claude-sonnet-4-6 --input-tokens 1500 --output-tokens 800
  python3 shared/claw_billing.py --init-config
  python3 shared/claw_billing.py --budget              # Budget status summary
  python3 shared/claw_billing.py --alerts              # Active budget alerts (JSON)

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "billing"
USAGE_LOG_FILE = DATA_DIR / "usage_log.jsonl"
BILLING_CONFIG_FILE = DATA_DIR / "billing_config.json"
REPORTS_DIR = DATA_DIR / "reports"

# Budget thresholds (env-var driven)
BUDGET_WARN_THRESHOLD = float(
    os.environ.get("CLAW_BUDGET_WARN_THRESHOLD", "0.80")
)
BUDGET_HARD_LIMIT = float(
    os.environ.get("CLAW_BUDGET_HARD_LIMIT", "100.0")
)
BUDGET_WEBHOOK_URL = os.environ.get("CLAW_BUDGET_WEBHOOK_URL", "")

_logger = logging.getLogger("claw_billing")

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
    print(f"{GREEN}[billing]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[billing]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[billing]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[billing]{NC} {msg}")


# -------------------------------------------------------------------------
# Cloud pricing — per million tokens (same as claw_strategy.py)
# -------------------------------------------------------------------------
CLOUD_PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-4-6":          {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":        {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":         {"input": 0.80,  "output": 4.0},
    "gpt-4.1":                  {"input": 2.0,   "output": 8.0},
    "gpt-4.1-mini":             {"input": 0.40,  "output": 1.60},
    "o3-mini":                  {"input": 1.10,  "output": 4.40},
    "deepseek-chat":            {"input": 0.14,  "output": 0.28},
    "deepseek-reasoner":        {"input": 0.55,  "output": 2.19},
    "gemini-2.0-flash":         {"input": 0.10,  "output": 0.40},
    "gemini-2.5-pro":           {"input": 1.25,  "output": 10.0},
    "llama-3.3-70b-versatile":  {"input": 0.59,  "output": 0.79},
    "mixtral-8x7b-32768":       {"input": 0.24,  "output": 0.24},
}

# Local inference electricity cost defaults
LOCAL_ELECTRICITY_RATE = 0.12   # $/kWh default
LOCAL_GPU_WATTS = {"idle": 30, "inference": 150}  # approximate GPU power draw

# Provider lookup by model prefix (for auto-detection)
MODEL_PROVIDER_MAP: Dict[str, str] = {
    "claude":   "anthropic",
    "gpt":      "openai",
    "o3":       "openai",
    "deepseek": "deepseek",
    "gemini":   "google",
    "llama":    "groq",
    "mixtral":  "groq",
}


def _detect_provider(model: str) -> str:
    """Best-effort provider detection from model ID."""
    for prefix, provider in MODEL_PROVIDER_MAP.items():
        if model.startswith(prefix):
            return provider
    return "unknown"


# -------------------------------------------------------------------------
# Directory bootstrapping
# -------------------------------------------------------------------------
def _ensure_dirs() -> None:
    """Create data/billing/ and data/billing/reports/ if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------------
# UsageLogger — append records to JSONL
# -------------------------------------------------------------------------
class UsageLogger:
    """Usage logger backed by DAL.  Falls back to JSONL file if DAL unavailable."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or USAGE_LOG_FILE
        self._dal = None
        try:
            from claw_dal import DAL
            self._dal = DAL.get_instance()
        except (ImportError, RuntimeError, OSError):
            pass
        _ensure_dirs()

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        response_time_ms: int = 0,
        agent_id: str = "",
        task_type: str = "",
        request_type: str = "",
        provider: str = "",
    ) -> Dict[str, Any]:
        """Write a single usage record. Returns the record dict."""
        if not provider:
            provider = _detect_provider(model)

        is_local = model not in CLOUD_PRICING
        record = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": model,
            "provider": provider,
            "type": "local" if is_local else "cloud",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "response_time_ms": response_time_ms,
            "agent_id": agent_id,
            "task_type": task_type,
        }
        if request_type:
            record["request_type"] = request_type

        # Write to DAL
        if self._dal:
            calculator = CostCalculator()
            cost = calculator.cost_for_record(record)
            self._dal.costs.record_cost(
                agent_id=agent_id or "billing",
                model=model, provider=provider,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost, avg_latency_ms=float(response_time_ms))
        else:
            # Fallback: JSONL
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

        # Auto-check budget after every recorded cost
        self._auto_check_budget()

        return record

    def _auto_check_budget(self) -> List["BudgetAlert"]:
        """Run a budget check against all recorded spend.

        Called automatically after each record() to detect threshold crossings
        as they happen.  Returns the list of alerts (if any).
        """
        try:
            all_records = self.read_all()
            calculator = CostCalculator()
            agg = calculator.aggregate(all_records)
            current_spend = agg["total_cost"]

            monitor = BudgetMonitor()
            return monitor.check_budget(current_spend)
        except (ValueError, KeyError, OSError, RuntimeError) as exc:
            _logger.debug(f"Auto budget check skipped: {exc}")
            return []

    def read_all(self) -> List[Dict[str, Any]]:
        """Read all records — from DAL or JSONL fallback."""
        if self._dal:
            rows = self._dal.costs.recent(limit=10000)
            return [
                {"timestamp": r.get("timestamp", ""), "model": r.get("model", ""),
                 "provider": r.get("provider", ""), "type": "cloud",
                 "input_tokens": r.get("input_tokens", 0),
                 "output_tokens": r.get("output_tokens", 0),
                 "response_time_ms": int(r.get("avg_latency_ms", 0)),
                 "agent_id": r.get("agent_id", ""), "task_type": ""}
                for r in rows
            ]
        records: List[Dict[str, Any]] = []
        if not self.log_path.exists():
            return records
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def read_range(
        self, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        """Read records within a time range (inclusive)."""
        all_records = self.read_all()
        filtered: List[Dict[str, Any]] = []
        for rec in all_records:
            ts_str = rec.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if start <= ts <= end:
                filtered.append(rec)
        return filtered

    def record_count(self) -> int:
        """Count total records without loading all into memory."""
        if self._dal:
            agg = self._dal.costs.aggregate()
            return agg.get("total_requests", 0)
        if not self.log_path.exists():
            return 0
        count = 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count


# -------------------------------------------------------------------------
# CostCalculator — compute costs from usage records
# -------------------------------------------------------------------------
class CostCalculator:
    """Calculates costs from usage records using cloud pricing tables
    and local electricity estimates."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        # Allow pricing overrides via config
        self.pricing = dict(CLOUD_PRICING)
        overrides = self.config.get("pricing_overrides", {})
        for model_id, rates in overrides.items():
            self.pricing[model_id] = rates

        self.electricity_rate = self.config.get(
            "electricity_rate", LOCAL_ELECTRICITY_RATE
        )
        self.gpu_watts = self.config.get("gpu_watts", dict(LOCAL_GPU_WATTS))

    def cost_for_record(self, record: Dict[str, Any]) -> float:
        """Calculate the cost of a single usage record in USD."""
        model = record.get("model", "")
        input_tokens = record.get("input_tokens", 0)
        output_tokens = record.get("output_tokens", 0)
        rec_type = record.get("type", "cloud")

        if rec_type == "local":
            return self._local_cost(record)

        rates = self.pricing.get(model)
        if not rates:
            return 0.0

        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        return input_cost + output_cost

    def _local_cost(self, record: Dict[str, Any]) -> float:
        """Estimate electricity cost for a local inference request."""
        response_ms = record.get("response_time_ms", 0)
        if response_ms <= 0:
            return 0.0

        inference_watts = self.gpu_watts.get("inference", 150)
        hours = response_ms / 1_000 / 3600
        kwh = (inference_watts / 1000) * hours
        return kwh * self.electricity_rate

    def aggregate(
        self, records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate aggregate cost metrics for a list of records."""
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_requests = len(records)
        cost_by_model: Dict[str, float] = {}
        cost_by_provider: Dict[str, float] = {}
        cost_by_agent: Dict[str, float] = {}
        cost_by_task: Dict[str, float] = {}
        tokens_by_model: Dict[str, Dict[str, int]] = {}
        cloud_cost = 0.0
        local_cost = 0.0
        total_response_ms = 0

        for rec in records:
            cost = self.cost_for_record(rec)
            total_cost += cost
            model = rec.get("model", "unknown")
            provider = rec.get("provider", "unknown")
            agent = rec.get("agent_id", "unknown")
            task = rec.get("task_type", "unknown")
            inp = rec.get("input_tokens", 0)
            out = rec.get("output_tokens", 0)
            resp_ms = rec.get("response_time_ms", 0)

            total_input_tokens += inp
            total_output_tokens += out
            total_response_ms += resp_ms

            cost_by_model[model] = cost_by_model.get(model, 0.0) + cost
            cost_by_provider[provider] = cost_by_provider.get(provider, 0.0) + cost
            if agent:
                cost_by_agent[agent] = cost_by_agent.get(agent, 0.0) + cost
            if task:
                cost_by_task[task] = cost_by_task.get(task, 0.0) + cost

            if model not in tokens_by_model:
                tokens_by_model[model] = {"input": 0, "output": 0, "requests": 0}
            tokens_by_model[model]["input"] += inp
            tokens_by_model[model]["output"] += out
            tokens_by_model[model]["requests"] += 1

            if rec.get("type") == "local":
                local_cost += cost
            else:
                cloud_cost += cost

        avg_response_ms = (
            total_response_ms / total_requests if total_requests > 0 else 0
        )

        return {
            "total_cost": round(total_cost, 6),
            "cloud_cost": round(cloud_cost, 6),
            "local_cost": round(local_cost, 6),
            "total_requests": total_requests,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "avg_response_ms": round(avg_response_ms, 1),
            "cost_by_model": {k: round(v, 6) for k, v in cost_by_model.items()},
            "cost_by_provider": {k: round(v, 6) for k, v in cost_by_provider.items()},
            "cost_by_agent": {k: round(v, 6) for k, v in cost_by_agent.items()},
            "cost_by_task": {k: round(v, 6) for k, v in cost_by_task.items()},
            "tokens_by_model": tokens_by_model,
        }


# -------------------------------------------------------------------------
# AlertManager — check thresholds, emit console warnings
# -------------------------------------------------------------------------
class AlertManager:
    """Checks spend against configurable thresholds and emits warnings."""

    DEFAULT_THRESHOLDS = {
        "daily": 10.0,
        "weekly": 50.0,
        "monthly": 100.0,
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        user_thresholds = self.config.get("thresholds", {})
        for period, amount in user_thresholds.items():
            if isinstance(amount, (int, float)):
                self.thresholds[period] = float(amount)

    def check(
        self,
        daily_cost: float,
        weekly_cost: float,
        monthly_cost: float,
    ) -> List[Dict[str, Any]]:
        """Check all thresholds. Returns list of triggered alerts."""
        alerts: List[Dict[str, Any]] = []

        checks = [
            ("daily", daily_cost),
            ("weekly", weekly_cost),
            ("monthly", monthly_cost),
        ]

        for period, actual in checks:
            threshold = self.thresholds.get(period, 0)
            if threshold <= 0:
                continue
            pct = (actual / threshold) * 100 if threshold > 0 else 0

            if actual >= threshold:
                alerts.append({
                    "level": "critical",
                    "period": period,
                    "actual": round(actual, 4),
                    "threshold": threshold,
                    "percent": round(pct, 1),
                    "message": (
                        f"OVER BUDGET: {period} spend ${actual:.4f} "
                        f"exceeds ${threshold:.2f} ({pct:.0f}%)"
                    ),
                })
            elif pct >= 80:
                alerts.append({
                    "level": "warning",
                    "period": period,
                    "actual": round(actual, 4),
                    "threshold": threshold,
                    "percent": round(pct, 1),
                    "message": (
                        f"APPROACHING LIMIT: {period} spend ${actual:.4f} "
                        f"is {pct:.0f}% of ${threshold:.2f}"
                    ),
                })

        return alerts

    def print_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Print alerts to console with color coding."""
        if not alerts:
            return
        print(f"\n{BOLD}{YELLOW}=== Billing Alerts ==={NC}\n")
        for alert in alerts:
            if alert["level"] == "critical":
                prefix = f"{RED}{BOLD}CRITICAL{NC}"
            else:
                prefix = f"{YELLOW}WARNING{NC}"
            print(f"  {prefix}  {alert['message']}")
        print()

    def set_threshold(self, monthly_amount: float) -> None:
        """Set the monthly threshold and derive daily/weekly from it."""
        self.thresholds["monthly"] = monthly_amount
        self.thresholds["weekly"] = round(monthly_amount / 4.33, 2)
        self.thresholds["daily"] = round(monthly_amount / 30, 2)


# -------------------------------------------------------------------------
# BudgetAlertLevel — severity enum for budget alerts
# -------------------------------------------------------------------------
class BudgetAlertLevel(str, Enum):
    """Budget alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# -------------------------------------------------------------------------
# BudgetAlert — a single budget alert instance
# -------------------------------------------------------------------------
class BudgetAlert:
    """Represents a single budget alert with level, message, and metadata."""

    def __init__(
        self,
        level: BudgetAlertLevel,
        message: str,
        current_spend: float,
        budget_limit: float,
        utilization_pct: float,
        timestamp: Optional[str] = None,
    ):
        self.level = level
        self.message = message
        self.current_spend = current_spend
        self.budget_limit = budget_limit
        self.utilization_pct = utilization_pct
        self.timestamp = timestamp or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize alert to a JSON-safe dict."""
        return {
            "level": self.level.value,
            "message": self.message,
            "current_spend": round(self.current_spend, 6),
            "budget_limit": round(self.budget_limit, 2),
            "utilization_pct": round(self.utilization_pct, 1),
            "timestamp": self.timestamp,
        }


# -------------------------------------------------------------------------
# BudgetMonitor — env-var-driven budget checking with webhook support
# -------------------------------------------------------------------------
class BudgetMonitor:
    """Monitors total spend against configurable budget thresholds.

    Thresholds are driven by environment variables:
      CLAW_BUDGET_WARN_THRESHOLD  — utilization fraction to trigger warn (default 0.80)
      CLAW_BUDGET_HARD_LIMIT      — absolute USD budget cap (default 100.0)
      CLAW_BUDGET_WEBHOOK_URL     — optional webhook URL for POST notifications
    """

    def __init__(
        self,
        warn_threshold: Optional[float] = None,
        hard_limit: Optional[float] = None,
        webhook_url: Optional[str] = None,
    ):
        self.warn_threshold = (
            warn_threshold if warn_threshold is not None else BUDGET_WARN_THRESHOLD
        )
        self.hard_limit = (
            hard_limit if hard_limit is not None else BUDGET_HARD_LIMIT
        )
        self.webhook_url = (
            webhook_url if webhook_url is not None else BUDGET_WEBHOOK_URL
        )
        self._notified_levels: Dict[str, bool] = {}

    def check_budget(
        self, current_spend: float
    ) -> List[BudgetAlert]:
        """Evaluate current spend against budget thresholds.

        Returns a list of BudgetAlert objects for every threshold crossed.
        Emits log warnings at 80%, 90%, and 100% of the budget limit.
        """
        alerts: List[BudgetAlert] = []

        if self.hard_limit <= 0:
            return alerts

        utilization = current_spend / self.hard_limit
        utilization_pct = utilization * 100

        # 100% — CRITICAL
        if utilization >= 1.0:
            alert = BudgetAlert(
                level=BudgetAlertLevel.CRITICAL,
                message=(
                    f"Budget exceeded: ${current_spend:.2f} "
                    f"of ${self.hard_limit:.2f} limit "
                    f"({utilization_pct:.1f}%)"
                ),
                current_spend=current_spend,
                budget_limit=self.hard_limit,
                utilization_pct=utilization_pct,
            )
            alerts.append(alert)
            _logger.critical(alert.message)

        # 90% — WARNING
        elif utilization >= 0.90:
            alert = BudgetAlert(
                level=BudgetAlertLevel.WARNING,
                message=(
                    f"Budget 90% utilized: ${current_spend:.2f} "
                    f"of ${self.hard_limit:.2f} limit "
                    f"({utilization_pct:.1f}%)"
                ),
                current_spend=current_spend,
                budget_limit=self.hard_limit,
                utilization_pct=utilization_pct,
            )
            alerts.append(alert)
            _logger.warning(alert.message)

        # 80% (configurable via warn_threshold) — INFO
        elif utilization >= self.warn_threshold:
            alert = BudgetAlert(
                level=BudgetAlertLevel.INFO,
                message=(
                    f"Budget {utilization_pct:.0f}% utilized: "
                    f"${current_spend:.2f} "
                    f"of ${self.hard_limit:.2f} limit"
                ),
                current_spend=current_spend,
                budget_limit=self.hard_limit,
                utilization_pct=utilization_pct,
            )
            alerts.append(alert)
            _logger.info(alert.message)

        # Fire webhook for WARNING and CRITICAL alerts
        if alerts and self.webhook_url:
            top_alert = alerts[0]
            if top_alert.level in (
                BudgetAlertLevel.WARNING,
                BudgetAlertLevel.CRITICAL,
            ):
                self._send_webhook(top_alert)

        return alerts

    def get_budget_status(
        self, current_spend: float
    ) -> Dict[str, Any]:
        """Return the current budget status as a JSON-safe dict.

        Suitable for the GET /billing/budget endpoint.
        """
        utilization_pct = (
            (current_spend / self.hard_limit * 100) if self.hard_limit > 0 else 0.0
        )
        alerts = self.check_budget(current_spend)

        return {
            "current_spend": round(current_spend, 6),
            "budget_limit": round(self.hard_limit, 2),
            "warn_threshold": round(self.warn_threshold, 2),
            "utilization_pct": round(utilization_pct, 1),
            "status": (
                "critical" if utilization_pct >= 100
                else "warning" if utilization_pct >= 90
                else "approaching" if utilization_pct >= self.warn_threshold * 100
                else "ok"
            ),
            "alerts": [a.to_dict() for a in alerts],
        }

    def get_alerts_response(
        self, current_spend: float
    ) -> Dict[str, Any]:
        """Return alert data as a JSON-safe dict.

        Suitable for the GET /billing/alerts endpoint.
        """
        alerts = self.check_budget(current_spend)
        utilization_pct = (
            (current_spend / self.hard_limit * 100) if self.hard_limit > 0 else 0.0
        )

        return {
            "alerts": [a.to_dict() for a in alerts],
            "current_spend": round(current_spend, 6),
            "budget_limit": round(self.hard_limit, 2),
            "utilization_pct": round(utilization_pct, 1),
        }

    def _send_webhook(self, alert: BudgetAlert) -> bool:
        """POST alert payload to the configured webhook URL.

        Returns True if the request succeeded, False otherwise.
        Uses only stdlib urllib (no external dependencies).
        """
        if not self.webhook_url:
            return False

        payload = json.dumps({
            "event": "budget_alert",
            "level": alert.level.value,
            "message": alert.message,
            "current_spend": round(alert.current_spend, 6),
            "budget_limit": round(alert.budget_limit, 2),
            "utilization_pct": round(alert.utilization_pct, 1),
            "timestamp": alert.timestamp,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError) as exc:
            _logger.error(f"Webhook POST failed: {exc}")
            return False


# -------------------------------------------------------------------------
# Forecaster — linear extrapolation
# -------------------------------------------------------------------------
class Forecaster:
    """Projects future spend based on observed spend rate."""

    def forecast(
        self, records: List[Dict[str, Any]], calculator: CostCalculator
    ) -> Dict[str, Any]:
        """Generate a spend forecast from usage records.

        Uses the observed daily spend rate (total cost / days spanned) to
        linearly extrapolate daily, weekly, and monthly projections.
        """
        if not records:
            return {
                "daily_rate": 0.0,
                "projected_daily": 0.0,
                "projected_weekly": 0.0,
                "projected_monthly": 0.0,
                "data_points": 0,
                "span_days": 0,
                "confidence": "none",
            }

        # Determine time span
        timestamps: List[datetime] = []
        for rec in records:
            ts_str = rec.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                timestamps.append(ts)
            except (ValueError, AttributeError):
                continue

        if not timestamps:
            return {
                "daily_rate": 0.0,
                "projected_daily": 0.0,
                "projected_weekly": 0.0,
                "projected_monthly": 0.0,
                "data_points": 0,
                "span_days": 0,
                "confidence": "none",
            }

        earliest = min(timestamps)
        latest = max(timestamps)
        span = (latest - earliest).total_seconds()
        span_days = max(span / 86400, 1.0 / 24)  # at least 1 hour

        agg = calculator.aggregate(records)
        total_cost = agg["total_cost"]
        daily_rate = total_cost / span_days

        # Confidence based on data volume
        if span_days >= 7 and len(records) >= 50:
            confidence = "high"
        elif span_days >= 2 and len(records) >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "daily_rate": round(daily_rate, 6),
            "projected_daily": round(daily_rate, 4),
            "projected_weekly": round(daily_rate * 7, 4),
            "projected_monthly": round(daily_rate * 30, 4),
            "data_points": len(records),
            "span_days": round(span_days, 2),
            "confidence": confidence,
            "total_observed": round(total_cost, 6),
        }


# -------------------------------------------------------------------------
# ReportGenerator — daily / weekly / monthly reports
# -------------------------------------------------------------------------
class ReportGenerator:
    """Generates cost reports for specified time periods."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = UsageLogger()
        self.calculator = CostCalculator(config)
        self.alert_manager = AlertManager(config)
        self.forecaster = Forecaster()
        _ensure_dirs()

    def _period_range(
        self, period: str
    ) -> Tuple[datetime, datetime]:
        """Return (start, end) datetime for the given period relative to now."""
        now = datetime.now(timezone.utc)
        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            weekday = now.weekday()  # Monday = 0
            start = (now - timedelta(days=weekday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now - timedelta(days=1)
        return start, now

    def generate(self, period: str = "daily") -> Dict[str, Any]:
        """Generate a cost report for the specified period."""
        start, end = self._period_range(period)
        records = self.logger.read_range(start, end)
        agg = self.calculator.aggregate(records)
        forecast = self.forecaster.forecast(records, self.calculator)

        # Also compute other periods for alert checking
        daily_start, _ = self._period_range("daily")
        weekly_start, _ = self._period_range("weekly")
        monthly_start, _ = self._period_range("monthly")

        daily_records = self.logger.read_range(daily_start, end)
        weekly_records = self.logger.read_range(weekly_start, end)
        monthly_records = self.logger.read_range(monthly_start, end)

        daily_agg = self.calculator.aggregate(daily_records)
        weekly_agg = self.calculator.aggregate(weekly_records)
        monthly_agg = self.calculator.aggregate(monthly_records)

        alerts = self.alert_manager.check(
            daily_cost=daily_agg["total_cost"],
            weekly_cost=weekly_agg["total_cost"],
            monthly_cost=monthly_agg["total_cost"],
        )

        report = {
            "report_type": period,
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "period_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": agg,
            "forecast": forecast,
            "alerts": alerts,
            "thresholds": self.alert_manager.thresholds,
            "period_totals": {
                "daily": round(daily_agg["total_cost"], 6),
                "weekly": round(weekly_agg["total_cost"], 6),
                "monthly": round(monthly_agg["total_cost"], 6),
            },
        }

        # Save report to disk
        report_filename = (
            f"report_{period}_{start.strftime('%Y%m%d')}.json"
        )
        report_path = REPORTS_DIR / report_filename
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report

    def print_report(self, report: Dict[str, Any]) -> None:
        """Pretty-print a report to the console with colors."""
        period = report.get("report_type", "unknown")
        summary = report.get("summary", {})
        forecast = report.get("forecast", {})
        alerts = report.get("alerts", [])
        period_totals = report.get("period_totals", {})

        print(
            f"\n{BOLD}{CYAN}=== Cost Analytics Report"
            f" — {period.upper()} ==={NC}\n"
        )
        print(
            f"  Period:    {report.get('period_start', '?')}"
            f"  to  {report.get('period_end', '?')}"
        )
        print(
            f"  Generated: {report.get('generated_at', '?')}"
        )
        print()

        # Cost summary
        print(f"{BOLD}Cost Summary:{NC}")
        total = summary.get("total_cost", 0)
        cloud = summary.get("cloud_cost", 0)
        local = summary.get("local_cost", 0)
        print(f"  Total cost:   {GREEN}${total:.6f}{NC}")
        print(f"  Cloud cost:   ${cloud:.6f}")
        print(f"  Local cost:   ${local:.6f}")
        print()

        # Usage stats
        print(f"{BOLD}Usage Statistics:{NC}")
        print(f"  Requests:      {summary.get('total_requests', 0)}")
        print(
            f"  Input tokens:  {summary.get('total_input_tokens', 0):,}"
        )
        print(
            f"  Output tokens: {summary.get('total_output_tokens', 0):,}"
        )
        print(
            f"  Avg response:  {summary.get('avg_response_ms', 0):.0f}ms"
        )
        print()

        # Period totals
        print(f"{BOLD}Period Totals:{NC}")
        print(f"  Today:      ${period_totals.get('daily', 0):.6f}")
        print(f"  This week:  ${period_totals.get('weekly', 0):.6f}")
        print(f"  This month: ${period_totals.get('monthly', 0):.6f}")
        print()

        # Cost by model (sorted descending)
        cost_by_model = summary.get("cost_by_model", {})
        if cost_by_model:
            print(f"{BOLD}Cost by Model:{NC}")
            sorted_models = sorted(
                cost_by_model.items(), key=lambda x: x[1], reverse=True
            )
            for model, cost in sorted_models:
                tokens_info = summary.get("tokens_by_model", {}).get(model, {})
                reqs = tokens_info.get("requests", 0)
                bar_width = max(
                    1,
                    int(
                        (cost / sorted_models[0][1]) * 20
                    ) if sorted_models[0][1] > 0 else 1,
                )
                bar = "#" * bar_width
                print(
                    f"  {model:<30} ${cost:.6f}"
                    f"  ({reqs} reqs)  {DIM}{bar}{NC}"
                )
            print()

        # Cost by provider
        cost_by_provider = summary.get("cost_by_provider", {})
        if cost_by_provider:
            print(f"{BOLD}Cost by Provider:{NC}")
            for prov, cost in sorted(
                cost_by_provider.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {prov:<20} ${cost:.6f}")
            print()

        # Cost by agent
        cost_by_agent = summary.get("cost_by_agent", {})
        if cost_by_agent:
            print(f"{BOLD}Cost by Agent:{NC}")
            for agent, cost in sorted(
                cost_by_agent.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {agent:<20} ${cost:.6f}")
            print()

        # Forecast
        if forecast and forecast.get("data_points", 0) > 0:
            confidence = forecast.get("confidence", "low")
            conf_color = (
                GREEN if confidence == "high"
                else YELLOW if confidence == "medium"
                else RED
            )
            print(f"{BOLD}Forecast:{NC}  {DIM}(confidence: {conf_color}{confidence}{NC}{DIM}){NC}")
            print(
                f"  Daily rate:        ${forecast.get('projected_daily', 0):.4f}/day"
            )
            print(
                f"  Projected weekly:  ${forecast.get('projected_weekly', 0):.4f}/week"
            )
            print(
                f"  Projected monthly: ${forecast.get('projected_monthly', 0):.4f}/month"
            )
            print(
                f"  Based on:          {forecast.get('data_points', 0)} data points"
                f" over {forecast.get('span_days', 0):.1f} days"
            )
            print()

        # Alerts
        self.alert_manager.print_alerts(alerts)

        # Thresholds
        thresholds = report.get("thresholds", {})
        if thresholds:
            print(f"{DIM}Thresholds:"
                  f"  daily=${thresholds.get('daily', 0):.2f}"
                  f"  weekly=${thresholds.get('weekly', 0):.2f}"
                  f"  monthly=${thresholds.get('monthly', 0):.2f}{NC}")
            print()


# -------------------------------------------------------------------------
# Status command
# -------------------------------------------------------------------------
def print_status(config: Optional[Dict] = None) -> None:
    """Show current period spend, top models, and alerts."""
    config = config or {}
    logger = UsageLogger()
    calculator = CostCalculator(config)
    alert_manager = AlertManager(config)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    all_records = logger.read_all()
    daily_records = logger.read_range(today_start, now)
    weekly_records = logger.read_range(week_start, now)
    monthly_records = logger.read_range(month_start, now)

    daily_agg = calculator.aggregate(daily_records)
    weekly_agg = calculator.aggregate(weekly_records)
    monthly_agg = calculator.aggregate(monthly_records)

    print(f"\n{BOLD}{CYAN}=== Billing Status ==={NC}\n")
    print(f"  Log file:      {USAGE_LOG_FILE}")
    print(f"  Total records: {len(all_records)}")
    print()

    # Period costs
    print(f"{BOLD}Current Spend:{NC}")
    print(f"  Today:      {GREEN}${daily_agg['total_cost']:.6f}{NC}"
          f"  ({daily_agg['total_requests']} requests)")
    print(f"  This week:  {GREEN}${weekly_agg['total_cost']:.6f}{NC}"
          f"  ({weekly_agg['total_requests']} requests)")
    print(f"  This month: {GREEN}${monthly_agg['total_cost']:.6f}{NC}"
          f"  ({monthly_agg['total_requests']} requests)")
    print()

    # Top models this month
    cost_by_model = monthly_agg.get("cost_by_model", {})
    if cost_by_model:
        print(f"{BOLD}Top Models (this month):{NC}")
        sorted_models = sorted(
            cost_by_model.items(), key=lambda x: x[1], reverse=True
        )[:5]
        for model, cost in sorted_models:
            tokens_info = monthly_agg.get("tokens_by_model", {}).get(model, {})
            reqs = tokens_info.get("requests", 0)
            inp = tokens_info.get("input", 0)
            out = tokens_info.get("output", 0)
            print(
                f"  {model:<30} ${cost:.6f}"
                f"  {reqs} reqs  {inp:,}in/{out:,}out tokens"
            )
        print()

    # Alerts
    alerts = alert_manager.check(
        daily_cost=daily_agg["total_cost"],
        weekly_cost=weekly_agg["total_cost"],
        monthly_cost=monthly_agg["total_cost"],
    )
    if alerts:
        alert_manager.print_alerts(alerts)
    else:
        print(f"  {GREEN}No active alerts.{NC}\n")

    # Thresholds
    print(f"{DIM}Thresholds:"
          f"  daily=${alert_manager.thresholds.get('daily', 0):.2f}"
          f"  weekly=${alert_manager.thresholds.get('weekly', 0):.2f}"
          f"  monthly=${alert_manager.thresholds.get('monthly', 0):.2f}{NC}\n")


# -------------------------------------------------------------------------
# Forecast command
# -------------------------------------------------------------------------
def print_forecast(config: Optional[Dict] = None) -> None:
    """Print a spend forecast to the console."""
    config = config or {}
    logger = UsageLogger()
    calculator = CostCalculator(config)
    alert_manager = AlertManager(config)

    # Use last 30 days of data for forecasting
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    records = logger.read_range(start, now)
    forecaster = Forecaster()
    forecast = forecaster.forecast(records, calculator)

    print(f"\n{BOLD}{CYAN}=== Spend Forecast ==={NC}\n")

    if forecast.get("data_points", 0) == 0:
        print(f"  {DIM}No usage data available. Log some requests first.{NC}\n")
        return

    confidence = forecast.get("confidence", "low")
    conf_color = (
        GREEN if confidence == "high"
        else YELLOW if confidence == "medium"
        else RED
    )

    print(f"  Data points:       {forecast['data_points']}")
    print(f"  Observation span:  {forecast['span_days']:.1f} days")
    print(f"  Total observed:    ${forecast['total_observed']:.6f}")
    print(f"  Confidence:        {conf_color}{confidence}{NC}")
    print()

    print(f"{BOLD}Projections:{NC}")
    daily = forecast.get("projected_daily", 0)
    weekly = forecast.get("projected_weekly", 0)
    monthly = forecast.get("projected_monthly", 0)

    monthly_threshold = alert_manager.thresholds.get("monthly", 0)

    print(f"  Daily:    ${daily:.4f}/day")
    print(f"  Weekly:   ${weekly:.4f}/week")
    print(f"  Monthly:  ${monthly:.4f}/month")
    print()

    if monthly_threshold > 0:
        pct = (monthly / monthly_threshold) * 100 if monthly_threshold else 0
        if pct >= 100:
            color = RED
        elif pct >= 80:
            color = YELLOW
        else:
            color = GREEN
        print(
            f"  Budget utilization: {color}{pct:.0f}%{NC}"
            f" of ${monthly_threshold:.2f}/month"
        )
        if pct >= 100:
            print(
                f"  {RED}{BOLD}Projected to exceed monthly budget!{NC}"
            )
        print()

    # Yearly extrapolation
    yearly = daily * 365
    print(f"{DIM}  Annualized: ${yearly:.2f}/year{NC}\n")


# -------------------------------------------------------------------------
# Budget status command
# -------------------------------------------------------------------------
def print_budget_status(config: Optional[Dict] = None) -> None:
    """Print budget status with utilization and active alerts."""
    config = config or {}
    logger = UsageLogger()
    calculator = CostCalculator(config)
    all_records = logger.read_all()
    agg = calculator.aggregate(all_records)
    current_spend = agg["total_cost"]

    monitor = BudgetMonitor()
    status = monitor.get_budget_status(current_spend)

    print(f"\n{BOLD}{CYAN}=== Budget Status ==={NC}\n")
    print(f"  Budget limit:      ${status['budget_limit']:.2f}")
    print(f"  Warn threshold:    {status['warn_threshold'] * 100:.0f}%")
    print(f"  Current spend:     {GREEN}${status['current_spend']:.6f}{NC}")

    util_pct = status["utilization_pct"]
    if util_pct >= 100:
        color = RED
    elif util_pct >= 90:
        color = YELLOW
    else:
        color = GREEN
    print(f"  Utilization:       {color}{util_pct:.1f}%{NC}")
    print(f"  Status:            {status['status'].upper()}")
    print()

    budget_alerts = status.get("alerts", [])
    if budget_alerts:
        print(f"{BOLD}Active Budget Alerts:{NC}")
        for alert in budget_alerts:
            if alert["level"] == "CRITICAL":
                prefix = f"{RED}{BOLD}CRITICAL{NC}"
            elif alert["level"] == "WARNING":
                prefix = f"{YELLOW}WARNING{NC}"
            else:
                prefix = f"{BLUE}INFO{NC}"
            print(f"  {prefix}  {alert['message']}")
        print()
    else:
        print(f"  {GREEN}No budget alerts.{NC}\n")


def print_alerts_json(config: Optional[Dict] = None) -> None:
    """Print active budget alerts as JSON (for API endpoint consumption)."""
    config = config or {}
    logger = UsageLogger()
    calculator = CostCalculator(config)
    all_records = logger.read_all()
    agg = calculator.aggregate(all_records)
    current_spend = agg["total_cost"]

    monitor = BudgetMonitor()
    response = monitor.get_alerts_response(current_spend)
    print(json.dumps(response, indent=2))


# -------------------------------------------------------------------------
# Config management
# -------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    """Load billing config from disk, falling back to defaults."""
    if BILLING_CONFIG_FILE.exists():
        try:
            with open(BILLING_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            warn(f"Could not parse {BILLING_CONFIG_FILE}, using defaults.")
    return {}


def init_config() -> None:
    """Generate a default billing config file."""
    _ensure_dirs()
    config = {
        "_comment": "Claw Billing Configuration",
        "thresholds": {
            "daily": 10.0,
            "weekly": 50.0,
            "monthly": 100.0,
        },
        "electricity_rate": LOCAL_ELECTRICITY_RATE,
        "gpu_watts": dict(LOCAL_GPU_WATTS),
        "pricing_overrides": {},
        "notes": (
            "Edit thresholds to set spend alerts. "
            "Add pricing_overrides to customize per-model rates. "
            "Run: python3 shared/claw_billing.py --status"
        ),
    }

    with open(BILLING_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    log(f"Config generated: {BILLING_CONFIG_FILE}")
    info("Edit thresholds, then run: python3 shared/claw_billing.py --status")


def set_threshold(amount: float) -> None:
    """Set the monthly spend threshold and save to config."""
    _ensure_dirs()
    config = load_config()
    alert_manager = AlertManager(config)
    alert_manager.set_threshold(amount)

    config["thresholds"] = alert_manager.thresholds

    with open(BILLING_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    log(f"Monthly threshold set to ${amount:.2f}")
    log(
        f"Derived thresholds:"
        f"  daily=${alert_manager.thresholds['daily']:.2f}"
        f"  weekly=${alert_manager.thresholds['weekly']:.2f}"
        f"  monthly=${alert_manager.thresholds['monthly']:.2f}"
    )


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------
def _print_usage() -> None:
    """Print CLI usage."""
    print(
        f"Usage: python3 shared/claw_billing.py [command]\n"
        f"\n"
        f"Commands:\n"
        f"  --report [daily|weekly|monthly]   Generate and print a cost report\n"
        f"  --forecast                        Show projected spend forecast\n"
        f"  --set-threshold <amount>          Set monthly spend threshold in USD\n"
        f"  --status                          Current spend, top models, alerts\n"
        f"  --log                             Log a usage record manually\n"
        f"     --model <model>                  Model ID (required)\n"
        f"     --input-tokens <n>               Input token count (required)\n"
        f"     --output-tokens <n>              Output token count (required)\n"
        f"     --response-time <ms>             Response time in ms (optional)\n"
        f"     --agent-id <id>                  Agent identifier (optional)\n"
        f"     --task-type <type>               Task type (optional)\n"
        f"     --provider <provider>            Provider override (optional)\n"
        f"  --init-config                     Generate billing_config.json template\n"
        f"  --budget                          Show budget status and utilization\n"
        f"  --alerts                          Print active budget alerts as JSON\n"
    )


def main() -> None:
    args = sys.argv[1:]

    if not args:
        _print_usage()
        sys.exit(1)

    action = args[0]
    config = load_config()

    if action == "--report":
        period = args[1] if len(args) > 1 else "daily"
        if period not in ("daily", "weekly", "monthly"):
            err(f"Invalid period: {period}. Use daily, weekly, or monthly.")
            sys.exit(1)
        gen = ReportGenerator(config)
        report = gen.generate(period)
        gen.print_report(report)
        log(f"Report saved to: {REPORTS_DIR}")

    elif action == "--forecast":
        print_forecast(config)

    elif action == "--set-threshold":
        if len(args) < 2:
            err("Usage: --set-threshold <amount>")
            sys.exit(1)
        try:
            amount = float(args[1])
        except ValueError:
            err(f"Invalid amount: {args[1]}")
            sys.exit(1)
        set_threshold(amount)

    elif action == "--status":
        print_status(config)

    elif action == "--log":
        # Parse --log sub-arguments
        model = ""
        input_tokens = 0
        output_tokens = 0
        response_time = 0
        agent_id = ""
        task_type = ""
        provider = ""

        i = 1
        while i < len(args):
            if args[i] == "--model" and i + 1 < len(args):
                model = args[i + 1]
                i += 2
            elif args[i] == "--input-tokens" and i + 1 < len(args):
                input_tokens = int(args[i + 1])
                i += 2
            elif args[i] == "--output-tokens" and i + 1 < len(args):
                output_tokens = int(args[i + 1])
                i += 2
            elif args[i] == "--response-time" and i + 1 < len(args):
                response_time = int(args[i + 1])
                i += 2
            elif args[i] == "--agent-id" and i + 1 < len(args):
                agent_id = args[i + 1]
                i += 2
            elif args[i] == "--task-type" and i + 1 < len(args):
                task_type = args[i + 1]
                i += 2
            elif args[i] == "--provider" and i + 1 < len(args):
                provider = args[i + 1]
                i += 2
            else:
                i += 1

        if not model:
            err("--log requires --model <model>")
            sys.exit(1)
        if input_tokens <= 0 and output_tokens <= 0:
            err("--log requires --input-tokens and/or --output-tokens > 0")
            sys.exit(1)

        usage_logger = UsageLogger()
        record = usage_logger.record(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_time_ms=response_time,
            agent_id=agent_id,
            task_type=task_type,
            provider=provider,
        )

        calculator = CostCalculator(config)
        cost = calculator.cost_for_record(record)

        log(
            f"Recorded: model={model}"
            f"  in={input_tokens} out={output_tokens}"
            f"  cost=${cost:.6f}"
        )

        # Check alerts after logging
        now = datetime.now(timezone.utc)
        today_start = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        daily = calculator.aggregate(
            usage_logger.read_range(today_start, now)
        )
        weekly = calculator.aggregate(
            usage_logger.read_range(week_start, now)
        )
        monthly = calculator.aggregate(
            usage_logger.read_range(month_start, now)
        )

        alert_manager = AlertManager(config)
        alerts = alert_manager.check(
            daily_cost=daily["total_cost"],
            weekly_cost=weekly["total_cost"],
            monthly_cost=monthly["total_cost"],
        )
        alert_manager.print_alerts(alerts)

    elif action == "--init-config":
        init_config()

    elif action == "--budget":
        print_budget_status(config)

    elif action == "--alerts":
        print_alerts_json(config)

    else:
        err(f"Unknown command: {action}")
        _print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
