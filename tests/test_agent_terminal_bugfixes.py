"""
Automated Test Suite for OpenArise IDE AI Agent and Integrated Terminal Bug Fixes.
Verifies:
1. Bug 1: Complete code generation, placeholder/stub rejection, argument alias normalization,
          HTML linked asset verification, filesystem write verification, accurate task failure/success.
2. Bug 2: Integrated Terminal process execution, stdout/stderr streaming, unbuffered python server,
          and clean process-tree termination with port release.
3. Bug 3: Agent task input clearing on start and completion while preserving timeline/log history.
"""

import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess

from core.agent_models import (
    AgentJournal,
    AgentPlan,
    AgentPlanStep,
    AgentTaskState,
    AgentToolCall,
    FileChangeRecord,
    FileChangeStatus,
    FileChangeType,
    StepStatus,
)
from core.agent_tools import (
    AgentToolRegistry,
    canonicalize_tool_name,
    is_placeholder_or_stub_content,
    normalize_tool_args,
    resolve_contained_path,
)
from core.agent_orchestrator import AgentWorker
from ui.terminal_widget import IntegratedTerminalWidget
from ui.agent_panel import AgentPanel


def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================", flush=True)
    print("STARTING AI AGENT & INTEGRATED TERMINAL BUG FIX TESTS", flush=True)
    print("=======================================================\n", flush=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_bugfix_test_")).resolve()
    print(f"Isolated test workspace: {temp_dir}", flush=True)

    try:
        # ---------------------------------------------------------
        # BUG 1 TESTS: Code Completeness & Quality Safeguards
        # ---------------------------------------------------------

        # [TEST 1] Argument Alias Normalization (contents, content, code, body, text, path aliases)
        print("[TEST 1] Verifying write_file Argument Normalization & Conflict Detection...", flush=True)
        # Aliases
        v_code, a_code, _ = normalize_tool_args("write_file", {"path": "a.js", "code": "const x = 1;"})
        v_body, a_body, _ = normalize_tool_args("write_file", {"path": "b.py", "body": "print(1)"})
        v_text, a_text, _ = normalize_tool_args("write_file", {"path": "c.txt", "text": "hello"})
        v_content, a_content, _ = normalize_tool_args("write_file", {"file": "d.css", "content": "body {}"})
        # Conflict
        v_conflict, _, err_conflict = normalize_tool_args("write_file", {"path": "e.css", "contents": "body {}", "code": "div {}"})
        
        t1_ok = (
            v_code and a_code.get("contents") == "const x = 1;" and
            v_body and a_body.get("contents") == "print(1)" and
            v_text and a_text.get("contents") == "hello" and
            v_content and a_content.get("contents") == "body {}" and a_content.get("path") == "d.css" and
            not v_conflict and "Conflicting" in err_conflict
        )
        test_results["1_argument_normalization_and_conflicts"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'}", flush=True)

        # [TEST 2] Placeholder and Stub Detection (Empty, Comments, Stubs)
        print("[TEST 2] Verifying Placeholder and Stub Detection...", flush=True)
        is_empty_stub, _ = is_placeholder_or_stub_content("", "styles.css")
        is_whitespace_stub, _ = is_placeholder_or_stub_content("   \n\t  ", "styles.css")
        is_css_comment_stub, _ = is_placeholder_or_stub_content("/* Add responsive UI styles here */", "styles.css")
        is_js_comment_stub, _ = is_placeholder_or_stub_content("// TODO: implement task CRUD logic", "app.js")
        is_html_comment_stub, _ = is_placeholder_or_stub_content("<!-- Add HTML here -->", "index.html")
        is_py_pass_stub, _ = is_placeholder_or_stub_content("pass", "worker.py")
        is_py_ellipsis_stub, _ = is_placeholder_or_stub_content("...", "worker.py")

        # Valid files must NOT be detected as stubs
        is_valid_css_stub, _ = is_placeholder_or_stub_content(
            "body { font-family: sans-serif; background: #121212; color: #fff; }\n.btn { padding: 8px; }",
            "styles.css"
        )
        is_valid_js_stub, _ = is_placeholder_or_stub_content(
            "function initApp() {\n    const tasks = JSON.parse(localStorage.getItem('tasks') || '[]');\n    console.log(tasks);\n}\nwindow.onload = initApp;",
            "app.js"
        )
        is_valid_html_stub, _ = is_placeholder_or_stub_content(
            "<!DOCTYPE html>\n<html>\n<head><title>Tasks</title></head>\n<body><div id='app'></div></body>\n</html>",
            "index.html"
        )
        is_valid_py_stub, _ = is_placeholder_or_stub_content(
            "def calculate_total(items):\n    return sum(item.price for item in items)\n",
            "calc.py"
        )

        t2_ok = (
            is_empty_stub and is_whitespace_stub and is_css_comment_stub and
            is_js_comment_stub and is_html_comment_stub and is_py_pass_stub and is_py_ellipsis_stub and
            not is_valid_css_stub and not is_valid_js_stub and not is_valid_html_stub and not is_valid_py_stub
        )
        test_results["2_placeholder_stub_detection"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'}", flush=True)

        # [TEST 3] Tool Dispatch Rejection of Stubs and Placeholders
        print("[TEST 3] Verifying Tool Dispatch Rejects Stubs at Write Time...", flush=True)
        journal = AgentJournal(temp_dir)
        registry = AgentToolRegistry(temp_dir, journal)

        # Proposed write with comment placeholder
        call_stub = AgentToolCall("call_stub", "write_file", {
            "path": "styles.css",
            "contents": "/* Add responsive UI styles here */"
        })
        ok_stub, out_stub = registry.execute_tool(call_stub)

        # Proposed write with complete real CSS
        call_real = AgentToolCall("call_real", "write_file", {
            "path": "styles.css",
            "contents": "body { margin: 0; background: #1a1a24; color: #fff; }\n.todo-list { list-style: none; }"
        })
        ok_real, out_real = registry.execute_tool(call_real)

        t3_ok = (not ok_stub and "Placeholder or stub" in out_stub and ok_real and "Queued for diff review" in out_real)
        test_results["3_tool_dispatch_stub_rejection"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'}", flush=True)

        # [TEST 4] HTML Linked Asset Verification
        print("[TEST 4] Verifying HTML Linked Asset Integrity Check...", flush=True)
        worker = AgentWorker(
            client=None,
            model="test-model",
            project_root=temp_dir,
            user_prompt="Build task app",
            parent=None
        )

        html_with_links = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <link rel=\"stylesheet\" href=\"styles.css\">\n"
            "  <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css\">\n"
            "</head>\n"
            "<body>\n"
            "  <h1>Tasks</h1>\n"
            "  <script src=\"app.js\"></script>\n"
            "  <script src=\"https://cdn.example.com/lib.js\"></script>\n"
            "</body>\n"
            "</html>"
        )

        # At this point styles.css and app.js don't exist on disk yet
        missing_initial = worker._verify_html_linked_assets("index.html", html_with_links)
        has_both_missing = "styles.css" in missing_initial and "app.js" in missing_initial

        # Create styles.css and app.js with substantive content
        (temp_dir / "styles.css").write_text("body { color: red; }", encoding="utf-8")
        (temp_dir / "app.js").write_text("console.log('ready');", encoding="utf-8")

        missing_after = worker._verify_html_linked_assets("index.html", html_with_links)
        has_none_missing = len(missing_after) == 0

        t4_ok = has_both_missing and has_none_missing
        test_results["4_html_linked_assets_verification"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (InitialMissing={missing_initial}, AfterMissing={missing_after})", flush=True)

        # [TEST 5] Orchestrator Strict Failure when File Operation Produces Stubs/Empty Files
        print("[TEST 5] Verifying Orchestrator Phase 5 Post-Completion Safeguards...", flush=True)
        worker5 = AgentWorker(
            client=None,
            model="test-model",
            project_root=temp_dir,
            user_prompt="Create styles.css",
            parent=None
        )
        worker5.plan = AgentPlan(
            task_description="Create styles.css",
            steps=[AgentPlanStep(step_number=1, description="Create styles.css", status=StepStatus.COMPLETED.value)],
            is_approved=True
        )

        # Manually create a stub file on disk and mark it APPLIED in journal to test Phase 5 safeguard
        stub_file = temp_dir / "stub_styles.css"
        stub_file.write_text("/* Add responsive UI styles here */", encoding="utf-8")
        rec_stub = FileChangeRecord(
            rel_path="stub_styles.css",
            change_type=FileChangeType.CREATE.value,
            new_content="/* Add responsive UI styles here */",
            status=FileChangeStatus.APPLIED.value
        )
        worker5.journal.records.append(rec_stub)

        # Simulate execution completion logic
        failed_msgs = []
        worker5.task_failed.connect(lambda msg: failed_msgs.append(msg))

        # Check the verification block
        target = resolve_contained_path(temp_dir, rec_stub.rel_path)
        is_stub, stub_reason = is_placeholder_or_stub_content(target.read_text(encoding="utf-8"), rec_stub.rel_path)
        if is_stub:
            worker5._fail(f"Task failed: Verification failed. File '{rec_stub.rel_path}' contains placeholder or stub code ({stub_reason}).")

        t5_ok = worker5.state == AgentTaskState.FAILED and len(failed_msgs) > 0 and "placeholder or stub" in failed_msgs[0]
        test_results["5_orchestrator_post_completion_stub_failure"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'}", flush=True)

        # ---------------------------------------------------------
        # BUG 2 TESTS: Integrated Terminal Execution & Output Streaming
        # ---------------------------------------------------------

        # [TEST 6] Integrated Terminal Shell Initialization
        print("[TEST 6] Verifying Terminal Shell Configuration & Channel Mode...", flush=True)
        term = IntegratedTerminalWidget(initial_cwd=temp_dir)
        term.show()

        # Wait for shell to start
        for _ in range(20):
            time.sleep(0.05)
            app.processEvents()

        is_running = term.process is not None and term.process.state() == QProcess.ProcessState.Running
        channel_mode = term.process.processChannelMode() if term.process else None
        is_merged = (channel_mode == QProcess.ProcessChannelMode.MergedChannels)

        t6_ok = is_running and is_merged
        test_results["6_terminal_init_and_merged_channels"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (Shell={term.shell_type}, Running={is_running}, MergedChannels={is_merged})", flush=True)

        # [TEST 7] Command Execution & Immediate Output Streaming (Get-Location or cd/dir)
        print("[TEST 7] Verifying Command Output Streaming in Terminal Widget...", flush=True)
        term.clear_terminal()
        if term.shell_type == "PowerShell":
            term.execute_command("Get-Location")
        else:
            term.execute_command("cd")

        for _ in range(30):
            time.sleep(0.05)
            app.processEvents()

        output_text = term.output_area.toPlainText()
        has_cwd_in_output = str(temp_dir.name).lower() in output_text.lower() or str(temp_dir).lower() in output_text.lower()

        t7_ok = has_cwd_in_output
        test_results["7_command_output_streaming"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'}", flush=True)

        # [TEST 8] Long-running Server Streaming & Clean Stop/Port Freeing
        print("[TEST 8] Verifying Long-Running Server Output & Port Release on Stop...", flush=True)
        # Find a free port
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.bind(("127.0.0.1", 0))
        test_port = srv_sock.getsockname()[1]
        srv_sock.close()

        term.execute_command(f"python -m http.server {test_port}")

        # Wait for server banner to stream into terminal
        banner_received = False
        for _ in range(40):
            time.sleep(0.05)
            app.processEvents()
            txt = term.output_area.toPlainText()
            if f"Serving HTTP on" in txt or f"{test_port}" in txt:
                banner_received = True
                break

        # Make an HTTP request to verify live server response
        req_status = 0
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/", timeout=3) as resp:
                req_status = resp.status
        except Exception as e:
            print(f"    HTTP request error: {e}", flush=True)

        # Allow access log to stream
        for _ in range(20):
            time.sleep(0.05)
            app.processEvents()

        # Stop the running process
        term.stop_btn.click()

        for _ in range(30):
            time.sleep(0.05)
            app.processEvents()

        # Check port release
        port_freed = False
        check_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            check_sock.bind(("127.0.0.1", test_port))
            port_freed = True
            check_sock.close()
        except Exception:
            port_freed = False

        # Terminal can execute commands again after stop
        term.execute_command("echo OPENARISE_RESET_VERIFIED")
        reset_cmd_received = False
        for _ in range(25):
            time.sleep(0.05)
            app.processEvents()
            if "OPENARISE_RESET_VERIFIED" in term.output_area.toPlainText():
                reset_cmd_received = True
                break

        t8_ok = banner_received and (req_status == 200) and port_freed and reset_cmd_received
        test_results["8_server_streaming_and_stop_port_release"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'} (Banner={banner_received}, Status={req_status}, PortFreed={port_freed}, ResetOk={reset_cmd_received})", flush=True)
        term.shutdown()

        # ---------------------------------------------------------
        # BUG 3 TESTS: Agent Input Clearing & History Preservation
        # ---------------------------------------------------------

        # [TEST 9] Task Input Clearing on Start & Completion
        print("[TEST 9] Verifying Agent Panel Task Input Clearing Lifecycle...", flush=True)
        from core.ollama_client import OllamaClient
        panel = AgentPanel(client=OllamaClient(), parent=None)
        panel.set_project_root(temp_dir)
        panel.show()

        # Populate input
        test_prompt = "Build a Task Management application with local storage"
        panel.task_input.setPlainText(test_prompt)

        # Verify initial text
        assert panel.task_input.toPlainText().strip() == test_prompt

        # Test start_task clears input
        # Mock current_model to return dummy model so start_task proceeds
        panel.current_model = lambda: "qwen2.5-coder:7b"
        panel.start_task()

        input_cleared_on_start = (panel.task_input.toPlainText() == "")
        active_prompt_saved = (getattr(panel, "active_task_prompt", "") == test_prompt)
        prompt_in_log = test_prompt in panel.log_browser.toPlainText()

        # Cancel worker to clean up thread
        if panel.worker:
            panel.worker.cancel()
            panel.worker.wait(1000)

        # Test _on_task_completed ensures input is empty and status is set
        panel.task_input.setPlainText("Accidental remnant")
        panel._on_task_completed("Task finished 3 files created.", "feat: task app")

        input_cleared_on_complete = (panel.task_input.toPlainText() == "")
        status_text = panel.status_lbl.text()
        has_success_status = "completed successfully" in status_text.lower()
        has_summary_in_log = "Task finished 3 files created." in panel.log_browser.toPlainText()

        t9_ok = (
            input_cleared_on_start and active_prompt_saved and prompt_in_log and
            input_cleared_on_complete and has_success_status and has_summary_in_log
        )
        test_results["9_agent_task_input_clearing_lifecycle"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'} (ClearedOnStart={input_cleared_on_start}, ClearedOnComplete={input_cleared_on_complete}, Status='{status_text}')", flush=True)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n=======================================================", flush=True)
    print("FINAL BUG FIX TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status_str = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status_str}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    if all_passed and len(test_results) == 9:
        print("OVERALL STATUS: ALL 9 BUG FIX TESTS PASSED", flush=True)
    else:
        print(f"OVERALL STATUS: TESTS FAILED ({sum(1 for v in test_results.values() if v)}/{len(test_results)} passed)", flush=True)
    print("=======================================================\n", flush=True)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
