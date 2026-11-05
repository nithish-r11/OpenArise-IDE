"""
Live Acceptance Verification for OpenArise IDE Critical Repairs:
- Test A: General AI Agent ("Create a Python file named agent_test.py containing a Hello World program")
- Test B: Website Builder ("Create a modern responsive technology company website...")
- Test C: Local Website Server (start, verify HTTP 200, clean termination)
"""

import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from core.agent_models import AgentTaskState
from core.agent_orchestrator import AgentWorker
from core.ollama_client import OllamaClient
from core.website_generator import AIWebsiteGenerator, WebsiteSpec
from core.website_server import WebsiteServerManager, WebsiteServerState
from ui.agent_diff_dialog import AgentDiffDialog


def run_acceptance_tests() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    print("\n==================================================================", flush=True)
    print("STARTING LIVE ACCEPTANCE TESTS (LIVE OLLAMA QWEN2.5-CODER:7B)", flush=True)
    print("==================================================================\n", flush=True)

    client = OllamaClient()
    connected, models = client.check_connection()
    if not connected:
        print("[FAIL] Cannot connect to local Ollama server at http://127.0.0.1:11434", flush=True)
        return 1

    model = "qwen2.5-coder:7b"
    print(f"Ollama connected. Active model: {model}\n", flush=True)

    work_dir = Path(tempfile.mkdtemp(prefix="openarise_accept_live_")).resolve()
    print(f"Acceptance workspace: {work_dir}\n", flush=True)

    try:
        # ==================================================================
        # TEST A: General AI Agent Mode
        # ==================================================================
        print("[TEST A] General Agent: 'Create a Python file named agent_test.py containing a Hello World program.'", flush=True)
        agent_project = work_dir / "agent_proj"
        agent_project.mkdir(parents=True, exist_ok=True)

        worker = AgentWorker(
            client=client,
            model=model,
            project_root=agent_project,
            user_prompt="Create a Python file named agent_test.py containing a Hello World program.",
            max_steps=5,
            max_retries=3,
        )

        completed_data = {}
        failed_data = {}

        def on_plan_ready(plan):
            print(f"  Plan generated: {len(plan.steps)} steps. Auto-approving plan...", flush=True)
            for s in plan.steps:
                print(f"    - Step {s.step_number}: {s.description}", flush=True)
            worker.approve_plan(True)

        def on_tool_req(call):
            print(f"  Tool approval requested for '{call.name}'. Auto-approving...", flush=True)
            worker.approve_tool(True)

        def on_diff_ready(records):
            print(f"  Diff Review ready with {len(records)} proposed file(s):", flush=True)
            decisions = {}
            for r in records:
                print(f"    - {r.rel_path} ({r.change_type})", flush=True)
                decisions[r.rel_path] = True
            print("  Accepting all proposed changes...", flush=True)
            worker.submit_diff_decisions(decisions)

        def on_task_completed(summary, commit):
            print(f"  Task Completed Event Received!", flush=True)
            print(f"    Summary: {summary}", flush=True)
            print(f"    Commit: {commit}", flush=True)
            completed_data["summary"] = summary
            completed_data["commit"] = commit

        def on_task_failed(err):
            print(f"  Task Failed Event Received: {err}", flush=True)
            failed_data["error"] = err

        worker.log_emitted.connect(lambda lvl, msg: print(f"    [{lvl.upper()}] {msg}", flush=True))
        worker.plan_ready.connect(on_plan_ready)
        worker.tool_requested.connect(on_tool_req)
        worker.diff_ready.connect(on_diff_ready)
        worker.task_completed.connect(on_task_completed)
        worker.task_failed.connect(on_task_failed)

        worker.start()

        # Wait for worker to finish (up to 180 seconds)
        t_start = time.time()
        while worker.isRunning() and (time.time() - t_start < 180):
            app.processEvents()
            time.sleep(0.1)

        if worker.isRunning():
            print("  [TIMEOUT] Worker exceeded time limit. Cancelling...", flush=True)
            worker.cancel()
            worker.wait(5000)

        # Flush queued Qt signals from worker thread
        worker.wait()
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()

        print(f"  Worker State: {worker.state}, CompletedData: {completed_data}, FailedData: {failed_data}", flush=True)

        created_file = agent_project / "agent_test.py"
        test_a_ok = (
            worker.state == AgentTaskState.COMPLETED
            and created_file.exists()
            and "hello" in created_file.read_text(encoding="utf-8").lower()
            and "Files modified: 1" in completed_data.get("summary", "")
        )

        print(f"  File exists: {created_file.exists()}", flush=True)
        if created_file.exists():
            print(f"  File content:\n---\n{created_file.read_text(encoding='utf-8').strip()}\n---", flush=True)
        print(f"  Result Test A: {'PASS' if test_a_ok else 'FAIL'}\n", flush=True)

        if not test_a_ok:
            return 1

        # ==================================================================
        # TEST B: Website Builder Generation & Diff Review
        # ==================================================================
        print("[TEST B] Website Builder: 'Create a modern responsive technology company website with Home, Services, About and Contact sections.'", flush=True)
        web_spec = WebsiteSpec(
            name="tech_company_site",
            dest_dir=work_dir,
            prompt="Create a modern responsive technology company website with Home, Services, About and Contact sections.",
            tech="html",
            is_multipage=False,
            model=model
        )

        print("  Generating website files with local AI model...", flush=True)
        records = AIWebsiteGenerator.generate_website(web_spec)
        print(f"  Generated {len(records)} file(s):", flush=True)
        for r in records:
            print(f"    - {r.rel_path} ({len(r.new_content or '')} bytes)", flush=True)

        # Open Diff Review Dialog
        diff_dialog = AgentDiffDialog(records)
        diff_dialog.setWindowTitle(f"Review Website Files — {web_spec.name}")
        # Test get_decisions and get_accepted_records
        decisions = diff_dialog.get_decisions()
        accepted_records = diff_dialog.get_accepted_records()

        print(f"  Diff Review verified: {len(accepted_records)} accepted records retrieved without crash.", flush=True)

        # Apply accepted files to disk
        site_dir = work_dir / web_spec.name
        site_dir.mkdir(parents=True, exist_ok=True)
        for rec in accepted_records:
            target_file = site_dir / rec.rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(rec.new_content or "", encoding="utf-8")

        index_exists = (site_dir / "index.html").exists()
        css_exists = (site_dir / "css" / "styles.css").exists() or (site_dir / "styles.css").exists()
        test_b_ok = index_exists and len(accepted_records) >= 3

        print(f"  index.html created: {index_exists}", flush=True)
        print(f"  Result Test B: {'PASS' if test_b_ok else 'FAIL'}\n", flush=True)

        if not test_b_ok:
            return 1

        # ==================================================================
        # TEST C: Local Website Server (Start, Probe, Clean Termination)
        # ==================================================================
        print("[TEST C] Local Website Server: Start, HTTP GET verification, and Clean Termination", flush=True)
        server_mgr = WebsiteServerManager(site_dir)
        server_started = server_mgr.start()
        print(f"  Server start initiated: {server_started}", flush=True)

        # Wait up to 10 seconds for server to reach RUNNING state
        t_wait = time.time()
        while server_mgr.state != WebsiteServerState.RUNNING and (time.time() - t_wait < 10):
            app.processEvents()
            time.sleep(0.1)

        url = server_mgr.url
        print(f"  Server State: {server_mgr.state}, Bound URL: {url}", flush=True)

        # HTTP GET Request
        http_ok = False
        if server_mgr.state == WebsiteServerState.RUNNING and url:
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    body = response.read().decode("utf-8")
                    status_code = response.getcode()
                    print(f"  HTTP GET {url} -> Status Code: {status_code}, Bytes: {len(body)}", flush=True)
                    http_ok = (status_code == 200) and len(body) > 0
            except Exception as exc:
                print(f"  HTTP GET failed: {exc}", flush=True)

        # Stop Server
        print("  Stopping local website server...", flush=True)
        server_mgr.stop()
        time.sleep(0.5)
        is_stopped = server_mgr.state == WebsiteServerState.STOPPED
        print(f"  Server stopped cleanly: {is_stopped}", flush=True)

        test_c_ok = http_ok and is_stopped
        print(f"  Result Test C: {'PASS' if test_c_ok else 'FAIL'}\n", flush=True)

        if not test_c_ok:
            return 1

        print("==================================================================", flush=True)
        print("ALL ACCEPTANCE TESTS (A, B, C) PASSED SUCCESSFULLY WITH LIVE MODEL!", flush=True)
        print("==================================================================\n", flush=True)
        return 0

    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(run_acceptance_tests())

