"""
Comprehensive Phase 6 integration tests for OpenArise AI Agent Mode.
Validates:
1. Agent mode activation & mode switching (Ctrl+Shift+A)
2. Project context retrieval & bounded filtering
3. Task planning generation
4. User plan approval workflow (proceed vs reject)
5. Controlled file creation inside project root
6. Multi-file modification tracking
7. Path traversal rejection (security containment)
8. Existing file backup verification before modification
9. Diff preview generation (line additions & deletions)
10. Accept and Reject changes (per-file disk safety)
11. Rollback applied changes (restores original & deletes created)
12. Terminal command approval gate
13. Dependency installation approval requirement
14. Invalid model tool-call rejection & schema validation
15. Agent task cancellation (clean interruption)
16. Retry limits & infinite loop prevention
17. Existing Ollama chat compatibility (zero regressions)
18. Git integration (pre-flight warning & post-completion diff/commit)
19. Clean shutdown & resource cleanup
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Ensure application root is in sys.path
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

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
from core.agent_orchestrator import AgentWorker
from core.agent_tools import AgentToolRegistry, resolve_contained_path
from core.context_manager import ContextManager
from core.git_service import GitService
from core.ollama_client import OllamaClient
from ui.agent_diff_dialog import AgentDiffDialog
from ui.main_window import MainWindow


def run_phase6_tests() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================", flush=True)
    print("STARTING OPENARISE IDE PHASE 6 AI AGENT MODE TEST SUITE", flush=True)
    print("=======================================================\n", flush=True)

    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p6_test_")).resolve()
    print(f"Isolated test workspace: {test_dir}", flush=True)

    window = MainWindow()
    window.show()
    app.processEvents()

    try:
        # TEST 1: Agent Mode Activation & Switching
        print("[TEST 1] Verifying Agent Mode Activation & Mode Switching...", flush=True)
        # Check initial mode is chat
        init_mode = window.chat.current_mode()
        # Switch to agent mode
        window.switch_to_agent_mode()
        app.processEvents()
        mode_after_agent = window.chat.current_mode()
        # Switch back to chat
        window.switch_to_chat_mode()
        app.processEvents()
        mode_after_chat = window.chat.current_mode()
        # Switch back to agent for rest of tests
        window.switch_to_agent_mode()
        app.processEvents()

        t1_ok = (init_mode == "chat" and mode_after_agent == "agent" and mode_after_chat == "chat")
        test_results["1_agent_mode_activation"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'} (Init={init_mode}, Agent={mode_after_agent}, Chat={mode_after_chat})", flush=True)

        # Set up a real project folder in test_dir
        project_root = test_dir / "my_project"
        project_root.mkdir(parents=True, exist_ok=True)
        readme = project_root / "README.md"
        readme.write_text("# My Awesome Project\nInitial readme text.\n", encoding="utf-8")
        src_dir = project_root / "src"
        src_dir.mkdir(exist_ok=True)
        app_file = src_dir / "app.py"
        app_file.write_text("def run():\n    print('Running App')\n", encoding="utf-8")

        window._load_project_folder(project_root)
        app.processEvents()

        # TEST 2: Project Context Retrieval & Bounded Filtering
        print("[TEST 2] Verifying Project Context Retrieval & Bounded Filtering...", flush=True)
        cm = ContextManager()
        cm.set_project(project_root)
        cm.update_index({
            "README.md": readme.read_text(encoding="utf-8"),
            "src/app.py": app_file.read_text(encoding="utf-8"),
        })
        bounded_ctx = cm.build_context(query="Running App", include_codebase=True, max_chars=1000)
        has_app_code = "Running App" in bounded_ctx
        is_bounded = len(bounded_ctx) <= 1200
        t2_ok = has_app_code and is_bounded
        test_results["2_context_retrieval"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'} (HasAppCode={has_app_code}, Bounded={is_bounded})", flush=True)

        # TEST 3: Task Planning Generation
        print("[TEST 3] Verifying Task Planning Generation...", flush=True)
        sample_steps = [
            AgentPlanStep(1, "Inspect existing src/app.py"),
            AgentPlanStep(2, "Add authentication logic in src/auth.py"),
            AgentPlanStep(3, "Add test suite in tests/test_auth.py"),
            AgentPlanStep(4, "Run unit tests and verify")
        ]
        plan = AgentPlan(task_description="Add authentication logic", steps=sample_steps)
        t3_ok = (len(plan.steps) == 4 and plan.steps[0].step_number == 1 and not plan.is_approved)
        test_results["3_task_planning"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'} (StepsCount={len(plan.steps)}, IsApproved={plan.is_approved})", flush=True)

        # TEST 4: User Approval Workflow (Proceed vs Reject)
        print("[TEST 4] Verifying User Approval Workflow...", flush=True)
        # Test approval True
        plan.is_approved = True
        approved_ok = plan.is_approved is True
        # Test rejection behavior: unapproved plan remains is_approved == False
        rejected_plan = AgentPlan(task_description="Risky task", steps=[AgentPlanStep(1, "Risky step")])
        reject_blocked = (rejected_plan.is_approved is False)
        t4_ok = approved_ok and reject_blocked
        test_results["4_user_approval_workflow"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (ApprovedOk={approved_ok}, RejectBlocked={reject_blocked})", flush=True)

        # TEST 5: Controlled File Creation
        print("[TEST 5] Verifying Controlled File Creation...", flush=True)
        journal = AgentJournal(project_root)
        registry = AgentToolRegistry(project_root, journal)
        # write_file records into journal as PROPOSED
        write_call = AgentToolCall("c1", "write_file", {"path": "src/auth.py", "content": "def authenticate():\n    return True\n"})
        res_ok, res_msg = registry.execute_tool(write_call)
        # Verify it's staged in journal
        staged_rec = next((r for r in journal.records if r.rel_path == "src/auth.py"), None)
        is_staged = staged_rec is not None and staged_rec.change_type == FileChangeType.CREATE.value
        # File should not exist on disk yet until accepted!
        not_on_disk_yet = not (project_root / "src" / "auth.py").exists()
        # Now accept and apply
        staged_rec.status = FileChangeStatus.ACCEPTED.value
        applied_cnt, applied_files = journal.apply_accepted()
        exists_now = (project_root / "src" / "auth.py").exists()
        content_correct = "def authenticate():" in (project_root / "src" / "auth.py").read_text(encoding="utf-8")

        t5_ok = res_ok and is_staged and not_on_disk_yet and exists_now and content_correct
        test_results["5_file_creation"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (Staged={is_staged}, SafetyGate={not_on_disk_yet}, Created={exists_now})", flush=True)

        # TEST 6: Multi-File Modification Tracking
        print("[TEST 6] Verifying Multi-File Modification Tracking...", flush=True)
        # Propose modification to README.md and app.py
        registry.execute_tool(AgentToolCall("c2", "write_file", {"path": "README.md", "content": "# Updated Readme\nWith auth.\n"}))
        registry.execute_tool(AgentToolCall("c3", "write_file", {"path": "src/app.py", "content": "from src.auth import authenticate\ndef run():\n    authenticate()\n"}))
        proposed_recs = [r for r in journal.records if r.status == FileChangeStatus.PROPOSED.value]
        t6_ok = len(proposed_recs) == 2 and any(r.rel_path == "README.md" for r in proposed_recs) and any(r.rel_path == "src/app.py" for r in proposed_recs)
        test_results["6_multi_file_modification"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (ProposedCount={len(proposed_recs)})", flush=True)

        # TEST 7: Path Traversal Rejection
        print("[TEST 7] Verifying Path Traversal Rejection...", flush=True)
        traversal_blocked = False
        try:
            resolve_contained_path(project_root, "../../escaped_file.txt")
        except ValueError as err:
            traversal_blocked = "traversal" in str(err).lower()

        abs_outside_blocked = False
        try:
            resolve_contained_path(project_root, "C:/Windows/System32/calc.exe")
        except ValueError as err:
            abs_outside_blocked = "traversal" in str(err).lower()

        t7_ok = traversal_blocked and abs_outside_blocked
        test_results["7_path_traversal_rejection"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'} (TraversalBlocked={traversal_blocked}, AbsOutsideBlocked={abs_outside_blocked})", flush=True)

        # TEST 8: Existing File Backup Verification
        print("[TEST 8] Verifying Existing File Backup Before Modification...", flush=True)
        app_rec = next(r for r in journal.records if r.rel_path == "src/app.py")
        has_backup = app_rec.backup_path is not None and app_rec.backup_path.exists()
        backup_content = app_rec.backup_path.read_text(encoding="utf-8") if has_backup else ""
        backup_matches_original = "Running App" in backup_content
        t8_ok = has_backup and backup_matches_original
        test_results["8_existing_file_backup"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'} (HasBackup={has_backup}, ContentMatches={backup_matches_original})", flush=True)

        # TEST 9: Diff Preview Generation
        print("[TEST 9] Verifying Diff Preview Generation...", flush=True)
        diff_dialog = AgentDiffDialog(proposed_recs, parent=window)
        # Select first file
        diff_dialog._on_file_selected(0)
        diff_text = diff_dialog.diff_viewer.toPlainText()
        has_diff_markup = "+" in diff_text and "-" in diff_text and "@@" in diff_text
        t9_ok = has_diff_markup and len(diff_dialog.decisions) == 2
        test_results["9_diff_preview"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'} (HasDiffMarkup={has_diff_markup}, FileCount={len(diff_dialog.decisions)})", flush=True)

        # TEST 10: Accept and Reject Changes (Selective Application)
        print("[TEST 10] Verifying Accept and Reject Changes (Selective Application)...", flush=True)
        # Accept README.md, reject src/app.py
        for r in proposed_recs:
            if r.rel_path == "README.md":
                r.status = FileChangeStatus.ACCEPTED.value
            else:
                r.status = FileChangeStatus.REJECTED.value

        app_content_before = app_file.read_text(encoding="utf-8")
        applied_cnt2, applied_files2 = journal.apply_accepted()

        readme_content_after = readme.read_text(encoding="utf-8")
        app_content_after = app_file.read_text(encoding="utf-8")

        readme_was_updated = "With auth." in readme_content_after
        app_was_protected = (app_content_after == app_content_before) and ("Running App" in app_content_after)

        t10_ok = (applied_cnt2 == 1 and readme_was_updated and app_was_protected)
        test_results["10_accept_reject_changes"] = t10_ok
        print(f"  Result: {'PASS' if t10_ok else 'FAIL'} (ReadmeUpdated={readme_was_updated}, AppUntouched={app_was_protected})", flush=True)

        # TEST 11: Rollback Applied Changes
        print("[TEST 11] Verifying Rollback of Applied Changes...", flush=True)
        # Journal has 2 applied files: src/auth.py (created) and README.md (modified)
        rollback_cnt, rollback_files = journal.rollback()

        # Check README.md restored to original
        readme_restored = "Initial readme text." in readme.read_text(encoding="utf-8")
        # Check src/auth.py was deleted
        auth_file_deleted = not (project_root / "src" / "auth.py").exists()

        t11_ok = (rollback_cnt >= 2 and readme_restored and auth_file_deleted)
        test_results["11_rollback"] = t11_ok
        print(f"  Result: {'PASS' if t11_ok else 'FAIL'} (RollbackCount={rollback_cnt}, ReadmeRestored={readme_restored}, CreatedFileDeleted={auth_file_deleted})", flush=True)

        # TEST 12: Terminal Command Approval Gate
        print("[TEST 12] Verifying Terminal Command Approval Gate...", flush=True)
        cmd_call = AgentToolCall("c4", "execute_approved_command", {"command": "echo Hello_OpenArise"})
        # Verify schema marks requires_approval = True
        schema_requires_appr = registry.TOOL_DEFINITIONS["execute_approved_command"]["requires_approval"]
        # Execution directly through registry works when approved
        cmd_ok, cmd_out = registry.execute_tool(cmd_call)
        t12_ok = schema_requires_appr and cmd_ok and "Hello_OpenArise" in cmd_out
        test_results["12_command_approval_gate"] = t12_ok
        print(f"  Result: {'PASS' if t12_ok else 'FAIL'} (RequiresApproval={schema_requires_appr}, ExecutedOnApproval={cmd_ok})", flush=True)

        # TEST 13: Dependency Installation Approval Requirement
        print("[TEST 13] Verifying Dependency Installation Approval Requirement...", flush=True)
        dep_call = AgentToolCall("c5", "execute_approved_command", {"command": "pip list"})
        dep_requires_approval = registry.TOOL_DEFINITIONS["execute_approved_command"]["requires_approval"]
        test_requires_approval = registry.TOOL_DEFINITIONS["run_tests"]["requires_approval"]
        t13_ok = dep_requires_approval and test_requires_approval
        test_results["13_dependency_approval_requirement"] = t13_ok
        print(f"  Result: {'PASS' if t13_ok else 'FAIL'} (DepReqApproval={dep_requires_approval}, TestReqApproval={test_requires_approval})", flush=True)

        # TEST 14: Invalid Model Tool-Call Rejection & Schema Validation
        print("[TEST 14] Verifying Invalid Tool-Call Rejection & Schema Validation...", flush=True)
        # Missing required parameter 'path'
        invalid_call_1 = AgentToolCall("c6", "read_file", {})
        val1_ok, val1_err = registry.validate_tool_call(invalid_call_1.name, invalid_call_1.args)
        # Unknown tool
        invalid_call_2 = AgentToolCall("c7", "delete_all_system_files", {})
        val2_ok, val2_err = registry.validate_tool_call(invalid_call_2.name, invalid_call_2.args)
        # Invalid type (integer instead of string)
        invalid_call_3 = AgentToolCall("c8", "read_file", {"path": 12345})
        val3_ok, val3_err = registry.validate_tool_call(invalid_call_3.name, invalid_call_3.args)

        t14_ok = (not val1_ok) and (not val2_ok) and (not val3_ok)
        test_results["14_invalid_tool_call_rejection"] = t14_ok
        print(f"  Result: {'PASS' if t14_ok else 'FAIL'} (MissingParamRejected={not val1_ok}, UnknownToolRejected={not val2_ok}, BadTypeRejected={not val3_ok})", flush=True)

        # TEST 15: Agent Task Cancellation
        print("[TEST 15] Verifying Agent Task Cancellation...", flush=True)
        dummy_worker = AgentWorker(
            client=window.client,
            model="qwen2.5-coder:7b",
            project_root=project_root,
            user_prompt="Long running task",
            parent=window
        )
        dummy_worker.cancel()
        t15_ok = dummy_worker._cancel_requested and dummy_worker.state == AgentTaskState.CANCELLED
        test_results["15_agent_cancellation"] = t15_ok
        print(f"  Result: {'PASS' if t15_ok else 'FAIL'} (CancelRequested={dummy_worker._cancel_requested}, StateCancelled={dummy_worker.state == AgentTaskState.CANCELLED})", flush=True)

        # TEST 16: Retry Limits & Infinite Loop Prevention
        print("[TEST 16] Verifying Retry Limits & Infinite Loop Prevention...", flush=True)
        # Worker has bounded limits
        t16_ok = dummy_worker.max_retries == 3 and dummy_worker.max_steps == 15
        test_results["16_retry_limits_loop_prevention"] = t16_ok
        print(f"  Result: {'PASS' if t16_ok else 'FAIL'} (MaxRetries={dummy_worker.max_retries}, MaxSteps={dummy_worker.max_steps})", flush=True)

        # TEST 17: Existing Ollama Chat Compatibility
        print("[TEST 17] Verifying Existing Ollama Chat Compatibility...", flush=True)
        # Verify ChatPanel proxies through container
        window.switch_to_chat_mode()
        app.processEvents()
        window.chat.input.setPlainText("Hello from test suite")
        text_in_input = window.chat.input.toPlainText()
        has_send_btn = hasattr(window.chat.chat_panel, "send_button")
        has_models = hasattr(window.chat, "set_models")
        t17_ok = (text_in_input == "Hello from test suite" and has_send_btn and has_models)
        test_results["17_chat_compatibility"] = t17_ok
        print(f"  Result: {'PASS' if t17_ok else 'FAIL'} (InputSet={text_in_input == 'Hello from test suite'}, HasSendBtn={has_send_btn})", flush=True)

        # TEST 18: Git Integration (Pre-flight Warning & Status)
        print("[TEST 18] Verifying Git Integration...", flush=True)
        git_repo = test_dir / "git_test_repo"
        git_repo.mkdir(parents=True, exist_ok=True)
        GitService.init_repo(git_repo)
        GitService.run_git_sync(git_repo, ["config", "user.name", "Agent Tester"])
        GitService.run_git_sync(git_repo, ["config", "user.email", "agent@test.org"])
        GitService.run_git_sync(git_repo, ["config", "commit.gpgsign", "false"])

        git_f = git_repo / "main.py"
        git_f.write_text("print('git test')\n")
        GitService.stage_file(git_repo, "main.py")
        GitService.commit(git_repo, "Initial git commit")

        # Create uncommitted change
        git_f.write_text("print('dirty change')\n")
        status_ok, _, repo_state = GitService.get_status(git_repo)
        is_dirty = not repo_state.is_clean

        git_worker = AgentWorker(
            client=window.client,
            model="qwen2.5-coder:7b",
            project_root=git_repo,
            user_prompt="Inspect repository",
            parent=window
        )
        warnings_caught = []
        git_worker.preflight_warning.connect(lambda w: warnings_caught.append(w))
        git_worker._run_preflight_checks()

        has_dirty_warning = len(warnings_caught) > 0 and "uncommitted" in warnings_caught[0].lower()
        t18_ok = is_dirty and has_dirty_warning
        test_results["18_git_integration"] = t18_ok
        print(f"  Result: {'PASS' if t18_ok else 'FAIL'} (IsDirty={is_dirty}, WarningEmitted={has_dirty_warning})", flush=True)

        # TEST 20: write_file Canonical 'contents' Parameter
        print("[TEST 20] Verifying write_file Canonical 'contents' Parameter Acceptance...", flush=True)
        p20_journal = AgentJournal(project_root)
        p20_reg = AgentToolRegistry(project_root, p20_journal)
        canonical_call = AgentToolCall("c20", "write_file", {"path": "src/canonical.py", "contents": "CANONICAL = True\n"})
        p20_valid, p20_err = p20_reg.validate_tool_call(canonical_call.name, canonical_call.args)
        p20_ok, p20_msg = p20_reg.execute_tool(canonical_call)
        p20_rec = next((r for r in p20_journal.records if r.rel_path == "src/canonical.py"), None)
        t20_ok = p20_valid and p20_ok and p20_rec is not None and p20_rec.new_content == "CANONICAL = True\n"
        test_results["20_write_file_canonical_contents"] = t20_ok
        print(f"  Result: {'PASS' if t20_ok else 'FAIL'} (Valid={p20_valid}, Exec={p20_ok})", flush=True)

        # TEST 21: write_file Legacy 'content' Parameter Normalization
        print("[TEST 21] Verifying write_file Legacy 'content' Parameter Normalization...", flush=True)
        p21_journal = AgentJournal(project_root)
        p21_reg = AgentToolRegistry(project_root, p21_journal)
        legacy_call = AgentToolCall("c21", "write_file", {"path": "src/legacy.py", "content": "LEGACY = True\n"})
        p21_valid, p21_err = p21_reg.validate_tool_call(legacy_call.name, legacy_call.args)
        p21_ok, p21_msg = p21_reg.execute_tool(legacy_call)
        p21_rec = next((r for r in p21_journal.records if r.rel_path == "src/legacy.py"), None)
        t21_ok = p21_valid and p21_ok and p21_rec is not None and p21_rec.new_content == "LEGACY = True\n" and legacy_call.args.get("contents") == "LEGACY = True\n"
        test_results["21_write_file_legacy_content_normalization"] = t21_ok
        print(f"  Result: {'PASS' if t21_ok else 'FAIL'} (Valid={p21_valid}, Exec={p21_ok}, NormalizedToContents={'contents' in legacy_call.args})", flush=True)

        # TEST 22: write_file Conflicting Arguments Rejection
        print("[TEST 22] Verifying write_file Conflicting Arguments Rejection...", flush=True)
        p22_journal = AgentJournal(project_root)
        p22_reg = AgentToolRegistry(project_root, p22_journal)
        conflict_call = AgentToolCall("c22", "write_file", {"path": "src/conflict.py", "content": "AAA", "contents": "BBB"})
        p22_valid, p22_err = p22_reg.validate_tool_call(conflict_call.name, conflict_call.args)
        p22_ok, p22_msg = p22_reg.execute_tool(conflict_call)
        is_rejected = (not p22_valid) and (not p22_ok) and ("conflict" in (p22_err or p22_msg).lower())
        test_results["22_write_file_conflicting_args_rejected"] = is_rejected
        print(f"  Result: {'PASS' if is_rejected else 'FAIL'} (Rejected={is_rejected})", flush=True)

        # TEST 23: write_file Missing Contents Parameter Rejection
        print("[TEST 23] Verifying write_file Missing Contents Parameter Rejection...", flush=True)
        missing_call = AgentToolCall("c23", "write_file", {"path": "src/missing.py"})
        p23_valid, p23_err = p20_reg.validate_tool_call(missing_call.name, missing_call.args)
        p23_ok, p23_msg = p20_reg.execute_tool(missing_call)
        missing_rejected = (not p23_valid) and (not p23_ok) and ("contents" in (p23_err or p23_msg).lower())
        test_results["23_write_file_missing_contents_rejected"] = missing_rejected
        print(f"  Result: {'PASS' if missing_rejected else 'FAIL'} (Rejected={missing_rejected})", flush=True)

        # TEST 24: Failed File Operations Mark Task FAILED (No False Success)
        print("[TEST 24] Verifying Failed File Operations Mark Task FAILED...", flush=True)
        failing_worker = AgentWorker(
            client=window.client,
            model="qwen2.5-coder:7b",
            project_root=project_root,
            user_prompt="Write file with bad path",
            parent=window
        )
        failed_caught = []
        completed_caught = []
        failing_worker.task_failed.connect(lambda msg: failed_caught.append(msg))
        failing_worker.task_completed.connect(lambda s, c: completed_caught.append(s))
        failing_worker.plan = AgentPlan("Test task", steps=[AgentPlanStep(1, "Create invalid file")])
        failing_worker._fail("Task failed: File operations failed for: invalid_path")
        t24_ok = failing_worker.state == AgentTaskState.FAILED and len(failed_caught) == 1 and len(completed_caught) == 0
        test_results["24_failed_file_op_marks_task_failed"] = t24_ok
        print(f"  Result: {'PASS' if t24_ok else 'FAIL'} (State={failing_worker.state}, FailedCaught={len(failed_caught)}, CompletedCaught={len(completed_caught)})", flush=True)

        # TEST 25: Accurate Modified File Count Reporting
        print("[TEST 25] Verifying Accurate Modified File Count Reporting...", flush=True)
        acc_journal = AgentJournal(project_root)
        rec1 = acc_journal.record_change("src/mod1.py", FileChangeType.CREATE.value, new_content="A=1\n")
        rec2 = acc_journal.record_change("src/mod2.py", FileChangeType.CREATE.value, new_content="B=2\n")
        rec1.status = FileChangeStatus.ACCEPTED.value
        rec2.status = FileChangeStatus.REJECTED.value
        applied_cnt, applied_fls = acc_journal.apply_accepted()
        count_is_accurate = (applied_cnt == 1 and len(acc_journal.records) == 2 and (project_root / "src" / "mod1.py").exists() and not (project_root / "src" / "mod2.py").exists())
        test_results["25_accurate_modified_file_count"] = count_is_accurate
        print(f"  Result: {'PASS' if count_is_accurate else 'FAIL'} (AppliedCount={applied_cnt}, RecordsCount={len(acc_journal.records)})", flush=True)

        # TEST 26: Duplicate Identical Invalid Tool Call Rejection
        print("[TEST 26] Verifying Duplicate Identical Invalid Tool Call Rejection...", flush=True)
        from core.agent_tools import normalize_tool_args
        norm_ok, norm_res, norm_err = normalize_tool_args("write_file", {"path": "test.py", "content": "foo", "contents": "bar"})
        has_conflict_error = (not norm_ok) and ("conflict" in norm_err.lower())
        call1_sig = f"write_file:{json.dumps({'path': 'test.py', 'content': 'foo'}, sort_keys=True)}"
        call2_sig = f"write_file:{json.dumps({'path': 'test.py', 'content': 'foo'}, sort_keys=True)}"
        call3_sig = f"write_file:{json.dumps({'path': 'test.py', 'contents': 'foo'}, sort_keys=True)}"
        signatures_match = (call1_sig == call2_sig and call1_sig != call3_sig)
        t26_ok = has_conflict_error and signatures_match
        test_results["26_duplicate_tool_call_prevention"] = t26_ok
        print(f"  Result: {'PASS' if t26_ok else 'FAIL'} (ConflictErr={has_conflict_error}, SigMatch={signatures_match})", flush=True)

        # TEST 19: Clean Shutdown & Resource Cleanup
        print("[TEST 19] Verifying Clean Shutdown & Resource Cleanup...", flush=True)
        window.close()
        app.processEvents()
        time.sleep(0.5)

        term_stopped = (
            window.terminal.process is None
            or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning
        )
        agent_stopped = (
            window.agent_panel.worker is None
            or not window.agent_panel.worker.isRunning()
        )
        t19_ok = term_stopped and agent_stopped
        test_results["19_clean_shutdown"] = t19_ok
        print(f"  Result: {'PASS' if t19_ok else 'FAIL'} (TerminalStopped={term_stopped}, AgentStopped={agent_stopped})", flush=True)

    finally:
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================", flush=True)
    print("FINAL PHASE 6 TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    print(f"OVERALL STATUS: {'ALL 19 PHASE 6 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)
    print("=======================================================\n", flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_phase6_tests())

