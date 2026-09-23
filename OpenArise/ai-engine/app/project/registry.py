from typing import Dict, List, Optional
from app.project.state import ProjectStateManager
from app.project.models import ProjectState

class ProjectRegistry:
    """In-memory registry for managing multiple project states."""
    
    def __init__(self):
        self._managers: Dict[str, ProjectStateManager] = {}
        
    def register_project(self, root_path: str) -> str:
        """Register a project and return its stable project_id. Creates initial state."""
        # Check if already registered by path
        for pid, manager in self._managers.items():
            if str(manager.root_path) == str(root_path):
                return pid
                
        # Register new
        new_manager = ProjectStateManager(root_path)
        new_manager.refresh() # initial scan
        pid = new_manager.project_id
        if pid:
            self._managers[pid] = new_manager
        return pid

    def get_project(self, project_id: str) -> Optional[ProjectState]:
        """Get the latest state of a project."""
        manager = self._managers.get(project_id)
        if manager:
            return manager.state
        return None

    def close_project(self, project_id: str) -> bool:
        """Close and remove a project from the registry."""
        if project_id in self._managers:
            del self._managers[project_id]
            return True
        return False
        
    def list_projects(self) -> List[str]:
        """List all registered project IDs."""
        return list(self._managers.keys())
