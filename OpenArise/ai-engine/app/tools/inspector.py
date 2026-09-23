import os
from typing import Any, Dict, List
from app.tools.base import BaseTool
from app.tools.permissions import RiskLevel

class ProjectInspectorTool(BaseTool):
    name: str = "inspect_project"
    description: str = "Inspects the project directory structure safely."
    risk_level: RiskLevel = RiskLevel.READ
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {"type": "integer", "description": "Maximum depth to traverse", "default": 3}
                }
            }
        }
        
    def execute(self, max_depth: int = 3, **kwargs) -> Any:
        ignore_dirs = {".git", "node_modules", "__pycache__", "venv", "env", ".venv"}
        result_files = []
        result_dirs = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Calculate current depth
            rel_path = os.path.relpath(root, self.project_root)
            depth = 0 if rel_path == "." else rel_path.count(os.sep) + 1
            
            if depth > max_depth:
                dirs.clear()
                continue
                
            # Filter directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            if rel_path != ".":
                result_dirs.append(rel_path)
                
            for file in files:
                if not file.startswith('.'):
                    full_rel_path = os.path.join(rel_path, file) if rel_path != "." else file
                    result_files.append(full_rel_path)
                    
            if len(result_files) > 1000:
                result_files.append("... [too many files, truncated]")
                break
                
        return {
            "directories": result_dirs[:100],
            "files": result_files
        }
