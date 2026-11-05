"""
Benchmark 3: Project Opening & Workspace Setup Latency
Measures duration to load a project folder into MainWindow, set working directories,
and initiate workspace subsystems.
"""

from __future__ import annotations
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication


def run_benchmark(iterations: int = 3) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow

    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_bench_proj_"))
    try:
        from core.git_service import GitService
        GitService.init_repo(temp_dir)
        # Create a mock project structure with 20 files
        for i in range(20):
            sub = temp_dir / f"module_{i // 5}"
            sub.mkdir(exist_ok=True)
            (sub / f"file_{i}.py").write_text(f"# file {i}\ndef func_{i}():\n    return {i}\n", encoding="utf-8")

        win = MainWindow()
        win.show()
        app.processEvents()

        load_times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            win._load_project_folder(temp_dir)
            app.processEvents()
            t1 = time.perf_counter()
            load_times.append((t1 - t0) * 1000)

        win.close()
        app.processEvents()

        return {
            "project_open_ms_median": round(statistics.median(load_times), 2),
            "project_open_ms_min": round(min(load_times), 2),
            "project_open_ms_max": round(max(load_times), 2),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 3 Results:", res)

