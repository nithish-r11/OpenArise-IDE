import json
import logging
import requests
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.llm.base import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Ollama implementation of the LLMProvider."""
    
    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = host or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_MODEL
        self.base_url = self.host.rstrip('/')
        
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate text from a prompt using Ollama."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama generation failed: {e}")
            raise RuntimeError(f"LLM Provider error: {e}")
            
    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        """Generate structured data according to a Pydantic schema."""
        url = f"{self.base_url}/api/generate"
        
        # Append schema instructions to system prompt
        schema_json = json.dumps(schema.model_json_schema())
        schema_instruction = f"\nYou must respond ONLY in valid JSON matching this schema:\n{schema_json}"
        
        full_system = (system_prompt or "") + schema_instruction
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": full_system,
            "stream": False,
            "format": "json"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "{}")
            
            # Parse the response text into the pydantic model
            parsed_json = json.loads(response_text)
            return schema.model_validate(parsed_json)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama structured generation failed: {e}")
            raise RuntimeError(f"LLM Provider connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Ollama returned invalid JSON: {e}")
            raise ValueError(f"LLM Provider returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Ollama structured parsing failed: {e}")
            raise ValueError(f"LLM Provider parsing error: {e}")
            
    def health_check(self) -> bool:
        """Check if the provider is healthy and the model is available."""
        try:
            # Check if server is up
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            # Check if model exists
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]
            
            # Allow model format like 'llama3' or 'llama3:latest'
            model_base = self.model.split(":")[0]
            for m in models:
                if m.startswith(model_base):
                    return True
            
            logger.warning(f"Ollama reachable, but model '{self.model}' not found.")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
