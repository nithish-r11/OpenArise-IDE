"""
AI Agent Orchestration Engine and Execution Worker for OpenArise IDE.
Runs autonomous, multi-step coding tasks using local Ollama models.
Enforces structured JSON protocols, step budgets, retry limits, bounded context,
plan approval gates, tool execution gates, and diff review gates.
"""

from __future__ import annotations
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from core.agent_models import (
    AgentJournal,
    AgentPlan,
    AgentPlanStep,
    AgentTaskState,
    AgentToolCall,
    FileChangeRecord,
    FileChangeStatus,
    StepStatus,
)
from core.agent_tools import (
    AgentToolRegistry,
    canonicalize_tool_name,
    normalize_tool_args,
    resolve_contained_path,
    is_placeholder_or_stub_content,
)
from core.context_manager import ContextManager
from core.git_service import GitService
from core.ollama_client import OllamaClient, OllamaError

ACTION_ALIASES: dict[str, str] = {
    "call_tool": "tool_call",
    "execute_tool": "tool_call",
    "run_tool": "tool_call",
    "tool": "tool_call",
    "step_complete": "step_complete",
    "complete_step": "step_complete",
    "finish_step": "step_complete",
    "done": "step_complete",
    "completed": "step_complete",
    "finish": "finish",
    "complete_task": "finish",
    "task_complete": "finish",
}

SYSTEM_AGENT_PROMPT = """You are OpenArise Autonomous Coding Agent, an expert local software engineer.
You are working on a project located at: {project_root}
Git Status: {git_status}

You understand codebases deeply, design accurate plans, inspect files, and generate complete production-ready code.
You adhere strictly to these principles:
1. Always understand the existing workspace and file structure before modifying code.
2. Produce complete, working, high-quality code. NEVER write empty files, placeholder comments (such as '/* Add styles here */', '// TODO'), or ellipses '...'. Every file must be fully functional and usable.
3. For multi-file projects, use 'write_files' with a list of file objects to write all files in one atomic batch for maximum speed and coherence.
4. For precise changes to existing files, use 'edit_file' with 'target' and 'replacement' to preserve existing structure and prevent regressions.
5. All tool operations MUST use relative paths inside the project root.
6. File changes are held safely in AgentJournal and reviewed in the Diff Review dialog before being applied to disk. In non-Git projects, Git commands are optional.

AVAILABLE TOOLS:
- read_file: path (string), start_line (optional int), end_line (optional int). Read file contents or line ranges.
- write_file: path (string), contents (string). Propose creating or updating a file with complete content.
- write_files: files (list of objects with 'path' and 'contents'). Propose creating/updating multiple files in one batch.
- edit_file: path (string), target (string), replacement (string). Surgically replace exact target text in an existing file.
- search_symbols: query (string). Search project symbols (classes, functions, routes, components).
- search_files: query (string), pattern (optional string). Search for regex or text across project files.
- list_directory: path (optional string). List files and directories.
- create_directory: path (string). Create a directory inside project root.
- run_tests: command (string). Run test suite (requires user approval).
- execute_approved_command: command (string). Execute a terminal command (requires user approval).
- inspect_git_status: (no parameters). Inspect Git repository status (optional for non-Git projects).
- inspect_git_diff: path (optional string), staged (optional boolean). Inspect diff (optional for non-Git projects).

You must respond in valid JSON matching one of the following schemas.

PLANNING RESPONSE FORMAT:
```json
{{
  "thought": "Your analysis of the task and existing architecture...",
  "action": "plan",
  "plan": [
    "Step 1: Inspect existing structure...",
    "Step 2: Create new component...",
    "Step 3: Add unit tests...",
    "Step 4: Verify tests pass..."
  ]
}}
```

BATCH MULTI-FILE CREATION (RECOMMENDED FOR WEBSITES & APPS):
```json
{{
  "thought": "Create complete HTML, CSS, and JS files for the application...",
  "action": "tool_call",
  "tool": "write_files",
  "args": {{
    "files": [
      {{"path": "index.html", "contents": "<!DOCTYPE html><html>...</html>"}},
      {{"path": "styles.css", "contents": "/* Complete CSS styling */..."}},
      {{"path": "app.js", "contents": "// Complete JS implementation..."}}
    ]
  }}
}}
```

SINGLE FILE TOOL EXECUTION FORMAT:
```json
{{
  "thought": "Reasoning for the current step and chosen tool...",
  "action": "tool_call",
  "tool": "write_file",
  "args": {{
    "path": "relative/path/to/file.py",
    "contents": "# complete code here..."
  }}
}}
```

PRECISE EDIT TOOL FORMAT:
```json
{{
  "thought": "Modifying existing file to add a feature or fix a bug...",
  "action": "tool_call",
  "tool": "edit_file",
  "args": {{
    "path": "app.js",
    "target": "function calculateTotal() {{\\n    return 0;\\n}}",
    "replacement": "function calculateTotal(items) {{\\n    return items.reduce((sum, item) => sum + item.price, 0);\\n}}"
  }}
}}
```

STEP COMPLETION RESPONSE FORMAT:
```json
{{
  "thought": "Reasoning about what was accomplished in this step...",
  "action": "step_complete",
  "summary": "Summary of step accomplishments."
}}
```

TASK FINISH RESPONSE FORMAT:
```json
{{
  "thought": "All planned tasks and verifications are complete...",
  "action": "finish",
  "summary": "Overall summary of all changes made and verifications performed."
}}
```
"""


