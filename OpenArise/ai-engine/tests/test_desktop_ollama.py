"""Deterministic regression tests; live Qwen acceptance is run separately."""
from unittest.mock import Mock, patch
import pytest
import requests
from pydantic import ValidationError
from app.config import DesktopSettings
from app.llm.ollama import OllamaProvider, OllamaError, OllamaInvalidResponse
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentRequest, AgentAction
from app.api.backend import BackendService
from app.api.services import ProjectWorkspaceService

def reply(data):
    response = Mock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response

def test_desktop_defaults_and_environment_overrides(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
    c = DesktopSettings(_env_file=None)
    assert (c.OLLAMA_HOST, c.OLLAMA_MODEL, c.OLLAMA_TIMEOUT_SECONDS) == ("http://127.0.0.1:11434", "qwen2.5-coder:7b", 180)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11500")
    monkeypatch.setenv("OLLAMA_MODEL", "another-model:small")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "240")
    c = DesktopSettings(_env_file=None)
    assert (c.OLLAMA_HOST, c.OLLAMA_MODEL, c.OLLAMA_TIMEOUT_SECONDS) == ("http://127.0.0.1:11500", "another-model:small", 240)

def test_desktop_dotenv_override(tmp_path):
    env = tmp_path / "provider.env"
    env.write_text("OLLAMA_HOST=http://127.0.0.1:11501\nOLLAMA_MODEL=configured:small\nOLLAMA_TIMEOUT_SECONDS=210\n")
    c = DesktopSettings(_env_file=env)
    assert (c.OLLAMA_HOST, c.OLLAMA_MODEL, c.OLLAMA_TIMEOUT_SECONDS) == ("http://127.0.0.1:11501", "configured:small", 210)

@pytest.mark.parametrize("timeout", [0, 29, 901])
def test_timeout_bounds(timeout):
    with pytest.raises(ValidationError):
        DesktopSettings(_env_file=None, OLLAMA_TIMEOUT_SECONDS=timeout)

def test_exact_model_availability_rejects_wrong_parameter_tag():
    p = OllamaProvider(model="qwen2.5-coder:7b")
    with patch("requests.get", return_value=reply({"models": [{"name": "qwen2.5-coder:32b"}]})):
        assert p.availability()["status"] == "model_unavailable"
    with patch("requests.get", return_value=reply({"models": [{"name": "qwen2.5-coder:7b"}]})):
        assert p.check_available() is True

def test_ollama_unavailable_is_distinct_and_does_not_expose_transport_details():
    p = OllamaProvider(model="qwen2.5-coder:7b")
    with patch("requests.get", side_effect=requests.ConnectionError("password=private-value")):
        status = p.availability()
    assert status["status"] == "ollama_unavailable"
    assert "private-value" not in status["message"]

def test_generation_model_not_found_is_distinct():
    response = requests.Response()
    response.status_code = 404
    p = OllamaProvider(model="missing:7b")
    with patch("requests.post", side_effect=requests.HTTPError("private response body", response=response)):
        with pytest.raises(OllamaError) as failure:
            p.generate("test")
    assert failure.value.code == "model_unavailable"
    assert "private" not in str(failure.value)

def test_generation_timeout_is_explicit_and_configurable():
    p = OllamaProvider(model="qwen2.5-coder:7b", timeout=240)
    with patch("requests.post", side_effect=requests.Timeout("private diagnostics")) as post:
        with pytest.raises(OllamaError) as failure:
            p.generate("test")
    assert post.call_args.kwargs["timeout"] == (5, 240)
    assert failure.value.code == "llm_timeout"
    assert "240 seconds" in failure.value.safe_message
    assert "private" not in failure.value.safe_message

def test_generation_http_failure_is_not_connection_unavailable():
    response = requests.Response()
    response.status_code = 500
    with patch("requests.post", side_effect=requests.HTTPError("private body", response=response)):
        with pytest.raises(OllamaError) as failure:
            OllamaProvider().generate("test")
    assert failure.value.code == "llm_generation_failed"

def test_invalid_action_schema_is_safe():
    with patch("requests.post", return_value=reply({"response": '{"password":"private-value"}', "done": True})):
        with pytest.raises(OllamaInvalidResponse) as failure:
            OllamaProvider().generate_structured("test", AgentAction)
    assert "private-value" not in str(failure.value)

