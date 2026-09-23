import uuid
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class TraceabilityState(str, Enum):
    UNMAPPED = "UNMAPPED"
    PARTIAL = "PARTIAL"
    MAPPED = "MAPPED"
    EVIDENCE_BACKED = "EVIDENCE_BACKED"
    INVALID = "INVALID"

class LinkType(str, Enum):
    REQUIREMENT_TO_FEATURE = "requirement_to_feature"
    FEATURE_TO_TASK = "feature_to_task"
    TASK_TO_IMPLEMENTATION = "task_to_implementation"
    REQUIREMENT_TO_IMPLEMENTATION = "requirement_to_implementation"
    IMPLEMENTATION_TO_TEST = "implementation_to_test"
    TEST_TO_EVIDENCE = "test_to_evidence"
    REQUIREMENT_TO_EVIDENCE = "requirement_to_evidence"

class TraceabilityLink(BaseModel):
    link_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    link_type: LinkType
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_backed: bool = False
    is_inferred: bool = False

class ImplementationNode(BaseModel):
    implementation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    module_name: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None  # e.g., 'class', 'function', 'module'
    feature_id: Optional[str] = None
    requirement_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class TestNode(BaseModel):
    __test__ = False
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    test_name: Optional[str] = None
    requirement_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

class TraceabilityGraph(BaseModel):
    project_id: str
    requirements: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    implementations: List[ImplementationNode] = Field(default_factory=list)
    tests: List[TestNode] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    links: List[TraceabilityLink] = Field(default_factory=list)
