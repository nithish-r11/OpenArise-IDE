import json
import logging
import requests
from typing import Optional
from pydantic import BaseModel, ValidationError
from app.llm.base import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

class OllamaError(RuntimeError):
    """Stable safe reason; HTTP bodies, credentials and prompts are never exposed."""
    def __init__(self, code, message):
        self.code, self.safe_message = code, message
        super().__init__("LLM Provider error: " + message)

class OllamaInvalidResponse(ValueError):
    code = "llm_generation_failed"
    def __init__(self, message):
        self.safe_message = message
        super().__init__(message)

class OllamaProvider(LLMProvider):
    """Existing synchronous Ollama provider; no fallback or automatic model pull."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        self.host = host or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_MODEL
        self.base_url = self.host.rstrip("/")
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT_SECONDS
        if not isinstance(self.timeout, int) or not 30 <= self.timeout <= 900:
            raise ValueError("Ollama timeout must be 30–900 seconds.")

    @staticmethod
    def _http_error(exc):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code == 404:
            return OllamaError("model_unavailable", "Configured Ollama model is unavailable. Install it in Ollama or correct OLLAMA_MODEL, then restart OpenArise.")
        return OllamaError("llm_generation_failed", "Ollama rejected generation. Check the model and Ollama service logs; no successful action is confirmed.")

    def check_available(self):
        """Check the exact configured tag, not a prefix that could match another size."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=(5, 5))
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            raise OllamaError("ollama_unavailable", "Ollama is unavailable. Start the service and check OLLAMA_HOST, then retry.") from exc
        except ValueError as exc:
            raise OllamaError("ollama_unavailable", "Ollama returned an invalid availability response. Check the configured endpoint.") from exc
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise OllamaError("ollama_unavailable", "Ollama returned an invalid model list. Check the configured endpoint.")
        expected = self.model if ":" in self.model.rsplit("/", 1)[-1] else self.model + ":latest"
        names = {row.get("name") or row.get("model") for row in models if isinstance(row, dict)}
        if self.model not in names and expected not in names:
            raise OllamaError("model_unavailable", "Configured Ollama model is not installed. Install it in Ollama or correct OLLAMA_MODEL, then restart OpenArise.")
        return True

    def availability(self):
        try:
            self.check_available()
            return {"status": "ready", "message": "Ollama is reachable and the configured model is installed."}
        except OllamaError as exc:
            return {"status": exc.code, "message": exc.safe_message}

    def _generate(self, payload):
        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=(5, self.timeout))
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise OllamaError("llm_timeout", f"Ollama generation timed out after {self.timeout} seconds. Local inference is synchronous; check model load and hardware before retrying.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError("ollama_unavailable", "Ollama is unavailable. Start the service and check OLLAMA_HOST, then retry.") from exc
        except requests.exceptions.RequestException as exc:
            raise self._http_error(exc) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaInvalidResponse("Ollama returned invalid JSON in its response envelope.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("response"), str) or not data["response"].strip() or data.get("done") is False:
            raise OllamaInvalidResponse("Ollama returned an empty or incomplete generation response.")
        return data["response"]

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        return self._generate(payload)

    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        schema_instruction = "\nYou must respond ONLY in valid JSON matching this schema:\n" + json.dumps(schema.model_json_schema())
        payload = {"model": self.model, "prompt": prompt, "system": (system_prompt or "") + schema_instruction,
                   "stream": False, "format": schema.model_json_schema() if kwargs.get("json_schema") else "json", "options": {"temperature": 0}}
        response_text = self._generate(payload)
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise OllamaInvalidResponse("Ollama returned invalid JSON for the requested action.") from exc
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise OllamaInvalidResponse("Ollama generation did not match the requested action schema.") from exc

    def health_check(self) -> bool:
        return self.availability()["status"] == "ready"
