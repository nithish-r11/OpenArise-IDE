import uuid
from enum import Enum
from typing import List
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class BlueprintStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

class FeatureItem(BaseModel):
    feature_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_ids: List[str] = Field(default_factory=list)
    title: str
    description: str
    status: BlueprintStatus = BlueprintStatus.PENDING

class TaskItem(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature_id: str
    title: str
    description: str
    status: BlueprintStatus = BlueprintStatus.PENDING
    dependencies: List[str] = Field(default_factory=list)

class ProjectBlueprint(BaseModel):
    project_id: str
    project_name: str
    description: str = ""
    requirements: List[str] = Field(default_factory=list)
    features: List[FeatureItem] = Field(default_factory=list)
    tasks: List[TaskItem] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_request: str = ""
