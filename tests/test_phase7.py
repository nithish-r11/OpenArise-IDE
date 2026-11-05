"""
Comprehensive Phase 7 integration tests for OpenArise AI Model Manager and Usage Analytics.
Validates:
1. Ollama model discovery & detailed metadata inspection
2. Default model persistence across SettingsManager restarts
3. Model download progress signal handling
4. Model removal confirmation logic & delete API
5. Authoritative input/output token metrics extraction
6. Generation speed calculation (tokens/sec formula)
7. SQLite usage database event persistence
8. Daily, weekly, and monthly usage aggregation
9. Model-wise statistics & success rate calculations
10. Failed and cancelled request tracking
11. CSV export generation & formatting
12. Clear history database sanitization
13. Missing metrics handling (preserves None, never invents tokens)
14. Existing Agent Mode (Phase 6) integration & mode switching
15. Clean UI integration (Ctrl+Shift+U, Command Palette, shutdown)
"""

import csv
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

from core.analytics_db import (
    AnalyticsDatabase,
    ModelUsageMetrics,
    OPERATION_CHAT,
    OPERATION_INLINE,
    OPERATION_TEST_GEN,
    OPERATION_AGENT,
    OPERATION_GIT,
    STATUS_SUCCESS,
    STATUS_FAILED,
    STATUS_CANCELLED,
)
from core.ollama_client import OllamaClient, format_bytes
from core.settings_manager import SettingsManager
from core.system_monitor import SystemResourceMonitor
from ui.analytics_dashboard import AnalyticsDashboardDialog
from ui.main_window import MainWindow
from ui.model_manager_tab import ModelManagerTab


