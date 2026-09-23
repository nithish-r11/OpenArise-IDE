import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class ProjectInfo(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_path: str
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class FileInfo(BaseModel):
    relative_path: str
    file_type: str
    size: int
    modified_at: float
    content_hash: Optional[str] = None
    is_test: bool = False
    is_source: bool = False
    is_config: bool = False

class PythonModuleInfo(BaseModel):
    relative_path: str
    module_name: str
    imports: List[str] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    test_functions: List[str] = Field(default_factory=list)
    syntax_error: Optional[str] = None

class DependencyInfo(BaseModel):
    name: str
    version_specifier: Optional[str] = None
    source_file: str

class ProjectState(BaseModel):
    project_info: ProjectInfo
    files: List[FileInfo] = Field(default_factory=list)
    python_modules: List[PythonModuleInfo] = Field(default_factory=list)
    symbols: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[DependencyInfo] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    tests: List[str] = Field(default_factory=list)
    git_available: bool = False
    scan_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    health_signals: Dict[str, Any] = Field(default_factory=dict)
