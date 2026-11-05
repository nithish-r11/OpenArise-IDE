"""
Benchmark 9: AI Streaming Response Rendering & Token Throughput Overhead
Measures the client-side parsing, Qt signal emission, and QTextEdit layout overhead
when consuming a stream of 200 tokens.
"""

from __future__ import annotations
import json
import statistics
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication
from ui.chat_panel import ChatPanel
from core.ollama_client import OllamaClient


def run_benchmark(iterations: int = 3, num_tokens: int = 200) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)

    # Simulate 200 streamed token chunks
    mock_tokens = [f"token_{i} " for i in range(num_tokens)]

    render_times = []
    for _ in range(iterations):
        chat = ChatPanel()
        chat.begin_response()
        app.processEvents()

        t0 = time.perf_counter()
        for tok in mock_tokens:
            chat.append_token(tok)
        chat.finish_response()
        app.processEvents()
        t1 = time.perf_counter()

        render_times.append((t1 - t0) * 1000)

    return {
        "chat_streaming_200_tokens_ms_median": round(statistics.median(render_times), 2),
        "chat_streaming_200_tokens_ms_min": round(min(render_times), 2),
        "chat_streaming_200_tokens_ms_max": round(max(render_times), 2),
        "tokens_per_second_client_capacity": round(num_tokens / (statistics.median(render_times) / 1000.0), 2),
    }


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 9 Results:", res)

