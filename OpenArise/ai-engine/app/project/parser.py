import ast
import os
from typing import Optional
from app.project.models import PythonModuleInfo

class PythonParser:
    """Safe Python AST parser."""
    
    @staticmethod
    def parse_file(file_path: str, relative_path: str, module_name: str) -> PythonModuleInfo:
        """Parse a Python file using AST and extract structural information."""
        info = PythonModuleInfo(
            relative_path=relative_path,
            module_name=module_name
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            info.syntax_error = f"Failed to read file: {e}"
            return info
            
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            info.syntax_error = f"SyntaxError: {e.msg} at line {e.lineno}"
            return info
        except Exception as e:
            info.syntax_error = f"Error parsing AST: {e}"
            return info
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    info.imports.append(node.module)
            elif isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                if node.name.startswith('test_'):
                    info.test_functions.append(node.name)
                else:
                    info.functions.append(node.name)
                    
        # Remove duplicates
        info.imports = list(set(info.imports))
        
        return info
