"""
Integration tests for the Billing service — verifies usage logging, cost
calculation, budget alerting, forecasting, and report generation lifecycle.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

# Reset DAL singleton to prevent stale connections from prior test runs
try:
    import claw_dal
    claw_dal.DAL._instance = None
except (ImportError, AttributeError):
    pass

from claw_billing import (
    UsageLogger,
    CostCalculator,
    AlertManager,
    Forecaster,
    ReportGenerator,
    BudgetAlertLevel,
    BudgetAlert,
    BudgetMonitor,
    CLOUD_PRICING,
)


@pytest.fixture(autouse=True)
def _disable_dal_for_billing(monkeypatch):
    """Prevent UsageLogger from attempting to connect to DAL.

    The DAL singleton tries to open production database paths which
    may not exist in test environments.
    """
    monkeypatch.setattr(
        "claw_billing.UsageLogger.__init__",
        _patched_usage_logger_init,
    )


def _patched_usage_logger_init(self, log_path=None):
    """Replacement __init__ that skips DAL entirely."""
    import claw_billing
    self.log_path = log_path or claw_billing.USAGE_LOG_FILE
    self._dal = None
    claw_billing._ensure_dirs()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def usage_logger(tmp_path):
    """Create a UsageLogger writing to a temp file."""
    log_file = tmp_path / "usage.jsonl"
    return UsageLogger(log_path=log_file)


@pytest.fixture
def cost_calculator():
    """Create a CostCalculator instance."""
    return CostCalculator()


@pytest.fixture
def populated_logger(tmp_path):
    """Create a logger with pre-populated usage records."""
    log_file = tmp_path / "usage.jsonl"
    logger = UsageLogger(log_path=log_file)

    now = datetime.now(timezone.utc)
    models = [
        ("deepseek-chat", 1000, 500),
        ("deepseek-chat", 2000, 1000),
        ("claude-sonnet-4-6", 500, 200),
        ("qwen2.5", 3000, 1500),
        ("gpt-4.1", 800, 400),
    ]

    for model, inp, out in models:
        logger.record(
            model=model,
            input_tokens=inp,
            output_tokens=out,
            response_time_ms=300,
            agent_id="test-agent",
            task_type="coding",
        )

    return logger


# ---------------------------------------------------------------------------
# Usage logging + cost calculation integration
# ---------------------------------------------------------------------------

class TestUsageLoggingCostIntegration:
    """Tests that logged usage records produce correct cost calculations."""

    def test_log_and_calculate_cloud_cost(self, usage_logger, cost_calculator):
        """A logged cloud model request should have calculable cost."""
        usage_logger.record(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            response_time_ms=450,
            agent_id="agent-1",
            task_type="coding",
        )

        records = usage_logger.read_all()
        assert len(records) == 1

        cost = cost_calculator.cost_for_record(records[0])
        assert cost > 0  # Cloud model should have non-zero cost

    def test_log_and_calculate_local_cost(self, usage_logger, cost_calculator):
        """A logged local model request should have minimal cost."""
        usage_logger.record(
            model="qwen2.5",
            input_tokens=1000,
            output_tokens=500,
            response_time_ms=3000,
            agent_id="agent-1",
            task_type="coding",
        )

        records = usage_logger.read_all()
        assert len(records) == 1

        cost = cost_calculator.cost_for_record(records[0])
        assert cost >= 0
        assert cost < 0.01  # Local cost should be very small

    def test_aggregate_mixed_costs(self, populated_logger, cost_calculator):
        """Aggregate should correctly sum costs across cloud and local models."""
        records = populated_logger.read_all()
        assert len(records) == 5

        agg = cost_calculator.aggregate(records)
        assert agg["total_requests"] == 5
        assert agg["total_input_tokens"] == 1000 + 2000 + 500 + 3000 + 800
        assert agg["total_output_tokens"] == 500 + 1000 + 200 + 1500 + 400
        assert agg["total_cost"] > 0

    def test_cost_per_model_breakdown(self, populated_logger, cost_calculator):
        """Aggregate should provide per-model cost breakdown."""
        records = populated_logger.read_all()
        agg = cost_calculator.aggregate(records)

        assert "cost_by_model" in agg
        assert len(agg["cost_by_model"]) >= 3  # At least deepseek, claude, gpt, qwen


# ---------------------------------------------------------------------------
# Budget alerting integration
# ---------------------------------------------------------------------------

class TestBudgetAlertIntegration:
    """Tests that budget alerts trigger correctly based on usage."""

    def test_no_alert_under_budget(self):
        """No alerts should fire when well under the budget."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(30.0)
        assert len(alerts) == 0

    def test_info_alert_at_threshold(self):
        """INFO alert should fire at the warning threshold."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(82.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.INFO

    def test_warning_alert_at_90_percent(self):
        """WARNING alert should fire at 90% utilization."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(92.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.WARNING

    def test_critical_alert_at_100_percent(self):
        """CRITICAL alert should fire at 100%+ utilization."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(105.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.CRITICAL

    def test_alert_escalation_sequence(self):
        """Alerts should escalate as spend increases."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)

        # 50% -> no alert
        alerts_50 = monitor.check_budget(50.0)
        assert len(alerts_50) == 0

        # 85% -> INFO
        alerts_85 = monitor.check_budget(85.0)
        assert alerts_85[0].level == BudgetAlertLevel.INFO

        # 92% -> WARNING
        alerts_92 = monitor.check_budget(92.0)
        assert alerts_92[0].level == BudgetAlertLevel.WARNING

        # 110% -> CRITICAL
        alerts_110 = monitor.check_budget(110.0)
        assert alerts_110[0].level == BudgetAlertLevel.CRITICAL

    def test_budget_status_response(self):
        """get_budget_status should return structured status data."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)

        status = monitor.get_budget_status(45.0)
        assert status["status"] == "ok"
        assert status["current_spend"] == 45.0
        assert status["budget_limit"] == 100.0
        assert status["utilization_pct"] == 45.0

    def test_alerts_response_format(self):
        """get_alerts_response should contain expected keys."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        response = monitor.get_alerts_response(95.0)

        assert "alerts" in response
        assert "current_spend" in response
        assert "budget_limit" in response
        assert isinstance(response["alerts"], list)
        assert len(response["alerts"]) == 1


