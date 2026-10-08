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

    def prepare_recovery(self, failure, diagnosis, attempts, repeated_count):
        """Retain one real plan; approvals target exact registered action IDs."""
        import uuid
        from app.models.schemas import ToolCall
        result = RecoveryResult(recovery_id="rec_" + uuid.uuid4().hex,
                                failure_id=failure.failure_id, status=RecoveryState.PLANNING,
                                attempts=attempts, failure_signature_before=failure.error_signature or "",
                                final_result="Recovery planning started.")
        session = {"result": result, "failure": failure, "calls": [], "index": 0,
                   "checkpointed": False, "records": [], "done": False}
        if not self.policy.can_retry_failure(failure.error_signature or "", attempts, repeated_count):
            result.status, result.final_result, session["done"] = RecoveryState.BLOCKED, "Recovery policy limit reached.", True
            return session
        plan = self.planner.plan(failure, diagnosis)
        if not plan:
            result.status, result.final_result, session["done"] = RecoveryState.FAILED, "Recovery plan unavailable.", True
            return session
        if not plan.proposed_actions or len(plan.proposed_actions) > self.policy.policy.max_actions_per_cycle:
            result.status, result.final_result, session["done"] = RecoveryState.BLOCKED, "Recovery action count is invalid.", True
            return session
        if failure.category in (FailureCategory.IMPORT_ERROR, FailureCategory.DEPENDENCY_ERROR):
            result.status, result.final_result, session["done"] = RecoveryState.BLOCKED, "Automatic dependency installation is disabled.", True
            return session
        try:
            for call in plan.proposed_actions:
                self.tool_registry.get_tool(call.tool_name)
            self.tool_registry.get_tool("execute_tests")
        except KeyError:
            result.status, result.final_result, session["done"] = RecoveryState.BLOCKED, "Recovery tool unavailable.", True
            return session
        calls = [call.model_copy(deep=True) for call in plan.proposed_actions]
        for index, call in enumerate(calls):
            call.tool_call_id = result.recovery_id + "_" + str(index)
        calls.append(ToolCall(tool_name="execute_tests", tool_call_id=result.recovery_id + "_retest"))
        session["calls"] = calls
        session["plan"] = plan
        return session

    def advance_recovery(self, session, record, state):
        """Execute approved actions once; return the next exact approval request."""
        import time
        from app.tools.permissions import PermissionAction
        result = session["result"]
        while not session["done"] and session["index"] < len(session["calls"]):
            call = session["calls"][session["index"]]
            tool = self.tool_registry.get_tool(call.tool_name)
            if not self.permission_manager.check_permission(call.tool_call_id, tool.risk_level):
                if self.permission_manager.get_action_for_risk(tool.risk_level) == PermissionAction.DENY:
                    result.status, result.final_result, session["done"] = RecoveryState.BLOCKED, "Recovery action denied by permission policy.", True
                    break
                result.status = RecoveryState.PERMISSION_REQUIRED
                result.final_result = "Recovery retest requires approval." if call.tool_name == "execute_tests" else "Recovery action requires approval."
                return call
            if not session["checkpointed"]:
                paths = [c.arguments.get("path") for c in session["calls"] if c.tool_name == "write_file"]
                if paths:
                    result.rollback_checkpoint = self.checkpoint_manager.create_checkpoint([p for p in paths if p])
                session["checkpointed"] = True
            retest = session["index"] == len(session["calls"]) - 1
            result.status = RecoveryState.RETESTING if retest else RecoveryState.APPLYING
            state("RETESTING" if retest else "RECOVERING", call.tool_call_id, True)
            started = time.monotonic()
            try:
                output = tool.execute(**call.arguments)
                exit_code = output.get("exit_code") if isinstance(output, dict) else None
                success = exit_code in (None, 0) and not (isinstance(output, dict) and (output.get("error") or output.get("success") is False))
                item = ToolResult(tool_name=call.tool_name, tool_call_id=call.tool_call_id, output=output,
                                  exit_code=exit_code, success=success, error=None if success else "Recovery execution failed.",
                                  duration=time.monotonic()-started, metadata={"executed": True})
            except Exception as exc:
                item = ToolResult(tool_name=call.tool_name, tool_call_id=call.tool_call_id, success=False,
                                  error=str(exc), duration=time.monotonic()-started, metadata={"executed": True})
            finally:
                self.permission_manager.revoke_approval(call.tool_call_id)
            session["records"].append(item)
            record(call, tool, item)
            session["index"] += 1
            result.actions_executed.append(call.tool_name)
            if call.tool_name == "execute_tests":
                result.tests_run.append(call.tool_call_id)
            if not item.success:
                result.status, result.final_result = RecoveryState.FAILED, "Recovery retest failed." if retest else "Recovery action failed."
                self._rollback(result)
                session["done"] = True
                break
            if retest:
                result.status, result.final_result, session["done"] = RecoveryState.RECOVERED, "Recovery retest passed. CompletionGate still determines completion.", True
                result.evidence = {"retest_tool_call_id": call.tool_call_id, "exit_code": item.exit_code}
        return None
