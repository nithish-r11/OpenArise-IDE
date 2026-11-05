# OpenArise IDE - Integrated Terminal, File Management & Run Python Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a bottom-docked persistent integrated terminal (`QProcess`), complete Project Explorer context menu with tab synchronization, one-click Python execution (F5) using project virtual environments, and toolbar UI refinements while preserving dark theme and Ollama AI workflows.

**Architecture:**
- Create `ui/terminal_widget.py` encapsulating `IntegratedTerminalWidget(QWidget)` with `QProcess` running persistent PowerShell (or CMD fallback), separate scrollable console output, dedicated bottom command input with Up/Down history, and New/Clear/Stop buttons.
- Update `ui/main_window.py` to embed the terminal in a `QDockWidget` at `BottomDockWidgetArea`, wire `View > Terminal` and `Ctrl+\`` shortcuts, remove duplicate logo/text from the toolbar, and add "Run Python" (`F5`).
- Upgrade `QTreeView` in `ui/main_window.py` with custom context menu (`Open`, `New File`, `New Folder`, `Rename` [F2], `Delete`, `Copy Path`), filename validation, delete safety checks, root protection, and two-way synchronization with `EditorTabs`.
- Wire `F5` / `Run Python` to check for unsaved edits, resolve `.venv` Python interpreter, and dispatch execution asynchronously to the terminal.

**Tech Stack:** Python 3.13, PyQt6 (`QtWidgets`, `QtCore`, `QtGui`), `QProcess`, `QDockWidget`, `QFileSystemModel`, `QTreeView`.

## Global Constraints
- Must use `QProcess` and Qt signals for terminal execution; never block the GUI thread.
- Must support Windows PowerShell with CMD fallback and maintain persistent working directory.
- Must preserve all existing features: Project Explorer, Editor tabs, Ollama AI chat with streaming, Ctrl+K inline edit, Test Generator, PyInstaller compatibility.
- Remove duplicate logo and "OpenArise" text from the main toolbar only; keep splash screen logo, application icon, and About dialog branding.
- Do not build final EXE yet.

## Review Focus
1. Command execution with special characters, quotes, or paths with spaces in the terminal.
2. Terminal input history bounds (Up/Down arrow pressing at ends of history without crashing).
3. Renaming an open file or folder with open files updates editor tab titles and file paths without losing unsaved changes.
4. Deletion safety: protecting project root from deletion and prompting confirmation before deleting open files.
5. Clean shutdown: ensuring `QProcess` and all worker threads terminate cleanly during `closeEvent`.

---

### Task 1: Terminal Widget (`ui/terminal_widget.py`)
- Create `TerminalInputLineEdit` supporting command history with Up/Down arrows and Enter execution.
- Create `IntegratedTerminalWidget` with `QPlainTextEdit` output area, input bar, New Terminal / Clear / Stop buttons, and working directory display.
- Manage persistent `powershell.exe` (or `cmd.exe`) process with `QProcess`, connecting `readyReadStandardOutput`, `readyReadStandardError`, and `errorOccurred`.
- Provide `execute_command(cmd: str)`, `clear_terminal()`, `stop_process()`, `restart_terminal()`, and `set_working_directory(path: Path)`.

### Task 2: Terminal Integration in Main Window & UI Layout (`ui/main_window.py`)
- Embed `IntegratedTerminalWidget` inside a bottom `QDockWidget("Terminal", self)`.
- Add `View > Terminal` menu action and `Ctrl+\`` keyboard shortcut.
- Remove duplicate logo and "OpenArise" text from the main toolbar.
- Connect project folder changes to `terminal.set_working_directory(project_root)`.
- Ensure clean shutdown of `terminal` in `MainWindow.closeEvent`.

### Task 3: Project Explorer Context Menu & Tab Synchronization (`ui/main_window.py` & `ui/editor_widget.py`)
- Enable `customContextMenuRequested` on `self.tree` with Open, New File, New Folder, Rename (F2), Delete, Copy Path.
- Implement input dialogs with filename validation (rejecting illegal Windows characters `\/:*?"<>|`).
- Implement file/folder renaming with bidirectional sync: update `EditorTabs` titles and `file_path` properties while preserving unsaved editor buffers.
- Implement deletion with safety checks: protect `self.project_root` from deletion, warn if file is open in editor, and remove deleted tabs.
- Install `F2` shortcut for renaming selected tree items.

### Task 4: Run Python Feature (F5 & Toolbar Button)
- Add "Run Python" button to the main toolbar and `F5` shortcut.
- Implement `run_python()`:
  - Check active editor; prompt to save if modified.
  - Detect virtual environment interpreter (`project_root / ".venv" / "Scripts" / "python.exe"`, or fallback to `sys.executable`).
  - Show and focus terminal dock.
  - Send execution command to the persistent terminal session.

### Task 5: Comprehensive Automated Testing & Verification
- Test all 16 required verification points using automated test script in `.venv`:
  1. Terminal open/close toggle (`Ctrl+\`` and `View > Terminal`)
  2. PowerShell command execution
  3. Python file execution via F5
  4. stdout and stderr output capture
  5. Persistent working directory maintenance
  6. Stop running process
  7. GUI responsiveness during commands
  8. Explorer context menu actions
  9. New File and New Folder creation
  10. Rename file and folder
  11. Rename open file with content preservation
  12. Delete confirmation and root protection
  13. F2 rename shortcut
  14. F5 unsaved changes prompt & run
  15. Clean application shutdown
  16. Ollama AI chat streaming preservation
- Run `python -m compileall main.py core ui`
- Document results and known limitations.