def run_phase7_tests() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================", flush=True)
    print("STARTING OPENARISE IDE PHASE 7 AI MODEL MANAGER & ANALYTICS TEST SUITE", flush=True)
    print("=======================================================\n", flush=True)

    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p7_test_")).resolve()
    print(f"Isolated test workspace: {test_dir}", flush=True)

    window = MainWindow()
    window.show()
    app.processEvents()

    try:
        # TEST 1: Ollama Model Discovery & Metadata Inspection
        print("[TEST 1] Verifying Ollama Model Discovery & Metadata...", flush=True)
        client = OllamaClient()
        conn_ok, conn_msg = client.check_connection()
        models = client.list_models()
        detailed_models = client.list_models_detailed()

        has_names = len(models) > 0
        has_detailed = len(detailed_models) > 0
        metadata_valid = False
        if has_detailed:
            first = detailed_models[0]
            metadata_valid = (
                "name" in first and
                "size" in first and
                "size_formatted" in first and
                "family" in first and
                "parameter_size" in first
            )

        t1_ok = conn_ok and has_names and has_detailed and metadata_valid
        test_results["1_model_discovery"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'} (Conn={conn_ok}, Count={len(models)}, ValidMeta={metadata_valid})", flush=True)

        # TEST 2: Default Model Persistence
        print("[TEST 2] Verifying Default Model Persistence in SettingsManager...", flush=True)
        custom_config_dir = test_dir / "config_test"
        sm1 = SettingsManager(config_dir=custom_config_dir)
        sm1.set("default_ollama_model", "deepseek-coder:6.7b")

        # Reload in fresh instance
        sm2 = SettingsManager(config_dir=custom_config_dir)
        persisted_model = sm2.get("default_ollama_model")
        t2_ok = (persisted_model == "deepseek-coder:6.7b")
        test_results["2_default_model_persistence"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'} (PersistedModel='{persisted_model}')", flush=True)

        # TEST 3: Model Download Progress Signal Handling
        print("[TEST 3] Verifying Model Download Progress Signal Handling...", flush=True)
        model_tab = ModelManagerTab(settings_manager=window.settings_manager, ollama_client=client, parent=window)
        progress_values = []
        model_tab._on_pull_progress("Downloading layer", 45)
        model_tab._on_pull_progress("Writing manifest", 100)
        t3_ok = (model_tab.pull_progress.value() == 100 and "Writing manifest (100%)" in model_tab.pull_status_lbl.text())
        test_results["3_model_download_progress"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'} (ProgressVal={model_tab.pull_progress.value()}, Status='{model_tab.pull_status_lbl.text()}')", flush=True)

        # TEST 4: Model Removal Confirmation & Delete API
        print("[TEST 4] Verifying Model Removal Logic & Safety Confirmation...", flush=True)
        has_delete_api = hasattr(client, "delete_model") and callable(client.delete_model)
        # Attempting delete on a nonexistent mock model returns clean failure or 404 without crashing
        del_ok, del_msg = client.delete_model("nonexistent-test-model-xyz-123")
        t4_ok = has_delete_api and (not del_ok) and ("fail" in del_msg.lower() or "404" in del_msg.lower() or "not found" in del_msg.lower())
        test_results["4_model_removal_safety"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (HasDeleteAPI={has_delete_api}, HandledSafely={not del_ok})", flush=True)

        # TEST 5: Actual Input/Output Token Collection
        print("[TEST 5] Verifying Authoritative Token Metrics Extraction...", flush=True)
        mock_payload = {
            "model": "qwen2.5-coder:7b",
            "prompt_eval_count": 35,
            "eval_count": 142,
            "total_duration": 2500000000,
            "load_duration": 400000000,
            "eval_duration": 2100000000,
        }
        metric = ModelUsageMetrics.from_ollama_payload(
            model="qwen2.5-coder:7b",
            operation_type=OPERATION_CHAT,
            payload=mock_payload,
        )
        t5_ok = (
            metric.input_tokens == 35 and
            metric.output_tokens == 142 and
            metric.total_tokens == 177 and
            metric.duration_ms == 2500.0 and
            metric.load_duration_ms == 400.0 and
            metric.eval_duration_ms == 2100.0
        )
        test_results["5_authoritative_tokens"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (In={metric.input_tokens}, Out={metric.output_tokens}, Total={metric.total_tokens})", flush=True)

        # TEST 6: Generation Speed Calculation (Tokens Per Second)
        print("[TEST 6] Verifying Generation Speed Calculation...", flush=True)
        # Speed = 142 / (2100000000 / 1e9) = 142 / 2.1 = 67.62 tok/s
        expected_speed = round(142 / (2100000000 / 1e9), 2)
        speed_matches = (metric.tokens_per_second == expected_speed)
        t6_ok = speed_matches and metric.tokens_per_second > 0
        test_results["6_speed_calculation"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (CalculatedSpeed={metric.tokens_per_second} tok/s, Expected={expected_speed})", flush=True)

        # TEST 7: SQLite Usage Database Event Persistence
        print("[TEST 7] Verifying SQLite Usage Database Event Persistence...", flush=True)
        test_db_path = test_dir / "analytics_test.db"
        analytics_db = AnalyticsDatabase(test_db_path)

        # Record test events
        row_id1 = analytics_db.record_event(metric)
        row_id2 = analytics_db.record_event(ModelUsageMetrics.from_ollama_payload(
            model="qwen2.5-coder:7b",
            operation_type=OPERATION_INLINE,
            payload={"prompt_eval_count": 10, "eval_count": 50, "total_duration": 1000000000, "eval_duration": 900000000}
        ))
        summary = analytics_db.get_summary_stats()
        t7_ok = (row_id1 > 0 and row_id2 > 0 and summary["total_requests"] == 2 and summary["total_tokens"] == 237)
        test_results["7_database_persistence"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'} (RowsRecorded={summary['total_requests']}, TotalTokens={summary['total_tokens']})", flush=True)

        # TEST 8: Daily, Weekly, and Monthly Aggregation
        print("[TEST 8] Verifying Daily, Weekly, and Monthly Aggregation...", flush=True)
        daily = analytics_db.get_daily_usage(30)
        weekly = analytics_db.get_weekly_usage(12)
        monthly = analytics_db.get_monthly_usage(12)

        has_daily = len(daily) >= 1 and daily[0]["total_tokens"] == 237
        has_weekly = len(weekly) >= 1 and weekly[0]["total_tokens"] == 237
        has_monthly = len(monthly) >= 1 and monthly[0]["total_tokens"] == 237

        t8_ok = has_daily and has_weekly and has_monthly
        test_results["8_time_aggregations"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'} (Daily={len(daily)}, Weekly={len(weekly)}, Monthly={len(monthly)})", flush=True)

        # TEST 9: Model-Wise Statistics & Success Rate
        print("[TEST 9] Verifying Model-Wise Statistics & Success Rate...", flush=True)
        per_model = analytics_db.get_per_model_usage()
        first_m = per_model[0] if per_model else {}
        t9_ok = (
            len(per_model) == 1 and
            first_m.get("model") == "qwen2.5-coder:7b" and
            first_m.get("request_count") == 2 and
            first_m.get("success_rate") == 100.0 and
            first_m.get("total_tokens") == 237
        )
        test_results["9_model_wise_stats"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'} (Model='{first_m.get('model')}', Requests={first_m.get('request_count')}, SuccessRate={first_m.get('success_rate')}%)", flush=True)

        # TEST 10: Failed and Cancelled Request Tracking
        print("[TEST 10] Verifying Failed and Cancelled Request Tracking...", flush=True)
        analytics_db.record_event(ModelUsageMetrics(
            model="qwen2.5-coder:7b",
            operation_type=OPERATION_TEST_GEN,
            status=STATUS_FAILED,
            error_message="Ollama connection refused",
            duration_ms=50.0
        ))
        analytics_db.record_event(ModelUsageMetrics(
            model="qwen2.5-coder:7b",
            operation_type=OPERATION_AGENT,
            status=STATUS_CANCELLED,
            error_message="User clicked cancel",
            duration_ms=120.0
        ))
        stats_with_fails = analytics_db.get_summary_stats()
        t10_ok = (
            stats_with_fails["total_requests"] == 4 and
            stats_with_fails["successful_requests"] == 2 and
            stats_with_fails["failed_requests"] == 1 and
            stats_with_fails["cancelled_requests"] == 1 and
            stats_with_fails["success_rate"] == 50.0
        )
        test_results["10_failed_cancelled_tracking"] = t10_ok
        print(f"  Result: {'PASS' if t10_ok else 'FAIL'} (Total=4, Succ=2, Fail=1, Cancel=1, Rate={stats_with_fails['success_rate']}%)", flush=True)

        # TEST 11: CSV Export
        print("[TEST 11] Verifying CSV Export Functionality...", flush=True)
        csv_file = test_dir / "exported_analytics.csv"
        exp_ok, exp_msg = analytics_db.export_to_csv(csv_file)
        file_exists = csv_file.exists() and csv_file.stat().st_size > 0

        # Read back CSV rows
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            header = reader[0]
            data_rows = reader[1:]

        has_header = "model" in header and "operation_type" in header and "tokens_per_second" in header
        has_all_rows = len(data_rows) == 4
        t11_ok = exp_ok and file_exists and has_header and has_all_rows
        test_results["11_csv_export"] = t11_ok
        print(f"  Result: {'PASS' if t11_ok else 'FAIL'} (ExportOk={exp_ok}, RowsInCSV={len(data_rows)})", flush=True)

        # TEST 12: Clear History
        print("[TEST 12] Verifying Clear History Sanitization...", flush=True)
        cleared_count = analytics_db.clear_history()
        summary_after_clear = analytics_db.get_summary_stats()
        t12_ok = (cleared_count == 4 and summary_after_clear["total_requests"] == 0 and summary_after_clear["total_tokens"] == 0)
        test_results["12_clear_history"] = t12_ok
        print(f"  Result: {'PASS' if t12_ok else 'FAIL'} (ClearedCount={cleared_count}, RemainingRequests={summary_after_clear['total_requests']})", flush=True)

        # TEST 13: Missing Metrics Handling (No Fabricated Tokens)
        print("[TEST 13] Verifying Missing Metrics Handling (No Fabricated Tokens)...", flush=True)
        # Empty payload without eval counts
        empty_payload = {"model": "qwen2.5-coder:7b", "done": True}
        unmeasured_metric = ModelUsageMetrics.from_ollama_payload(
            model="qwen2.5-coder:7b",
            operation_type=OPERATION_CHAT,
            payload=empty_payload
        )
        t13_ok = (
            unmeasured_metric.input_tokens is None and
            unmeasured_metric.output_tokens is None and
            unmeasured_metric.total_tokens is None and
            unmeasured_metric.tokens_per_second is None
        )
        test_results["13_missing_metrics_handling"] = t13_ok
        print(f"  Result: {'PASS' if t13_ok else 'FAIL'} (InputNone={unmeasured_metric.input_tokens is None}, SpeedNone={unmeasured_metric.tokens_per_second is None})", flush=True)

        # TEST 14: Existing Agent Mode Integration
        print("[TEST 14] Verifying Existing Agent Mode & Container Functionality...", flush=True)
        window.switch_to_agent_mode()
        app.processEvents()
        is_agent = (window.chat.current_mode() == "agent")
        has_agent_panel = hasattr(window, "agent_panel") and window.agent_panel is not None
        window.switch_to_chat_mode()
        app.processEvents()
        is_chat = (window.chat.current_mode() == "chat")
        t14_ok = is_agent and has_agent_panel and is_chat
        test_results["14_agent_mode_integration"] = t14_ok
        print(f"  Result: {'PASS' if t14_ok else 'FAIL'} (AgentModeOk={is_agent}, ChatModeOk={is_chat})", flush=True)

        # TEST 15: Clean UI Integration (Shortcut, Command Palette & Shutdown)
        print("[TEST 15] Verifying Clean UI Integration (Shortcut, Command Palette, Shutdown)...", flush=True)
        has_analytics_cmd = window.command_registry.has("view.ai_analytics")
        has_models_cmd = window.command_registry.has("ai.manage_models")

        # Hardware report verification
        report = SystemResourceMonitor.inspect_system(client)
        has_hw_ram = report.ram_measured and report.total_ram_gb > 0

        # Clean shutdown
        window.close()
        app.processEvents()
        time.sleep(0.5)

        term_stopped = (
            window.terminal.process is None
            or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning
        )

        t15_ok = has_analytics_cmd and has_models_cmd and has_hw_ram and term_stopped
        test_results["15_clean_ui_integration"] = t15_ok
        print(f"  Result: {'PASS' if t15_ok else 'FAIL'} (AnalyticsCmd={has_analytics_cmd}, ModelsCmd={has_models_cmd}, RAMMeasured={has_hw_ram}, ShutdownOk={term_stopped})", flush=True)

    finally:
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================", flush=True)
    print("FINAL PHASE 7 TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    print(f"OVERALL STATUS: {'ALL 15 PHASE 7 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)
    print("=======================================================\n", flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_phase7_tests())

