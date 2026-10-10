"""Production permission regression: real mutations in disposable pytest projects."""
import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.state import AgentLifecycleError
from app.models.schemas import AgentAction, AgentRequest, ToolCall
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from app.tools.execution import PythonExecutionTool
from app.tools.permissions import PermissionManager, RiskLevel
from tests.hardening_helpers import OfflineLLM


def agent_for(root, permissions=None):
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(root)))
    provider = OfflineLLM(AgentAction(action_type="tool_call", tool_calls=[ToolCall(
        tool_name="write_file", tool_call_id="write-1",
        arguments={"path": "denied_probe.py", "content": "print(123)\n"},
    )]))
    return AgentOrchestrator(provider, tool_registry=registry,
                             permission_manager=permissions, project_root=str(root))


@pytest.mark.parametrize("grant", ["missing", "bare", "test_mode"])
def test_no_explicit_pending_approval_never_creates_file(tmp_path, grant):
    permissions = PermissionManager(test_mode=grant == "test_mode")
    if grant == "bare":
        permissions.grant_approval("write-1")
    agent = agent_for(tmp_path, permissions)
    result = agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    assert result.status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()
    assert result.data["tool_results"] == []
    assert agent.resume_request("current", "write-1").status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()


@pytest.mark.parametrize("operation", ["deny", "cancel"])
def test_denial_or_cancellation_revokes_grant_and_cannot_resume(tmp_path, operation):
    agent = agent_for(tmp_path)
    agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    agent.approve_action("current", "write-1")
    result = agent.deny_action("current", "write-1") if operation == "deny" else agent.cancel_request("current")
    assert result.status == ("denied" if operation == "deny" else "cancelled")
    assert result.data["tool_results"][0]["metadata"]["executed"] is False
    with pytest.raises(AgentLifecycleError):
        agent.resume_request("current", "write-1")
    assert not (tmp_path / "denied_probe.py").exists()


@pytest.mark.parametrize("request_id,call_id", [("other", "write-1"), ("current", "wrong")])
def test_invalid_approval_cannot_authorize_write(tmp_path, request_id, call_id):
    agent = agent_for(tmp_path)
    agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    with pytest.raises(AgentLifecycleError):
        agent.approve_action(request_id, call_id)
    assert agent.resume_request("current", "write-1").status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()


def test_revocation_at_tool_start_prevents_actual_write(tmp_path):
    agent = agent_for(tmp_path)
    agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    agent.approve_action("current", "write-1")
    original_event = agent._event
    def revoke_before_execute(event_type, tool_call_id=None):
        if event_type == "tool_started":
            agent.permission_manager.revoke_approval(tool_call_id)
        original_event(event_type, tool_call_id)
    agent._event = revoke_before_execute
    result = agent.resume_request("current", "write-1")
    assert result.status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()
    assert result.data["tool_results"] == []


def test_changed_arguments_cannot_spend_previous_approval(tmp_path):
    agent = agent_for(tmp_path)
    agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    agent.approve_action("current", "write-1")
    agent._action.tool_calls[0].arguments["path"] = "unexpected.py"
    with pytest.raises(AgentLifecycleError):
        agent.resume_request("current", "write-1")
    assert not (tmp_path / "denied_probe.py").exists()
    assert not (tmp_path / "unexpected.py").exists()


def test_allow_executes_only_exact_pending_call_once(tmp_path):
    agent = agent_for(tmp_path)
    agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    approved = agent.approve_action("current", "write-1")
    assert approved.pending_action.approved
    assert not (tmp_path / "denied_probe.py").exists()
    result = agent.resume_request("current", "write-1")
    assert result.data["tool_results"][0]["metadata"]["executed"] is True
    assert (tmp_path / "denied_probe.py").read_text() == "print(123)\n"
    with pytest.raises(AgentLifecycleError):
        agent.resume_request("current", "write-1")
    assert len(agent.get_request("current").data["tool_results"]) == 1


