from enum import Enum
from typing import Dict, Optional
import hashlib
import json
from threading import RLock

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
        self._call_approvals = {}
        self._lock = RLock()
        
    def get_action_for_risk(self, risk: RiskLevel) -> PermissionAction:
        if self.test_mode:
            return PermissionAction.ALLOW
            
        if risk == RiskLevel.READ:
            return PermissionAction.ALLOW
        else:
            return PermissionAction.ASK
            
    def grant_approval(self, tool_call_id: str):
        # Used by explicit editor Save/Create operations. Agent calls use the
        # scoped grant below; a bare ID must never authorize an AI action.
        with self._lock:
            self._approvals[tool_call_id] = True

    def revoke_approval(self, tool_call_id: str):
        """Approvals are single-use and must not outlive their action."""
        with self._lock:
            self._approvals.pop(tool_call_id, None)
            self._call_approvals.pop(tool_call_id, None)

    @staticmethod
    def _scope(request_id, call, risk):
        try:
            if risk not in (RiskLevel.READ, RiskLevel.WRITE, RiskLevel.EXECUTE):
                return None
            if not all(isinstance(value, str) and value.strip()
                       for value in (request_id, call.tool_call_id, call.tool_name)):
                return None
            encoded = json.dumps(call.arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)
            return (request_id, call.tool_call_id, call.tool_name, risk,
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest())
        except (AttributeError, ValueError, TypeError):
            return None

    def grant_call_approval(self, request_id, call, risk):
        """Record an explicit decision for one retained request/action/scope."""
        scope = self._scope(request_id, call, risk)
        if scope is None or self.get_action_for_risk(risk) == PermissionAction.DENY:
            raise PermissionError("The action cannot be approved.")
        with self._lock:
            self._call_approvals[call.tool_call_id] = scope

    def check_call_permission(self, request_id, call, risk):
        """Agent WRITE/EXECUTE always need a scoped decision, including tests."""
        scope = self._scope(request_id, call, risk)
        if scope is None or self.get_action_for_risk(risk) == PermissionAction.DENY:
            return False
        if risk == RiskLevel.READ:
            return self.get_action_for_risk(risk) == PermissionAction.ALLOW
        with self._lock:
            return self._call_approvals.get(call.tool_call_id) == scope

    def consume_call_permission(self, request_id, call, risk):
        """Final check immediately before execution; grants cannot be replayed."""
        with self._lock:
            if not self.check_call_permission(request_id, call, risk):
                return False
            self._call_approvals.pop(call.tool_call_id, None)
            return True
        
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
