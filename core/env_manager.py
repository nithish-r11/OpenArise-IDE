"""
OpenArise IDE - Development Environment Manager
Detects 16 system developer tools, manages project-specific Python virtual
environments and interpreters, detects Node package managers, and provides SDK guidance.
"""

import os
import re
import sys
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple


@dataclass
class ToolInfo:
    name: str
    installed: bool
    version: str
    executable_path: Optional[str]
    category: str
    doc_url: str


TOOL_DEFINITIONS = [
    {
        "name": "Python",
        "commands": ["python", "py"],
        "flag": "--version",
        "category": "Language",
        "doc_url": "https://www.python.org/downloads/",
    },
    {
        "name": "pip",
        "commands": ["pip", "pip3"],
        "flag": "--version",
        "category": "Package Manager",
        "doc_url": "https://pip.pypa.io/",
    },
    {
        "name": "Node.js",
        "commands": ["node"],
        "flag": "--version",
        "category": "Language",
        "doc_url": "https://nodejs.org/",
    },
    {
        "name": "npm",
        "commands": ["npm.cmd" if sys.platform == "win32" else "npm", "npm"],
        "flag": "--version",
        "category": "Package Manager",
        "doc_url": "https://www.npmjs.com/",
    },
    {
        "name": "pnpm",
        "commands": ["pnpm.cmd" if sys.platform == "win32" else "pnpm", "pnpm"],
        "flag": "--version",
        "category": "Package Manager",
        "doc_url": "https://pnpm.io/",
    },
    {
        "name": "Java JDK",
        "commands": ["javac", "java"],
        "flag": "-version",
        "category": "Language",
        "doc_url": "https://adoptium.net/",
    },
    {
        "name": "Maven",
        "commands": ["mvn.cmd" if sys.platform == "win32" else "mvn", "mvn"],
        "flag": "-version",
        "category": "Build Tool",
        "doc_url": "https://maven.apache.org/",
    },
    {
        "name": "Gradle",
        "commands": ["gradle.bat" if sys.platform == "win32" else "gradle", "gradle"],
        "flag": "-version",
        "category": "Build Tool",
        "doc_url": "https://gradle.org/",
    },
    {
        "name": "Flutter",
        "commands": ["flutter.bat" if sys.platform == "win32" else "flutter", "flutter"],
        "flag": "--version",
        "category": "Framework SDK",
        "doc_url": "https://flutter.dev/",
    },
    {
        "name": "Dart",
        "commands": ["dart.bat" if sys.platform == "win32" else "dart", "dart"],
        "flag": "--version",
        "category": "Language",
        "doc_url": "https://dart.dev/",
    },
    {
        "name": ".NET SDK",
        "commands": ["dotnet"],
        "flag": "--version",
        "category": "Framework SDK",
        "doc_url": "https://dotnet.microsoft.com/download",
    },
    {
        "name": "Rust",
        "commands": ["rustc"],
        "flag": "--version",
        "category": "Language",
        "doc_url": "https://www.rust-lang.org/tools/install",
    },
    {
        "name": "Cargo",
        "commands": ["cargo"],
        "flag": "--version",
        "category": "Package Manager",
        "doc_url": "https://doc.rust-lang.org/cargo/",
    },
    {
        "name": "Go",
        "commands": ["go"],
        "flag": "version",
        "category": "Language",
        "doc_url": "https://go.dev/dl/",
    },
    {
        "name": "Git",
        "commands": ["git"],
        "flag": "--version",
        "category": "VCS",
        "doc_url": "https://git-scm.com/",
    },
    {
        "name": "CMake",
        "commands": ["cmake"],
        "flag": "--version",
        "category": "Build Tool",
        "doc_url": "https://cmake.org/download/",
    },
]


