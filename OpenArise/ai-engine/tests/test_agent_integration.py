import json
import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.state import AgentLifecycleError
from app.models.schemas import AgentAction, AgentRequest, ToolCall, ActionState
from app.tools.base import ToolRegistry, BaseTool
from app.tools.fs import ReadFileTool, WriteFileTool
from app.tools.execution import PythonExecutionTool, TestExecutionTool
from app.tools.permissions import PermissionManager, RiskLevel, PermissionAction
from tests.hardening_helpers import OfflineLLM, requirements_from_prompt


def make_agent(root, calls, permissions=None):
    registry = ToolRegistry()
    for tool in (ReadFileTool(str(root)), WriteFileTool(str(root)),
                 PythonExecutionTool(str(root)), TestExecutionTool(str(root))):
        registry.register(tool)
    llm = OfflineLLM(calls if callable(calls) else AgentAction(action_type="tool_call", tool_calls=calls))
    agent = AgentOrchestrator(llm, tool_registry=registry,
                              permission_manager=permissions, project_root=str(root))
    return agent, llm


def write_call(call_id="write-1", path="result.py"):
    return ToolCall(tool_call_id=call_id, tool_name="write_file",
                    arguments={"path": path, "content": "answer = 42\n"})


def test_real_write_preserves_result_identity_and_reaches_gate(tmp_path):
    agent, llm = make_agent(tmp_path, [write_call()], PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(request_id="request-1", prompt="Create result.py"))
    assert (tmp_path / "result.py").read_text() == "answer = 42\n"
    assert response.status == "unverified"
    assert response.current_state == "COMPLETED"
    assert response.data["tool_results"][0]["tool_call_id"] == "write-1"
    assert response.data["tool_results"][0]["success"] is True
    req = response.data["requirements"][0]
    evidence = response.data["evidence"][0]
    assert req["description"] == "Create result.py"
    assert evidence["requirement_id"] == req["requirement_id"]
    assert evidence["tool_call_id"] == "write-1"
    assert evidence["evidence_id"] in req["evidence_references"]
    assert response.data["verification"]["overall_status"] == "PARTIALLY_VERIFIED"
    assert llm.action_requests == 1


def test_complete_offline_request_tool_test_evidence_gate_flow(tmp_path):
    (tmp_path / "test_answer.py").write_text("def test_answer():\n    from result import answer\n    assert answer == 42\n")
    calls = [write_call(), ToolCall(tool_name="execute_tests", tool_call_id="test-1",
                                    arguments={"test_path": "test_answer.py"})]
    agent, _ = make_agent(tmp_path, calls, PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="Implement answer = 42 and pass its test"))
    assert response.status == "success"
    assert response.data["verification"]["overall_status"] == "VERIFIED"
    assert response.data["verification"]["report"]["tests_executed"] == 1
    assert response.data["verification"]["report"]["total_requirements"] == 1
    assert [r["tool_call_id"] for r in response.data["tool_results"]] == ["write-1", "test-1"]
    assert response.data["evidence"][1]["evidence_type"] == "TEST_PASS"
    assert response.data["evidence"][1]["result"]["exit_code"] == 0
    assert any(e["current_state"] == "VERIFYING" for e in response.data["events"])


def test_failed_real_tests_are_contradictory_and_never_success(tmp_path):
    (tmp_path / "test_fail.py").write_text("def test_failure():\n    assert False\n")
    agent, _ = make_agent(tmp_path, [ToolCall(tool_name="execute_tests", tool_call_id="fail",
                                             arguments={"test_path": "test_fail.py"})],
                          PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="Pass the existing test"))
    assert response.status == "failure"
    result = response.data["tool_results"][0]
    assert not result["success"] and result["exit_code"] == 1
    evidence = response.data["evidence"][0]
    assert evidence["evidence_type"] == "TEST_FAIL"
    assert evidence["strength"] == "CONTRADICTORY"
    assert response.data["verification"]["overall_status"] == "NOT_VERIFIED"


def test_unknown_tool_and_exception_keep_consistent_results(tmp_path):
    calls = [ToolCall(tool_call_id="unknown", tool_name="nonexistent"),
             ToolCall(tool_call_id="missing", tool_name="read_file", arguments={"path": "missing.py"})]
    agent, _ = make_agent(tmp_path, calls)
    response = agent.process_request(AgentRequest(prompt="Inspect files"))
    assert response.status == "failure"
    assert [r["tool_call_id"] for r in response.data["tool_results"]] == ["unknown", "missing"]
    assert all(not r["success"] and r["error"] for r in response.data["tool_results"])
    assert response.data["verification"]["overall_status"] == "NOT_VERIFIED"


