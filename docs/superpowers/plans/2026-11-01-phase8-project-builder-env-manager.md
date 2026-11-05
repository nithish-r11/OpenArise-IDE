# Phase 8: Universal Project Builder & Development Environment Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 8 for OpenArise IDE: a multi-step Universal Project Builder wizard (Python & JS/TS templates), Development Environment Manager (detecting 16 tools, project `.venv` & interpreter management, Node package managers), Windows title-bar/taskbar branding enforcement, and deep IDE integration while preserving all features and tests from Phases 2–7.

**Architecture:** 
- `core/project_builder.py` & `core/templates/`: Pure offline project template definitions with parameter substitution, name/path validation, traversal security, and collision safeguards.
- `ui/new_project_wizard.py`: 6-step modal wizard dialog with Next/Back navigation, template preview tree, and creation progress.
- `core/env_manager.py`: Tool detection engine for 16 developer tools with timeout guards, virtual environment manager, and interpreter persistence.
- `ui/env_manager_dialog.py`: Dedicated dashboard for installed tools, project interpreter selection, and package manager workflows.
- `ui/main_window.py` & `main.py`: Title bar text-only enforcement via Win32 `WS_EX_DLGMODALFRAME` / `WM_SETICON` while preserving taskbar logo and splash screen; menu and command palette integration.
- `tests/test_phase8.py`: 21-point automated test suite with isolated mocking.

**Tech Stack:** PyQt6, Python 3.12+, Win32 ctypes (`user32`, `shell32`, `kernel32`), standard library (`subprocess`, `shutil`, `pathlib`, `json`).

**Spec:** User Request - Phase 8 Universal Project Builder & Development Environment Manager with Branding and Phase 2-7 Preservation.

## Global Constraints
- Do not build final EXE yet.
- Zero internet dependency for basic templates and tool detection.
- Never overwrite existing files silently.
- Never install packages or SDKs without explicit user approval.
- Window title must display "OpenArise IDE" with text only (no small icon in title bar).
- Windows taskbar must display the crisp OpenArise logo.
- Main toolbar must have zero logo icon and zero duplicate brand text.
- Splash screen and About dialog must retain original `openarise_logo.jpg`.
- Preserve all existing Phase 2–7 functionality and ensure all 94 previous regression tests continue to pass.

## Review Focus
1. Malicious or traversal project paths (e.g. `../../etc` or `C:\Windows`) must be rejected cleanly.
2. Target directory already containing files must abort project creation unless explicitly safe.
3. Uninstalled or missing tools (e.g. Flutter, Rust, CMake) must return clean `installed=False` without hanging or throwing exceptions.
4. Windows title-bar icon suppression must not hide the title text or crash on non-Windows/test environments.
5. F5 Run Python must prefer the selected project interpreter over global Python.

---

### Task 1: Mandatory OpenArise Branding Refinements
**Files:**
- Modify: `ui/main_window.py`
- Modify: `main.py`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Produces: `MainWindow._apply_windows_branding()`, `MainWindow.windowTitle() == "OpenArise IDE"`
- Consumes: `assets/branding/openarise_logo.jpg`, `assets/branding/openarise.ico`, Win32 API

- [ ] **Step 1: Write branding test cases in `tests/test_phase8.py`**
  Verify: Window title is "OpenArise IDE", main toolbar contains no logo/brand text, splash screen and about dialog retain logo, and title bar icon suppression helper succeeds.
- [ ] **Step 2: Run test to verify it fails**
  Run: `E:\OpenArise_IDE\OpenArise_IDE\.venv\Scripts\python.exe tests/test_phase8.py`
- [ ] **Step 3: Implement branding adjustments in `ui/main_window.py` and `main.py`**
  - Set `SetCurrentProcessExplicitAppUserModelID("OpenArise.IDE.App.1.0")` in `main.py`.
  - In `MainWindow`: clear window icon, apply `WS_EX_DLGMODALFRAME` style and `WM_SETICON(ICON_SMALL, 0)` on Windows hwnd.
  - Verify main toolbar has no logo icon and no brand label.
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Verify in actual Windows runtime**

---

### Task 2: Universal Project Builder Templates & Scaffolding Engine
**Files:**
- Create: `core/project_builder.py`
- Create: `core/templates/__init__.py`
- Create: `core/templates/python_app/`
- Create: `core/templates/python_venv/`
- Create: `core/templates/flask_app/`
- Create: `core/templates/fastapi_app/`
- Create: `core/templates/node_app/`
- Create: `core/templates/express_app/`
- Create: `core/templates/react_vite/`
- Create: `core/templates/ts_starter/`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Produces:
  - `ProjectTemplate(id, name, language, category, description, files)`
  - `ProjectBuilder.list_templates() -> list[ProjectTemplate]`
  - `ProjectBuilder.validate_project_name(name: str) -> tuple[bool, str]`
  - `ProjectBuilder.validate_destination(name: str, dest_dir: Path) -> tuple[bool, str, Path]`
  - `ProjectBuilder.preview_project(template_id: str, name: str) -> list[tuple[str, bool]]`
  - `ProjectBuilder.create_project(template_id: str, name: str, dest_dir: Path, init_git: bool, create_venv: bool) -> tuple[bool, str, Path]`

