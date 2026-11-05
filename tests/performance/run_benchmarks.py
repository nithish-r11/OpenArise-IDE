"""
Master Benchmark Suite Runner for OpenArise IDE Performance Audit.
Executes all 10 component benchmarks and reports comprehensive metrics.
"""

from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from tests.performance import (
    bench_app_init,
    bench_main_window,
    bench_project_open,
    bench_file_explorer,
    bench_indexing,
    bench_editor_large_file,
    bench_terminal_output,
    bench_ai_connection,
    bench_ai_streaming,
    bench_agent_overhead,
)


def run_full_suite() -> dict:
    print("\n=======================================================", flush=True)
    print("STARTING OPENARISE IDE PERFORMANCE BENCHMARK SUITE", flush=True)
    print("=======================================================\n", flush=True)

    results = {}

    benchmarks = [
        ("1. Application Initialization", bench_app_init.run_benchmark),
        ("2. Main Window Construction", bench_main_window.run_benchmark),
        ("3. Project Opening", bench_project_open.run_benchmark),
        ("4. File Explorer Traversal", bench_file_explorer.run_benchmark),
        ("5. Large Directory Indexing", bench_indexing.run_benchmark),
        ("6. Editor Large-File & Highlighting", bench_editor_large_file.run_benchmark),
        ("7. Terminal Output Rendering", bench_terminal_output.run_benchmark),
        ("8. AI Connection Latency", bench_ai_connection.run_benchmark),
        ("9. AI Streaming Token Render", bench_ai_streaming.run_benchmark),
        ("10. AI Agent Overhead", bench_agent_overhead.run_benchmark),
    ]

    for title, fn in benchmarks:
        print(f"Running {title}...", flush=True)
        t0 = time.perf_counter()
        try:
            res = fn()
            elapsed = (time.perf_counter() - t0) * 1000
            results[title] = res
            print(f"  [OK] Completed in {elapsed:.1f}ms: {res}", flush=True)
        except Exception as exc:
            print(f"  [FAIL] Error: {exc}", flush=True)
            results[title] = {"error": str(exc)}

    print("\n=======================================================", flush=True)
    print("BENCHMARK SUITE EXECUTION COMPLETE", flush=True)
    print("=======================================================\n", flush=True)
    return results


if __name__ == "__main__":
    all_results = run_full_suite()
    print(json.dumps(all_results, indent=2))

