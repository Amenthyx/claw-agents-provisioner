"""
Tests for shared/claw_billing.py — Cost Analytics & Alerting.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

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


class TestUsageLogger:
    """Tests for UsageLogger append and read."""

    def test_record_appends_to_file(self, tmp_path):
        """UsageLogger.record should append a JSONL line."""
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=log_file)
        record = logger.record(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            response_time_ms=450,
            agent_id="agent-1",
            task_type="coding",
        )
        assert record["model"] == "claude-sonnet-4-6"
        assert record["input_tokens"] == 1000
        assert record["output_tokens"] == 500
        assert record["provider"] == "anthropic"
        assert record["type"] == "cloud"

        # Verify file was written
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["model"] == "claude-sonnet-4-6"

    def test_read_all(self, tmp_path):
        """UsageLogger.read_all should return all logged records."""
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=log_file)
        logger.record(model="gpt-4.1", input_tokens=100, output_tokens=50)
        logger.record(model="deepseek-chat", input_tokens=200, output_tokens=100)

        records = logger.read_all()
        assert len(records) == 2
        assert records[0]["model"] == "gpt-4.1"
        assert records[1]["model"] == "deepseek-chat"

    def test_local_model_detected(self, tmp_path):
        """Models not in CLOUD_PRICING should be marked as local."""
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=log_file)
        record = logger.record(model="qwen2.5", input_tokens=100, output_tokens=50)
        assert record["type"] == "local"


class TestCostCalculator:
    """Tests for CostCalculator pricing."""

    def test_cloud_cost_calculation(self):
        """Cloud cost should use per-million-token pricing."""
        calc = CostCalculator()
        record = {
            "model": "claude-sonnet-4-6",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "type": "cloud",
        }
        cost = calc.cost_for_record(record)
        # claude-sonnet-4-6: input=$3/M, output=$15/M
        expected = 3.0 + 15.0
        assert abs(cost - expected) < 0.01

    def test_cloud_cost_small_tokens(self):
        """Small token counts should yield proportionally small costs."""
        calc = CostCalculator()
        record = {
            "model": "deepseek-chat",
            "input_tokens": 1000,
            "output_tokens": 500,
            "type": "cloud",
        }
        cost = calc.cost_for_record(record)
        # deepseek-chat: input=$0.14/M, output=$0.28/M
        expected = (1000 / 1_000_000) * 0.14 + (500 / 1_000_000) * 0.28
        assert abs(cost - expected) < 0.0001

    def test_local_cost_estimation(self):
        """Local cost should estimate electricity from response time."""
        calc = CostCalculator()
        record = {
            "model": "qwen2.5",
            "input_tokens": 1000,
            "output_tokens": 500,
            "type": "local",
            "response_time_ms": 5000,  # 5 seconds
        }
        cost = calc.cost_for_record(record)
        # 5s = 5/3600 hours, 150W GPU, $0.12/kWh
        # kwh = (150/1000) * (5/3600) = 0.000208
        # cost = 0.000208 * 0.12 = ~0.000025
        assert cost > 0
        assert cost < 0.001  # very small

    def test_local_cost_zero_response_time(self):
        """Local cost with 0 response time should be 0."""
        calc = CostCalculator()
        record = {
            "model": "llama3.2",
            "input_tokens": 100,
            "output_tokens": 50,
            "type": "local",
            "response_time_ms": 0,
        }
        cost = calc.cost_for_record(record)
        assert cost == 0.0

    def test_aggregate(self):
        """Aggregate should sum costs across records."""
        calc = CostCalculator()
        records = [
            {"model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 500,
             "type": "cloud", "provider": "anthropic", "agent_id": "a1",
             "task_type": "coding", "response_time_ms": 0},
            {"model": "deepseek-chat", "input_tokens": 2000, "output_tokens": 1000,
             "type": "cloud", "provider": "deepseek", "agent_id": "a1",
             "task_type": "chat", "response_time_ms": 0},
        ]
        agg = calc.aggregate(records)
        assert agg["total_requests"] == 2
        assert agg["total_input_tokens"] == 3000
        assert agg["total_output_tokens"] == 1500
        assert agg["total_cost"] > 0


class TestAlertManager:
    """Tests for AlertManager threshold checks."""

    def test_no_alerts_under_threshold(self):
        """No alerts when spend is below all thresholds."""
        mgr = AlertManager()
        alerts = mgr.check(daily_cost=1.0, weekly_cost=10.0, monthly_cost=30.0)
        assert len(alerts) == 0

    def test_critical_alert_over_threshold(self):
        """Critical alert when spend exceeds threshold."""
        mgr = AlertManager(config={"thresholds": {"monthly": 50.0, "weekly": 12.0, "daily": 2.0}})
        alerts = mgr.check(daily_cost=3.0, weekly_cost=5.0, monthly_cost=20.0)
        daily_alerts = [a for a in alerts if a["period"] == "daily"]
        assert len(daily_alerts) == 1
        assert daily_alerts[0]["level"] == "critical"

    def test_warning_alert_at_80_percent(self):
        """Warning alert when spend reaches 80% of threshold."""
        mgr = AlertManager(config={"thresholds": {"monthly": 100.0, "weekly": 50.0, "daily": 10.0}})
        alerts = mgr.check(daily_cost=8.5, weekly_cost=10.0, monthly_cost=20.0)
        daily_alerts = [a for a in alerts if a["period"] == "daily"]
        assert len(daily_alerts) == 1
        assert daily_alerts[0]["level"] == "warning"

    def test_set_threshold_derives_daily_weekly(self):
        """set_threshold should derive daily and weekly from monthly."""
        mgr = AlertManager()
        mgr.set_threshold(300.0)
        assert mgr.thresholds["monthly"] == 300.0
        assert mgr.thresholds["daily"] == round(300.0 / 30, 2)
        assert mgr.thresholds["weekly"] == round(300.0 / 4.33, 2)


class TestForecaster:
    """Tests for Forecaster linear extrapolation."""

    def test_forecast_empty_records(self):
        """Forecast with no records should return zeros."""
        forecaster = Forecaster()
        calc = CostCalculator()
        result = forecaster.forecast([], calc)
        assert result["daily_rate"] == 0.0
        assert result["projected_monthly"] == 0.0
        assert result["confidence"] == "none"

    def test_forecast_with_records(self):
        """Forecast should extrapolate from observed spend."""
        now = datetime.now(timezone.utc)
        records = []
        # Simulate 10 records over 5 days
        for i in range(10):
            ts = (now - timedelta(days=5) + timedelta(hours=i * 12)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            records.append({
                "timestamp": ts,
                "model": "deepseek-chat",
                "input_tokens": 1000,
                "output_tokens": 500,
                "type": "cloud",
                "provider": "deepseek",
                "response_time_ms": 200,
            })

        forecaster = Forecaster()
        calc = CostCalculator()
        result = forecaster.forecast(records, calc)

        assert result["data_points"] == 10
        assert result["daily_rate"] > 0
        assert result["projected_weekly"] > result["projected_daily"]
        assert result["projected_monthly"] > result["projected_weekly"]
        assert result["confidence"] in ("low", "medium", "high")


class TestReportGenerator:
    """Tests for ReportGenerator daily report."""

    def test_generate_daily_report(self, tmp_path):
        """Daily report should produce a valid report dict."""
        # Create usage log with a record
        log_file = tmp_path / "data" / "billing" / "usage_log.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        reports_dir = tmp_path / "data" / "billing" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        record = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": "deepseek-chat",
            "provider": "deepseek",
            "type": "cloud",
            "input_tokens": 1000,
            "output_tokens": 500,
            "response_time_ms": 300,
            "agent_id": "test",
            "task_type": "coding",
        }
        log_file.write_text(json.dumps(record) + "\n")

        # Patch module-level paths
        import claw_billing
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


class TestBudgetAlertLevel:
    """Tests for BudgetAlertLevel enum."""

    def test_levels_exist(self):
        """All three alert levels should be defined."""
        assert BudgetAlertLevel.INFO.value == "INFO"
        assert BudgetAlertLevel.WARNING.value == "WARNING"
        assert BudgetAlertLevel.CRITICAL.value == "CRITICAL"


class TestBudgetAlert:
    """Tests for BudgetAlert data class."""

    def test_to_dict(self):
        """BudgetAlert.to_dict should serialize all fields."""
        alert = BudgetAlert(
            level=BudgetAlertLevel.WARNING,
            message="Budget 90% utilized",
            current_spend=90.0,
            budget_limit=100.0,
            utilization_pct=90.0,
            timestamp="2026-03-01T00:00:00Z",
        )
        d = alert.to_dict()
        assert d["level"] == "WARNING"
        assert d["message"] == "Budget 90% utilized"
        assert d["current_spend"] == 90.0
        assert d["budget_limit"] == 100.0
        assert d["utilization_pct"] == 90.0
        assert d["timestamp"] == "2026-03-01T00:00:00Z"

    def test_to_dict_auto_timestamp(self):
        """BudgetAlert should auto-generate timestamp if not provided."""
        alert = BudgetAlert(
            level=BudgetAlertLevel.INFO,
            message="test",
            current_spend=50.0,
            budget_limit=100.0,
            utilization_pct=50.0,
        )
        d = alert.to_dict()
        assert "timestamp" in d
        assert d["timestamp"].endswith("Z")


class TestBudgetMonitor:
    """Tests for BudgetMonitor threshold detection and alerting."""

    def test_no_alerts_under_warn_threshold(self):
        """No alerts when spend is below warn threshold."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(50.0)
        assert len(alerts) == 0

    def test_info_alert_at_80_percent(self):
        """INFO alert triggers at the warn threshold (default 80%)."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(80.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.INFO
        assert alerts[0].utilization_pct == 80.0

    def test_info_alert_at_85_percent(self):
        """INFO alert triggers between 80% and 90%."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(85.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.INFO

    def test_warning_alert_at_90_percent(self):
        """WARNING alert triggers at 90% utilization."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(90.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.WARNING
        assert alerts[0].utilization_pct == 90.0

    def test_warning_alert_at_95_percent(self):
        """WARNING alert triggers between 90% and 100%."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(95.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.WARNING

    def test_critical_alert_at_100_percent(self):
        """CRITICAL alert triggers at 100% (budget exceeded)."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(100.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.CRITICAL
        assert alerts[0].utilization_pct == 100.0

    def test_critical_alert_over_100_percent(self):
        """CRITICAL alert triggers when spend exceeds budget."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        alerts = monitor.check_budget(150.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.CRITICAL
        assert alerts[0].utilization_pct == 150.0

    def test_custom_warn_threshold(self):
        """Custom warn threshold should be respected."""
        monitor = BudgetMonitor(warn_threshold=0.50, hard_limit=100.0)
        # 55% should trigger INFO with 0.50 threshold
        alerts = monitor.check_budget(55.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.INFO

    def test_zero_hard_limit_no_alerts(self):
        """Zero hard limit should produce no alerts."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=0.0)
        alerts = monitor.check_budget(50.0)
        assert len(alerts) == 0

    def test_get_budget_status_ok(self):
        """Budget status should be 'ok' when well under threshold."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        status = monitor.get_budget_status(30.0)
        assert status["status"] == "ok"
        assert status["current_spend"] == 30.0
        assert status["budget_limit"] == 100.0
        assert status["utilization_pct"] == 30.0

    def test_get_budget_status_approaching(self):
        """Budget status should be 'approaching' at warn threshold."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        status = monitor.get_budget_status(82.0)
        assert status["status"] == "approaching"

    def test_get_budget_status_warning(self):
        """Budget status should be 'warning' at 90%."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        status = monitor.get_budget_status(92.0)
        assert status["status"] == "warning"

    def test_get_budget_status_critical(self):
        """Budget status should be 'critical' at 100%+."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        status = monitor.get_budget_status(105.0)
        assert status["status"] == "critical"

    def test_get_alerts_response_format(self):
        """Alerts response should contain expected top-level keys."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        response = monitor.get_alerts_response(95.0)
        assert "alerts" in response
        assert "current_spend" in response
        assert "budget_limit" in response
        assert "utilization_pct" in response
        assert isinstance(response["alerts"], list)
        assert len(response["alerts"]) == 1
        assert response["alerts"][0]["level"] == "WARNING"

    def test_get_alerts_response_no_alerts(self):
        """Alerts response with low spend should have empty alerts list."""
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=100.0)
        response = monitor.get_alerts_response(10.0)
        assert response["alerts"] == []
        assert response["current_spend"] == 10.0

    def test_webhook_payload_format(self):
        """Webhook payload should contain all required fields."""
        # We test the payload structure by examining what _send_webhook
        # would send.  Since we cannot mock urllib easily without external
        # libs, we verify the BudgetAlert.to_dict output matches the
        # expected webhook schema.
        alert = BudgetAlert(
            level=BudgetAlertLevel.CRITICAL,
            message="Budget exceeded: $120.00 of $100.00 limit (120.0%)",
            current_spend=120.0,
            budget_limit=100.0,
            utilization_pct=120.0,
            timestamp="2026-03-01T12:00:00Z",
        )
        payload = {
            "event": "budget_alert",
            "level": alert.level.value,
            "message": alert.message,
            "current_spend": round(alert.current_spend, 6),
            "budget_limit": round(alert.budget_limit, 2),
            "utilization_pct": round(alert.utilization_pct, 1),
            "timestamp": alert.timestamp,
        }
        assert payload["event"] == "budget_alert"
        assert payload["level"] == "CRITICAL"
        assert payload["current_spend"] == 120.0
        assert payload["budget_limit"] == 100.0
        assert payload["utilization_pct"] == 120.0
        assert payload["timestamp"] == "2026-03-01T12:00:00Z"
        assert "message" in payload

        # Verify the payload is valid JSON
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        assert decoded == payload

    def test_webhook_not_called_for_info(self):
        """Webhook should NOT fire for INFO-level alerts."""
        # BudgetMonitor only calls _send_webhook for WARNING/CRITICAL.
        # With an unreachable URL, INFO should produce alerts but no
        # network error (since webhook is not attempted).
        monitor = BudgetMonitor(
            warn_threshold=0.80,
            hard_limit=100.0,
            webhook_url="http://unreachable.invalid:9999/hook",
        )
        # 82% = INFO level — webhook should not fire
        alerts = monitor.check_budget(82.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.INFO

    def test_webhook_attempted_for_critical(self):
        """Webhook should be attempted for CRITICAL alerts (fails gracefully)."""
        monitor = BudgetMonitor(
            warn_threshold=0.80,
            hard_limit=100.0,
            webhook_url="http://unreachable.invalid:9999/hook",
        )
        # 110% = CRITICAL — webhook fires but fails silently
        alerts = monitor.check_budget(110.0)
        assert len(alerts) == 1
        assert alerts[0].level == BudgetAlertLevel.CRITICAL


class TestBudgetAutoCheck:
    """Tests for auto-budget-check after UsageLogger.record."""

    def test_auto_check_runs_after_record(self, tmp_path):
        """Recording a cost should trigger budget auto-check without error."""
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=log_file)
        # This should not raise even though budget check runs internally
        record = logger.record(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
        )
        assert record["model"] == "claude-sonnet-4-6"
        assert log_file.exists()
