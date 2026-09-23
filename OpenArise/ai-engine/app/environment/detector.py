import sys
import platform
import shutil
import os
from app.environment.models import EnvironmentInfo, InspectionScope

class EnvironmentDetector:
    """Safely detects Python and Git environment details."""
    
    def detect(self, project_root: str) -> EnvironmentInfo:
        info = EnvironmentInfo()
        
        # Current environment python (the one running the agent engine)
        info.python_available = sys.executable is not None
        info.python_executable = sys.executable
        info.python_version = platform.python_version()
        info.platform = platform.system()
        
        # Git availability
        info.git_available = shutil.which("git") is not None
        
        # Virtualenv presence check (do not execute, just observe directories)
        venv_paths = [os.path.join(project_root, ".venv"), os.path.join(project_root, "venv")]
        detected_venv = None
        for venv in venv_paths:
            if os.path.isdir(venv):
                detected_venv = venv
                break
                
        if detected_venv:
            info.virtualenv_present = True
            info.virtualenv_path = detected_venv
            
            # Very basic check for usability (is there a python binary?)
            bin_dir = "Scripts" if info.platform == "Windows" else "bin"
            py_bin = os.path.join(detected_venv, bin_dir, "python.exe" if info.platform == "Windows" else "python")
            info.virtualenv_usable = os.path.isfile(py_bin)
            
            # Scope detection
            # If the currently executing python is NOT inside the project's venv
            if info.python_executable and not info.python_executable.startswith(os.path.abspath(detected_venv)):
                info.inspection_scope = InspectionScope.PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED
            else:
                info.inspection_scope = InspectionScope.CURRENT_ENVIRONMENT
        else:
            info.inspection_scope = InspectionScope.CURRENT_ENVIRONMENT
            
        return info
