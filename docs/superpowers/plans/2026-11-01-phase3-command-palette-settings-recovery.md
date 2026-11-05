# Phase 3: Command Palette, Personalization Settings, Auto Save & Crash Recovery Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 3 for OpenArise IDE comprising a borderless floating Command Palette (top-center, `Ctrl+Shift+P`), a centralized Command Registry, a dedicated Personalization Settings Dialog backed by persistent JSON configuration with 5 themes, a reliable mtime-aware Auto Save engine, and an automated Crash Recovery system.

**Architecture:**
- `core/commands.py`: Implements `Command` and `CommandRegistry` maintaining actions, shortcut labels, and search/filtering.
- `ui/command_palette.py`: Implements borderless floating top-center palette with search input, instant filtering, Up/Down navigation, Enter execution, and Escape closing.
- `core/settings_manager.py` & `ui/themes.py`: Implements JSON configuration persistence in `~/.openarise/settings.json`, validation, defaults, and 5 complete themes (OpenArise Dark, Dracula, Monokai, Nord, Light).
- `ui/settings_dialog.py`: Personalization dialog for Editor, Terminal, AI, Themes, Startup, and Auto Save with Reset to Defaults and immediate live application.
- `core/recovery_manager.py`: Automated crash recovery tracking `clean_exit`, periodic buffer snapshots, cursor positions, and prompt dialog upon unclean restart.
- Auto Save engine in `MainWindow` with `QTimer` honoring disk mtime to prevent silent overwrites of external modifications.

**Tech Stack:** Python 3.13, PyQt6 (`QtWidgets`, `QtCore`, `QtGui`), `QTimer`, `QProcess`, `QPlainTextEdit`, `pathlib`, `json`.

## Global Constraints
- Must maintain dark theme default and existing branding (splash screen, window icon, About dialog).
- Never block the GUI thread; use `QTimer` for scheduling autosave and recovery snapshots.
- Must preserve all working features: Project Explorer, Editor tabs, Terminal, Run Python F5, Ollama chat with streaming, Ctrl+K inline edit, Test Generator, and PyInstaller compatibility.
- Do not build final EXE yet.

## Review Focus
1. Command Palette focus, keyboard navigation, and event filtering without losing focus or crashing on empty results.
2. Conflict handling during Auto Save: files modified externally must not be silently overwritten.
3. Live theme switching cleanly updates stylesheets across all open widgets, dialogs, and editors without UI glitches.
4. Crash recovery restores exact buffer contents, file paths, and cursor positions without overwriting original disk files.
5. Clean application shutdown properly marks `clean_exit=True` and releases all processes and timer resources.

---

### Task 1: Command Registry (`core/commands.py`)
- Define `Command` dataclass (`id`, `title`, `category`, `shortcut`, `handler`, `description`).
- Implement `CommandRegistry` with `register()`, `unregister()`, `get()`, `all_commands()`, and substring/fuzzy `search(query)`.
- Export registry instance in `core/__init__.py`.

### Task 2: Floating Command Palette UI (`ui/command_palette.py`)
- Create `CommandPalette(QDialog)` with frameless window hint, translucent dark styling, and top-center positioning over `MainWindow`.
- Embed search input line edit with search icon and placeholder.
- Embed list widget displaying matching commands with title and shortcut badge.
- Implement live typing filter, Up/Down arrow selection, Enter execution, and Escape dismissal.

### Task 3: Settings Manager & Theme System (`core/settings_manager.py` & `ui/themes.py`)
- Implement `SettingsManager` saving/loading `~/.openarise/settings.json` with schema validation and reset to defaults.
- Implement `ui/themes.py` providing stylesheets for `OpenArise Dark`, `Dracula`, `Monokai`, `Nord`, and `Light`.
- Provide live theme and editor setting applicator for `MainWindow` and `EditorTabs`.

### Task 4: Personalization Settings Dialog (`ui/settings_dialog.py`)
- Create `SettingsDialog` with tabs/sections for Editor, Terminal, AI, Themes, Startup, and Auto Save.
- Bind controls to `SettingsManager` values with live preview / immediate application and "Reset to Defaults".

### Task 5: Auto Save Engine (`ui/main_window.py` & `ui/editor_widget.py`)
- Track `disk_mtime` in `EditorTabs` when loading and saving files.
- Wire `QTimer` in `MainWindow` for configurable auto-save interval.
- Check mtime before saving to avoid overwriting external modifications.
- Update status bar with timestamp on successful auto-save.

### Task 6: Crash Recovery Manager (`core/recovery_manager.py` & `ui/recovery_dialog.py`)
- Implement `RecoveryManager` storing buffer snapshots, cursor positions, and `clean_exit` flag in `~/.openarise/recovery/`.
- Create `RecoveryDialog` prompting users to Restore or Discard recovered session upon unexpected restart.
- Wire periodic snapshot in `MainWindow` and clean exit cleanup in `closeEvent`.

### Task 7: Integrate Everything into `MainWindow` (`ui/main_window.py`)
- Register all 15 required commands in `CommandRegistry`.
- Wire `Ctrl+Shift+P` shortcut to open `CommandPalette`.
- Wire `Find in Files`, `Go to File`, `Toggle Explorer`, and `Save All` actions.
- Apply user settings on startup (theme, editor font, autosave, last project).
- Check recovery status on startup.

### Task 8: Comprehensive Automated Testing & Verification
- Test Command Palette shortcut, filtering, navigation, and execution of all 15 commands.
- Test Settings persistence, validation, reset, and live theme switching across all 5 themes.
- Test Auto Save with timer and external modification conflict prevention.
- Test Crash Recovery: simulate crash, verify snapshot, restore session, and discard session.
- Run `python -m compileall main.py core ui tests`.
- Run complete existing test suite and verify Ollama chat and terminal.