def test_real_backend_envelope_retains_model_answer_without_false_verification(tmp_path):
    provider = OllamaProvider(model="qwen2.5-coder:7b")
    agent = AgentOrchestrator(provider, project_root=str(tmp_path))
    service = BackendService(ProjectWorkspaceService(str(tmp_path), agent))
    with patch("requests.get", return_value=reply({"models":[{"name":provider.model}]})), patch("requests.post", return_value=reply({"response": '{"action_type":"message","tool_calls":[],"message":"def multiply(a, b):\\n    return a * b"}', "done":True})) as post:
        result = service.dispatch({"request_id":"real-envelope","method":"request_agent_execution","params":{"prompt":"Create a Python function named multiply(a, b) that returns a * b."}})
    assert result.request_id == "real-envelope"
    assert result.success is True
    assert result.data["status"] == "unverified"
    assert result.data["data"]["agent_message"] == "def multiply(a, b):\n    return a * b"
    assert result.data["data"]["tool_results"] == []
    assert result.data["data"]["verification"]["overall_status"] != "VERIFIED"
    assert post.call_args.kwargs["json"]["model"] == "qwen2.5-coder:7b"
    assert post.call_args.kwargs["json"]["stream"] is False
    assert "intelligence_summary" in post.call_args.kwargs["json"]["prompt"]

@pytest.mark.parametrize("code,category", [("ollama_unavailable","ENVIRONMENT_ERROR"),("model_unavailable","CONFIGURATION_ERROR"),("llm_timeout","TIMEOUT"),("llm_generation_failed","UNKNOWN")])
def test_agent_maps_safe_provider_failures_without_bypassing_gate(tmp_path, code, category):
    provider = OllamaProvider(model="qwen2.5-coder:7b")
    agent = AgentOrchestrator(provider, project_root=str(tmp_path))
    with patch.object(provider,"check_available",side_effect=OllamaError(code,"Safe provider reason.")):
        result = agent.process_request(AgentRequest(prompt="Explain this project."))
    assert result.status == "failure"
    assert result.message == "Safe provider reason."
    assert result.data["error"]["category"] == category
    assert result.data["verification"]["overall_status"] != "VERIFIED"
    assert result.data["tool_results"] == []

def test_answer_only_schema_rejects_model_tool_calls():
    from app.models.schemas import AgentMessageAction
    with pytest.raises(ValidationError):
        AgentMessageAction(action_type="tool_call", tool_calls=[{"tool_name":"write_file"}], message="unsafe")

def test_answer_only_backend_uses_same_provider_and_gate(tmp_path):
    provider = OllamaProvider(model="qwen2.5-coder:7b")
    agent = AgentOrchestrator(provider, project_root=str(tmp_path))
    service = BackendService(ProjectWorkspaceService(str(tmp_path), agent))
    with patch("requests.get", return_value=reply({"models":[{"name":provider.model}]})), patch("requests.post", return_value=reply({"response": '{"action_type":"message","tool_calls":[],"message":"def multiply(a, b):\\n    return a * b"}', "done":True})) as post:
        result=service.dispatch({"request_id":"answer-only","method":"request_agent_execution","params":{"prompt":"Create multiply code.", "context_data":{"response_mode":"text_only"}}})
    assert result.success and result.data["status"]=="unverified"
    assert result.data["data"]["tool_results"]==[]
    assert result.data["data"]["verification"]["overall_status"]!="VERIFIED"
    payload=post.call_args.kwargs["json"]
    assert payload["format"]["properties"]["tool_calls"]["maxItems"]==0
    assert "Available tools:" not in payload["prompt"]
    assert "intelligence_summary" in payload["prompt"]

def test_answer_only_invalid_model_action_fails_without_executing(tmp_path):
    provider=OllamaProvider(model="qwen2.5-coder:7b")
    agent=AgentOrchestrator(provider, project_root=str(tmp_path))
    with patch("requests.get",return_value=reply({"models":[{"name":provider.model}]})), patch("requests.post",return_value=reply({"response":'{"action_type":"tool_call","tool_calls":[{"tool_name":"write_file"}],"message":"write"}',"done":True})):
        result=agent.process_request(AgentRequest(prompt="Show code.",context_data={"response_mode":"text_only"}))
    assert result.status=="failure"
    assert result.pending_action is None
    assert result.data["tool_results"]==[]
    assert result.data["error"]["error_signature"]=="llm_generation_failed"