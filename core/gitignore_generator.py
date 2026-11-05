"""
Built-in .gitignore templates generator for OpenArise IDE.
Supports Python, Node.js, Java, C++, C#, Flutter, and General Development.
Includes overwrite protection.
"""

from pathlib import Path
from typing import Dict, List, Tuple


GITIGNORE_TEMPLATES: Dict[str, str] = {
    "Python": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing & Coverage
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
""",

    "Node.js": """# Logs
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Dependency directories
node_modules/
jspm_packages/

# Production build artifacts
dist/
build/
.next/
out/

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
""",

    "Java": """# Compiled class file
*.class

# Log file
*.log

# BlueJ files
*.ctxt

# Mobile Tools for Java (J2ME)
.mtj.tmp/

# Package Files #
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# virtual machine crash logs
hs_err_pid*
replay_pid*

# Build tools
target/
.gradle/
build/
""",

    "C++": """# Prerequisites
*.d

# Compiled Object files
*.slo
*.lo
*.o
*.obj

# Precompiled Headers
*.gch
*.pch

# Compiled Dynamic libraries
*.so
*.dylib
*.dll

# Fortran module files
*.mod
*.smod

# Compiled Static libraries
*.lai
*.la
*.a
*.lib

# Executables
*.exe
*.out
*.app
build/
cmake-build-*/
""",

    "C#": """## Core
bin/
obj/

# Visual Studio files
.vs/
*.user
*.userosscache
*.suo
*.userprefs

# Build results
[Dd]ebug/
[Rr]elease/
x64/
x86/
[Bb]uild/
bld/
[Bb]in/
[Oo]bj/
""",

    "Flutter": """# Flutter/Dart artifacts
.dart_tool/
.flutter-plugins
.flutter-plugins-dependencies
.packages
.pub-cache/
.pub/
build/

# Android-specific
android/app/debug/
android/app/profile/
android/app/release/

# iOS-specific
ios/.generated/
ios/Flutter/App.framework
ios/Flutter/Flutter.framework
ios/Flutter/Flutter.podspec
ios/Pods/
""",

    "General development": """# Operating System Files
.DS_Store
Thumbs.db
Desktop.ini
$RECYCLE.BIN/

# Editor / IDE settings
.vscode/
.idea/
*.swp
*.swo
*~
*.bak

# Temporary files
*.tmp
*.temp
"""
}


class GitignoreGenerator:
    """Generates combined or single .gitignore files safely."""

    @staticmethod
    def list_templates() -> List[str]:
        return list(GITIGNORE_TEMPLATES.keys())

    @staticmethod
    def get_template(name: str) -> str:
        return GITIGNORE_TEMPLATES.get(name, "")

    @classmethod
    def generate_gitignore(
        cls,
        target_dir: Path,
        template_names: List[str],
        overwrite: bool = False,
    ) -> Tuple[bool, str]:
        """
        Generates a .gitignore file in target_dir from chosen templates.
        Protects against overwriting existing files unless explicitly specified.
        """
        dest = (target_dir / ".gitignore").resolve()
        if dest.exists() and not overwrite:
            return False, "A .gitignore file already exists. Overwrite confirmation required."

        blocks = []
        for name in template_names:
            content = cls.get_template(name)
            if content:
                blocks.append(f"# === {name} ===\n{content.strip()}\n")

        if not blocks:
            return False, "No valid templates selected."

        full_content = "\n".join(blocks)
        try:
            dest.write_text(full_content, encoding="utf-8")
            return True, f"Generated .gitignore with {len(template_names)} template(s)."
        except Exception as exc:
            return False, f"Failed to write .gitignore: {exc}"

