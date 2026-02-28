"""
Tests for shared/claw_hardware.py — Hardware Detection & Runtime Recommendation.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_hardware import HardwareDetector, RuntimeRecommender


class TestHardwareDetector:
    """Tests for HardwareDetector instantiation and GPU summary."""

    def test_instantiation(self):
        """HardwareDetector should initialize with default attributes."""
        detector = HardwareDetector()
        assert detector.os_name in ("Linux", "Darwin", "Windows")
        assert isinstance(detector.gpus, list)
        assert len(detector.gpus) == 0
        assert detector.ram_gb == 0.0
        assert isinstance(detector.cpu, dict)

    def test_gpu_summary_no_gpus(self):
        """GPU summary with no GPUs should report has_gpu=False."""
        detector = HardwareDetector()
        detector.gpus = []
        summary = detector._gpu_summary()
        assert summary["has_gpu"] is False
        assert summary["primary_vendor"] is None
        assert summary["primary_api"] is None
        assert summary["total_vram_gb"] == 0
        assert summary["max_vram_gb"] == 0

    def test_gpu_summary_with_mock_gpu(self):
        """GPU summary should reflect a single NVIDIA GPU."""
        detector = HardwareDetector()
        detector.gpus = [
            {
                "vendor": "NVIDIA",
                "name": "RTX 4090",
                "vram_gb": 24.0,
                "api": "CUDA",
            }
        ]
        summary = detector._gpu_summary()
        assert summary["has_gpu"] is True
        assert summary["primary_vendor"] == "NVIDIA"
        assert summary["primary_api"] == "CUDA"
        assert summary["total_vram_gb"] == 24.0
        assert summary["max_vram_gb"] == 24.0
        assert summary["gpu_count"] == 1

    def test_gpu_summary_multiple_gpus(self):
        """GPU summary should aggregate totals across multiple GPUs."""
        detector = HardwareDetector()
        detector.gpus = [
            {"vendor": "NVIDIA", "name": "RTX 4090", "vram_gb": 24.0, "api": "CUDA"},
            {"vendor": "NVIDIA", "name": "RTX 4080", "vram_gb": 16.0, "api": "CUDA"},
        ]
        summary = detector._gpu_summary()
        assert summary["has_gpu"] is True
        assert summary["total_vram_gb"] == 40.0
        assert summary["max_vram_gb"] == 24.0
        assert summary["gpu_count"] == 2


class TestRuntimeRecommender:
    """Tests for RuntimeRecommender logic."""

    def test_nvidia_gpu_recommends_vllm(self, mock_hardware_profile):
        """NVIDIA GPU should recommend vLLM as primary."""
        recommender = RuntimeRecommender(mock_hardware_profile)
        rec = recommender.recommend()
        assert rec["primary"]["id"] == "vllm"
        assert rec["fallback"]["id"] == "ollama"
        assert "NVIDIA" in rec["reason"]

    def test_cpu_only_recommends_llamacpp(self):
        """CPU-only profile should recommend llama.cpp."""
        profile = {
            "gpu_summary": {"has_gpu": False, "primary_vendor": None, "primary_api": None},
            "ram_gb": 16.0,
            "cpu": {"brand": "Intel Core i5", "cores": 8, "arch": "x86_64", "features": []},
            "gpus": [],
        }
        recommender = RuntimeRecommender(profile)
        rec = recommender.recommend()
        assert rec["primary"]["id"] == "llamacpp"
        assert rec["fallback"]["id"] == "ollama"

    def test_apple_silicon_recommends_ollama(self):
        """Apple Silicon profile should recommend Ollama with Metal."""
        profile = {
            "gpu_summary": {
                "has_gpu": True,
                "primary_vendor": "Apple",
                "primary_api": "Metal",
                "max_vram_gb": 32.0,
            },
            "ram_gb": 32.0,
            "cpu": {"brand": "Apple M2 Max", "cores": 12, "arch": "arm64", "features": ["Apple Silicon", "Metal"]},
            "gpus": [{"vendor": "Apple", "name": "M2 Max", "vram_gb": 32.0, "api": "Metal"}],
        }
        recommender = RuntimeRecommender(profile)
        rec = recommender.recommend()
        assert rec["primary"]["id"] == "ollama"
        assert "Apple Silicon" in rec["reason"]

    def test_recommend_models_high_vram(self, mock_hardware_profile):
        """High VRAM should place system in 'high' tier."""
        recommender = RuntimeRecommender(mock_hardware_profile)
        model_rec = recommender.recommend_models()
        assert model_rec["available_memory_gb"] == 24.0
        assert model_rec["memory_type"] == "VRAM"
        assert model_rec["tier"] == "high"

    def test_recommend_models_low_ram_cpu_only(self):
        """Low RAM CPU-only should use 60% RAM allocation."""
        profile = {
            "gpu_summary": {"has_gpu": False, "primary_vendor": None, "max_vram_gb": 0},
            "ram_gb": 4.0,
            "cpu": {"brand": "Generic", "cores": 2, "arch": "x86_64", "features": []},
            "gpus": [],
        }
        recommender = RuntimeRecommender(profile)
        model_rec = recommender.recommend_models()
        assert model_rec["memory_type"] == "RAM"
        # 4.0 * 0.6 = 2.4
        assert model_rec["available_memory_gb"] == 2.4
        assert model_rec["tier"] == "minimal"

    def test_amd_gpu_recommends_ollama(self):
        """AMD GPU should recommend Ollama as primary."""
        profile = {
            "gpu_summary": {"has_gpu": True, "primary_vendor": "AMD", "primary_api": "ROCm", "max_vram_gb": 16.0},
            "ram_gb": 32.0,
            "cpu": {"brand": "AMD Ryzen 9", "cores": 16, "arch": "x86_64", "features": []},
            "gpus": [{"vendor": "AMD", "name": "RX 7900 XTX", "vram_gb": 16.0, "api": "ROCm"}],
        }
        recommender = RuntimeRecommender(profile)
        rec = recommender.recommend()
        assert rec["primary"]["id"] == "ollama"
        assert rec["fallback"]["id"] == "llamacpp"

    def test_intel_gpu_recommends_ipexllm(self):
        """Intel Arc GPU should recommend ipex-llm."""
        profile = {
            "gpu_summary": {"has_gpu": True, "primary_vendor": "Intel", "primary_api": "SYCL", "max_vram_gb": 16.0},
            "ram_gb": 32.0,
            "cpu": {"brand": "Intel Core Ultra", "cores": 16, "arch": "x86_64", "features": []},
            "gpus": [{"vendor": "Intel", "name": "Intel Arc A770", "vram_gb": 16.0, "api": "SYCL"}],
        }
        recommender = RuntimeRecommender(profile)
        rec = recommender.recommend()
        assert rec["primary"]["id"] == "ipexllm"
