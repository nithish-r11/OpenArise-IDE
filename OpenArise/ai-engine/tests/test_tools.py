import pytest
from typing import Any, Dict
from app.tools.base import BaseTool, ToolRegistry

class DummyTool(BaseTool):
    name: str = "dummy_tool"
    description: str = "A dummy tool for testing."
    
    def execute(self, **kwargs) -> Any:
        return "success"
        
    def get_schema(self) -> Dict[str, Any]:
        return {"name": self.name}

def test_tool_registry():
    registry = ToolRegistry()
    tool = DummyTool()
    
    registry.register(tool)
    
    retrieved_tool = registry.get_tool("dummy_tool")
    assert retrieved_tool == tool
    assert retrieved_tool.execute() == "success"
    
    schemas = registry.get_all_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy_tool"
    
    with pytest.raises(KeyError):
        registry.get_tool("nonexistent_tool")
