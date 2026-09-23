import os
import subprocess
import sys
from typing import Any, Dict
from app.tools.base import BaseTool
from app.tools.permissions import RiskLevel
from app.tools.fs import _is_safe_path

class PythonExecutionTool(BaseTool):
    name: str = "execute_python"
    description: str = "Executes a python script safely."
    risk_level: RiskLevel = RiskLevel.EXECUTE
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "script_path": {"type": "string", "description": "Relative path to python script"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments to pass"
                    },
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 10}
                },
                "required": ["script_path"]
            }
        }
        
    def execute(self, script_path: str, args: list[str] = None, timeout: int = 10, **kwargs) -> Any:
        if not _is_safe_path(self.project_root, script_path):
            raise ValueError(f"Execution of path '{script_path}' is denied.")
            
        full_path = os.path.join(self.project_root, script_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Script '{script_path}' not found.")
            
        cmd = [sys.executable, full_path]
        if args:
            cmd.extend(args)
            
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired as e:
            return {
                "exit_code": -1,
                "stdout": e.stdout.decode('utf-8') if e.stdout else "",
                "stderr": e.stderr.decode('utf-8') if e.stderr else "Execution timed out.",
                "error": "TimeoutExpired"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to execute script: {e}")

class TestExecutionTool(BaseTool):
    __test__ = False
    name: str = "execute_tests"
    description: str = "Executes pytest in the project root."
    risk_level: RiskLevel = RiskLevel.EXECUTE
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Specific test file/dir to run (optional)"}
                }
            }
        }
        
    def execute(self, test_path: str = None, **kwargs) -> Any:
        # Avoid running pytest with full shell=True for safety
        # Instead, invoke pytest module using current python interpreter
        cmd = [sys.executable, "-m", "pytest"]
        if test_path:
            if not _is_safe_path(self.project_root, test_path):
                raise ValueError(f"Access to test path '{test_path}' is denied.")
            cmd.append(test_path)
            
        try:
            # We don't want tests running forever in agent logic
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired as e:
            return {
                "exit_code": -1,
                "stdout": e.stdout.decode('utf-8') if e.stdout else "",
                "stderr": e.stderr.decode('utf-8') if e.stderr else "Pytest execution timed out.",
                "error": "TimeoutExpired"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to execute pytest: {e}")
