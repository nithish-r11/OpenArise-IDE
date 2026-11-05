"""
Live Manual Acceptance Test: AI Agent in Non-Git Project
Verifies that the autonomous AI agent can successfully execute a task,
handle optional Git inspection (such as inspect_git_diff / inspect_git_status)
on a non-Git repository, display proposed changes via AgentJournal,
approve Diff Review, apply the file to disk, and finish in COMPLETED state
with accurate modified file counts.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication

from core.agent_models import AgentTaskState
from core.agent_orchestrator import AgentWorker
from core.git_service import GitService
from core.ollama_client import OllamaClient


def run_live_test() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    print("\n==================================================================", flush=True)
    print("STARTING LIVE NON-GIT PROJECT AGENT TEST (OLLAMA QWEN2.5-CODER:7B)", flush=True)
    print("==================================================================\n", flush=True)

    client = OllamaClient()
    connected, models = client.check_connection()
    if not connected:
        print("[FAIL] Cannot connect to local Ollama server at http://127.0.0.1:11434", flush=True)
        return 1

    model = "qwen2.5-coder:7b"
    print(f"Ollama connected. Model: {model}\n", flush=True)

    test_workspace = Path(tempfile.mkdtemp(prefix="openarise_nongit_accept_")).resolve()
    print(f"Non-Git Test Workspace: {test_workspace}", flush=True)

    # Explicitly verify project is NOT a Git repository
    is_git = GitService.is_git_repository(test_workspace)
    print(f"Is Git Repository: {is_git} (Expected: False)", flush=True)
    if is_git:
        print("[FAIL] Test workspace must not be a Git repository.", flush=True)
        return 1

    try:
        worker = AgentWorker(
            client=client,
            model=model,
            project_root=test_workspace,
            user_prompt="Create a Python file named agent_test.py containing a Hello World program.",
            max_steps=5,
            max_retries=3,
        )

        completed_data = {}
        failed_data = {}
        tool_calls_observed = []

        def on_plan_ready(plan):
            print(f"  [PLAN READY] {len(plan.steps)} steps planned:", flush=True)
            for s in plan.steps:
                print(f"    - Step {s.step_number}: {s.description}", flush=True)
            worker.approve_plan(True)

        def on_tool_req(call):
            print(f"  [TOOL REQUEST] Approval requested for '{call.name}'. Auto-approving...", flush=True)
            worker.approve_tool(True)

        def on_tool_fin(call):
            status_str = "SUCCESS" if not call.error else f"FAIL ({call.error})"
            tool_calls_observed.append(call.name)
            print(f"  [TOOL FINISHED] {call.name} -> {status_str}", flush=True)

        def on_diff_ready(records):
            print(f"  [DIFF READY] {len(records)} proposed record(s) ready for review:", flush=True)
            for r in records:
                print(f"    - {r.rel_path} ({r.change_type})", flush=True)
            # Accept all proposed changes
            decisions = {r.rel_path: True for r in records}
            worker.submit_diff_decisions(decisions)

        def on_completed(summary, suggested_commit):
            completed_data["summary"] = summary
            completed_data["suggested_commit"] = suggested_commit
            print(f"  [TASK COMPLETED]\n    Summary: {summary.strip()}\n    Commit: '{suggested_commit}'", flush=True)

        def on_failed(error):
            failed_data["error"] = error
            print(f"  [TASK FAILED] Error: {error}", flush=True)

        worker.plan_ready.connect(on_plan_ready)
        worker.tool_requested.connect(on_tool_req)
        worker.tool_finished.connect(on_tool_fin)
        worker.diff_ready.connect(on_diff_ready)
        worker.task_completed.connect(on_completed)
        worker.task_failed.connect(on_failed)

        print("\nStarting AgentWorker in non-Git workspace...", flush=True)
        worker.start()

        # Event loop with 180s timeout
        t_start = time.time()
        while worker.isRunning() and (time.time() - t_start < 180):
            app.processEvents()
            time.sleep(0.1)

        if worker.isRunning():
            print("  [TIMEOUT] Worker exceeded time limit. Cancelling...", flush=True)
            worker.cancel()
            worker.wait(5000)

        worker.wait()
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()

        print(f"\nFinal Worker State: {worker.state}", flush=True)
        print(f"Tools executed: {tool_calls_observed}", flush=True)

        created_file = test_workspace / "agent_test.py"
        file_exists = created_file.exists()
        print(f"Created file exists: {file_exists}", flush=True)

        file_content = created_file.read_text(encoding="utf-8") if file_exists else ""
        print(f"File content:\n---\n{file_content.strip()}\n---", flush=True)

        has_hello = "hello" in file_content.lower()
        is_completed = worker.state == AgentTaskState.COMPLETED
        has_modified_1 = "Files modified: 1" in completed_data.get("summary", "")
        no_failed_error = len(failed_data) == 0

        success = is_completed and file_exists and has_hello and has_modified_1 and no_failed_error

        print("\nVerification Checklist:")
        print(f"  1. Task Completed (state == COMPLETED): {is_completed}", flush=True)
        print(f"  2. File exists on disk: {file_exists}", flush=True)
        print(f"  3. File contains 'Hello World': {has_hello}", flush=True)
        print(f"  4. Accurate file count ('Files modified: 1'): {has_modified_1}", flush=True)
        print(f"  5. No failure errors: {no_failed_error}", flush=True)

        print("\n==================================================================", flush=True)
        if success:
            print("LIVE NON-GIT AGENT TEST RESULT: PASS", flush=True)
        else:
            print("LIVE NON-GIT AGENT TEST RESULT: FAIL", flush=True)
        print("==================================================================\n", flush=True)
        return 0 if success else 1

    finally:
        try:
            shutil.rmtree(test_workspace, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(run_live_test())

