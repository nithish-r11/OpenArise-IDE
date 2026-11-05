"""
Benchmark 5: Large Directory Indexing & ContextManager Processing
Measures the throughput of ProjectIndexer scanning files and ContextManager index creation.
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
from core.context_manager import ContextManager, ProjectIndexer


def run_benchmark(iterations: int = 3, num_files: int = 100) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_bench_idx_"))
    try:
        # Generate files with varying content lengths
        for i in range(num_files):
            sub = temp_dir / f"pkg_{i % 10}"
            sub.mkdir(exist_ok=True)
            content = f"# Module {i}\n" + "def example_function():\n    pass\n" * 20
            (sub / f"module_{i}.py").write_text(content, encoding="utf-8")

        indexing_times = []
        context_build_times = []

        for _ in range(iterations):
            # 1. ProjectIndexer execution
            indexer = ProjectIndexer(temp_dir)
            t0 = time.perf_counter()
            indexer.start()
            indexer.wait(10000)
            t1 = time.perf_counter()
            indexing_times.append((t1 - t0) * 1000)

            # 2. ContextManager build_context
            cm = ContextManager()
            cm.set_project(temp_dir)
            # simulate updated index
            cm.update_index({f"file_{i}.py": "content" * 50 for i in range(num_files)})
            t2 = time.perf_counter()
            ctx = cm.build_context("example query", include_codebase=True, max_chars=8000)
            t3 = time.perf_counter()
            context_build_times.append((t3 - t2) * 1000)

        return {
            "project_indexing_100_files_ms_median": round(statistics.median(indexing_times), 2),
            "project_indexing_100_files_ms_min": round(min(indexing_times), 2),
            "project_indexing_100_files_ms_max": round(max(indexing_times), 2),
            "context_build_ms_median": round(statistics.median(context_build_times), 2),
            "indexed_files_count": num_files,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 5 Results:", res)