def test_nonzero_python_exit_is_failure_not_success(tmp_path):
    (tmp_path / "fail.py").write_text("raise SystemExit(7)\n")
    agent, _ = make_agent(tmp_path, [ToolCall(tool_name="execute_python", tool_call_id="python",
                                             arguments={"script_path": "fail.py"})],
                          PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="Execute fail.py"))
    assert response.status == "failure"
    assert response.data["tool_results"][0]["exit_code"] == 7
    assert response.data["verification"]["overall_status"] == "NOT_VERIFIED"


def test_ask_approve_resume_preserves_exact_call_without_inference(tmp_path):
    agent, llm = make_agent(tmp_path, [write_call()])
    request = AgentRequest(request_id="permission-request", prompt="Create result.py")
    pending = agent.process_request(request)
    assert pending.action_state == ActionState.PERMISSION_REQUIRED
    assert pending.pending_action.request_id == request.request_id
    assert pending.pending_action.tool_call_id == "write-1"
    assert pending.data["tool_results"] == []
    assert not (tmp_path / "result.py").exists()
    assert agent.resume_request(request.request_id, "write-1").status == "permission_required"
    pending.pending_action.tool_call.arguments["content"] = "tampered"
    approved = agent.approve_action(request.request_id, "write-1")
    assert approved.pending_action.approved
    assert not (tmp_path / "result.py").exists()
    completed = agent.resume_request(request.request_id, "write-1")
    assert (tmp_path / "result.py").read_text() == "answer = 42\n"
    assert completed.request_id == request.request_id
    assert completed.pending_action is None
    assert llm.action_requests == 1
    assert not agent.permission_manager.check_permission("write-1", RiskLevel.WRITE)
    with pytest.raises(AgentLifecycleError):
        agent.resume_request(request.request_id, "write-1")


@pytest.mark.parametrize("operation", ["deny", "cancel"])
def test_deny_or_cancel_never_executes_pending_action(tmp_path, operation):
    agent, _ = make_agent(tmp_path, [write_call()])
    agent.process_request(AgentRequest(request_id="pending", prompt="Create a file"))
    agent.approve_action("pending", "write-1")
    response = agent.deny_action("pending", "write-1") if operation == "deny" else agent.cancel_request("pending")
    assert response.status == ("denied" if operation == "deny" else "cancelled")
    assert not (tmp_path / "result.py").exists()
    assert response.data["tool_results"][0]["metadata"]["executed"] is False
    assert not agent.permission_manager.check_permission("write-1", RiskLevel.WRITE)
    with pytest.raises(AgentLifecycleError):
        agent.approve_action("pending", "write-1")


def test_two_pending_tools_do_not_rerun_completed_prefix(tmp_path):
    agent, llm = make_agent(tmp_path, [write_call("one", "one.py"), write_call("two", "two.py")])
    agent.process_request(AgentRequest(request_id="multi", prompt="Create two files"))
    agent.approve_action("multi", "one")
    response = agent.resume_request("multi", "one")
    assert response.pending_action.tool_call_id == "two"
    assert (tmp_path / "one.py").exists() and not (tmp_path / "two.py").exists()
    agent.approve_action("multi", "two")
    response = agent.resume_request("multi", "two")
    assert all(r["success"] for r in response.data["tool_results"])
    assert len(response.data["tool_results"]) == 2
    assert llm.action_requests == 1


def test_request_replay_is_idempotent_and_conflicts_are_rejected(tmp_path):
    agent, llm = make_agent(tmp_path, [write_call()], PermissionManager(test_mode=True))
    request = AgentRequest(request_id="replay", prompt="Write the file")
    first = agent.process_request(request)
    assert agent.process_request(request) == first
    assert llm.action_requests == 1
    with pytest.raises(AgentLifecycleError):
        agent.process_request(AgentRequest(request_id="replay", prompt="Different instruction"))


def test_pending_request_cannot_be_replaced_or_wrong_id_approved(tmp_path):
    agent, _ = make_agent(tmp_path, [write_call()])
    agent.process_request(AgentRequest(request_id="retained", prompt="Write"))
    with pytest.raises(AgentLifecycleError):
        agent.process_request(AgentRequest(request_id="other", prompt="Replace"))
    with pytest.raises(AgentLifecycleError):
        agent.approve_action("retained", "wrong")
    with pytest.raises(AgentLifecycleError):
        agent.approve_action("other", "write-1")
    assert agent.get_request("retained").pending_action.tool_call_id == "write-1"


def test_revoked_approval_stays_pending_on_resume(tmp_path):
    agent, _ = make_agent(tmp_path, [write_call()])
    agent.process_request(AgentRequest(request_id="revoked", prompt="Write"))
    agent.approve_action("revoked", "write-1")
    agent.permission_manager.revoke_approval("write-1")
    assert agent.resume_request("revoked", "write-1").status == "permission_required"
    assert not (tmp_path / "result.py").exists()


