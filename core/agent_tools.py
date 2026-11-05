"""
Agent Tool Registry and Security Containment Guards for OpenArise AI Agent Mode.
Implements bounded project inspection, safe file staging via AgentJournal,
regex search, directory listing, and approval-gated command/test execution.
"""

from __future__ import annotations
import fnmatch
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Optional

from core.agent_models import AgentJournal, AgentToolCall, FileChangeType, FileChangeStatus
from core.git_service import GitService

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".idea", "dist", "build", ".openarise_backups"
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".json",
    ".yaml", ".yml", ".toml", ".md", ".txt", ".rst", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".sh", ".bat", ".sql", ".xml"
}
MAX_FILE_BYTES = 512_000


TOOL_ALIASES: dict[str, str] = {
    # write_files
    "create_files": "write_files",
    "save_files": "write_files",
    "batch_write": "write_files",
    "write_all": "write_files",
    # write_file
    "create_file": "write_file",
    "modify_file": "write_file",
    "edit_file": "write_file",
    "file_write": "write_file",
    "save_file": "write_file",
    # replace_in_file
    "patch_file": "replace_in_file",
    "replace_code": "replace_in_file",
    "update_file_section": "replace_in_file",
    # read_file
    "file_read": "read_file",
    "cat": "read_file",
    "view_file": "read_file",
    # search_symbols
    "find_symbol": "search_symbols",
    "find_symbols": "search_symbols",
    "lookup_symbol": "search_symbols",
    "list_symbols": "search_symbols",
    # search_files
    "grep": "search_files",
    "find_in_files": "search_files",
    "file_search": "search_files",
    "search": "search_files",
    # list_directory
    "list_dir": "list_directory",
    "dir_list": "list_directory",
    "ls": "list_directory",
    "list_files": "list_directory",
    # create_directory
    "mkdir": "create_directory",
    "make_directory": "create_directory",
    "create_dir": "create_directory",
    "make_dir": "create_directory",
    # run_tests
    "pytest": "run_tests",
    "test": "run_tests",
    "run_test": "run_tests",
    "execute_tests": "run_tests",
    # inspect_git_status
    "git_status": "inspect_git_status",
    "status_git": "inspect_git_status",
    # inspect_git_diff
    "git_diff": "inspect_git_diff",
    "diff_git": "inspect_git_diff",
    # execute_approved_command
    "execute_command": "execute_approved_command",
    "run_command": "execute_approved_command",
    "terminal_command": "execute_approved_command",
    "exec_command": "execute_approved_command",
    "run_terminal_command": "execute_approved_command",
    "shell_command": "execute_approved_command",
}


def canonicalize_tool_name(name: str) -> Optional[str]:
    """
    Returns the canonical tool name for any registered tool or supported legacy alias.
    Returns None if genuinely unsupported.
    """
    if not isinstance(name, str):
        return None
    cleaned = name.strip()
    if cleaned in AgentToolRegistry.TOOL_DEFINITIONS:
        return cleaned
    return TOOL_ALIASES.get(cleaned)


