"""Desktop-owned JSONL host. Imports the protected backend; never duplicates its writer."""
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid

# Fixed repository source, not the selected project, supplies backend modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-engine"))
from app.tools.fs import ReadFileTool, WriteFileTool, _is_safe_path
from app.tools.permissions import PermissionManager, PermissionAction
from app.project.capabilities import TEXT_EXTENSIONS

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

    def target(self, relative, directory=False, must_exist=True):
        if not isinstance(relative, str) or len(relative) > 2048 or "\\" in relative or ":" in relative:
            raise FileError("access_denied", "This path is not accessible.")
        parts = PurePosixPath(relative).parts
        if relative and any(not p or p in ("..", ".") or re.search(r'[<>"|?*\x00-\x1f]', p) or p.endswith((".", " "))
                            or re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p, re.I) for p in relative.split("/")):
            raise FileError("access_denied", "Use a valid relative path in this project.")
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
        resolved = target.resolve(strict=must_exist)
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

    def search_files(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 120:
            raise FileError("invalid_request", "Enter a filename or relative path (up to 120 characters).")
        self.capabilities()
        entries = []
        for file in self.workspace.state_manager.state.files:
            if query.casefold() not in file.relative_path.casefold():
                continue
            try:
                self.target(file.relative_path)
                entries.append({"name": Path(file.relative_path).name, "path": file.relative_path, "kind": "file"})
            except (FileError, OSError):
                continue
            if len(entries) == 200:
                break
        return sorted(entries, key=lambda e: e["path"].casefold())

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
        read_only = target.suffix.lower() not in TEXT_EXTENSIONS or not bool(target.stat().st_mode & stat.S_IWRITE)
        self.opened[relative] = before
        return {"path": relative, "content": content, "revision": before, "readOnly": read_only}

    def save_file(self, params):
        relative, content, revision = params["path"], params["content"], params["revision"]
        target = self.target(relative)
        if target.suffix.lower() not in TEXT_EXTENSIONS or not target.stat().st_mode & stat.S_IWRITE:
            raise FileError("read_only", "This file is read-only. Supported UTF-8 source and configuration files can be edited.")
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

    def create_file(self, relative):
        target = self.target(relative, must_exist=False)
        if target.exists():
            raise FileError("conflict", "A file already exists at this path. Open it instead; no content was replaced.")
        if target.suffix.lower() not in TEXT_EXTENSIONS:
            raise FileError("read_only", "Choose a supported source or configuration extension, such as .py, .tsx, .js or .json.")
        if not target.parent.is_dir():
            raise FileError("not_found", "The parent folder does not exist. Choose an existing folder in this project.")
        call_id = str(uuid.uuid4())
        if self.permissions.get_action_for_risk(self.writer.risk_level) == PermissionAction.ASK:
            self.permissions.grant_approval(call_id)
        try:
            if not self.permissions.check_permission(call_id, self.writer.risk_level):
                raise FileError("permission_required", "File creation is blocked by the current permission policy.")
            self.target(relative, must_exist=False)
            self.writer.execute(path=relative, content="", overwrite=False)
        except FileExistsError:
            raise FileError("conflict", "This path was created by another operation. Open it instead.") from None
        finally:
            self.permissions.revoke_approval(call_id)
        return self.read_file(relative)

    def capabilities(self):
        from app.api.services import ProjectWorkspaceService
        if self.workspace is None:
            self.workspace = ProjectWorkspaceService(str(self.root))
        else:
            self.workspace.refresh_workspace()
        return self.workspace.get_project_capabilities().data

    def create_folder(self, relative):
        target = self.target(relative, must_exist=False)
        if target.exists():
            raise FileError("conflict", "A file or folder already exists here. Nothing was replaced.")
        if not target.parent.is_dir():
            raise FileError("not_found", "Create the parent folder first.")
        call_id = str(uuid.uuid4())
        if self.permissions.get_action_for_risk(self.writer.risk_level) == PermissionAction.ASK:
            self.permissions.grant_approval(call_id)
        try:
            if not self.permissions.check_permission(call_id, self.writer.risk_level):
                raise FileError("permission_required", "Folder creation is blocked by the permission policy.")
            self.target(relative, must_exist=False).mkdir()
        except FileExistsError:
            raise FileError("conflict", "This path was created by another operation. Refresh Explorer.") from None
        finally:
            self.permissions.revoke_approval(call_id)
        return {"path": relative, "kind": "folder"}

    def inspect_rename(self, relative):
        target = self.target(relative)
        rows = [target]
        if target.is_dir():
            for directory, folders, files in os.walk(target, followlinks=False):
                for name in sorted(folders + files):
                    item = Path(directory) / name
                    self.target(item.relative_to(self.root).as_posix())
                    rows.append(item)
                    if len(rows) > 2000:
                        raise FileError("too_large", "Close the project and rename this large folder outside OpenArise.")
        digest = hashlib.sha256()
        total_bytes = 0
        for item in sorted(rows):
            info = item.stat()
            digest.update(str((item.relative_to(target) if item != target else ".", info.st_ino, info.st_mode, info.st_mtime_ns)).encode())
            if item.is_file():
                total_bytes += info.st_size
                if total_bytes > 8 * MAX_BYTES:
                    raise FileError("too_large", "This folder is too large for safe rename review. Close it and rename it outside OpenArise.")
                digest.update(self.digest(item).encode())
        return {"path": relative, "kind": "folder" if target.is_dir() else "file", "revision": digest.hexdigest()}

    def rename_path(self, params):
        relative, destination, revision = params["path"], params["destination"], params["revision"]
        if os.name != "nt":
            raise FileError("unavailable", "Safe no-overwrite rename is enabled only on Windows.")
        source = self.target(relative)
        target = self.target(destination, must_exist=False)
        if source == target or target.exists() or source in target.parents:
            raise FileError("conflict", "Choose a new path. Existing files and folders are never replaced.")
        if not target.parent.is_dir():
            raise FileError("not_found", "The destination folder does not exist.")
        if self.inspect_rename(relative)["revision"] != revision:
            raise FileError("conflict", "The file or folder changed after review. Refresh and review its new name.")
        call_id = str(uuid.uuid4())
        if self.permissions.get_action_for_risk(self.writer.risk_level) == PermissionAction.ASK:
            self.permissions.grant_approval(call_id)
        try:
            if not self.permissions.check_permission(call_id, self.writer.risk_level):
                raise FileError("permission_required", "Renaming is blocked by the permission policy.")
            self.target(relative); self.target(destination, must_exist=False)
            if self.inspect_rename(relative)["revision"] != revision:
                raise FileError("conflict", "Contents changed. Rename was not performed.")
            # Windows MoveFile semantics fail if the destination exists, including races.
            os.rename(source, target)
        except FileExistsError:
            raise FileError("conflict", "The destination already exists. Nothing was replaced.") from None
        finally:
            self.permissions.revoke_approval(call_id)
        self.opened = {p: r for p, r in self.opened.items() if p != relative and not p.startswith(relative + "/")}
        return {"path": destination, "kind": "folder" if target.is_dir() else "file"}

    def command_capability(self, command_id):
        for command in self.capabilities()["commands"]:
            if command["id"] == command_id and command["kind"] == "node_script":
                return command
        raise FileError("invalid_request", "This project command is no longer available. Refresh project capabilities.")

    def prepare_command(self, params):
        from app.tools.permissions import RiskLevel
        from app.project.commands import resolve_command
        command = self.command_capability(params["capabilityId"])
        if not command["supported"]:
            raise FileError("unavailable", command["reason"])
        if command["revision"] != params["revision"]:
            raise FileError("conflict", "The package manifest changed after command review. Refresh and approve the new command.")
        call_id = str(uuid.uuid4())
        if params["approved"] and self.permissions.get_action_for_risk(RiskLevel.EXECUTE) == PermissionAction.ASK:
            self.permissions.grant_approval(call_id)
        try:
            if not self.permissions.check_permission(call_id, RiskLevel.EXECUTE):
                raise FileError("permission_required", "This project script requires explicit approval. No command ran.")
            try:
                return resolve_command(str(self.root), command, params["revision"])
            except ValueError as error:
                raise FileError("unavailable", str(error)) from None
        finally:
            self.permissions.revoke_approval(call_id)

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
        if method == "command_capability" and set(params) == {"capabilityId"}:
            return self.command_capability(params["capabilityId"])
        if method == "prepare_command" and set(params) == {"capabilityId", "revision", "approved"} and type(params["approved"]) is bool:
            return self.prepare_command(params)
        if method == "info" and params == {}:
            return {"name": self.root.name or str(self.root), "rootPath": str(self.root)}
        if method == "list" and set(params) == {"path"}:
            return self.list_directory(params["path"])
        if method == "read" and set(params) == {"path"}:
            return self.read_file(params["path"])
        if method == "create" and set(params) == {"path"}:
            return self.create_file(params["path"])
        if method == "create_folder" and set(params) == {"path"}:
            return self.create_folder(params["path"])
        if method == "inspect_rename" and set(params) == {"path"}:
            return self.inspect_rename(params["path"])
        if method == "rename" and set(params) == {"path", "destination", "revision"} and all(isinstance(v, str) for v in params.values()):
            return self.rename_path(params)
        if method == "search" and set(params) == {"query"}:
            return self.search_files(params["query"])
        if method == "save" and set(params) == {"path", "content", "revision"} and all(isinstance(v, str) for v in params.values()):
            return self.save_file(params)
        if method == "observe" and params == {}:
            from app.api.services import ProjectWorkspaceService
            if self.workspace is None:
                self.workspace = ProjectWorkspaceService(str(self.root))
            else:
                self.workspace.refresh_workspace()
            state = self.workspace.get_project_state().data
            return {"files": len(state["files"]), "modules": len(state["python_modules"]), "observedAt": state["scan_timestamp"],
                    "capabilities": self.workspace.get_project_capabilities().data}
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
