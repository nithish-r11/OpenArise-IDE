import uuid
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class TimelineEventType(str, Enum):
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_SCANNED = "PROJECT_SCANNED"
    BLUEPRINT_CREATED = "BLUEPRINT_CREATED"
    REQUIREMENT_CREATED = "REQUIREMENT_CREATED"
    REQUIREMENT_UPDATED = "REQUIREMENT_UPDATED"
    FEATURE_CREATED = "FEATURE_CREATED"
    TASK_CREATED = "TASK_CREATED"
    IMPLEMENTATION_MAPPED = "IMPLEMENTATION_MAPPED"
    EVIDENCE_LINKED = "EVIDENCE_LINKED"
    HEALTH_CHECKED = "HEALTH_CHECKED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    AGENT_STATE_CHANGED = "AGENT_STATE_CHANGED"

class DriftState(str, Enum):
    NO_DRIFT = "NO_DRIFT"
    POTENTIAL_DRIFT = "POTENTIAL_DRIFT"
    CONFIRMED_STRUCTURAL_DRIFT = "CONFIRMED_STRUCTURAL_DRIFT"
    UNRESOLVED = "UNRESOLVED"

class TimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: TimelineEventType
    title: str
    description: str
    related_project_id: Optional[str] = None
    related_requirement_ids: List[str] = Field(default_factory=list)
    related_feature_ids: List[str] = Field(default_factory=list)
    related_task_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic fingerprint for duplicate prevention (ignores timestamp and event_id)."""
        parts = [
            self.event_type.value,
            self.title,
            self.description,
            str(self.related_project_id),
            ",".join(sorted(self.related_requirement_ids)),
            ",".join(sorted(self.related_feature_ids)),
            ",".join(sorted(self.related_task_ids))
        ]
        return "|".join(parts)

class RequirementBaseline(BaseModel):
    requirement_id: str
    content_hash: Optional[str] = None
    acceptance_criteria_hash: Optional[str] = None
    implementation_hashes: Dict[str, str] = Field(default_factory=dict)
    task_feature_ids: Dict[str, str] = Field(default_factory=dict)
    associated_feature_ids: List[str] = Field(default_factory=list)
    associated_task_ids: List[str] = Field(default_factory=list)
    implementation_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    
class ChangeImpactCandidate(BaseModel):
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    changed_file: str
    changed_symbol: Optional[str] = None
    related_requirement_ids: List[str] = Field(default_factory=list)
    related_feature_ids: List[str] = Field(default_factory=list)
    related_task_ids: List[str] = Field(default_factory=list)
    basis: str

class DriftFinding(BaseModel):
    requirement_id: str
    state: DriftState
    reason: str
    related_implementations: List[str] = Field(default_factory=list)
    related_tasks: List[str] = Field(default_factory=list)

class ProjectIntelligenceSnapshot(BaseModel):
    project_id: str
    project_name: str
    scan_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Factual summaries
    project_state_summary: Dict[str, int] = Field(default_factory=dict)
    blueprint_summary: Dict[str, int] = Field(default_factory=dict)
    traceability_summary: Dict[str, int] = Field(default_factory=dict)
    environment_summary: Dict[str, Any] = Field(default_factory=dict)
    health_summary: Dict[str, int] = Field(default_factory=dict)
    requirement_summary: Dict[str, Any] = Field(default_factory=dict)
    
    drift_summary: List[DriftFinding] = Field(default_factory=list)
    timeline_summary: List[TimelineEvent] = Field(default_factory=list)
