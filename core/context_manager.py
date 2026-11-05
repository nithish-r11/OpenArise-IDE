"""
Codebase Understanding and Reusable Context Engine for OpenArise IDE.
Provides structured project profiling, framework/dependency detection,
compact file tree representations, AST/regex symbol extraction, and token-optimized
workspace summaries for Cursor-level AI coding.
"""

from __future__ import annotations
import ast
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".idea", "dist", "build", ".openarise_backups", ".pytest_cache"
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".json", ".yaml",
    ".yml", ".toml", ".md", ".txt", ".rst", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb", ".sh", ".bat", ".sql", ".xml"
}
MAX_FILE_BYTES = 512_000


@dataclass
class ProjectSymbol:
    name: str
    kind: str  # "function", "class", "route", "variable", "component"
    line: int
    file_path: str
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "file_path": self.file_path,
            "details": self.details,
        }


@dataclass
class ProjectProfile:
    project_type: str = "generic"
    frameworks: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    file_tree: list[str] = field(default_factory=list)
    symbols: dict[str, list[ProjectSymbol]] = field(default_factory=dict)
    summary_text: str = ""
    last_updated: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_type": self.project_type,
            "frameworks": self.frameworks,
            "entrypoints": self.entrypoints,
            "dependencies": self.dependencies,
            "file_tree": self.file_tree,
            "symbols_count": sum(len(syms) for syms in self.symbols.values()),
            "last_updated": self.last_updated,
        }


def extract_python_symbols(code: str, rel_path: str) -> list[ProjectSymbol]:
    """Extracts classes, functions, and web framework route decorators from Python code using AST."""
    symbols: list[ProjectSymbol] = []
    try:
        tree = ast.parse(code, filename=rel_path)
    except SyntaxError:
        # Fallback to simple regex if code has syntax errors during in-progress edits
        for line_no, line in enumerate(code.splitlines(), start=1):
            m = re.match(r"^\s*(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            if m:
                kind = "class" if m.group(1) == "class" else "function"
                symbols.append(ProjectSymbol(name=m.group(2), kind=kind, line=line_no, file_path=rel_path))
        return symbols

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(ProjectSymbol(
                name=node.name,
                kind="class",
                line=node.lineno,
                file_path=rel_path,
                details=f"class {node.name}"
            ))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check for route decorators (e.g., @app.get, @router.post, @app.route)
            is_route = False
            route_detail = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in ("get", "post", "put", "delete", "patch", "route"):
                        is_route = True
                        route_detail = f"@{dec.func.attr}"
            kind = "route" if is_route else "function"
            symbols.append(ProjectSymbol(
                name=node.name,
                kind=kind,
                line=node.lineno,
                file_path=rel_path,
                details=route_detail or f"def {node.name}"
            ))

    return symbols


def extract_javascript_symbols(code: str, rel_path: str) -> list[ProjectSymbol]:
    """Extracts classes, exported functions, and React components from JS/TS code using regex."""
    symbols: list[ProjectSymbol] = []
    lines = code.splitlines()

    func_pattern = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)")
    arrow_pattern = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(")
    class_pattern = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_$]+)")

    for line_no, line in enumerate(lines, start=1):
        m_cls = class_pattern.search(line)
        if m_cls:
            symbols.append(ProjectSymbol(name=m_cls.group(1), kind="class", line=line_no, file_path=rel_path))
            continue
        m_func = func_pattern.search(line)
        if m_func:
            name = m_func.group(1)
            kind = "component" if name[0].isupper() else "function"
            symbols.append(ProjectSymbol(name=name, kind=kind, line=line_no, file_path=rel_path))
            continue
        m_arrow = arrow_pattern.search(line)
        if m_arrow:
            name = m_arrow.group(1)
            kind = "component" if name[0].isupper() else "function"
            symbols.append(ProjectSymbol(name=name, kind=kind, line=line_no, file_path=rel_path))

    return symbols