def is_placeholder_or_stub_content(content: str, rel_path: str = "") -> tuple[bool, str]:
    """
    Detects whether proposed file content is empty, a placeholder comment, or a stub without real code.
    Returns (is_stub: bool, reason: str).
    """
    if not isinstance(content, str):
        return True, "Content is not a string."

    stripped = content.strip()
    if not stripped:
        return True, "File content is completely empty (0 bytes)."

    if len(stripped) < 15:
        if stripped in ("pass", "...", "{}", ";", "<!-- -->", "/* */", "None"):
            return True, f"File content is a trivial stub ({stripped!r})."

    # Strip multi-line comments
    no_comments = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    no_comments = re.sub(r"<!--.*?-->", "", no_comments, flags=re.DOTALL)
    # Strip single line comments
    lines = [line.strip() for line in no_comments.splitlines()]
    non_comment_lines = [
        line for line in lines
        if line and not line.startswith("//") and not line.startswith("#")
    ]
    pure_code = "\n".join(non_comment_lines).strip()

    # If after removing comments there is no substantive code left
    if not pure_code:
        return True, "File consists solely of comments or placeholder notes without functional implementation."

    # File-type specific checks
    ext = rel_path.lower().split(".")[-1] if "." in rel_path else ""

    if ext == "css":
        if "{" not in pure_code or "}" not in pure_code or ":" not in pure_code:
            return True, "CSS stylesheet contains no valid style rule blocks (missing '{', '}' or properties)."

    elif ext in ("js", "ts"):
        js_indicators = [
            "function", "const", "let", "var", "class", "=>", "document.",
            "window.", "localStorage", "addEventListener", "return", "export", "import"
        ]
        if not any(k in pure_code for k in js_indicators):
            return True, "JavaScript file lacks functional declarations, statements, or DOM logic."

    elif ext in ("html", "htm"):
        if "<" not in pure_code or ">" not in pure_code:
            return True, "HTML file lacks markup tags."
        if not any(tag in pure_code.lower() for tag in (
            "<html", "<body", "<div", "<main", "<header", "<section", "<button", "<form", "<p", "<h1", "<table", "<ul"
        )):
            return True, "HTML file lacks substantive layout or structure tags."

    elif ext == "py":
        py_stripped = pure_code.strip()
        if py_stripped in ("pass", "..."):
            return True, "Python file contains only pass or ellipsis."

    return False, ""


def normalize_tool_args(name: str, args: dict) -> tuple[bool, dict, str]:
    """
    Normalizes tool arguments to canonical names.
    - For write_file:
      - Canonical parameter is 'contents'.
      - Safely normalizes aliases ('content', 'code', 'body', 'text') to 'contents'.
      - Explicitly rejects conflicting content values.
      - Safely normalizes 'file_path', 'filepath', 'filename', or 'file' to 'path'.
    - For read_file, create_directory, list_directory, inspect_git_diff:
      - Safely normalizes 'file_path', 'filepath', 'filename', or 'file' to 'path'.
    - For execute_approved_command and run_tests:
      - Safely normalizes 'cmd' to 'command'.
    - For search_files:
      - Safely normalizes 'keyword' to 'query'.

    Returns:
        (is_valid: bool, normalized_args: dict, error_message: str)
    """
    if not isinstance(args, dict):
        return False, {}, f"Tool arguments must be a dictionary, got {type(args).__name__}."

    canonical_name = canonicalize_tool_name(name) or name
    normalized = dict(args)

    # Normalize path aliases
    if canonical_name in ("write_file", "read_file", "create_directory", "list_directory", "inspect_git_diff"):
        path_aliases = ["file_path", "filepath", "filename", "file"]
        has_path = "path" in normalized
        found_alt = [k for k in path_aliases if k in normalized]

        if has_path and found_alt:
            for alt in found_alt:
                if normalized["path"] != normalized[alt]:
                    return (
                        False,
                        normalized,
                        f"Conflicting arguments: both 'path' and '{alt}' provided with different values for '{canonical_name}'."
                    )
                normalized.pop(alt, None)
        elif not has_path and found_alt:
            first_val = normalized[found_alt[0]]
            for alt in found_alt[1:]:
                if normalized[alt] != first_val:
                    return (
                        False,
                        normalized,
                        f"Conflicting path arguments: '{found_alt[0]}' and '{alt}' differ for '{canonical_name}'."
                    )
                normalized.pop(alt, None)
            normalized["path"] = normalized.pop(found_alt[0])

    if canonical_name == "write_file":
        content_aliases = ["content", "code", "body", "text"]
        has_contents = "contents" in normalized
        found_content_alts = [k for k in content_aliases if k in normalized]

        if has_contents and found_content_alts:
            for alt in found_content_alts:
                if normalized["contents"] != normalized[alt]:
                    return (
                        False,
                        normalized,
                        f"Conflicting arguments: both '{alt}' and 'contents' provided with different values for 'write_file'. Please specify only canonical 'contents'."
                    )
                normalized.pop(alt, None)
        elif not has_contents and found_content_alts:
            first_val = normalized[found_content_alts[0]]
            for alt in found_content_alts[1:]:
                if normalized[alt] != first_val:
                    return (
                        False,
                        normalized,
                        f"Conflicting content arguments: '{found_content_alts[0]}' and '{alt}' differ for 'write_file'."
                    )
                normalized.pop(alt, None)
            normalized["contents"] = normalized.pop(found_content_alts[0])

        if "contents" in normalized and not isinstance(normalized["contents"], str):
            normalized["contents"] = str(normalized["contents"])

    elif canonical_name == "write_files":
        # Accept 'files', 'file_list', 'items'
        for alt in ("file_list", "items", "changes"):
            if alt in normalized and "files" not in normalized:
                normalized["files"] = normalized.pop(alt)
        if "files" in normalized and isinstance(normalized["files"], list):
            for item in normalized["files"]:
                if isinstance(item, dict):
                    if "content" in item and "contents" not in item:
                        item["contents"] = item.pop("content")
                    elif "code" in item and "contents" not in item:
                        item["contents"] = item.pop("code")

    elif canonical_name in ("replace_in_file", "edit_file"):
        for alt in ("old_str", "search", "find", "old_text", "old_code"):
            if alt in normalized and "target" not in normalized:
                normalized["target"] = normalized.pop(alt)
        for alt in ("new_str", "replace", "value", "new_text", "new_code"):
            if alt in normalized and "replacement" not in normalized:
                normalized["replacement"] = normalized.pop(alt)

    elif canonical_name == "search_symbols":
        for alt in ("symbol", "name", "keyword", "term"):
            if alt in normalized and "query" not in normalized:
                normalized["query"] = normalized.pop(alt)

    elif canonical_name in ("execute_approved_command", "run_tests"):
        if "cmd" in normalized and "command" not in normalized:
            normalized["command"] = normalized.pop("cmd")
        elif "cmd" in normalized and "command" in normalized:
            if normalized["cmd"] != normalized["command"]:
                return (
                    False,
                    normalized,
                    f"Conflicting arguments: both 'cmd' and 'command' provided for '{canonical_name}'."
                )
            normalized.pop("cmd", None)

    elif canonical_name == "search_files":
        if "keyword" in normalized and "query" not in normalized:
            normalized["query"] = normalized.pop("keyword")

    elif canonical_name == "list_directory":
        if "dir" in normalized and "path" not in normalized:
            normalized["path"] = normalized.pop("dir")
        elif "directory" in normalized and "path" not in normalized:
            normalized["path"] = normalized.pop("directory")
        if normalized.get("path") is None:
            normalized["path"] = ""

    return True, normalized, ""