@pytest.mark.parametrize("change", ["request", "tool", "arguments", "risk"])
def test_scoped_grant_cannot_authorize_a_different_action(tmp_path, change):
    agent = agent_for(tmp_path)
    pending = agent.process_request(AgentRequest(request_id="current", prompt="Create a file"))
    call = pending.pending_action.tool_call
    agent.permission_manager.grant_call_approval("old-request" if change == "request" else "current", call, RiskLevel.WRITE)
    changed = call.model_copy(deep=True)
    if change == "tool": changed.tool_name = "execute_python"
    if change == "arguments": changed.arguments["content"] = "unexpected"
    risk = RiskLevel.EXECUTE if change == "risk" else RiskLevel.WRITE
    assert not agent.permission_manager.check_call_permission("current", changed, risk)
    # A forged presentation flag alone is not a decision.
    if change == "request":
        agent._pending.approved = True
        assert agent.resume_request("current", "write-1").status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()


def test_approval_is_consumed_before_operation_and_cannot_be_replayed(tmp_path):
    manager = PermissionManager()
    call = ToolCall(tool_name="write_file", tool_call_id="single", arguments={"path": "a.py", "content": "x"})
    manager.grant_call_approval("request", call, RiskLevel.WRITE)
    assert manager.consume_call_permission("request", call, RiskLevel.WRITE)
    assert not manager.consume_call_permission("request", call, RiskLevel.WRITE)


def test_even_scoped_grant_cannot_skip_explicit_pending_decision(tmp_path):
    agent = agent_for(tmp_path)
    call = agent.llm.action.tool_calls[0]
    agent.permission_manager.grant_call_approval("current", call, RiskLevel.WRITE)
    result = agent.process_request(AgentRequest(request_id="current", prompt="Create denied_probe.py"))
    assert result.status == "permission_required"
    assert not (tmp_path / "denied_probe.py").exists()


@pytest.mark.parametrize("decision", ["missing", "deny", "invalid"])
def test_unapproved_execution_cannot_modify_project(tmp_path, decision):
    (tmp_path / "probe.py").write_text('from pathlib import Path\nPath(__file__).with_name("executed.txt").write_text("unexpected")\n')
    agent = agent_for(tmp_path)
    agent.tool_registry.register(PythonExecutionTool(str(tmp_path)))
    agent.llm.action = AgentAction(action_type="tool_call", tool_calls=[ToolCall(
        tool_name="execute_python", tool_call_id="execute-1", arguments={"script_path": "probe.py"})])
    agent.process_request(AgentRequest(request_id="execute", prompt="Run probe.py"))
    if decision == "deny":
        assert agent.deny_action("execute", "execute-1").status == "denied"
        with pytest.raises(AgentLifecycleError): agent.resume_request("execute", "execute-1")
    else:
        if decision == "invalid":
            with pytest.raises(AgentLifecycleError): agent.approve_action("execute", "write-1")
        assert agent.resume_request("execute", "execute-1").status == "permission_required"
    assert not (tmp_path / "executed.txt").exists()


def test_recovery_checks_revocation_after_checkpoint_before_write(tmp_path):
    from tests.test_hardening_security import make_recovery
    permissions = PermissionManager()
    engine, failure, diagnosis = make_recovery(tmp_path, permissions)
    session = engine.prepare_recovery(failure, diagnosis, 1, 1)
    call = session["calls"][0]
    permissions.grant_call_approval(session["request_id"], call, RiskLevel.WRITE)
    checkpoint = engine.checkpoint_manager.create_checkpoint
    def revoke_at_checkpoint(paths):
        permissions.revoke_approval(call.tool_call_id)
        return checkpoint(paths)
    engine.checkpoint_manager.create_checkpoint = revoke_at_checkpoint
    recorded = []
    assert engine.advance_recovery(session, lambda *args: recorded.append(args), lambda *args: None) == call
    assert not (tmp_path / "changed.py").exists()
    assert recorded == []
