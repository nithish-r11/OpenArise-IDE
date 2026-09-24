import json
import logging
import time
from pathlib import Path
from threading import RLock
from typing import Optional

from app.agent.state import AgentState, AgentLifecycleError
from app.models.schemas import (
    ActionState, AgentAction, AgentEvent, AgentRequest, AgentResponse,
    DiagnosisResult, EvidenceRecord, EvidenceStrength, EvidenceType, ExecutionState,
    FailureCategory, FailureEvent, FailureStatus, PendingAction, ToolResult,
    VerificationStatus,
)
from app.context.manager import ContextManager
from app.llm.base import LLMProvider
from app.tools.base import ToolRegistry
from app.tools.execution import TestExecutionTool
from app.tools.permissions import PermissionAction, PermissionManager, RiskLevel
from app.failures.detector import FailureDetector
from app.failures.analyzer import RootCauseAnalyzer
from app.failures.history import FailureHistoryManager
from app.recovery.engine import RecoveryEngine
from app.recovery.planner import RecoveryPlanner
from app.recovery.checkpoint import CheckpointManager
from app.memory.manager import MemoryManager
from app.memory.redact import SecretRedactor
from app.verification.requirements import RequirementExtractor
from app.verification.evidence import EvidenceLedger
from app.verification.engine import IndependentVerifier
from app.verification.drift import RequirementDriftDetector
from app.verification.gate import CompletionGate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI software engineering agent.
You operate inside OpenArise IDE.
Do not claim an action was executed unless a tool actually executed it.
Do not claim tests passed without test evidence.
Clearly distinguish reasoning, proposed actions, and completed actions.
Use only registered tools. Associate tool calls with the supplied requirement IDs.
Follow the current agent state. Do not install dependencies automatically.
Be concise and structured."""


class AgentOrchestrator:
    """Synchronous agent pipeline with one retained, resumable action per request."""

    def __init__(self, llm_provider: LLMProvider, context_manager: Optional[ContextManager] = None,
                 tool_registry: Optional[ToolRegistry] = None, permission_manager: Optional[PermissionManager] = None,
                 failure_history: Optional[FailureHistoryManager] = None, project_root: str = "."):
        self.project_root = str(Path(project_root).resolve())
        self.llm = llm_provider
        self.context = context_manager or ContextManager()
        self.tool_registry = tool_registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager()
        self.failure_detector = FailureDetector()
        self.root_cause_analyzer = RootCauseAnalyzer(self.llm)
        self.failure_history = failure_history or FailureHistoryManager()
        self.memory_manager = MemoryManager(self.project_root)
        self.checkpoint_manager = CheckpointManager(self.project_root)
        self.recovery_planner = RecoveryPlanner(self.llm, self.memory_manager)
        self.recovery_engine = RecoveryEngine(
            self.recovery_planner, self.tool_registry, self.permission_manager, self.checkpoint_manager
        )
        self.requirement_extractor = RequirementExtractor(self.llm)
        self.evidence_ledger = EvidenceLedger()
        self.independent_verifier = IndependentVerifier(self.project_root, self.evidence_ledger)
        self.drift_detector = RequirementDriftDetector(self.project_root, self.evidence_ledger)
        self.completion_gate = CompletionGate(self.independent_verifier)
        self.requirements = []
        self.state = AgentState.IDLE
        self.execution_state = ExecutionState(current_state=self.state.value)
        self._lock = RLock()
        self._requests = {}
        self._responses = {}
        self._request = None
        self._action = None
        self._pending = None
        self._pending_tool = None
        self._tool_results = []
        self._next_tool = 0
        self._recovery_attempts = 0

    def _event(self, event_type, tool_call_id=None):
        if self._request:
            self.execution_state.events.append(AgentEvent(
                request_id=self._request.request_id,
                sequence=len(self.execution_state.events) + 1,
                event_type=event_type, current_state=self.state.value,
                tool_call_id=tool_call_id,
            ))

    def _transition_to(self, new_state: AgentState):
        self.state = new_state
        self.execution_state.current_state = new_state.value
        self._event("state_changed")

    def _response(self, status, message, action_state, verification=None, error=None):
        data = {
            "action_type": self._action.action_type if self._action else None,
            "agent_message": self._action.message if self._action else None,
            "tool_calls": [t.model_dump(mode="json") for t in self._action.tool_calls] if self._action else [],
            "tool_results": [r.model_dump(mode="json") for r in self._tool_results],
            "requirements": [r.model_dump(mode="json") for r in self.requirements],
            "evidence": [e.model_dump(mode="json") for e in self.evidence_ledger.list_evidence()],
            "verification": verification.model_dump(mode="json") if verification else None,
            "events": [e.model_dump(mode="json") for e in self.execution_state.events],
        }
        if error:
            data["error"] = error
        response = AgentResponse(
            request_id=self._request.request_id, status=status, message=message,
            current_state=self.state.value, action_state=action_state,
            pending_action=self._pending.model_copy(deep=True) if self._pending else None,
            data=data,
        )
        self._responses[self._request.request_id] = response.model_copy(deep=True)
        return response

    def process_request(self, request: AgentRequest) -> AgentResponse:
        with self._lock:
            if request.request_id in self._requests:
                if self._requests[request.request_id] != request.model_dump(mode="json"):
                    raise AgentLifecycleError("action_conflict", "Request ID was already used for different input.")
                return self.get_request(request.request_id)
            if self._pending:
                raise AgentLifecycleError("action_conflict", "Resolve the pending action before starting another request.")
            self._request = request.model_copy(deep=True)
            self._requests[request.request_id] = request.model_dump(mode="json")
            self._action = None
            self._tool_results = []
            self._next_tool = 0
            self._recovery_attempts = 0
            self.execution_state = ExecutionState(current_state=self.state.value)
            self.evidence_ledger.clear()
            self.requirements = []
            try:
                self._transition_to(AgentState.THINKING)
                self.context.update_request(request.prompt)
                self.context.project_state = dict(request.context_data or {})
                self.requirements = self.requirement_extractor.extract(request.prompt)
                prompt = (
                    f"User Request: {request.prompt}\n\nContext Summary:\n"
                    f"{json.dumps(self.context.get_context_summary(), indent=2)}\n\n"
                    f"Requirements:\n{json.dumps([r.model_dump(mode='json') for r in self.requirements])}\n\n"
                    f"Available tools:\n{json.dumps(self.tool_registry.get_all_schemas())}\n\nDetermine the next action."
                )
                self._transition_to(AgentState.PLANNING)
                generated = self.llm.generate_structured(
                    prompt=prompt, schema=AgentAction, system_prompt=SYSTEM_PROMPT
                )
                self._action = AgentAction.model_validate(generated).model_copy(deep=True)
                ids = [call.tool_call_id for call in self._action.tool_calls]
                if len(ids) != len(set(ids)) or any(not value for value in ids):
                    raise ValueError("Tool call IDs must be unique and nonempty within an action.")
                self.execution_state.history.append(self._action.model_copy(deep=True))
                return self._continue()
            except Exception as exc:
                return self._fail_internal(exc)

    def get_request(self, request_id: str) -> AgentResponse:
        with self._lock:
            if request_id not in self._responses:
                raise AgentLifecycleError("request_not_found", "Unknown agent request.")
            return self._responses[request_id].model_copy(deep=True)

    def _require_pending(self, request_id, tool_call_id=None):
        if request_id not in self._requests:
            raise AgentLifecycleError("request_not_found", "Unknown agent request.")
        if not self._pending or self._pending.request_id != request_id:
            raise AgentLifecycleError("action_conflict", "Request has no pending action.")
        if tool_call_id is not None and tool_call_id != self._pending.tool_call_id:
            raise AgentLifecycleError("action_conflict", "Tool call ID does not match the pending action.")
        try:
            current_tool = self.tool_registry.get_tool(self._pending.tool_call.tool_name)
        except KeyError:
            current_tool = None
        if current_tool is not self._pending_tool or current_tool.risk_level != self._pending.risk_level:
            raise AgentLifecycleError("action_conflict", "Pending tool registration changed; cancel the request.")

    def approve_action(self, request_id: str, tool_call_id: str) -> AgentResponse:
        with self._lock:
            self._require_pending(request_id, tool_call_id)
            if self.permission_manager.get_action_for_risk(self._pending.risk_level) == PermissionAction.DENY:
                raise AgentLifecycleError("permission_required", "Permission policy denies this action.")
            self.permission_manager.grant_approval(tool_call_id)
            self._pending.approved = True
            self._transition_to(AgentState.APPROVED)
            self._event("permission_approved", tool_call_id)
            return self._response("approved", "Permission recorded; resume to execute the stored action.", ActionState.APPROVED)

    def resume_request(self, request_id: str, tool_call_id: str) -> AgentResponse:
        with self._lock:
            self._require_pending(request_id, tool_call_id)
            if not self.permission_manager.check_permission(tool_call_id, self._pending.risk_level):
                self._pending.approved = False
                self._transition_to(AgentState.PERMISSION_REQUIRED)
                return self._response("permission_required", "Approval is required before execution.", ActionState.PERMISSION_REQUIRED)
            self._pending = None
            self._pending_tool = None
            try:
                return self._continue()
            except Exception as exc:
                return self._fail_internal(exc)

    def deny_action(self, request_id: str, tool_call_id: str) -> AgentResponse:
        with self._lock:
            self._require_pending(request_id, tool_call_id)
            return self._stop_pending(ActionState.DENIED, "Pending action denied; remaining tools were not executed.")

    def cancel_request(self, request_id: str) -> AgentResponse:
        with self._lock:
            if request_id not in self._requests:
                raise AgentLifecycleError("request_not_found", "Unknown agent request.")
            if not self._pending or self._pending.request_id != request_id:
                raise AgentLifecycleError("action_conflict", "Only a pending request can be cancelled.")
            return self._stop_pending(ActionState.CANCELLED, "Request cancelled; earlier executed tools are not rolled back.")

    def _stop_pending(self, action_state, message):
        call = self._pending.tool_call
        self.permission_manager.revoke_approval(call.tool_call_id)
        self._tool_results.append(ToolResult(
            tool_name=call.tool_name, tool_call_id=call.tool_call_id, success=False,
            error=action_state.value, metadata={"executed": False},
        ))
        self._pending = None
        self._pending_tool = None
        return self._finish(action_state, message)

    def _continue(self):
        while self._next_tool < len(self._action.tool_calls):
            call = self._action.tool_calls[self._next_tool]
            try:
                tool = self.tool_registry.get_tool(call.tool_name)
            except KeyError:
                self._record_result(call, None, ToolResult(
                    tool_name=call.tool_name, tool_call_id=call.tool_call_id,
                    success=False, error="Tool not found in registry.", metadata={"executed": False},
                ))
                self._next_tool += 1
                continue
            known_requirements = {r.requirement_id for r in self.requirements}
            if set(call.requirement_ids) - known_requirements:
                self._record_result(call, tool, ToolResult(
                    tool_name=call.tool_name, tool_call_id=call.tool_call_id, success=False,
                    error="Unknown requirement association.", metadata={"executed": False},
                ))
                self._next_tool += 1
                continue
            if not self.permission_manager.check_permission(call.tool_call_id, tool.risk_level):
                self._pending_tool = tool
                self._pending = PendingAction(
                    request_id=self._request.request_id, tool_call_id=call.tool_call_id,
                    tool_call=call.model_copy(deep=True), risk_level=tool.risk_level,
                    action_index=self._next_tool,
                )
                if self.permission_manager.get_action_for_risk(tool.risk_level) == PermissionAction.DENY:
                    return self._stop_pending(ActionState.DENIED, "Permission policy denied the pending action.")
                self._transition_to(AgentState.PERMISSION_REQUIRED)
                self._event("permission_required", call.tool_call_id)
                return self._response("permission_required", "Tool approval is required.", ActionState.PERMISSION_REQUIRED)
            self._transition_to(AgentState.EXECUTING)
            self._event("tool_started", call.tool_call_id)
            started = time.monotonic()
            try:
                output = tool.execute(**call.arguments)
                exit_code = output.get("exit_code") if isinstance(output, dict) else None
                success = exit_code in (None, 0) and not (
                    isinstance(output, dict) and (output.get("error") or output.get("success") is False)
                )
                result = ToolResult(
                    tool_name=call.tool_name, tool_call_id=call.tool_call_id, success=success,
                    output=output, exit_code=exit_code,
                    error=None if success else f"Tool execution failed (exit code {exit_code}).",
                    duration=time.monotonic() - started, metadata={"executed": True},
                )
            except Exception as exc:
                result = ToolResult(
                    tool_name=call.tool_name, tool_call_id=call.tool_call_id, success=False,
                    error=str(exc), duration=time.monotonic() - started, metadata={"executed": True},
                )
            finally:
                self.permission_manager.revoke_approval(call.tool_call_id)
            self._record_result(call, tool, result)
            self._next_tool += 1
            if not result.success:
                try:
                    self._handle_failure(result)
                except Exception:
                    logger.exception("Failure diagnosis/recovery was unavailable.")
        return self._finish()

    def _record_result(self, call, tool, result):
        self._tool_results.append(result)
        self.context.add_tool_result(result.model_dump(mode="json"))
        self._transition_to(AgentState.OBSERVING)
        self._event("tool_finished", call.tool_call_id)
        requirement_ids = call.requirement_ids or (
            [self.requirements[0].requirement_id] if len(self.requirements) == 1 else []
        )
        is_test = isinstance(tool, TestExecutionTool) and result.metadata.get("executed", False)
        evidence_type = (EvidenceType.TEST_PASS if result.success else EvidenceType.TEST_FAIL) if is_test else EvidenceType.TOOL_RESULT
        strength = EvidenceStrength.CONTRADICTORY if not result.success else (
            EvidenceStrength.DIRECT if is_test and result.exit_code == 0 else EvidenceStrength.SUPPORTING
        )
        # A later mutation invalidates earlier test proof. A subsequent passing
        # test can supersede stale passing evidence, never contradictory evidence.
        if result.metadata.get("executed") and tool and tool.risk_level in (RiskLevel.WRITE, RiskLevel.EXECUTE) and not is_test:
            for prior in self.evidence_ledger.list_evidence():
                if prior.evidence_type == EvidenceType.TEST_PASS:
                    prior.result["stale"] = True
        if is_test and result.success:
            for prior in self.evidence_ledger.list_evidence():
                if (prior.requirement_id in requirement_ids
                        and prior.evidence_type == EvidenceType.TEST_PASS
                        and prior.result.get("stale")):
                    prior.result["superseded"] = True
        for requirement in self.requirements:
            if requirement.requirement_id not in requirement_ids:
                continue
            evidence = EvidenceRecord(
                requirement_id=requirement.requirement_id, evidence_type=evidence_type,
                strength=strength, source=call.tool_name, summary=f"Tool {call.tool_name} execution",
                result={"success": result.success, "exit_code": result.exit_code,
                        "output": result.output, "error": result.error, "executed": result.metadata.get("executed")},
                tool_call_id=call.tool_call_id,
            )
            self.evidence_ledger.add_evidence(evidence)
            requirement.evidence_references.append(evidence.evidence_id)

    def _handle_failure(self, result):
        detection = self.failure_detector.detect(result)
        if not detection:
            return
        failure = FailureEvent(
            tool_call_id=result.tool_call_id, tool_name=result.tool_name,
            category=detection["category"], summary=detection["summary"],
            error_signature=detection["error_signature"], affected_file=detection["affected_file"],
            evidence=SecretRedactor().redact_dict(
                {"output": result.output, "error": result.error, "exit_code": result.exit_code}
            ),
        )
        self.context.add_failure(failure.model_dump(mode="json"))
        memory_record = self.memory_manager.record_failure(failure)
        diagnosis = DiagnosisResult.model_validate(self.root_cause_analyzer.analyze(failure))
        failure.root_cause = diagnosis.probable_root_cause
        failure.confidence = diagnosis.confidence
        failure.status = FailureStatus.DIAGNOSED
        self.memory_manager.update_with_diagnosis(memory_record.memory_id, diagnosis)
        self.failure_history.record_failure(failure)
        self._transition_to(AgentState.RECOVERING)
        self._recovery_attempts += 1
        recovery = self.recovery_engine.attempt_recovery(
            failure, diagnosis, attempts=1,
            repeated_count=3 if self.failure_history.detect_loop(result.tool_name, detection["error_signature"]) else 1,
        )
        self.memory_manager.update_with_recovery(memory_record.memory_id, recovery)
        self._event("recovery_finished", result.tool_call_id)

    def _finish(self, terminal=None, message=None):
        self._transition_to(AgentState.VERIFYING)
        self.drift_detector.detect_drift(self.requirements)
        gate = self.completion_gate.evaluate(
            self.memory_manager.project_id, self.requirements, recovery_attempts=self._recovery_attempts
        )
        if terminal is not None:
            self._transition_to(AgentState(terminal.value.upper()))
            return self._response(terminal.value, message, terminal, gate)
        if any(not r.success for r in self._tool_results):
            self._transition_to(AgentState.FAILED)
            return self._response("failure", "One or more tools failed; inspect tool results and verification.", ActionState.FAILED, gate)
        self._transition_to(AgentState.COMPLETED)
        if gate.overall_status == VerificationStatus.VERIFIED:
            return self._response("success", "Action completed and fully verified.", ActionState.COMPLETED, gate)
        return self._response(
            "unverified", f"Agent finished but verification status is: {gate.overall_status.value}",
            ActionState.COMPLETED, gate,
        )

    def _fail_internal(self, exc):
        logger.exception("Agent processing failed.")
        if self._pending:
            self.permission_manager.revoke_approval(self._pending.tool_call_id)
        self._pending = None
        self._pending_tool = None
        self._transition_to(AgentState.FAILED)
        failure = FailureEvent(
            category=FailureCategory.UNKNOWN, summary=f"Orchestrator error: {type(exc).__name__}",
        )
        self.context.add_failure(failure.model_dump(mode="json"))
        gate = self.completion_gate.evaluate(
            self.memory_manager.project_id, self.requirements, recovery_attempts=self._recovery_attempts
        )
        return self._response(
            "failure", "Agent processing failed. Inspect backend logs and retained tool results.",
            ActionState.FAILED, gate, error=failure.model_dump(mode="json"),
        )