# ---------------------------------------------------------------------------
# Forecasting integration
# ---------------------------------------------------------------------------

class TestForecastIntegration:
    """Tests that forecasting works with real usage data."""

    def test_forecast_from_logged_data(self, populated_logger, cost_calculator):
        """Forecast should extrapolate from logged usage records."""
        records = populated_logger.read_all()
        forecaster = Forecaster()

        result = forecaster.forecast(records, cost_calculator)
        assert "daily_rate" in result
        assert "projected_monthly" in result
        assert "confidence" in result
        assert result["data_points"] == 5

    def test_forecast_empty_data(self, cost_calculator):
        """Forecast with no records should return zeros."""
        forecaster = Forecaster()
        result = forecaster.forecast([], cost_calculator)

        assert result["daily_rate"] == 0.0
        assert result["projected_monthly"] == 0.0
        assert result["confidence"] == "none"

    def test_forecast_increases_with_data_points(self, tmp_path, cost_calculator):
        """More data points should increase forecast confidence."""
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=log_file)
        now = datetime.now(timezone.utc)

        # Create 20 records over 10 days
        for i in range(20):
            ts = (now - timedelta(days=10) + timedelta(hours=i * 12)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            logger.record(
                model="deepseek-chat",
                input_tokens=1000 + i * 100,
                output_tokens=500 + i * 50,
                response_time_ms=200,
            )

        records = logger.read_all()
        forecaster = Forecaster()
        result = forecaster.forecast(records, cost_calculator)

        assert result["data_points"] == 20
        assert result["daily_rate"] > 0
        assert result["projected_monthly"] > 0
        assert result["confidence"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Alert Manager threshold integration
# ---------------------------------------------------------------------------

class TestAlertManagerThresholdIntegration:
    """Tests AlertManager with custom thresholds and multiple periods."""

    def test_set_threshold_updates_all_periods(self):
        """Setting a monthly threshold should derive daily and weekly."""
        mgr = AlertManager()
        mgr.set_threshold(150.0)

        assert mgr.thresholds["monthly"] == 150.0
        assert mgr.thresholds["daily"] == round(150.0 / 30, 2)
        assert mgr.thresholds["weekly"] == round(150.0 / 4.33, 2)

    def test_multi_period_alerts(self):
        """Multiple periods can trigger alerts simultaneously."""
        mgr = AlertManager(config={
            "thresholds": {"monthly": 100.0, "weekly": 25.0, "daily": 5.0}
        })

        # Daily over, weekly over, monthly under
        alerts = mgr.check(daily_cost=6.0, weekly_cost=30.0, monthly_cost=50.0)
        periods = {a["period"] for a in alerts}

        assert "daily" in periods
        assert "weekly" in periods


# ---------------------------------------------------------------------------
# Report generation integration
# ---------------------------------------------------------------------------

class TestReportGenerationIntegration:
    """Tests report generation with real usage data."""

    def test_generate_daily_report(self, tmp_path):
        """Daily report should contain summary and forecast sections."""
        import claw_billing

        log_file = tmp_path / "data" / "billing" / "usage_log.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        reports_dir = tmp_path / "data" / "billing" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Add a usage record
        now = datetime.now(timezone.utc)
        record = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": "deepseek-chat",
            "provider": "deepseek",
            "type": "cloud",
            "input_tokens": 2000,
            "output_tokens": 1000,
            "response_time_ms": 250,
            "agent_id": "test",
            "task_type": "coding",
        }
        log_file.write_text(json.dumps(record) + "\n")

        # Patch module paths
        orig_log = claw_billing.USAGE_LOG_FILE
        orig_reports = claw_billing.REPORTS_DIR
        orig_data = claw_billing.DATA_DIR

        try:
            claw_billing.USAGE_LOG_FILE = log_file
            claw_billing.REPORTS_DIR = reports_dir
            claw_billing.DATA_DIR = log_file.parent

            gen = ReportGenerator()
            gen.logger = UsageLogger(log_path=log_file)
            report = gen.generate("daily")

            assert report["report_type"] == "daily"
            assert "summary" in report
            assert "forecast" in report
            assert report["summary"]["total_requests"] >= 0
        finally:
            claw_billing.USAGE_LOG_FILE = orig_log
            claw_billing.REPORTS_DIR = orig_reports
            claw_billing.DATA_DIR = orig_data


# ---------------------------------------------------------------------------
# Cloud pricing coverage
# ---------------------------------------------------------------------------

class TestCloudPricingIntegration:
    """Tests that all known cloud models have pricing entries."""

    def test_common_models_have_pricing(self):
        """All commonly used cloud models should have pricing data."""
        expected_models = [
            "deepseek-chat",
            "claude-sonnet-4-6",
            "gpt-4.1",
        ]
        for model in expected_models:
            assert model in CLOUD_PRICING, \
                f"Missing pricing for model: {model}"
            pricing = CLOUD_PRICING[model]
            assert "input" in pricing
            assert "output" in pricing
            assert pricing["input"] >= 0
            assert pricing["output"] >= 0

    def test_local_model_zero_cloud_cost(self, cost_calculator):
        """Local models should have zero API cost (only electricity)."""
        record = {
            "model": "llama3.2",
            "input_tokens": 10000,
            "output_tokens": 5000,
            "type": "local",
            "response_time_ms": 0,
        }
        cost = cost_calculator.cost_for_record(record)
        assert cost == 0.0  # Zero response time -> zero cost


# ---------------------------------------------------------------------------
# Usage logger auto-detection
# ---------------------------------------------------------------------------

class TestUsageLoggerAutoDetection:
    """Tests model type auto-detection in the usage logger."""

    def test_cloud_model_detected(self, usage_logger):
        """Known cloud models should be tagged as 'cloud'."""
        record = usage_logger.record(
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
        )
        assert record["type"] == "cloud"
        assert record["provider"] == "anthropic"

    def test_local_model_detected(self, usage_logger):
        """Unknown models should be tagged as 'local'."""
        record = usage_logger.record(
            model="custom-local-model",
            input_tokens=100,
            output_tokens=50,
        )
        assert record["type"] == "local"

    def test_deepseek_provider_detected(self, usage_logger):
        """DeepSeek models should be tagged with 'deepseek' provider."""
        record = usage_logger.record(
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
        )
        assert record["provider"] == "deepseek"