def resolve_contained_path(project_root: Path, rel_path: str) -> Path:
    """
    Strictly verifies that rel_path resolves inside project_root.
    Raises ValueError on any path traversal (e.g., '../', drive root, etc.).
    """
    root = Path(project_root).resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Path traversal rejected: '{rel_path}' is outside project root.")
    return target


class AgentToolRegistry:
    """
    Registry of tools available to the OpenArise AI Agent.
    Enforces project root containment, JSON schema validation, and user approval gates.
    """

    TOOL_DEFINITIONS = {
        "read_file": {
            "description": "Read the content of a project file (up to 512KB). Optional start_line and end_line for range inspection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path inside the project"},
                    "start_line": {"type": "integer", "description": "Optional 1-indexed start line"},
                    "end_line": {"type": "integer", "description": "Optional 1-indexed end line"}
                },
                "required": ["path"]
            },
            "requires_approval": False
        },
        "write_file": {
            "description": "Propose creating or updating a file with complete content. Queued for diff review and user approval before disk write.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path inside the project"},
                    "contents": {"type": "string", "description": "The complete new content of the file"}
                },
                "required": ["path", "contents"]
            },
            "requires_approval": True  # File write requires diff review / approval
        },
        "write_files": {
            "description": "Propose creating or updating multiple files in one atomic batch. Queued for diff review before disk write.",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "description": "List of file objects, each containing 'path' and complete 'contents'"
                    }
                },
                "required": ["files"]
            },
            "requires_approval": True
        },
        "replace_in_file": {
            "description": "Make precise surgical code replacements in an existing file. Replaces unique 'target' string with 'replacement'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path inside the project"},
                    "target": {"type": "string", "description": "Exact text in the file to be replaced"},
                    "replacement": {"type": "string", "description": "New text to substitute in place of target"}
                },
                "required": ["path", "target", "replacement"]
            },
            "requires_approval": True
        },
        "search_symbols": {
            "description": "Search indexed project symbols (classes, functions, routes, components) across project files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Symbol name or substring to search for"}
                },
                "required": ["query"]
            },
            "requires_approval": False
        },
        "search_files": {
            "description": "Search for a regex or string across project files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Regex or keyword to search for"},
                    "pattern": {"type": "string", "description": "Optional glob filter (e.g. '*.py')"}
                },
                "required": ["query"]
            },
            "requires_approval": False
        },
        "list_directory": {
            "description": "List files and subdirectories in a directory inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path (empty string for project root)"}
                },
                "required": []
            },
            "requires_approval": False
        },
        "create_directory": {
            "description": "Create a new directory inside the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path to create"}
                },
                "required": ["path"]
            },
            "requires_approval": False
        },
        "run_tests": {
            "description": "Run the project test suite (e.g., pytest, unittest). Requires explicit user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Test command (e.g., 'pytest' or 'python -m unittest')"}
                },
                "required": ["command"]
            },
            "requires_approval": True
        },
        "inspect_git_status": {
            "description": "Inspect the Git repository status (branches, modified files, conflicts). Optional in non-Git projects.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "requires_approval": False
        },
        "inspect_git_diff": {
            "description": "Inspect diff of changes. Uses Git diff in repositories, or AgentJournal diff in non-Git projects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional relative file path"},
                    "staged": {"type": "boolean", "description": "Whether to check staged changes"}
                },
                "required": []
            },
            "requires_approval": False
        },
        "execute_approved_command": {
            "description": "Execute a terminal command inside the project directory. Requires explicit user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Exact shell command to execute"}
                },
                "required": ["command"]
            },
            "requires_approval": True
        }
    }

    @classmethod
    def get_canonical_name(cls, name: str) -> Optional[str]:
        return canonicalize_tool_name(name)

    @classmethod
    def get_tools_prompt_summary(cls) -> str:
        """Returns concise summary of canonical tools for model prompts."""
        lines = []
        for name, spec in cls.TOOL_DEFINITIONS.items():
            reqs = spec["parameters"].get("required", [])
            props = spec["parameters"].get("properties", {})
            param_str = ", ".join(f"{p}: {props[p].get('type', 'any')}" for p in reqs)
            lines.append(f"- {name}({param_str}): {spec['description']}")
        return "\n".join(lines)

    def __init__(self, project_root: Path, journal: AgentJournal, context_manager: Optional[Any] = None):
        self.project_root = Path(project_root).resolve()
        self.journal = journal
        self.context_manager = context_manager

    def validate_tool_call(self, name: str, args: dict) -> tuple[bool, str]:
        """Validates that the tool name and arguments match the tool schema."""
        canonical_name = canonicalize_tool_name(name)
        if not canonical_name:
            return False, f"Unknown tool: '{name}'. Available: {list(self.TOOL_DEFINITIONS.keys())}"

        # If routed to write_file but args specify target/replacement, route to replace_in_file
        if canonical_name == "write_file" and ("target" in args or "old_str" in args or "search" in args):
            canonical_name = "replace_in_file"

        valid_norm, norm_args, norm_err = normalize_tool_args(canonical_name, args)
        if not valid_norm:
            return False, norm_err

        schema = self.TOOL_DEFINITIONS[canonical_name]
        reqs = schema["parameters"].get("required", [])
        for req in reqs:
            if req not in norm_args:
                return False, f"Missing required parameter '{req}' for tool '{canonical_name}'."

        # Validate types
        props = schema["parameters"].get("properties", {})
        for param, spec in props.items():
            if param in norm_args and norm_args[param] is not None:
                expected_type = spec.get("type")
                val = norm_args[param]
                if expected_type == "string" and not isinstance(val, str):
                    return False, f"Parameter '{param}' must be a string, got {type(val).__name__}."
                elif expected_type == "boolean" and not isinstance(val, bool):
                    return False, f"Parameter '{param}' must be a boolean, got {type(val).__name__}."
                elif expected_type == "integer" and not isinstance(val, int):
                    return False, f"Parameter '{param}' must be an integer, got {type(val).__name__}."
                elif expected_type == "array" and not isinstance(val, list):
                    return False, f"Parameter '{param}' must be a list/array, got {type(val).__name__}."

        return True, ""

    def execute_tool(self, tool_call: AgentToolCall) -> tuple[bool, str]:
        """
        Executes a validated tool call.
        Enforces containment and records file operations in the journal.
        """
        canonical_name = canonicalize_tool_name(tool_call.name)
        if not canonical_name:
            err = f"Unknown tool: '{tool_call.name}'. Available: {list(self.TOOL_DEFINITIONS.keys())}"
            tool_call.error = err
            return False, err
        tool_call.name = canonical_name

        # If routed to write_file but args specify target/replacement, route to replace_in_file
        if tool_call.name == "write_file" and ("target" in tool_call.args or "old_str" in tool_call.args or "search" in tool_call.args):
            tool_call.name = "replace_in_file"

        valid_norm, norm_args, norm_err = normalize_tool_args(tool_call.name, tool_call.args)
        if not valid_norm:
            tool_call.error = norm_err
            return False, norm_err
        tool_call.args = norm_args

        valid, msg = self.validate_tool_call(tool_call.name, tool_call.args)
        if not valid:
            tool_call.error = msg
            return False, msg

        tool_name = tool_call.name
        args = tool_call.args

        try:
            if tool_name == "read_file":
                return self._tool_read_file(args["path"], args.get("start_line"), args.get("end_line"))

            elif tool_name == "write_file":
                # Staged via journal for diff preview and approval
                return self._tool_write_file(args["path"], args["contents"])

            elif tool_name == "write_files":
                # Batch multi-file creation staged via journal
                return self._tool_write_files(args["files"])

            elif tool_name in ("replace_in_file", "edit_file"):
                # Surgical string replacement staged via journal
                return self._tool_edit_file(args["path"], args["target"], args["replacement"])

            elif tool_name == "search_symbols":
                return self._tool_search_symbols(args["query"])

            elif tool_name == "search_files":
                return self._tool_search_files(args["query"], args.get("pattern"))

            elif tool_name == "list_directory":
                return self._tool_list_directory(args.get("path", ""))

            elif tool_name == "create_directory":
                return self._tool_create_directory(args["path"])

            elif tool_name == "run_tests":
                return self._tool_run_tests(args["command"])

            elif tool_name == "inspect_git_status":
                return self._tool_git_status()

            elif tool_name == "inspect_git_diff":
                return self._tool_git_diff(args.get("path"), args.get("staged", False))

            elif tool_name == "execute_approved_command":
                return self._tool_execute_command(args["command"])

            else:
                return False, f"Unhandled tool '{tool_name}'."

        except Exception as exc:
            tool_call.error = str(exc)
            return False, f"Tool error ({tool_name}): {exc}"

    # --- Tool Implementations ---

    def _tool_read_file(
        self,
        rel_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> tuple[bool, str]:
        target = resolve_contained_path(self.project_root, rel_path)
        # Check if file has staged modifications in the journal first
        content = None
        for rec in reversed(self.journal.records):
            try:
                rec_target = resolve_contained_path(self.project_root, rec.rel_path)
                if rec_target == target and rec.status == FileChangeStatus.PROPOSED.value:
                    if rec.change_type == FileChangeType.DELETE.value:
                        return False, f"File has been marked for deletion: '{rel_path}'"
                    if rec.new_content is not None:
                        content = rec.new_content
                        break
            except ValueError:
                continue

        if content is None:
            if not target.exists() or not target.is_file():
                return False, f"File does not exist: '{rel_path}'"
            if target.stat().st_size > MAX_FILE_BYTES:
                return False, f"File exceeds maximum allowed size ({MAX_FILE_BYTES} bytes)."
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return False, f"Failed to read file: {exc}"

        lines = content.splitlines()
        if start_line is not None or end_line is not None:
            s = max(1, start_line or 1)
            e = min(len(lines), end_line or len(lines))
            numbered = [f"{idx:4d} | {lines[idx - 1]}" for idx in range(s, e + 1)]
            return True, f"Lines {s}-{e} of {rel_path} ({len(lines)} total lines):\n" + "\n".join(numbered)

        return True, content

    def _tool_write_files(self, files: list[dict]) -> tuple[bool, str]:
        """Proposes creating or updating multiple files in one batch."""
        if not isinstance(files, list) or not files:
            return False, "Parameter 'files' must be a non-empty list of file dictionaries."

        staged_summaries = []
        for idx, item in enumerate(files):
            if not isinstance(item, dict):
                return False, f"Entry at index {idx} in 'files' must be a dictionary."
            path = item.get("path")
            contents = item.get("contents") if "contents" in item else item.get("content")
            if not path or not isinstance(path, str):
                return False, f"Entry at index {idx} is missing a valid 'path' string."
            if contents is None:
                return False, f"Entry at index {idx} ('{path}') is missing 'contents'."

            contents = str(contents)
            is_stub, stub_reason = is_placeholder_or_stub_content(contents, path)
            if is_stub:
                return (
                    False,
                    f"Batch write rejected at '{path}': Placeholder or stub content detected ({stub_reason}). "
                    "You must provide complete, functional code for all files in the batch."
                )

            target = resolve_contained_path(self.project_root, path)
            change_type = FileChangeType.MODIFY.value if target.exists() else FileChangeType.CREATE.value
            self.journal.record_change(path, change_type, new_content=contents)
            staged_summaries.append(f"{path} ({len(contents)} bytes)")

        return True, f"Successfully proposed {len(staged_summaries)} file(s): {', '.join(staged_summaries)}. Queued for diff review."

    def _tool_edit_file(self, rel_path: str, target_str: str, replacement: str) -> tuple[bool, str]:
        """Makes precise surgical string replacement in an existing file."""
        target_path = resolve_contained_path(self.project_root, rel_path)
        current_content = None

        # Check journal first
        for rec in reversed(self.journal.records):
            try:
                if resolve_contained_path(self.project_root, rec.rel_path) == target_path and rec.status == FileChangeStatus.PROPOSED.value:
                    current_content = rec.new_content
                    break
            except ValueError:
                continue

        if current_content is None:
            if not target_path.exists() or not target_path.is_file():
                return False, f"Cannot edit non-existent file: '{rel_path}'. Use write_file to create new files."
            try:
                current_content = target_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return False, f"Failed to read file for editing: {exc}"

        if target_str not in current_content:
            return (
                False,
                f"Edit failed for '{rel_path}': Target text not found in file.\n"
                f"Ensure the target matches the exact whitespace, indentation, and characters in the existing file."
            )

        occurrences = current_content.count(target_str)
        new_content = current_content.replace(target_str, replacement)

        is_stub, stub_reason = is_placeholder_or_stub_content(new_content, rel_path)
        if is_stub:
            return (
                False,
                f"Edit rejected for '{rel_path}': Modified file would contain placeholder or stub code ({stub_reason})."
            )

        change_type = FileChangeType.MODIFY.value
        self.journal.record_change(rel_path, change_type, new_content=new_content)
        return True, f"Successfully edited '{rel_path}' (replaced {occurrences} occurrence(s), new size {len(new_content)} bytes). Queued for diff review."

    def _tool_search_symbols(self, query: str) -> tuple[bool, str]:
        """Searches indexed project symbols by name or kind."""
        if self.context_manager and hasattr(self.context_manager, "search_symbols"):
            matches = self.context_manager.search_symbols(query)
            if matches:
                lines = [f"{m['file_path']}:{m['line']}: {m['kind']} {m['name']} {m.get('details', '')}".strip() for m in matches[:30]]
                return True, f"Found {len(matches)} symbol match(es) for '{query}':\n" + "\n".join(lines)

        # Fallback regex search
        pattern = rf"\b(def|class|function|const|let)\s+([A-Za-z0-9_]*{re.escape(query)}[A-Za-z0-9_]*)"
        return self._tool_search_files(pattern)

    def _tool_write_file(self, rel_path: str, contents: str) -> tuple[bool, str]:
        # Validate that proposed content is substantive and not an empty file, stub, or placeholder
        is_stub, stub_reason = is_placeholder_or_stub_content(contents, rel_path)
        if is_stub:
            return (
                False,
                f"Content rejected for '{rel_path}': Placeholder or stub content detected ({stub_reason}). "
                "You must provide the complete, functional, production-ready code for this file without placeholders or stubs."
            )

        target = resolve_contained_path(self.project_root, rel_path)
        change_type = FileChangeType.MODIFY.value if target.exists() else FileChangeType.CREATE.value
        record = self.journal.record_change(rel_path, change_type, new_content=contents)
        return True, f"File modification proposed for '{rel_path}' ({len(contents)} bytes). Queued for diff review."

    def _tool_search_files(self, query: str, pattern: Optional[str] = None) -> tuple[bool, str]:
        matches = []
        try:
            regex = re.compile(query, re.IGNORECASE)
        except re.error as err:
            return False, f"Invalid regex pattern: {err}"

        for current, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file_name in files:
                if pattern and not fnmatch.fnmatch(file_name, pattern):
                    continue
                file_path = Path(current) / file_name
                if file_path.suffix.lower() not in TEXT_EXTENSIONS or file_path.stat().st_size > MAX_FILE_BYTES:
                    continue

                try:
                    rel = str(file_path.relative_to(self.project_root))
                    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    for idx, line in enumerate(lines, start=1):
                        if regex.search(line):
                            matches.append(f"{rel}:{idx}: {line.strip()[:150]}")
                            if len(matches) >= 50:
                                matches.append("... [Search truncated at 50 results]")
                                break
                    if len(matches) >= 50:
                        break
                except Exception:
                    continue
            if len(matches) >= 50:
                break

        if not matches:
            return True, f"No matches found for query: '{query}'"
        return True, "\n".join(matches)

    def _tool_list_directory(self, rel_path: str = "") -> tuple[bool, str]:
        target = resolve_contained_path(self.project_root, rel_path) if rel_path else self.project_root
        if not target.exists() or not target.is_dir():
            return False, f"Directory does not exist: '{rel_path}'"

        items = []
        try:
            for entry in sorted(os.listdir(target)):
                if entry in IGNORED_DIRS:
                    continue
                p = target / entry
                indicator = "/" if p.is_dir() else ""
                items.append(f"{entry}{indicator}")

            # Also surface any staged files in this directory from the journal
            for rec in self.journal.records:
                if rec.status == FileChangeStatus.PROPOSED.value:
                    try:
                        rec_target = resolve_contained_path(self.project_root, rec.rel_path)
                        if rec_target.parent == target:
                            name_str = f"{rec_target.name}"
                            if name_str not in items and f"{name_str}/" not in items:
                                items.append(name_str)
                    except ValueError:
                        continue

            return True, "\n".join(items) if items else "(Empty directory)"
        except Exception as exc:
            return False, f"Failed to list directory: {exc}"

    def _tool_create_directory(self, rel_path: str) -> tuple[bool, str]:
        target = resolve_contained_path(self.project_root, rel_path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return True, f"Directory created: '{rel_path}'"
        except Exception as exc:
            return False, f"Failed to create directory: {exc}"

    def _tool_run_tests(self, command: str) -> tuple[bool, str]:
        """Runs the approved test command in project root."""
        return self._tool_execute_command(command)

    def _generate_journal_diff(self, rel_path: Optional[str] = None) -> str:
        """
        Generates unified diff representation from AgentJournal.records for non-Git projects
        or when Git diff is unavailable.
        """
        diff_chunks = []
        target_path = rel_path.replace("\\", "/").lstrip("./") if rel_path else None
        matching_records = [
            r for r in self.journal.records
            if not target_path or r.rel_path.replace("\\", "/").lstrip("./") == target_path
        ]
        if not matching_records:
            return "(No proposed changes in AgentJournal)"

        import difflib
        for r in matching_records:
            clean_rel = r.rel_path.replace("\\", "/")
            old_lines = (r.old_content or "").splitlines(keepends=True)
            new_lines = (r.new_content or "").splitlines(keepends=True)
            unified = list(difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{clean_rel}",
                tofile=f"b/{clean_rel}",
            ))
            if unified:
                diff_chunks.append("".join(unified).strip())
            else:
                change_desc = r.change_type.upper()
                size = len(r.new_content or "")
                diff_chunks.append(f"--- a/{clean_rel}\n+++ b/{clean_rel}\n@@ {change_desc} ({size} bytes) @@\n+{r.new_content or ''}")
        return "\n\n".join(diff_chunks)

    def _tool_git_status(self) -> tuple[bool, str]:
        # Detect whether current project is a Git repository before querying Git
        if not GitService.is_git_repository(self.project_root):
            proposed_count = len([r for r in self.journal.records if r.status == FileChangeStatus.PROPOSED.value])
            return True, (
                "Notice: Current project is not a Git repository. "
                f"Proposed file modifications in AgentJournal: {proposed_count}. "
                "(Git status check is optional for non-Git projects; proceed with plan execution.)"
            )

        ok, msg, state = GitService.get_status(self.project_root)
        if not ok or state is None:
            return True, f"Notice: Git status check unavailable ({msg}). Continuing with AgentJournal tracking."
        lines = [
            f"Branch: {state.current_branch or 'None'}",
            f"Clean: {state.is_clean}",
            f"Staged changes ({len(state.staged_files)}): {[f.path for f in state.staged_files]}",
            f"Unstaged changes ({len(state.unstaged_files)}): {[f.path for f in state.unstaged_files]}",
            f"Untracked files ({len(state.untracked_files)}): {[f.path for f in state.untracked_files]}",
            f"Has conflicts: {bool(state.conflict_files)}",
        ]
        return True, "\n".join(lines)

    def _tool_git_diff(self, rel_path: Optional[str] = None, staged: bool = False) -> tuple[bool, str]:
        # Detect whether current project is a Git repository before querying Git diff
        if not GitService.is_git_repository(self.project_root):
            journal_diff = self._generate_journal_diff(rel_path)
            notice = (
                "Notice: Current project is not a Git repository. "
                "Git diff is not applicable, but proposed file modifications are tracked in AgentJournal:\n\n"
                f"{journal_diff}\n\n"
                "(All proposed modifications will be reviewed and approved via the Diff Review dialog. "
                "Git diff inspection is optional; do NOT retry inspect_git_diff. "
                "Please proceed to complete the step with step_complete.)"
            )
            return True, notice

        ok, msg, diff = GitService.get_diff(self.project_root, rel_file=rel_path, staged=staged)
        if not ok:
            journal_diff = self._generate_journal_diff(rel_path)
            return True, (
                f"Notice: Git diff unavailable ({msg}).\n"
                f"Proposed changes tracked in AgentJournal:\n\n{journal_diff}\n\n"
                "(Git diff inspection is optional; changes will be presented via Diff Review. Proceed with step_complete.)"
            )
        return True, diff if diff.strip() else "(No diff)"

    def _tool_execute_command(self, command: str) -> tuple[bool, str]:
        """
        Safely executes an approved shell command with cwd=project_root.
        Prevents terminal popups using CREATE_NO_WINDOW.
        """
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            res = subprocess.run(
                command,
                cwd=str(self.project_root),
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=flags,
            )
            out = res.stdout.strip()
            err = res.stderr.strip()
            output_parts = []
            if out:
                output_parts.append(f"STDOUT:\n{out}")
            if err:
                output_parts.append(f"STDERR:\n{err}")
            output_parts.append(f"Exit code: {res.returncode}")
            return (res.returncode == 0), "\n\n".join(output_parts)
        except subprocess.TimeoutExpired:
            return False, "Command timed out after 60 seconds."
        except Exception as exc:
            return False, f"Command execution error: {exc}"

