from typing import Optional
from pydantic import BaseModel
from app.llm.base import LLMProvider

class DummyLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        return "dummy response"
        
    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        return schema()
        
    def health_check(self) -> bool:
        return True

def test_llm_provider_interface():
    llm = DummyLLM()
    assert llm.generate("test") == "dummy response"
    assert llm.health_check() is True
