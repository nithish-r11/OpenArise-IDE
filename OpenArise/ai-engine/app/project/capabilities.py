"""Static project capabilities. Detection is an observation, never execution proof."""
import codecs
import hashlib
import json
import re
from pathlib import Path

from app.memory.redact import SecretRedactor
from app.project.scanner import ProjectScanner
from app.tools.fs import _is_safe_path

TEXT_EXTENSIONS = {".py", ".pyw", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
                   ".html", ".css", ".scss", ".json", ".toml", ".yaml", ".yml",
                   ".ini", ".cfg", ".txt", ".md", ".svg"}
LANGUAGES = {"py": "Python", "pyw": "Python", "js": "JavaScript", "jsx": "JavaScript",
             "mjs": "JavaScript", "cjs": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript",
             "html": "HTML", "css": "CSS", "scss": "CSS"}
MANIFESTS = {"package.json", "pyproject.toml", "requirements.txt", "package-lock.json",
             "pnpm-lock.yaml", "yarn.lock", "tsconfig.json"}
ENTRY_NAMES = {"main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "index.html",
               "main.tsx", "main.jsx", "index.tsx", "index.jsx", "server.js", "server.ts",
               "index.js", "index.ts"}


def read_project_text(root, relative, limit=65536):
    """Bounded UTF-8 observation; excludes secrets, links, runtime and binary files."""
    root = Path(root).resolve()
    path = root
    if not isinstance(relative, str) or not _is_safe_path(str(root), relative):
        return None
    scanner = ProjectScanner(str(root))
    if scanner._is_sensitive(relative):
        return None
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink() or path.is_junction():
            return None
    try:
        if not path.is_file() or path.stat().st_nlink > 1:
            return None
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if b"\0" in data:
            return None
        # Truncation may split a valid multibyte codepoint. Keep its complete
        # prefix while still refusing genuinely invalid UTF-8 content.
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        return decoder.decode(data[:limit], final=len(data) <= limit)
    except (OSError, UnicodeError, ValueError):
        return None


def detect_capabilities(root, state):
    """Extensible descriptor layer shared by the facade, context and desktop host."""
    files = sorted(f.relative_path for f in state.files if f.content_hash)
    names = set(files)
    languages = sorted({LANGUAGES[f.file_type] for f in state.files if f.file_type in LANGUAGES})
    frontend, backend, managers, commands, warnings = set(), set(), set(), [], []
    declarations, run_candidates = [], []
    for relative in files:
        name = Path(relative).name
        if name == "package.json":
            raw = read_project_text(root, relative)
            try:
                package = json.loads(raw) if raw is not None else None
                if not isinstance(package, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                warnings.append(f"Cannot inspect {relative}: unreadable, oversized or invalid JSON.")
                continue
            folder = Path(relative).parent.as_posix()
            prefix = "" if folder == "." else folder + "/"
            deps = {**(package.get("dependencies") if isinstance(package.get("dependencies"), dict) else {}),
                    **(package.get("devDependencies") if isinstance(package.get("devDependencies"), dict) else {})}
            if "react" in deps:
                frontend.add("React")
            if "vite" in deps or any(p.startswith(prefix + "vite.config.") for p in files):
                frontend.add("Vite")
            if "express" in deps:
                backend.add("Express")
            backend.add("Node.js") if "express" in deps or any(prefix + n in names for n in ("server.js", "server.ts")) else None
            manager = "pnpm" if prefix + "pnpm-lock.yaml" in names else "yarn" if prefix + "yarn.lock" in names else "npm"
            managers.add(manager)
            scripts = package.get("scripts")
            if not isinstance(scripts, dict):
                continue
            for action in ("dev", "start"):
                if isinstance(scripts.get(action), str) and scripts[action].strip():
                    run_candidates.append(f"{manager} run {action}" + (f" · {folder}" if folder != "." else "") + " (candidate; execution not enabled)")
            for action in ("build", "test"):
                script = scripts.get(action)
                if not isinstance(script, str) or not script.strip() or len(script) > 1000 or re.search(r"[\x00-\x1f]", script):
                    continue
                command_id = hashlib.sha256(f"{relative}:{action}".encode()).hexdigest()[:24]
                commands.append({"id": command_id, "kind": "node_script", "directory": folder,
                                 "label": f"{manager} run {action}" + (f" · {folder}" if folder != "." else ""),
                                 "manager": manager, "action": action, "manifest": relative,
                                 "revision": hashlib.sha256(raw.encode()).hexdigest(),
                                 "script": SecretRedactor().redact(script), "approvalRequired": True,
                                 "supported": manager == "npm",
                                 "reason": "Runs project-defined code after approval; dependencies and Node/npm must be installed." if manager == "npm" else f"{manager} detected; execution is not implemented. No npm fallback."})
        elif name in ("requirements.txt", "pyproject.toml"):
            managers.add("pip" if name == "requirements.txt" else "pyproject")
            text = read_project_text(root, relative) or ""
            declarations.append(text.lower())
    imports = {name.split(".")[0].lower() for m in state.python_modules for name in m.imports}
    for framework in ("fastapi", "flask", "django"):
        if framework in imports or any(re.search(r"\b" + framework + r"\b", text) for text in declarations):
            backend.add({"fastapi": "FastAPI", "flask": "Flask", "django": "Django"}[framework])
    if "Python" in languages:
        backend.add("Python")
    if "HTML" in languages or "CSS" in languages:
        frontend.add("HTML/CSS")
    if any(Path(p).name.startswith("vite.config.") for p in files):
        frontend.add("Vite")
    entries = [p for p in files if Path(p).name in ENTRY_NAMES][:20]
    run_candidates += [f"python {p} (candidate; review imports and runtime requirements first)" for p in entries if p.endswith(".py")]
    manifests = [p for p in files if Path(p).name in MANIFESTS or Path(p).name.startswith("vite.config.")][:30]
    if "Python" in languages:
        commands.insert(0, {"id": "python-tests", "kind": "pytest", "directory": ".", "label": "pytest",
                            "manager": "Python", "action": "test", "manifest": "", "revision": "",
                            "script": "", "approvalRequired": False, "supported": True,
                            "reason": "Uses the displayed Python environment. Manual test execution is not agent verification."})
    return {"projectType": "full-stack" if frontend and backend else "frontend" if frontend else "backend" if backend else "unknown",
            "frontend": sorted(frontend), "backend": sorted(backend), "languages": languages,
            "dependencyManagers": sorted(managers), "entryPoints": entries, "manifests": manifests,
            "commands": commands[:20], "warnings": warnings[:10], "observedAt": state.scan_timestamp,
            "runCandidates": run_candidates[:20],
            "interpretation": "Static observations and candidate entry points; installed dependencies, execution and verification are separate."}
