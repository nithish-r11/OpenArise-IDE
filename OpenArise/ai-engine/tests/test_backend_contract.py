import json
import pytest

from app.api.backend import BackendService, BackendRequest, BackendResponse
from app.api.services import ProjectWorkspaceService
from app.api.models import ErrorCode
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentAction, ToolCall
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from tests.hardening_helpers import OfflineLLM


@pytest.fixture
def backend(tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    agent = AgentOrchestrator(OfflineLLM(AgentAction(action_type="tool_call", tool_calls=[
        ToolCall(tool_name="write_file", tool_call_id="tool", arguments={"path": "result.py", "content": "value = 1\n"})
    ])), tool_registry=registry, project_root=str(tmp_path))
    return BackendService(ProjectWorkspaceService(str(tmp_path), agent))


def send(backend, command_id, method, **params):
    return backend.dispatch(BackendRequest(request_id=command_id, method=method, params=params))


def test_backend_envelope_serializes_and_read_dispatch_is_allowlisted(backend):
    response = send(backend, "read", "get_project_information")
    assert response.success and response.request_id == "read"
    assert BackendResponse.model_validate_json(response.model_dump_json()) == response
    denied = send(backend, "private", "_refresh_state")
    assert denied.error.code == ErrorCode.UNSUPPORTED_OPERATION


def test_backend_permission_lifecycle_and_events(backend, tmp_path):
    pending = send(backend, "action", "request_agent_execution", prompt="Write result.py")
    assert pending.success and pending.action_state.value == "permission_required"
    assert pending.data["pending_action"]["request_id"] == "action"
    assert not (tmp_path / "result.py").exists()
    approved = send(backend, "approval", "approve_agent_action", request_id="action", tool_call_id="tool")
    assert approved.action_state.value == "approved"
    assert not (tmp_path / "result.py").exists()
    resumed = send(backend, "resume", "resume_agent_execution", request_id="action", tool_call_id="tool")
    assert resumed.success and resumed.data["status"] == "unverified"
    assert (tmp_path / "result.py").exists()
    assert all(event.request_id == "action" for event in resumed.events)
    assert [e.sequence for e in resumed.events] == list(range(1, len(resumed.events) + 1))
    events = send(backend, "events", "get_agent_events", request_id="action", after_sequence=approved.events[-1].sequence)
    assert events.data and all(e["sequence"] > approved.events[-1].sequence for e in events.data)
    replay = send(backend, "resume", "resume_agent_execution", request_id="action", tool_call_id="tool")
    assert replay == resumed
    assert len(replay.data["data"]["tool_results"]) == 1


@pytest.mark.parametrize("payload", [
    {"method": "get_project_information", "unexpected": True},
    {"request_id": "", "method": "get_project_information"},
    {"method": "get_project_information", "params": []},
])
def test_invalid_backend_envelopes_have_structured_errors(backend, payload):
    result = backend.dispatch(payload)
    assert not result.success
    assert result.error.code == ErrorCode.INVALID_REQUEST


def test_backend_rejects_wrong_parameters_and_id_conflicts(backend):
    result = send(backend, "bad-params", "get_project_information", unexpected=True)
    assert result.error.code == ErrorCode.INVALID_REQUEST
    send(backend, "same", "get_project_information")
    conflict = send(backend, "same", "get_project_state")
    assert conflict.error.code == ErrorCode.ACTION_CONFLICT
    conflict = send(backend, "a", "request_agent_execution", request_id="b", prompt="write")
    assert conflict.error.code == ErrorCode.INVALID_REQUEST


def test_backend_sanitizes_internal_errors(backend, monkeypatch):
    def broken():
        raise RuntimeError("password=do-not-expose")
    monkeypatch.setattr(backend.workspace, "get_health_report", broken)
    result = send(backend, "broken", "get_health_report")
    assert not result.success and result.error.code == ErrorCode.INTERNAL_ERROR
    assert "do-not-expose" not in result.model_dump_json()
    assert "Traceback" not in result.model_dump_json()


def test_shutdown_cancels_pending_work_and_rejects_new_commands(backend, tmp_path):
    send(backend, "action", "request_agent_execution", prompt="Write result.py")
    send(backend, "approve", "approve_agent_action", request_id="action", tool_call_id="tool")
    result = send(backend, "close", "shutdown")
    assert result.success and result.data["closed"]
    assert backend.workspace.orchestrator.get_request("action").status == "cancelled"
    assert not (tmp_path / "result.py").exists()
    assert send(backend, "after", "get_project_state").error.code == ErrorCode.SERVICE_CLOSED
    assert send(backend, "close", "shutdown") == result


def test_unconfigured_agent_error_and_invalid_drift_are_typed(tmp_path):
    backend = BackendService(ProjectWorkspaceService(str(tmp_path)))
    result = send(backend, "no-agent", "request_agent_execution", prompt="Write")
    assert result.error.code == ErrorCode.UNSUPPORTED_OPERATION
    result = send(backend, "bad-baseline", "get_drift_report", baseline_dict={})
    assert result.error.code == ErrorCode.INVALID_REQUEST


@pytest.mark.parametrize("value", [object(), float("nan")])
def test_non_json_backend_parameters_are_rejected(backend, value):
    response = backend.dispatch(BackendRequest(method="get_project_information", params={"bad": value}))
    assert not response.success
    assert response.error.code == ErrorCode.INVALID_REQUEST
