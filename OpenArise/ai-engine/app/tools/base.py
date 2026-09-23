from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from app.tools.permissions import RiskLevel

class BaseTool(ABC):
    """Base interface for all agent tools."""
    
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.READ
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the tool with the given arguments."""
        pass
        
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return the JSON schema representation of the tool's expected arguments."""
        pass

class ToolRegistry:
    """Registry to hold and manage available tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        
    def get_tool(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool {name} not found in registry.")
        return self._tools[name]
        
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self._tools.values()]
