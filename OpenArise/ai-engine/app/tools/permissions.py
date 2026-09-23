from enum import Enum
from typing import Dict, Optional

class RiskLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"

class PermissionAction(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ASK = "ASK"

class PermissionManager:
    """Manages permissions for tool execution."""
    
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self._approvals: Dict[str, bool] = {}  # tool_call_id -> bool
        
    def get_action_for_risk(self, risk: RiskLevel) -> PermissionAction:
        if self.test_mode:
            return PermissionAction.ALLOW
            
        if risk == RiskLevel.READ:
            return PermissionAction.ALLOW
        else:
            return PermissionAction.ASK
            
    def grant_approval(self, tool_call_id: str):
        self._approvals[tool_call_id] = True
        
    def check_permission(self, tool_call_id: str, risk: RiskLevel) -> bool:
        """Returns True if execution is allowed, False if permission is denied or required."""
        action = self.get_action_for_risk(risk)
        
        if action == PermissionAction.ALLOW:
            return True
        elif action == PermissionAction.DENY:
            return False
        elif action == PermissionAction.ASK:
            return self._approvals.get(tool_call_id, False)
            
        return False
