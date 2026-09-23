import uuid
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class DependencyState(str, Enum):
    DECLARED = "declared"
    INSTALLED = "installed"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"
    UNKNOWN = "unknown"
    INSPECTION_NOT_AVAILABLE = "inspection_not_available"

class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"

class InstallationAction(str, Enum):
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    BLOCKED = "BLOCKED"

class InspectionScope(str, Enum):
    CURRENT_ENVIRONMENT = "current_environment"
    PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED = "project_virtualenv_detected_but_not_inspected"

class EnvironmentInfo(BaseModel):
    python_available: bool = False
    python_executable: Optional[str] = None
    python_version: Optional[str] = None
    virtualenv_present: bool = False
    virtualenv_path: Optional[str] = None
    virtualenv_usable: bool = False
    platform: Optional[str] = None
    git_available: bool = False
    inspection_scope: InspectionScope = InspectionScope.CURRENT_ENVIRONMENT

class DependencyStatus(BaseModel):
    name: str
    version_specifier: Optional[str] = None
    declared: bool = False
    installed: bool = False
    installed_version: Optional[str] = None
    status: DependencyState = DependencyState.UNKNOWN
    source_file: Optional[str] = None
    action: InstallationAction = InstallationAction.REVIEW_REQUIRED
    message: Optional[str] = None

class HealthCheck(BaseModel):
    check_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    status: str
    severity: Severity
    message: str
    evidence: Optional[str] = None

class ProjectHealthReport(BaseModel):
    project_id: str
    checks: List[HealthCheck] = Field(default_factory=list)
    dependency_status: List[DependencyStatus] = Field(default_factory=list)
    environment: EnvironmentInfo
    health_signals: dict = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
