import pytest
from app.tools.fs import ReadFileTool, WriteFileTool, _is_safe_path
from app.tools.execution import PythonExecutionTool, TestExecutionTool
from app.tools.permissions import PermissionManager, RiskLevel
from app.tools.base import ToolRegistry
from app.recovery.checkpoint import CheckpointManager
from app.recovery.engine import RecoveryEngine
from app.recovery.planner import RecoveryPlanner
from app.models.schemas import FailureEvent, FailureCategory, DiagnosisResult, RecoveryPlan, ToolCall, RecoveryState
from tests.mock_llm import MockLLMProvider


def test_sibling_prefix_escape_is_rejected_by_file_tools_and_checkpoints(tmp_path):
    root = tmp_path / "project"
    sibling = tmp_path / "project-other"
    root.mkdir()
    sibling.mkdir()
    (sibling / "outside.py").write_text("private")
    path = "../project-other/outside.py"
    assert not _is_safe_path(str(root), path)
    with pytest.raises(ValueError):
        ReadFileTool(str(root)).execute(path=path)
    with pytest.raises(ValueError):
        WriteFileTool(str(root)).execute(path=path, content="changed", overwrite=True)
    with pytest.raises(ValueError):
        CheckpointManager(str(root)).create_checkpoint([path])
    assert (sibling / "outside.py").read_text() == "private"


@pytest.mark.parametrize("path", [".env.local", "Credentials.json", "keys/private.pem", "secrets/config.py", ".openarise/memory/memory.sqlite"])
def test_secret_and_runtime_paths_are_excluded(tmp_path, path):
    assert not _is_safe_path(str(tmp_path), path)
    with pytest.raises(ValueError):
        WriteFileTool(str(tmp_path)).execute(path=path, content="secret")


def test_absolute_paths_and_checkpoint_id_traversal_are_rejected(tmp_path):
    assert not _is_safe_path(str(tmp_path), str(tmp_path / "file.py"))
    manager = CheckpointManager(str(tmp_path))
    assert manager.rollback_checkpoint("../outside") is False


def test_checkpoint_rolls_back_newly_created_files(tmp_path):
    manager = CheckpointManager(str(tmp_path))
    checkpoint = manager.create_checkpoint(["new.py"])
    (tmp_path / "new.py").write_text("created")
    assert manager.rollback_checkpoint(checkpoint)
    assert not (tmp_path / "new.py").exists()


def make_recovery(tmp_path, permission, category=FailureCategory.RUNTIME_ERROR):
    plan = RecoveryPlan(
        recovery_id="plan", failure_id="failure", goal="Repair", diagnosis_summary="Repair",
        proposed_actions=[ToolCall(tool_name="write_file", tool_call_id="write",
                                   arguments={"path": "changed.py", "content": "value = 1"})],
        expected_result="Fixed", risk_level=RiskLevel.READ,
    )
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    registry.register(TestExecutionTool(str(tmp_path)))
    registry.register(PythonExecutionTool(str(tmp_path)))
    planner = RecoveryPlanner(MockLLMProvider(structured_response=plan))
    engine = RecoveryEngine(planner, registry, permission, CheckpointManager(str(tmp_path)))
    failure = FailureEvent(failure_id="failure", summary="Failed", category=category,
                           tool_name="execute_python", error_signature="signature")
    diagnosis = DiagnosisResult(category=category, summary="Failed", probable_root_cause="problem", confidence="LOW")
    return engine, failure, diagnosis


def test_recovery_checks_actual_tool_risk_not_model_declared_read_risk(tmp_path):
    permission = PermissionManager()
    permission.grant_approval("plan")
    engine, failure, diagnosis = make_recovery(tmp_path, permission)
    result = engine.attempt_recovery(failure, diagnosis, 1, 1)
    assert result.status == RecoveryState.BLOCKED
    assert "Permission" in result.final_result
    assert not (tmp_path / "changed.py").exists()


def test_recovery_retest_requires_separate_execute_permission_before_mutation(tmp_path):
    permission = PermissionManager()
    permission.grant_approval("plan")
    permission.grant_approval("write")
    engine, failure, diagnosis = make_recovery(tmp_path, permission)
    result = engine.attempt_recovery(failure, diagnosis, 1, 1)
    assert result.status == RecoveryState.BLOCKED
    assert "validation" in result.final_result
    assert not (tmp_path / "changed.py").exists()


def test_missing_dependency_recovery_does_not_install_even_in_test_mode(tmp_path):
    engine, failure, diagnosis = make_recovery(tmp_path, PermissionManager(test_mode=True), FailureCategory.IMPORT_ERROR)
    result = engine.attempt_recovery(failure, diagnosis, 1, 1)
    assert result.status == RecoveryState.BLOCKED
    assert "installation is disabled" in result.final_result
    assert not (tmp_path / "install_dep.py").exists()


def test_nested_secret_fields_are_redacted_before_persistence():
    from app.memory.redact import SecretRedactor
    result = SecretRedactor().redact_dict({"actions": [{"token": "private", "nested": {"api-key": "hidden"}}]})
    assert "private" not in str(result)
    assert "hidden" not in str(result)


def test_recovery_duplicate_call_ids_cannot_reuse_one_approval(tmp_path):
    engine, failure, diagnosis = make_recovery(tmp_path, PermissionManager(test_mode=True))
    plan = engine.planner.llm.structured_response
    plan.proposed_actions.append(plan.proposed_actions[0].model_copy(deep=True))
    result = engine.attempt_recovery(failure, diagnosis, 1, 1)
    assert result.status == RecoveryState.BLOCKED
    assert "unique" in result.final_result
    assert not (tmp_path / "changed.py").exists()
