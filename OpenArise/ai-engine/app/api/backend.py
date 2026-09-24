"""Framework-independent envelopes and synchronous dispatch; no transport listener."""
import inspect
import json
import logging
import uuid
from threading import RLock
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.api.models import ApiError, ErrorCode, ErrorResponse
from app.models.schemas import ActionState, AgentEvent

logger = logging.getLogger(__name__)


class BackendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    method: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class BackendResponse(BaseModel):
    request_id: str
    success: bool
    action_state: Optional[ActionState] = None
    data: Any = None
    error: Optional[ErrorResponse] = None
    events: list[AgentEvent] = Field(default_factory=list)


class BackendService:
    """Serializes one workspace's calls and retains command responses for safe replay."""

    METHODS = frozenset({
        "get_project_information", "get_project_state", "get_blueprint", "get_requirements",
        "get_traceability_graph", "get_environment_status", "get_health_report",
        "get_intelligence_snapshot", "get_timeline", "get_drift_report",
        "refresh_workspace", "create_requirement_baseline", "request_agent_execution",
        "get_agent_execution", "get_evidence", "get_agent_events",
        "approve_agent_action", "resume_agent_execution", "deny_agent_action",
        "cancel_agent_execution", "shutdown",
    })

    def __init__(self, workspace):
        self.workspace = workspace
        self._lock = RLock()
        self._closed = False
        self._requests = {}
        self._responses = {}

    @staticmethod
    def _error(request_id, code, message):
        return BackendResponse(
            request_id=request_id, success=False,
            error=ErrorResponse(code=code, message=message),
        )

    def dispatch(self, request: BackendRequest | dict) -> BackendResponse:
        try:
            request = BackendRequest.model_validate(request)
        except (ValidationError, TypeError, ValueError):
            request_id = request.get("request_id") if isinstance(request, dict) else None
            return self._error(request_id if isinstance(request_id, str) else "invalid",
                               ErrorCode.INVALID_REQUEST, "Invalid backend request envelope.")
        with self._lock:
            try:
                fingerprint = request.model_dump(mode="json")
                json.dumps(fingerprint, allow_nan=False)
            except (ValueError, TypeError):
                return self._error(request.request_id, ErrorCode.INVALID_REQUEST, "Parameters must be JSON values.")
            if request.request_id in self._requests:
                if self._requests[request.request_id] != fingerprint:
                    return self._error(request.request_id, ErrorCode.ACTION_CONFLICT,
                                       "Command ID was already used for different input.")
                return self._responses[request.request_id].model_copy(deep=True)
            if self._closed:
                return self._error(request.request_id, ErrorCode.SERVICE_CLOSED, "Backend service is closed.")
            if request.method not in self.METHODS:
                return self._error(request.request_id, ErrorCode.UNSUPPORTED_OPERATION, "Unsupported backend method.")
            params = dict(request.params)
            if request.method == "request_agent_execution":
                if "request_id" in params and params["request_id"] != request.request_id:
                    return self._error(request.request_id, ErrorCode.INVALID_REQUEST,
                                       "Starting an agent action uses the envelope request ID.")
                params["request_id"] = request.request_id
            method = getattr(self.workspace, request.method)
            try:
                inspect.signature(method).bind(**params)
            except TypeError:
                return self._error(request.request_id, ErrorCode.INVALID_REQUEST, "Invalid method parameters.")
            try:
                result = method(**params)
                data = result.data
                state = ActionState.COMPLETED
                events = []
                if isinstance(data, dict) and "action_state" in data:
                    state = ActionState(data["action_state"])
                    events = [AgentEvent.model_validate(event) for event in data.get("data", {}).get("events", [])]
                response = BackendResponse(
                    request_id=request.request_id, success=True, action_state=state, data=data, events=events
                )
                if request.method == "shutdown":
                    self._closed = True
            except ApiError as exc:
                response = self._error(request.request_id, exc.code, exc.message)
            except Exception:
                logger.exception("Backend dispatch failed.")
                response = self._error(request.request_id, ErrorCode.INTERNAL_ERROR,
                                       "Backend operation failed. Consult backend logs.")
            self._requests[request.request_id] = fingerprint
            self._responses[request.request_id] = response.model_copy(deep=True)
            return response