class ProjectIndexer(QThread):
    indexed = pyqtSignal(dict)
    progress = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, project_root: Path | str, parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()

    def run(self):
        try:
            context: dict[str, str] = {}
            for current, dirs, names in os.walk(self.project_root):
                if self.isInterruptionRequested():
                    return
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for name in names:
                    if self.isInterruptionRequested():
                        return
                    path = Path(current) / name
                    try:
                        if path.suffix.lower() not in TEXT_EXTENSIONS or path.stat().st_size > MAX_FILE_BYTES:
                            continue
                        relative = str(path.relative_to(self.project_root)).replace("\\", "/")
                        content = path.read_text(encoding="utf-8", errors="replace")
                        context[relative] = content
                        self.progress.emit(f"Indexed {relative}")
                    except (OSError, UnicodeError):
                        continue
            self.indexed.emit(context)
        except Exception as exc:
            self.failed.emit(f"Project indexing failed: {exc}")


class ContextManager:
    """
    Central Project Understanding and Context Cache for OpenArise IDE.
    Maintains active file memory, project architecture profiling, dependency inspection,
    and fast symbol resolution with minimal prompt overhead.
    """

    def __init__(self):
        self.root: Optional[Path] = None
        self.files: dict[str, str] = {}
        self._profile: Optional[ProjectProfile] = None

    def set_project(self, root: Path | str):
        self.root = Path(root).resolve()
        self.files = {}
        self._profile = None

    def update_index(self, mapping: dict[str, str]):
        self.files = {k.replace("\\", "/"): v for k, v in mapping.items()}
        self._profile = None

    def get_file(self, relative_path: str) -> str:
        if not self.root:
            raise RuntimeError("No project is open.")
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        candidate = (self.root / clean_rel).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError("The requested file is outside the project.")
        content = candidate.read_text(encoding="utf-8", errors="replace")
        self.files[clean_rel] = content
        return content

    def update_file_content(self, relative_path: str, content: str):
        """Incrementally updates cache for an applied file change."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        self.files[clean_rel] = content
        if self._profile:
            # Refresh symbols for this specific file
            syms = self._extract_file_symbols(clean_rel, content)
            self._profile.symbols[clean_rel] = syms
            if clean_rel not in self._profile.file_tree:
                self._profile.file_tree.append(clean_rel)
                self._profile.file_tree.sort()
            self._profile.last_updated = time.time()

    def remove_file(self, relative_path: str):
        """Removes a file from cached files and profile."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        self.files.pop(clean_rel, None)
        if self._profile:
            self._profile.symbols.pop(clean_rel, None)
            if clean_rel in self._profile.file_tree:
                self._profile.file_tree.remove(clean_rel)
            self._profile.last_updated = time.time()

    def get_project_profile(self, force_refresh: bool = False) -> ProjectProfile:
        """
        Analyzes the project directory structure, dependencies, frameworks,
        entrypoints, and code symbols, caching the result in memory.
        """
        if self._profile and not force_refresh:
            return self._profile

        if not self.root or not self.root.exists():
            return ProjectProfile()

        file_tree: list[str] = []
        dependencies: list[str] = []
        frameworks: list[str] = []
        entrypoints: list[str] = []
        symbols: dict[str, list[ProjectSymbol]] = {}

        # 1. Scan directory structure (bounded and non-ignored)
        for current, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for name in names:
                path = Path(current) / name
                if path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size <= MAX_FILE_BYTES:
                    rel = str(path.relative_to(self.root)).replace("\\", "/")
                    file_tree.append(rel)

        file_tree.sort()

        # 2. Inspect dependencies & configs
        pkg_json = self.root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                deps = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
                dependencies.extend(deps[:20])
                if "react" in deps:
                    frameworks.append("React")
                if "vue" in deps:
                    frameworks.append("Vue")
                if "express" in deps:
                    frameworks.append("Express")
                if "vite" in deps:
                    frameworks.append("Vite")
                if "next" in deps:
                    frameworks.append("Next.js")
            except Exception:
                pass

        req_txt = self.root / "requirements.txt"
        if req_txt.exists():
            try:
                for line in req_txt.read_text(encoding="utf-8", errors="replace").splitlines():
                    clean = line.strip().split("==")[0].split(">=")[0].strip()
                    if clean and not clean.startswith("#"):
                        dependencies.append(clean)
                        if clean.lower() == "fastapi":
                            frameworks.append("FastAPI")
                        elif clean.lower() == "flask":
                            frameworks.append("Flask")
                        elif clean.lower() == "django":
                            frameworks.append("Django")
            except Exception:
                pass

        pyproj = self.root / "pyproject.toml"
        if pyproj.exists():
            try:
                text = pyproj.read_text(encoding="utf-8", errors="replace").lower()
                if "fastapi" in text and "FastAPI" not in frameworks:
                    frameworks.append("FastAPI")
                if "flask" in text and "Flask" not in frameworks:
                    frameworks.append("Flask")
            except Exception:
                pass

        # 3. Detect Entrypoints
        candidate_entries = [
            "index.html", "main.py", "app.py", "manage.py", "server.js",
            "index.js", "src/main.jsx", "src/index.tsx", "src/App.tsx", "src/App.jsx"
        ]
        for ce in candidate_entries:
            if ce in file_tree:
                entrypoints.append(ce)

        # 4. Determine Project Type
        has_html = any(f.endswith(".html") for f in file_tree)
        has_py = any(f.endswith(".py") for f in file_tree)
        has_js_ts = any(f.endswith((".js", ".jsx", ".ts", ".tsx")) for f in file_tree)

        if frameworks:
            project_type = f"{'/'.join(frameworks)} Application"
        elif has_html and (has_js_ts or any(f.endswith(".css") for f in file_tree)) and not has_py:
            project_type = "Static Web Application (HTML5 / CSS / Vanilla JS)"
        elif has_py and has_html:
            project_type = "Full-Stack Python Web Application"
        elif has_py:
            project_type = "Python Application / Module"
        elif has_js_ts:
            project_type = "JavaScript / TypeScript Project"
        elif not file_tree:
            project_type = "Empty Workspace (New Project Creation)"
        else:
            project_type = "General Software Workspace"

        # 5. Extract symbols for key files (up to 15 files to keep profiling fast)
        key_files = [f for f in file_tree if f.endswith((".py", ".js", ".jsx", ".ts", ".tsx"))][:15]
        for rel in key_files:
            try:
                content = self.files.get(rel)
                if content is None:
                    target = self.root / rel
                    content = target.read_text(encoding="utf-8", errors="replace")
                    self.files[rel] = content
                syms = self._extract_file_symbols(rel, content)
                if syms:
                    symbols[rel] = syms
            except Exception:
                continue

        profile = ProjectProfile(
            project_type=project_type,
            frameworks=frameworks,
            entrypoints=entrypoints,
            dependencies=dependencies[:15],
            file_tree=file_tree,
            symbols=symbols,
            last_updated=time.time(),
        )
        self._profile = profile
        return profile

    def _extract_file_symbols(self, rel_path: str, content: str) -> list[ProjectSymbol]:
        ext = Path(rel_path).suffix.lower()
        if ext == ".py":
            return extract_python_symbols(content, rel_path)
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            return extract_javascript_symbols(content, rel_path)
        return []

    def search_symbols(self, query: str) -> list[dict[str, Any]]:
        """Searches indexed project symbols by name or kind."""
        profile = self.get_project_profile()
        query_lower = query.lower()
        matches: list[dict[str, Any]] = []

        for rel, syms in profile.symbols.items():
            for s in syms:
                if query_lower in s.name.lower() or query_lower in s.kind.lower():
                    matches.append(s.to_dict())

        return matches

    def get_workspace_summary(self, max_tokens: int = 600) -> str:
        """
        Generates a token-optimized Cursor-style project summary for LLM prompt injection.
        Provides project type, entrypoints, dependencies, compact file hierarchy,
        and high-level symbol catalog without dumping raw file bodies.
        """
        profile = self.get_project_profile()
        lines = []

        lines.append(f"Workspace Root: {self.root.name if self.root else 'Unknown'}")
        lines.append(f"Project Architecture: {profile.project_type}")

        if profile.entrypoints:
            lines.append(f"Primary Entrypoints: {', '.join(profile.entrypoints)}")

        if profile.dependencies:
            lines.append(f"Detected Dependencies: {', '.join(profile.dependencies[:12])}")

        if profile.file_tree:
            lines.append("Project File Structure:")
            # Display up to 30 files cleanly
            for f in profile.file_tree[:30]:
                lines.append(f"  - {f}")
            if len(profile.file_tree) > 30:
                lines.append(f"  ... (+{len(profile.file_tree) - 30} more files)")
        else:
            lines.append("Project File Structure: (Empty workspace - ready for new project creation)")

        if profile.symbols:
            lines.append("Key Project Symbols & Signatures:")
            symbol_count = 0
            for rel, syms in profile.symbols.items():
                if symbol_count >= 15:
                    break
                sym_strs = [f"{s.name} ({s.kind})" for s in syms[:4]]
                if sym_strs:
                    lines.append(f"  - {rel}: {', '.join(sym_strs)}")
                    symbol_count += len(sym_strs)

        return "\n".join(lines)

    def build_context(
        self,
        query: str,
        active_file: Optional[str] = None,
        selected_code: Optional[str] = None,
        attached_files: Optional[list[str]] = None,
        include_codebase: bool = False,
        max_chars: int = 12000,
        active_content: Optional[str] = None,
        attached_contents: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Builds a compact, high-relevance prompt context.
        Uses structured workspace profiling instead of dumping entire directories.
        """
        chunks = []

        # 1. Always inject compact workspace summary
        if self.root:
            chunks.append(f"PROJECT OVERVIEW:\n{self.get_workspace_summary()}")

        # 2. Active file content if provided
        if active_file:
            content = active_content
            if content is None:
                content = self.files.get(active_file, "")
            if not content and self.root:
                try:
                    content = self.get_file(active_file)
                except Exception:
                    content = ""
            if content:
                chunks.append(f"ACTIVE FILE: {active_file}\n{content[:6000]}")

        # 3. Selected code
        if selected_code:
            chunks.append(f"SELECTED CODE:\n{selected_code}")

        # 4. Explicitly attached files
        for relative in attached_files or []:
            content = None
            if attached_contents and relative in attached_contents:
                content = attached_contents[relative]
            if content is None:
                content = self.files.get(relative)
            if content is None and self.root:
                try:
                    content = self.get_file(relative)
                except Exception:
                    content = None
            if content is not None:
                chunks.append(f"ATTACHED FILE: {relative}\n{content[:5000]}")

        # 5. Only include codebase files if explicitly asked, and prioritize relevant files
        if include_codebase and self.files:
            query_lower = query.lower()
            relevant_files = []
            for relative, content in self.files.items():
                if relative == active_file:
                    continue
                # Score relevance by query keywords or file extensions
                score = sum(1 for kw in query_lower.split() if len(kw) > 3 and kw in content.lower())
                if score > 0 or relative in ("index.html", "main.py", "app.py"):
                    relevant_files.append((score, relative, content))

            relevant_files.sort(key=lambda x: x[0], reverse=True)
            for _, relative, content in relevant_files[:4]:
                chunks.append(f"RELEVANT FILE: {relative}\n{content[:3000]}")

        combined = "\n\n".join(chunks)
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n[Context truncated to fit prompt budget.]"
        return combined
