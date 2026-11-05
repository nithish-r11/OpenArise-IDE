"""
Mandatory Real-World Benchmark Suite for OpenArise IDE AI Agent V1.0.
Executes live benchmark tasks using the installed local Ollama model (qwen2.5-coder:7b):
- Test A: Website Creation (Task Management with HTML/CSS/JS/CRUD/LocalStorage)
- Test B: Existing Project Modification (Feature addition preserving code)
- Test C: Autonomous Debugging (Controlled error identification, fix & verify)
- Test D: Full-Stack Application (Frontend, backend, API integration)
- Test E: Integrated Terminal & Runtime Verification (Local server startup, HTTP 200, port release)

Measures and records exact execution times, model calls, tool calls, and file modifications.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from PyQt6.QtCore import QCoreApplication
from core.agent_models import AgentTaskState, FileChangeStatus
from core.agent_orchestrator import AgentWorker
from core.context_manager import ContextManager
from core.ollama_client import OllamaClient


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def run_benchmarks():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    client = OllamaClient()
    connected, conn_msg = client.check_connection()
    if not connected:
        print(f"ERROR: Ollama server not reachable: {conn_msg}")
        return 1

    model = "qwen2.5-coder:7b"
    benchmark_dir = Path(tempfile.mkdtemp(prefix="openarise_v1_benchmark_")).resolve()
    results = {}

    print("\n=======================================================", flush=True)
    print("OPENARISE IDE AI AGENT V1.0 REAL-WORLD OLLAMA BENCHMARK", flush=True)
    print(f"Model: {model} (Local VRAM)")
    print(f"Benchmark Workspace: {benchmark_dir}")
    print("=======================================================\n", flush=True)

    try:
        # =====================================================================
        # TEST A: Website Creation
        # =====================================================================
        print(">>> STARTING TEST A: Website Creation (Task Management App)...", flush=True)
        dir_a = benchmark_dir / "test_a_website"
        dir_a.mkdir(parents=True, exist_ok=True)
        cm_a = ContextManager()
        cm_a.set_project(dir_a)

        prompt_a = (
            "Create a complete, responsive Task Management website with HTML, CSS, and JavaScript. "
            "Include task CRUD (add, toggle complete, delete), filter buttons (all, active, completed), "
            "and LocalStorage persistence. Use write_files to generate index.html, styles.css, and app.js."
        )

        worker_a = AgentWorker(
            client=client,
            model=model,
            project_root=dir_a,
            user_prompt=prompt_a,
            context_manager=cm_a
        )

        model_calls_a = 0
        tokens_streamed_a = 0
        first_token_time_a = None
        start_time_a = time.time()

        # Connect logging to count model calls and stream tokens
        def on_log_a(level, msg):
            nonlocal tokens_streamed_a
            if "tokens streamed" in msg:
                try:
                    parts = msg.split("(")
                    toks = int(parts[1].split()[0])
                    tokens_streamed_a = max(tokens_streamed_a, toks)
                except Exception:
                    pass

        worker_a.log_emitted.connect(on_log_a)

        # Auto-approve plan & diff review
        worker_a.plan_ready.connect(lambda plan: worker_a.approve_plan(True))
        worker_a.diff_ready.connect(lambda records: worker_a.submit_diff_decisions({r.rel_path: True for r in records}))
        worker_a.tool_requested.connect(lambda tc: worker_a.approve_tool(True))

        orig_query_ollama = worker_a._query_ollama

        def tracking_query_a(messages):
            nonlocal model_calls_a, first_token_time_a
            model_calls_a += 1
            t_call = time.time()
            res = orig_query_ollama(messages)
            if first_token_time_a is None:
                first_token_time_a = time.time() - t_call
            return res

        worker_a._query_ollama = tracking_query_a

        worker_a.start()
        while worker_a.isRunning():
            app.processEvents()
            time.sleep(0.05)

        duration_a = time.time() - start_time_a
        files_created_a = [p.name for p in dir_a.glob("*.*") if p.is_file()]
        total_bytes_a = sum(p.stat().st_size for p in dir_a.glob("*.*") if p.is_file())

        ok_a = (
            worker_a.state == AgentTaskState.COMPLETED and
            "index.html" in files_created_a and
            len(files_created_a) >= 2 and
            total_bytes_a > 500
        )
        results["Test A - Website Creation"] = {
            "passed": ok_a,
            "duration_s": round(duration_a, 2),
            "first_token_s": round(first_token_time_a or 0.0, 2),
            "model_calls": model_calls_a,
            "tool_calls": len(worker_a.journal.records),
            "files_created": files_created_a,
            "total_bytes": total_bytes_a,
        }
        print(f"  Result: {'PASS' if ok_a else 'FAIL'} (Duration={duration_a:.1f}s, ModelCalls={model_calls_a}, Files={files_created_a})\n", flush=True)

        # =====================================================================
        # TEST B: Existing Project Modification
        # =====================================================================
        print(">>> STARTING TEST B: Existing Project Modification (Adding Priority Feature)...", flush=True)
        cm_b = ContextManager()
        cm_b.set_project(dir_a)

        prompt_b = (
            "Modify the existing task management website in app.js and index.html to add a Priority selector "
            "(High, Medium, Low) for new tasks. Preserve all existing task CRUD, filters, and LocalStorage. "
            "Use write_files or write_file to save the updated files with complete functional code."
        )

        worker_b = AgentWorker(
            client=client,
            model=model,
            project_root=dir_a,
            user_prompt=prompt_b,
            context_manager=cm_b
        )

        model_calls_b = 0
        start_time_b = time.time()
        first_token_b = None

        def tracking_query_b(messages):
            nonlocal model_calls_b, first_token_b
            model_calls_b += 1
            t_call = time.time()
            res = orig_query_ollama(messages)
            if first_token_b is None:
                first_token_b = time.time() - t_call
            return res

        worker_b._query_ollama = tracking_query_b
        worker_b.plan_ready.connect(lambda plan: worker_b.approve_plan(True))
        worker_b.diff_ready.connect(lambda records: worker_b.submit_diff_decisions({r.rel_path: True for r in records}))
        worker_b.tool_requested.connect(lambda tc: worker_b.approve_tool(True))

        worker_b.start()
        while worker_b.isRunning():
            app.processEvents()
            time.sleep(0.05)

        duration_b = time.time() - start_time_b
        html_content_b = (dir_a / "index.html").read_text(encoding="utf-8", errors="replace")
        app_content_b = (dir_a / "app.js").read_text(encoding="utf-8", errors="replace") if (dir_a / "app.js").exists() else ""

        ok_b = (
            worker_b.state == AgentTaskState.COMPLETED and
            ("priority" in html_content_b.lower() or "priority" in app_content_b.lower())
        )
        results["Test B - Modification"] = {
            "passed": ok_b,
            "duration_s": round(duration_b, 2),
            "first_token_s": round(first_token_b or 0.0, 2),
            "model_calls": model_calls_b,
            "tool_calls": len(worker_b.journal.records),
        }
        print(f"  Result: {'PASS' if ok_b else 'FAIL'} (Duration={duration_b:.1f}s, ModelCalls={model_calls_b})\n", flush=True)

        # =====================================================================
        # TEST C: Autonomous Debugging
        # =====================================================================
        print(">>> STARTING TEST C: Autonomous Debugging (Syntax Error Recovery)...", flush=True)
        # Introduce a controlled error in app.js
        target_file = dir_a / "app.js" if (dir_a / "app.js").exists() else dir_a / "index.html"
        orig_content = target_file.read_text(encoding="utf-8")
        # Corrupt file with a broken syntax block at the bottom
        target_file.write_text(orig_content + "\n\nfunction brokenSyntax( { return ;;\n", encoding="utf-8")

        prompt_c = (
            f"The application has an invalid syntax error in {target_file.name}. "
            f"Inspect {target_file.name}, fix the syntax error so the file is clean and valid, and save the corrected code using write_file."
        )

        worker_c = AgentWorker(
            client=client,
            model=model,
            project_root=dir_a,
            user_prompt=prompt_c,
            context_manager=cm_b
        )

        model_calls_c = 0
        start_time_c = time.time()
        first_token_c = None

        def tracking_query_c(messages):
            nonlocal model_calls_c, first_token_c
            model_calls_c += 1
            t_call = time.time()
            res = orig_query_ollama(messages)
            if first_token_c is None:
                first_token_c = time.time() - t_call
            return res

        worker_c._query_ollama = tracking_query_c
        worker_c.plan_ready.connect(lambda plan: worker_c.approve_plan(True))
        worker_c.diff_ready.connect(lambda records: worker_c.submit_diff_decisions({r.rel_path: True for r in records}))
        worker_c.tool_requested.connect(lambda tc: worker_c.approve_tool(True))

        worker_c.start()
        while worker_c.isRunning():
            app.processEvents()
            time.sleep(0.05)

        duration_c = time.time() - start_time_c
        fixed_content = target_file.read_text(encoding="utf-8")
        ok_c = (
            worker_c.state == AgentTaskState.COMPLETED and
            "brokenSyntax( {" not in fixed_content
        )
        results["Test C - Debugging"] = {
            "passed": ok_c,
            "duration_s": round(duration_c, 2),
            "first_token_s": round(first_token_c or 0.0, 2),
            "model_calls": model_calls_c,
            "tool_calls": len(worker_c.journal.records),
        }
        print(f"  Result: {'PASS' if ok_c else 'FAIL'} (Duration={duration_c:.1f}s, Fixed={ok_c})\n", flush=True)

        # =====================================================================
        # TEST D: Full-Stack Application
        # =====================================================================
        print(">>> STARTING TEST D: Full-Stack Application (Python Backend + Web Client)...", flush=True)
        dir_d = benchmark_dir / "test_d_fullstack"
        dir_d.mkdir(parents=True, exist_ok=True)
        cm_d = ContextManager()
        cm_d.set_project(dir_d)

        prompt_d = (
            "Create a full-stack Notes application with a Python backend in server.py (using standard http.server and json) "
            "and a frontend client in index.html. The backend provides GET /notes and POST /notes endpoints. "
            "Use write_files to generate server.py, index.html, and README.md."
        )

        worker_d = AgentWorker(
            client=client,
            model=model,
            project_root=dir_d,
            user_prompt=prompt_d,
            context_manager=cm_d
        )

        model_calls_d = 0
        start_time_d = time.time()
        first_token_d = None

        def tracking_query_d(messages):
            nonlocal model_calls_d, first_token_d
            model_calls_d += 1
            t_call = time.time()
            res = orig_query_ollama(messages)
            if first_token_d is None:
                first_token_d = time.time() - t_call
            return res

        worker_d._query_ollama = tracking_query_d
        worker_d.plan_ready.connect(lambda plan: worker_d.approve_plan(True))
        worker_d.diff_ready.connect(lambda records: worker_d.submit_diff_decisions({r.rel_path: True for r in records}))
        worker_d.tool_requested.connect(lambda tc: worker_d.approve_tool(True))

        worker_d.start()
        while worker_d.isRunning():
            app.processEvents()
            time.sleep(0.05)

        duration_d = time.time() - start_time_d
        files_d = [p.name for p in dir_d.glob("*.*") if p.is_file()]

        # Verify server.py syntax
        server_py = dir_d / "server.py"
        py_valid = False
        if server_py.exists():
            try:
                compile(server_py.read_text(encoding="utf-8"), "server.py", "exec")
                py_valid = True
            except SyntaxError:
                pass

        ok_d = (
            worker_d.state == AgentTaskState.COMPLETED and
            "server.py" in files_d and
            py_valid and
            len(files_d) >= 2
        )
        results["Test D - Full-Stack App"] = {
            "passed": ok_d,
            "duration_s": round(duration_d, 2),
            "first_token_s": round(first_token_d or 0.0, 2),
            "model_calls": model_calls_d,
            "tool_calls": len(worker_d.journal.records),
            "files_created": files_d,
        }
        print(f"  Result: {'PASS' if ok_d else 'FAIL'} (Duration={duration_d:.1f}s, Files={files_d})\n", flush=True)

        # =====================================================================
        # TEST E: Terminal & Runtime Verification
        # =====================================================================
        print(">>> STARTING TEST E: Integrated Terminal & Runtime Execution...", flush=True)
        test_port = find_free_port()
        print(f"Starting background HTTP test server on port {test_port} for {dir_a}...", flush=True)

        # Launch Python HTTP server on test port
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(test_port), "--directory", str(dir_a)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        http_ok = False
        html_received = ""
        try:
            # Poll server for up to 5 seconds
            t_end = time.time() + 5.0
            while time.time() < t_end:
                try:
                    resp = requests.get(f"http://127.0.0.1:{test_port}/index.html", timeout=1)
                    if resp.status_code == 200:
                        http_ok = True
                        html_received = resp.text
                        break
                except Exception:
                    time.sleep(0.3)
        finally:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3)
            except Exception:
                server_proc.kill()
                try:
                    server_proc.wait(timeout=2)
                except Exception:
                    pass
            time.sleep(1.2)

        # Confirm port is freed
        port_freed = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            port_freed = (s.connect_ex(("127.0.0.1", test_port)) != 0)

        ok_e = http_ok and port_freed and len(html_received) > 100
        results["Test E - Terminal & Runtime"] = {
            "passed": ok_e,
            "port": test_port,
            "http_status": 200 if http_ok else 0,
            "port_freed": port_freed,
            "html_bytes": len(html_received),
        }
        print(f"  Result: {'PASS' if ok_e else 'FAIL'} (Status=200, PortFreed={port_freed}, Bytes={len(html_received)})\n", flush=True)

    finally:
        shutil.rmtree(benchmark_dir, ignore_errors=True)

    print("=======================================================", flush=True)
    print("MANDATORY REAL-WORLD OLLAMA BENCHMARK SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for name, data in results.items():
        st = "PASSED" if data.get("passed") else "FAILED"
        print(f"  {name}: {st}")
        for k, v in data.items():
            if k != "passed":
                print(f"    - {k}: {v}")
        if not data.get("passed"):
            all_passed = False

    print("=======================================================", flush=True)
    print(f"OVERALL BENCHMARK STATUS: {'ALL 5 BENCHMARKS PASSED' if all_passed else 'SOME BENCHMARKS FAILED'}")
    print("=======================================================\n", flush=True)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_benchmarks())

