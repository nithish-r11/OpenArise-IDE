"""
Benchmark 4: File Explorer Model & Directory Traversal Throughput
Measures scanning and population overhead of the file explorer system across structured directories.
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

from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QApplication


def run_benchmark(iterations: int = 3) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_bench_fs_"))
    try:
        # Create 100 nested files
        for i in range(10):
            d = temp_dir / f"pkg_{i}"
            d.mkdir(exist_ok=True)
            for j in range(10):
                (d / f"source_{j}.py").write_text(f"x = {j}\n", encoding="utf-8")

        scan_times = []
        for _ in range(iterations):
            model = QFileSystemModel()
            t0 = time.perf_counter()
            root_idx = model.setRootPath(str(temp_dir))
            app.processEvents()
            t1 = time.perf_counter()
            scan_times.append((t1 - t0) * 1000)

        return {
            "filesystem_model_scan_ms_median": round(statistics.median(scan_times), 2),
            "filesystem_model_scan_ms_min": round(min(scan_times), 2),
            "filesystem_model_scan_ms_max": round(max(scan_times), 2),
            "total_files_scanned": 100,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 4 Results:", res)

