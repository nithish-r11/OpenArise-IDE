"""Desktop-owned JSONL host. Imports the protected backend; never duplicates its writer."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid

# Fixed repository source, not the selected project, supplies backend modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-engine"))
from app.tools.fs import ReadFileTool, WriteFileTool, _is_safe_path
from app.tools.permissions import PermissionManager, PermissionAction

MAX_BYTES = 2 * 1024 * 1024
IGNORED = {".git", ".venv", "venv", ".openarise", "__pycache__", ".pytest_cache",
           "node_modules", "dist", "dist-electron", "build"}

class FileError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message

class FileHost:
    def __init__(self, root, permissions=None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise FileError("access_denied", "Choose an existing project directory.")
        self.permissions = permissions or PermissionManager(test_mode=False)
        self.reader = ReadFileTool(str(self.root))
        self.writer = WriteFileTool(str(self.root))
        self.opened = {}
        self.workspace = None

    def target(self, relative, directory=False):
        if not isinstance(relative, str) or len(relative) > 2048 or "\\" in relative or ":" in relative:
            raise FileError("access_denied", "This path is not accessible.")
        parts = PurePosixPath(relative).parts
        if relative.startswith("/") or any(p in ("..", ".") or p.lower() in IGNORED for p in parts):
            raise FileError("access_denied", "This path is not accessible.")
        target = self.root
        for part in parts:
            target = target / part
            if target.is_symlink() or target.is_junction():
                raise FileError("access_denied", "Linked files and folders are not supported.")
        if not parts and directory:
            return self.root
        if not parts or not _is_safe_path(str(self.root), relative):
            raise FileError("access_denied", "This path is protected.")
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise FileError("access_denied", "This path is outside the project.")
        if resolved.is_file() and resolved.stat().st_nlink > 1:
            raise FileError("access_denied", "Files with multiple hard links are not supported.")
        return resolved

    def list_directory(self, relative):
        target = self.target(relative, directory=True)
        if not target.is_dir():
            raise FileError("not_found", "Folder is no longer available.")
        entries = []
        with os.scandir(target) as children:
            for child in children:
                rel = (PurePosixPath(relative) / child.name).as_posix()
                if child.name.lower() in IGNORED:
                    continue
                try:
                    item = self.target(rel)
                    if item.is_dir() or item.is_file():
                        entries.append({"name": child.name, "path": rel, "kind": "folder" if item.is_dir() else "file"})
                except (FileError, OSError):
                    continue
                if len(entries) > 2000:
                    raise FileError("too_large", "Folder has more than 2,000 visible entries. Open a smaller project folder.")
        return sorted(entries, key=lambda e: (e["kind"] != "folder", e["name"].casefold()))

    def digest(self, target):
        if not target.is_file():
            raise FileError("not_found", "File is no longer available.")
        if target.stat().st_size > MAX_BYTES:
            raise FileError("too_large", "Files larger than 2 MiB cannot be opened.")
        return hashlib.sha256(target.read_bytes()).hexdigest()

    def read_file(self, relative):
        target = self.target(relative)
        before = self.digest(target)
        call_id = str(uuid.uuid4())
        if not self.permissions.check_permission(call_id, self.reader.risk_level):
            raise FileError("permission_required", "Read access is not permitted.")
        content = self.reader.execute(path=relative)["content"]
        if "\x00" in content:
            raise FileError("unsupported_encoding", "Binary files cannot be opened in the text editor.")
        if before != self.digest(target):
            raise FileError("conflict", "File changed while opening. Try again.")
        read_only = target.suffix.lower() not in (".py", ".pyw") or not bool(target.stat().st_mode & stat.S_IWRITE)
        self.opened[relative] = before
        return {"path": relative, "content": content, "revision": before, "readOnly": read_only}

    def save_file(self, params):
        relative, content, revision = params["path"], params["content"], params["revision"]
        target = self.target(relative)
        if target.suffix.lower() not in (".py", ".pyw") or not target.stat().st_mode & stat.S_IWRITE:
            raise FileError("read_only", "This file is read-only. Phase 2 supports saving Python files.")
        if len(content.encode("utf-8")) > MAX_BYTES or "\x00" in content:
            raise FileError("too_large", "The editor buffer exceeds the supported text size.")
        if relative not in self.opened or self.opened[relative] != revision or self.digest(target) != revision:
            raise FileError("conflict", "File changed on disk. Your edits are retained; reopen the file after resolving the conflict.")
        # The dedicated Save command is a human-authorized buffer write, not an agent action.
        # Root, path, content and revision are retained for this synchronous call only.
        call_id = str(uuid.uuid4())
        action = self.permissions.get_action_for_risk(self.writer.risk_level)
        if action == PermissionAction.ASK:
            self.permissions.grant_approval(call_id)
        try:
            if not self.permissions.check_permission(call_id, self.writer.risk_level):
                raise FileError("permission_required", "Saving is blocked by the current permission policy.")
            # Revalidate immediately before delegating; no independent write implementation.
            self.target(relative)
            if self.digest(target) != revision:
                raise FileError("conflict", "File changed on disk. Save was not performed.")
            self.writer.execute(path=relative, content=content, overwrite=True)
        finally:
            self.permissions.revoke_approval(call_id)
        return self.read_file(relative)

    def environment(self):
        from app.environment.detector import EnvironmentDetector
        info = EnvironmentDetector().detect(str(self.root))
        if info.virtualenv_present:
            folder = Path(info.virtualenv_path)
            executable = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            # Windows linked environments may escape the selected workspace.
            linked = folder.is_symlink() or folder.is_junction()
            available = info.virtualenv_usable and not linked
            return {"executable": str(executable), "label": "Project virtual environment",
                    "status": "ready" if available else "unavailable",
                    "message": "Selected project environment." if available else "Project environment is missing its interpreter or is linked. No fallback was selected."}
        return {"executable": info.python_executable or "", "label": "Backend environment (no project venv)",
                "status": "ready" if info.python_available else "unavailable",
                "message": "No .venv or venv detected; using the explicitly displayed backend interpreter."}

    def validate_run(self, params):
        relative, revision = params["path"], params["revision"]
        target = self.target(relative)
        if target.suffix.lower() not in (".py", ".pyw"):
            raise FileError("access_denied", "Only saved Python files can run.")
        if self.opened.get(relative) != revision or self.digest(target) != revision:
            raise FileError("conflict", "File changed on disk. Reopen and review it before running.")
        return {"path": str(target)}

    def dispatch(self, method, params):
        if method == "environment" and params == {}:
            return self.environment()
        if method == "validate_run" and set(params) == {"path", "revision"}:
            return self.validate_run(params)
        if method == "info" and params == {}:
            return {"name": self.root.name or str(self.root), "rootPath": str(self.root)}
        if method == "list" and set(params) == {"path"}:
            return self.list_directory(params["path"])
        if method == "read" and set(params) == {"path"}:
            return self.read_file(params["path"])
        if method == "save" and set(params) == {"path", "content", "revision"} and all(isinstance(v, str) for v in params.values()):
            return self.save_file(params)
        if method == "observe" and params == {}:
            from app.api.services import ProjectWorkspaceService
            if self.workspace is None:
                self.workspace = ProjectWorkspaceService(str(self.root))
            else:
                self.workspace.refresh_workspace()
            state = self.workspace.get_project_state().data
            return {"files": len(state["files"]), "modules": len(state["python_modules"]), "observedAt": state["scan_timestamp"]}
        if method == "shutdown" and params == {}:
            if self.workspace:
                self.workspace.shutdown()
            return {"closed": True}
        raise FileError("invalid_request", "Unsupported desktop file operation.")

def main():
    host = FileHost(sys.argv[1])
    while True:
        line = sys.stdin.buffer.readline(16 * MAX_BYTES + 1)
        if not line:
            break
        if len(line) > 16 * MAX_BYTES:
            break
        request_id = "invalid"
        method = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or set(request) != {"id", "method", "params"} or not isinstance(request["id"], str) or not isinstance(request["params"], dict):
                raise FileError("invalid_request", "Invalid desktop file request.")
            request_id, method = request["id"], request["method"]
            result = {"id": request_id, "ok": True, "data": host.dispatch(method, request["params"])}
        except FileError as error:
            result = {"id": request_id, "ok": False, "code": error.code, "message": error.message}
        except UnicodeError:
            result = {"id": request_id, "ok": False, "code": "unsupported_encoding", "message": "Only UTF-8 text files are supported."}
        except FileNotFoundError:
            result = {"id": request_id, "ok": False, "code": "not_found", "message": "The selected file or folder no longer exists."}
        except PermissionError:
            result = {"id": request_id, "ok": False, "code": "access_denied", "message": "Access to this file or folder is denied."}
        except Exception:
            result = {"id": request_id, "ok": False, "code": "io_error", "message": "The file operation could not be completed."}
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if method == "shutdown":
            break

if __name__ == "__main__":
    main()
