"""
Shared pytest fixtures for Claw Agents Provisioner test suite.
"""

import json
import os
import tempfile

import pytest


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temp directory with a mock project structure."""
    shared = tmp_path / "shared"
    shared.mkdir()
    assessment = tmp_path / "assessment"
    assessment.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "billing").mkdir(parents=True)
    (data / "memory").mkdir(parents=True)
    (data / "rag").mkdir(parents=True)
    (data / "skills").mkdir(parents=True)
    finetune = tmp_path / "finetune"
    (finetune / "adapters").mkdir(parents=True)
    (finetune / "datasets").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_hardware_profile():
    """Return a sample hardware profile dict."""
    return {
        "detected_at": "2026-02-28T12:00:00Z",
        "os": {"name": "Linux", "version": "6.5.0", "arch": "x86_64"},
        "cpu": {
            "brand": "Intel Core i9-14900K",
            "cores": 24,
            "arch": "x86_64",
            "features": ["AVX-512", "AVX2"],
        },
        "ram_gb": 64.0,
        "gpus": [
            {
                "vendor": "NVIDIA",
                "name": "NVIDIA RTX 4090",
                "vram_gb": 24.0,
                "driver": "545.29.06",
                "compute_capability": "8.9",
                "api": "CUDA",
            }
        ],
        "gpu_summary": {
            "has_gpu": True,
            "primary_vendor": "NVIDIA",
            "primary_api": "CUDA",
            "total_vram_gb": 24.0,
            "max_vram_gb": 24.0,
            "gpu_count": 1,
        },
    }


@pytest.fixture
def mock_strategy():
    """Return a sample strategy.json dict."""
    return {
        "version": "1.0",
        "generated_at": "2026-02-28T12:00:00Z",
        "total_models": 3,
        "prefer_local": True,
        "task_routing": {
            "coding": {
                "description": "Code generation, review, debugging",
                "min_quality": 7,
                "primary": {
                    "model": "qwen2.5",
                    "provider": "Ollama",
                    "type": "local",
                    "score": 85.0,
                    "openai_base": "http://localhost:11434/v1",
                },
                "fallback": {
                    "model": "deepseek-chat",
                    "provider": "DeepSeek",
                    "type": "cloud",
                    "score": 70.0,
                    "openai_base": None,
                },
            },
            "simple_chat": {
                "description": "Simple Q&A, casual conversation",
                "min_quality": 5,
                "primary": {
                    "model": "llama3.2",
                    "provider": "Ollama",
                    "type": "local",
                    "score": 75.0,
                    "openai_base": "http://localhost:11434/v1",
                },
            },
        },
        "models_inventory": [
            {"id": "qwen2.5", "provider": "Ollama", "type": "local"},
            {"id": "llama3.2", "provider": "Ollama", "type": "local"},
            {"id": "deepseek-chat", "provider": "DeepSeek", "type": "cloud"},
        ],
    }


@pytest.fixture
def mock_assessment():
    """Return a sample client-assessment.json dict."""
    return {
        "assessment_version": "3.0",
        "assessment_date": "2026-02-28",
        "client_profile": {
            "company_name": "Test Corp",
            "contact_name": "Jane Doe",
            "contact_email": "jane@testcorp.com",
            "industry": "technology",
            "company_size": "11-50",
            "tech_savvy": 4,
            "primary_devices": ["desktop", "mobile"],
            "service_package": "private",
        },
        "use_cases": {
            "primary_use_cases": ["customer-support", "code-review"],
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
            "daily_requests": 500,
            "peak_concurrent_users": 20,
            "response_time_target": "fast",
            "max_context_length": "medium",
        },
        "budget": {
            "monthly_api_budget": 50,
            "infrastructure_budget": 0,
            "fine_tuning_budget": 10,
        },
        "channels": {
            "primary_channel": "web-chat",
            "secondary_channels": ["telegram"],
        },
        "compliance": {
            "regulations": ["gdpr"],
        },
        "fine_tuning": {
            "enabled": False,
            "method": "prompt-only",
        },
    }
