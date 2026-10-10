"""Resolve only observed npm test/build scripts; never accept an executable or shell."""
import shutil
from pathlib import Path
from app.project.capabilities import detect_capabilities
from app.project.models import ProjectState, ProjectInfo
from app.project.scanner import ProjectScanner


def project_commands(root):
    scanner = ProjectScanner(root)
    files, _ = scanner.scan_files()
    return detect_capabilities(root, ProjectState(project_info=ProjectInfo(root_path=str(root), name=Path(root).name), files=files))["commands"]


def resolve_command(root, command, revision):
    root = Path(root).resolve()
    current = next((c for c in project_commands(str(root)) if c["id"] == command["id"]), None)
    if not current or current["revision"] != revision or current["action"] not in ("test", "build"):
        raise ValueError("The package manifest changed. Refresh and approve the new command.")
    if not current["supported"] or current["manager"] != "npm":
        raise ValueError(current["reason"] or "This package manager is not enabled.")
    directory = root if current["directory"] == "." else root / current["directory"]
    cursor = directory
    while cursor != root:
        if cursor.is_symlink() or cursor.is_junction():
            raise ValueError("Linked project directories cannot execute commands.")
        cursor = cursor.parent
    directory = directory.resolve(strict=True)
    if not directory.is_relative_to(root):
        raise ValueError("Command directory is outside this project.")
    node = shutil.which("node")
    if not node or Path(node).resolve().is_relative_to(root):
        raise ValueError("Node.js is unavailable outside this project. Install Node.js and reopen OpenArise.")
    node = Path(node).resolve()
    cli = node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not cli.is_file() or cli.resolve().is_relative_to(root):
        raise ValueError("npm is unavailable beside Node.js. Repair the Node.js installation.")
    return {"executable": str(node), "arguments": [str(cli), "run", current["action"], "--ignore-scripts"],
            "directory": str(directory), "label": current["label"], "test": current["action"] == "test"}
