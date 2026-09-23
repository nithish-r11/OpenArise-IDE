from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class LLMProvider(ABC):
    """Base interface for LLM Providers."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate text from a prompt."""
        pass
        
    @abstractmethod
    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        """Generate structured data according to a Pydantic schema."""
        pass
        
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is healthy and available."""
        pass
