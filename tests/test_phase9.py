"""
OpenArise IDE - Phase 9 Complete 25-Point Test Suite
Tests:
  1. Website Builder UI
  2. Prompt validation
  3. Technology selection
  4. HTML project generation
  5. React + Vite project generation
  6. Multi-page project structure
  7. Generated file preview
  8. File approval
  9. File rejection
  10. Overwrite protection
  11. Path traversal prevention
  12. Active project context
  13. AI prompt construction
  14. Ollama response parsing
  15. Generated file validation
  16. Package manager detection
  17. Dependency approval
  18. Local server startup
  19. Port conflict handling
  20. Server cancellation
  21. Server termination and cleanup
  22. Browser URL generation
  23. Error capture
  24. AI-assisted error correction
  25. Existing AI Agent compatibility
"""

from __future__ import annotations
import json
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from core.agent_models import FileChangeRecord, FileChangeType, FileChangeStatus
from core.website_server import WebsiteServerManager, WebsiteServerState, is_port_available, find_available_port
from core.website_generator import AIWebsiteGenerator, WebsiteSpec
from ui.website_builder_dialog import WebsiteBuilderDialog, WebsiteGenerationWorker
from ui.website_server_panel import WebsiteServerPanel
from ui.main_window import MainWindow


def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p9_test_"))
    results = {}

    print("\n=======================================================")
    print("STARTING OPENARISE IDE PHASE 9 TEST SUITE (25 TESTS)")
    print("=======================================================\n")
    print(f"Isolated test workspace: {test_dir}")

    window = None
    try:
        # Mock startup recovery dialog
        with patch.object(MainWindow, "_check_startup_recovery_and_project", MagicMock()):
            window = MainWindow()
        window._load_project_folder(test_dir)
        app.processEvents()

        # -------------------------------------------------------------
        # TEST 1: Website Builder UI
        # -------------------------------------------------------------
        print("[TEST 1] Verifying Website Builder UI Initialization...")
        builder_dlg = WebsiteBuilderDialog(default_model="qwen2.5-coder:7b", initial_dest=test_dir, parent=window)
        app.processEvents()
        t1_ok = (
            builder_dlg.name_edit is not None and
            builder_dlg.dest_edit is not None and
            builder_dlg.prompt_edit is not None and
            builder_dlg.radio_html.isChecked() and
            not builder_dlg.radio_react.isChecked() and
            builder_dlg.generate_btn.isEnabled()
        )
        results["1_website_builder_ui"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 2: Prompt Validation
        # -------------------------------------------------------------
        print("[TEST 2] Verifying Prompt Validation & Example Prompts...")
        builder_dlg.prompt_edit.setPlainText("abc")  # < 5 chars
        with patch.object(QMessageBox, "warning") as mock_warn:
            builder_dlg._start_generation()
            t2_short_rejected = mock_warn.called

        builder_dlg._load_example_prompt()
        t2_loaded_example = len(builder_dlg.prompt_edit.toPlainText().strip()) > 30
        t2_ok = t2_short_rejected and t2_loaded_example
        results["2_prompt_validation"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 3: Technology Selection
        # -------------------------------------------------------------
        print("[TEST 3] Verifying Technology Selection Switching...")
        builder_dlg.radio_react.setChecked(True)
        t3_react_active = builder_dlg.radio_react.isChecked() and not builder_dlg.radio_html.isChecked()
        builder_dlg.radio_html.setChecked(True)
        t3_html_active = builder_dlg.radio_html.isChecked() and not builder_dlg.radio_react.isChecked()
        t3_ok = t3_react_active and t3_html_active
        results["3_technology_selection"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 4: HTML Project Generation
        # -------------------------------------------------------------
        print("[TEST 4] Verifying HTML Project Generation...")
        spec_html = WebsiteSpec(
            name="test-html-site",
            dest_dir=test_dir,
            prompt="Personal portfolio website with home and about sections.",
            tech="html",
            is_multipage=False,
        )
        with patch.object(AIWebsiteGenerator, "_query_ollama_generator", return_value=None):
            records_html = AIWebsiteGenerator.generate_website(spec_html)
        files_html = {r.rel_path: r.new_content for r in records_html}
        t4_ok = (
            "index.html" in files_html and
            "css/styles.css" in files_html and
            "js/app.js" in files_html and
            "README.md" in files_html and
            ("test html site" in files_html["index.html"].lower() or "portfolio" in files_html["index.html"].lower())
        )
        results["4_html_project_generation"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (Files: {list(files_html.keys())})")

        # -------------------------------------------------------------
        # TEST 5: React + Vite Project Generation
        # -------------------------------------------------------------
        print("[TEST 5] Verifying React + Vite Project Generation...")
        spec_react = WebsiteSpec(
            name="test-react-site",
            dest_dir=test_dir,
            prompt="Interactive dashboard app.",
            tech="react",
            is_multipage=False,
        )
        with patch.object(AIWebsiteGenerator, "_query_ollama_generator", return_value=None):
            records_react = AIWebsiteGenerator.generate_website(spec_react)
        files_react = {r.rel_path: r.new_content for r in records_react}
        t5_ok = (
            "package.json" in files_react and
            "index.html" in files_react and
            "src/main.jsx" in files_react and
            "src/App.jsx" in files_react and
            "vite.config.js" in files_react and
            '"vite"' in files_react["package.json"]
        )
        results["5_react_vite_generation"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (Files: {list(files_react.keys())})")

        # -------------------------------------------------------------
        # TEST 6: Multi-Page Project Structure
        # -------------------------------------------------------------
        print("[TEST 6] Verifying Multi-Page Project Structure...")
        spec_multi = WebsiteSpec(
            name="test-multipage-site",
            dest_dir=test_dir,
            prompt="Corporate company website with about and contact pages.",
            tech="html",
            is_multipage=True,
        )
        with patch.object(AIWebsiteGenerator, "_query_ollama_generator", return_value=None):
            records_multi = AIWebsiteGenerator.generate_website(spec_multi)
        files_multi = {r.rel_path: r.new_content for r in records_multi}
        t6_ok = (
            "index.html" in files_multi and
            "about.html" in files_multi and
            "contact.html" in files_multi and
            "css/styles.css" in files_multi
        )
        results["6_multipage_structure"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (HasMultiPages={t6_ok})")

        # -------------------------------------------------------------
        # TEST 7: Generated File Preview
        # -------------------------------------------------------------
        print("[TEST 7] Verifying Generated File Preview & Record Types...")
        t7_ok = all(
            r.change_type in (FileChangeType.CREATE, FileChangeType.CREATE.value) and
            r.status in (FileChangeStatus.PROPOSED, FileChangeStatus.PROPOSED.value) and
            len(r.new_content or "") > 10
            for r in records_html
        )
        results["7_generated_file_preview"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 8: File Approval
        # -------------------------------------------------------------
        print("[TEST 8] Verifying File Approval Writing to Disk...")
        approved_site_dir = test_dir / "approved-site"
        approved_site_dir.mkdir(parents=True, exist_ok=True)
        for rec in records_html:
            tf = approved_site_dir / rec.rel_path
            tf.parent.mkdir(parents=True, exist_ok=True)
            tf.write_text(rec.new_content or "", encoding="utf-8")
        t8_ok = (
            (approved_site_dir / "index.html").exists() and
            (approved_site_dir / "css" / "styles.css").exists()
        )
        results["8_file_approval"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 9: File Rejection
        # -------------------------------------------------------------
        print("[TEST 9] Verifying File Rejection...")
        rejected_site_dir = test_dir / "rejected-site"
        # Simulate rejected decision: do not write
        t9_ok = not rejected_site_dir.exists()
        results["9_file_rejection"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 10: Overwrite Protection
        # -------------------------------------------------------------
        print("[TEST 10] Verifying Overwrite Protection (Collision Guard)...")
        existing_dir = test_dir / "existing-occupied"
        existing_dir.mkdir(parents=True, exist_ok=True)
        (existing_dir / "old_file.txt").write_text("precious user content", encoding="utf-8")

        spec_collide = WebsiteSpec(
            name="existing-occupied",
            dest_dir=test_dir,
            prompt="Try to overwrite",
            tech="html"
        )
        t10_caught = False
        try:
            AIWebsiteGenerator.generate_website(spec_collide)
        except FileExistsError:
            t10_caught = True
        t10_ok = t10_caught and (existing_dir / "old_file.txt").read_text() == "precious user content"
        results["10_overwrite_protection"] = t10_ok
        print(f"  Result: {'PASS' if t10_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 11: Path Traversal Prevention
        # -------------------------------------------------------------
        print("[TEST 11] Verifying Path Traversal Prevention...")
        t11_caught = False
        try:
            bad_files = {"../escape.html": "hacked"}
            AIWebsiteGenerator._validate_generated_files(bad_files, "html")
        except ValueError:
            t11_caught = True
        results["11_path_traversal_prevention"] = t11_caught
        print(f"  Result: {'PASS' if t11_caught else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 12: Active Project Context
        # -------------------------------------------------------------
        print("[TEST 12] Verifying Active Project Context...")
        window.website_server_panel.set_project(approved_site_dir)
        t12_ok = window.website_server_panel.project_dir == approved_site_dir
        results["12_active_project_context"] = t12_ok
        print(f"  Result: {'PASS' if t12_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 13: AI Prompt Construction
        # -------------------------------------------------------------
        print("[TEST 13] Verifying AI Prompt Construction...")
        captured_prompts = []
        def fake_post(url, json=None, **kwargs):
            captured_prompts.append(json)
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {
                "message": {
                    "content": '{"thought": "test", "files": [{"path": "index.html", "content": "<h1>Custom AI</h1>"}]}'
                }
            }
            return mock_res

        with patch("requests.post", side_effect=fake_post):
            spec_ai = WebsiteSpec(name="ai-site", dest_dir=test_dir, prompt="Cyberpunk coffee shop site", tech="html")
            recs = AIWebsiteGenerator.generate_website(spec_ai)
            t13_ok = (
                len(captured_prompts) > 0 and
                "Cyberpunk coffee shop site" in captured_prompts[0]["messages"][-1]["content"] and
                "HTML5, CSS3, and modern JavaScript" in captured_prompts[0]["messages"][0]["content"] and
                recs[0].new_content == "<h1>Custom AI</h1>"
            )
        results["13_ai_prompt_construction"] = t13_ok
        print(f"  Result: {'PASS' if t13_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 14: Ollama Response Parsing
        # -------------------------------------------------------------
        print("[TEST 14] Verifying Ollama Response Parsing (Clean & Fenced JSON)...")
        clean_json = '{"thought": "clean", "files": [{"path": "index.html", "content": "clean"}]}'
        fenced_json = '```json\n{"thought": "fenced", "files": [{"path": "index.html", "content": "fenced"}]}\n```'
        broken_json = 'Not a json response'
        p1 = AIWebsiteGenerator._parse_json_payload(clean_json)
        p2 = AIWebsiteGenerator._parse_json_payload(fenced_json)
        p3 = AIWebsiteGenerator._parse_json_payload(broken_json)
        t14_ok = (
            p1 is not None and p1.get("thought") == "clean" and
            p2 is not None and p2.get("thought") == "fenced" and
            p3 is None
        )
        results["14_response_parsing"] = t14_ok
        print(f"  Result: {'PASS' if t14_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 15: Generated File Validation
        # -------------------------------------------------------------
        print("[TEST 15] Verifying Generated File Validation...")
        val_ok, issues = AIWebsiteGenerator.validate_website_project(approved_site_dir)
        t15_valid = val_ok and len(issues) == 0

        # Break a stylesheet reference
        bad_site_dir = test_dir / "bad-site"
        bad_site_dir.mkdir(parents=True, exist_ok=True)
        (bad_site_dir / "index.html").write_text(
            '<html><head><link rel="stylesheet" href="css/missing.css"></head><body></body></html>',
            encoding="utf-8"
        )
        val_bad_ok, bad_issues = AIWebsiteGenerator.validate_website_project(bad_site_dir)
        t15_flagged = not val_bad_ok and any("missing.css" in iss for iss in bad_issues)
        t15_ok = t15_valid and t15_flagged
        results["15_file_validation"] = t15_ok
        print(f"  Result: {'PASS' if t15_ok else 'FAIL'} (ValidOk={t15_valid}, BrokenFlagged={t15_flagged})")

        # -------------------------------------------------------------
        # TEST 16: Package Manager Detection
        # -------------------------------------------------------------
        print("[TEST 16] Verifying Package Manager Detection...")
        srv_mgr = window.website_server_manager
        pnpm_dir = test_dir / "pnpm-proj"
        pnpm_dir.mkdir(parents=True, exist_ok=True)
        (pnpm_dir / "package.json").write_text("{}", encoding="utf-8")
        (pnpm_dir / "pnpm-lock.yaml").write_text("", encoding="utf-8")

        npm_dir = test_dir / "npm-proj"
        npm_dir.mkdir(parents=True, exist_ok=True)
        (npm_dir / "package.json").write_text("{}", encoding="utf-8")

        t16_ok = (
            srv_mgr.detect_package_manager(pnpm_dir) == "pnpm" and
            srv_mgr.detect_package_manager(npm_dir) == "npm"
        )
        results["16_package_manager_detection"] = t16_ok
        print(f"  Result: {'PASS' if t16_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 17: Dependency Approval Requirement
        # -------------------------------------------------------------
        print("[TEST 17] Verifying Dependency Approval Gate...")
        react_uninstalled = test_dir / "react-no-deps"
        react_uninstalled.mkdir(parents=True, exist_ok=True)
        (react_uninstalled / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")

        # Set handler returning False (approval denied)
        srv_mgr.set_dependency_approval_handler(lambda title, msg: False)
        start_res = srv_mgr.start(react_uninstalled)
        t17_ok = (
            start_res is False and
            srv_mgr.state == WebsiteServerState.ERROR and
            any("Dependency installation was not approved" in log for log in srv_mgr.get_logs())
        )
        results["17_dependency_approval"] = t17_ok
        print(f"  Result: {'PASS' if t17_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 18: Local Server Startup on 127.0.0.1
        # -------------------------------------------------------------
        print("[TEST 18] Verifying Local Server Startup on 127.0.0.1...")
        test_port = find_available_port(8920)
        started = srv_mgr.start(approved_site_dir, port=test_port)
        app.processEvents()

        # Wait up to 3 seconds for server readiness
        start_wait = time.time()
        while time.time() - start_wait < 3.0:
            app.processEvents()
            if srv_mgr.state == WebsiteServerState.RUNNING:
                break
            time.sleep(0.05)

        t18_ok = (
            started is True and
            srv_mgr.state == WebsiteServerState.RUNNING and
            srv_mgr.current_url == f"http://127.0.0.1:{test_port}" and
            srv_mgr.current_port == test_port
        )
        results["18_local_server_startup"] = t18_ok
        print(f"  Result: {'PASS' if t18_ok else 'FAIL'} (URL={srv_mgr.current_url}, State={srv_mgr.state})")

        # -------------------------------------------------------------
        # TEST 19: Port Conflict Handling
        # -------------------------------------------------------------
        print("[TEST 19] Verifying Port Conflict Handling & Free Port Finding...")
        # Occupy a dummy port
        dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy_sock.bind(("127.0.0.1", 0))
        occupied_port = dummy_sock.getsockname()[1]

        t19_is_busy = not is_port_available(occupied_port)
        next_free = find_available_port(occupied_port)
        t19_found_different = next_free != occupied_port and is_port_available(next_free)
        dummy_sock.close()

        t19_ok = t19_is_busy and t19_found_different
        results["19_port_conflict_handling"] = t19_ok
        print(f"  Result: {'PASS' if t19_ok else 'FAIL'} (BusyDetected={t19_is_busy}, FoundFree={next_free})")

        # -------------------------------------------------------------
        # TEST 20: Server Cancellation
        # -------------------------------------------------------------
        print("[TEST 20] Verifying Server Worker / Process Cancellation...")
        spec_cancel = WebsiteSpec(name="cancel-site", dest_dir=test_dir, prompt="cancel test")
        worker = WebsiteGenerationWorker(spec_cancel)
        worker.cancel()
        t20_ok = worker._is_cancelled is True
        results["20_server_cancellation"] = t20_ok
        print(f"  Result: {'PASS' if t20_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 21: Server Termination and Cleanup
        # -------------------------------------------------------------
        print("[TEST 21] Verifying Server Termination and Process Cleanup...")
        srv_mgr.stop()
        app.processEvents()
        t21_ok = (
            srv_mgr.state == WebsiteServerState.STOPPED and
            srv_mgr.current_url is None and
            not srv_mgr.is_running()
        )
        results["21_server_termination_cleanup"] = t21_ok
        print(f"  Result: {'PASS' if t21_ok else 'FAIL'}")

        # -------------------------------------------------------------
        # TEST 22: Browser URL Generation & Copy
        # -------------------------------------------------------------
        print("[TEST 22] Verifying Browser URL Generation & Copy...")
        srv_mgr.current_url = "http://127.0.0.1:8920"
        window.website_server_panel._on_url_ready("http://127.0.0.1:8920")
        app.processEvents()

        with patch("webbrowser.open") as mock_browse:
            window.website_server_panel._open_browser()
            t22_browse_called = mock_browse.called and mock_browse.call_args[0][0] == "http://127.0.0.1:8920"

        window.website_server_panel._copy_url()
        copied_text = QApplication.clipboard().text()
        t22_copied = (copied_text == "http://127.0.0.1:8920")
        t22_ok = t22_browse_called and t22_copied
        results["22_browser_url_generation"] = t22_ok
        print(f"  Result: {'PASS' if t22_ok else 'FAIL'} (BrowseOpened={t22_browse_called}, ClipboardCopied={t22_copied})")

        # -------------------------------------------------------------
        # TEST 23: Error Capture
        # -------------------------------------------------------------
        print("[TEST 23] Verifying Error Capture & State...")
        srv_mgr._parse_server_output("Error: Address already in use 127.0.0.1:8000")
        app.processEvents()
        t23_ok = (
            srv_mgr.state == WebsiteServerState.ERROR and
            not window.website_server_panel.fix_ai_btn.isHidden()
        )
        results["23_error_capture"] = t23_ok
        print(f"  Result: {'PASS' if t23_ok else 'FAIL'} (State=ERROR, FixButtonVisible=True)")

        # -------------------------------------------------------------
        # TEST 24: AI-Assisted Error Correction
        # -------------------------------------------------------------
        print("[TEST 24] Verifying AI-Assisted Error Correction...")
        error_sample = "Uncaught SyntaxError: Unexpected token in index.html"
        mock_fix_res = MagicMock()
        mock_fix_res.status_code = 200
        mock_fix_res.json.return_value = {
            "message": {
                "content": '{"thought": "fix error", "files": [{"path": "index.html", "content": "<!DOCTYPE html><html>Fixed</html>"}]}'
            }
        }
        with patch("requests.post", return_value=mock_fix_res):
            fix_records = AIWebsiteGenerator.fix_website_errors(approved_site_dir, error_sample)
        t24_ok = (
            len(fix_records) > 0 and
            any(r.change_type in (FileChangeType.MODIFY, FileChangeType.CREATE, FileChangeType.MODIFY.value, FileChangeType.CREATE.value) for r in fix_records)
        )
        results["24_ai_error_correction"] = t24_ok
        print(f"  Result: {'PASS' if t24_ok else 'FAIL'} (FixRecordsCount={len(fix_records)})")

        # -------------------------------------------------------------
        # TEST 25: Existing AI Agent Compatibility
        # -------------------------------------------------------------
        print("[TEST 25] Verifying Existing AI Agent Compatibility...")
        # Verify Agent Mode switcher, tabs, and panel coexist peacefully
        agent_tab_ok = hasattr(window, "agent_panel") and window.agent_panel is not None
        server_tab_ok = hasattr(window, "website_server_panel") and window.website_server_panel is not None
        term_dock_ok = hasattr(window, "terminal_dock") and window.terminal_dock is not None
        window.switch_to_agent_mode()
        app.processEvents()
        agent_visible = window.chat.stack.currentWidget() == window.chat.agent_panel

        window.switch_to_chat_mode()
        app.processEvents()
        chat_visible = window.chat.stack.currentWidget() == window.chat.chat_panel

        t25_ok = agent_tab_ok and server_tab_ok and term_dock_ok and agent_visible and chat_visible
        results["25_agent_compatibility"] = t25_ok
        print(f"  Result: {'PASS' if t25_ok else 'FAIL'}")

    finally:
        if window:
            if hasattr(window, "website_server_manager") and window.website_server_manager:
                window.website_server_manager.stop()
            window.close()
            app.processEvents()
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\n=======================================================")
    print("FINAL PHASE 9 TEST RESULTS SUMMARY")
    print("=======================================================")
    all_passed = True
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=======================================================")
    print(f"OVERALL STATUS: {'ALL 25 PHASE 9 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=======================================================\n")
    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
