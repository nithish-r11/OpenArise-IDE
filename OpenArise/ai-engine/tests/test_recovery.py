import pytest
import os
import tempfile
from app.models.schemas import (
    FailureEvent, DiagnosisResult, FailureCategory, ConfidenceLevel, 
    RecoveryPlan, ToolCall, ToolResult, RecoveryState
)
from app.tools.permissions import PermissionManager, RiskLevel
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool, ReadFileTool
from app.tools.execution import PythonExecutionTool, TestExecutionTool
from app.recovery.checkpoint import CheckpointManager
from app.recovery.policy import RecoveryPolicyManager
from app.recovery.planner import RecoveryPlanner
from app.recovery.engine import RecoveryEngine
from tests.mock_llm import MockLLMProvider

@pytest.fixture
def sandbox():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_checkpoint_and_rollback(sandbox):
    manager = CheckpointManager(sandbox)
    
    # Create file
    test_file = os.path.join(sandbox, "test.txt")
    with open(test_file, "w") as f:
        f.write("v1")
        
    # Checkpoint
    cid = manager.create_checkpoint(["test.txt"])
    
    # Modify
    with open(test_file, "w") as f:
        f.write("v2")
        
    # Rollback
    manager.rollback_checkpoint(cid)
    
    with open(test_file, "r") as f:
        assert f.read() == "v1"

def test_policy_manager():
    manager = RecoveryPolicyManager()
    assert manager.can_retry_failure("sig", 1, 1) is True
    assert manager.can_retry_failure("sig", 4, 1) is False # max attempts
    assert manager.can_retry_failure("sig", 1, 3) is False # loop detection

def test_recovery_planner_deterministic():
    llm = MockLLMProvider()
    planner = RecoveryPlanner(llm)
    
    failure = FailureEvent(
        failure_id="1",
        category=FailureCategory.IMPORT_ERROR,
        summary="No module named 'fastapi'"
    )
    diagnosis = DiagnosisResult(
        category=FailureCategory.IMPORT_ERROR,
        summary="Missing fastapi",
        probable_root_cause="fastapi",
        confidence=ConfidenceLevel.HIGH
    )
    
    plan = planner.plan(failure, diagnosis)
    assert plan is not None
    assert plan.requires_permission is True
    assert plan.risk_level == RiskLevel.EXECUTE
    assert len(plan.proposed_actions) == 2
    assert plan.proposed_actions[0].tool_name == "write_file"
    assert plan.proposed_actions[1].tool_name == "execute_python"

def test_recovery_engine_blocked_by_permission(sandbox):
    planner = RecoveryPlanner(MockLLMProvider())
    tool_registry = ToolRegistry()
    tool_registry.register(WriteFileTool(sandbox))
    tool_registry.register(PythonExecutionTool(sandbox))
    
    # Strict permissions (deny WRITE/EXECUTE)
    perm = PermissionManager(test_mode=False) 
    manager = CheckpointManager(sandbox)
    
    engine = RecoveryEngine(planner, tool_registry, perm, manager)
    
    failure = FailureEvent(
        failure_id="1",
        category=FailureCategory.IMPORT_ERROR,
        summary="No module named 'fastapi'",
        error_signature="sig"
    )
    diagnosis = DiagnosisResult(
        category=FailureCategory.IMPORT_ERROR,
        summary="Missing fastapi",
        probable_root_cause="fastapi",
        confidence=ConfidenceLevel.HIGH
    )
    
    result = engine.attempt_recovery(failure, diagnosis, 1, 1)
    
    assert result.status == RecoveryState.BLOCKED
    assert "Permission" in result.final_result
