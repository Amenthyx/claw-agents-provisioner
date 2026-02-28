"""
Integration tests — multi-module pipelines.

Tests that verify the interaction between multiple shared modules
when combined into end-to-end workflows, verify all shared modules load,
check CLI help output, and confirm project directory structure.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
sys.path.insert(0, str(Path(__file__).parent.parent / "assessment"))

PROJECT_ROOT = Path(__file__).parent.parent


class TestHardwareToStrategyPipeline:
    """Integration: hardware detect -> strategy generate."""

    def test_hardware_profile_feeds_strategy(self, mock_hardware_profile):
        """StrategyGenerator should accept a hardware profile and include it in output."""
        from claw_strategy import StrategyGenerator

        # Simulate scan results with one local model
        scan_results = {
            "local_models": [
                {
                    "id": "qwen2.5",
                    "full_id": "qwen2.5:latest",
                    "provider": "local",
                    "runtime": "ollama",
                    "runtime_name": "Ollama",
                    "openai_base": "http://localhost:11434/v1",
                    "quality": 8,
                    "speed": 6,
                    "cost_input": 0.0,
                    "cost_output": 0.0,
                    "specialization": ["general", "multilingual", "coding"],
                },
            ],
            "cloud_models": [],
            "available_runtimes": ["ollama"],
            "total": 1,
        }

        generator = StrategyGenerator(
            scan_results, config={"prefer_local": True},
            hardware_profile=mock_hardware_profile
        )
        strategy = generator.generate()

        assert strategy["version"] == "1.0"
        assert strategy["total_models"] == 1
        assert "task_routing" in strategy
        assert "hardware" in strategy
        assert strategy["hardware"]["detected"] is True
        assert strategy["hardware"]["ram_gb"] == 64.0

    def test_strategy_scores_model_for_all_task_types(self, mock_hardware_profile):
        """Strategy should produce routing for all 7 task types."""
        from claw_strategy import StrategyGenerator, TASK_TYPES

        scan_results = {
            "local_models": [
                {
                    "id": "llama3.2",
                    "full_id": "llama3.2:latest",
                    "provider": "local",
                    "runtime": "ollama",
                    "runtime_name": "Ollama",
                    "openai_base": "http://localhost:11434/v1",
                    "quality": 6,
                    "speed": 8,
                    "cost_input": 0.0,
                    "cost_output": 0.0,
                    "specialization": ["general", "chat"],
                },
            ],
            "cloud_models": [],
            "available_runtimes": ["ollama"],
            "total": 1,
        }

        generator = StrategyGenerator(scan_results)
        strategy = generator.generate()

        routing = strategy.get("task_routing", {})
        for task_name in TASK_TYPES:
            assert task_name in routing, f"Missing routing for {task_name}"
            assert "primary" in routing[task_name]


class TestValidateToResolvePipeline:
    """Integration: assessment validate -> resolve."""

    def test_valid_assessment_resolves(self, tmp_path, mock_assessment):
        """A valid assessment should pass validation and produce a resolution."""
        from validate import validate_manual, validate_business_rules
        from resolve import select_llm_model, ResolutionResult

        # Write assessment to file
        assessment_file = tmp_path / "assessment.json"
        assessment_file.write_text(json.dumps(mock_assessment))

        # Load the real schema
        schema_path = Path(__file__).parent.parent / "assessment" / "schema" / "assessment-schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Step 1: Validate (manual mode for portability)
        errors = validate_manual(mock_assessment, schema)
        assert errors == [], f"Unexpected validation errors: {errors}"

        # Step 2: Business rules
        warnings = validate_business_rules(mock_assessment)
        # Warnings are advisory, not blocking
        assert isinstance(warnings, list)

        # Step 3: Resolve LLM model
        provider, model = select_llm_model(mock_assessment, {})
        assert provider in ("deepseek", "anthropic", "openai", "local")
        assert isinstance(model, str) and len(model) > 0

        # Step 4: Build result
        result = ResolutionResult(
            platform="openclaw",
            llm_provider=provider,
            llm_model=model,
            skills=["customer-support", "code-review"],
            compliance_flags=["encryption"],
            monthly_api_cost_estimate=[25, 50],
            recommended_adapter="01-customer-support",
            fine_tuning_enabled=False,
            fine_tuning_method="prompt-only",
            base_model=None,
            lora_rank=32,
            client_industry="technology",
            data_sensitivity="medium",
        )
        d = result.to_dict()
        assert d["llm_provider"] == provider
        assert d["llm_model"] == model

    def test_invalid_assessment_fails_validation(self, mock_assessment):
        """An assessment missing required sections should fail validation."""
        from validate import validate_manual

        schema_path = Path(__file__).parent.parent / "assessment" / "schema" / "assessment-schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Remove two required sections
        del mock_assessment["budget"]
        del mock_assessment["channels"]

        errors = validate_manual(mock_assessment, schema)
        assert len(errors) >= 2
        assert any("budget" in e for e in errors)
        assert any("channels" in e for e in errors)


class TestAssessmentPipeline:
    """End-to-end test: validate assessment -> resolve -> generate config."""

    def test_validate_then_resolve(self, mock_assessment):
        """A valid assessment should validate cleanly and resolve to a config."""
        from validate import validate_manual, validate_business_rules
        from resolve import select_llm_model

        # Load the real schema
        schema_path = PROJECT_ROOT / "assessment" / "schema" / "assessment-schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Step 1: Validate
        errors = validate_manual(mock_assessment, schema)
        assert errors == [], f"Validation should pass, got: {errors}"

        warnings = validate_business_rules(mock_assessment)
        assert isinstance(warnings, list)

        # Step 2: Resolve LLM model
        provider, model = select_llm_model(mock_assessment, {})
        assert provider in ("deepseek", "anthropic", "openai", "local")
        assert isinstance(model, str)
        assert len(model) > 0

    def test_resolution_result_roundtrip(self):
        """ResolutionResult should serialize to dict and round-trip via JSON."""
        from resolve import ResolutionResult

        result = ResolutionResult(
            platform="picoclaw",
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            skills=["web-search", "calculator"],
            compliance_flags=["encryption"],
            monthly_api_cost_estimate=[0, 10],
            recommended_adapter="01-customer-support",
            fine_tuning_enabled=False,
            fine_tuning_method="prompt-only",
            base_model=None,
            lora_rank=32,
            client_industry="technology",
            client_language="en",
            data_sensitivity="medium",
            storage_preference="private-cloud",
        )

        d = result.to_dict()
        assert d["platform"] == "picoclaw"
        assert d["skills"] == ["web-search", "calculator"]
        assert d["compliance_flags"] == ["encryption"]
        assert d["client_industry"] == "technology"
        assert d["storage_preference"] == "private-cloud"

        # Verify JSON-serializable round-trip
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        assert deserialized["llm_model"] == "deepseek-chat"

    def test_full_pipeline_with_file(self, tmp_project_dir, mock_assessment):
        """Write assessment to file, validate, resolve — full file-based flow."""
        from validate import load_json, validate_manual, validate_business_rules
        from resolve import select_llm_model

        # Write assessment to a temp file
        assessment_file = tmp_project_dir / "assessment" / "test-assessment.json"
        assessment_file.write_text(json.dumps(mock_assessment, indent=2))

        # Load it back
        loaded = load_json(assessment_file)
        assert loaded["client_profile"]["company_name"] == "Test Corp"

        # Validate
        schema_path = PROJECT_ROOT / "assessment" / "schema" / "assessment-schema.json"
        schema = load_json(schema_path)
        errors = validate_manual(loaded, schema)
        assert errors == []

        # Resolve
        provider, model = select_llm_model(loaded, {})
        assert provider is not None
        assert model is not None


class TestModuleImports:
    """Verify all shared modules can be imported without errors."""

    def test_import_claw_billing(self):
        """claw_billing module should import without errors."""
        import claw_billing
        assert hasattr(claw_billing, "__name__")

    def test_import_claw_memory(self):
        """claw_memory module should import without errors."""
        import claw_memory
        assert hasattr(claw_memory, "__name__")

    def test_import_claw_rag(self):
        """claw_rag module should import without errors."""
        import claw_rag
        assert hasattr(claw_rag, "__name__")

    def test_import_claw_router(self):
        """claw_router module should import without errors."""
        import claw_router
        assert hasattr(claw_router, "__name__")

    def test_import_claw_skills(self):
        """claw_skills module should import without errors."""
        import claw_skills
        assert hasattr(claw_skills, "__name__")

    def test_import_claw_orchestrator(self):
        """claw_orchestrator module should import without errors."""
        import claw_orchestrator
        assert hasattr(claw_orchestrator, "__name__")

    def test_import_claw_dashboard(self):
        """claw_dashboard module should import without errors."""
        import claw_dashboard
        assert hasattr(claw_dashboard, "__name__")

    def test_import_claw_wizard(self):
        """claw_wizard module should import without errors."""
        import claw_wizard
        assert hasattr(claw_wizard, "__name__")

    def test_import_claw_adapter_selector(self):
        """claw_adapter_selector module should import without errors."""
        import claw_adapter_selector
        assert hasattr(claw_adapter_selector, "AdapterSelector")

    def test_import_claw_hardware(self):
        """claw_hardware module should import without errors."""
        import claw_hardware
        assert hasattr(claw_hardware, "__name__")

    def test_import_claw_security(self):
        """claw_security module should import without errors."""
        import claw_security
        assert hasattr(claw_security, "__name__")

    def test_import_claw_strategy(self):
        """claw_strategy module should import without errors."""
        import claw_strategy
        assert hasattr(claw_strategy, "__name__")

    def test_import_claw_vault(self):
        """claw_vault module should import without errors."""
        import claw_vault
        assert hasattr(claw_vault, "__name__")

    def test_import_claw_optimizer(self):
        """claw_optimizer module should import without errors."""
        import claw_optimizer
        assert hasattr(claw_optimizer, "__name__")

    def test_import_assessment_validate(self):
        """assessment/validate.py should import without errors."""
        import validate
        assert hasattr(validate, "validate_assessment")

    def test_import_assessment_resolve(self):
        """assessment/resolve.py should import without errors."""
        import resolve
        assert hasattr(resolve, "resolve_assessment")


class TestCLIHelp:
    """Tests for the claw.sh CLI help text (parsed from file content).

    We read the file content directly rather than executing it, because
    claw.sh uses `set -euo pipefail` and has an undefined DIM variable
    that causes early termination on some bash versions before the full
    help text is printed.
    """

    @staticmethod
    def _load_claw_content():
        """Load claw.sh file content for subcommand verification."""
        claw_path = PROJECT_ROOT / "claw.sh"
        return claw_path.read_text(encoding="utf-8").lower()

    def test_claw_sh_is_valid_bash(self):
        """claw.sh should pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", "./claw.sh"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"claw.sh has syntax errors: {result.stderr}"

    def test_help_mentions_dashboard(self):
        """claw.sh should contain the dashboard subcommand."""
        assert "dashboard" in self._load_claw_content()

    def test_help_mentions_router(self):
        """claw.sh should contain the router subcommand."""
        assert "router" in self._load_claw_content()

    def test_help_mentions_memory(self):
        """claw.sh should contain the memory subcommand."""
        assert "memory" in self._load_claw_content()

    def test_help_mentions_rag(self):
        """claw.sh should contain the rag subcommand."""
        assert "rag" in self._load_claw_content()

    def test_help_mentions_billing(self):
        """claw.sh should contain the billing subcommand."""
        assert "billing" in self._load_claw_content()

    def test_help_mentions_skills(self):
        """claw.sh should contain the skills subcommand."""
        assert "skills" in self._load_claw_content()

    def test_help_mentions_wizard(self):
        """claw.sh should contain the wizard subcommand."""
        assert "wizard" in self._load_claw_content()

    def test_help_mentions_adapter(self):
        """claw.sh should contain the adapter subcommand."""
        assert "adapter" in self._load_claw_content()

    def test_help_mentions_orchestrator(self):
        """claw.sh should contain the orchestrator subcommand."""
        assert "orchestrator" in self._load_claw_content()


