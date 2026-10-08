"""Deterministic provider edge cases with actual file writes and real pytest."""
import pytest
from app.llm.base import LLMProvider
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentAction, AgentRequest, ToolCall, RecoveryPlan, DiagnosisResult, ConfidenceLevel, FailureCategory
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from app.tools.execution import TestExecutionTool
from app.tools.permissions import PermissionManager, RiskLevel

GOOD="def multiply(a, b):\n    return a * b\n"
BAD="def multiply(a, b):\n    return a + b\n"
TEST="from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n"

class Provider(LLMProvider):
    def __init__(self, baseline=True): self.baseline=baseline
    def generate(self,*args,**kwargs): raise AssertionError("Not used")
    def health_check(self): return True
    def generate_structured(self,prompt,schema,**kwargs):
        if schema is AgentAction:
            calls=[ToolCall(tool_name="write_file",arguments={"path":"math_ops.py","content":BAD,"overwrite":True}),ToolCall(tool_name="execute_tests")]
            if self.baseline: calls.insert(0,ToolCall(tool_name="execute_tests"))
            return AgentAction(action_type="tool_call",tool_calls=calls)
        if schema is DiagnosisResult:
            return DiagnosisResult(category=FailureCategory.TEST_FAILURE,summary="Multiplication test failed.",probable_root_cause="Addition instead of multiplication.",confidence=ConfidenceLevel.HIGH)
        if schema is RecoveryPlan:
            return RecoveryPlan(failure_id="ignored",goal="Restore multiplication",diagnosis_summary="Fix implementation.",
                                proposed_actions=[ToolCall(tool_name="write_file",arguments={"path":"math_ops.py","content":GOOD,"overwrite":True})],
                                expected_result="Passing original tests",risk_level=RiskLevel.READ)
        raise AssertionError(schema)

def agent(root, baseline=True):
    (root/"math_ops.py").write_text(GOOD)
    (root/"test_math_ops.py").write_text(TEST)
    registry=ToolRegistry()
    registry.register(WriteFileTool(str(root)))
    registry.register(TestExecutionTool(str(root)))
    return AgentOrchestrator(Provider(baseline),tool_registry=registry,permission_manager=PermissionManager(False),project_root=str(root))

def complete(a, response):
    pending=[]
    while response.pending_action:
        p=response.pending_action
        pending.append(p.model_copy(deep=True))
        approved=a.approve_action(p.request_id,p.tool_call_id)
        assert approved.status=="approved"
        response=a.resume_request(p.request_id,p.tool_call_id)
    return response,pending

def test_real_recovery_and_fresh_retest_verify_original_requirement(tmp_path):
    a=agent(tmp_path)
    response,pending=complete(a,a.process_request(AgentRequest(prompt="Demonstrate fault recovery then restore multiplication.")))
    assert len(pending)==5
    assert [p.risk_level for p in pending]==[RiskLevel.EXECUTE,RiskLevel.WRITE,RiskLevel.EXECUTE,RiskLevel.WRITE,RiskLevel.EXECUTE]
    assert response.status=="success"
    assert response.data["recovery"]["status"]=="RECOVERED"
    assert response.data["verification"]["overall_status"]=="VERIFIED"
    evidence=response.data["evidence"]
    ids={e["requirement_id"] for e in evidence}
    assert ids=={response.data["requirements"][0]["requirement_id"]}
    old,failed,fresh=[e for e in evidence if e["evidence_type"] in ("TEST_PASS","TEST_FAIL")]
    assert old["result"]["stale"] and old["result"]["superseded"]
    assert failed["result"]["success"] is False and failed["result"]["resolved_by"]==fresh["evidence_id"]
    assert fresh["result"]["exit_code"]==0 and fresh["result"]["project_snapshot"]
    assert any(e["evidence_type"]=="RECOVERY_RESULT" for e in evidence)
    assert (tmp_path/"math_ops.py").read_text()==GOOD
    assert (tmp_path/"test_math_ops.py").read_text()==TEST

def test_recovery_retest_failure_rolls_back_and_never_verifies(tmp_path):
    a=agent(tmp_path,baseline=False)
    (tmp_path/"test_unrecoverable.py").write_text("def test_controlled_failure():\n    assert False, 'intentional acceptance failure'\n")
    response,pending=complete(a,a.process_request(AgentRequest(prompt="Repair only math_ops.py; preserve all tests.")))
    assert response.status=="failure"
    assert response.data["recovery"]["status"]=="ROLLED_BACK"
    assert response.data["verification"]["overall_status"]=="NOT_VERIFIED"
    assert not any(e["result"].get("resolved_by") for e in response.data["evidence"])
    assert (tmp_path/"math_ops.py").read_text()==BAD

