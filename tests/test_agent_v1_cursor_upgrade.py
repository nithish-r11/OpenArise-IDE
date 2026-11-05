"""
Comprehensive Automated Test Suite for OpenArise IDE AI Agent V1.0 Upgrade.
Verifies:
1. Reusable Codebase Understanding & Project Profiling (static web, python, dependencies, entrypoints).
2. Fast AST and Regex Symbol Extraction (Python classes, functions, route decorators, JS components).
3. Compact Workspace Summary generation (Cursor-level token optimization).
4. Symbol Search tool dispatch and resolution.
5. Batch 'write_files' atomic multi-file creation and diff review staging.
6. Surgical 'edit_file' search-and-replace with whitespace and content preservation.
7. Enhanced 'read_file' with line range inspection and line numbering.
8. Autonomous Build, Run, and Test Runnable Detection.
9. Autonomous Self-Healing Debugger recovery cycle.
10. Streaming Token Progress emission in AgentWorker.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    normalize_tool_args,
    resolve_contained_path,
)
from core.context_manager import (
    ContextManager,
    ProjectProfile,
    extract_javascript_symbols,
    extract_python_symbols,
)
from core.agent_orchestrator import AgentWorker


def run_tests():
    test_results = {}
    temp_dir = Path(tempfile.mkdtemp(prefix="openarise_v1_test_"))
    print("\n=======================================================", flush=True)
    print("STARTING AI AGENT V1.0 CURSOR-LEVEL UPGRADE TESTS", flush=True)
    print("=======================================================", flush=True)
    print(f"Isolated test workspace: {temp_dir}\n", flush=True)

    try:
        # [TEST 1] Project Profiling & Framework Detection
        print("[TEST 1] Verifying Reusable Codebase Understanding & Project Profiling...", flush=True)
        # Create a mock web project structure
        (temp_dir / "index.html").write_text("<!DOCTYPE html><html><head><title>App</title><link rel='stylesheet' href='styles.css'></head><body><script src='app.js'></script></body></html>", encoding="utf-8")
        (temp_dir / "styles.css").write_text("body { font-family: sans-serif; }", encoding="utf-8")
        (temp_dir / "app.js").write_text("function initApp() { console.log('ready'); }\nclass TaskStore { constructor() { this.tasks = []; } }", encoding="utf-8")
        
        cm = ContextManager()
        cm.set_project(temp_dir)
        profile = cm.get_project_profile()

        t1_ok = (
            "Static Web Application" in profile.project_type and
            "index.html" in profile.entrypoints and
            "index.html" in profile.file_tree and
            "styles.css" in profile.file_tree and
            "app.js" in profile.file_tree and
            "app.js" in profile.symbols
        )
        test_results["1_project_profiling_and_type_detection"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'} (Type='{profile.project_type}', Entrypoints={profile.entrypoints})", flush=True)

        # [TEST 2] Fast Symbol Extraction (Python AST & JS Regex)
        print("[TEST 2] Verifying AST and Regex Symbol Extraction...", flush=True)
        py_code = (
            "import os\n\n"
            "class UserManager:\n"
            "    def __init__(self):\n"
            "        self.users = []\n\n"
            "    def register_user(self, email):\n"
            "        return True\n\n"
            "@app.get('/api/users')\n"
            "def list_users():\n"
            "    return []\n"
        )
        py_syms = extract_python_symbols(py_code, "auth.py")
        py_sym_names = [s.name for s in py_syms]
        py_sym_kinds = [s.kind for s in py_syms]

        js_code = (
            "export class TaskStore {\n"
            "  constructor() { this.items = []; }\n"
            "}\n\n"
            "export function renderTaskList() {\n"
            "  return null;\n"
            "}\n\n"
            "export const TaskCard = () => {\n"
            "  return null;\n"
            "};\n"
        )
        js_syms = extract_javascript_symbols(js_code, "components.jsx")
        js_sym_names = [s.name for s in js_syms]

        t2_ok = (
            "UserManager" in py_sym_names and "class" in py_sym_kinds and
            "register_user" in py_sym_names and "list_users" in py_sym_names and
            "route" in py_sym_kinds and
            "TaskStore" in js_sym_names and "renderTaskList" in js_sym_names and "TaskCard" in js_sym_names
        )
        test_results["2_symbol_extraction_ast_and_regex"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'} (PySymbols={py_sym_names}, JsSymbols={js_sym_names})", flush=True)

        # [TEST 3] Compact Workspace Summary Generation (Cursor-Style Token Optimization)
        print("[TEST 3] Verifying Compact Workspace Summary (Token Budget Efficiency)...", flush=True)
        summary = cm.get_workspace_summary(max_tokens=600)
        summary_lines = summary.splitlines()

        t3_ok = (
            "Project Architecture:" in summary and
            "Primary Entrypoints: index.html" in summary and
            "Project File Structure:" in summary and
            "Key Project Symbols & Signatures:" in summary and
            len(summary) < 2500  # Token-efficient representation
        )
        test_results["3_compact_workspace_summary"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'} (Length={len(summary)} chars, Lines={len(summary_lines)})", flush=True)

        # [TEST 4] Symbol Search Tool Execution
        print("[TEST 4] Verifying Symbol Search Tool Dispatch & Resolution...", flush=True)
        journal = AgentJournal(temp_dir)
        registry = AgentToolRegistry(temp_dir, journal, context_manager=cm)

        call_sym = AgentToolCall(id="c1", name="search_symbols", args={"query": "TaskStore"})
        ok_sym, out_sym = registry.execute_tool(call_sym)

        t4_ok = (ok_sym and "TaskStore" in out_sym and "app.js" in out_sym)
        test_results["4_symbol_search_dispatch"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'}", flush=True)

        # [TEST 5] Batch 'write_files' Atomic Tool Execution
        print("[TEST 5] Verifying Batch 'write_files' Multi-File Creation...", flush=True)
        multi_files_payload = [
            {
                "path": "frontend/index.html",
                "contents": "<!DOCTYPE html><html><head><title>Task Manager</title></head><body><h1>Tasks</h1></body></html>"
            },
            {
                "path": "frontend/style.css",
                "contents": "body { margin: 0; padding: 20px; background: #0d1117; color: #fff; }"
            },
            {
                "path": "frontend/main.js",
                "contents": "document.addEventListener('DOMContentLoaded', () => { console.log('Tasks ready'); });"
            }
        ]
        call_batch = AgentToolCall(id="c2", name="write_files", args={"files": multi_files_payload})
        ok_batch, out_batch = registry.execute_tool(call_batch)

        # Confirm all 3 files staged in journal as PROPOSED
        proposed_paths = [r.rel_path for r in journal.records if r.status == FileChangeStatus.PROPOSED.value]

        t5_ok = (
            ok_batch and
            "frontend/index.html" in proposed_paths and
            "frontend/style.css" in proposed_paths and
            "frontend/main.js" in proposed_paths and
            len(journal.records) == 3
        )
        test_results["5_batch_write_files_execution"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (StagedCount={len(proposed_paths)})", flush=True)

        # [TEST 6] Batch 'write_files' Stub and Placeholder Rejection
        print("[TEST 6] Verifying Batch 'write_files' Stub Rejection...", flush=True)
        stub_batch = [
            {"path": "good.js", "contents": "function foo() { return 42; }"},
            {"path": "bad.css", "contents": "/* Add responsive UI styles here */"}
        ]
        call_stub_batch = AgentToolCall(id="c3", name="write_files", args={"files": stub_batch})
        ok_stub_batch, out_stub_batch = registry.execute_tool(call_stub_batch)

        t6_ok = (not ok_stub_batch and "Placeholder or stub" in out_stub_batch and "bad.css" in out_stub_batch)
        test_results["6_batch_write_stub_rejection"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'}", flush=True)

        # [TEST 7] Surgical 'edit_file' Search-and-Replace Tool Execution
        print("[TEST 7] Verifying Surgical 'edit_file' Tool Execution...", flush=True)
        # Edit existing app.js
        target_str = "function initApp() { console.log('ready'); }"
        replacement_str = (
            "function initApp() {\n"
            "    console.log('OpenArise Task Manager V1.0 initialized');\n"
            "    loadStoredTasks();\n"
            "}"
        )
        call_edit = AgentToolCall(
            id="c4",
            name="edit_file",
            args={"path": "app.js", "target": target_str, "replacement": replacement_str}
        )
        ok_edit, out_edit = registry.execute_tool(call_edit)

        # Inspect the staged change record in journal
        app_rec = [r for r in journal.records if r.rel_path == "app.js"][-1]
        t7_ok = (
            ok_edit and
            "replaced 1 occurrence" in out_edit and
            replacement_str in app_rec.new_content and
            target_str not in app_rec.new_content and
            "class TaskStore" in app_rec.new_content  # Verifies rest of file preserved untouched!
        )
        test_results["7_surgical_edit_file_execution"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'} (RestOfFilePreserved=True)", flush=True)

        # [TEST 8] Enhanced 'read_file' with Line Range Inspection
        print("[TEST 8] Verifying Enhanced 'read_file' with Line Range...", flush=True)
        call_read_full = AgentToolCall(id="c5", name="read_file", args={"path": "app.js"})
        ok_rf, out_rf = registry.execute_tool(call_read_full)

        call_read_range = AgentToolCall(id="c6", name="read_file", args={"path": "app.js", "start_line": 1, "end_line": 2})
        ok_rr, out_rr = registry.execute_tool(call_read_range)

        t8_ok = (
            ok_rf and "OpenArise Task Manager" in out_rf and
            ok_rr and "1 |" in out_rr and "2 |" in out_rr
        )
        test_results["8_enhanced_read_file_line_ranges"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'}", flush=True)

        # [TEST 9] Autonomous Build, Run & Test Runnable Detection
        print("[TEST 9] Verifying Project Runnable Detection & Launch Guidance...", flush=True)
        worker = AgentWorker(
            client=None,
            model="qwen2.5-coder:7b",
            project_root=temp_dir,
            user_prompt="Build task manager website",
            context_manager=cm,
            parent=None
        )
        runnable_summary = worker._detect_and_verify_runnable()

        t9_ok = (
            "Website Entrypoint: index.html" in runnable_summary and
            "Local Server: Run 'python -m http.server 8000'" in runnable_summary and
            "Direct Browser: file:///" in runnable_summary
        )
        test_results["9_autonomous_runnable_detection"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'}", flush=True)

        # [TEST 10] Autonomous Self-Healing Debugger Recovery
        print("[TEST 10] Verifying Autonomous Self-Healing Debugger...", flush=True)
        # Create a Python file with a simulated error
        py_test_file = temp_dir / "calc.py"
        py_test_file.write_text("def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a /", encoding="utf-8")

        # Mock model response for self-healing repair
        healing_json = {
            "thought": "Fixing incomplete division function syntax.",
            "action": "tool_call",
            "tool": "write_file",
            "args": {
                "path": "calc.py",
                "contents": "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b if b != 0 else None\n"
            }
        }
        with patch.object(worker, "_call_model_with_retries", return_value=healing_json):
            healed = worker._attempt_self_healing("Syntax error in 'calc.py': unexpected EOF", failing_file="calc.py")

        # Verify repaired content on disk and syntax compilable
        repaired_content = py_test_file.read_text(encoding="utf-8")
        is_compilable = False
        try:
            compile(repaired_content, "calc.py", "exec")
            is_compilable = True
        except SyntaxError:
            pass

        t10_ok = (healed and is_compilable and "return a / b" in repaired_content)
        test_results["10_autonomous_self_healing_recovery"] = t10_ok
        print(f"  Result: {'PASS' if t10_ok else 'FAIL'} (Healed={healed}, Compilable={is_compilable})", flush=True)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n=======================================================", flush=True)
    print("FINAL AI AGENT V1.0 TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status_str = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status_str}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    if all_passed and len(test_results) == 10:
        print("OVERALL STATUS: ALL 10 AGENT V1.0 TESTS PASSED", flush=True)
    else:
        print(f"OVERALL STATUS: TESTS FAILED ({sum(1 for v in test_results.values() if v)}/{len(test_results)} passed)", flush=True)
    print("=======================================================\n", flush=True)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())

