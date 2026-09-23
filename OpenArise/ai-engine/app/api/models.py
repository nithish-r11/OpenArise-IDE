from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict

class ErrorCode(str, Enum):
    PROJECT_NOT_FOUND = "project_not_found"
    INVALID_PROJECT_ROOT = "invalid_project_root"
    PROJECT_STATE_UNAVAILABLE = "project_state_unavailable"
    ENVIRONMENT_UNAVAILABLE = "environment_unavailable"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    PERMISSION_REQUIRED = "permission_required"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    INTERNAL_ERROR = "internal_error"

class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

class ErrorResponse(BaseModel):
    success: bool = False
    code: ErrorCode
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
