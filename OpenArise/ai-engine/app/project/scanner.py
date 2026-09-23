import os
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any

from app.project.models import FileInfo, DependencyInfo

IGNORED_DIRS = {
    '.git', '__pycache__', '.venv', 'venv', 'node_modules',
    'build', 'dist', '.openarise'
}

SENSITIVE_FILES = {
    '.env', 'credentials', 'secret', 'token'
}
SENSITIVE_EXTS = {'.pem', '.key'}

FRAMEWORKS = {'fastapi', 'flask', 'django', 'pytest'}

class ProjectScanner:
    """Safe, read-only project scanner."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        
    def _is_safe_path(self, path: Path) -> bool:
        """Ensure path is within root_path and resolve symlinks safely."""
        try:
            resolved = path.resolve()
            return self.root_path in resolved.parents or resolved == self.root_path
        except Exception:
            return False
            
    def _is_sensitive(self, filename: str) -> bool:
        """Check if file might contain secrets."""
        name_lower = filename.lower()
        if any(s in name_lower for s in SENSITIVE_FILES):
            return True
        ext = Path(filename).suffix.lower()
        if ext in SENSITIVE_EXTS:
            return True
        return False
        
    def _get_content_hash(self, path: Path) -> str:
        """Safely compute SHA-256 hash of file content."""
        hasher = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def scan_files(self) -> Tuple[List[FileInfo], bool]:
        """Scan project files safely."""
        files = []
        git_available = False
        
        # Check for git
        git_dir = self.root_path / '.git'
        if git_dir.exists() and git_dir.is_dir():
            git_available = True
            
        for root, dirs, filenames in os.walk(self.root_path):
            current_dir = Path(root)
            
            # Prevent path traversal and symlink escapes
            if not self._is_safe_path(current_dir):
                dirs.clear()
                continue
                
            # Filter ignored dirs
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
            
            for filename in filenames:
                file_path = current_dir / filename
                
                if not file_path.is_file() or not self._is_safe_path(file_path):
                    continue
                    
                rel_path = file_path.relative_to(self.root_path).as_posix()
                
                try:
                    stat = file_path.stat()
                except Exception:
                    continue
                    
                is_sensitive = self._is_sensitive(filename)
                content_hash = None
                if not is_sensitive:
                    content_hash = self._get_content_hash(file_path)
                    
                file_type = file_path.suffix.lstrip('.') or 'unknown'
                
                is_test = 'test' in filename.lower()
                is_source = file_type in ('py', 'js', 'ts', 'go', 'rs', 'java', 'cpp', 'c', 'h')
                is_config = file_type in ('toml', 'yaml', 'yml', 'json', 'ini') or filename in ('requirements.txt', 'setup.py', 'Dockerfile')
                
                files.append(FileInfo(
                    relative_path=rel_path,
                    file_type=file_type,
                    size=stat.st_size,
                    modified_at=stat.st_mtime,
                    content_hash=content_hash,
                    is_test=is_test,
                    is_source=is_source,
                    is_config=is_config
                ))
                
        return files, git_available

    def scan_dependencies(self) -> List[DependencyInfo]:
        """Statically detect dependencies from common Python config files."""
        deps = []
        
        req_file = self.root_path / 'requirements.txt'
        if req_file.exists() and req_file.is_file() and self._is_safe_path(req_file):
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Simple split for >=, ==, <=, etc.
                            match = re.match(r'^([a-zA-Z0-9\-_]+)(.*)$', line)
                            if match:
                                name = match.group(1).strip()
                                version = match.group(2).strip() or None
                                deps.append(DependencyInfo(
                                    name=name,
                                    version_specifier=version,
                                    source_file='requirements.txt'
                                ))
            except Exception:
                pass
                
        setup_file = self.root_path / 'setup.py'
        if setup_file.exists() and setup_file.is_file() and self._is_safe_path(setup_file):
            try:
                with open(setup_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Very basic static regex extraction for install_requires=['pkg==1.0']
                    matches = re.findall(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
                    for match in matches:
                        pkgs = re.findall(r"['\"]([^'\"]+)['\"]", match)
                        for pkg in pkgs:
                            pkg_match = re.match(r'^([a-zA-Z0-9\-_]+)(.*)$', pkg)
                            if pkg_match:
                                name = pkg_match.group(1).strip()
                                version = pkg_match.group(2).strip() or None
                                deps.append(DependencyInfo(
                                    name=name,
                                    version_specifier=version,
                                    source_file='setup.py'
                                ))
            except Exception:
                pass
                
        return deps
