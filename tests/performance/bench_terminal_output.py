"""
Benchmark 7: Terminal Output Handling & Rendering Throughput
Measures time to process and render large streams of output lines (500 lines and 2,000 lines) in IntegratedTerminalWidget.
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
from ui.terminal_widget import IntegratedTerminalWidget


def run_benchmark(iterations: int = 3) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)

    lines_500 = [f"[stdout {i:04d}] Running integration test step {i} with payload data...\n" for i in range(500)]
    lines_2000 = [f"[stdout {i:04d}] Running integration test step {i} with payload data...\n" for i in range(2000)]

    # 1. 500 lines append
    times_500 = []
    for _ in range(iterations):
        term = IntegratedTerminalWidget()
        term.shutdown()  # avoid shell process
        term.clear_terminal()
        t0 = time.perf_counter()
        for line in lines_500:
            term._append_output(line)
        app.processEvents()
        t1 = time.perf_counter()
        times_500.append((t1 - t0) * 1000)

    # 2. 2,000 lines append
    times_2000 = []
    for _ in range(iterations):
        term = IntegratedTerminalWidget()
        term.shutdown()
        term.clear_terminal()
        t0 = time.perf_counter()
        for line in lines_2000:
            term._append_output(line)
        app.processEvents()
        t1 = time.perf_counter()
        times_2000.append((t1 - t0) * 1000)

    return {
        "terminal_render_500_lines_ms_median": round(statistics.median(times_500), 2),
        "terminal_render_500_lines_ms_min": round(min(times_500), 2),
        "terminal_render_500_lines_ms_max": round(max(times_500), 2),
        "terminal_render_2000_lines_ms_median": round(statistics.median(times_2000), 2),
        "terminal_render_2000_lines_ms_min": round(min(times_2000), 2),
        "terminal_render_2000_lines_ms_max": round(max(times_2000), 2),
    }


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 7 Results:", res)

