"""
Benchmark 1: Application Initialization & Import Overhead
Measures raw import durations of core modules, PyQt6, and main application entry points.
"""

from __future__ import annotations
import importlib
import statistics
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def run_benchmark(iterations: int = 3) -> dict:
    results = {}
    import subprocess

    def measure_cmd(cmd_str: str) -> float:
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            subprocess.run(
                [sys.executable, "-c", cmd_str],
                cwd=str(APP_DIR),
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
        return round(statistics.median(times), 2)

    # 1. Base PyQt6 import
    results["pyqt6_import_ms"] = measure_cmd(
        "import PyQt6.QtCore, PyQt6.QtWidgets, PyQt6.QtGui"
    )

    # 2. Core modules import
    results["core_modules_import_ms"] = measure_cmd(
        "import core.ollama_client, core.agent_orchestrator, core.context_manager, core.git_service, core.system_monitor"
    )

    # 3. UI modules import
    results["ui_modules_import_ms"] = measure_cmd(
        "import ui.main_window, ui.editor_widget, ui.chat_panel, ui.agent_panel, ui.terminal_widget"
    )

    # 4. Total CLI startup import
    results["full_main_import_ms"] = measure_cmd(
        "import main"
    )

    return results


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 1 Results:", res)

