import json
from app.llm.base import LLMProvider
from app.models.schemas import AgentAction, DiagnosisResult, ConfidenceLevel, FailureCategory


class OfflineLLM(LLMProvider):
    """Only inference is replaced; integration tests use production backend objects."""

    def __init__(self, action):
        self.action = action
        self.action_requests = 0
        self.last_prompt = None

    def health_check(self):
        return True

    def generate(self, prompt, system_prompt=None, **kwargs):
        raise AssertionError("Unexpected unstructured inference")

    def generate_structured(self, prompt, schema, system_prompt=None, **kwargs):
        if schema is AgentAction:
            self.last_prompt = prompt
            self.action_requests += 1
            return self.action(prompt) if callable(self.action) else self.action.model_copy(deep=True)
        if schema is DiagnosisResult:
            return DiagnosisResult(
                category=FailureCategory.RUNTIME_ERROR, summary="Offline failure",
                probable_root_cause="Inspect captured tool output", confidence=ConfidenceLevel.LOW,
            )
        raise ValueError("Offline tests do not propose automatic recovery actions")


def requirements_from_prompt(prompt):
    return json.loads(prompt.split("Requirements:\n", 1)[1].split("\n\nAvailable tools:", 1)[0])
