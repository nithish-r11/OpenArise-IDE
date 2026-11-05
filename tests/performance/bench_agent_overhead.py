"""
Benchmark 10: AI Agent Task Execution Overhead & Tool Dispatch Latency
Measures non-inference overhead in the AI Agent loop:
prompt assembly, journal recording, diff computation, and tool execution.
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
from core.agent_models import AgentJournal, AgentToolCall, FileChangeType, FileChangeStatus
from core.agent_tools import AgentToolRegistry
from ui.agent_diff_dialog import AgentDiffDialog


def run_benchmark(iterations: int = 5) -> dict:
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_bench_agent_"))
    try:
        # Create base files
        f1 = temp_dir / "app.py"
        f1.write_text("def main():\n    print('Hello World')\n" * 50, encoding="utf-8")

        dispatch_times = []
        journal_times = []
        diff_dialog_times = []

        for _ in range(iterations):
            journal = AgentJournal(temp_dir)
            registry = AgentToolRegistry(temp_dir, journal)

            # 1. Tool execution (write_file dispatch & backup)
            t0 = time.perf_counter()
            call = AgentToolCall(
                id="call_bench",
                name="write_file",
                args={"path": "app.py", "contents": "def main():\n    print('Modified')\n" * 50}
            )
            ok, msg = registry.execute_tool(call)
            t1 = time.perf_counter()
            dispatch_times.append((t1 - t0) * 1000)

            # 2. Diff preparation & dialog instantiation
            proposed = [r for r in journal.records if r.status == FileChangeStatus.PROPOSED.value]
            t2 = time.perf_counter()
            dlg = AgentDiffDialog(proposed)
            app.processEvents()
            t3 = time.perf_counter()
            diff_dialog_times.append((t3 - t2) * 1000)

            # 3. Apply accepted changes
            for r in proposed:
                r.status = FileChangeStatus.ACCEPTED.value
            t4 = time.perf_counter()
            cnt, files = journal.apply_accepted()
            t5 = time.perf_counter()
            journal_times.append((t5 - t4) * 1000)

        return {
            "agent_write_tool_dispatch_ms_median": round(statistics.median(dispatch_times), 2),
            "agent_diff_dialog_construct_ms_median": round(statistics.median(diff_dialog_times), 2),
            "agent_journal_disk_apply_ms_median": round(statistics.median(journal_times), 2),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_benchmark()
    print("Benchmark 10 Results:", res)

