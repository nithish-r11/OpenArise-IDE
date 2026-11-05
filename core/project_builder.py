"""
OpenArise IDE - Universal Project Builder
Scaffolds local projects from built-in templates with offline support,
directory validation, path traversal guards, and optional Git/.venv setup.
"""

import os
import re
import sys
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


@dataclass
class ProjectTemplate:
    id: str
    name: str
    language: str  # "Python" or "JavaScript / TypeScript"
    category: str
    description: str
    files: Dict[str, str] = field(default_factory=dict)


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[\s_]+", "-", cleaned) or "openarise-app"


# ----------------------------------------------------------------------
# Template Definitions (Offline Available)
# ----------------------------------------------------------------------

TEMPLATES: Dict[str, ProjectTemplate] = {
    "python_app": ProjectTemplate(
        id="python_app",
        name="Python Application",
        language="Python",
        category="Console & CLI",
        description="A standard Python application with entry point, arguments, and unit tests.",
        files={
            "main.py": (
                '"""\n'
                '{{PROJECT_NAME}}\n'
                'Created with OpenArise IDE\n'
                '"""\n'
                'import sys\n'
                'import argparse\n\n'
                'def main():\n'
                '    parser = argparse.ArgumentParser(description="{{PROJECT_NAME}} Application")\n'
                '    parser.add_argument("--name", default="Developer", help="Name to greet")\n'
                '    args = parser.parse_args()\n'
                '    print(f"Hello, {args.name}! Welcome to {{PROJECT_NAME}}.")\n'
                '    return 0\n\n'
                'if __name__ == "__main__":\n'
                '    sys.exit(main())\n'
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "A Python application scaffolded with **OpenArise IDE**.\n\n"
                "## Running\n"
                "```bash\n"
                "python main.py\n"
                "```\n\n"
                "## Tests\n"
                "```bash\n"
                "pytest\n"
                "```\n"
            ),
            ".gitignore": (
                "__pycache__/\n"
                "*.py[cod]\n"
                "*$py.class\n"
                ".venv/\n"
                "venv/\n"
                ".pytest_cache/\n"
                ".coverage\n"
                "dist/\n"
                "build/\n"
            ),
            "tests/test_main.py": (
                "from main import main\n\n"
                "def test_main():\n"
                "    assert callable(main)\n"
            ),
        },
    ),
    "python_venv": ProjectTemplate(
        id="python_venv",
        name="Python (Virtual Environment Ready)",
        language="Python",
        category="General",
        description="Modular Python application with src/ layout, requirements.txt, and virtualenv structure.",
        files={
            "src/app.py": (
                '"""\n'
                '{{PROJECT_NAME}} - Main Application Module\n'
                '"""\n\n'
                'class Application:\n'
                '    def __init__(self, name: str = "{{PROJECT_NAME}}"):\n'
                '        self.name = name\n\n'
                '    def run(self) -> str:\n'
                '        return f"{self.name} is running successfully."\n\n'
                'def main():\n'
                '    app = Application()\n'
                '    print(app.run())\n\n'
                'if __name__ == "__main__":\n'
                '    main()\n'
            ),
            "requirements.txt": (
                "# Core dependencies for {{PROJECT_NAME}}\n"
                "pytest>=8.0.0\n"
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "Python project ready for virtual environment.\n\n"
                "## Setup\n"
                "```bash\n"
                "python -m venv .venv\n"
                ".\\.venv\\Scripts\\activate\n"
                "pip install -r requirements.txt\n"
                "python src/app.py\n"
                "```\n"
            ),
            ".gitignore": (
                "__pycache__/\n"
                "*.py[cod]\n"
                ".venv/\n"
                "venv/\n"
                ".pytest_cache/\n"
            ),
            "tests/test_app.py": (
                "import sys\n"
                "from pathlib import Path\n"
                'sys.path.insert(0, str(Path(__file__).parent.parent / "src"))\n'
                "from app import Application\n\n"
                "def test_app_run():\n"
                "    app = Application()\n"
                '    assert "running successfully" in app.run()\n'
            ),
        },
    ),
    "flask_app": ProjectTemplate(
        id="flask_app",
        name="Flask Web Application",
        language="Python",
        category="Web Backend",
        description="Lightweight web application using Flask with HTML templates and static CSS.",
        files={
            "app.py": (
                "from flask import Flask, render_template, jsonify\n\n"
                "app = Flask(__name__)\n\n"
                '@app.route("/")\n'
                "def index():\n"
                '    return render_template("index.html", project_name="{{PROJECT_NAME}}")\n\n'
                '@app.route("/api/health")\n'
                "def health():\n"
                '    return jsonify({"status": "healthy", "project": "{{PROJECT_NAME}}"})\n\n'
                'if __name__ == "__main__":\n'
                '    app.run(host="127.0.0.1", port=5000, debug=True)\n'
            ),
            "templates/index.html": (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '    <meta charset="UTF-8">\n'
                "    <title>{{ project_name }} - OpenArise IDE</title>\n"
                '    <link rel="stylesheet" href="/static/style.css">\n'
                "</head>\n"
                "<body>\n"
                '    <div class="card">\n'
                "        <h1>{{ project_name }}</h1>\n"
                "        <p>Your Flask application is up and running in OpenArise IDE.</p>\n"
                '        <a href="/api/health">Check API Health</a>\n'
                "    </div>\n"
                "</body>\n"
                "</html>\n"
            ),
            "static/style.css": (
                "body {\n"
                '    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;\n'
                "    background-color: #17191f;\n"
                "    color: #e6e8ef;\n"
                "    margin: 0;\n"
                "    display: flex;\n"
                "    justify-content: center;\n"
                "    align-items: center;\n"
                "    height: 100vh;\n"
                "}\n"
                ".card {\n"
                "    background: #20232b;\n"
                "    padding: 36px 48px;\n"
                "    border-radius: 8px;\n"
                "    border: 1px solid #343b49;\n"
                "    text-align: center;\n"
                "}\n"
                "h1 { color: #8ab4f8; margin-top: 0; }\n"
                "a { color: #8ab4f8; text-decoration: none; }\n"
                "a:hover { text-decoration: underline; }\n"
            ),
            "requirements.txt": "flask>=3.0.0\n",
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "Flask web service created with **OpenArise IDE**.\n\n"
                "## Running\n"
                "```bash\n"
                "pip install -r requirements.txt\n"
                "python app.py\n"
                "```\n"
            ),
            ".gitignore": "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n",
        },
    ),
    "fastapi_app": ProjectTemplate(
        id="fastapi_app",
        name="FastAPI Web Application",
        language="Python",
        category="Web API",
        description="High-performance modern API server with FastAPI, Pydantic, and modular routers.",
        files={
            "main.py": (
                "from fastapi import FastAPI\n"
                "from fastapi.middleware.cors import CORSMiddleware\n"
                "from routers import items\n\n"
                'app = FastAPI(title="{{PROJECT_NAME}}", version="1.0.0")\n\n'
                "app.add_middleware(\n"
                "    CORSMiddleware,\n"
                '    allow_origins=["*"],\n'
                "    allow_credentials=True,\n"
                '    allow_methods=["*"],\n'
                '    allow_headers=["*"],\n'
                ")\n\n"
                'app.include_router(items.router, prefix="/api/items", tags=["items"])\n\n'
                '@app.get("/")\n'
                "def root():\n"
                '    return {"message": "Welcome to {{PROJECT_NAME}}", "docs": "/docs"}\n\n'
                '@app.get("/health")\n'
                "def health():\n"
                '    return {"status": "ok", "app": "{{PROJECT_NAME}}"}\n'
            ),
            "routers/__init__.py": "# API Routers\n",
            "routers/items.py": (
                "from fastapi import APIRouter\n\n"
                "router = APIRouter()\n\n"
                '@router.get("/")\n'
                "def list_items():\n"
                '    return [{"id": 1, "name": "Item A", "project": "{{PROJECT_NAME}}"}]\n'
            ),
            "requirements.txt": (
                "fastapi>=0.110.0\n"
                "uvicorn>=0.28.0\n"
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "FastAPI application created with **OpenArise IDE**.\n\n"
                "## Running\n"
                "```bash\n"
                "pip install -r requirements.txt\n"
                "uvicorn main:app --reload\n"
                "```\n"
                "Browse interactive Swagger UI at: `http://localhost:8000/docs`\n"
            ),
            ".gitignore": "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n",
        },
    ),
    "node_app": ProjectTemplate(
        id="node_app",
        name="Node.js Application",
        language="JavaScript / TypeScript",
        category="Console & CLI",
        description="Clean Node.js application starter with package.json and entry script.",
        files={
            "package.json": (
                '{\n'
                '  "name": "{{PROJECT_SLUG}}",\n'
                '  "version": "1.0.0",\n'
                '  "description": "{{PROJECT_NAME}} application created with OpenArise IDE",\n'
                '  "main": "index.js",\n'
                '  "scripts": {\n'
                '    "start": "node index.js",\n'
                '    "test": "node -e \\"console.log(\'No tests\')\\""\n'
                '  },\n'
                '  "author": "{{AUTHOR}}",\n'
                '  "license": "MIT"\n'
                '}\n'
            ),
            "index.js": (
                '/**\n'
                ' * {{PROJECT_NAME}}\n'
                ' * Author: {{AUTHOR}}\n'
                ' */\n'
                'console.log("Welcome to {{PROJECT_NAME}} running on Node.js!");\n'
                'console.log(`Node version: ${process.version}`);\n'
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "Node.js starter project.\n\n"
                "## Run\n"
                "```bash\n"
                "node index.js\n"
                "```\n"
            ),
            ".gitignore": "node_modules/\n.env\n*.log\n",
        },
    ),
    "express_app": ProjectTemplate(
        id="express_app",
        name="Express Web Application",
        language="JavaScript / TypeScript",
        category="Web Backend",
        description="RESTful Express.js web server with static file support and JSON API routes.",
        files={
            "package.json": (
                '{\n'
                '  "name": "{{PROJECT_SLUG}}",\n'
                '  "version": "1.0.0",\n'
                '  "description": "Express application for {{PROJECT_NAME}}",\n'
                '  "main": "server.js",\n'
                '  "scripts": {\n'
                '    "start": "node server.js"\n'
                '  },\n'
                '  "dependencies": {\n'
                '    "express": "^4.19.2"\n'
                '  },\n'
                '  "author": "{{AUTHOR}}",\n'
                '  "license": "MIT"\n'
                '}\n'
            ),
            "server.js": (
                "const express = require('express');\n"
                "const app = express();\n"
                "const PORT = process.env.PORT || 3000;\n\n"
                "app.use(express.json());\n\n"
                "app.get('/', (req, res) => {\n"
                "  res.send('<h1>{{PROJECT_NAME}}</h1><p>Express server is running.</p>');\n"
                "});\n\n"
                "app.get('/api/status', (req, res) => {\n"
                "  res.json({ status: 'online', app: '{{PROJECT_NAME}}' });\n"
                "});\n\n"
                "app.listen(PORT, () => {\n"
                "  console.log(`Server listening on port ${PORT}`);\n"
                "});\n"
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "Express web application created with **OpenArise IDE**.\n\n"
                "## Running\n"
                "```bash\n"
                "npm install\n"
                "npm start\n"
                "```\n"
            ),
            ".gitignore": "node_modules/\n.env\n*.log\n",
        },
    ),
    "react_vite": ProjectTemplate(
        id="react_vite",
        name="React with Vite",
        language="JavaScript / TypeScript",
        category="Web Frontend",
        description="Modern React web application using Vite for ultra-fast bundling and development.",
        files={
            "package.json": (
                '{\n'
                '  "name": "{{PROJECT_SLUG}}",\n'
                '  "private": true,\n'
                '  "version": "0.1.0",\n'
                '  "type": "module",\n'
                '  "scripts": {\n'
                '    "dev": "vite",\n'
                '    "build": "vite build",\n'
                '    "preview": "vite preview"\n'
                '  },\n'
                '  "dependencies": {\n'
                '    "react": "^18.2.0",\n'
                '    "react-dom": "^18.2.0"\n'
                '  },\n'
                '  "devDependencies": {\n'
                '    "@vitejs/plugin-react": "^4.2.1",\n'
                '    "vite": "^5.2.0"\n'
                '  }\n'
                '}\n'
            ),
            "vite.config.js": (
                "import { defineConfig } from 'vite';\n"
                "import react from '@vitejs/plugin-react';\n\n"
                "export default defineConfig({\n"
                "  plugins: [react()],\n"
                "  server: { port: 5173 }\n"
                "});\n"
            ),
            "index.html": (
                "<!doctype html>\n"
                '<html lang="en">\n'
                "  <head>\n"
                '    <meta charset="UTF-8" />\n'
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
                "    <title>{{PROJECT_NAME}}</title>\n"
                "  </head>\n"
                "  <body>\n"
                '    <div id="root"></div>\n'
                '    <script type="module" src="/src/main.jsx"></script>\n'
                "  </body>\n"
                "</html>\n"
            ),
            "src/main.jsx": (
                "import React from 'react';\n"
                "import ReactDOM from 'react-dom/client';\n"
                "import App from './App.jsx';\n"
                "import './App.css';\n\n"
                "ReactDOM.createRoot(document.getElementById('root')).render(\n"
                "  <React.StrictMode>\n"
                "    <App />\n"
                "  </React.StrictMode>\n"
                ");\n"
            ),
            "src/App.jsx": (
                "import { useState } from 'react';\n\n"
                "export default function App() {\n"
                "  const [count, setCount] = useState(0);\n\n"
                "  return (\n"
                '    <div className="container">\n'
                "      <h1>{{PROJECT_NAME}}</h1>\n"
                "      <p>React + Vite starter in OpenArise IDE</p>\n"
                "      <button onClick={() => setCount((c) => c + 1)}>\n"
                "        Count is {count}\n"
                "      </button>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            ),
            "src/App.css": (
                "body {\n"
                "  background-color: #17191f;\n"
                "  color: #e6e8ef;\n"
                '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;\n'
                "  display: flex;\n"
                "  justify-content: center;\n"
                "  align-items: center;\n"
                "  height: 100vh;\n"
                "  margin: 0;\n"
                "}\n"
                ".container {\n"
                "  text-align: center;\n"
                "  background: #20232b;\n"
                "  padding: 40px;\n"
                "  border-radius: 8px;\n"
                "  border: 1px solid #343b49;\n"
                "}\n"
                "button {\n"
                "  background: #303747;\n"
                "  color: #e6e8ef;\n"
                "  border: 1px solid #424b5d;\n"
                "  border-radius: 4px;\n"
                "  padding: 8px 16px;\n"
                "  cursor: pointer;\n"
                "}\n"
                "button:hover {\n"
                "  background: #3d4960;\n"
                "}\n"
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "React + Vite application scaffolded with **OpenArise IDE**.\n\n"
                "## Running\n"
                "```bash\n"
                "npm install\n"
                "npm run dev\n"
                "```\n"
            ),
            ".gitignore": "node_modules/\ndist/\n.env\n*.log\n",
        },
    ),
    "ts_starter": ProjectTemplate(
        id="ts_starter",
        name="TypeScript Starter Project",
        language="JavaScript / TypeScript",
        category="Console & CLI",
        description="Configured TypeScript application with tsconfig.json, compiler options, and build scripts.",
        files={
            "package.json": (
                '{\n'
                '  "name": "{{PROJECT_SLUG}}",\n'
                '  "version": "1.0.0",\n'
                '  "description": "TypeScript starter project for {{PROJECT_NAME}}",\n'
                '  "main": "dist/index.js",\n'
                '  "scripts": {\n'
                '    "build": "tsc",\n'
                '    "start": "tsc && node dist/index.js",\n'
                '    "watch": "tsc -w"\n'
                '  },\n'
                '  "devDependencies": {\n'
                '    "typescript": "^5.4.0",\n'
                '    "@types/node": "^20.11.0"\n'
                '  },\n'
                '  "author": "{{AUTHOR}}",\n'
                '  "license": "MIT"\n'
                '}\n'
            ),
            "tsconfig.json": (
                '{\n'
                '  "compilerOptions": {\n'
                '    "target": "ES2022",\n'
                '    "module": "CommonJS",\n'
                '    "outDir": "./dist",\n'
                '    "rootDir": "./src",\n'
                '    "strict": true,\n'
                '    "esModuleInterop": true,\n'
                '    "skipLibCheck": true,\n'
                '    "forceConsistentCasingInFileNames": true\n'
                '  },\n'
                '  "include": ["src/**/*"]\n'
                '}\n'
            ),
            "src/index.ts": (
                "interface AppConfig {\n"
                "  name: string;\n"
                "  version: string;\n"
                "}\n\n"
                "const config: AppConfig = {\n"
                '  name: "{{PROJECT_NAME}}",\n'
                '  version: "1.0.0",\n'
                "};\n\n"
                "function greet(cfg: AppConfig): string {\n"
                "  return `Hello from ${cfg.name} (v${cfg.version})!`;\n"
                "}\n\n"
                "console.log(greet(config));\n"
            ),
            "README.md": (
                "# {{PROJECT_NAME}}\n\n"
                "TypeScript starter project.\n\n"
                "## Running\n"
                "```bash\n"
                "npm install\n"
                "npm start\n"
                "```\n"
            ),
            ".gitignore": "node_modules/\ndist/\n*.log\n",
        },
    ),
}


