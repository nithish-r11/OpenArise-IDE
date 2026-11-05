# OpenArise IDE – AI Agent V1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade OpenArise IDE's AI Agent to a fast, reliable, Cursor-quality autonomous coding engine capable of understanding codebases, multi-file generation/editing, autonomous build/run/test/debugging, and delivering working websites and applications with optimal performance on local `qwen2.5-coder:7b`.

**Architecture:** 
1. `core/context_manager.py`: Reusable workspace profiling, framework detection, compact file tree, and symbol/API indexing.
2. `core/agent_tools.py`: New canonical tools (`write_files`, `edit_file`, `search_symbols`) with strict containment and validation.
3. `core/agent_orchestrator.py`: Streaming token generation, compact prompt construction, adaptive single/multi-file execution, autonomous build/run/test engine, and self-healing debugger.
4. `ui/agent_panel.py`: Live streaming progress feedback, multi-file diff summary, and actionable run/view instructions.

**Tech Stack:** Python 3.13, PyQt6, Ollama API (`qwen2.5-coder:7b`), Subprocess/QProcess, Requests.

**Spec:** User specification for OpenArise IDE AI Agent V1.0.

---

## Global Constraints

- Optimize strictly for local-first execution with Ollama and `qwen2.5-coder:7b`.
- Maintain full compatibility with non-Git and Git workspaces.
- Preserve existing minimal toolbar (4 buttons) and menu bar hierarchy.
- Zero visual redesign or layout jitter in `ui/agent_panel.py`.
- Strict path traversal protection: reject any path outside project root.
- Strict code safety: never overwrite working code without diff review and backup.
- Do NOT build the EXE yet.

---

## Review Focus

1. **Context token budget:** Ensure project summary fits within 300-600 tokens so prompt evaluation latency remains sub-second.
2. **Deterministic tool responses:** Ensure model output conforms to JSON schemas without hallucinated tool names or argument conflicts.
3. **Multi-file atomicity:** Batch file changes (`write_files`) must be tracked in `AgentJournal` as individual records for granular diff review.
4. **Autonomous debugging termination:** Ensure self-healing debug cycle terminates cleanly after maximum 2 retries to prevent infinite loops.
5. **Terminal process isolation:** Ensure background test/server processes do not leak or block the UI thread.

---

## Tasks

### Task 1: Reusable Codebase Understanding & Context Engine
**Files:**
- Modify: `core/context_manager.py`
- Test: `tests/test_agent_v1_cursor_upgrade.py`

- [ ] Add `ProjectProfile` dataclass in `core/context_manager.py` (framework, dependencies, entrypoints, file tree).
- [ ] Implement fast AST/regex symbol extraction (`extract_symbols`) for Python and JavaScript/TypeScript.
- [ ] Implement `get_workspace_summary(max_tokens=600)` generating a compact, structured representation.
- [ ] Implement in-memory profile caching with incremental invalidation on file changes.
- [ ] Add unit tests for workspace profiling and symbol search.

### Task 2: Cursor-Like Multi-File Tools & Precise Editing
**Files:**
- Modify: `core/agent_tools.py`
- Modify: `core/agent_models.py`
- Test: `tests/test_agent_v1_cursor_upgrade.py`

- [ ] Add `write_files(files: list[dict])` tool supporting batch file creation/modification in a single turn.
- [ ] Add `edit_file(path: str, target: str, replacement: str)` tool for surgical code replacements preserving file structure.
- [ ] Add `search_symbols(query: str)` tool querying the workspace symbol index.
- [ ] Update `normalize_tool_args` and `AgentToolRegistry` to register and validate new canonical tools and aliases.
- [ ] Add unit tests for `write_files`, `edit_file`, and symbol search.

### Task 3: High-Performance Streaming & Prompt Optimization
**Files:**
- Modify: `core/agent_orchestrator.py`
- Modify: `core/ollama_client.py`
- Test: `tests/test_agent_v1_cursor_upgrade.py`

- [ ] Implement streaming chat queries in `_query_ollama` using `stream: True` with live token progress callback.
- [ ] Configure optimal generation parameters for `qwen2.5-coder:7b` (`temperature: 0.1`, `num_predict: 4096`).
- [ ] Implement compact prompt construction using `get_workspace_summary()` instead of raw codebase dumping.
- [ ] Implement adaptive step advancement: auto-complete step when all required files are generated without requiring separate model turn for `step_complete`.
- [ ] Add unit tests verifying prompt compactness and streaming callback reception.

### Task 4: Autonomous Build, Run, Test & Self-Healing Debugger
**Files:**
- Modify: `core/agent_orchestrator.py`
- Test: `tests/test_agent_v1_cursor_upgrade.py`

- [ ] Implement project runnable detection (`detect_project_runnable`): identify web servers, python scripts, test suites.
- [ ] Implement post-application build/run/test verification in Phase 5 of `AgentWorker.run()`.
- [ ] Implement autonomous self-healing debugger (`_run_self_healing_debug_cycle`): diagnose error tracebacks, call model for corrective patch, propose diff, and re-run.
- [ ] Generate actionable launch instructions for the user (e.g. browser URL, terminal command).
- [ ] Add unit tests simulating build failure and self-healing recovery.

### Task 5: UI Live Feedback & Actionable Delivery
**Files:**
- Modify: `ui/agent_panel.py`
- Test: `tests/test_agent_ui_layout_stability.py`

- [ ] Add streaming token progress display to status label and activity timeline during generation.
- [ ] Display rich multi-file change summaries on completion.
- [ ] Verify UI layout stability remains 100% stable during streaming updates.

### Task 6: Automated Test Suite & Regression Verification
**Files:**
- Create: `tests/test_agent_v1_cursor_upgrade.py`
- Run: `tests/test_agent_terminal_bugfixes.py`
- Run: `tests/test_critical_fixes.py`
- Run: `tests/verify_minimal_toolbar.py`
- Run: `tests/test_startup_direct_launch.py`

- [ ] Run full automated test suite and ensure all tests pass with code 0.
- [ ] Verify clean Python bytecode compilation (`python -m compileall`).

### Task 7: Mandatory Real-World Ollama Benchmark Suite
**Files:**
- Create: `tests/benchmarks/benchmark_ollama_v1.py`

- [ ] Execute Test A: Website Creation (Task Management HTML/CSS/JS/CRUD/LocalStorage).
- [ ] Execute Test B: Existing Project Modification (Feature addition preserving code).
- [ ] Execute Test C: Debugging (Controlled error identification, fix & verify).
- [ ] Execute Test D: Full-Stack Application (Frontend, backend, API integration).
- [ ] Execute Test E: Terminal & Runtime (Execution via terminal, server startup, HTTP verification).
- [ ] Record exact real-world measurements and generate completion report.

