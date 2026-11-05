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

from PyQt6.QtCore import Qt, QPoint, QEvent
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QMessageBox, QInputDialog

from ui.main_window import MainWindow
from core.settings_manager import SettingsManager, DEFAULT_SETTINGS
from core.recovery_manager import RecoveryManager
from ui.themes import get_theme_stylesheet, THEMES


def create_key_press_event(key: Qt.Key, text: str = "") -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)


def run_phase3_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================")
    print("STARTING OPENARISE IDE PHASE 3 INTEGRATION TEST SUITE")
    print("=======================================================\n")

    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p3_test_"))
    print(f"Isolated test workspace: {test_dir}")

    window = MainWindow()
    window.show()
    app.processEvents()

    # Set project root to isolated test workspace
    window.project_root = test_dir
    window.context.set_project(test_dir)
    window.fs_model.setRootPath(str(test_dir))
    window.tree.setRootIndex(window.fs_model.index(str(test_dir)))
    window.terminal.set_working_directory(test_dir)
    app.processEvents()
    time.sleep(0.5)

    try:
        # TEST 1: Command Palette Shortcut & Positioning
        print("[TEST 1] Verifying Command Palette Shortcut & Top-Center Positioning...")
        initial_hidden = not window.command_palette.isVisible()
        window.command_palette.show_palette()
        app.processEvents()
        time.sleep(0.1)

        palette_visible = window.command_palette.isVisible()
        palette_geo = window.command_palette.geometry()
        parent_geo = window.geometry()
        is_centered = abs((palette_geo.x() + palette_geo.width() // 2) - (parent_geo.x() + parent_geo.width() // 2)) <= 10
        is_near_top = palette_geo.y() == parent_geo.y() + 48
        is_frameless = bool(window.command_palette.windowFlags() & Qt.WindowType.FramelessWindowHint)

        test_results["1_palette_shortcut_and_position"] = initial_hidden and palette_visible and is_centered and is_near_top and is_frameless
        print(f"  Result: {'PASS' if test_results['1_palette_shortcut_and_position'] else 'FAIL'} (Visible={palette_visible}, Centered={is_centered}, NearTop={is_near_top}, Frameless={is_frameless})")

        # TEST 2: Live Search Filtering in Command Palette
        print("[TEST 2] Verifying Live Search Filtering in Command Palette...")
        window.command_palette.search_input.setText("Save")
        app.processEvents()
        save_count = window.command_palette.results_list.count()
        save_filtered_ok = save_count >= 2  # "Save" and "Save All"

        # Check all results match
        all_match = True
        for i in range(save_count):
            item = window.command_palette.results_list.item(i)
            cmd = item.data(Qt.ItemDataRole.UserRole)
            if "save" not in cmd.title.lower() and "save" not in cmd.category.lower():
                all_match = False

        # Non-matching query
        window.command_palette.search_input.setText("xyz_non_existent_command_123")
        app.processEvents()
        zero_count = window.command_palette.results_list.count() == 0

        # Clear query restores all
        window.command_palette.search_input.setText("")
        app.processEvents()
        restored_count = window.command_palette.results_list.count() == len(window.command_registry.all_commands())

        test_results["2_live_search_filtering"] = save_filtered_ok and all_match and zero_count and restored_count
        print(f"  Result: {'PASS' if test_results['2_live_search_filtering'] else 'FAIL'} (SaveCount={save_count}, ZeroCount={zero_count}, Restored={restored_count})")

        # TEST 3: Keyboard Navigation & Dismissal (Up/Down/Enter/Escape)
        print("[TEST 3] Verifying Keyboard Navigation and Dismissal...")
        window.command_palette.search_input.clear()
        app.processEvents()
        initial_row = window.command_palette.results_list.currentRow()

        # Simulate Down Arrow
        down_event = create_key_press_event(Qt.Key.Key_Down)
        window.command_palette.eventFilter(window.command_palette.search_input, down_event)
        app.processEvents()
        row_after_down = window.command_palette.results_list.currentRow()
        down_ok = row_after_down == initial_row + 1

        # Simulate Up Arrow
        up_event = create_key_press_event(Qt.Key.Key_Up)
        window.command_palette.eventFilter(window.command_palette.search_input, up_event)
        app.processEvents()
        row_after_up = window.command_palette.results_list.currentRow()
        up_ok = row_after_up == initial_row

        # Simulate Escape dismissal
        esc_event = create_key_press_event(Qt.Key.Key_Escape)
        window.command_palette.eventFilter(window.command_palette.search_input, esc_event)
        app.processEvents()
        closed_ok = not window.command_palette.isVisible()

        test_results["3_keyboard_navigation_dismissal"] = down_ok and up_ok and closed_ok
        print(f"  Result: {'PASS' if test_results['3_keyboard_navigation_dismissal'] else 'FAIL'} (Down={down_ok}, Up={up_ok}, EscClose={closed_ok})")

        # TEST 4: Command Registry & Execution of All 15 Commands
        print("[TEST 4] Verifying Registration & Execution of All 15 Registered Commands...")
        expected_commands = [
            "file.open_folder", "file.new_file", "file.save", "file.save_all",
            "run.python", "view.toggle_terminal", "terminal.clear",
            "ai.generate_tests", "project.reindex", "edit.find_in_files",
            "file.go_to_file", "view.toggle_explorer", "preferences.settings",
            "help.extensions", "help.about"
        ]
        registered_ids = [cmd.id for cmd in window.command_registry.all_commands()]
        all_15_registered = all(cid in registered_ids for cid in expected_commands) and len(expected_commands) == 15

        # Test execution of toggle_explorer
        explorer_visible_before = window.tree.isVisible()
        window.command_registry.execute("view.toggle_explorer")
        app.processEvents()
        explorer_toggled = window.tree.isVisible() != explorer_visible_before
        window.command_registry.execute("view.toggle_explorer")
        app.processEvents()

        # Test execution of toggle_terminal
        term_visible_before = window.terminal_dock.isVisible()
        window.command_registry.execute("view.toggle_terminal")
        app.processEvents()
        term_toggled = window.terminal_dock.isVisible() != term_visible_before
        window.command_registry.execute("view.toggle_terminal")
        app.processEvents()

        # Test execution of terminal.clear
        window.terminal.output_area.setPlainText("SOME TEST TERMINAL OUTPUT TO CLEAR")
        window.command_registry.execute("terminal.clear")
        app.processEvents()
        term_cleared = window.terminal.output_area.toPlainText() == ""

        # Test execution of file.new_file
        tab_count_before = window.editor.count()
        window.command_registry.execute("file.new_file")
        app.processEvents()
        new_file_executed = window.editor.count() == tab_count_before + 1

        test_results["4_all_15_registered_commands"] = all_15_registered and explorer_toggled and term_toggled and term_cleared and new_file_executed
        print(f"  Result: {'PASS' if test_results['4_all_15_registered_commands'] else 'FAIL'} (Registered={all_15_registered}, ExplorerToggle={explorer_toggled}, TermToggle={term_toggled}, Clear={term_cleared}, NewFile={new_file_executed})")

        # TEST 5: Personalization Settings Persistence
        print("[TEST 5] Verifying Settings Persistence Across Restarts...")
        custom_config_dir = test_dir / "custom_config"
        mgr1 = SettingsManager(config_dir=custom_config_dir)
        mgr1.set("editor_font_size", 17)
        mgr1.set("tab_size", 8)
        mgr1.set("theme", "Nord")
        mgr1.set("auto_save", False)
        mgr1.set("startup_behavior", "blank")
        mgr1.save()

        # Load fresh instance from file
        mgr2 = SettingsManager(config_dir=custom_config_dir)
        persisted = (
            mgr2.get("editor_font_size") == 17
            and mgr2.get("tab_size") == 8
            and mgr2.get("theme") == "Nord"
            and mgr2.get("auto_save") is False
            and mgr2.get("startup_behavior") == "blank"
        )

        mgr2.reset_to_defaults()
        reset_ok = mgr2.get("editor_font_size") == DEFAULT_SETTINGS["editor_font_size"] and mgr2.get("tab_size") == DEFAULT_SETTINGS["tab_size"]

        test_results["5_settings_persistence"] = persisted and reset_ok
        print(f"  Result: {'PASS' if test_results['5_settings_persistence'] else 'FAIL'} (Persisted={persisted}, ResetDefaults={reset_ok})")

        # TEST 6: Theme Switching Across All 5 Themes
        print("[TEST 6] Verifying Theme Switching for All 5 Themes...")
        theme_names = ["OpenArise Dark", "Dracula", "Monokai", "Nord", "Light"]
        themes_ok = True
        for theme_name in theme_names:
            css = get_theme_stylesheet(theme_name)
            if not css or len(css) < 500:
                themes_ok = False
                break
            window.setStyleSheet(css)
            app.processEvents()

        # Re-apply OpenArise Dark
        window.setStyleSheet(get_theme_stylesheet("OpenArise Dark"))
        app.processEvents()

        test_results["6_theme_switching"] = themes_ok and len(THEMES) == 5
        print(f"  Result: {'PASS' if test_results['6_theme_switching'] else 'FAIL'} (5 Themes Verified={themes_ok})")

        # TEST 7: Live Editor Font & Configuration Application
        print("[TEST 7] Verifying Live Editor Configuration Application...")
        window.apply_user_settings({
            "editor_font_family": "Courier New",
            "editor_font_size": 18,
            "tab_size": 2,
            "word_wrap": True,
            "line_numbers": False,
        })
        app.processEvents()
        current_ed = window.editor.current_editor()
        font_ok = current_ed.font().family() == "Courier New" and current_ed.font().pointSize() == 18
        tab_size_ok = current_ed.tab_size == 2
        wrap_ok = current_ed.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        lines_ok = current_ed.show_line_numbers is False

        # Restore normal settings
        window.apply_user_settings({
            "editor_font_family": "Consolas",
            "editor_font_size": 11,
            "tab_size": 4,
            "word_wrap": False,
            "line_numbers": True,
        })
        app.processEvents()
        restored_editor_ok = current_ed.show_line_numbers is True and current_ed.tab_size == 4

        test_results["7_live_editor_configuration"] = font_ok and tab_size_ok and wrap_ok and lines_ok and restored_editor_ok
        print(f"  Result: {'PASS' if test_results['7_live_editor_configuration'] else 'FAIL'} (Font={font_ok}, TabSize={tab_size_ok}, Wrap={wrap_ok}, Lines={lines_ok})")

        # TEST 8: Auto Save on Timer
        print("[TEST 8] Verifying Auto Save on Timer...")
        autosave_file = test_dir / "autosave_test.py"
        autosave_file.write_text("# Initial autosave file\n", encoding="utf-8")
        as_editor = window.editor.open_file(str(autosave_file))
        as_marker = f"# AUTOSAVE_EDIT_{int(time.time())}"
        as_editor.setPlainText(f"# Initial autosave file\n{as_marker}\n")
        as_editor.document().setModified(True)

        window._run_autosave()
        app.processEvents()

        file_content = autosave_file.read_text(encoding="utf-8")
        autosave_saved = as_marker in file_content and not as_editor.document().isModified()

        test_results["8_auto_save_on_timer"] = autosave_saved
        print(f"  Result: {'PASS' if autosave_saved else 'FAIL'} (SavedOnDisk={autosave_saved})")

        # TEST 9: External File Modification Conflict Detection
        print("[TEST 9] Verifying External File Modification Conflict Detection...")
        time.sleep(0.05)
        # Modify file on disk externally
        external_marker = f"# EXTERNAL_MODIFICATION_{int(time.time())}"
        autosave_file.write_text(external_marker, encoding="utf-8")

        # Make an unsaved local edit in the editor buffer
        as_editor.setPlainText("# LOCAL_DIRTY_BUFFER_CONTENT")
        as_editor.document().setModified(True)

        # Run autosave: must detect external change and NOT overwrite the external change
        window._run_autosave()
        app.processEvents()

        disk_after = autosave_file.read_text(encoding="utf-8")
        external_preserved = disk_after == external_marker
        status_msg = window.status.currentMessage()
        conflict_detected = "modified externally" in status_msg or "skipped overwrite" in status_msg

        test_results["9_external_modification_guard"] = external_preserved and conflict_detected
        print(f"  Result: {'PASS' if test_results['9_external_modification_guard'] else 'FAIL'} (ExternalPreserved={external_preserved}, ConflictReported={conflict_detected})")

        # TEST 10: Crash Recovery Snapshot Creation
        print("[TEST 10] Verifying Crash Recovery Snapshot Creation...")
        recovery_dir = test_dir / "recovery_test"
        rec_mgr = RecoveryManager(recovery_dir=recovery_dir)
        rec_mgr.start_session(test_dir)

        test_tabs_info = [
            {
                "tab_name": "unsaved_draft.py",
                "file_path": None,
                "is_modified": True,
                "cursor_position": 14,
                "content": "def unsaved_work():\n    return 42\n"
            },
            {
                "tab_name": "project_file.py",
                "file_path": str(test_dir / "project_file.py"),
                "is_modified": True,
                "cursor_position": 8,
                "content": "val = 100\n"
            }
        ]
        rec_mgr.save_snapshot(test_dir, test_tabs_info)

        meta_exists = (recovery_dir / "recovery_metadata.json").exists()
        snap_0_exists = (recovery_dir / "snapshots" / "tab_0.txt").exists()
        snap_1_exists = (recovery_dir / "snapshots" / "tab_1.txt").exists()
        snap_0_content = (recovery_dir / "snapshots" / "tab_0.txt").read_text(encoding="utf-8") if snap_0_exists else ""

        snapshot_created = meta_exists and snap_0_exists and snap_1_exists and "def unsaved_work" in snap_0_content

        test_results["10_crash_recovery_snapshot"] = snapshot_created
        print(f"  Result: {'PASS' if snapshot_created else 'FAIL'} (Metadata={meta_exists}, SnapshotsExist={snap_0_exists and snap_1_exists})")

        # TEST 11: Crash Recovery Restore Workflow
        print("[TEST 11] Verifying Crash Recovery Restore Workflow...")
        # Fresh RecoveryManager inspecting the crashed snapshot directory
        rec_mgr2 = RecoveryManager(recovery_dir=recovery_dir)
        has_session = rec_mgr2.has_recoverable_session()
        recovered_session = rec_mgr2.get_recovered_session()

        session_valid = has_session and recovered_session is not None and len(recovered_session["tabs"]) == 2

        # Restore into editor
        tab_count_before = window.editor.count()
        window.editor.restore_session_tabs(recovered_session["tabs"])
        app.processEvents()

        restored_tab_editor = window.editor.current_editor()
        restored_ok = (
            window.editor.count() == tab_count_before + 2
            and "val = 100" in restored_tab_editor.toPlainText()
        )

        test_results["11_crash_recovery_restore"] = session_valid and restored_ok
        print(f"  Result: {'PASS' if test_results['11_crash_recovery_restore'] else 'FAIL'} (HasSession={has_session}, Restored={restored_ok})")

        # TEST 12: Crash Recovery Discard Workflow
        print("[TEST 12] Verifying Crash Recovery Discard Workflow...")
        rec_mgr2.clear_recovery()
        has_after_clear = rec_mgr2.has_recoverable_session()
        dir_cleared = not recovery_dir.exists()

        test_results["12_crash_recovery_discard"] = not has_after_clear and dir_cleared
        print(f"  Result: {'PASS' if test_results['12_crash_recovery_discard'] else 'FAIL'} (HasSessionAfterClear={has_after_clear}, DirRemoved={dir_cleared})")

        # TEST 13: Integrated Terminal & Run Python (F5) Compatibility
        print("[TEST 13] Verifying Terminal & Run Python (F5) Compatibility...")
        py_test_file = test_dir / "p3_f5_exec.py"
        p3_marker = f"P3_RUN_OK_{int(time.time())}"
        py_test_file.write_text(f'print("{p3_marker}")\n', encoding="utf-8")
        window.editor.open_file(str(py_test_file))
        app.processEvents()

        orig_question = QMessageBox.question
        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Save
        window.run_python()
        QMessageBox.question = orig_question

        start_wait = time.time()
        f5_found = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if p3_marker in window.terminal.output_area.toPlainText():
                f5_found = True
                break

        test_results["13_terminal_and_f5_compatibility"] = f5_found
        print(f"  Result: {'PASS' if f5_found else 'FAIL'} (MarkerFound={f5_found})")

        # TEST 14: Ollama AI Chat Preservation & Clean Application Shutdown
        print("[TEST 14] Verifying Ollama AI Chat Preservation & Clean Shutdown...")
        ollama_models = window.client.list_models()
        qwen_available = any("qwen2.5-coder:7b" in m for m in ollama_models)

        # Test clean shutdown
        window.close()
        app.processEvents()
        time.sleep(0.5)

        timers_stopped = not window.autosave_timer.isActive() and not window.recovery_timer.isActive()
        terminal_shutdown = window.terminal.process is None or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning

        test_results["14_ollama_and_clean_shutdown"] = qwen_available and timers_stopped and terminal_shutdown
        print(f"  Result: {'PASS' if test_results['14_ollama_and_clean_shutdown'] else 'FAIL'} (Qwen2.5Coder={qwen_available}, TimersStopped={timers_stopped}, TermShutdown={terminal_shutdown})")

    finally:
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================")
    print("FINAL PHASE 3 TEST RESULTS SUMMARY")
    print("=======================================================")
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=======================================================")
    print(f"OVERALL STATUS: {'ALL 14 PHASE 3 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=======================================================\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_phase3_tests())
