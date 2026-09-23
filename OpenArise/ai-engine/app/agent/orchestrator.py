import logging
import json
from typing import Optional
from app.agent.state import AgentState
from app.models.schemas import AgentRequest, AgentResponse, AgentAction, ExecutionState, FailureEvent, ToolResult, FailureCategory
from app.context.manager import ContextManager
from app.llm.base import LLMProvider
from app.tools.base import ToolRegistry
from app.tools.permissions import PermissionManager
from app.failures.detector import FailureDetector
from app.failures.analyzer import RootCauseAnalyzer
from app.failures.history import FailureHistoryManager

from app.recovery.engine import RecoveryEngine
from app.recovery.planner import RecoveryPlanner
from app.recovery.checkpoint import CheckpointManager
from app.models.schemas import RecoveryState, VerificationStatus
from app.memory.manager import MemoryManager
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
Follow the current agent state.
Be concise and structured."""

class AgentOrchestrator:
    """Minimal Agent Orchestrator for handling AI execution pipelines."""
    
    def __init__(self, llm_provider: LLMProvider, context_manager: Optional[ContextManager] = None, 
                 tool_registry: Optional[ToolRegistry] = None, permission_manager: Optional[PermissionManager] = None,
                 failure_history: Optional[FailureHistoryManager] = None, project_root: str = "."):
        self.llm = llm_provider
        self.context = context_manager or ContextManager()
        self.tool_registry = tool_registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager()
        self.failure_detector = FailureDetector()
        self.root_cause_analyzer = RootCauseAnalyzer(self.llm)
        self.failure_history = failure_history or FailureHistoryManager()
        self.memory_manager = MemoryManager(project_root)
        
        # Recovery
        self.checkpoint_manager = CheckpointManager(project_root)
        self.recovery_planner = RecoveryPlanner(self.llm, self.memory_manager)
        self.recovery_engine = RecoveryEngine(
            self.recovery_planner, self.tool_registry, 
            self.permission_manager, self.checkpoint_manager
        )
        
        # Verification
        self.requirement_extractor = RequirementExtractor(self.llm)
        self.evidence_ledger = EvidenceLedger()
        self.independent_verifier = IndependentVerifier(project_root, self.evidence_ledger)
        self.drift_detector = RequirementDriftDetector(project_root, self.evidence_ledger)
        self.completion_gate = CompletionGate(self.independent_verifier)
        self.requirements = []
        
        self.state = AgentState.IDLE
        self.execution_state = ExecutionState(current_state=self.state.value)
        
    def _transition_to(self, new_state: AgentState):
        """Transition to a new state and update execution tracking."""
        logger.info(f"State transition: {self.state} -> {new_state}")
        self.state = new_state
        self.execution_state.current_state = new_state.value
        
    def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process a user request through the AI pipeline."""
        try:
            self._transition_to(AgentState.THINKING)
            
            # Build context
            self.context.update_request(request.prompt)
            if request.context_data:
                for k, v in request.context_data.items():
                    self.context.project_state[k] = v
                    
            context_summary = self.context.get_context_summary()
            
            # Prepare prompt
            prompt = f"User Request: {request.prompt}\n\nContext Summary:\n{json.dumps(context_summary, indent=2)}\n\nDetermine the next action."
            
            # Call LLM
            self._transition_to(AgentState.EXECUTING)
            
            action: AgentAction = self.llm.generate_structured(
                prompt=prompt,
                schema=AgentAction,
                system_prompt=SYSTEM_PROMPT
            )
            
            self.execution_state.history.append(action)
            
            # Process the action
            self._transition_to(AgentState.OBSERVING)
            
            tool_results = []
            
            if action.tool_calls:
                for t_call in action.tool_calls:
                    try:
                        tool = self.tool_registry.get_tool(t_call.tool_name)
                    except KeyError:
                        res = ToolResult(
                            tool_name=t_call.tool_name,
                            tool_call_id=t_call.tool_call_id,
                            success=False,
                            error="Tool not found in registry."
                        )
                        tool_results.append(res)
                        continue
                        
                    start_time = __import__('time').time()
                    
                    if not self.permission_manager.check_permission(t_call.tool_call_id, tool.risk_level):
                        res = ToolResult(
                            tool_name=t_call.tool_name,
                            tool_call_id=t_call.tool_call_id,
                            success=False,
                            error="permission_required"
                        )
                        tool_results.append(res)
                        continue
                        
                    try:
                        output = tool.execute(**t_call.arguments)
                        duration = __import__('time').time() - start_time
                        
                        exit_code = None
                        if isinstance(output, dict) and "exit_code" in output:
                            exit_code = output.get("exit_code")
                            
                        res = ToolResult(
                            tool_name=t_call.tool_name,
                            tool_call_id=t_call.tool_call_id,
                            success=True if exit_code in (None, 0) else False,
                            output=output,
                            duration=duration,
                            exit_code=exit_code
                        )
                    except Exception as e:
                        duration = __import__('time').time() - start_time
                        res = ToolResult(
                            tool_name=t_call.tool_name,
                            tool_call_id=t_call.tool_call_id,
                            success=False,
                            error=str(e),
                            duration=duration
                        )
                        
                    tool_results.append(res)
                    self.context.add_tool_result(res.model_dump())
                    
                    # Phase 7: Collect Evidence
                    from app.models.schemas import EvidenceRecord, EvidenceType, EvidenceStrength
                    
                    ev_type = EvidenceType.TEST_PASS if "test" in tool_call.tool_name and res.success else (EvidenceType.TEST_FAIL if "test" in tool_call.tool_name else EvidenceType.TOOL_RESULT)
                    ev_strength = EvidenceStrength.DIRECT if "test" in tool_call.tool_name else EvidenceStrength.SUPPORTING
                    
                    if self.requirements:
                        ev = EvidenceRecord(
                            requirement_id=self.requirements[0].requirement_id,
                            evidence_type=ev_type,
                            strength=ev_strength,
                            source=tool_call.tool_name,
                            summary=f"Tool {tool_call.tool_name} execution",
                            result={"output": res.output, "exit_code": res.exit_code, "success": res.success},
                            tool_call_id=tool_call.tool_call_id
                        )
                        self.evidence_ledger.add_evidence(ev)
                    
                    # Failure Detection Pipeline
                    detection = self.failure_detector.detect(res)
                    if detection:
                        # We have a failure
                        failure_event = FailureEvent(
                            tool_call_id=res.tool_call_id,
                            tool_name=res.tool_name,
                            category=detection["category"],
                            summary=detection["summary"],
                            error_signature=detection["error_signature"],
                            affected_file=detection["affected_file"],
                            evidence={"output": res.output, "error": res.error, "exit_code": res.exit_code}
                        )
                        
                        # Add failure to context so agent can see it
                        self.context.add_failure(failure_event.model_dump())
                        
                        # Memory: Record Failure
                        try:
                            memory_record = self.memory_manager.record_failure(failure_event)
                        except Exception as e:
                            logger.error(f"Memory storage failed: {e}")
                            memory_record = None
                        
                        # Root Cause Analysis
                        diagnosis = self.root_cause_analyzer.analyze(failure_event)
                        failure_event.root_cause = diagnosis.probable_root_cause
                        failure_event.confidence = diagnosis.confidence
                        failure_event.status = "DIAGNOSED"
                        
                        # Memory: Update Diagnosis
                        if memory_record:
                            try:
                                self.memory_manager.update_with_diagnosis(memory_record.memory_id, diagnosis)
                            except Exception as e:
                                logger.error(f"Memory update failed: {e}")
                        
                        # Record in history
                        self.failure_history.record_failure(failure_event)
                        
                        # Detect loops
                        if self.failure_history.detect_loop(res.tool_name, detection["error_signature"]):
                            logger.warning(f"REPEATED_FAILURE detected for {res.tool_name} with signature {detection['error_signature']}")
                            # Phase 5 will handle recovery. For now just log.
                        
                        # Attempt Recovery
                        recovery_result = self.recovery_engine.attempt_recovery(
                            failure_event, diagnosis, attempts=1, repeated_count=1 if not self.failure_history.detect_loop(res.tool_name, detection["error_signature"]) else 3
                        )
                        
                        # Memory: Record Recovery
                        if memory_record:
                            try:
                                self.memory_manager.update_with_recovery(memory_record.memory_id, recovery_result)
                            except Exception as e:
                                logger.error(f"Memory update failed: {e}")
                        
                        if recovery_result.status == RecoveryState.RECOVERED:
                            logger.info(f"Successfully recovered from failure: {failure_event.failure_id}")
                            # Agent can continue
                            continue
                        elif recovery_result.status == RecoveryState.BLOCKED:
                            logger.info(f"Recovery blocked: {recovery_result.final_result}")
                        else:
                            logger.warning(f"Recovery failed/rolled back: {recovery_result.final_result}")
                            
            # Phase 7: Completion Gate
            # Drift detection first
            self.drift_detector.detect_drift(self.requirements)
            
            # Evaluate gate
            gate_result = self.completion_gate.evaluate(self.memory_manager.project_id, self.requirements)
            
            self._transition_to(AgentState.COMPLETED)
            
            if gate_result.overall_status == VerificationStatus.VERIFIED:
                return AgentResponse(
                    status="success",
                    message="Action completed and fully verified.",
                    data={
                        "action_type": action.action_type, 
                        "tool_calls": [t.model_dump() for t in action.tool_calls],
                        "tool_results": [r.model_dump() for r in tool_results],
                        "verification": gate_result.model_dump()
                    }
                )
            else:
                logger.warning(f"Completion Gate blocked full success. Status: {gate_result.overall_status}")
                return AgentResponse(
                    status="unverified",
                    message=f"Agent finished but verification status is: {gate_result.overall_status.value}",
                    data={
                        "action_type": action.action_type, 
                        "tool_calls": [t.model_dump() for t in action.tool_calls],
                        "tool_results": [r.model_dump() for r in tool_results],
                        "verification": gate_result.model_dump()
                    }
                )
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            self._transition_to(AgentState.FAILED)
            
            failure = FailureEvent(
                category=FailureCategory.UNKNOWN,
                summary=f"Orchestrator error: {type(e).__name__}",
                root_cause=str(e),
                evidence={"traceback": str(e)}
            )
            self.context.add_failure(failure.model_dump())
            
            return AgentResponse(
                status="failure",
                message=f"Agent failed to process request: {e}",
                data={"error": failure.model_dump()}
            )