- [ ] **Step 1: Write template engine tests in `tests/test_phase8.py`**
  Verify discovery of all 8 templates, name validation, traversal protection, collision rejection, and file creation.
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `core/project_builder.py` and template files**
  Implement validation, template substitution, file generation, and optional git/venv initialization.
- [ ] **Step 4: Run test to verify it passes**

---

### Task 3: Development Environment Manager Engine
**Files:**
- Create: `core/env_manager.py`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Produces:
  - `ToolInfo(name, installed, version, path, category, doc_url)`
  - `EnvironmentManager.detect_all_tools(force_refresh=False) -> dict[str, ToolInfo]`
  - `EnvironmentManager.detect_tool(name: str) -> ToolInfo`
  - `EnvironmentManager.detect_python_interpreters() -> list[Path]`
  - `EnvironmentManager.get_project_interpreter(project_root: Path) -> Path`
  - `EnvironmentManager.set_project_interpreter(project_root: Path, interpreter: Path)`
  - `EnvironmentManager.create_virtualenv(target_dir: Path) -> tuple[bool, str]`
  - `EnvironmentManager.detect_package_manager(project_root: Path) -> str`

- [ ] **Step 1: Write environment manager tests in `tests/test_phase8.py`**
  Test detection of 16 tools, missing tool handling, interpreter selection, virtual environment creation, and package manager identification.
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `core/env_manager.py`**
  Implement safe process execution with timeouts, tool detection table, virtual environment helper, and persistent interpreter configuration.
- [ ] **Step 4: Run test to verify it passes**

---

### Task 4: New Project Multi-Step Wizard UI
**Files:**
- Create: `ui/new_project_wizard.py`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Produces: `NewProjectWizardDialog(parent=None)`
- Signals: `project_created(str)` (emits newly created project root path)

- [ ] **Step 1: Write wizard UI tests in `tests/test_phase8.py`**
  Verify dialog initialization, step navigation (Next/Back), form validation, preview tree, and cancel.
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `NewProjectWizardDialog` in `ui/new_project_wizard.py`**
  Implement 6 wizard steps using `QStackedWidget`, step indicator, Back/Next/Cancel navigation, and OpenArise Dark styling.
- [ ] **Step 4: Run test to verify it passes**

---

### Task 5: Environment Manager UI & Settings Tab Integration
**Files:**
- Create: `ui/env_manager_dialog.py`
- Modify: `ui/settings_dialog.py`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Produces:
  - `EnvironmentManagerDialog(env_manager, project_root, parent=None)`
  - `DevelopmentEnvironmentsTab(env_manager, project_root, parent=None)`
- Modifies: `SettingsDialog` to include Tab 6 ("Development Environments").

- [ ] **Step 1: Write UI tests for Environment Manager dialog and settings tab in `tests/test_phase8.py`**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `EnvironmentManagerDialog` and `DevelopmentEnvironmentsTab`**
  Implement installed tools table, interpreter selector, and integrate into `SettingsDialog`.
- [ ] **Step 4: Run test to verify it passes**

---

### Task 6: MainWindow Integration, Menu Wiring & F5 Python Execution
**Files:**
- Modify: `ui/main_window.py`
- Modify: `core/commands.py`
- Test: `tests/test_phase8.py`

**Interfaces:**
- Menus:
  - `File -> New Project…` (`Ctrl+Shift+N`)
  - `Tools -> Environment Manager…`
  - `Tools -> Select Python Interpreter…`
- Commands:
  - `file.new_project`
  - `tools.environment_manager`
  - `tools.select_interpreter`
- Execution:
  - `MainWindow.run_python` resolves interpreter through `EnvironmentManager.get_project_interpreter()`.

- [ ] **Step 1: Write integration tests for menu actions, commands, and interpreter binding in `tests/test_phase8.py`**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Wire `MainWindow` actions, command registry, and execution pipeline**
- [ ] **Step 4: Run test to verify it passes**

---

### Task 7: Comprehensive Verification & Full Regression Testing
**Files:**
- Run: `tests/test_phase8.py`
- Run: `tests/test_phase7.py`
- Run: `tests/test_phase6.py`
- Run: `tests/test_phase5.py`
- Run: `tests/test_phase4.py`
- Run: `tests/test_phase3.py`
- Run: `tests/test_features.py`
- Run: `python -m compileall main.py core ui extensions tests`

- [ ] **Step 1: Execute all 21+ Phase 8 tests**
- [ ] **Step 2: Execute all 94 prior regression tests**
- [ ] **Step 3: Run full bytecode compilation**
- [ ] **Step 4: Final deliverable report and task tracking update**