def test_denial_prevents_initial_mutation(tmp_path):
    a=agent(tmp_path,baseline=False)
    response=a.process_request(AgentRequest(prompt="Controlled change."))
    p=response.pending_action
    assert p.risk_level==RiskLevel.WRITE
    result=a.deny_action(p.request_id,p.tool_call_id)
    assert result.status=="denied"
    assert (tmp_path/"math_ops.py").read_text()==GOOD

def test_cancel_recovery_keeps_failed_gate_and_no_automatic_approval(tmp_path):
    a=agent(tmp_path,baseline=False)
    r=a.process_request(AgentRequest(prompt="Restore multiplication."))
    for _ in range(2):
        p=r.pending_action
        a.approve_action(p.request_id,p.tool_call_id)
        r=a.resume_request(p.request_id,p.tool_call_id)
    assert r.pending_action and r.data["recovery"]["status"]=="PERMISSION_REQUIRED"
    result=a.cancel_request(r.request_id)
    assert result.status=="cancelled"
    assert result.data["verification"]["overall_status"]=="NOT_VERIFIED"
    assert (tmp_path/"math_ops.py").read_text()==BAD

def test_external_mutation_invalidates_retained_verified_gate(tmp_path):
    a=agent(tmp_path)
    result,_=complete(a,a.process_request(AgentRequest(prompt="Restore multiplication.")))
    assert result.status=="success"
    (tmp_path/"math_ops.py").write_text(BAD)
    refreshed=a.get_request(result.request_id)
    assert refreshed.status=="unverified"
    assert refreshed.data["verification"]["overall_status"]!="VERIFIED"
    (tmp_path/"math_ops.py").write_text(GOOD)
    assert a.get_request(result.request_id).status=="unverified"

def test_forged_resolution_without_actual_recovery_link_is_rejected(tmp_path):
    a=agent(tmp_path,baseline=False)
    r=a.process_request(AgentRequest(prompt="Controlled change."))
    for _ in range(2):
        p=r.pending_action
        a.approve_action(p.request_id,p.tool_call_id)
        r=a.resume_request(p.request_id,p.tool_call_id)
    record=next(e for e in a.evidence_ledger.list_evidence() if e.evidence_type.value=="TEST_FAIL")
    record.result["resolved_by"]="invented"
    assert a.independent_verifier.resolution_is_valid(record) is False

def test_duplicate_resume_cannot_execute_recovery_action_twice(tmp_path):
    a=agent(tmp_path,baseline=False)
    r=a.process_request(AgentRequest(prompt="Controlled change."))
    p=r.pending_action
    a.approve_action(p.request_id,p.tool_call_id)
    resumed=a.resume_request(p.request_id,p.tool_call_id)
    assert resumed.pending_action.tool_call_id!=p.tool_call_id
    from app.agent.state import AgentLifecycleError
    with pytest.raises(AgentLifecycleError):
        a.resume_request(p.request_id,p.tool_call_id)

def test_planner_uses_failure_facts_not_completed_fault_instructions(tmp_path):
    from app.recovery.planner import RecoveryPlanner
    from app.models.schemas import FailureEvent
    class RecordingProvider(Provider):
        def generate_structured(self, prompt, schema, **kwargs):
            if schema is RecoveryPlan:
                assert "COMPLETED_FAULT_STEP_REPEAT" not in prompt
                assert "Arithmetic assertion failed" in prompt
            return super().generate_structured(prompt, schema, **kwargs)
    planner = RecoveryPlanner(RecordingProvider())
    failure = FailureEvent(category=FailureCategory.TEST_FAILURE, summary="Actual failing pytest",
                           evidence={"user_request": "COMPLETED_FAULT_STEP_REPEAT", "stderr": "Arithmetic assertion failed"})
    diagnosis = DiagnosisResult(category=FailureCategory.TEST_FAILURE, summary="Test failed",
                                probable_root_cause="Addition instead of multiplication", confidence=ConfidenceLevel.HIGH)
    plan = planner.plan(failure, diagnosis)
    assert plan and plan.failure_id == failure.failure_id
    assert plan.proposed_actions[0].tool_name == "write_file"
