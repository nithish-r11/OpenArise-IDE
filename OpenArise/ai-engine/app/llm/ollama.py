import json
import logging
from copy import deepcopy
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
        # Developer diagnostics contain numeric timing/token counts only, never
        # prompts, source code, model text, paths or credentials.
        metrics = {key: value for key in ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration')
                   if isinstance((value := data.get(key)), int) and not isinstance(value, bool) and 0 <= value < 10**15}
        logger.info('Ollama generation metrics: %s', metrics)
        return data["response"]

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        return self._generate(payload)

    def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None, **kwargs) -> BaseModel:
        generation_schema = schema.model_json_schema()
        if kwargs.get('minimum_tool_calls'):
            generation_schema['properties']['tool_calls']['minItems'] = kwargs['minimum_tool_calls']
        # Constrain model arguments to the actual registered tools. AgentAction's
        # generic argument dictionary alone cannot constrain manifest IDs/revisions.
        if kwargs.get("tool_schemas") and "ToolCall" in generation_schema.get("$defs", {}):
            base = generation_schema["$defs"]["ToolCall"]
            variants = []
            for tool in kwargs["tool_schemas"]:
                parameters = tool["parameters"]
                if any(value.get("enum") == [] for value in parameters.get("properties", {}).values()):
                    continue
                variant = deepcopy(base)
                variant["properties"]["tool_name"] = {"type": "string", "const": tool["name"]}
                variant["properties"]["arguments"] = deepcopy(parameters)
                if tool['name'] == 'write_file':
                    arguments = variant['properties']['arguments']
                    arguments['required'] = list(dict.fromkeys([*arguments.get('required', []), 'overwrite']))
                    arguments['properties']['overwrite'].pop('default', None)
                    arguments['properties']['overwrite']['description'] = 'Explicitly choose true to replace an existing file, or false for exclusive creation of a new file.'
                variant["required"] = list(dict.fromkeys([*variant.get("required", []), "arguments"]))
                variants.append(variant)
            if variants:
                generation_schema["$defs"]["ToolCall"] = {"anyOf": variants}
                if kwargs.get('requested_steps'):
                    by_name = {variant['properties']['tool_name']['const']: variant for variant in variants}
                    ordered = []
                    for step in kwargs['requested_steps']:
                        if step['tool_name'] not in by_name:
                            raise OllamaInvalidResponse('A requested tool is unavailable in this project; no action was executed.')
                        variant = deepcopy(by_name[step['tool_name']])
                        arguments = variant['properties']['arguments']
                        for key, value in step['arguments'].items():
                            if key not in arguments.get('properties', {}):
                                raise OllamaInvalidResponse('Requested tool arguments are invalid; no action was executed.')
                            arguments['properties'][key]['const'] = value
                            arguments['required'] = list(dict.fromkeys([*arguments.get('required', []), key]))
                        ordered.append(variant)
                    generation_schema['properties']['action_type'] = {'type': 'string', 'const': 'tool_call'}
                    generation_schema['properties']['tool_calls'] = {'type': 'array', 'items': ordered,
                        'minItems': len(ordered), 'maxItems': len(ordered)}
                    generation_schema['required'] = list(dict.fromkeys([*generation_schema.get('required', []), 'tool_calls']))
                    generation_schema['$defs'].pop('ToolCall')
        schema_instruction = "\nYou must respond ONLY in valid JSON matching this schema:\n" + json.dumps(generation_schema, separators=(',', ':'))
        payload = {"model": self.model, "prompt": prompt, "system": (system_prompt or "") + schema_instruction,
                   "stream": False, "format": generation_schema if kwargs.get("json_schema") else "json", "options": {"temperature": 0}}
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