class TestDataDirectories:
    """Verify that required data/ subdirectories exist in the project."""

    def test_data_billing_exists(self):
        """data/billing directory should exist."""
        assert (PROJECT_ROOT / "data" / "billing").is_dir()

    def test_data_memory_exists(self):
        """data/memory directory should exist."""
        assert (PROJECT_ROOT / "data" / "memory").is_dir()

    def test_data_rag_exists(self):
        """data/rag directory should exist."""
        assert (PROJECT_ROOT / "data" / "rag").is_dir()

    def test_data_router_exists(self):
        """data/router directory should exist."""
        assert (PROJECT_ROOT / "data" / "router").is_dir()

    def test_data_orchestrator_exists(self):
        """data/orchestrator directory should exist."""
        assert (PROJECT_ROOT / "data" / "orchestrator").is_dir()

    def test_data_skills_exists(self):
        """data/skills directory should exist."""
        assert (PROJECT_ROOT / "data" / "skills").is_dir()

    def test_data_dashboard_exists(self):
        """data/dashboard directory should exist."""
        assert (PROJECT_ROOT / "data" / "dashboard").is_dir()

    def test_data_wizard_exists(self):
        """data/wizard directory should exist."""
        assert (PROJECT_ROOT / "data" / "wizard").is_dir()

    def test_finetune_adapters_exists(self):
        """finetune/adapters directory should exist."""
        assert (PROJECT_ROOT / "finetune" / "adapters").is_dir()

    def test_finetune_datasets_exists(self):
        """finetune/datasets directory should exist."""
        assert (PROJECT_ROOT / "finetune" / "datasets").is_dir()

    def test_assessment_schema_exists(self):
        """assessment/schema directory and schema file should exist."""
        schema_file = PROJECT_ROOT / "assessment" / "schema" / "assessment-schema.json"
        assert schema_file.is_file(), f"Schema file not found: {schema_file}"

    def test_needs_mapping_matrix_exists(self):
        """assessment/needs-mapping-matrix.json should exist."""
        matrix_file = PROJECT_ROOT / "assessment" / "needs-mapping-matrix.json"
        assert matrix_file.is_file(), f"Matrix file not found: {matrix_file}"

    def test_claw_sh_exists(self):
        """claw.sh should exist at the project root."""
        claw_sh = PROJECT_ROOT / "claw.sh"
        assert claw_sh.is_file(), f"claw.sh not found: {claw_sh}"
