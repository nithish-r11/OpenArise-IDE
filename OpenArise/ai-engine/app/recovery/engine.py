import logging
from typing import Optional
from app.models.schemas import (
    FailureEvent, RecoveryPlan, RecoveryResult, RecoveryState, 
    ToolResult, DiagnosisResult
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
            
        # 2. PERMISSION
        result.status = RecoveryState.PERMISSION_REQUIRED
        for action in plan.proposed_actions:
            if not self.permission_manager.check_permission(plan.recovery_id, plan.risk_level):
                result.status = RecoveryState.BLOCKED
                result.final_result = "Permission Denied or ASK."
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
                output = tool.execute(**action.arguments)
                result.actions_executed.append(action.tool_name)
            except Exception as e:
                logger.error(f"Recovery action failed: {e}")
                self._rollback(result)
                return result
                
        # 5. RETESTING
        result.status = RecoveryState.RETESTING
        # For simplicity in MVP, if there's a test tool, run it. Otherwise assume failure tool.
        # Ideally, run the same tool that failed.
        try:
            tool = self.tool_registry.get_tool(failure.tool_name)
            # Reconstruct arguments from evidence if possible, or just run tests
            # A true retest would have the exact arguments, but we don't have them in FailureEvent easily.
            # In a real system, the orchestrator should pass the original tool call.
            # We will use execute_tests as a generic validation if tool_name is test, or we'll just return RECOVERED
            # and let the Orchestrator loop retest if needed. The prompt says "Execute the smallest relevant test".
            
            # Since we can't easily guess original args without saving them, we run 'execute_tests'
            # to validate if we fixed syntax/imports.
            test_tool = self.tool_registry.get_tool("execute_tests")
            test_output = test_tool.execute()
            result.tests_run.append("execute_tests")
            
            # Detect failure on the test
            res = ToolResult(
                tool_name="execute_tests",
                tool_call_id="retest",
                success=(test_output.get("exit_code") == 0),
                output=test_output
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