class ProjectBuilder:
    """
    Project Builder engine: validates inputs, previews file structures,
    and creates scaffolded projects safely without silent overwrites.
    """

    @classmethod
    def list_templates(cls, language: Optional[str] = None) -> List[ProjectTemplate]:
        templates = list(TEMPLATES.values())
        if language:
            templates = [t for t in templates if t.language.lower() == language.lower()]
        return templates

    @classmethod
    def get_template(cls, template_id: str) -> Optional[ProjectTemplate]:
        return TEMPLATES.get(template_id)

    @classmethod
    def validate_project_name(cls, name: str) -> Tuple[bool, str]:
        if not name or not name.strip():
            return False, "Project name cannot be empty."
        if name.endswith("."):
            return False, "Project name cannot end with a dot."
        if name.endswith(" ") or name.startswith(" "):
            return False, "Project name cannot end with a dot or space."
        name = name.strip()
        if len(name) > 64:
            return False, "Project name cannot exceed 64 characters."
        if not re.match(r"^[a-zA-Z0-9_\-\.\s]+$", name):
            return False, "Project name contains invalid characters. Use letters, numbers, spaces, dots, hyphens, and underscores."
        if name.upper() in WINDOWS_RESERVED_NAMES:
            return False, f"'{name}' is a reserved Windows device name."
        return True, ""

    @classmethod
    def validate_destination(cls, name: str, dest_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        val_ok, val_err = cls.validate_project_name(name)
        if not val_ok:
            return False, val_err, None

        if not dest_dir:
            return False, "Destination directory must be selected.", None

        dest_dir = Path(dest_dir).resolve()
        if not dest_dir.exists():
            return False, f"Destination folder does not exist: {dest_dir}", None
        if not dest_dir.is_dir():
            return False, f"Destination path is not a directory: {dest_dir}", None

        # Build resolved target path
        target_path = (dest_dir / name.strip()).resolve()

        # Prevent directory traversal attacks
        try:
            target_path.relative_to(dest_dir)
        except ValueError:
            return False, "Invalid path: Project destination attempts directory traversal outside base directory.", None

        # Check existing directory & overwrite collision
        if target_path.exists():
            if not target_path.is_dir():
                return False, f"A file already exists with the name '{target_path.name}'.", None
            # Check if directory has contents
            try:
                items = list(target_path.iterdir())
                if items:
                    return False, f"Target directory '{target_path}' already exists and is not empty. Overwriting is blocked.", None
            except PermissionError:
                return False, f"Permission denied accessing directory: {target_path}", None

        return True, "", target_path

    @classmethod
    def preview_project(cls, template_id: str, name: str) -> List[Tuple[str, bool]]:
        """
        Returns list of (relative_path, is_dir) representing the files and folders
        that will be generated.
        """
        tpl = TEMPLATES.get(template_id)
        if not tpl:
            return []

        entries = set()
        for rel_path in tpl.files.keys():
            parts = Path(rel_path).parts
            # Add all parent directories
            for i in range(1, len(parts)):
                parent_dir = "/".join(parts[:i])
                entries.add((parent_dir, True))
            entries.add((rel_path.replace("\\", "/"), False))

        return sorted(list(entries), key=lambda x: (not x[1], x[0]))

    @classmethod
    def create_project(
        cls,
        template_id: str,
        name: str,
        dest_dir: Path,
        init_git: bool = False,
        create_venv: bool = False,
        author: str = "OpenArise Developer",
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Scaffolds the project files into target directory safely.
        """
        valid, err, target_path = cls.validate_destination(name, dest_dir)
        if not valid or not target_path:
            return False, err, None

        tpl = TEMPLATES.get(template_id)
        if not tpl:
            return False, f"Unknown template ID: '{template_id}'", None

        def notify(msg: str, pct: int):
            if progress_callback:
                progress_callback(msg, pct)

        notify("Preparing project directory…", 10)
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, f"Failed to create project root directory: {exc}", None

        slug = _slugify(name)
        total_files = len(tpl.files)

        # Write template files
        for i, (rel_path, content) in enumerate(tpl.files.items(), start=1):
            file_path = target_path / rel_path
            pct = 10 + int((i / max(1, total_files)) * 60)
            notify(f"Writing {rel_path}…", pct)

            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Substitute variables
            resolved_content = (
                content.replace("{{PROJECT_NAME}}", name.strip())
                .replace("{{PROJECT_SLUG}}", slug)
                .replace("{{AUTHOR}}", author.strip())
            )

            try:
                file_path.write_text(resolved_content, encoding="utf-8")
            except OSError as exc:
                return False, f"Failed writing '{rel_path}': {exc}", target_path

        # Optional Git initialization
        if init_git:
            notify("Initializing Git repository…", 80)
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=str(target_path),
                    check=False,
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass

        # Optional Python virtual environment
        if create_venv and tpl.language == "Python":
            notify("Creating Python virtual environment (.venv)…", 90)
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", str(target_path / ".venv")],
                    cwd=str(target_path),
                    check=False,
                    capture_output=True,
                    timeout=60,
                )
            except Exception:
                pass

        notify("Project created successfully!", 100)
        return True, "Project created successfully.", target_path
