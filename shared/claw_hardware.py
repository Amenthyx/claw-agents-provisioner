#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Hardware Detection & Runtime Recommendation Engine
=============================================================================
Auto-detects GPU, VRAM, CPU, RAM, and OS to recommend the optimal local LLM
runtime from: Ollama, llama.cpp, ipex-llm, vLLM, SGLang, Docker Model Runner.

Supports:
  - NVIDIA GPU (CUDA)     — via nvidia-smi
  - AMD GPU (ROCm)        — via rocm-smi / sysfs
  - Intel Arc/Flex GPU     — via xpu-smi / lspci
  - Apple Silicon (Metal)  — via system_profiler
  - CPU detection          — /proc/cpuinfo, sysctl, wmic
  - RAM detection          — /proc/meminfo, sysctl, wmic

Usage:
  python3 shared/claw_hardware.py --detect      # Detect + save hardware_profile.json
  python3 shared/claw_hardware.py --report      # Print formatted hardware report
  python3 shared/claw_hardware.py --recommend   # Recommend runtime + models
  python3 shared/claw_hardware.py --json        # JSON to stdout
  python3 shared/claw_hardware.py --summary     # One-line summary for install.sh

Output: hardware_profile.json — cached hardware detection results

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
HARDWARE_PROFILE_FILE = PROJECT_ROOT / "hardware_profile.json"
OLLAMA_MODELS_FILE = SCRIPT_DIR / "ollama-models.json"

# -------------------------------------------------------------------------
# Colors (for terminal output)
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[hardware]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[hardware]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[hardware]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[hardware]{NC} {msg}")


def _run(cmd: List[str], timeout: int = 10) -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
        pass
    return None