class EnvironmentManager:
    """
    Manages developer toolchains, Python virtual environments and interpreters,
    and Node.js package managers.
    """

    _cache: Dict[str, ToolInfo] = {}

    @classmethod
    def detect_tool(cls, name: str, force_refresh: bool = False) -> ToolInfo:
        if not force_refresh and name in cls._cache:
            return cls._cache[name]

        target_def = next((d for d in TOOL_DEFINITIONS if d["name"].lower() == name.lower()), None)
        if not target_def:
            info = ToolInfo(
                name=name,
                installed=False,
                version="Unknown",
                executable_path=None,
                category="Unknown",
                doc_url="",
            )
            cls._cache[name] = info
            return info

        category = target_def["category"]
        doc_url = target_def["doc_url"]

        # Search commands
        found_exe = None
        for cmd in target_def["commands"]:
            resolved = shutil.which(cmd)
            if resolved:
                found_exe = resolved
                break

        if not found_exe:
            info = ToolInfo(
                name=target_def["name"],
                installed=False,
                version="Not Installed",
                executable_path=None,
                category=category,
                doc_url=doc_url,
            )
            cls._cache[name] = info
            return info

        # Execute version flag with timeout guard
        version_str = "Installed"
        try:
            flag = target_def["flag"]
            cmd_args = [found_exe, flag]
            proc = subprocess.run(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2.0,
                check=False,
            )
            raw_out = (proc.stdout or proc.stderr or "").strip()
            # Extract first line of version output
            if raw_out:
                first_line = raw_out.splitlines()[0]
                version_str = first_line.strip()
        except (subprocess.TimeoutExpired, OSError, Exception):
            version_str = "Installed"

        info = ToolInfo(
            name=target_def["name"],
            installed=True,
            version=version_str,
            executable_path=found_exe,
            category=category,
            doc_url=doc_url,
        )
        cls._cache[name] = info
        return info

    @classmethod
    def detect_all_tools(cls, force_refresh: bool = False) -> Dict[str, ToolInfo]:
        results = {}
        for defn in TOOL_DEFINITIONS:
            name = defn["name"]
            results[name] = cls.detect_tool(name, force_refresh=force_refresh)
        return results

    @classmethod
    def detect_python_interpreters(cls, project_root: Optional[Path] = None) -> List[Path]:
        """
        Discovers all available Python interpreters on the host system,
        prioritizing project virtualenv.
        """
        candidates: List[Path] = []

        # 1. Project-specific virtualenv
        if project_root:
            p_venv = Path(project_root) / ".venv" / "Scripts" / "python.exe"
            if p_venv.exists():
                candidates.append(p_venv.resolve())
            p_venv_bin = Path(project_root) / ".venv" / "bin" / "python"
            if p_venv_bin.exists():
                candidates.append(p_venv_bin.resolve())

        # 2. Application runtime virtualenv
        app_venv = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
        if app_venv.exists():
            candidates.append(app_venv.resolve())

        # 3. Current active running sys.executable
        if sys.executable:
            candidates.append(Path(sys.executable).resolve())

        # 4. PATH python / py
        for p_name in ("python", "python3", "py"):
            wh = shutil.which(p_name)
            if wh:
                p_path = Path(wh).resolve()
                if p_path not in candidates and p_path.exists():
                    candidates.append(p_path)

        # 5. Standard Windows installation paths
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            search_dirs = [
                Path("C:/Python312"), Path("C:/Python311"), Path("C:/Python310"),
                Path("C:/Program Files/Python312"), Path("C:/Program Files/Python311"), Path("C:/Program Files/Python310"),
            ]
            if local_appdata:
                search_dirs.append(Path(local_appdata) / "Programs" / "Python" / "Python312")
                search_dirs.append(Path(local_appdata) / "Programs" / "Python" / "Python311")
                search_dirs.append(Path(local_appdata) / "Programs" / "Python" / "Python310")

            for s_dir in search_dirs:
                exe = s_dir / "python.exe"
                if exe.exists() and exe.resolve() not in candidates:
                    candidates.append(exe.resolve())

        # Filter duplicates while preserving order
        unique: List[Path] = []
        for c in candidates:
            if c not in unique and c.is_file():
                unique.append(c)

        return unique

    @classmethod
    def get_project_interpreter(cls, project_root: Optional[Path], settings_manager=None) -> Path:
        """
        Resolves the preferred Python interpreter for the active project.
        Precedence:
        1. Explicitly configured interpreter in settings for this project.
        2. Project `.venv/Scripts/python.exe`.
        3. App `.venv/Scripts/python.exe`.
        4. sys.executable.
        """
        if settings_manager and project_root:
            proj_str = str(Path(project_root).resolve())
            saved_interpreters = settings_manager.get("project_interpreters", {})
            if proj_str in saved_interpreters:
                saved = Path(saved_interpreters[proj_str])
                if saved.exists():
                    return saved

        # Project .venv
        if project_root:
            p_venv = Path(project_root) / ".venv" / "Scripts" / "python.exe"
            if p_venv.exists():
                return p_venv.resolve()
            p_venv_nix = Path(project_root) / ".venv" / "bin" / "python"
            if p_venv_nix.exists():
                return p_venv_nix.resolve()

        # Application .venv
        app_venv = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
        if app_venv.exists():
            return app_venv.resolve()

        return Path(sys.executable).resolve()

    @classmethod
    def set_project_interpreter(cls, project_root: Path, interpreter_path: Path, settings_manager=None):
        """
        Persists the chosen interpreter for a given project in settings.
        """
        if not settings_manager or not project_root:
            return
        proj_str = str(Path(project_root).resolve())
        saved_interpreters = settings_manager.get("project_interpreters", {})
        saved_interpreters[proj_str] = str(Path(interpreter_path).resolve())
        settings_manager.set("project_interpreters", saved_interpreters)

    @classmethod
    def create_virtualenv(cls, target_dir: Path, python_exe: Optional[Path] = None) -> Tuple[bool, str]:
        """
        Creates a virtual environment at target_dir using python_exe.
        """
        exe = str(python_exe or sys.executable)
        target = Path(target_dir).resolve()
        try:
            proc = subprocess.run(
                [exe, "-m", "venv", str(target)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if proc.returncode == 0 and (target / "Scripts" / "python.exe").exists() or (target / "bin" / "python").exists():
                return True, "Virtual environment created successfully."
            return False, proc.stderr or proc.stdout or "Failed creating virtualenv."
        except Exception as exc:
            return False, str(exc)

    @classmethod
    def detect_package_manager(cls, project_root: Path) -> str:
        """
        Identifies whether a Node project prefers pnpm, yarn, or npm based on lockfiles.
        """
        root = Path(project_root).resolve()
        if (root / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (root / "yarn.lock").exists():
            return "yarn"
        if (root / "package-lock.json").exists():
            return "npm"
        return "npm"

    @classmethod
    def detect_project_environment(cls, project_root: Optional[Path]) -> Dict:
        """
        Inspects an opened project folder and returns its environment attributes.
        """
        if not project_root:
            return {"has_python": False, "has_node": False, "venv_exists": False}

        root = Path(project_root).resolve()
        has_reqs = (root / "requirements.txt").exists() or (root / "pyproject.toml").exists()
        has_py_files = any(root.glob("*.py"))
        has_pkg_json = (root / "package.json").exists()
        venv_exists = (root / ".venv" / "Scripts" / "python.exe").exists() or (root / ".venv" / "bin" / "python").exists()

        pkg_mgr = cls.detect_package_manager(root) if has_pkg_json else None

        return {
            "has_python": has_reqs or has_py_files,
            "has_node": has_pkg_json,
            "venv_exists": venv_exists,
            "package_manager": pkg_mgr,
            "requirements_path": str(root / "requirements.txt") if (root / "requirements.txt").exists() else None,
            "package_json_path": str(root / "package.json") if has_pkg_json else None,
        }

