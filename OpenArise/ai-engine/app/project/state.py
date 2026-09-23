import os
from pathlib import Path
from typing import Dict, Optional

from app.project.models import ProjectInfo, ProjectState, FileInfo
from app.project.scanner import ProjectScanner, FRAMEWORKS
from app.project.parser import PythonParser

class ProjectStateManager:
    """Orchestrates scanning, parsing, and tracking project state."""
    
    def __init__(self, root_path: str, project_id: Optional[str] = None):
        self.root_path = Path(root_path).resolve()
        self.scanner = ProjectScanner(str(self.root_path))
        self.state: Optional[ProjectState] = None
        self.project_id = project_id
        
    def _calculate_health_signals(self, files: list[FileInfo], modules: list, deps: list, git_avail: bool) -> dict:
        signals = {
            "empty_project": len(files) == 0,
            "no_python_files": not any(f.file_type == 'py' for f in files),
            "no_tests": not any(f.is_test for f in files),
            "syntax_errors": any(m.syntax_error for m in modules if m.syntax_error),
            "git_available": git_avail,
            "missing_dependency_declaration": len(deps) == 0
        }
        return signals

    def refresh(self) -> ProjectState:
        """Scan, parse, and refresh the entire project state safely."""
        # 1. Scan files
        files, git_available = self.scanner.scan_files()
        
        # 2. Extract basic info
        project_name = self.root_path.name
        
        if not self.state:
            info = ProjectInfo(root_path=str(self.root_path), name=project_name)
            if self.project_id:
                info.project_id = self.project_id
            self.project_id = info.project_id
        else:
            info = self.state.project_info

        # 3. Parse python modules
        python_modules = []
        frameworks_detected = set()
        test_files = []
        
        # Determine changed files by comparing with previous state (if any)
        prev_hashes = {f.relative_path: f.content_hash for f in self.state.files} if self.state else {}
        prev_modules = {m.relative_path: m for m in self.state.python_modules} if self.state else {}
        
        for f in files:
            if f.file_type == 'py':
                # Skip re-parsing if content hash is identical
                if f.content_hash and f.content_hash == prev_hashes.get(f.relative_path) and f.relative_path in prev_modules:
                    mod_info = prev_modules[f.relative_path]
                else:
                    file_path = str(self.root_path / f.relative_path)
                    mod_info = PythonParser.parse_file(file_path, f.relative_path, Path(f.relative_path).stem)
                    
                python_modules.append(mod_info)
                
                # Check frameworks in imports
                for imp in mod_info.imports:
                    base_imp = imp.split('.')[0].lower()
                    if base_imp in FRAMEWORKS:
                        frameworks_detected.add(base_imp)
                        
                if mod_info.test_functions:
                    test_files.append(f.relative_path)
                    
            if f.is_test and f.relative_path not in test_files:
                test_files.append(f.relative_path)

        # 4. Scan dependencies
        dependencies = self.scanner.scan_dependencies()
        
        # Add frameworks from dependencies too
        for dep in dependencies:
            name_lower = dep.name.lower()
            if name_lower in FRAMEWORKS:
                frameworks_detected.add(name_lower)

        # 5. Calculate Health
        health = self._calculate_health_signals(files, python_modules, dependencies, git_available)

        # 6. Build State
        self.state = ProjectState(
            project_info=info,
            files=files,
            python_modules=python_modules,
            dependencies=dependencies,
            frameworks=list(frameworks_detected),
            tests=test_files,
            git_available=git_available,
            health_signals=health
        )
        
        return self.state
