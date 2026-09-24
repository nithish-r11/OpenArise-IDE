from enum import Enum

class AgentState(str, Enum):
    """Strongly typed states for the agent."""
    IDLE = "IDLE"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"


class AgentLifecycleError(ValueError):
    """Framework-independent request/continuation error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
