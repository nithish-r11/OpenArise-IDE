# Phase 6: OpenArise AI Agent Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a local-first autonomous AI Agent Mode for OpenArise IDE supporting multi-step planning, bounded context retrieval, controlled tool execution, multi-file code editing with diff previews and user approval gates, change journal with full rollback, test-driven debugging, Git integration, and a premium dark UI.

**Architecture:** 
- `core/agent_models.py`: Data models for plans, steps, tool calls, change records, and journal.
- `core/agent_tools.py`: Safe tool registry with containment validation and execution guards.
- `core/agent_orchestrator.py`: Autonomous agent execution loop on QThread with structured JSON protocol, retry/budget limits, and signal-driven approval gates.
- `ui/agent_diff_dialog.py`: Multi-file visual diff inspection and approval dialog.
- `ui/agent_panel.py`: Comprehensive UI for task planning, progress tracking, approval cards, and rollbacks.
- `ui/chat_agent_container.py`: Seamless Mode Switcher between Chat Mode and Agent Mode (`Ctrl+Shift+A`).
- `ui/main_window.py`: IDE integration, shortcuts, command palette, and safe shutdown.
- `tests/test_phase6.py`: 19-point automated test suite validating all safety and functional requirements.

**Tech Stack:** Python 3.13, PyQt6, Ollama API, Pathlib, Git, Subprocess.

**Spec:** OpenArise IDE Phase 6 Specifications.

---

## Global Constraints
- Preserve all existing Phase 1–5 features and 60/60 passing tests.
- Local-first: local Ollama by default (no external cloud required).
- Security: never execute arbitrary shell commands without explicit user approval.
- Containment: enforce strict project-root containment on all file operations; reject any path traversal attempts.
- Safeguards: never silently overwrite project files; create automatic backups before modifying existing files.
- Non-destructive: user approval required for plan, file changes (diff preview), and terminal commands.
- Robustness: step budgets and retry limits to prevent infinite loops.
- DO NOT BUILD FINAL EXE YET.

---

## Review Focus
1. Path traversal attempts (`../`, absolute paths, symlink tricks) must be rejected with `ValueError` and never touch files outside project root.
2. Unapproved file modifications must never reach disk; only accepted files in the diff dialog are written.
3. Rollback must restore modified files to exact pre-task content and delete created files without leaving orphaned artifacts.
4. Terminal commands (`execute_approved_command`, `run_tests`) must never run without explicit user confirmation.
5. Malformed or non-JSON model output must be caught gracefully, retried with corrective prompts up to the limit, and not crash the agent or IDE.

---

## Task Decomposition

### Task 1: Agent Models and Change Journal (`core/agent_models.py`)
- Define `AgentTaskState`, `AgentPlanStep`, `AgentPlan`, `AgentToolCall`, `FileChangeRecord`.
- Implement `AgentJournal`:
  - `backup_file(path)`
  - `record_change(rel_path, change_type, old_content, new_content)`
  - `apply_changes(records_to_apply)`
  - `rollback()`
  - `get_summary()`

### Task 2: Agent Tools Registry & Containment Guard (`core/agent_tools.py`)
- Implement `AgentToolRegistry`:
  - Containment check helper `resolve_contained_path(project_root, rel_path)`
  - `read_file(path)`
  - `write_file(path, content)`
  - `search_files(query, pattern)`
  - `list_directory(path)`
  - `create_directory(path)`
  - `run_tests(command)` (flags `requires_approval=True`)
  - `inspect_git_status()`
  - `inspect_git_diff()`
  - `execute_approved_command(command)` (flags `requires_approval=True`)
- Tool JSON schema validation and sanitization.

### Task 3: Agent Orchestrator & Execution Loop (`core/agent_orchestrator.py`)
- Implement `AgentWorker(QThread)`:
  - Structured prompt protocols for planning and tool execution.
  - Robust JSON parser with fallback extraction from markdown fences.
  - Phase 1: Pre-flight Git check & project context gathering.
  - Phase 2: Plan generation & user approval pause.
  - Phase 3: Step-by-step tool loop with bounded steps (max 15), retry limits (max 3), and context updates.
  - Phase 4: File modification diff aggregation & approval pause.
  - Phase 5: Execution of approved changes, test verification, and post-completion summary with Git diff.
  - Thread cancellation and interruption handling.

### Task 4: Multi-File Diff Review Dialog (`ui/agent_diff_dialog.py`)
- Implement `AgentDiffDialog`:
  - File list with change badges (`CREATE`, `MODIFY`, `DELETE`).
  - Unified/side-by-side HTML diff viewer for selected file.
  - Checkboxes or per-file "Accept" / "Reject" toggles, plus "Accept All" and "Reject All".
  - Clear file diff stats (+ additions, - deletions).

### Task 5: Agent Mode UI Panel & Mode Switcher (`ui/agent_panel.py`, `ui/chat_agent_container.py`)
- Implement `AgentPanel`:
  - Goal input box, model selector, Start Task, Cancel, Rollback, and Retry buttons.
  - Plan checklist widget with live step status indicators.
  - Approval cards:
    - Plan Approval Card (Approve Plan / Reject)
    - Command Approval Card (Approve Command / Reject)
    - File Review Card (Launch Diff Review)
  - Activity log / timeline showing inspected files, tool executions, and findings.
  - Final summary card with Git diff suggestion.
- Implement `ChatAgentContainer`:
  - Segmented mode switcher `[💬 Chat Mode] [🤖 Agent Mode]`.
  - QStackedWidget hosting both `ChatPanel` and `AgentPanel`.
  - Backward compatibility forwarding methods so existing callers of `self.chat` work seamlessly.

### Task 6: Main IDE & Command Palette Integration (`ui/main_window.py`)
- Mount `ChatAgentContainer` into the right sidebar of `MainWindow`.
- Connect `Ctrl+Shift+A` shortcut to switch directly to Agent Mode.
- Register Command Palette actions:
  - `view.chat_mode`: Switch to Chat Mode
  - `view.agent_mode`: Switch to Agent Mode (`Ctrl+Shift+A`)
  - `agent.start_task`: Agent: Start New Task
  - `agent.cancel_task`: Agent: Cancel Running Task
  - `agent.rollback`: Agent: Rollback Last Task Changes
- Update `closeEvent` to cancel running agent tasks cleanly.

### Task 7: 19-Point Automated Test Suite (`tests/test_phase6.py`)
- Write comprehensive test suite covering all 19 required points in isolated temporary workspaces.
- Execute and verify 19/19 tests pass with exit code 0.

### Task 8: Full Regression & Bytecode Verification
- Run Phase 5 (`test_phase5.py`), Phase 4 (`test_phase4.py`), Phase 3 (`test_phase3.py`), and Phase 2 (`test_features.py`).
- Run `python -m compileall main.py core ui extensions tests`.
- Deliver final Phase 6 report.

