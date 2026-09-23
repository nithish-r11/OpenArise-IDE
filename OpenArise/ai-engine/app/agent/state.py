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
