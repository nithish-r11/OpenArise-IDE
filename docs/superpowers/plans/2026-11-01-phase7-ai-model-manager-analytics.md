# Phase 7: OpenArise AI Model Manager and Usage Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a comprehensive AI Model Manager, Ollama response metrics collector, local SQLite usage database, system resource monitor, and professional Usage Analytics Dashboard for OpenArise IDE.

**Architecture:**
- `core/analytics_db.py`: SQLite database tracking exact metrics from Ollama final chunks with daily, weekly, monthly, per-model aggregations, and CSV export.
- `core/system_monitor.py`: Hardware monitor measuring RAM via Win32 `GlobalMemoryStatusEx`, CPU, GPU VRAM via `nvidia-smi`, and Ollama model VRAM via `/api/ps`.
- `core/ollama_client.py`: Enhanced client supporting `/api/tags` extended details, `/api/delete`, `/api/ps`, `/api/show`, and emitting authoritative `metrics_collected` signal from streaming and generate workers.
- `ui/analytics_dashboard.py`: Full-featured analytics dialog with summary cards, time aggregation, per-model breakdown, request history, CSV export, and clear history.
- `ui/model_manager_tab.py`: Enhanced Settings tab ("AI & Models") with model discovery, sizes/families, download with progress, remove with confirmation, default model selector, resource recommendations, and connection health status.
- `ui/settings_dialog.py`: Integrated "AI & Models" tab replacing basic model dropdown while preserving all existing settings.
- `ui/main_window.py`: Registered `Ctrl+Shift+U`, Command Palette actions, and connected metrics collection across all AI subsystems (Chat, Inline, Tests, Agent, Git).
- `tests/test_phase7.py`: Dedicated 15-point automated integration test suite validating model management, metrics collection, database persistence, aggregations, CSV export, and regressions.

**Tech Stack:** Python 3.13, PyQt6, SQLite3, Ollama REST API, ctypes (Windows Win32 API), subprocess.

**Spec:** OpenArise IDE Phase 7 Specifications.

---

## Global Constraints
- Preserve all existing Phase 1–6 features and 79/79 passing integration tests.
- Local-first: 100% local SQLite storage (`~/.openarise/analytics.db`); no network transmission of usage data.
- Authoritative metrics: Do NOT invent or estimate actual token counts when authoritative metrics are unavailable.
- Single Settings System: Integrate directly into the existing `SettingsManager` and `SettingsDialog`.
- Clean Teardown: Safely cancel and wait for any active Ollama threads before process exit.
- DO NOT BUILD FINAL EXE YET.

---

## Review Focus
1. Authoritative metrics extraction: Only parse `prompt_eval_count`, `eval_count`, `total_duration`, etc., when present in the final chunk (`done: true`); do not fabricate token counts.
2. Tokens per second formula: `eval_count / (eval_duration_seconds)` when both are valid and `> 0`.
3. Model deletion confirmation: Must require explicit user confirmation before issuing `/api/delete`.
4. Path & Database safety: Database connection and CSV export must handle locked files or missing directories safely.
5. Resource metrics: Clearly distinguish measured data from unavailable metrics.

---

## Task Decomposition

### Task 1: Analytics Database (`core/analytics_db.py`)
- SQLite schema for `usage_events`.
- `ModelUsageMetrics` dataclass with operation categories: Chat, Inline AI Edit, Test Generation, AI Agent, Git AI Assistant.
- Queries for summary stats, daily/weekly/monthly aggregation, per-model stats, history pagination.
- CSV exporter and history clear with confirmation.

### Task 2: System Resource Monitor (`core/system_monitor.py`)
- RAM measurement via `ctypes.windll.kernel32.GlobalMemoryStatusEx`.
- CPU measurement.
- GPU & VRAM detection via `nvidia-smi` parsing.
- Ollama model memory inspection via `/api/ps`.
- Resource-based model recommendation matrix.

### Task 3: Ollama Client Extensions & Metrics Capture (`core/ollama_client.py`)
- Add endpoints: `delete_model`, `list_models_detailed`, `show_model`, `list_running_models`.
- Enhance `OllamaStreamWorker` and `OllamaGenerateWorker` to capture final chunk metrics and emit `metrics_collected(dict)`.

### Task 4: Analytics Dashboard UI (`ui/analytics_dashboard.py`)
- Summary metric cards (Total Requests, Tokens, Speed, Avg Duration).
- Aggregation views (Daily, Weekly, Monthly, Model breakdown).
- Request history table with status indicators.
- CSV export button & Clear History button.

### Task 5: AI & Models Settings Integration (`ui/model_manager_tab.py`, `ui/settings_dialog.py`)
- Model manager UI: Installed models table (name, size, family, parameter size).
- Default model picker & persistence via `SettingsManager`.
- Model puller with progress bar.
- Model delete with confirmation dialog.
- Connection health indicator.
- Resource recommendation card.
- Link to open Analytics Dashboard.

### Task 6: Main IDE Integration & Subsystem Wiring (`ui/main_window.py`)
- Register `Ctrl+Shift+U` shortcut and Command Palette actions (`view.ai_analytics`, `ai.manage_models`).
- Connect chat, inline edit, test generator, and agent worker metrics to `AnalyticsDatabase`.
- Menu items in `&View` and `&AI`.

### Task 7: 15-Point Automated Test Suite (`tests/test_phase7.py`)
- Implement 15 test points in an isolated temporary environment.
- Verify 15/15 tests pass with exit code 0.

### Task 8: Full Regression & Bytecode Verification
- Run Phase 6 (`test_phase6.py`), Phase 5 (`test_phase5.py`), Phase 4 (`test_phase4.py`), Phase 3 (`test_phase3.py`), and Phase 2 (`test_features.py`).
- Run `python -m compileall main.py core ui extensions tests`.
- Deliver final Phase 7 report.

