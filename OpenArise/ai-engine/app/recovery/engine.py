import logging
from typing import Optional
from app.models.schemas import (
    FailureEvent, RecoveryPlan, RecoveryResult, RecoveryState, 
    ToolResult, DiagnosisResult, FailureCategory
)
from app.recovery.checkpoint import CheckpointManager
from app.recovery.policy import RecoveryPolicyManager
from app.recovery.planner import RecoveryPlanner
from app.tools.base import ToolRegistry
from app.tools.permissions import PermissionManager
from app.failures.detector import FailureDetector

logger = logging.getLogger(__name__)

class RecoveryEngine:
    """Orchestrates the autonomous recovery process safely."""
    
    def __init__(self, planner: RecoveryPlanner, tool_registry: ToolRegistry, 
                 permission_manager: PermissionManager, checkpoint_manager: CheckpointManager):
        self.planner = planner
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.checkpoint_manager = checkpoint_manager
        self.policy = RecoveryPolicyManager()
        self.detector = FailureDetector()
        
    def attempt_recovery(self, failure: FailureEvent, diagnosis: DiagnosisResult, 
                         attempts: int, repeated_count: int) -> RecoveryResult:
        """Runs the recovery state machine."""
        
        result = RecoveryResult(
            recovery_id="rec_" + failure.failure_id,
            failure_id=failure.failure_id,
            status=RecoveryState.PLANNING,
            failure_signature_before=failure.error_signature or "",
            final_result="Initiated"
        )
        
        if not self.policy.can_retry_failure(failure.error_signature or "", attempts, repeated_count):
            result.status = RecoveryState.BLOCKED
            result.final_result = "Policy limit reached."
            return result
            
        # 1. PLANNING
        plan = self.planner.plan(failure, diagnosis)
        if not plan:
            result.status = RecoveryState.FAILED
            result.final_result = "Failed to create recovery plan."
            return result
            
        call_ids = [action.tool_call_id for action in plan.proposed_actions]
        if len(call_ids) != len(set(call_ids)) or any(not value for value in call_ids):
            result.status = RecoveryState.BLOCKED
            result.final_result = "Recovery tool call IDs must be unique and nonempty."
            return result
        if len(plan.proposed_actions) > self.policy.policy.max_actions_per_cycle:
            result.status = RecoveryState.BLOCKED
            result.final_result = "Recovery action limit exceeded."
            return result

        # Recovery never inherits approval merely from a model's declared risk.
        result.status = RecoveryState.PERMISSION_REQUIRED
        for action in plan.proposed_actions:
            if not self.permission_manager.check_permission(plan.recovery_id, plan.risk_level):
                result.status = RecoveryState.BLOCKED
                result.final_result = "Permission Denied or ASK."
                return result
            try:
                tool = self.tool_registry.get_tool(action.tool_name)
            except KeyError:
                result.status = RecoveryState.BLOCKED
                result.final_result = "Recovery tool is unavailable."
                return result
            if not self.permission_manager.check_permission(action.tool_call_id, tool.risk_level):
                result.status = RecoveryState.BLOCKED
                result.final_result = "Permission required for the exact recovery tool call."
                return result
        if failure.category in (FailureCategory.IMPORT_ERROR, FailureCategory.DEPENDENCY_ERROR):
            result.status = RecoveryState.BLOCKED
            result.final_result = "Automatic dependency installation is disabled."
            return result
        try:
            test_tool = self.tool_registry.get_tool("execute_tests")
        except KeyError:
            result.status = RecoveryState.BLOCKED
            result.final_result = "Recovery validation tool is unavailable."
            return result
        retest_id = plan.recovery_id + ":retest"
        if not self.permission_manager.check_permission(retest_id, test_tool.risk_level):
            result.status = RecoveryState.BLOCKED
            result.final_result = "Permission required for recovery validation."
            return result

        # 3. CHECKPOINT
        result.status = RecoveryState.CHECKPOINTING
        files_to_backup = []
        for action in plan.proposed_actions:
            if action.tool_name in ("write_file", "edit_file"):
                files_to_backup.append(action.arguments.get("path"))
                
        if files_to_backup:
            checkpoint_id = self.checkpoint_manager.create_checkpoint([f for f in files_to_backup if f])
            result.rollback_checkpoint = checkpoint_id
            
        # 4. APPLYING
        result.status = RecoveryState.APPLYING
        for action in plan.proposed_actions:
            try:
                tool = self.tool_registry.get_tool(action.tool_name)
                if not self.permission_manager.check_permission(action.tool_call_id, tool.risk_level):
                    result.status = RecoveryState.BLOCKED
                    result.final_result = "Recovery tool permission was revoked."
                    self._rollback(result)
                    return result
                try:
                    output = tool.execute(**action.arguments)
                finally:
                    self.permission_manager.revoke_approval(action.tool_call_id)
                result.actions_executed.append(action.tool_name)
                if isinstance(output, dict) and (output.get("exit_code") not in (None, 0) or output.get("error") or output.get("success") is False):
                    result.status = RecoveryState.FAILED
                    result.final_result = "Recovery action returned a failure."
                    self._rollback(result)
                    return result
            except Exception as e:
                logger.error(f"Recovery action failed: {e}")
                result.status = RecoveryState.FAILED
                result.final_result = "Recovery action raised an exception."
                self._rollback(result)
                return result
                
        # 5. RETESTING
        result.status = RecoveryState.RETESTING
        # For simplicity in MVP, if there's a test tool, run it. Otherwise assume failure tool.
        # Ideally, run the same tool that failed.
        try:
            if not self.permission_manager.check_permission(retest_id, test_tool.risk_level):
                result.status = RecoveryState.BLOCKED
                result.final_result = "Recovery validation permission was revoked."
                self._rollback(result)
                return result
            try:
                test_output = test_tool.execute()
            finally:
                self.permission_manager.revoke_approval(retest_id)
            result.tests_run.append("execute_tests")
            
            # Detect failure on the test
            res = ToolResult(
                tool_name="execute_tests",
                tool_call_id=retest_id,
                success=(test_output.get("exit_code") == 0),
                output=test_output,
                exit_code=test_output.get("exit_code")
            )
            detection = self.detector.detect(res)
            
            if detection:
                result.failure_signature_after = detection["error_signature"]
                result.status = RecoveryState.FAILED
                result.final_result = "Retest failed."
                self._rollback(result)
            else:
                result.status = RecoveryState.RECOVERED
                result.final_result = "Recovery successful and verified."
                
        except Exception as e:
            result.status = RecoveryState.FAILED
            result.final_result = f"Retest execution failed: {e}"
            self._rollback(result)
            
        return result
        
    def _rollback(self, result: RecoveryResult):
        if result.rollback_checkpoint:
            result.status = RecoveryState.ROLLING_BACK
            success = self.checkpoint_manager.rollback_checkpoint(result.rollback_checkpoint)
            if success:
                result.rollback_performed = True
                result.status = RecoveryState.ROLLED_BACK
                result.final_result += " (Rolled back successfully)"
            else:
                result.status = RecoveryState.FAILED
                result.final_result += " (Rollback failed)"
