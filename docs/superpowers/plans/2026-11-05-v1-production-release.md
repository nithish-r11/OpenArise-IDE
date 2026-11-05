# OpenArise IDE V1.0 Production Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the complete codebase and test suites, build production-grade Windows x64 portable executable and Inno Setup installer, verify runtime performance with Ollama and offline, and produce a verified release package with checksums.

**Architecture:** PyInstaller compiles PyQt6, QScintilla, and core libraries into a single-file portable Windows x64 executable embedding branding assets. Inno Setup wraps the executable, license, and assets into a signed-style Windows setup wizard supporting installation to `%LOCALAPPDATA%\Programs\OpenArise IDE` (or Program Files), desktop/start-menu shortcuts, and a clean uninstaller.

**Tech Stack:** Python 3.13, PyQt6, QScintilla, PyInstaller 6.x, Inno Setup 6, PowerShell.

**Spec:** User request: "OpenArise IDE – V1.0 Production Release Build" (2026-11-05).

## Global Constraints
- Application Name: `OpenArise IDE`.
- Version: `1.0.0`.
- Icon: `assets/branding/openarise.ico` strictly on Title bar, Taskbar, and Executable / Installer icon.
- Exclude development files, tests, benchmarks, virtual environments, caches (`__pycache__`), and git directories.
- Do NOT bundle Ollama or model weights. Document them as prerequisites.
- Keep local-first; do not publish or upload anything online.
- No UI redesign or feature removals; maintain 4-button minimal toolbar and top menu order.

## Review Focus
1. Complete test suite coverage: audit all historical tests (phases 3-9, features, etc.) against recent UI simplifications (e.g. 4-button toolbar, no splash screen).
2. Packaging assets: verify PyInstaller extracts branding icons at runtime in `sys._MEIPASS`.
3. Packaged execution: verify QProcess terminal works properly in the frozen environment without relying on virtualenv paths.
4. Offline resilience: verify IDE launches gracefully and displays clear guidance when Ollama daemon is stopped.
5. Inno Setup verification: verify setup installs cleanly, creates valid shortcuts, and uninstalls cleanly without leaving orphan files.

---

### Task 1: Complete Test Suite Audit & Regression Fixes
Run all test files in `tests/`. Identify any tests from earlier phases that assert superseded states (such as splash screen existence or old 8-button toolbar), update them to match the approved V1.0 architecture, and verify 100% of discoverable tests pass.

### Task 2: PyInstaller Spec & Inno Setup Script Setup
Audit `OpenAriseIDE.spec` and `build_exe.py`. Ensure hidden imports (PyQt6.QtCore, PyQt6.QtGui, PyQt6.QtWidgets, PyQt6.Qsci, etc.) and asset paths are fully dynamic and correct. Write `installer.iss` for Inno Setup.

### Task 3: Inno Setup Installation & Build Execution
Install Inno Setup using `winget`. Execute PyInstaller build to produce `dist/OpenAriseIDE.exe`. Compile `installer.iss` with `iscc` to produce `dist/OpenAriseIDE-Setup-1.0.0.exe`.

### Task 4: Packaged Binary & Installer Verification
Launch `dist/OpenAriseIDE.exe`. Verify branding, title bar, Ollama connectivity, agent file creation, diff review, and terminal output. Test offline behavior when Ollama is stopped. Run the installer and verify installation and uninstallation.

### Task 5: Release Package Assembly & Final Documentation
Assemble `release/v1.0.0/` containing portable executable, installer, README, Ollama instructions, troubleshooting, release notes, and SHA-256 checksums. Produce final report.