def test_changed_tool_registration_cannot_use_old_approval(tmp_path):
    agent, _ = make_agent(tmp_path, [write_call()])
    agent.process_request(AgentRequest(request_id="changed-tool", prompt="Write"))
    agent.approve_action("changed-tool", "write-1")
    agent.tool_registry.register(WriteFileTool(str(tmp_path)))
    with pytest.raises(AgentLifecycleError):
        agent.resume_request("changed-tool", "write-1")
    assert agent.cancel_request("changed-tool").status == "cancelled"
    assert not (tmp_path / "result.py").exists()


def test_deny_policy_is_authoritative_even_with_stored_approval(tmp_path):
    class DenyWrites(PermissionManager):
        def get_action_for_risk(self, risk):
            return PermissionAction.DENY if risk == RiskLevel.WRITE else PermissionAction.ALLOW
    permission = DenyWrites()
    permission.grant_approval("write-1")
    agent, _ = make_agent(tmp_path, [write_call()], permission)
    response = agent.process_request(AgentRequest(prompt="Write"))
    assert response.status == "denied"
    assert not (tmp_path / "result.py").exists()


def test_multiple_requirements_receive_only_explicitly_associated_evidence(tmp_path):
    (tmp_path / "test_one.py").write_text("def test_one():\n    assert True\n")
    def action(prompt):
        requirements = requirements_from_prompt(prompt)
        return AgentAction(action_type="tool_call", tool_calls=[ToolCall(
            tool_name="execute_tests", arguments={"test_path": "test_one.py"},
            requirement_ids=[requirements[0]["requirement_id"]],
        )])
    agent, _ = make_agent(tmp_path, action, PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="- Pass the first test\n- Implement another feature"))
    results = response.data["verification"]["requirement_results"]
    assert [r["status"] for r in results] == ["VERIFIED", "INCONCLUSIVE"]
    assert response.status == "unverified"


def test_new_request_does_not_inherit_previous_evidence(tmp_path):
    agent, llm = make_agent(tmp_path, [write_call()], PermissionManager(test_mode=True))
    first = agent.process_request(AgentRequest(prompt="Write"))
    llm.action = AgentAction(action_type="respond", message="No execution")
    second = agent.process_request(AgentRequest(prompt="Another request"))
    assert first.data["evidence"] and second.data["evidence"] == []
    assert second.data["verification"]["overall_status"] == "INCONCLUSIVE"
    assert second.data["agent_message"] == "No execution"


def test_duplicate_tool_ids_are_rejected_before_execution(tmp_path):
    agent, _ = make_agent(tmp_path, [write_call("same", "one.py"), write_call("same", "two.py")],
                          PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="Create files"))
    assert response.status == "failure"
    assert not (tmp_path / "one.py").exists()


def test_tool_named_like_a_test_does_not_manufacture_verification(tmp_path):
    class FakeTest(BaseTool):
        name = "test_everything"
        def get_schema(self):
            return {"name": self.name}
        def execute(self, **kwargs):
            return {"exit_code": 0}
    agent, _ = make_agent(tmp_path, [ToolCall(tool_name="test_everything")])
    agent.tool_registry.register(FakeTest())
    response = agent.process_request(AgentRequest(prompt="Verify all features"))
    assert response.status == "unverified"
    assert response.data["evidence"][0]["evidence_type"] == "TOOL_RESULT"


def test_explicit_failed_tool_output_is_not_reported_as_success(tmp_path):
    class ReportedFailure(BaseTool):
        name = "reported_failure"
        def get_schema(self):
            return {"name": self.name}
        def execute(self, **kwargs):
            return {"success": False, "message": "Could not finish"}
    agent, _ = make_agent(tmp_path, [ToolCall(tool_name="reported_failure")])
    agent.tool_registry.register(ReportedFailure())
    response = agent.process_request(AgentRequest(prompt="Complete operation"))
    assert response.status == "failure"
    assert response.data["tool_results"][0]["success"] is False
    assert response.data["verification"]["overall_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize("retest", [False, True])
def test_mutation_invalidates_prior_test_proof_until_retested(tmp_path, retest):
    (tmp_path / "feature.py").write_text("value = 1\n")
    (tmp_path / "test_feature.py").write_text(
        "def test_value():\n    from feature import value\n    assert value in (1, 2)\n"
    )
    calls = [
        ToolCall(tool_name="execute_tests", tool_call_id="before", arguments={"test_path": "test_feature.py"}),
        ToolCall(tool_name="write_file", tool_call_id="change",
                 arguments={"path": "feature.py", "content": "value = 2\n", "overwrite": True}),
    ]
    if retest:
        calls.append(ToolCall(tool_name="execute_tests", tool_call_id="after", arguments={"test_path": "test_feature.py"}))
    agent, _ = make_agent(tmp_path, calls, PermissionManager(test_mode=True))
    response = agent.process_request(AgentRequest(prompt="Maintain the tested numeric value"))
    assert response.status == ("success" if retest else "unverified")
    assert response.data["evidence"][0]["result"]["stale"]
    assert response.data["verification"]["overall_status"] == ("VERIFIED" if retest else "INCONCLUSIVE")
