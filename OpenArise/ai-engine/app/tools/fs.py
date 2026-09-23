import os
from typing import Any, Dict
from app.tools.base import BaseTool
from app.tools.permissions import RiskLevel

def _is_safe_path(project_root: str, relative_path: str) -> bool:
    abs_path = os.path.abspath(os.path.join(project_root, relative_path))
    if not abs_path.startswith(os.path.abspath(project_root)):
        return False
    
    base_name = os.path.basename(abs_path)
    sensitive_files = {".env", "credentials", "id_rsa", "id_ed25519", "secrets.json"}
    if base_name in sensitive_files:
        return False
    return True

class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Reads a file from the project safely."
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
                    "path": {"type": "string", "description": "Relative path to read"}
                },
                "required": ["path"]
            }
        }
        
    def execute(self, path: str, **kwargs) -> Any:
        if not _is_safe_path(self.project_root, path):
            raise ValueError(f"Access to path '{path}' is denied.")
            
        full_path = os.path.join(self.project_root, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File '{path}' not found.")
            
        file_size = os.path.getsize(full_path)
        if file_size > 5 * 1024 * 1024:
            raise ValueError(f"File '{path}' is too large ({file_size} bytes).")
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {
            "path": path,
            "size": file_size,
            "content": content
        }

class WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = "Creates or replaces a project file."
    risk_level: RiskLevel = RiskLevel.WRITE
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to write"},
                    "content": {"type": "string", "description": "File content"},
                    "overwrite": {"type": "boolean", "description": "Set to true to explicitly overwrite", "default": False}
                },
                "required": ["path", "content"]
            }
        }
        
    def execute(self, path: str, content: str, overwrite: bool = False, **kwargs) -> Any:
        if not _is_safe_path(self.project_root, path):
            raise ValueError(f"Write access to path '{path}' is denied.")
            
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Content too large.")
            
        full_path = os.path.join(self.project_root, path)
        if os.path.exists(full_path) and not overwrite:
            raise FileExistsError(f"File '{path}' already exists. Use overwrite=True to replace.")
            
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return {"path": path, "status": "written", "bytes": len(content)}

class EditFileTool(BaseTool):
    name: str = "edit_file"
    description: str = "Edits a project file via exact string replacement."
    risk_level: RiskLevel = RiskLevel.WRITE
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path"},
                    "old_text": {"type": "string", "description": "Exact old text"},
                    "new_text": {"type": "string", "description": "New text"}
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
        
    def execute(self, path: str, old_text: str, new_text: str, **kwargs) -> Any:
        if not _is_safe_path(self.project_root, path):
            raise ValueError(f"Edit access to path '{path}' is denied.")
            
        full_path = os.path.join(self.project_root, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File '{path}' not found.")
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        count = content.count(old_text)
        if count == 0:
            raise ValueError("old_text not found in file.")
        elif count > 1:
            raise ValueError(f"old_text found {count} times. Ambiguous edit.")
            
        new_content = content.replace(old_text, new_text)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return {"path": path, "status": "edited"}