def _run_powershell(ps_cmd: str, timeout: int = 10) -> Optional[str]:
    """Run a PowerShell command and return stdout (Windows only)."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
        pass
    return None


# -------------------------------------------------------------------------
# HardwareDetector — discovers GPU, CPU, RAM, OS
# -------------------------------------------------------------------------
class HardwareDetector:
    """Detects GPU, VRAM, CPU, RAM, and OS using subprocess calls."""

    def __init__(self) -> None:
        self.os_name = platform.system()  # Linux, Darwin, Windows
        self.os_version = platform.version()
        self.arch = platform.machine()  # x86_64, aarch64, arm64, AMD64
        self.gpus: List[Dict[str, Any]] = []
        self.cpu: Dict[str, Any] = {}
        self.ram_gb: float = 0.0

    def detect_all(self) -> Dict[str, Any]:
        """Run all detection routines and return a hardware profile."""
        log("Detecting hardware...")

        self._detect_cpu()
        self._detect_ram()
        self._detect_nvidia_gpu()
        self._detect_amd_gpu()
        self._detect_intel_gpu()
        self._detect_apple_silicon()

        profile = {
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "os": {
                "name": self.os_name,
                "version": self.os_version,
                "arch": self.arch,
            },
            "cpu": self.cpu,
            "ram_gb": round(self.ram_gb, 1),
            "gpus": self.gpus,
            "gpu_summary": self._gpu_summary(),
        }

        return profile

    # --- CPU Detection ---
    def _detect_cpu(self) -> None:
        """Detect CPU brand, cores, and features."""
        brand = "Unknown CPU"
        cores = os.cpu_count() or 1
        features: List[str] = []

        if self.os_name == "Linux":
            out = _run(["cat", "/proc/cpuinfo"])
            if out:
                # Brand
                for line in out.splitlines():
                    if line.startswith("model name"):
                        brand = line.split(":", 1)[1].strip()
                        break
                # Features (flags)
                for line in out.splitlines():
                    if line.startswith("flags"):
                        flags = line.split(":", 1)[1].strip()
                        if "avx512" in flags or "avx512f" in flags:
                            features.append("AVX-512")
                        if "avx2" in flags:
                            features.append("AVX2")
                        if "amx" in flags or "amx_bf16" in flags or "amx_int8" in flags:
                            features.append("AMX")
                        break

        elif self.os_name == "Darwin":
            out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
            if out:
                brand = out
            # Check for Apple Silicon
            if self.arch in ("arm64", "aarch64"):
                features.append("Apple Silicon")
                features.append("Metal")
                # Detect specific chip
                chip_out = _run(["sysctl", "-n", "hw.model"])
                if chip_out:
                    features.append(chip_out)

        elif self.os_name == "Windows":
            # Try PowerShell first (works in Git Bash), fall back to wmic
            out = _run_powershell(
                "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"
            )
            if not out:
                out = _run(["wmic", "cpu", "get", "Name", "/value"])
                if out:
                    for line in out.splitlines():
                        if line.startswith("Name="):
                            out = line.split("=", 1)[1].strip()
                            break
            if out:
                brand = out.strip()

            # Heuristic feature detection based on CPU brand
            if "Intel" in brand:
                # Core Ultra, Xeon w5/w7, 12th+ gen Core i9/i7 have AVX-512
                if any(x in brand for x in ["Ultra", "Xeon w", "Xeon W"]):
                    features.append("AVX-512")
                    features.append("AMX")
                elif any(x in brand for x in ["i9-1", "i7-1"]):
                    features.append("AVX-512 (likely)")
                if "Ultra" in brand:
                    features.append("Intel Hybrid (P+E cores)")

        self.cpu = {
            "brand": brand,
            "cores": cores,
            "arch": self.arch,
            "features": features,
        }

    # --- RAM Detection ---
    def _detect_ram(self) -> None:
        """Detect total system RAM in GB."""
        if self.os_name == "Linux":
            out = _run(["cat", "/proc/meminfo"])
            if out:
                for line in out.splitlines():
                    if line.startswith("MemTotal:"):
                        kb = int(re.findall(r"\d+", line)[0])
                        self.ram_gb = kb / 1024 / 1024
                        return

        elif self.os_name == "Darwin":
            out = _run(["sysctl", "-n", "hw.memsize"])
            if out:
                self.ram_gb = int(out) / 1024 / 1024 / 1024
                return

        elif self.os_name == "Windows":
            # Try PowerShell first (works in Git Bash), fall back to wmic
            out = _run_powershell(
                "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize"
            )
            if out:
                try:
                    kb = int(out.strip())
                    self.ram_gb = kb / 1024 / 1024
                    return
                except ValueError:
                    pass

            out = _run(["wmic", "OS", "get", "TotalVisibleMemorySize", "/value"])
            if out:
                for line in out.splitlines():
                    if line.startswith("TotalVisibleMemorySize="):
                        kb = int(line.split("=", 1)[1].strip())
                        self.ram_gb = kb / 1024 / 1024
                        return

    # --- NVIDIA GPU Detection ---
    def _detect_nvidia_gpu(self) -> None:
        """Detect NVIDIA GPUs via nvidia-smi."""
        out = _run([
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ])

        # Windows fallback: nvidia-smi may not be in Git Bash PATH
        if not out and self.os_name == "Windows":
            # Try common install path
            nvidia_smi_path = "C:/Program Files/NVIDIA Corporation/NVSMI/nvidia-smi.exe"
            out = _run([
                nvidia_smi_path,
                "--query-gpu=name,memory.total,driver_version,compute_cap",
                "--format=csv,noheader,nounits",
            ])
            # Also try via PowerShell
            if not out:
                out = _run_powershell(
                    "& 'C:\\Windows\\System32\\nvidia-smi.exe' "
                    "--query-gpu=name,memory.total,driver_version,compute_cap "
                    "--format=csv,noheader,nounits"
                )

        if not out:
            return

        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                vram_mb = 0
                try:
                    vram_mb = int(parts[1])
                except (ValueError, IndexError):
                    pass

                gpu = {
                    "vendor": "NVIDIA",
                    "name": parts[0],
                    "vram_gb": round(vram_mb / 1024, 1),
                    "driver": parts[2] if len(parts) > 2 else "unknown",
                    "compute_capability": parts[3] if len(parts) > 3 else "unknown",
                    "api": "CUDA",
                }
                self.gpus.append(gpu)
                log(f"  NVIDIA GPU: {gpu['name']} ({gpu['vram_gb']} GB VRAM)")

    # --- AMD GPU Detection ---
    def _detect_amd_gpu(self) -> None:
        """Detect AMD GPUs via rocm-smi or sysfs."""
        if self.os_name not in ("Linux",):
            return

        # Try rocm-smi first
        out = _run(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--csv"])
        if out:
            lines = out.strip().splitlines()
            for line in lines[1:]:  # Skip header
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    gpu = {
                        "vendor": "AMD",
                        "name": parts[0] if parts[0] else "AMD GPU",
                        "vram_gb": 0,
                        "api": "ROCm",
                    }
                    # Try to parse VRAM
                    if len(parts) >= 3:
                        try:
                            vram_bytes = int(parts[2])
                            gpu["vram_gb"] = round(vram_bytes / 1024 / 1024 / 1024, 1)
                        except (ValueError, IndexError):
                            pass
                    self.gpus.append(gpu)
                    log(f"  AMD GPU: {gpu['name']} ({gpu['vram_gb']} GB VRAM)")
            return

        # Fallback: sysfs vendor check
        try:
            import glob as globmod
            for card in sorted(globmod.glob("/sys/class/drm/card*/device/vendor")):
                with open(card) as f:
                    vendor_id = f.read().strip()
                if vendor_id == "0x1002":  # AMD vendor ID
                    card_dir = str(Path(card).parent)
                    name = "AMD GPU"
                    # Try to get device name
                    device_file = os.path.join(card_dir, "device")
                    if os.path.exists(device_file):
                        with open(device_file) as f:
                            name = f"AMD GPU ({f.read().strip()})"
                    gpu = {
                        "vendor": "AMD",
                        "name": name,
                        "vram_gb": 0,
                        "api": "ROCm",
                    }
                    self.gpus.append(gpu)
                    log(f"  AMD GPU detected (sysfs): {name}")
        except (OSError, IOError):
            pass

    # --- Intel GPU Detection ---
    def _detect_intel_gpu(self) -> None:
        """Detect Intel Arc/Flex GPUs via xpu-smi, lspci, or PowerShell (Windows)."""
        if self.os_name == "Windows":
            self._detect_intel_gpu_windows()
            return

        if self.os_name not in ("Linux",):
            return

        # Try xpu-smi
        out = _run(["xpu-smi", "discovery"])
        if out:
            # Parse xpu-smi discovery output
            current_gpu: Dict[str, Any] = {}
            for line in out.splitlines():
                if "Device Name" in line:
                    if current_gpu:
                        self.gpus.append(current_gpu)
                    name = line.split(":", 1)[1].strip() if ":" in line else "Intel GPU"
                    current_gpu = {
                        "vendor": "Intel",
                        "name": name,
                        "vram_gb": 0,
                        "api": "SYCL",
                    }
                elif "Memory Physical Size" in line and current_gpu:
                    try:
                        mem_str = line.split(":", 1)[1].strip()
                        mem_mb = float(re.findall(r"[\d.]+", mem_str)[0])
                        if "GiB" in mem_str or "GB" in mem_str:
                            current_gpu["vram_gb"] = round(mem_mb, 1)
                        else:
                            current_gpu["vram_gb"] = round(mem_mb / 1024, 1)
                    except (ValueError, IndexError):
                        pass
            if current_gpu:
                self.gpus.append(current_gpu)
                log(f"  Intel GPU: {current_gpu['name']} ({current_gpu['vram_gb']} GB)")
            return

        # Fallback: lspci for Intel VGA/Display
        out = _run(["lspci"])
        if out:
            for line in out.splitlines():
                if ("VGA" in line or "Display" in line or "3D" in line) and "Intel" in line:
                    # Check for discrete (Arc/Flex) vs integrated
                    if any(x in line for x in ["Arc", "Flex", "DG1", "DG2"]):
                        gpu = {
                            "vendor": "Intel",
                            "name": line.split(":", 2)[-1].strip() if ":" in line else "Intel Arc GPU",
                            "vram_gb": 0,
                            "api": "SYCL",
                        }
                        self.gpus.append(gpu)
                        log(f"  Intel GPU (lspci): {gpu['name']}")

    def _detect_intel_gpu_windows(self) -> None:
        """Detect Intel GPUs on Windows via PowerShell Get-CimInstance."""
        out = _run_powershell(
            "Get-CimInstance Win32_VideoController | "
            "ForEach-Object { $_.Name + '|' + $_.AdapterRAM }"
        )
        if not out:
            return

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 1)
            name = parts[0].strip()

            # Only detect Intel discrete GPUs (Arc, Flex, DG1, DG2), not integrated
            if "Intel" not in name:
                continue
            if not any(x in name for x in ["Arc", "Flex", "DG1", "DG2"]):
                continue

            vram_gb = 0.0
            if len(parts) > 1 and parts[1].strip():
                try:
                    adapter_ram_bytes = int(parts[1].strip())
                    # WMI AdapterRAM is capped at ~4 GB (32-bit uint)
                    # For GPUs with >4 GB, parse from name if available
                    vram_gb = round(adapter_ram_bytes / 1024 / 1024 / 1024, 1)
                except (ValueError, OverflowError):
                    pass

            # Parse VRAM from name (e.g. "Intel(R) Arc(TM) 140T GPU (16GB)")
            name_match = re.search(r"\((\d+)\s*GB\)", name)
            if name_match:
                vram_gb = float(name_match.group(1))

            gpu = {
                "vendor": "Intel",
                "name": name,
                "vram_gb": vram_gb,
                "api": "SYCL",
            }
            self.gpus.append(gpu)
            log(f"  Intel GPU: {name} ({vram_gb} GB VRAM)")

    # --- Apple Silicon Detection ---
    def _detect_apple_silicon(self) -> None:
        """Detect Apple Silicon GPU (unified memory) on macOS."""
        if self.os_name != "Darwin" or self.arch not in ("arm64", "aarch64"):
            return

        out = _run(["system_profiler", "SPDisplaysDataType"])
        if not out:
            return

        chip_name = "Apple Silicon GPU"
        for line in out.splitlines():
            line = line.strip()
            if "Chipset Model:" in line:
                chip_name = line.split(":", 1)[1].strip()
                break

        # Apple Silicon uses unified memory — GPU VRAM = system RAM
        gpu = {
            "vendor": "Apple",
            "name": chip_name,
            "vram_gb": round(self.ram_gb, 1),  # Unified memory
            "api": "Metal",
            "unified_memory": True,
        }
        self.gpus.append(gpu)
        log(f"  Apple Silicon: {chip_name} ({gpu['vram_gb']} GB unified memory)")

    # --- Summary ---
    def _gpu_summary(self) -> Dict[str, Any]:
        """Generate a summary of GPU capabilities."""
        if not self.gpus:
            return {
                "has_gpu": False,
                "primary_vendor": None,
                "primary_api": None,
                "total_vram_gb": 0,
                "max_vram_gb": 0,
            }

        primary = self.gpus[0]
        total_vram = sum(g.get("vram_gb", 0) for g in self.gpus)
        max_vram = max(g.get("vram_gb", 0) for g in self.gpus)

        return {
            "has_gpu": True,
            "primary_vendor": primary["vendor"],
            "primary_api": primary.get("api", "unknown"),
            "total_vram_gb": round(total_vram, 1),
            "max_vram_gb": round(max_vram, 1),
            "gpu_count": len(self.gpus),
        }


# -------------------------------------------------------------------------
# RuntimeRecommender — recommends best local LLM runtime
# -------------------------------------------------------------------------
class RuntimeRecommender:
    """Uses detected hardware to recommend the optimal local LLM runtime."""

    # Runtime metadata
    RUNTIMES = {
        "vllm": {
            "name": "vLLM",
            "port": 8000,
            "requires_gpu": True,
            "supported_apis": ["CUDA"],
            "description": "Highest throughput GPU inference with PagedAttention",
        },
        "ollama": {
            "name": "Ollama",
            "port": 11434,
            "requires_gpu": False,
            "supported_apis": ["CUDA", "ROCm", "Metal"],
            "description": "Easiest setup, broad hardware support, CPU + GPU",
        },
        "llamacpp": {
            "name": "llama.cpp",
            "port": 8080,
            "requires_gpu": False,
            "supported_apis": ["CUDA", "ROCm", "Metal", "SYCL", "CPU"],
            "description": "Most efficient CPU inference, smallest footprint",
        },
        "ipexllm": {
            "name": "ipex-llm",
            "port": 8010,
            "requires_gpu": False,
            "supported_apis": ["SYCL", "CPU"],
            "description": "Intel-optimized with SYCL/AMX acceleration",
        },
        "sglang": {
            "name": "SGLang",
            "port": 30000,
            "requires_gpu": True,
            "supported_apis": ["CUDA"],
            "description": "Fast serving with RadixAttention, CUDA only",
        },
        "docker_model_runner": {
            "name": "Docker Model Runner",
            "port": 12434,
            "requires_gpu": False,
            "supported_apis": ["CUDA", "CPU"],
            "description": "Docker-native model serving, easy container integration",
        },
    }

    def __init__(self, hardware_profile: Dict[str, Any]) -> None:
        self.profile = hardware_profile
        self.gpu_summary = hardware_profile.get("gpu_summary", {})
        self.ram_gb = hardware_profile.get("ram_gb", 0)
        self.cpu = hardware_profile.get("cpu", {})
        self.gpus = hardware_profile.get("gpus", [])

    def recommend(self) -> Dict[str, Any]:
        """Recommend the best runtime based on detected hardware."""
        has_gpu = self.gpu_summary.get("has_gpu", False)
        vendor = self.gpu_summary.get("primary_vendor", "")
        api = self.gpu_summary.get("primary_api", "")
        max_vram = self.gpu_summary.get("max_vram_gb", 0)
        cpu_features = self.cpu.get("features", [])

        primary = ""
        fallback = ""
        reason = ""

        if has_gpu and vendor == "NVIDIA":
            primary = "vllm"
            fallback = "ollama"
            reason = "NVIDIA GPU detected — vLLM provides highest throughput with PagedAttention and CUDA"

        elif has_gpu and vendor == "AMD":
            primary = "ollama"
            fallback = "llamacpp"
            reason = "AMD GPU detected — Ollama has the best ROCm support for AMD GPUs"

        elif has_gpu and vendor == "Intel":
            primary = "ipexllm"
            fallback = "ollama"
            reason = "Intel Arc/Flex GPU detected — ipex-llm provides Intel-optimized SYCL backend"

        elif has_gpu and vendor == "Apple":
            primary = "ollama"
            fallback = "llamacpp"
            reason = "Apple Silicon detected — Ollama has native Metal support for best performance"

        elif any("AMX" in f for f in cpu_features) or any("AVX-512" in f for f in cpu_features):
            primary = "ipexllm"
            fallback = "llamacpp"
            reason = "Intel CPU with AMX/AVX-512 detected — ipex-llm provides hardware-accelerated inference"

        elif self.ram_gb < 8:
            primary = "llamacpp"
            fallback = "ollama"
            reason = "Low RAM (<8 GB) — llama.cpp has the smallest memory footprint"

        elif self.cpu.get("arch", "") in ("aarch64", "arm64") and vendor != "Apple":
            primary = "ollama"
            fallback = "llamacpp"
            reason = "ARM CPU detected — Ollama provides pre-built ARM binaries"

        else:
            primary = "llamacpp"
            fallback = "ollama"
            reason = "Generic CPU detected — llama.cpp is the most efficient for CPU-only inference"

        primary_info = self.RUNTIMES.get(primary, {})
        fallback_info = self.RUNTIMES.get(fallback, {})

        return {
            "primary": {
                "id": primary,
                "name": primary_info.get("name", primary),
                "port": primary_info.get("port", 0),
                "description": primary_info.get("description", ""),
            },
            "fallback": {
                "id": fallback,
                "name": fallback_info.get("name", fallback),
                "port": fallback_info.get("port", 0),
                "description": fallback_info.get("description", ""),
            },
            "reason": reason,
            "all_compatible": self._list_compatible_runtimes(),
        }

    def _list_compatible_runtimes(self) -> List[Dict[str, Any]]:
        """List all runtimes compatible with detected hardware."""
        compatible = []
        has_gpu = self.gpu_summary.get("has_gpu", False)
        api = self.gpu_summary.get("primary_api", "")

        for rt_id, rt_info in self.RUNTIMES.items():
            # Skip GPU-only runtimes if no GPU
            if rt_info["requires_gpu"] and not has_gpu:
                continue

            # Check API compatibility
            if has_gpu and api and api not in rt_info["supported_apis"]:
                # GPU present but API not supported — still compatible if CPU fallback
                if "CPU" not in rt_info["supported_apis"] and not rt_info["requires_gpu"]:
                    continue

            compatible.append({
                "id": rt_id,
                "name": rt_info["name"],
                "port": rt_info["port"],
                "description": rt_info["description"],
            })

        return compatible

    def recommend_models(self) -> Dict[str, Any]:
        """Recommend models that fit the available VRAM/RAM."""
        max_vram = self.gpu_summary.get("max_vram_gb", 0)
        has_gpu = self.gpu_summary.get("has_gpu", False)

        # Use VRAM for GPU systems, RAM for CPU-only (with conservative allocation)
        if has_gpu and max_vram > 0:
            available_memory = max_vram
            memory_type = "VRAM"
        else:
            # CPU-only: allocate ~60% of RAM for model
            available_memory = self.ram_gb * 0.6
            memory_type = "RAM"

        # Load model registry
        models = self._load_model_registry()

        fitting = []
        too_large = []

        for model in models:
            model_vram = model.get("vram_gb", 0)
            if model_vram <= available_memory:
                fitting.append(model)
            else:
                too_large.append(model)

        # Determine VRAM tier
        if available_memory >= 24:
            tier = "high"
            tier_label = "24+ GB — all models, can run multiple simultaneously"
        elif available_memory >= 16:
            tier = "medium-high"
            tier_label = "16 GB — 14B models and below"
        elif available_memory >= 8:
            tier = "medium"
            tier_label = "8 GB — 7B models and below"
        elif available_memory >= 4:
            tier = "low"
            tier_label = "4 GB — 3B models only"
        else:
            tier = "minimal"
            tier_label = "<4 GB — very limited, smallest models only"

        return {
            "available_memory_gb": round(available_memory, 1),
            "memory_type": memory_type,
            "tier": tier,
            "tier_label": tier_label,
            "fitting_models": fitting,
            "too_large_models": too_large,
        }

    def _load_model_registry(self) -> List[Dict]:
        """Load model specs from ollama-models.json."""
        if not OLLAMA_MODELS_FILE.exists():
            return []

        try:
            with open(OLLAMA_MODELS_FILE) as f:
                data = json.load(f)
            return data.get("models", [])
        except (json.JSONDecodeError, IOError):
            return []


# -------------------------------------------------------------------------
# CLI Output Formatting
# -------------------------------------------------------------------------
def print_hardware_report(profile: Dict) -> None:
    """Print a formatted hardware report."""
    print(f"\n{BOLD}{CYAN}=== Hardware Detection Report ==={NC}\n")

    # OS
    os_info = profile.get("os", {})
    print(f"  {BOLD}OS:{NC}       {os_info.get('name', '?')} ({os_info.get('arch', '?')})")
    print(f"  {BOLD}Version:{NC}  {os_info.get('version', '?')}")

    # CPU
    cpu = profile.get("cpu", {})
    print(f"\n  {BOLD}CPU:{NC}      {cpu.get('brand', '?')}")
    print(f"  {BOLD}Cores:{NC}    {cpu.get('cores', '?')}")
    if cpu.get("features"):
        print(f"  {BOLD}Features:{NC} {', '.join(cpu['features'])}")

    # RAM
    print(f"\n  {BOLD}RAM:{NC}      {profile.get('ram_gb', 0)} GB")

    # GPUs
    gpus = profile.get("gpus", [])
    if gpus:
        print(f"\n  {BOLD}GPUs ({len(gpus)}):{NC}")
        for i, gpu in enumerate(gpus):
            unified = " (unified)" if gpu.get("unified_memory") else ""
            print(f"    {i+1}. {gpu['name']} — {gpu.get('vram_gb', 0)} GB{unified} [{gpu.get('api', '?')}]")
    else:
        print(f"\n  {BOLD}GPU:{NC}      {DIM}None detected{NC}")

    # GPU Summary
    summary = profile.get("gpu_summary", {})
    if summary.get("has_gpu"):
        print(f"\n  {BOLD}GPU API:{NC}  {summary.get('primary_api', '?')}")
        print(f"  {BOLD}Max VRAM:{NC} {summary.get('max_vram_gb', 0)} GB")

    print()


def print_recommendation_report(recommendation: Dict, model_rec: Dict) -> None:
    """Print a formatted runtime recommendation report."""
    print(f"\n{BOLD}{CYAN}=== Runtime Recommendation ==={NC}\n")

    primary = recommendation.get("primary", {})
    fallback = recommendation.get("fallback", {})

    print(f"  {BOLD}{GREEN}RECOMMENDED:{NC} {BOLD}{primary.get('name', '?')}{NC} (port {primary.get('port', '?')})")
    print(f"    {primary.get('description', '')}")
    print(f"\n  {BOLD}Fallback:{NC}    {fallback.get('name', '?')} (port {fallback.get('port', '?')})")
    print(f"    {fallback.get('description', '')}")
    print(f"\n  {BOLD}Reason:{NC}      {recommendation.get('reason', '')}")

    # Compatible runtimes
    compatible = recommendation.get("all_compatible", [])
    if compatible:
        print(f"\n  {BOLD}All compatible runtimes:{NC}")
        for rt in compatible:
            marker = f" {GREEN}<-- recommended{NC}" if rt["id"] == primary.get("id") else ""
            print(f"    - {rt['name']} (:{rt['port']}){marker}")

    # Model recommendations
    print(f"\n{BOLD}{CYAN}=== Model Recommendations ==={NC}\n")
    print(f"  {BOLD}Available {model_rec['memory_type']}:{NC} {model_rec['available_memory_gb']} GB")
    print(f"  {BOLD}Tier:{NC}                  {model_rec['tier_label']}")

    fitting = model_rec.get("fitting_models", [])
    if fitting:
        print(f"\n  {BOLD}{GREEN}Models that fit ({len(fitting)}):{NC}")
        for m in fitting:
            print(f"    - {m['name']:.<20} {m.get('parameters', '?'):>5} params  {m.get('size_gb', '?')} GB  (needs {m.get('vram_gb', '?')} GB)")
    else:
        print(f"\n  {YELLOW}No models fit in available memory.{NC}")
        print(f"  Consider upgrading RAM or using a cloud provider.")

    too_large = model_rec.get("too_large_models", [])
    if too_large:
        print(f"\n  {DIM}Too large for this system:{NC}")
        for m in too_large:
            print(f"    {DIM}- {m['name']:.<20} needs {m.get('vram_gb', '?')} GB{NC}")

    print()


def print_summary(profile: Dict, recommendation: Dict, model_rec: Dict) -> str:
    """Print a one-line summary suitable for install.sh parsing."""
    gpu_summary = profile.get("gpu_summary", {})
    primary = recommendation.get("primary", {})

    if gpu_summary.get("has_gpu"):
        gpu_name = profile.get("gpus", [{}])[0].get("name", "GPU")
        vram = gpu_summary.get("max_vram_gb", 0)
        summary = f"{gpu_name} ({vram}GB VRAM) | {profile.get('ram_gb', 0)}GB RAM | {primary.get('name', '?')} recommended"
    else:
        cpu_brand = profile.get("cpu", {}).get("brand", "CPU")
        # Shorten CPU brand
        cpu_short = cpu_brand.split("@")[0].strip() if "@" in cpu_brand else cpu_brand[:40]
        summary = f"{cpu_short} | {profile.get('ram_gb', 0)}GB RAM | CPU-only | {primary.get('name', '?')} recommended"

    fitting_count = len(model_rec.get("fitting_models", []))
    summary += f" | {fitting_count} models fit"

    return summary


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 shared/claw_hardware.py [--detect|--report|--recommend|--json|--summary]")
        print()
        print("Commands:")
        print("  --detect      Detect hardware and save hardware_profile.json")
        print("  --report      Print formatted hardware report")
        print("  --recommend   Recommend best runtime and models")
        print("  --json        Output hardware profile as JSON to stdout")
        print("  --summary     One-line summary (for install.sh)")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--detect":
        detector = HardwareDetector()
        profile = detector.detect_all()

        with open(HARDWARE_PROFILE_FILE, "w") as f:
            json.dump(profile, f, indent=2)

        log(f"Hardware profile saved to: {HARDWARE_PROFILE_FILE}")
        print_hardware_report(profile)

    elif action == "--report":
        if HARDWARE_PROFILE_FILE.exists():
            with open(HARDWARE_PROFILE_FILE) as f:
                profile = json.load(f)
        else:
            info("No cached profile — running live detection...")
            detector = HardwareDetector()
            profile = detector.detect_all()

        print_hardware_report(profile)

    elif action == "--recommend":
        # Detect or load
        if HARDWARE_PROFILE_FILE.exists():
            with open(HARDWARE_PROFILE_FILE) as f:
                profile = json.load(f)
        else:
            detector = HardwareDetector()
            profile = detector.detect_all()

        recommender = RuntimeRecommender(profile)
        recommendation = recommender.recommend()
        model_rec = recommender.recommend_models()

        print_hardware_report(profile)
        print_recommendation_report(recommendation, model_rec)

    elif action == "--json":
        # Detect and output JSON to stdout
        detector = HardwareDetector()
        profile = detector.detect_all()

        recommender = RuntimeRecommender(profile)
        recommendation = recommender.recommend()
        model_rec = recommender.recommend_models()

        output = {
            "hardware": profile,
            "recommendation": recommendation,
            "models": model_rec,
        }

        print(json.dumps(output, indent=2))

    elif action == "--summary":
        # One-line summary for install.sh
        detector = HardwareDetector()
        profile = detector.detect_all()

        recommender = RuntimeRecommender(profile)
        recommendation = recommender.recommend()
        model_rec = recommender.recommend_models()

        summary = print_summary(profile, recommendation, model_rec)
        print(summary)

    else:
        err(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