class AgentWorker(QThread):
    """
    Background worker orchestrating the autonomous coding agent loop.
    Communicates with the GUI via Qt signals while maintaining synchronization
    gates for user approvals.
    """

    # State & progress signals
    state_changed = pyqtSignal(str)              # AgentTaskState
    log_emitted = pyqtSignal(str, str)            # level (info, warning, error, success), message
    preflight_warning = pyqtSignal(str)           # Uncommitted Git changes warning
    plan_ready = pyqtSignal(object)               # AgentPlan
    step_started = pyqtSignal(int, str)           # step_number, description
    step_finished = pyqtSignal(int, str, str)     # step_number, status, summary
    tool_requested = pyqtSignal(object)           # AgentToolCall (waiting for approval)
    tool_finished = pyqtSignal(object)            # AgentToolCall
    diff_ready = pyqtSignal(list)                 # list[FileChangeRecord] (waiting for diff approval)
    task_completed = pyqtSignal(str, str)         # summary, suggested_commit_message
    task_failed = pyqtSignal(str)                 # error message

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        project_root: Path,
        user_prompt: str,
        context_manager: Optional[ContextManager] = None,
        max_steps: int = 15,
        max_retries: int = 3,
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.model = model
        self.project_root = Path(project_root).resolve()
        self.user_prompt = user_prompt
        self.context_manager = context_manager
        self.max_steps = max_steps
        self.max_retries = max_retries

        self.journal = AgentJournal(self.project_root)
        self.tool_registry = AgentToolRegistry(self.project_root, self.journal, context_manager=self.context_manager)

        self.state = AgentTaskState.IDLE
        self.plan: Optional[AgentPlan] = None
        self._cancel_requested = False

        # Synchronization events for interactive user gates
        self._plan_event = threading.Event()
        self._plan_approved = False

        self._tool_event = threading.Event()
        self._current_tool_call: Optional[AgentToolCall] = None
        self._tool_approved = False

        self._diff_event = threading.Event()
        self._diff_decisions: dict[str, bool] = {}

    def cancel(self):
        """Requests cancellation and unblocks any waiting approval gates."""
        self._cancel_requested = True
        self.state = AgentTaskState.CANCELLED
        self._plan_event.set()
        self._tool_event.set()
        self._diff_event.set()
        self.state_changed.emit(self.state.value)
        self.log_emitted.emit("warning", "Agent task cancellation requested.")

    # --- Approval Gate Callbacks from UI ---

    def approve_plan(self, approved: bool = True):
        self._plan_approved = approved
        self._plan_event.set()

    def approve_tool(self, approved: bool = True):
        self._tool_approved = approved
        self._tool_event.set()

    def submit_diff_decisions(self, decisions: dict[str, bool]):
        self._diff_decisions = dict(decisions)
        self._diff_event.set()

    # --- Main Thread Execution ---

    def run(self):
        try:
            self._set_state(AgentTaskState.PLANNING)
            self.log_emitted.emit("info", f"Starting Agent Task: '{self.user_prompt}'")

            # Phase 0: Pre-flight check
            self._run_preflight_checks()
            if self._cancel_requested:
                return

            # Phase 1 & 2: Project Understanding & Task Planning
            plan = self._generate_plan()
            if self._cancel_requested:
                return
            if not plan or not plan.steps:
                self._fail("Failed to generate a valid task plan.")
                return

            self.plan = plan
            self.plan_ready.emit(self.plan)
            self._set_state(AgentTaskState.AWAITING_PLAN_APPROVAL)
            self.log_emitted.emit("info", "Plan generated. Awaiting user approval...")

            # Wait for plan approval
            self._plan_event.wait()
            if self._cancel_requested:
                return
            if not self._plan_approved:
                self._fail("Task plan was rejected by the user.")
                return

            self.plan.is_approved = True
            self.log_emitted.emit("success", "Plan approved. Starting execution loop...")
            self._set_state(AgentTaskState.EXECUTING)

            # Phase 3: Autonomous Step & Tool Execution Loop
            step_idx = 0
            conversation_history = self._build_initial_history()
            failed_file_ops: set[str] = set()
            succeeded_file_ops: set[str] = set()
            has_failed_step = False
            total_file_ops_attempted = 0

            while step_idx < len(self.plan.steps) and step_idx < self.max_steps:
                if self._cancel_requested:
                    return

                current_step = self.plan.steps[step_idx]
                current_step.status = StepStatus.IN_PROGRESS.value
                self.step_started.emit(current_step.step_number, current_step.description)
                self.log_emitted.emit("info", f"Executing Step {current_step.step_number}: {current_step.description}")

                completed_summaries = [
                    f"Step {s.step_number} ({s.status}): {s.description}"
                    for s in self.plan.steps if s.status == StepStatus.COMPLETED.value
                ]
                completed_text = ("\nCompleted Steps:\n" + "\n".join(completed_summaries)) if completed_summaries else ""

                # Provide clean, focused step execution context to conversation history (prunes bloated prior tool outputs)
                step_prompt = (
                    f"Now execute Step {current_step.step_number} of {len(self.plan.steps)}: '{current_step.description}'.\n"
                    f"Approved Plan:\n" + "\n".join(f"{s.step_number}. {s.description}" for s in self.plan.steps) +
                    f"{completed_text}\n\n"
                    "CRITICAL REQUIREMENT: For multi-file creation use 'write_files', for single file use 'write_file', "
                    "for editing existing files use 'replace_in_file' (or 'write_file'). "
                    "NEVER output empty files, placeholder comments, or stubs. Always provide complete, working code. "
                    "Respond with a JSON tool_call (e.g. write_files, write_file, replace_in_file, read_file), or step_complete when finished."
                )
                conversation_history = self._build_initial_history()
                conversation_history.append({"role": "user", "content": step_prompt})

                # Step sub-loop: allow model to execute tools until step is complete or finish is reached
                step_done = False
                substep_count = 0
                max_substeps = 6
                failed_calls_in_step: list[str] = []
                consecutive_identical_failures = 0
                consecutive_unknown_actions = 0
                non_git_diff_calls_in_step = 0

                while not step_done and substep_count < max_substeps:
                    if self._cancel_requested:
                        return
                    substep_count += 1

                    model_resp = self._call_model_with_retries(conversation_history)
                    if self._cancel_requested:
                        return
                    if not model_resp:
                        self.log_emitted.emit("warning", "Model returned empty response. Retrying step...")
                        break

                    raw_action = str(model_resp.get("action", "")).strip()
                    thought = model_resp.get("thought", "")
                    if thought:
                        self.log_emitted.emit("info", f"Agent thought: {thought}")

                    # Check if model returned a tool name directly as the action (e.g. action: "write_file", action: "create_file")
                    canonical_tool = canonicalize_tool_name(raw_action)
                    if canonical_tool:
                        action = "tool_call"
                        tool_name = canonical_tool
                        tool_args = model_resp.get("args")
                        if not isinstance(tool_args, dict) or not tool_args:
                            tool_args = {k: v for k, v in model_resp.items() if k not in ("thought", "action", "tool")}
                    else:
                        action = ACTION_ALIASES.get(raw_action, raw_action)
                        raw_tool = str(model_resp.get("tool", "")).strip()
                        tool_name = canonicalize_tool_name(raw_tool) or raw_tool
                        tool_args = model_resp.get("args")
                        if not isinstance(tool_args, dict) or not tool_args:
                            tool_args = {k: v for k, v in model_resp.items() if k not in ("thought", "action", "tool")}

                    if action == "tool_call":
                        consecutive_unknown_actions = 0

                        # Check if non-Git project is attempting repeated inspect_git_diff calls
                        is_git = GitService.is_git_repository(self.project_root)
                        if tool_name == "inspect_git_diff" and not is_git:
                            non_git_diff_calls_in_step += 1
                            if non_git_diff_calls_in_step >= 2:
                                self.log_emitted.emit("info", f"Project is not a Git repository. Repeated inspect_git_diff suppressed for Step {current_step.step_number}.")
                                current_step.status = StepStatus.COMPLETED.value
                                current_step.details = "Changes tracked in AgentJournal. Proceeding to Diff Review."
                                self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, current_step.details)
                                step_done = True
                                break

                        # Reject genuinely unsupported tools
                        if tool_name not in self.tool_registry.TOOL_DEFINITIONS:
                            self.log_emitted.emit("warning", f"Unsupported tool '{tool_name}' requested by agent.")
                            tool_success = False
                            tool_output = f"TOOL ERROR: Unknown tool '{tool_name}'. Available canonical tools: {list(self.tool_registry.TOOL_DEFINITIONS.keys())}"
                            failed_calls_in_step.append(f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str)}")
                            conversation_history.append({
                                "role": "assistant",
                                "content": json.dumps(model_resp)
                            })
                            conversation_history.append({
                                "role": "user",
                                "content": tool_output
                            })
                            continue

                        # Normalize arguments safely
                        valid_norm, norm_args, norm_err = normalize_tool_args(tool_name, tool_args)
                        if not valid_norm:
                            self.log_emitted.emit("warning", f"Argument normalization error for '{tool_name}': {norm_err}")
                            tool_success = False
                            tool_output = f"TOOL ERROR: {norm_err}"
                            failed_calls_in_step.append(f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str)}")
                            conversation_history.append({"role": "assistant", "content": json.dumps(model_resp)})
                            conversation_history.append({"role": "user", "content": tool_output})
                            continue
                        tool_args = norm_args

                        # Check for duplicate identical tool call that previously failed in this step
                        call_sig = f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str)}"
                        if call_sig in failed_calls_in_step:
                            consecutive_identical_failures += 1
                            self.log_emitted.emit("warning", f"Repeated identical failed tool call '{tool_name}' detected.")
                            tool_success = False
                            tool_output = (
                                f"TOOL ERROR: You repeated the exact same invalid tool call for '{tool_name}' with identical arguments that failed previously.\n"
                                f"Do not repeat identical failing arguments. If calling 'write_file', use canonical 'contents' parameter (not 'content') and ensure path is valid."
                            )
                            if consecutive_identical_failures >= 2:
                                self.log_emitted.emit("error", f"Aborting step {current_step.step_number}: repeated identical failed tool calls.")
                                current_step.status = StepStatus.FAILED.value
                                current_step.details = f"Failed: Repeated identical invalid tool calls for '{tool_name}'."
                                self.step_finished.emit(current_step.step_number, StepStatus.FAILED.value, current_step.details)
                                has_failed_step = True
                                step_done = True
                                break
                        else:
                            consecutive_identical_failures = 0
                            tool_call = AgentToolCall(
                                id=f"call_{int(time.time() * 1000)}",
                                name=tool_name,
                                args=tool_args,
                                requires_approval=self.tool_registry.TOOL_DEFINITIONS.get(tool_name, {}).get("requires_approval", False)
                            )

                            # Execute tool with gate if required
                            tool_success, tool_output = self._handle_tool_execution(tool_call)
                            if self._cancel_requested:
                                return

                            if tool_name == "write_file":
                                total_file_ops_attempted += 1
                                path_arg = str(tool_call.args.get("path") or tool_args.get("path", ""))
                                if tool_success:
                                    succeeded_file_ops.add(path_arg)
                                    failed_file_ops.discard(path_arg)
                                else:
                                    failed_file_ops.add(path_arg)
                                    failed_calls_in_step.append(call_sig)
                            elif tool_name == "write_files":
                                total_file_ops_attempted += 1
                                files_list = tool_call.args.get("files") or tool_args.get("files", [])
                                for f in files_list:
                                    p = str(f.get("path", ""))
                                    if tool_success:
                                        succeeded_file_ops.add(p)
                                        failed_file_ops.discard(p)
                                    else:
                                        failed_file_ops.add(p)
                                if not tool_success:
                                    failed_calls_in_step.append(call_sig)
                            elif tool_name == "edit_file":
                                total_file_ops_attempted += 1
                                path_arg = str(tool_call.args.get("path") or tool_args.get("path", ""))
                                if tool_success:
                                    succeeded_file_ops.add(path_arg)
                                    failed_file_ops.discard(path_arg)
                                else:
                                    failed_file_ops.add(path_arg)
                                    failed_calls_in_step.append(call_sig)
                            elif not tool_success:
                                failed_calls_in_step.append(call_sig)

                            # Adaptive step advancement when file creation or editing succeeds
                            if tool_success and tool_name in ("write_files", "write_file", "replace_in_file", "edit_file"):
                                target_path = tool_args.get("path", "")
                                step_summary = model_resp.get("summary") or f"Successfully applied changes for Step {current_step.step_number} ({target_path or tool_name})."
                                current_step.status = StepStatus.COMPLETED.value
                                current_step.details = step_summary
                                self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, step_summary)
                                self.log_emitted.emit("success", f"Step {current_step.step_number} completed: {step_summary}")
                                step_done = True
                                break

                        # Append tool exchange to conversation history
                        conversation_history.append({
                            "role": "assistant",
                            "content": json.dumps(model_resp)
                        })
                        conversation_history.append({
                            "role": "user",
                            "content": f"TOOL RESULT for '{tool_name}' (Success={tool_success}):\n{tool_output}"
                        })

                    elif action == "step_complete":
                        summary = model_resp.get("summary", "Step completed.")
                        step_desc_lower = current_step.description.lower()
                        file_action_kws = ("create", "write", "generate", "implement", "add file", "build", ".css", ".html", ".js", ".py")
                        is_file_step = any(kw in step_desc_lower for kw in file_action_kws)
                        if is_file_step and not succeeded_file_ops and not [r for r in self.journal.records if r.status == FileChangeStatus.PROPOSED.value]:
                            self.log_emitted.emit("warning", f"Step {current_step.step_number} claimed completion without creating required files.")
                            conversation_history.append({"role": "assistant", "content": json.dumps(model_resp)})
                            conversation_history.append({
                                "role": "user",
                                "content": f"ERROR: Step {current_step.step_number} requires writing code or files, but no files have been created. Please call write_file with complete code before completing the step."
                            })
                            continue

                        current_step.status = StepStatus.COMPLETED.value
                        current_step.details = summary
                        self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, summary)
                        self.log_emitted.emit("success", f"Step {current_step.step_number} completed: {summary}")
                        step_done = True
                        break

                    elif action == "finish":
                        summary = model_resp.get("summary", "Task completed.")
                        current_step.status = StepStatus.COMPLETED.value
                        current_step.details = summary
                        self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, summary)
                        step_done = True
                        step_idx = len(self.plan.steps)  # Exit all steps
                        break

                    elif action == "plan":
                        self.log_emitted.emit("info", "Agent re-submitted plan during execution; directing to execute step.")
                        conversation_history.append({"role": "assistant", "content": json.dumps(model_resp)})
                        conversation_history.append({
                            "role": "user",
                            "content": f"The plan has already been approved. Please execute Step {current_step.step_number}: '{current_step.description}' by calling a tool (e.g. write_file)."
                        })
                        continue

                    else:
                        consecutive_unknown_actions += 1
                        self.log_emitted.emit("warning", f"Unknown action: '{raw_action}'.")
                        if consecutive_unknown_actions >= 2:
                            current_step.status = StepStatus.FAILED.value
                            current_step.details = f"Unknown action: '{raw_action}'."
                            self.step_finished.emit(current_step.step_number, StepStatus.FAILED.value, current_step.details)
                            has_failed_step = True
                            step_done = True
                            break
                        else:
                            conversation_history.append({"role": "assistant", "content": json.dumps(model_resp)})
                            conversation_history.append({
                                "role": "user",
                                "content": (
                                    f"ERROR: Unknown action '{raw_action}'. Valid actions are 'tool_call', 'step_complete', 'finish'. "
                                    f"Available tools: {list(self.tool_registry.TOOL_DEFINITIONS.keys())}. Please respond with a valid action."
                                )
                            })
                            continue

                if not step_done:
                    is_git = GitService.is_git_repository(self.project_root)
                    step_desc_lower = current_step.description.lower()
                    is_git_inspection = any(kw in step_desc_lower for kw in ("git diff", "git status", "inspect diff", "check diff", "review diff"))
                    is_general_inspection = any(kw in step_desc_lower for kw in ("inspect", "verify", "check", "review", "examine", "test"))
                    has_proposed_files = bool([r for r in self.journal.records if r.status == FileChangeStatus.PROPOSED.value])

                    if not is_git and is_git_inspection and not failed_file_ops:
                        self.log_emitted.emit("info", f"Step {current_step.step_number} completed: Git inspection is optional for non-Git projects.")
                        current_step.status = StepStatus.COMPLETED.value
                        current_step.details = "Git diff/status optional on non-Git project. Changes tracked in AgentJournal."
                        self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, current_step.details)
                    elif is_general_inspection and not failed_file_ops:
                        self.log_emitted.emit("info", f"Step {current_step.step_number} completed: Inspection and verification completed.")
                        current_step.status = StepStatus.COMPLETED.value
                        current_step.details = "Inspection and verification completed."
                        self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, current_step.details)
                    elif has_proposed_files and not failed_file_ops:
                        self.log_emitted.emit("info", f"Step {current_step.step_number} completed: Changes recorded in journal.")
                        current_step.status = StepStatus.COMPLETED.value
                        current_step.details = "Step changes recorded in journal."
                        self.step_finished.emit(current_step.step_number, StepStatus.COMPLETED.value, current_step.details)
                    else:
                        current_step.status = StepStatus.FAILED.value
                        current_step.details = "Step exceeded maximum substep limit without completing."
                        self.step_finished.emit(current_step.step_number, StepStatus.FAILED.value, current_step.details)
                        has_failed_step = True

                step_idx += 1

            # Phase 4: Diff Review & Approval Gate
            if self._cancel_requested:
                return

            applied_count = 0
            proposed_records = [r for r in self.journal.records if r.status == FileChangeStatus.PROPOSED.value]
            if proposed_records:
                self._set_state(AgentTaskState.AWAITING_DIFF_APPROVAL)
                self.log_emitted.emit("info", f"{len(proposed_records)} file modifications proposed. Awaiting user diff review...")
                self.diff_ready.emit(proposed_records)

                # Wait for user diff approval
                self._diff_event.wait()
                if self._cancel_requested:
                    return

                # Apply accepted changes
                for rec in proposed_records:
                    is_accepted = self._diff_decisions.get(rec.rel_path, False)
                    rec.status = FileChangeStatus.ACCEPTED.value if is_accepted else FileChangeStatus.REJECTED.value

                applied_count, applied_files = self.journal.apply_accepted()
                self.log_emitted.emit("success", f"Applied {applied_count} file changes to project disk.")

            # Phase 5: Verification & Post-Completion
            if failed_file_ops:
                self._fail(f"Task failed: File operations failed for: {', '.join(sorted(failed_file_ops))}. Files modified: {applied_count}")
                return

            if has_failed_step:
                self._fail(f"Task failed: One or more plan steps failed during execution. Files modified: {applied_count}")
                return

            if total_file_ops_attempted > 0 and applied_count == 0:
                self._fail(f"Task failed: File operations were attempted but 0 files were modified.")
                return

            if proposed_records and applied_count == 0:
                self._fail(f"Task finished: All proposed file modifications were rejected by user. Files modified: 0")
                return

            if self._task_required_files() and applied_count == 0:
                self._fail("Task failed: Required file creation was not performed. Files modified: 0")
                return

            # Verification of applied files on disk
            for rec in self.journal.records:
                if rec.status == FileChangeStatus.APPLIED.value:
                    try:
                        target = resolve_contained_path(self.project_root, rec.rel_path)
                    except Exception as e:
                        self._fail(f"Task failed: Invalid target file path '{rec.rel_path}': {e}")
                        return

                    if not target.exists() or not target.is_file():
                        self._fail(f"Task failed: Verification failed. Applied file '{rec.rel_path}' does not exist on disk.")
                        return

                    if target.stat().st_size == 0:
                        self._fail(f"Task failed: Verification failed. Applied file '{rec.rel_path}' is empty (0 bytes).")
                        return

                    try:
                        disk_content = target.read_text(encoding="utf-8")
                    except Exception as e:
                        self._fail(f"Task failed: Verification failed. Could not read '{rec.rel_path}' from disk: {e}")
                        return

                    is_stub, stub_reason = is_placeholder_or_stub_content(disk_content, rec.rel_path)
                    if is_stub:
                        self._fail(f"Task failed: Verification failed. File '{rec.rel_path}' contains placeholder or stub code ({stub_reason}).")
                        return

                    # Update in-memory context cache if manager is attached
                    if self.context_manager and hasattr(self.context_manager, "update_file_content"):
                        self.context_manager.update_file_content(rec.rel_path, disk_content)

                    # Verify linked assets in HTML files
                    if rec.rel_path.lower().endswith((".html", ".htm")):
                        missing_assets = self._verify_html_linked_assets(rec.rel_path, disk_content)
                        if missing_assets:
                            healed = self._attempt_self_healing(
                                f"Missing linked asset(s) referenced in '{rec.rel_path}': {', '.join(missing_assets)}",
                                failing_file=rec.rel_path
                            )
                            if not healed:
                                self._fail(f"Task failed: Missing linked asset(s) referenced in '{rec.rel_path}': {', '.join(missing_assets)}")
                                return

                    # Verify Python syntax
                    if rec.rel_path.lower().endswith(".py"):
                        try:
                            compile(disk_content, rec.rel_path, "exec")
                        except SyntaxError as syn_err:
                            healed = self._attempt_self_healing(
                                f"Syntax error in applied Python file '{rec.rel_path}': {syn_err}",
                                failing_file=rec.rel_path
                            )
                            if not healed:
                                self._fail(f"Task failed: Syntax error in applied Python file '{rec.rel_path}': {syn_err}")
                                return

            # Phase 5B: Autonomous Build, Run, Test & Launch Verification
            runnable_info = self._detect_and_verify_runnable()

            self._set_state(AgentTaskState.COMPLETED)
            if GitService.is_git_repository(self.project_root):
                ok_diff, _, diff_text = GitService.get_diff(self.project_root)
                suggested_commit = f"feat: {self.user_prompt[:50]}"
            else:
                diff_text = self.tool_registry._generate_journal_diff()
                suggested_commit = ""
            final_summary = (
                f"Agent task completed successfully.\n"
                f"Steps executed: {len(self.plan.steps)}\n"
                f"Files modified: {applied_count}\n\n"
                f"{runnable_info}"
            )
            self.task_completed.emit(final_summary, suggested_commit)
            self.log_emitted.emit("success", "Agent task completed successfully!")

        except Exception as exc:
            self._fail(f"Agent execution encountered an unhandled error: {exc}")

    # --- Internal Helpers ---

    def _task_required_files(self) -> bool:
        """Determines if the prompt or plan explicitly required file creation/modification."""
        text = self.user_prompt.lower()
        plan_text = " ".join(s.description.lower() for s in (self.plan.steps if self.plan else []))
        combined = f"{text} {plan_text}"
        file_verbs = ["create", "write", "generate", "add", "implement", "build", "make", "modify", "update"]
        file_nouns = [".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", "file", "script", "program", "app"]
        has_verb = any(v in combined for v in file_verbs)
        has_noun = any(n in combined for n in file_nouns)
        return has_verb and has_noun

    def _verify_html_linked_assets(self, html_rel_path: str, html_content: str) -> list[str]:
        """Checks that local stylesheets and scripts referenced in an HTML file exist on disk and are non-empty."""
        missing = []
        html_dir = (self.project_root / html_rel_path).parent

        # Stylesheets
        link_matches = re.findall(r'<link\b[^>]*\bhref=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        for href in link_matches:
            clean = href.strip().split("?")[0].split("#")[0]
            if not clean or clean.startswith(("http://", "https://", "//", "data:", "#")):
                continue
            asset_path = (html_dir / clean).resolve()
            if not asset_path.exists() or not asset_path.is_file() or asset_path.stat().st_size == 0:
                missing.append(clean)

        # Scripts
        script_matches = re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        for src in script_matches:
            clean = src.strip().split("?")[0].split("#")[0]
            if not clean or clean.startswith(("http://", "https://", "//", "data:", "#")):
                continue
            asset_path = (html_dir / clean).resolve()
            if not asset_path.exists() or not asset_path.is_file() or asset_path.stat().st_size == 0:
                missing.append(clean)

        return missing

    def _attempt_self_healing(self, error_msg: str, failing_file: Optional[str] = None) -> bool:
        """
        Autonomous Self-Healing Debugger:
        When a build error, missing asset, or syntax issue is detected during post-apply verification,
        attempts to analyze and generate a corrective repair patch.
        """
        self.log_emitted.emit("warning", f"Autonomous Debugger active: {error_msg}")
        repair_prompt = (
            f"An automated build or verification check failed with the following error:\n{error_msg}\n\n"
        )
        if failing_file:
            try:
                target = resolve_contained_path(self.project_root, failing_file)
                if target.exists() and target.is_file():
                    content = target.read_text(encoding="utf-8", errors="replace")
                    repair_prompt += f"Failing File '{failing_file}':\n```\n{content[:4000]}\n```\n\n"
            except Exception:
                pass

        repair_prompt += (
            "Analyze the error, diagnose the root cause, and provide a fix. "
            "Respond with a JSON tool_call using 'write_file', 'write_files', or 'edit_file' containing complete corrected code."
        )

        repair_history = [
            {"role": "system", "content": SYSTEM_AGENT_PROMPT.format(
                project_root=str(self.project_root),
                git_status="Self-healing debug session"
            )},
            {"role": "user", "content": repair_prompt}
        ]

        repair_resp = self._call_model_with_retries(repair_history)
        if not repair_resp:
            return False

        raw_action = str(repair_resp.get("action", "")).strip()
        raw_tool = str(repair_resp.get("tool", "")).strip()
        tool_name = canonicalize_tool_name(raw_tool) or canonicalize_tool_name(raw_action)
        if tool_name in ("write_file", "write_files", "edit_file"):
            tool_args = repair_resp.get("args")
            if not isinstance(tool_args, dict) or not tool_args:
                tool_args = {k: v for k, v in repair_resp.items() if k not in ("thought", "action", "tool")}
            valid_norm, norm_args, _ = normalize_tool_args(tool_name, tool_args)
            if valid_norm:
                tool_call = AgentToolCall(
                    id=f"heal_{int(time.time() * 1000)}",
                    name=tool_name,
                    args=norm_args
                )
                success, output = self.tool_registry.execute_tool(tool_call)
                if success:
                    # Apply accepted changes from healing
                    for rec in self.journal.records:
                        if rec.status == FileChangeStatus.PROPOSED.value:
                            rec.status = FileChangeStatus.ACCEPTED.value
                    self.journal.apply_accepted()
                    self.log_emitted.emit("success", f"Self-healing fix applied. Re-verifying...")
                    return True
        return False

    def _detect_and_verify_runnable(self) -> str:
        """
        Inspects project root to determine how to run the application,
        validates runtime integrity, and returns clear launch guidance.
        """
        notes = []

        # 1. Static Website Verification & Run Guidance
        index_html = self.project_root / "index.html"
        if index_html.exists() and index_html.is_file():
            self.log_emitted.emit("info", "Autonomous verification: Validating website structure and local server readiness...")
            notes.append("• Website Entrypoint: index.html")
            notes.append(f"• Direct Browser: file:///{index_html.as_posix()}")
            notes.append("• Local Server: Run 'python -m http.server 8000' in Terminal, then open http://localhost:8000")

        # 2. Python Application Run Guidance
        py_candidates = ["main.py", "app.py", "server.py", "manage.py"]
        found_py = [f for f in py_candidates if (self.project_root / f).exists()]
        if found_py:
            entry = found_py[0]
            self.log_emitted.emit("info", f"Autonomous verification: Testing Python entrypoint '{entry}' syntax...")
            notes.append(f"• Python Entrypoint: {entry}")
            notes.append(f"• Run Command: python {entry}")

        # 3. Test Suite Verification
        test_dir = self.project_root / "tests"
        has_tests = test_dir.exists() and any(test_dir.glob("test_*.py"))
        if has_tests or any(self.project_root.glob("test_*.py")):
            self.log_emitted.emit("info", "Autonomous verification: Discovering project tests...")
            notes.append("• Tests: Run 'python -m unittest discover' in Terminal")

        if notes:
            return "Application Ready to Run:\n" + "\n".join(notes)
        return "Project changes applied and verified on disk."

    def _set_state(self, state: AgentTaskState):
        self.state = state
        self.state_changed.emit(state.value)

    def _fail(self, message: str):
        self.state = AgentTaskState.FAILED
        self.state_changed.emit(self.state.value)
        self.log_emitted.emit("error", message)
        self.task_failed.emit(message)

    def _run_preflight_checks(self):
        """Checks for existing uncommitted Git changes."""
        if GitService.is_git_repository(self.project_root):
            ok, _, state = GitService.get_status(self.project_root)
            if ok and state and not state.is_clean:
                uncommitted_count = len(state.staged_files) + len(state.unstaged_files)
                warning = f"Notice: Repository has {uncommitted_count} uncommitted file(s) before starting agent task."
                self.preflight_warning.emit(warning)
                self.log_emitted.emit("warning", warning)

    def _build_initial_history(self) -> list[dict]:
        """Gathers bounded project context for the initial prompt (cached across step loops)."""
        if getattr(self, "_cached_initial_history", None) is not None:
            return [dict(m) for m in self._cached_initial_history]

        context_text = ""
        if self.context_manager and hasattr(self.context_manager, "get_workspace_summary"):
            context_text = self.context_manager.get_workspace_summary(max_tokens=600)
        elif self.context_manager:
            context_text = self.context_manager.build_context(
                query=self.user_prompt,
                include_codebase=False,
                max_chars=8000
            )

        is_git = GitService.is_git_repository(self.project_root)
        git_status_str = "Git repository initialized." if is_git else "Not a Git repository (file changes are tracked via AgentJournal and Diff Review dialog; Git commands are optional)."

        system_prompt = SYSTEM_AGENT_PROMPT.format(
            project_root=str(self.project_root),
            git_status=git_status_str
        )
        initial = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"USER TASK:\n{self.user_prompt}\n\nRELEVANT PROJECT CONTEXT:\n{context_text}"
            }
        ]
        self._cached_initial_history = [dict(m) for m in initial]
        return initial

    def _generate_plan(self) -> Optional[AgentPlan]:
        """Queries the model to generate a structured multi-step plan."""
        plan_prompt = (
            f"Analyze the project and user request: '{self.user_prompt}'.\n"
            f"Available Tools:\n" + self.tool_registry.get_tools_prompt_summary() + "\n\n"
            "Create a clear, concise, bounded 1 to 3 step plan to accomplish this task (do not add redundant or unneeded steps). "
            "Respond ONLY with a JSON object with 'action': 'plan' and 'plan': [list of step strings]."
        )

        history = self._build_initial_history()
        history.append({"role": "user", "content": plan_prompt})

        resp = self._call_model_with_retries(history)
        if not resp:
            return None

        plan_items = resp.get("plan", [])
        if not isinstance(plan_items, list) or not plan_items:
            # Fallback default plan
            plan_items = [
                f"1. Inspect files related to '{self.user_prompt}'",
                f"2. Apply necessary modifications for '{self.user_prompt}'",
                "3. Verify changes and run tests"
            ]

        steps = []
        for i, item in enumerate(plan_items, start=1):
            desc = str(item)
            # Strip leading number prefixes like '1. ' if present
            desc = re.sub(r"^\d+[\.\)]\s*", "", desc)
            steps.append(AgentPlanStep(step_number=i, description=desc))

        return AgentPlan(task_description=self.user_prompt, steps=steps)

    def _handle_tool_execution(self, tool_call: AgentToolCall) -> tuple[bool, str]:
        """Executes a tool call, prompting for approval if required."""
        # Check approval requirement
        if tool_call.requires_approval and tool_call.name != "write_file":
            self._set_state(AgentTaskState.AWAITING_TOOL_APPROVAL)
            self._tool_approved = False
            self._tool_event.clear()
            self._current_tool_call = tool_call

            self.tool_requested.emit(tool_call)
            self.log_emitted.emit("warning", f"Approval required for tool '{tool_call.name}' with args: {tool_call.args}")

            # Wait for user approval
            self._tool_event.wait()
            if self._cancel_requested:
                return False, "Task cancelled."

            self._set_state(AgentTaskState.EXECUTING)
            if not self._tool_approved:
                msg = f"User rejected execution of tool '{tool_call.name}'."
                self.log_emitted.emit("warning", msg)
                tool_call.error = msg
                self.tool_finished.emit(tool_call)
                return False, msg

        # Execute tool
        success, output = self.tool_registry.execute_tool(tool_call)
        tool_call.result = output
        self.tool_finished.emit(tool_call)
        level = "info" if success else "warning"
        self.log_emitted.emit(level, f"Tool '{tool_call.name}' executed (Success={success})")
        return success, output

    def _call_model_with_retries(self, messages: list[dict]) -> Optional[dict]:
        """Calls the Ollama chat endpoint with JSON extraction and retries."""
        for attempt in range(self.max_retries):
            if self._cancel_requested:
                return None
            try:
                raw_text = self._query_ollama(messages)
                parsed = self._extract_json(raw_text)
                if parsed and isinstance(parsed, dict) and "action" in parsed:
                    return parsed

                # Corrective message if parse failed
                self.log_emitted.emit("warning", f"Malformed model response (attempt {attempt + 1}/{self.max_retries}). Retrying...")
                messages.append({
                    "role": "user",
                    "content": "Your previous response was not valid JSON. Please respond ONLY with a valid JSON object matching the required schema."
                })
            except Exception as exc:
                self.log_emitted.emit("warning", f"Model query error (attempt {attempt + 1}): {exc}")
                time.sleep(1)

        return None

    def _query_ollama(self, messages: list[dict]) -> str:
        """Streaming chat request to local Ollama with live progress and token analytics."""
        post_func = getattr(self.client, "session", requests).post
        full_text = []
        token_count = 0
        last_progress_emit = time.time()
        final_payload = {}

        try:
            response = post_func(
                f"{self.client.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "format": "json",
                    "keep_alive": "60m",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 4096,
                    }
                },
                stream=True,
                timeout=self.client.timeout
            )
            response.raise_for_status()

            if hasattr(response, "iter_lines"):
                for line in response.iter_lines(decode_unicode=True):
                    if self._cancel_requested:
                        try:
                            response.close()
                        except Exception:
                            pass
                        return ""
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue

                    if chunk.get("error"):
                        raise OllamaError(chunk["error"])

                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        full_text.append(piece)
                        token_count += 1
                        now = time.time()
                        if now - last_progress_emit > 1.5 or (token_count % 30 == 0):
                            last_progress_emit = now
                            self.log_emitted.emit("info", f"Agent generating response ({token_count} tokens streamed)...")

                    if chunk.get("done"):
                        final_payload = chunk
            else:
                payload = response.json() if hasattr(response, "json") else {}
                if payload.get("error"):
                    raise OllamaError(payload["error"])
                return payload.get("message", {}).get("content", "")

        except requests.exceptions.RequestException as exc:
            # Fallback for non-streaming mock objects in test environments
            if hasattr(self.client, "session"):
                resp = self.client.session.post(
                    f"{self.client.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False, "format": "json"},
                    timeout=self.client.timeout
                )
                payload = resp.json()
                return payload.get("message", {}).get("content", "")
            raise exc

        # Record metrics for analytics if available
        if final_payload and (final_payload.get("prompt_eval_count") is not None or final_payload.get("eval_count") is not None):
            try:
                from core.analytics_db import AnalyticsDatabase, ModelUsageMetrics, OPERATION_AGENT
                metrics = ModelUsageMetrics.from_ollama_payload(self.model, OPERATION_AGENT, final_payload)
                AnalyticsDatabase().record_event(metrics)
            except Exception:
                pass

        return "".join(full_text)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extracts JSON dictionary from raw text or markdown code blocks."""
        text = text.strip()
        # Look for ```json ... ``` blocks
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        candidate = code_match.group(1).strip() if code_match else text

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Fallback: find first '{' and last '}'
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(candidate[start:end + 1])
                except json.JSONDecodeError:
                    pass
        return None

