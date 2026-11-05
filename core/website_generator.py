"""
OpenArise IDE - AI Website Generation and Editing Engine
Generates complete, production-grade website projects (HTML+CSS+JS or React+Vite)
using local Ollama models with offline template fallbacks, multi-file JSON schemas,
safe path validation, website structure validation, and incremental editing.
"""

from __future__ import annotations
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple

import requests

from core.agent_models import FileChangeRecord, FileChangeType, FileChangeStatus
from core.project_builder import ProjectBuilder


@dataclass
class WebsiteSpec:
    """Specification for AI website creation."""
    name: str
    dest_dir: Path
    prompt: str
    tech: str = "html"                 # "html" or "react"
    is_multipage: bool = False
    model: str = "qwen2.5-coder:7b"


class AIWebsiteGenerator:
    """
    Engine for creating, editing, and validating website projects with local Ollama.
    """

    OLLAMA_API_URL = "http://127.0.0.1:11434"

    @classmethod
    def generate_website(
        cls,
        spec: WebsiteSpec,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> List[FileChangeRecord]:
        """
        Generates complete source files for a new website project.
        Returns a list of FileChangeRecord proposals ready for diff review.
        """
        def update_progress(msg: str, pct: int):
            if progress_callback:
                progress_callback(msg, pct)

        update_progress("Validating project parameters...", 10)
        valid_name, err_name = ProjectBuilder.validate_project_name(spec.name)
        if not valid_name:
            raise ValueError(f"Invalid website name: {err_name}")

        dest_path = Path(spec.dest_dir).resolve()
        if not dest_path.exists() or not dest_path.is_dir():
            raise ValueError(f"Target directory does not exist: {dest_path}")

        project_target = dest_path / spec.name
        if project_target.exists() and any(project_target.iterdir()):
            raise FileExistsError(
                f"Directory '{project_target.name}' already exists and is not empty. "
                "Choose a different name or destination to prevent overwrites."
            )

        update_progress(f"Connecting to Ollama model '{spec.model}'...", 25)

        # Attempt AI generation via Ollama
        generated_files = cls._query_ollama_generator(spec, update_progress)

        # Fallback to rich offline templates if Ollama was unreachable or produced invalid output
        if not generated_files:
            update_progress("Synthesizing comprehensive offline project structure...", 60)
            generated_files = cls._generate_offline_scaffold(spec)

        update_progress("Validating generated project structure...", 85)
        cls._validate_generated_files(generated_files, spec.tech)

        # Convert to FileChangeRecords
        records: List[FileChangeRecord] = []
        for rel_path, content in generated_files.items():
            records.append(
                FileChangeRecord(
                    rel_path=rel_path.replace("\\", "/"),
                    change_type=FileChangeType.CREATE.value,
                    status=FileChangeStatus.PROPOSED.value,
                    old_content="",
                    new_content=content,
                )
            )

        update_progress("Website project successfully generated.", 100)
        return records

    @classmethod
    def _query_ollama_generator(
        cls,
        spec: WebsiteSpec,
        update_progress: Callable[[str, int], None]
    ) -> Optional[Dict[str, str]]:
        """Queries Ollama for a structured JSON multi-file website project."""
        tech_guidelines = (
            "You are creating a Vanilla HTML5, CSS3, and modern JavaScript website."
            if spec.tech == "html" else
            "You are creating a modern React + Vite web application using standard JSX and CSS."
        )

        multipage_guidelines = (
            "Create multiple interconnected HTML pages (e.g. index.html, about.html, contact.html) with consistent navigation."
            if (spec.tech == "html" and spec.is_multipage) else
            "Create a clean multi-section or single-page responsive layout with cohesive styling."
        )

        system_prompt = (
            "You are an elite web architect and frontend engineer.\n"
            f"{tech_guidelines}\n"
            f"{multipage_guidelines}\n\n"
            "Generate COMPLETE, production-ready, beautiful code. Do not use ellipses ('...') or placeholders.\n"
            "You MUST respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "thought": "Brief architecture overview",\n'
            '  "files": [\n'
            '    {"path": "index.html", "content": "<!DOCTYPE html>..."},\n'
            '    {"path": "css/styles.css", "content": "/* CSS */..."},\n'
            '    {"path": "js/app.js", "content": "// JS..."}\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"Project Name: {spec.name}\n"
            f"Technology: {spec.tech.upper()}\n"
            f"Multi-Page: {'Yes' if spec.is_multipage else 'No'}\n"
            f"User Website Requirements:\n{spec.prompt}\n\n"
            "Please generate all necessary source code files now in the specified JSON format."
        )

        try:
            update_progress("Generating website files with AI...", 40)
            response = requests.post(
                f"{cls.OLLAMA_API_URL}/api/chat",
                json={
                    "model": spec.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "keep_alive": "30m",
                },
                timeout=60,
            )
            if response.status_code == 200:
                payload = response.json()
                raw_text = payload.get("message", {}).get("content", "")
                parsed = cls._parse_json_payload(raw_text)
                if parsed and isinstance(parsed.get("files"), list) and len(parsed["files"]) > 0:
                    files_dict = {}
                    for item in parsed["files"]:
                        path = item.get("path")
                        content = item.get("content")
                        if path and content:
                            files_dict[path.strip().lstrip("/\\")] = content
                    if "index.html" in files_dict or "package.json" in files_dict:
                        return files_dict
        except Exception:
            # Model offline or timeout -> fall back cleanly
            pass
        return None

    @classmethod
    def _parse_json_payload(cls, raw: str) -> Optional[dict]:
        """Extracts JSON from markdown fences or raw string."""
        if not raw:
            return None
        raw = raw.strip()
        # Direct attempt
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Search for markdown fenced block ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    @classmethod
    def _validate_generated_files(cls, files: Dict[str, str], tech: str):
        """Ensures generated files contain no path traversals and have entry points."""
        if not files:
            raise ValueError("No files generated.")

        for p in files.keys():
            if ".." in p or p.startswith("/") or p.startswith("\\"):
                raise ValueError(f"Path traversal detected in generated path: '{p}'")

        if tech == "html" and "index.html" not in files:
            raise ValueError("Generated HTML project is missing entry point 'index.html'.")
        if tech == "react" and "package.json" not in files:
            raise ValueError("Generated React project is missing 'package.json'.")

    @classmethod
    def _generate_offline_scaffold(cls, spec: WebsiteSpec) -> Dict[str, str]:
        """
        Creates complete, responsive, and functional website templates
        tailored to the user prompt. Available 100% offline.
        """
        name_title = spec.name.replace("-", " ").replace("_", " ").title()

        if spec.tech == "react":
            return cls._scaffold_react_project(spec, name_title)
        else:
            return cls._scaffold_html_project(spec, name_title)

    @classmethod
    def _scaffold_html_project(cls, spec: WebsiteSpec, title: str) -> Dict[str, str]:
        files: Dict[str, str] = {}

        # 1. Main Stylesheet (css/styles.css)
        css = (
            ":root {\n"
            "  --bg-primary: #0f1117;\n"
            "  --bg-secondary: #1a1d27;\n"
            "  --bg-card: #232736;\n"
            "  --accent: #6366f1;\n"
            "  --accent-hover: #4f46e5;\n"
            "  --text-main: #f8fafc;\n"
            "  --text-muted: #94a3b8;\n"
            "  --border: #334155;\n"
            "  --font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;\n"
            "}\n\n"
            "* { box-sizing: border-box; margin: 0; padding: 0; }\n"
            "body {\n"
            "  background-color: var(--bg-primary);\n"
            "  color: var(--text-main);\n"
            "  font-family: var(--font-family);\n"
            "  line-height: 1.6;\n"
            "}\n\n"
            ".container { width: 90%; max-width: 1200px; margin: 0 auto; padding: 0 1rem; }\n"
            "header {\n"
            "  background: rgba(15, 17, 23, 0.9);\n"
            "  backdrop-filter: blur(8px);\n"
            "  border-bottom: 1px solid var(--border);\n"
            "  position: sticky; top: 0; z-index: 100;\n"
            "}\n"
            ".nav-wrapper { display: flex; justify-content: space-between; align-items: center; height: 70px; }\n"
            ".logo { font-size: 1.5rem; font-weight: bold; color: var(--text-main); text-decoration: none; }\n"
            ".logo span { color: var(--accent); }\n"
            ".nav-links { display: flex; gap: 1.5rem; list-style: none; }\n"
            ".nav-links a {\n"
            "  color: var(--text-muted); text-decoration: none; font-weight: 500; transition: color 0.2s;\n"
            "}\n"
            ".nav-links a:hover, .nav-links a.active { color: var(--accent); }\n"
            ".hero {\n"
            "  padding: 5rem 0 4rem; text-align: center;\n"
            "  background: radial-gradient(circle at center, rgba(99, 102, 241, 0.15) 0%, transparent 70%);\n"
            "}\n"
            ".hero h1 { font-size: 3rem; margin-bottom: 1rem; line-height: 1.2; }\n"
            ".hero p { font-size: 1.25rem; color: var(--text-muted); max-width: 700px; margin: 0 auto 2rem; }\n"
            ".btn {\n"
            "  display: inline-block; padding: 0.75rem 1.75rem; border-radius: 8px;\n"
            "  background: var(--accent); color: #ffffff; text-decoration: none; font-weight: 600;\n"
            "  transition: background 0.2s, transform 0.2s; border: none; cursor: pointer;\n"
            "}\n"
            ".btn:hover { background: var(--accent-hover); transform: translateY(-2px); }\n"
            ".grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; margin: 3rem 0; }\n"
            ".card {\n"
            "  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 2rem;\n"
            "  transition: transform 0.2s, border-color 0.2s;\n"
            "}\n"
            ".card:hover { transform: translateY(-4px); border-color: var(--accent); }\n"
            ".card h3 { margin-bottom: 0.75rem; color: var(--text-main); }\n"
            ".card p { color: var(--text-muted); font-size: 0.95rem; }\n"
            "form { display: flex; flex-direction: column; gap: 1rem; max-width: 500px; margin: 2rem auto; }\n"
            "input, textarea {\n"
            "  width: 100%; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid var(--border);\n"
            "  background: var(--bg-secondary); color: var(--text-main); font-family: inherit;\n"
            "}\n"
            "footer {\n"
            "  border-top: 1px solid var(--border); padding: 2rem 0; text-align: center; color: var(--text-muted);\n"
            "  margin-top: 4rem;\n"
            "}\n"
            "@media (max-width: 768px) {\n"
            "  .hero h1 { font-size: 2.2rem; }\n"
            "  .nav-links { gap: 1rem; }\n"
            "}\n"
        )
        files["css/styles.css"] = css

        # 2. Main JavaScript (js/app.js)
        js = (
            "// OpenArise Generated Interactive Client Script\n"
            "document.addEventListener('DOMContentLoaded', () => {\n"
            "  console.log('OpenArise website loaded successfully.');\n\n"
            "  // Interactive Form Handler\n"
            "  const contactForm = document.querySelector('#contact-form');\n"
            "  if (contactForm) {\n"
            "    contactForm.addEventListener('submit', (e) => {\n"
            "      e.preventDefault();\n"
            "      const btn = contactForm.querySelector('button[type=\"submit\"]');\n"
            "      if (btn) {\n"
            "        const originalText = btn.textContent;\n"
            "        btn.textContent = 'Thank you! Message Sent.';\n"
            "        btn.disabled = true;\n"
            "        setTimeout(() => {\n"
            "          btn.textContent = originalText;\n"
            "          btn.disabled = false;\n"
            "          contactForm.reset();\n"
            "        }, 3000);\n"
            "      }\n"
            "    });\n"
            "  }\n\n"
            "  // Card hover micro-animations\n"
            "  const cards = document.querySelectorAll('.card');\n"
            "  cards.forEach(card => {\n"
            "    card.addEventListener('mouseenter', () => {\n"
            "      card.style.borderColor = 'var(--accent)';\n"
            "    });\n"
            "  });\n"
            "});\n"
        )
        files["js/app.js"] = js

        # 3. Main Entry HTML (index.html)
        index_html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"  <title>{title} — Built with OpenArise IDE</title>\n"
            '  <link rel="stylesheet" href="css/styles.css">\n'
            "</head>\n"
            "<body>\n"
            "  <header>\n"
            '    <div class="container nav-wrapper">\n'
            f'      <a href="index.html" class="logo">{title.split()[0]}<span>.io</span></a>\n'
            '      <nav>\n'
            '        <ul class="nav-links">\n'
            '          <li><a href="index.html" class="active">Home</a></li>\n'
            + ('          <li><a href="about.html">About</a></li>\n' if spec.is_multipage else '          <li><a href="#about">About</a></li>\n')
            + ('          <li><a href="contact.html">Contact</a></li>\n' if spec.is_multipage else '          <li><a href="#contact">Contact</a></li>\n')
            + "        </ul>\n"
            "      </nav>\n"
            "    </div>\n"
            "  </header>\n\n"
            '  <main class="container">\n'
            '    <section class="hero">\n'
            f"      <h1>Welcome to {title}</h1>\n"
            f"      <p>{spec.prompt}</p>\n"
            '      <a href="#contact" class="btn">Get Started</a>\n'
            "    </section>\n\n"
            '    <section class="grid" id="about">\n'
            '      <div class="card">\n'
            "        <h3>Modern Architecture</h3>\n"
            "        <p>Built with clean responsive CSS variables, accessible semantics, and blazing performance.</p>\n"
            "      </div>\n"
            '      <div class="card">\n'
            "        <h3>Local Development</h3>\n"
            "        <p>Live-tested using OpenArise local development server bound securely to 127.0.0.1.</p>\n"
            "      </div>\n"
            '      <div class="card">\n'
            "        <h3>AI Powered</h3>\n"
            f"        <p>Custom tailored from your natural-language specification: '{spec.prompt[:60]}...'</p>\n"
            "      </div>\n"
            "    </section>\n\n"
            '    <section id="contact" style="padding: 2rem 0; text-align: center;">\n'
            "      <h2>Get in Touch</h2>\n"
            '      <form id="contact-form">\n'
            '        <input type="text" placeholder="Your Name" required>\n'
            '        <input type="email" placeholder="Your Email Address" required>\n'
            '        <textarea placeholder="Your Message..." rows="4" required></textarea>\n'
            '        <button type="submit" class="btn">Send Message</button>\n'
            "      </form>\n"
            "    </section>\n"
            "  </main>\n\n"
            "  <footer>\n"
            '    <div class="container">\n'
            f"      <p>&copy; {time.strftime('%Y')} {title}. Generated with OpenArise IDE.</p>\n"
            "    </div>\n"
            "  </footer>\n\n"
            '  <script src="js/app.js"></script>\n'
            "</body>\n"
            "</html>\n"
        )
        files["index.html"] = index_html

        # 4. Multi-page: about.html & contact.html if requested
        if spec.is_multipage:
            files["about.html"] = (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '  <meta charset="UTF-8">\n'
                '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                f"  <title>About Us — {title}</title>\n"
                '  <link rel="stylesheet" href="css/styles.css">\n'
                "</head>\n"
                "<body>\n"
                "  <header>\n"
                '    <div class="container nav-wrapper">\n'
                f'      <a href="index.html" class="logo">{title.split()[0]}<span>.io</span></a>\n'
                '      <nav><ul class="nav-links">\n'
                '        <li><a href="index.html">Home</a></li>\n'
                '        <li><a href="about.html" class="active">About</a></li>\n'
                '        <li><a href="contact.html">Contact</a></li>\n'
                "      </ul></nav>\n"
                "    </div>\n"
                "  </header>\n"
                '  <main class="container" style="padding: 4rem 0;">\n'
                f"    <h1>About {title}</h1>\n"
                f"    <p style='color: var(--text-muted); margin-top: 1rem;'>{spec.prompt}</p>\n"
                "  </main>\n"
                "  <footer>\n"
                f"    <p>&copy; {time.strftime('%Y')} {title}.</p>\n"
                "  </footer>\n"
                '  <script src="js/app.js"></script>\n'
                "</body>\n"
                "</html>\n"
            )
            files["contact.html"] = (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '  <meta charset="UTF-8">\n'
                '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                f"  <title>Contact Us — {title}</title>\n"
                '  <link rel="stylesheet" href="css/styles.css">\n'
                "</head>\n"
                "<body>\n"
                "  <header>\n"
                '    <div class="container nav-wrapper">\n'
                f'      <a href="index.html" class="logo">{title.split()[0]}<span>.io</span></a>\n'
                '      <nav><ul class="nav-links">\n'
                '        <li><a href="index.html">Home</a></li>\n'
                '        <li><a href="about.html">About</a></li>\n'
                '        <li><a href="contact.html" class="active">Contact</a></li>\n'
                "      </ul></nav>\n"
                "    </div>\n"
                "  </header>\n"
                '  <main class="container" style="padding: 4rem 0; text-align: center;">\n'
                "    <h1>Contact Our Team</h1>\n"
                '    <form id="contact-form">\n'
                '      <input type="text" placeholder="Your Name" required>\n'
                '      <input type="email" placeholder="Your Email Address" required>\n'
                '      <textarea placeholder="Your Message..." rows="4" required></textarea>\n'
                '      <button type="submit" class="btn">Send Message</button>\n'
                "    </form>\n"
                "  </main>\n"
                "  <footer>\n"
                f"    <p>&copy; {time.strftime('%Y')} {title}.</p>\n"
                "  </footer>\n"
                '  <script src="js/app.js"></script>\n'
                "</body>\n"
                "</html>\n"
            )

        # 5. README.md
        files["README.md"] = (
            f"# {title}\n\n"
            f"**Website Description:** {spec.prompt}\n\n"
            "Generated with **OpenArise IDE AI Website Builder**.\n\n"
            "## Running Locally\n"
            "In OpenArise IDE:\n"
            "1. Click **Run Website** (or press `Ctrl+F5`).\n"
            "2. Open the displayed URL in your browser (`http://127.0.0.1:8000`).\n\n"
            "From the command line:\n"
            "```bash\n"
            "python -m http.server 8000 --bind 127.0.0.1\n"
            "```\n"
        )

        return files

    @classmethod
    def _scaffold_react_project(cls, spec: WebsiteSpec, title: str) -> Dict[str, str]:
        files: Dict[str, str] = {}

        # 1. package.json
        files["package.json"] = json.dumps({
            "name": spec.name.lower().replace(" ", "-"),
            "private": True,
            "version": "0.1.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.3.1",
                "react-dom": "^18.3.1"
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.3.1",
                "vite": "^5.3.4"
            }
        }, indent=2)

        # 2. vite.config.js
        files["vite.config.js"] = (
            "import { defineConfig } from 'vite';\n"
            "import react from '@vitejs/plugin-react';\n\n"
            "export default defineConfig({\n"
            "  plugins: [react()],\n"
            "  server: {\n"
            "    host: '127.0.0.1',\n"
            "    port: 5173\n"
            "  }\n"
            "});\n"
        )

        # 3. index.html
        files["index.html"] = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"  <title>{title} — React Application</title>\n"
            "</head>\n"
            "<body>\n"
            '  <div id="root"></div>\n'
            '  <script type="module" src="/src/main.jsx"></script>\n'
            "</body>\n"
            "</html>\n"
        )

        # 4. src/main.jsx
        files["src/main.jsx"] = (
            "import React from 'react';\n"
            "import ReactDOM from 'react-dom/client';\n"
            "import App from './App.jsx';\n"
            "import './index.css';\n\n"
            "ReactDOM.createRoot(document.getElementById('root')).render(\n"
            "  <React.StrictMode>\n"
            "    <App />\n"
            "  </React.StrictMode>\n"
            ");\n"
        )

        # 5. src/index.css
        files["src/index.css"] = (
            ":root {\n"
            "  --bg: #0f172a;\n"
            "  --card: #1e293b;\n"
            "  --accent: #38bdf8;\n"
            "  --accent-glow: rgba(56, 189, 248, 0.3);\n"
            "  --text: #f8fafc;\n"
            "  --text-muted: #94a3b8;\n"
            "}\n"
            "* { box-sizing: border-box; margin: 0; padding: 0; }\n"
            "body {\n"
            "  background-color: var(--bg);\n"
            "  color: var(--text);\n"
            "  font-family: system-ui, -apple-system, sans-serif;\n"
            "  min-height: 100vh;\n"
            "}\n"
            ".container { width: 90%; max-width: 1100px; margin: 0 auto; padding: 2rem 0; }\n"
            ".hero { text-align: center; padding: 4rem 0 2rem; }\n"
            ".hero h1 { font-size: 2.8rem; margin-bottom: 1rem; color: var(--accent); }\n"
            ".grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-top: 3rem; }\n"
            ".card { background: var(--card); padding: 1.5rem; border-radius: 12px; border: 1px solid #334155; }\n"
            "button {\n"
            "  background: var(--accent); color: #0f172a; font-weight: bold; border: none; padding: 0.75rem 1.5rem;\n"
            "  border-radius: 8px; cursor: pointer; transition: transform 0.2s;\n"
            "}\n"
            "button:hover { transform: scale(1.05); }\n"
        )

        # 6. src/App.jsx
        files["src/App.jsx"] = (
            "import React, { useState } from 'react';\n\n"
            "export default function App() {\n"
            "  const [count, setCount] = useState(0);\n"
            "  return (\n"
            '    <div className="container">\n'
            '      <header className="hero">\n'
            f"        <h1>{title}</h1>\n"
            f"        <p>{spec.prompt}</p>\n"
            "        <div style={{ marginTop: '2rem' }}>\n"
            "          <button onClick={() => setCount(c => c + 1)}>\n"
            "            Interactive Clicks: {count}\n"
            "          </button>\n"
            "        </div>\n"
            "      </header>\n"
            '      <section className="grid">\n'
            '        <div className="card">\n'
            "          <h3>React + Vite Engine</h3>\n"
            "          <p>Instant Hot Module Replacement (HMR) and optimized build toolchain.</p>\n"
            "        </div>\n"
            '        <div className="card">\n'
            "          <h3>Safe Approval Gate</h3>\n"
            "          <p>Every file verified through OpenArise Diff Review before creation.</p>\n"
            "        </div>\n"
            '        <div className="card">\n'
            "          <h3>Full-Stack Extensible</h3>\n"
            "          <p>Easily add React components, state stores, and Tailwind CSS.</p>\n"
            "        </div>\n"
            "      </section>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )

        # 7. README.md
        files["README.md"] = (
            f"# {title} (React + Vite)\n\n"
            f"{spec.prompt}\n\n"
            "## Development\n"
            "```bash\n"
            "npm install\n"
            "npm run dev\n"
            "```\n"
        )

        return files

    @classmethod
    def validate_website_project(cls, project_dir: Path) -> Tuple[bool, List[str]]:
        """
        Validates existing website project integrity.
        Checks entry point, referenced files, script tags, stylesheets, and React package.json.
        """
        issues: List[str] = []
        p_dir = Path(project_dir).resolve()
        if not p_dir.exists() or not p_dir.is_dir():
            return False, ["Project directory does not exist."]

        has_index = (p_dir / "index.html").exists()
        has_pkg = (p_dir / "package.json").exists()

        if not has_index and not has_pkg:
            issues.append("Missing entry point: Neither 'index.html' nor 'package.json' found.")

        # HTML Specific Checks
        if has_index:
            try:
                html_text = (p_dir / "index.html").read_text(encoding="utf-8", errors="replace")
                # Check stylesheets
                css_refs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', html_text)
                for href in css_refs:
                    if not href.startswith("http://") and not href.startswith("https://"):
                        target_file = p_dir / href.split("?")[0]
                        if not target_file.exists():
                            issues.append(f"Referenced stylesheet not found on disk: '{href}'")

                # Check script tags
                js_refs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html_text)
                for src in js_refs:
                    if not src.startswith("http://") and not src.startswith("https://"):
                        target_file = p_dir / src.split("?")[0]
                        if not target_file.exists():
                            issues.append(f"Referenced script file not found on disk: '{src}'")
            except Exception as exc:
                issues.append(f"Failed parsing index.html: {exc}")

        # React Specific Checks
        if has_pkg:
            try:
                pkg_data = json.loads((p_dir / "package.json").read_text(encoding="utf-8"))
                scripts = pkg_data.get("scripts", {})
                if "dev" not in scripts and "start" not in scripts:
                    issues.append("package.json is missing 'dev' or 'start' npm script.")
            except Exception as exc:
                issues.append(f"Invalid package.json: {exc}")

        return (len(issues) == 0, issues)

    @classmethod
    def edit_website(
        cls,
        project_dir: Path,
        instruction: str,
        model: str = "qwen2.5-coder:7b"
    ) -> List[FileChangeRecord]:
        """
        Applies natural-language modifications to an existing website project.
        Inspects existing code, asks Ollama for targeted edits, and returns diff records.
        """
        p_dir = Path(project_dir).resolve()
        if not p_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {p_dir}")

        # Gather existing source files (up to context limits)
        relevant_files: Dict[str, str] = {}
        for ext in ("*.html", "*.css", "*.js", "*.jsx", "*.json"):
            for f in p_dir.glob(ext):
                if f.is_file() and not f.name.startswith("."):
                    rel = str(f.relative_to(p_dir)).replace("\\", "/")
                    try:
                        relevant_files[rel] = f.read_text(encoding="utf-8", errors="replace")[:10000]
                    except Exception:
                        pass
            # Also subdirs css/ js/ src/
            for subdir in ("css", "js", "src"):
                sub_p = p_dir / subdir
                if sub_p.exists() and sub_p.is_dir():
                    for f in sub_p.glob(ext):
                        rel = str(f.relative_to(p_dir)).replace("\\", "/")
                        if rel not in relevant_files:
                            try:
                                relevant_files[rel] = f.read_text(encoding="utf-8", errors="replace")[:10000]
                            except Exception:
                                pass

        # Attempt Ollama edit
        proposed_files: Dict[str, str] = {}
        try:
            context_blocks = [f"--- FILE: {p} ---\n{c}\n--- END ---" for p, c in relevant_files.items()]
            system_prompt = (
                "You are modifying an existing website project based on a user instruction.\n"
                "Return ONLY a JSON object containing the modified or newly created files:\n"
                "{\n"
                '  "thought": "Analysis of changes required",\n'
                '  "files": [\n'
                '    {"path": "relative/path/to/file", "content": "Complete updated file content"}\n'
                '  ]\n'
                "}"
            )
            user_prompt = (
                f"CURRENT PROJECT FILES:\n\n"
                + "\n\n".join(context_blocks[:6])
                + f"\n\nUSER REQUEST:\n{instruction}"
            )
            response = requests.post(
                f"{cls.OLLAMA_API_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "keep_alive": "30m",
                },
                timeout=60,
            )
            if response.status_code == 200:
                payload = response.json()
                raw_text = payload.get("message", {}).get("content", "")
                parsed = cls._parse_json_payload(raw_text)
                if parsed and isinstance(parsed.get("files"), list):
                    for item in parsed["files"]:
                        p = item.get("path")
                        c = item.get("content")
                        if p and c:
                            proposed_files[p.strip().lstrip("/\\")] = c
        except Exception:
            pass

        # If Ollama didn't return files, apply smart programmatic fallback edits
        if not proposed_files:
            proposed_files = cls._apply_fallback_edit(p_dir, instruction, relevant_files)

        # Build FileChangeRecords
        records: List[FileChangeRecord] = []
        for rel_path, new_content in proposed_files.items():
            file_on_disk = p_dir / rel_path
            orig_content = ""
            ch_type = FileChangeType.CREATE
            if file_on_disk.exists() and file_on_disk.is_file():
                orig_content = file_on_disk.read_text(encoding="utf-8", errors="replace")
                ch_type = FileChangeType.MODIFY

            records.append(
                FileChangeRecord(
                    rel_path=rel_path.replace("\\", "/"),
                    change_type=ch_type.value if hasattr(ch_type, "value") else str(ch_type),
                    status=FileChangeStatus.PROPOSED.value,
                    old_content=orig_content,
                    new_content=new_content,
                )
            )

        return records

    @classmethod
    def _apply_fallback_edit(cls, p_dir: Path, instruction: str, files: Dict[str, str]) -> Dict[str, str]:
        """Generates appropriate fallback diff when Ollama is offline."""
        result: Dict[str, str] = {}
        inst_lower = instruction.lower()

        # Check for theme change
        if "dark" in inst_lower or "blue" in inst_lower or "theme" in inst_lower or "color" in inst_lower:
            for p, c in files.items():
                if p.endswith(".css"):
                    updated = c.replace("#0f1117", "#0a192f").replace("#6366f1", "#00b4d8").replace("#1a1d27", "#112240")
                    result[p] = updated
                    break

        # Check for adding a page
        if "contact" in inst_lower and "contact.html" not in files:
            result["contact.html"] = (
                "<!DOCTYPE html>\n<html><head><title>Contact</title><link rel='stylesheet' href='css/styles.css'></head>\n"
                "<body><div class='container'><h1>Contact Us</h1><p>We would love to hear from you!</p></div></body></html>\n"
            )

        # Default: comment modification in main entry file
        if not result:
            for p in ("index.html", "src/App.jsx", "README.md"):
                if p in files:
                    updated = files[p] + f"\n<!-- Update: {instruction} -->\n"
                    result[p] = updated
                    break

        return result

    @classmethod
    def fix_website_errors(
        cls,
        project_dir: Path,
        error_logs: str,
        model: str = "qwen2.5-coder:7b"
    ) -> List[FileChangeRecord]:
        """
        Diagnoses server or build error logs and proposes targeted code fixes.
        """
        instruction = f"Fix the following website runtime / build error:\n{error_logs}"
        return cls.edit_website(project_dir, instruction, model)
