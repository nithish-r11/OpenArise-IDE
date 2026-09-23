import importlib.metadata
from typing import List, Dict
from app.project.models import ProjectState
from app.environment.models import DependencyStatus, DependencyState, InstallationAction, EnvironmentInfo, InspectionScope

class DependencyInspector:
    """Safely inspects dependencies without executing arbitrary code."""
    
    def inspect(self, state: ProjectState, env_info: EnvironmentInfo) -> List[DependencyStatus]:
        results = []
        
        # Determine if we can inspect the environment
        if env_info.inspection_scope == InspectionScope.PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED:
            # We can't safely inspect the target venv with importlib.metadata since we are running outside it
            for dep in state.dependencies:
                results.append(DependencyStatus(
                    name=dep.name,
                    version_specifier=dep.version_specifier,
                    declared=True,
                    status=DependencyState.INSPECTION_NOT_AVAILABLE,
                    source_file=dep.source_file,
                    action=InstallationAction.REVIEW_REQUIRED,
                    message="Project virtualenv exists but is not currently inspected."
                ))
            return results

        # We are inspecting the current environment
        # Build map of installed packages
        installed_packages = {}
        for dist in importlib.metadata.distributions():
            installed_packages[dist.metadata["Name"].lower()] = dist.version

        # Evaluate declared dependencies
        for dep in state.dependencies:
            name_lower = dep.name.lower()
            
            # Simple version parsing (e.g. >=1.0.0, ==2.0.0) could be added here.
            # For MVP, we check existence and match exact `==` if present.
            status = DependencyState.DECLARED
            action = InstallationAction.INSTALL_REQUIRED
            installed_version = installed_packages.get(name_lower)
            message = None
            
            if installed_version:
                status = DependencyState.INSTALLED
                action = InstallationAction.READY
                
                # Basic version mismatch check for strict equality
                if dep.version_specifier and dep.version_specifier.startswith("=="):
                    req_ver = dep.version_specifier[2:].strip()
                    if installed_version != req_ver:
                        status = DependencyState.VERSION_MISMATCH
                        action = InstallationAction.REVIEW_REQUIRED
                        message = f"Version mismatch. Required: {req_ver}, Installed: {installed_version}"
            else:
                status = DependencyState.MISSING
                message = f"Missing required dependency '{dep.name}'"
                
            results.append(DependencyStatus(
                name=dep.name,
                version_specifier=dep.version_specifier,
                declared=True,
                installed=installed_version is not None,
                installed_version=installed_version,
                status=status,
                source_file=dep.source_file,
                action=action,
                message=message
            ))
            
        return results
