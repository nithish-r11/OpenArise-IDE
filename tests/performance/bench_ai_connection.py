"""
Benchmark 8: AI Connection & Metadata Inspection Latency
Measures round-trip latency to local Ollama daemon for health checks, model tags, and running processes.
"""

from __future__ import annotations
import statistics
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.ollama_client import OllamaClient


def run_benchmark(iterations: int = 5) -> dict:
    client = OllamaClient()

    conn_times = []
    list_times = []
    ps_times = []

    for _ in range(iterations):
        # 1. Connection check (/api/tags with timeout)
        t0 = time.perf_counter()
        ok, msg = client.check_connection()
        t1 = time.perf_counter()
        conn_times.append((t1 - t0) * 1000)

        # 2. Detailed list (/api/tags + parsing)
        t0 = time.perf_counter()
        models = client.list_models_detailed()
        t1 = time.perf_counter()
        list_times.append((t1 - t0) * 1000)

        # 3. Running models inspection (/api/ps)
        t0 = time.perf_counter()
        running = client.list_running_models()
        t1 = time.perf_counter()
        ps_times.append((t1 - t0) * 1000)

    return {
        "ollama_check_connection_ms_median": round(statistics.median(conn_times), 2),
        "ollama_check_connection_ms_min": round(min(conn_times), 2),
        "ollama_check_connection_ms_max": round(max(conn_times), 2),
        "ollama_list_models_detailed_ms_median": round(statistics.median(list_times), 2),
        "ollama_list_running_ps_ms_median": round(statistics.median(ps_times), 2),
    }


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 8 Results:", res)

