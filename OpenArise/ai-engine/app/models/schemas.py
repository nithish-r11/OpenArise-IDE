import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class AgentRequest(BaseModel):
    """Initial request to the agent."""
    prompt: str = Field(..., description="The user's instruction or request")
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")

class ToolCall(BaseModel):
    """A request for the agent to call a tool."""
    tool_name: str = Field(..., description="The name of the tool to call")
    tool_call_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID for this tool call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")

class ToolResult(BaseModel):
    """The result of calling a tool."""
    tool_name: str
    tool_call_id: str
    success: bool = True
    output: Any = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration: float = 0.0
    exit_code: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentAction(BaseModel):
    """An action taken by the agent."""
    action_type: str = Field(..., description="The type of action (e.g., tool_call, message)")
    tool_calls: List[ToolCall] = Field(default_factory=list)
    message: Optional[str] = None

class AgentResponse(BaseModel):
    """The final response from the agent."""
    status: str = Field(..., description="The final status of the request (e.g., success, failure)")
    message: str = Field(..., description="The final message to the user")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional structured data")

class ExecutionState(BaseModel):
    """The current execution state of the agent."""
    current_state: str
    history: List[AgentAction] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)

from enum import Enum

class FailureCategory(str, Enum):
    SYNTAX_ERROR = "SYNTAX_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    TEST_FAILURE = "TEST_FAILURE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    TIMEOUT = "TIMEOUT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    UNKNOWN = "UNKNOWN"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class FailureStatus(str, Enum):
    DETECTED = "DETECTED"
    DIAGNOSED = "DIAGNOSED"
    UNRESOLVED = "UNRESOLVED"

class FailureEvent(BaseModel):
    """A failure event detected during execution."""
    failure_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_call_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_name: Optional[str] = None
    category: FailureCategory = FailureCategory.UNKNOWN
    summary: str
    root_cause: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    affected_file: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    status: FailureStatus = FailureStatus.DETECTED
    error_signature: Optional[str] = None

class DiagnosisResult(BaseModel):
    """Result of root cause analysis."""
    category: FailureCategory
    summary: str
    probable_root_cause: str
    affected_tool: Optional[str] = None
    affected_file: Optional[str] = None
    suggested_next_investigation: Optional[str] = None
    confidence: ConfidenceLevel

class RecoveryState(str, Enum):
    PLANNING = "PLANNING"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    CHECKPOINTING = "CHECKPOINTING"
    APPLYING = "APPLYING"
    RETESTING = "RETESTING"
    RECOVERED = "RECOVERED"
    RETRYING = "RETRYING"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"

class RecoveryPolicy(BaseModel):
    """Configuration for recovery limits."""
    max_attempts_per_failure: int = 3
    max_repeated_identical: int = 2
    max_actions_per_cycle: int = 5
    timeout_seconds: int = 60

from app.tools.permissions import RiskLevel

class RecoveryPlan(BaseModel):
    """A proposed recovery plan."""
    recovery_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_id: str
    goal: str
    diagnosis_summary: str
    proposed_actions: List[ToolCall] = Field(default_factory=list)
    expected_result: str
    risk_level: RiskLevel = RiskLevel.READ
    requires_permission: bool = False
    max_attempts: int = 3
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RecoveryResult(BaseModel):
    """Result of a recovery attempt."""
    recovery_id: str
    failure_id: str
    status: RecoveryState
    attempts: int = 0
    actions_executed: List[str] = Field(default_factory=list)
    tests_run: List[str] = Field(default_factory=list)
    final_result: str
    rollback_performed: bool = False
    rollback_checkpoint: Optional[str] = None
    failure_signature_before: str
    failure_signature_after: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration: float = 0.0

class FailureMemoryRecord(BaseModel):
    """Persistent memory record for a failure and its recovery attempts."""
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    session_id: Optional[str] = None
    failure_id: str
    failure_signature: str
    tool_name: Optional[str] = None
    category: FailureCategory
    summary: str
    root_cause: Optional[str] = None
    diagnosis_confidence: ConfidenceLevel = ConfidenceLevel.LOW
    affected_file: Optional[str] = None
    recovery_plan: Optional[Dict[str, Any]] = None
    recovery_actions: List[str] = Field(default_factory=list)
    test_evidence: Dict[str, Any] = Field(default_factory=dict)
    outcome: Optional[RecoveryState] = None
    rollback_performed: bool = False
    attempt_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = Field(default_factory=list)

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    
class EvidenceType(str, Enum):
    FILE_EXISTS = "FILE_EXISTS"
    SYMBOL_EXISTS = "SYMBOL_EXISTS"
    CODE_INSPECTION = "CODE_INSPECTION"
    TEST_PASS = "TEST_PASS"
    TEST_FAIL = "TEST_FAIL"
    COMMAND_RESULT = "COMMAND_RESULT"
    TOOL_RESULT = "TOOL_RESULT"
    RECOVERY_RESULT = "RECOVERY_RESULT"
    RUNTIME_RESULT = "RUNTIME_RESULT"

class EvidenceStrength(str, Enum):
    DIRECT = "DIRECT"
    SUPPORTING = "SUPPORTING"
    WEAK = "WEAK"
    CONTRADICTORY = "CONTRADICTORY"

class EvidenceRecord(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str
    evidence_type: EvidenceType
    strength: EvidenceStrength
    source: str
    summary: str
    result: Dict[str, Any]
    tool_call_id: Optional[str] = None
    file_hash: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Requirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    priority: str = "HIGH"
    status: VerificationStatus = VerificationStatus.PENDING
    implementation_references: List[str] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RequirementResult(BaseModel):
    requirement_id: str
    status: VerificationStatus
    evidence_used: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    explanation: str
    confidence: ConfidenceLevel

class CompletionReport(BaseModel):
    total_requirements: int
    verified: int
    partially_verified: int
    unverified: int
    inconclusive: int
    evidence_count: int
    tests_executed: int
    recovery_attempts: int
    remaining_issues: List[str] = Field(default_factory=list)

class VerificationResult(BaseModel):
    verification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    requirement_results: List[RequirementResult] = Field(default_factory=list)
    overall_status: VerificationStatus
    report: CompletionReport
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration: float = 0.0
