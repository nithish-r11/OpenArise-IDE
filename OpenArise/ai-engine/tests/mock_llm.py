from typing import Optional, Any
from pydantic import BaseModel
from app.llm.base import LLMProvider

class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for offline testing."""
    
    def __init__(self, should_fail: bool = False, structured_response: Optional[BaseModel] = None, healthy: bool = True):
        self.should_fail = should_fail
        self.structured_response = structured_response
        self.healthy = healthy
        self.last_prompt = None
        self.last_system_prompt = None
        
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if self.should_fail:
            raise RuntimeError("Mock provider failed generation")
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return "Mock response"
        
    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        if self.should_fail:
            raise ValueError("Mock provider failed structured generation")
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self.structured_response:
            return self.structured_response
        return schema()  # Return default instance of schema
        
    def health_check(self) -> bool:
        return self.healthy
