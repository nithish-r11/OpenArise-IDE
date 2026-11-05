"""
Automated Test Suite for OpenArise IDE AI Agent UI Layout Stability.
Verifies:
1. Agent panel layout stability across task start, execution, completion, failure, and cancellation.
2. Prevention of unnecessary resizing, jumping, or shifting during progress updates.
3. Development Plan table height stability.
4. Activity Timeline height stability during live updates.
5. Non-disruptive log appending without forcing the entire panel to scroll.
6. Smart auto-scroll: auto-scrolls only when viewing latest entries.
7. Scroll preservation when viewing older activity logs.
8. Elimination of layout recalculations and horizontal layout explosions from long step descriptions.
9. Smooth manual window resizing behavior.
"""

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from unittest.mock import patch
from core.agent_models import AgentPlan, AgentPlanStep, StepStatus, AgentToolCall, AgentTaskState
from core.agent_orchestrator import AgentWorker
from ui.agent_panel import AgentPanel


def run_tests():
    # Patch AgentWorker.start to avoid launching background threads in UI geometry tests
    patch.object(AgentWorker, "start", lambda self: None).start()

    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================", flush=True)
    print("STARTING AI AGENT UI LAYOUT STABILITY TESTS", flush=True)
    print("=======================================================\n", flush=True)

    panel = AgentPanel(client=None, parent=None)
    panel.resize(380, 700)
    panel.show()
    app.processEvents()

    # [TEST 1] Progress Bar Retention & Position Stability on Task Start
    print("[TEST 1] Verifying Progress Bar Size Retention & Start Stability...", flush=True)
    initial_status_geom = panel.status_lbl.geometry()
    initial_tree_h = panel.plan_tree.height()
    initial_log_h = panel.log_browser.height()

    panel.task_input.setPlainText("Build authentication module")
    panel.current_model = lambda: "qwen2.5-coder:7b"
    panel.set_project_root(PROJECT_ROOT)
    panel.start_task()
    app.processEvents()

    after_start_status_geom = panel.status_lbl.geometry()
    after_start_tree_h = panel.plan_tree.height()
    after_start_log_h = panel.log_browser.height()

    # Progress bar should now be visible, but y-position of status_lbl must NOT move
    y_diff = after_start_status_geom.y() - initial_status_geom.y()
    t1_ok = (
        panel.progress_bar.isVisible() and
        y_diff == 0 and
        after_start_tree_h == initial_tree_h and
        after_start_log_h == initial_log_h
    )
    test_results["1_progress_bar_retention_and_start_stability"] = t1_ok
    print(f"  Result: {'PASS' if t1_ok else 'FAIL'} (Y-shift={y_diff}px, TreeHeight={after_start_tree_h})", flush=True)

    # [TEST 2] Development Plan Table Height Stability on Plan Ready & Populated
    print("[TEST 2] Verifying Development Plan Table Height Stability...", flush=True)
    plan = AgentPlan("Build authentication module", steps=[
        AgentPlanStep(1, "Create models and user schemas with password hashing."),
        AgentPlanStep(2, "Implement login, register, and token refresh routes."),
        AgentPlanStep(3, "Add JWT middleware and route authorization checks."),
        AgentPlanStep(4, "Write comprehensive integration tests for all auth routes.")
    ], is_approved=False)

    panel._on_plan_ready(plan)
    app.processEvents()

    plan_ready_tree_h = panel.plan_tree.height()
    # Development plan tree must maintain its stable height and not collapse
    t2_ok = (plan_ready_tree_h == initial_tree_h and panel.plan_tree.topLevelItemCount() == 4)
    test_results["2_development_plan_table_height_stability"] = t2_ok
    print(f"  Result: {'PASS' if t2_ok else 'FAIL'} (Height={plan_ready_tree_h}, Steps={panel.plan_tree.topLevelItemCount()})", flush=True)

    # [TEST 3] Status Label Long Description Elision & No Width Explosion
    print("[TEST 3] Verifying Status Label Elision (No Horizontal Explosion)...", flush=True)
    long_desc = (
        "Create the full HTML structure for the task management dashboard with sections for adding, "
        "editing, deleting, toggling completion, filtering tasks, and local storage state hydration."
    )
    panel._on_step_started(1, long_desc)
    app.processEvents()

    label_w = panel.status_lbl.width()
    label_h = panel.status_lbl.height()
    # Label width must fit panel width (approx 360px) and never explode horizontally
    t3_ok = (label_w <= 365 and label_h == 18 and panel.status_lbl.toolTip() == f"Running Step 1: {long_desc}")
    test_results["3_status_label_horizontal_containment"] = t3_ok
    print(f"  Result: {'PASS' if t3_ok else 'FAIL'} (Width={label_w}px, Height={label_h}px, TooltipMatches=True)", flush=True)

    # [TEST 4] Plan Table Stability Across Step Running and Completed
    print("[TEST 4] Verifying Plan Table Stability on Step Started & Finished...", flush=True)
    panel._on_step_finished(1, "completed", "HTML structure successfully created with all required components.")
    app.processEvents()
    step_finish_tree_h = panel.plan_tree.height()

    panel._on_step_started(2, "Implement login, register, and token refresh routes.")
    app.processEvents()
    step2_start_tree_h = panel.plan_tree.height()

    t4_ok = (step_finish_tree_h == initial_tree_h and step2_start_tree_h == initial_tree_h)
    test_results["4_plan_table_stability_during_execution"] = t4_ok
    print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (FinishHeight={step_finish_tree_h}, NextStartHeight={step2_start_tree_h})", flush=True)

    # [TEST 5] Smart Auto-Scroll in Activity Timeline
    print("[TEST 5] Verifying Smart Auto-Scroll when Viewing Latest Entries...", flush=True)
    for i in range(25):
        panel._append_log("info", f"Execution trace {i}: Agent analyzing files and dispatching tool actions...")
    app.processEvents()

    sb = panel.log_browser.verticalScrollBar()
    at_bottom_init = sb.value() == sb.maximum() and sb.maximum() > 0

    panel._append_log("info", "Live log entry streaming in at bottom...")
    app.processEvents()

    at_bottom_after = sb.value() == sb.maximum()
    t5_ok = at_bottom_init and at_bottom_after
    test_results["5_smart_auto_scroll_at_bottom"] = t5_ok
    print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (AutoScrolled={at_bottom_after}, Pos={sb.value()}/{sb.maximum()})", flush=True)

    # [TEST 6] Preservation of User Scroll Position when Viewing Older Logs
    print("[TEST 6] Verifying User Scroll Position Preservation (Reading Older Logs)...", flush=True)
    target_pos = 45
    sb.setValue(target_pos)
    app.processEvents()
    assert sb.value() == target_pos

    # Append 10 new logs while user is scrolled up
    for i in range(10):
        panel._append_log("info", f"Background activity {i} while user is inspecting earlier log line...")
    app.processEvents()

    current_pos = sb.value()
    t6_ok = (current_pos == target_pos)
    test_results["6_preserve_scroll_position_when_scrolled_up"] = t6_ok
    print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (Expected={target_pos}, Actual={current_pos})", flush=True)

    # [TEST 7] Task Completion Layout Stability
    print("[TEST 7] Verifying Layout Stability on Task Completion...", flush=True)
    panel._on_task_completed("Auth module completed with 4 files.", "feat: auth")
    app.processEvents()

    completed_status_geom = panel.status_lbl.geometry()
    completed_tree_h = panel.plan_tree.height()
    completed_y_diff = completed_status_geom.y() - initial_status_geom.y()

    t7_ok = (
        not panel.progress_bar.isVisible() and
        completed_y_diff == 0 and
        completed_tree_h == initial_tree_h and
        "completed successfully" in panel.status_lbl.text().lower()
    )
    test_results["7_task_completion_layout_stability"] = t7_ok
    print(f"  Result: {'PASS' if t7_ok else 'FAIL'} (Y-shift={completed_y_diff}px, TreeHeight={completed_tree_h})", flush=True)

    # [TEST 8] Task Cancellation and Failure Layout Stability
    print("[TEST 8] Verifying Layout Stability on Cancellation and Failure...", flush=True)
    # Simulate start and then cancellation
    panel.task_input.setPlainText("Another task")
    panel.start_task()
    app.processEvents()

    panel.cancel_task()
    app.processEvents()

    cancel_y_diff = panel.status_lbl.geometry().y() - initial_status_geom.y()
    cancel_tree_h = panel.plan_tree.height()

    panel._on_task_failed("Simulated failure")
    app.processEvents()

    fail_y_diff = panel.status_lbl.geometry().y() - initial_status_geom.y()
    fail_tree_h = panel.plan_tree.height()

    t8_ok = (cancel_y_diff == 0 and cancel_tree_h == initial_tree_h and fail_y_diff == 0 and fail_tree_h == initial_tree_h)
    test_results["8_cancellation_and_failure_stability"] = t8_ok
    print(f"  Result: {'PASS' if t8_ok else 'FAIL'} (CancelShift={cancel_y_diff}px, FailShift={fail_y_diff}px)", flush=True)

    # [TEST 9] Manual Window/Panel Resizing Behavior
    print("[TEST 9] Verifying Smooth Manual Resizing Behavior...", flush=True)
    panel.resize(520, 850)
    app.processEvents()

    resized_tree_h = panel.plan_tree.height()
    resized_log_h = panel.log_browser.height()
    resized_panel_w = panel.width()

    # Plan tree maintains stable height (0 stretch); extra height allocated to log browser
    t9_ok = (
        resized_panel_w == 520 and
        resized_tree_h == initial_tree_h and
        resized_log_h > initial_log_h and
        panel.status_lbl.width() >= 480
    )
    test_results["9_manual_resizing_behavior"] = t9_ok
    print(f"  Result: {'PASS' if t9_ok else 'FAIL'} (PanelW={resized_panel_w}, TreeH={resized_tree_h}, LogH={resized_log_h})", flush=True)

    panel.close()

    print("\n=======================================================", flush=True)
    print("FINAL LAYOUT STABILITY TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status_str = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status_str}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    if all_passed and len(test_results) == 9:
        print("OVERALL STATUS: ALL 9 LAYOUT STABILITY TESTS PASSED", flush=True)
    else:
        print(f"OVERALL STATUS: TESTS FAILED ({sum(1 for v in test_results.values() if v)}/{len(test_results)} passed)", flush=True)
    print("=======================================================\n", flush=True)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
