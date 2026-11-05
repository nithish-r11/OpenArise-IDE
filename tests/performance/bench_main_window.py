"""
Benchmark 2: Main Window Construction & Layout Overhead
Measures MainWindow instantiation time, widget initialization, and first paint/show latency.
"""

from __future__ import annotations
import statistics
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication


def run_benchmark(iterations: int = 3) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow

    construct_times = []
    show_render_times = []
    total_startup_times = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        win = MainWindow()
        t1 = time.perf_counter()

        win.show()
        app.processEvents()
        t2 = time.perf_counter()

        construct_times.append((t1 - t0) * 1000)
        show_render_times.append((t2 - t1) * 1000)
        total_startup_times.append((t2 - t0) * 1000)

        win.close()
        app.processEvents()

    return {
        "mainwindow_construct_ms_median": round(statistics.median(construct_times), 2),
        "mainwindow_construct_ms_min": round(min(construct_times), 2),
        "mainwindow_construct_ms_max": round(max(construct_times), 2),
        "mainwindow_show_render_ms_median": round(statistics.median(show_render_times), 2),
        "mainwindow_total_init_ms_median": round(statistics.median(total_startup_times), 2),
    }


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 2 Results:", res)

