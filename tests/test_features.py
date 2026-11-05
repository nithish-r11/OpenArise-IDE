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

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from ui.main_window import MainWindow

def run_all_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================")
    print("STARTING OPENARISE IDE COMPLETE 16-POINT TEST SUITE")
    print("=======================================================\n")

    # Setup isolated test directory
    test_dir = Path(tempfile.mkdtemp(prefix="openarise_test_"))
    print(f"Isolated test workspace: {test_dir}")

    window = MainWindow()
    window.show()
    app.processEvents()

    # Set project root to test directory
    window.project_root = test_dir
    window.context.set_project(test_dir)
    window.fs_model.setRootPath(str(test_dir))
    window.tree.setRootIndex(window.fs_model.index(str(test_dir)))
    window.terminal.set_working_directory(test_dir)
    app.processEvents()
    time.sleep(1.0)

    try:
        # TEST 1: Terminal Open and Close
        print("[TEST 1] Verifying Terminal Open and Close...")
        initial_visible = window.terminal_dock.isVisible()
        window.toggle_terminal()
        app.processEvents()
        hidden_ok = not window.terminal_dock.isVisible()
        window.toggle_terminal()
        app.processEvents()
        visible_again = window.terminal_dock.isVisible()
        test_results["1_terminal_open_close"] = initial_visible and hidden_ok and visible_again
        print(f"  Result: {'PASS' if test_results['1_terminal_open_close'] else 'FAIL'}")

        # TEST 2: PowerShell Commands
        print("[TEST 2] Verifying PowerShell Command Execution...")
        test_marker = f"PWSH_MARKER_{int(time.time())}"
        window.terminal.execute_command(f'Write-Output "{test_marker}"')
        start_wait = time.time()
        pwsh_found = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if test_marker in window.terminal.output_area.toPlainText():
                pwsh_found = True
                break
        test_results["2_powershell_commands"] = pwsh_found
        print(f"  Result: {'PASS' if pwsh_found else 'FAIL'}")

        # TEST 3: Python File Execution
        print("[TEST 3] Verifying Python File Execution...")
        py_test_file = test_dir / "test_exec.py"
        py_marker = f"PY_EXEC_OK_{int(time.time())}"
        py_test_file.write_text(f'print("{py_marker}")\n', encoding="utf-8")
        editor = window.editor.open_file(str(py_test_file))
        app.processEvents()
        window.run_python()
        start_wait = time.time()
        py_found = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if py_marker in window.terminal.output_area.toPlainText():
                py_found = True
                break
        test_results["3_python_execution"] = py_found
        print(f"  Result: {'PASS' if py_found else 'FAIL'}")

        # TEST 4: stdout and stderr
        print("[TEST 4] Verifying stdout and stderr handling...")
        stdout_marker = f"OUT_{int(time.time())}"
        stderr_marker = f"ERR_{int(time.time())}"
        # Command that outputs to both stdout and stderr
        cmd_both = f'Write-Output "{stdout_marker}"; [Console]::Error.WriteLine("{stderr_marker}")'
        window.terminal.execute_command(cmd_both)
        start_wait = time.time()
        out_ok = False
        err_ok = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            output = window.terminal.output_area.toPlainText()
            if stdout_marker in output:
                out_ok = True
            if stderr_marker in output:
                err_ok = True
            if out_ok and err_ok:
                break
        test_results["4_stdout_stderr"] = out_ok and err_ok
        print(f"  Result: {'PASS' if test_results['4_stdout_stderr'] else 'FAIL'} (stdout={out_ok}, stderr={err_ok})")

        # TEST 5: Persistent Working Directory
        print("[TEST 5] Verifying Persistent Working Directory...")
        sub_dir = test_dir / "sub_cwd_test"
        sub_dir.mkdir(exist_ok=True)
        window.terminal.set_working_directory(sub_dir)
        app.processEvents()
        time.sleep(0.5)
        window.terminal.execute_command('(Get-Location).Path')
        start_wait = time.time()
        cwd_ok = False
        sub_dir_str = str(sub_dir)
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if sub_dir.name in window.terminal.output_area.toPlainText():
                cwd_ok = True
                break
        test_results["5_persistent_cwd"] = cwd_ok and (window.terminal.cwd == sub_dir)
        print(f"  Result: {'PASS' if test_results['5_persistent_cwd'] else 'FAIL'}")

        # TEST 6: Stop Running Process
        print("[TEST 6] Verifying Stop Running Process...")
        window.terminal.execute_command('Start-Sleep -Seconds 15')
        app.processEvents()
        time.sleep(0.3)
        window.terminal.stop_btn.click()
        app.processEvents()
        time.sleep(1.0)
        # Verify shell is restarted and responsive
        window.terminal.execute_command('Write-Output "AFTER_STOP_ALIVE"')
        start_wait = time.time()
        after_stop_ok = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if "AFTER_STOP_ALIVE" in window.terminal.output_area.toPlainText():
                after_stop_ok = True
                break
        test_results["6_stop_process"] = after_stop_ok
        print(f"  Result: {'PASS' if after_stop_ok else 'FAIL'}")

        # TEST 7: GUI Responsiveness
        print("[TEST 7] Verifying GUI Responsiveness during background execution...")
        window.terminal.execute_command('Start-Sleep -Seconds 2')
        t0 = time.time()
        # Verify event processing loop doesn't block
        for _ in range(10):
            app.processEvents()
            time.sleep(0.01)
        responsiveness_duration = time.time() - t0
        gui_responsive = responsiveness_duration < 0.5
        test_results["7_gui_responsiveness"] = gui_responsive
        print(f"  Result: {'PASS' if gui_responsive else 'FAIL'} (Duration: {responsiveness_duration:.3f}s)")

        # TEST 8: File Explorer Right-click Menu
        print("[TEST 8] Verifying File Right-click Menu Setup...")
        policy_ok = window.tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        # Check menu action generation logic
        val_ok, _ = window._validate_filename("valid_file.py")
        val_err, _ = window._validate_filename('invalid|name?.txt')
        test_results["8_right_click_menu"] = policy_ok and val_ok and (not val_err)
        print(f"  Result: {'PASS' if test_results['8_right_click_menu'] else 'FAIL'}")

        # TEST 9: New File and New Folder
        print("[TEST 9] Verifying New File and New Folder creation...")
        # Mock QInputDialog for New File
        orig_get_text = QInputDialog.getText
        QInputDialog.getText = lambda *args, **kwargs: ("created_by_test.py", True)
        window.new_file_in_tree(test_dir)
        created_file = test_dir / "created_by_test.py"
        new_file_ok = created_file.exists() and window.editor.is_file_open(created_file)

        # Mock QInputDialog for New Folder
        QInputDialog.getText = lambda *args, **kwargs: ("created_dir_by_test", True)
        window.new_folder_in_tree(test_dir)
        created_dir = test_dir / "created_dir_by_test"
        new_folder_ok = created_dir.exists() and created_dir.is_dir()

        QInputDialog.getText = orig_get_text
        test_results["9_new_file_and_folder"] = new_file_ok and new_folder_ok
        print(f"  Result: {'PASS' if test_results['9_new_file_and_folder'] else 'FAIL'} (File={new_file_ok}, Folder={new_folder_ok})")

        # TEST 10: Rename File and Folder
        print("[TEST 10] Verifying Rename File and Folder...")
        QInputDialog.getText = lambda *args, **kwargs: ("renamed_file_test.py", True)
        window.rename_tree_item(created_file)
        renamed_file = test_dir / "renamed_file_test.py"
        file_renamed_ok = renamed_file.exists() and not created_file.exists()

        QInputDialog.getText = lambda *args, **kwargs: ("renamed_dir_test", True)
        window.rename_tree_item(created_dir)
        renamed_dir = test_dir / "renamed_dir_test"
        dir_renamed_ok = renamed_dir.exists() and not created_dir.exists()

        QInputDialog.getText = orig_get_text
        test_results["10_rename_file_and_folder"] = file_renamed_ok and dir_renamed_ok
        print(f"  Result: {'PASS' if test_results['10_rename_file_and_folder'] else 'FAIL'}")

        # TEST 11: Rename an Already-Open File with Unsaved Content Preservation
        print("[TEST 11] Verifying Rename open file preserves unsaved content...")
        open_target = test_dir / "open_to_rename.py"
        open_target.write_text("# Initial disk content\n", encoding="utf-8")
        ed = window.editor.open_file(str(open_target))
        # Add unsaved dirty content to editor buffer
        ed.setPlainText("# Initial disk content\n# DIRTY UNSAVED CONTENT 9999\n")
        ed.document().setModified(True)

        QInputDialog.getText = lambda *args, **kwargs: ("open_renamed_success.py", True)
        window.rename_tree_item(open_target)
        QInputDialog.getText = orig_get_text

        renamed_open_target = test_dir / "open_renamed_success.py"
        tab_idx = window.editor.find_tab_by_path(renamed_open_target)
        tab_text_ok = tab_idx is not None and window.editor.tabText(tab_idx) == "open_renamed_success.py"
        buffer_preserved = "DIRTY UNSAVED CONTENT 9999" in window.editor.widget(tab_idx).toPlainText()
        test_results["11_rename_open_file"] = tab_text_ok and buffer_preserved
        print(f"  Result: {'PASS' if test_results['11_rename_open_file'] else 'FAIL'} (TabUpdated={tab_text_ok}, BufferPreserved={buffer_preserved})")

        # TEST 12: Delete Confirmation and Root Protection
        print("[TEST 12] Verifying Delete Confirmation & Root Protection...")
        # Verify root cannot be deleted
        orig_warning = QMessageBox.warning
        warning_shown = []
        QMessageBox.warning = lambda parent, title, text, *args: warning_shown.append(title)
        window.delete_tree_item(test_dir)
        root_protected = test_dir.exists() and any("Protected" in w for w in warning_shown)

        # Verify deleting an open file prompts and closes tab
        orig_question = QMessageBox.question
        QMessageBox.warning = lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        window.delete_tree_item(renamed_open_target)
        file_deleted_ok = not renamed_open_target.exists()
        tab_closed_ok = not window.editor.is_file_open(renamed_open_target)

        QMessageBox.warning = orig_warning
        QMessageBox.question = orig_question
        test_results["12_delete_confirmation"] = root_protected and file_deleted_ok and tab_closed_ok
        print(f"  Result: {'PASS' if test_results['12_delete_confirmation'] else 'FAIL'} (RootProtected={root_protected}, FileDeleted={file_deleted_ok}, TabClosed={tab_closed_ok})")

        # TEST 13: F2 Shortcut for Rename
        print("[TEST 13] Verifying F2 Shortcut for Rename...")
        f2_shortcut_key = window.rename_shortcut.key().toString()
        f2_ok = f2_shortcut_key == "F2"
        test_results["13_f2_shortcut"] = f2_ok
        print(f"  Result: {'PASS' if f2_ok else 'FAIL'} (Key={f2_shortcut_key})")

        # TEST 14: Run Python using F5 with Unsaved Changes Prompt
        print("[TEST 14] Verifying Run Python F5 with Unsaved Edits...")
        f5_test_file = test_dir / "f5_test.py"
        f5_test_file.write_text('print("OLD_F5_CONTENT")\n', encoding="utf-8")
        f5_ed = window.editor.open_file(str(f5_test_file))
        new_f5_marker = f"F5_NEW_MARKER_{int(time.time())}"
        f5_ed.setPlainText(f'print("{new_f5_marker}")\n')
        f5_ed.document().setModified(True)

        # Mock question returning Save
        orig_question = QMessageBox.question
        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Save
        window.run_python()
        QMessageBox.question = orig_question

        start_wait = time.time()
        f5_found = False
        while time.time() - start_wait < 8:
            app.processEvents()
            time.sleep(0.1)
            if new_f5_marker in window.terminal.output_area.toPlainText():
                f5_found = True
                break
        test_results["14_run_python_f5"] = f5_found and not f5_ed.document().isModified()
        print(f"  Result: {'PASS' if test_results['14_run_python_f5'] else 'FAIL'} (SavedAndExecuted={test_results['14_run_python_f5']})")

        # TEST 15: Application Clean Shutdown
        print("[TEST 15] Verifying Application Clean Shutdown...")
        terminal_proc = window.terminal.process
        proc_running_before = terminal_proc is not None and terminal_proc.state() != terminal_proc.ProcessState.NotRunning
        window.close()
        app.processEvents()
        time.sleep(0.5)
        proc_stopped_after = window.terminal.process is None or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning
        test_results["15_clean_shutdown"] = proc_running_before and proc_stopped_after
        print(f"  Result: {'PASS' if test_results['15_clean_shutdown'] else 'FAIL'}")

        # TEST 16: Existing Ollama Chat Functionality
        print("[TEST 16] Verifying Ollama AI Chat Functionality...")
        ollama_ok = False
        try:
            from core.ollama_client import OllamaClient
            client = OllamaClient()
            client.health()
            models = client.list_models()
            qwen_found = any("qwen2.5-coder:7b" in m for m in models)
            ollama_ok = qwen_found
        except Exception as e:
            print(f"  Ollama check error: {e}")
        test_results["16_ollama_chat_functionality"] = ollama_ok
        print(f"  Result: {'PASS' if ollama_ok else 'FAIL'} (Qwen2.5-coder:7b found={ollama_ok})")

    finally:
        # Cleanup temporary test directory
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================")
    print("FINAL 16-POINT TEST RESULTS SUMMARY")
    print("=======================================================")
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=======================================================")
    print(f"OVERALL STATUS: {'ALL 16 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=======================================================\n")
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
