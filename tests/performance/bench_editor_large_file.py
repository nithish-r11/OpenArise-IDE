"""
Benchmark 6: Editor Large-File Loading & Syntax Highlighting Overhead
Measures time to load and highlight large code files (1,000 lines and 5,000 lines) in CodeEditor.
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
from ui.editor_widget import CodeEditor, PythonHighlighter


def generate_python_code(lines_count: int) -> str:
    blocks = []
    for i in range(lines_count // 5):
        blocks.append(
            f"class ServiceHandler_{i}:\n"
            f"    # Important service logic {i}\n"
            f"    def process_request(self, item_id: int = {i}) -> bool:\n"
            f"        msg = 'processing item ' + str(item_id)\n"
            f"        return item_id % 2 == 0\n"
        )
    return "\n".join(blocks)


def run_benchmark(iterations: int = 3) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)

    code_1k = generate_python_code(1000)
    code_5k = generate_python_code(5000)

    # 1. Measure 1,000 lines loading & highlighting
    times_1k = []
    for _ in range(iterations):
        editor = CodeEditor()
        t0 = time.perf_counter()
        editor.setPlainText(code_1k)
        app.processEvents()
        t1 = time.perf_counter()
        times_1k.append((t1 - t0) * 1000)

    # 2. Measure 5,000 lines loading & highlighting
    times_5k = []
    for _ in range(iterations):
        editor = CodeEditor()
        t0 = time.perf_counter()
        editor.setPlainText(code_5k)
        app.processEvents()
        t1 = time.perf_counter()
        times_5k.append((t1 - t0) * 1000)

    return {
        "editor_load_1000_lines_ms_median": round(statistics.median(times_1k), 2),
        "editor_load_1000_lines_ms_min": round(min(times_1k), 2),
        "editor_load_1000_lines_ms_max": round(max(times_1k), 2),
        "editor_load_5000_lines_ms_median": round(statistics.median(times_5k), 2),
        "editor_load_5000_lines_ms_min": round(min(times_5k), 2),
        "editor_load_5000_lines_ms_max": round(max(times_5k), 2),
    }


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 6 Results:", res)

