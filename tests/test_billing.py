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
