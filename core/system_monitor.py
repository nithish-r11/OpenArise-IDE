"""
System Resource Monitor for OpenArise IDE.
Measures available RAM, CPU load, GPU/VRAM (when supported), and active Ollama model memory.
Clearly distinguishes authoritative measured metrics from unavailable estimates,
and provides hardware-aware model recommendations.
"""

from __future__ import annotations
import ctypes
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]


@dataclass
class ModelRecommendation:
    category: str
    suggested_models: list[str]
    reason: str
    suitable_for_system: bool


@dataclass
class SystemResourceReport:
    total_ram_gb: float
    available_ram_gb: float
    used_ram_gb: float
    ram_percent: float
    ram_measured: bool = True

    cpu_percent: float = 0.0
    cpu_measured: bool = True

    gpu_name: str = "Unavailable"
    gpu_vram_total_gb: Optional[float] = None
    gpu_vram_used_gb: Optional[float] = None
    gpu_vram_free_gb: Optional[float] = None
    gpu_measured: bool = False

    loaded_models: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[ModelRecommendation] = field(default_factory=list)


class SystemResourceMonitor:
    """Monitors local host hardware resources and Ollama memory allocation."""

    @staticmethod
    def get_memory_status() -> tuple[bool, float, float, float, float]:
        """
        Queries Windows physical RAM using GlobalMemoryStatusEx.
        Returns: (measured, total_gb, avail_gb, used_gb, percent_used)
        """
        if os.name == "nt":
            try:
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total = stat.ullTotalPhys / (1024 ** 3)
                    avail = stat.ullAvailPhys / (1024 ** 3)
                    used = total - avail
                    pct = float(stat.dwMemoryLoad)
                    return True, round(total, 2), round(avail, 2), round(used, 2), pct
            except Exception:
                pass
        return False, 0.0, 0.0, 0.0, 0.0

    @staticmethod
    def get_cpu_percent(sample_duration: float = 0.05) -> tuple[bool, float]:
        """
        Measures CPU utilization on Windows via GetSystemTimes.
        Returns: (measured, cpu_percent)
        """
        if os.name == "nt":
            try:
                def _to_int(ft):
                    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

                i1, k1, u1 = FILETIME(), FILETIME(), FILETIME()
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i1), ctypes.byref(k1), ctypes.byref(u1))
                time.sleep(sample_duration)
                i2, k2, u2 = FILETIME(), FILETIME(), FILETIME()
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i2), ctypes.byref(k2), ctypes.byref(u2))

                usr = _to_int(u2) - _to_int(u1)
                ker = _to_int(k2) - _to_int(k1)
                idl = _to_int(i2) - _to_int(i1)
                sys_time = usr + ker
                pct = ((sys_time - idl) * 100.0 / sys_time) if sys_time > 0 else 0.0
                return True, round(max(0.0, min(100.0, pct)), 1)
            except Exception:
                pass
        return False, 0.0

    @staticmethod
    def get_gpu_status() -> tuple[bool, str, Optional[float], Optional[float], Optional[float]]:
        """
        Queries NVIDIA GPU metrics via nvidia-smi if installed.
        Returns: (measured, name, total_gb, used_gb, free_gb)
        """
        if not shutil.which("nvidia-smi"):
            return False, "Not detected / Non-NVIDIA GPU", None, None, None

        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=flags,
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    name = parts[0]
                    total = round(float(parts[1]) / 1024, 2)
                    used = round(float(parts[2]) / 1024, 2)
                    free = round(float(parts[3]) / 1024, 2)
                    return True, name, total, used, free
        except Exception:
            pass

        return False, "Not detected / Non-NVIDIA GPU", None, None, None

    @classmethod
    def get_recommendations(cls, total_ram_gb: float, vram_gb: Optional[float]) -> list[ModelRecommendation]:
        """Generates hardware-aware model recommendations."""
        recs = []

        # 1. Compact models (suitable for <= 8GB RAM)
        recs.append(ModelRecommendation(
            category="Lightweight (1B - 3B)",
            suggested_models=["qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "deepseek-coder:1.3b"],
            reason="Fast inference with low memory footprint (~1.5GB - 3.5GB RAM).",
            suitable_for_system=True
        ))

        # 2. Balanced coding models (requires >= 8GB RAM)
        can_run_7b = total_ram_gb >= 7.5 or (vram_gb is not None and vram_gb >= 5.5)
        recs.append(ModelRecommendation(
            category="Recommended Standard (7B)",
            suggested_models=["qwen2.5-coder:7b", "deepseek-coder:6.7b", "codellama:7b"],
            reason="Best blend of coding capability, speed, and accuracy (~5GB - 8GB RAM/VRAM).",
            suitable_for_system=can_run_7b
        ))

        # 3. High-capability models (requires >= 16GB RAM or >= 10GB VRAM)
        can_run_14b = total_ram_gb >= 15.5 or (vram_gb is not None and vram_gb >= 10.0)
        recs.append(ModelRecommendation(
            category="Advanced & Heavy (14B - 32B)",
            suggested_models=["qwen2.5-coder:14b", "codestral:22b", "qwen2.5-coder:32b"],
            reason="Exceptional reasoning for complex architectures. Requires substantial RAM/VRAM (>12GB).",
            suitable_for_system=can_run_14b
        ))

        return recs

    @classmethod
    def inspect_system(cls, ollama_client=None) -> SystemResourceReport:
        """Inspects all host resources and loaded Ollama models."""
        ram_ok, total_ram, avail_ram, used_ram, ram_pct = cls.get_memory_status()
        cpu_ok, cpu_pct = cls.get_cpu_percent()
        gpu_ok, gpu_name, vram_total, vram_used, vram_free = cls.get_gpu_status()

        loaded_models = []
        if ollama_client and hasattr(ollama_client, "list_running_models"):
            try:
                loaded_models = ollama_client.list_running_models()
            except Exception:
                loaded_models = []

        recommendations = cls.get_recommendations(total_ram, vram_total)

        return SystemResourceReport(
            total_ram_gb=total_ram,
            available_ram_gb=avail_ram,
            used_ram_gb=used_ram,
            ram_percent=ram_pct,
            ram_measured=ram_ok,
            cpu_percent=cpu_pct,
            cpu_measured=cpu_ok,
            gpu_name=gpu_name,
            gpu_vram_total_gb=vram_total,
            gpu_vram_used_gb=vram_used,
            gpu_vram_free_gb=vram_free,
            gpu_measured=gpu_ok,
            loaded_models=loaded_models,
            recommendations=recommendations,
        )

