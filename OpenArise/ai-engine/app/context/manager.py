from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from app.context.adapter import bounded_intelligence_summary
from app.memory.redact import SecretRedactor

@dataclass
class ContextManager:
    """Manages the context for the agent."""
    
    user_request: Optional[str] = None
    project_root: Optional[str] = None
    selected_files: List[str] = field(default_factory=list)
    relevant_code: Dict[str, str] = field(default_factory=dict)
    terminal_output: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    previous_failures: List[Dict[str, Any]] = field(default_factory=list)
    project_state: Dict[str, Any] = field(default_factory=dict)
    
    def update_request(self, request: str):
        self.user_request = request
        
    def add_selected_file(self, file_path: str):
        if file_path not in self.selected_files:
            self.selected_files.append(file_path)
            
    def add_relevant_code(self, file_path: str, code: str):
        self.relevant_code[file_path] = code
        
    def add_terminal_output(self, output: str):
        self.terminal_output.append(output)
        
    def add_tool_result(self, result: Dict[str, Any]):
        self.tool_results.append(result)
        
    def add_failure(self, failure: Dict[str, Any]):
        self.previous_failures.append(failure)
        
    def get_context_summary(self) -> Dict[str, Any]:
        """Returns a summary of the current context for the LLM."""
        summary = {
            "user_request": self.user_request,
            "project_root": self.project_root,
            "selected_files": self.selected_files[:20],
            "code_snippets": len(self.relevant_code),
            "recent_terminal": [SecretRedactor().redact(line[:1000]) for line in self.terminal_output[-5:]],
            "recent_tools": [
                {key: result.get(key) for key in ("tool_name", "tool_call_id", "success", "exit_code")}
                for result in self.tool_results[-5:]
            ],
            "failures": len(self.previous_failures)
        }
        intelligence = bounded_intelligence_summary(self.project_state.get("intelligence_summary"))
        if intelligence:
            summary["intelligence_summary"] = intelligence
        return summary
