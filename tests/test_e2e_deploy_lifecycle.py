"""
End-to-end tests for the Deploy Lifecycle — verifies the full sequence:
  assessment -> resolve -> env generation -> config generation ->
  health check simulation -> basic operation simulation -> teardown.

All external dependencies (Docker, LLM APIs) are mocked. Tests verify
the logical flow and data contracts between pipeline stages.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
sys.path.insert(0, str(Path(__file__).parent.parent / "assessment"))

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deploy_assessment():
    """A standard assessment for deploy lifecycle testing."""
    return {
        "assessment_version": "3.0",
        "assessment_date": "2026-03-01",
        "client_profile": {
            "company_name": "DeployTest Inc",
            "contact_name": "Jane Deploy",
            "contact_email": "jane@deploytest.com",
            "industry": "technology",
            "company_size": "11-50",
            "tech_savvy": 4,
            "primary_devices": ["desktop", "mobile"],
            "service_package": "private",
        },
        "use_cases": {
            "primary_use_cases": ["customer-support"],
            "complexity_level": "moderate",
        },
        "communication_preferences": {
            "languages": ["en"],
            "primary_language": "en",
            "tone": "professional",
            "verbosity": "balanced",
        },
        "data_privacy": {
            "sensitivity": "medium",
            "storage_preference": "private-cloud",
            "encryption_required": True,
            "data_residency": "EU",
        },
        "performance_scale": {
            "daily_requests": 200,
            "peak_concurrent_users": 10,
            "response_time_target": "fast",
            "max_context_length": "medium",
        },
        "budget": {
            "monthly_api_budget": 30,
            "infrastructure_budget": 0,
            "fine_tuning_budget": 0,
        },
        "channels": {
            "primary_channel": "web-chat",
            "secondary_channels": [],
        },
        "compliance": {
            "regulations": ["gdpr"],
        },
        "fine_tuning": {
            "enabled": False,
            "method": "prompt-only",
        },
    }


@pytest.fixture
def real_schema():
    """Load the real assessment JSON schema."""
    schema_path = PROJECT_ROOT / "assessment" / "schema" / "assessment-schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Full deploy lifecycle
# ---------------------------------------------------------------------------

class TestFullDeployLifecycle:
    """E2E test of the complete deploy pipeline with mocked infrastructure."""

    def test_full_lifecycle(self, tmp_path, deploy_assessment, real_schema):
        """
        Full lifecycle:
        1. Validate assessment
        2. Resolve configuration
        3. Generate .env
        4. Generate agent config
        5. Simulate health check (mocked)
        6. Simulate basic operation (memory + router mocked)
        7. Teardown (cleanup temp files)
        """
        from validate import validate_manual, validate_business_rules
        from resolve import resolve_assessment
        from generate_env import generate_env
        from generate_config import (
            generate_zeroclaw_config,
            generate_picoclaw_config,
            generate_openclaw_config,
        )

        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()

        # -- Phase 1: Validate --
        errors = validate_manual(deploy_assessment, real_schema)
        assert errors == [], f"Validation failed: {errors}"

        warnings = validate_business_rules(deploy_assessment)
        assert isinstance(warnings, list)

        # -- Phase 2: Resolve --
        result = resolve_assessment(deploy_assessment)
        assert result.platform is not None
        assert result.llm_provider is not None
        assert result.llm_model is not None

        # -- Phase 3: Generate .env --
        env_content = generate_env(deploy_assessment, result, "deploy.json")
        env_file = deploy_dir / ".env"
        env_file.write_text(env_content)

        assert env_file.exists()
        assert f"CLAW_AGENT={result.platform}" in env_content

        # -- Phase 4: Generate agent configs --
        config_files = {}

        zc = generate_zeroclaw_config(deploy_assessment, result)
        config_files["zeroclaw.toml"] = zc
        (deploy_dir / "zeroclaw.toml").write_text(zc)

        pc = generate_picoclaw_config(deploy_assessment, result)
        config_files["picoclaw.json"] = pc
        (deploy_dir / "picoclaw.json").write_text(pc)

        oc = generate_openclaw_config(deploy_assessment, result)
        config_files["openclaw.json"] = oc
        (deploy_dir / "openclaw.json").write_text(oc)

        # Verify all configs were generated
        assert len(config_files) == 3
        for name, content in config_files.items():
            assert len(content) > 0, f"Config {name} is empty"

        # -- Phase 5: Simulate health check --
        from claw_health import HealthChecker

        checker = HealthChecker(interval=60)
        # Mock all services as healthy
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            checker._check_all()

        overall = checker.get_overall_status()
        assert overall == "healthy"
        checker.stop()

        # -- Phase 6: Simulate basic operation --
        # Memory: create conversation, add messages
        from claw_memory import ConversationStore

        db_path = deploy_dir / "memory.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("deploy-agent")
        store.add_message(conv["id"], "user", "Hello from deploy test")
        store.add_message(conv["id"], "assistant", "Deployment verified!")

        retrieved = store.get_conversation(conv["id"])
        assert retrieved is not None
        assert len(retrieved["messages"]) == 2
        store.close()

        # Router: verify task detection
        from claw_router import detect_task_type
        task = detect_task_type([
            {"role": "user", "content": "Help me with customer support"}
        ])
        assert isinstance(task, str)

        # -- Phase 7: Teardown --
        import shutil
        shutil.rmtree(deploy_dir)
        assert not deploy_dir.exists()


# ---------------------------------------------------------------------------
# Deploy with all 5 platforms
# ---------------------------------------------------------------------------

class TestDeployAllPlatforms:
    """Tests that config generation works for all 5 agent platforms."""

    PLATFORMS = ["zeroclaw", "nanoclaw", "picoclaw", "openclaw", "parlant"]

    def test_resolve_to_known_platform(self, deploy_assessment):
        """Resolver should always select a known platform."""
        from resolve import resolve_assessment

        result = resolve_assessment(deploy_assessment)
        assert result.platform in self.PLATFORMS

    def test_generate_configs_for_resolved_platform(self, deploy_assessment):
        """Config generation should succeed for the resolved platform."""
        from resolve import resolve_assessment, ResolutionResult
        from generate_config import (
            generate_zeroclaw_config,
            generate_picoclaw_config,
            generate_openclaw_config,
            generate_nanoclaw_patches,
        )

        result = resolve_assessment(deploy_assessment)

        generators = {
            "zeroclaw": generate_zeroclaw_config,
            "picoclaw": generate_picoclaw_config,
            "openclaw": generate_openclaw_config,
        }

        if result.platform in generators:
            config = generators[result.platform](deploy_assessment, result)
            assert len(config) > 0

        if result.platform == "nanoclaw":
            patches = generate_nanoclaw_patches(deploy_assessment, result)
            assert isinstance(patches, dict)
            assert len(patches) > 0


# ---------------------------------------------------------------------------
# Health check simulation
# ---------------------------------------------------------------------------

class TestHealthCheckSimulation:
    """Tests health check workflow during deployment."""

    def test_all_services_healthy(self):
        """Simulates all services reporting healthy."""
        from claw_health import HealthChecker, SERVICES

        checker = HealthChecker(interval=60)
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            checker._check_all()

        all_statuses = checker.get_all()
        for svc_id, status in all_statuses.items():
            assert status["status"] == "healthy", f"{svc_id} is not healthy"

        assert checker.get_overall_status() == "healthy"
        checker.stop()

    def test_partial_deployment_degraded(self):
        """Simulates partial deployment where some services fail."""
        from claw_health import HealthChecker, SERVICES

        checker = HealthChecker(interval=60)

        # First two services healthy, rest unhealthy
        service_ids = list(SERVICES.keys())

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claw_health.urllib.request.urlopen", return_value=mock_response):
            checker._check_one(service_ids[0])

        with patch("claw_health.urllib.request.urlopen",
                   side_effect=ConnectionRefusedError("refused")):
            for svc_id in service_ids[1:]:
                checker._check_one(svc_id)

        assert checker.get_overall_status() == "degraded"
        checker.stop()


# ---------------------------------------------------------------------------
# Memory + RAG operation simulation
# ---------------------------------------------------------------------------

class TestOperationSimulation:
    """Tests basic service operations that would run after deployment."""

    def test_memory_conversation_lifecycle(self, tmp_path):
        """Simulates a full conversation lifecycle after deployment."""
        from claw_memory import ConversationStore

        db = tmp_path / "ops_memory.db"
        store = ConversationStore(db_path=db)

        # Create conversation
        conv = store.create_conversation("deployed-agent")
        assert conv is not None

        # Add messages
        messages = [
            ("user", "I need help with my order"),
            ("assistant", "I'd be happy to help. What's your order number?"),
            ("user", "Order #12345"),
            ("assistant", "Let me look that up. Your order is in transit."),
        ]
        for role, content in messages:
            msg = store.add_message(conv["id"], role, content)
            assert msg is not None

        # Retrieve and verify
        full = store.get_conversation(conv["id"])
        assert len(full["messages"]) == 4

        # Search
        results = store.search("order")
        assert len(results) >= 2

        # Stats
        stats = store.get_stats()
        assert stats["conversations"] == 1
        assert stats["messages"] == 4

        store.close()

    def test_rag_ingest_and_search(self, tmp_path):
        """Simulates RAG document ingestion and search after deployment."""
        from claw_rag import TrigramIndex, KnowledgeBase

        # Create knowledge base
        index = TrigramIndex()
        chunks = {}
        files = {}
        kb = KnowledgeBase("deployed-agent", index, chunks, files)

        # Ingest support docs
        faq = tmp_path / "faq.txt"
        faq.write_text(
            "Q: How do I reset my password?\n"
            "A: Go to Settings > Account > Reset Password.\n\n"
            "Q: How do I update my billing information?\n"
            "A: Navigate to Settings > Billing > Payment Methods.\n\n"
            "Q: What are your support hours?\n"
            "A: We offer 24/7 support via chat and email.\n"
        )

        added = kb.ingest_file(str(faq))
        assert added > 0

        # Search for relevant FAQ
        results = kb.search("reset password")
        assert len(results) > 0
        assert any("password" in r["text"].lower() for r in results)

    def test_billing_tracking_after_deploy(self, tmp_path):
        """Simulates billing tracking during operation."""
        from claw_billing import UsageLogger, CostCalculator, BudgetMonitor

        log_file = tmp_path / "usage.jsonl"
        # Bypass DAL to avoid production database errors
        logger = UsageLogger.__new__(UsageLogger)
        logger.log_path = log_file
        logger._dal = None
        import claw_billing
        claw_billing._ensure_dirs()
        calc = CostCalculator()

        # Simulate 10 API calls
        for i in range(10):
            logger.record(
                model="deepseek-chat",
                input_tokens=500 + i * 100,
                output_tokens=250 + i * 50,
                response_time_ms=200 + i * 10,
                agent_id="deployed-agent",
                task_type="customer-support",
            )

        records = logger.read_all()
        assert len(records) == 10

        agg = calc.aggregate(records)
        assert agg["total_requests"] == 10
        assert agg["total_cost"] > 0

        # Check budget
        monitor = BudgetMonitor(warn_threshold=0.80, hard_limit=30.0)
        alerts = monitor.check_budget(agg["total_cost"])
        # With deepseek-chat, 10 small requests should be well under $30
        assert len(alerts) == 0 or alerts[0].level.value == "INFO"


# ---------------------------------------------------------------------------
# Orchestrator routing simulation
# ---------------------------------------------------------------------------

class TestOrchestratorRoutingSimulation:
    """Tests orchestrator task routing during operation."""

    def test_submit_and_route_task(self, tmp_path):
        """Simulates submitting a task and routing it to an agent."""
        import threading
        from claw_orchestrator import AgentRegistry, TaskQueue, _init_db

        db_path = tmp_path / "orch.db"
        with patch("claw_orchestrator.DATA_DIR", tmp_path):
            conn = _init_db(db_path)

        # Bypass DAL to avoid production database errors
        registry = AgentRegistry.__new__(AgentRegistry)
        registry._conn = conn
        registry._lock = threading.Lock()
        registry._dal = None
        queue = TaskQueue(conn)

        # Register agents
        registry.auto_register_known()
        registry.update_status("nanoclaw", "healthy")

        # Submit a coding task
        tid = queue.submit("Review PR #42", description="Code review needed",
                           priority=4, agent_hint="nanoclaw")

        # Assign to nanoclaw
        assigned = queue.assign(tid, "nanoclaw")
        assert assigned is True

        # Complete
        completed = queue.complete(tid, result="PR approved")
        assert completed is True

        conn.close()


# ---------------------------------------------------------------------------
# Teardown verification
# ---------------------------------------------------------------------------

class TestTeardownVerification:
    """Tests that teardown properly cleans up resources."""

    def test_cleanup_deploy_directory(self, tmp_path):
        """Teardown should remove the deploy directory."""
        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()
        (deploy_dir / ".env").write_text("CLAW_AGENT=zeroclaw")
        (deploy_dir / "config.json").write_text("{}")

        assert deploy_dir.exists()

        import shutil
        shutil.rmtree(deploy_dir)
        assert not deploy_dir.exists()

    def test_cleanup_database_files(self, tmp_path):
        """Teardown should close and remove database files."""
        from claw_memory import ConversationStore

        db = tmp_path / "teardown.db"
        store = ConversationStore(db_path=db)
        store.create_conversation("test")
        store.close()

        assert db.exists()
        db.unlink()
        assert not db.exists()
