import os
import re
from typing import Dict, Any, Optional
from app.models.schemas import ToolResult, FailureCategory

class FailureDetector:
    """Detects and deterministically classifies failures from ToolResults."""
    
    def detect(self, tool_result: ToolResult) -> Optional[Dict[str, Any]]:
        """
        Evaluates a ToolResult and returns a deterministic classification if a failure is detected.
        Returns None if successful.
        """
        if tool_result.success:
            return None
            
        error_msg = tool_result.error or ""
        output_data = tool_result.output or {}
        
        stderr = ""
        stdout = ""
        
        if isinstance(output_data, dict):
            stderr = output_data.get("stderr", "")
            stdout = output_data.get("stdout", "")
            
        full_text = f"{error_msg}\n{stderr}\n{stdout}"
        
        # 1. Deterministic classification
        category = self._classify_text(full_text)
        
        if error_msg == "permission_required":
            category = FailureCategory.PERMISSION_ERROR
            
        # 2. Extract affected file if obvious
        affected_file = self._extract_file(full_text)
        
        # 3. Create normalized signature
        normalized_error = self._normalize_error(full_text, category)
        signature = f"{tool_result.tool_name}:{category.value}:{normalized_error}"
        
        return {
            "category": category,
            "error_signature": signature,
            "affected_file": affected_file,
            "summary": self._extract_summary(full_text, category)
        }
        
    def _classify_text(self, text: str) -> FailureCategory:
        if "TimeoutExpired" in text or "Execution timed out" in text:
            return FailureCategory.TIMEOUT
        if "ModuleNotFoundError" in text or "ImportError" in text:
            return FailureCategory.IMPORT_ERROR
        if "SyntaxError" in text or "IndentationError" in text:
            return FailureCategory.SYNTAX_ERROR
        if "FileNotFoundError" in text or "No such file or directory" in text:
            return FailureCategory.FILE_NOT_FOUND
        if "PermissionError" in text or "Access is denied" in text or "permission denied" in text.lower():
            return FailureCategory.PERMISSION_ERROR
        if "AssertionError" in text or "FAILED" in text and "==" in text:
            return FailureCategory.TEST_FAILURE
        if "Exception" in text or "Error" in text:
            return FailureCategory.RUNTIME_ERROR
            
        return FailureCategory.UNKNOWN
        
    def _normalize_error(self, text: str, category: FailureCategory) -> str:
        """Create a deterministic normalized string from the error to use as a signature."""
        if category == FailureCategory.IMPORT_ERROR:
            match = re.search(r"No module named '([^']+)'", text)
            if match:
                return match.group(1)
        if category == FailureCategory.FILE_NOT_FOUND:
            match = re.search(r"No such file or directory: '([^']+)'", text)
            if match:
                return os.path.basename(match.group(1))
        
        # Fallback to the first exception line or first 50 chars
        lines = text.splitlines()
        for line in reversed(lines):
            if "Error" in line or "Exception" in line:
                return line.strip()[:100]
                
        return text.strip()[:50]
        
    def _extract_file(self, text: str) -> Optional[str]:
        # Simple extraction for python tracebacks
        match = re.search(r'File "([^"]+)", line \d+', text)
        if match:
            return match.group(1)
        return None
        
    def _extract_summary(self, text: str, category: FailureCategory) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Unknown error occurred."
            
        # Try to find the actual error line
        for line in reversed(lines):
            if "Error:" in line or "Exception:" in line:
                return line
                
        return lines[-1] if lines else "Error details unavailable."
