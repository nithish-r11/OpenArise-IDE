import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.project.state import ProjectStateManager
from app.blueprint.requirements import RequirementManager
from app.blueprint.manager import BlueprintManager
from app.traceability.mapper import ImplementationMapper
from app.traceability.models import LinkType
from app.environment.manager import EnvironmentManager
from app.intelligence.service import IntelligenceService
from app.intelligence.models import RequirementBaseline, TimelineEvent, TimelineEventType
from app.agent.orchestrator import AgentOrchestrator
from app.agent.state import AgentLifecycleError
from app.models.schemas import AgentRequest, Requirement
from app.api.models import ApiError, ErrorCode, SuccessResponse

logger = logging.getLogger(__name__)


class ProjectWorkspaceService:
    """Single workspace facade. Observation never writes files or runs project code."""

    def __init__(self, project_root: str, orchestrator: Optional[AgentOrchestrator] = None):
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise ApiError(ErrorCode.INVALID_PROJECT_ROOT, "Project root is not an existing directory.")
        self.project_root = str(root)
        if orchestrator and Path(orchestrator.project_root) != root:
            raise ApiError(ErrorCode.INVALID_PROJECT_ROOT, "Agent and workspace roots must match.")
        project_id = str(uuid.uuid5(uuid.NAMESPACE_URL, root.as_uri()))
        self.state_manager = ProjectStateManager(self.project_root, project_id=project_id)
        self.req_manager = RequirementManager()
        self.blueprint_manager = BlueprintManager(self.req_manager)
        self.current_blueprint = None
        self.traceability_mapper = ImplementationMapper(project_id)
        self.traceability_graph = self.traceability_mapper.graph_manager
        self.environment_manager = EnvironmentManager()
        self.intelligence_service = IntelligenceService()
        self.orchestrator = orchestrator
        self._health_report = None
        self._drift_reports = {}
        self._execution_inputs = {}
        self._last_scan = None
        self._closed = False
        self._refresh_state()

    def _ensure_open(self):
        if self._closed:
            raise ApiError(ErrorCode.SERVICE_CLOSED, "Workspace service is closed.")

    def _event(self, kind, title, description, requirements=None):
        self.intelligence_service.record_event(TimelineEvent(
            event_type=kind, title=title, description=description,
            related_project_id=self.state_manager.project_id,
            related_requirement_ids=requirements or [],
        ))

    def _refresh_state(self):
        self._ensure_open()
        try:
            state = self.state_manager.refresh()
            scan = sorted((f.relative_path, f.content_hash, f.size) for f in state.files)
            if scan != self._last_scan:
                self._event(TimelineEventType.PROJECT_SCANNED, "Project scanned", state.scan_timestamp)
                self._last_scan = scan
            if self.current_blueprint is None:
                self.current_blueprint = self.blueprint_manager.generate_initial_blueprint(state, "Initial load")
                self._event(TimelineEventType.BLUEPRINT_CREATED, "Blueprint initialized", "Initial factual scaffold.")
            self.traceability_mapper.build_from_state_and_blueprint(state, self.current_blueprint)
            self._health_report = self.environment_manager.evaluate_project(
                self.project_root, state, self.current_blueprint
            )
            self._drift_reports.clear()
        except ApiError:
            raise
        except Exception:
            logger.exception("Workspace refresh failed.")
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Failed to refresh workspace observations.") from None

    def _state(self):
        self._ensure_open()
        if self.state_manager.state is None:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is unavailable.")
        return self.state_manager.state

    def refresh_workspace(self):
        self._refresh_state()
        return self.get_intelligence_snapshot()

    def get_project_information(self):
        return SuccessResponse(data=self._state().project_info.model_dump(mode="json"))

    def get_project_state(self):
        return SuccessResponse(data=self._state().model_dump(mode="json"))

    def get_blueprint(self):
        self._ensure_open()
        return SuccessResponse(data=self.current_blueprint.model_dump(mode="json"))

    def get_requirements(self):
        self._ensure_open()
        return SuccessResponse(data=[r.model_dump(mode="json") for r in self.req_manager.list_requirements()])

    def get_traceability_graph(self):
        self._ensure_open()
        return SuccessResponse(data=self.traceability_graph.graph.model_dump(mode="json"))

    def get_environment_status(self):
        self._ensure_open()
        if self._health_report is None:
            raise ApiError(ErrorCode.ENVIRONMENT_UNAVAILABLE, "Environment observations are unavailable.")
        return SuccessResponse(data=self._health_report.environment.model_dump(mode="json"))

    def get_health_report(self):
        self._ensure_open()
        if self._health_report is None:
            raise ApiError(ErrorCode.ENVIRONMENT_UNAVAILABLE, "Health observations are unavailable.")
        return SuccessResponse(data=self._health_report.model_dump(mode="json"))

    def get_intelligence_snapshot(self):
        snapshot = self.intelligence_service.build_snapshot(
            self._state(), self.current_blueprint, self.traceability_graph, self._health_report
        )
        requirements = self.req_manager.list_requirements()
        snapshot.requirement_summary = {
            "total": len(requirements),
            "by_verification_status": {
                status: sum(req.status.value == status for req in requirements)
                for status in sorted({req.status.value for req in requirements})
            },
        }
        snapshot.timeline_summary = self.intelligence_service.get_timeline()
        snapshot.drift_summary = list(self._drift_reports.values())
        return SuccessResponse(data=snapshot.model_dump(mode="json"))

    def get_timeline(self):
        self._ensure_open()
        return SuccessResponse(data=[e.model_dump(mode="json") for e in self.intelligence_service.get_timeline()])

    def create_requirement_baseline(self, requirement_id: str):
        self._ensure_open()
        requirement = self.req_manager.get_requirement(requirement_id)
        if requirement is None:
            raise ApiError(ErrorCode.INVALID_REQUEST, "Unknown requirement.")
        graph = self.traceability_graph.graph
        features = [f.feature_id for f in self.current_blueprint.features if requirement_id in f.requirement_ids]
        tasks = [t for t in self.current_blueprint.tasks if t.feature_id in features]
        implementations = sorted({
            link.target_id for link in graph.links
            if (link.link_type == LinkType.REQUIREMENT_TO_IMPLEMENTATION and link.source_id == requirement_id)
            or (link.link_type == LinkType.TASK_TO_IMPLEMENTATION and link.source_id in {t.task_id for t in tasks})
        })
        hashes = {f.relative_path: f.content_hash for f in self._state().files}
        baseline = RequirementBaseline(
            requirement_id=requirement_id, associated_feature_ids=features,
            associated_task_ids=[t.task_id for t in tasks],
            task_feature_ids={t.task_id: t.feature_id for t in tasks},
            implementation_ids=implementations,
            implementation_hashes={n.implementation_id: hashes[n.file_path]
                                   for n in graph.implementations
                                   if n.implementation_id in implementations and hashes.get(n.file_path)},
            evidence_ids=list(requirement.evidence_references),
        )
        return SuccessResponse(data=baseline.model_dump(mode="json"))

    def get_drift_report(self, baseline_dict: dict):
        try:
            baseline = RequirementBaseline.model_validate(baseline_dict)
        except (ValueError, TypeError):
            raise ApiError(ErrorCode.INVALID_REQUEST, "Invalid requirement baseline.") from None
        finding = self.intelligence_service.detect_drift(
            baseline, self._state(), self.current_blueprint, self.traceability_graph
        )
        self._drift_reports[baseline.requirement_id] = finding
        self._event(TimelineEventType.DRIFT_DETECTED, "Drift evaluated",
                    f"{finding.state.value}: {finding.reason}", [baseline.requirement_id])
        return SuccessResponse(data=finding.model_dump(mode="json"))

    def _agent(self):
        self._ensure_open()
        if self.orchestrator is None:
            raise ApiError(ErrorCode.UNSUPPORTED_OPERATION, "AgentOrchestrator is not configured for this workspace.")
        return self.orchestrator

    def _call_agent(self, method, *args):
        try:
            return getattr(self._agent(), method)(*args)
        except AgentLifecycleError as exc:
            raise ApiError(ErrorCode(exc.code), str(exc)) from None
        except ApiError:
            raise
        except Exception:
            logger.exception("Agent service operation failed.")
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Agent service operation failed.") from None

    def _adopt_response(self, response):
        for item in response.data.get("requirements", []):
            requirement = Requirement.model_validate(item)
            is_new = self.req_manager.get_requirement(requirement.requirement_id) is None
            self.req_manager.store_requirement(requirement)
            if requirement.requirement_id not in self.current_blueprint.requirements:
                self.current_blueprint.requirements.append(requirement.requirement_id)
            if is_new:
                self._event(TimelineEventType.REQUIREMENT_CREATED, "Requirement tracked",
                            requirement.title, [requirement.requirement_id])
        self._refresh_state()
        graph = self.traceability_graph
        calls = {call["tool_call_id"]: call for call in response.data.get("tool_calls", [])}
        results = {result["tool_call_id"]: result for result in response.data.get("tool_results", [])}
        for evidence in response.data.get("evidence", []):
            req_id, evidence_id = evidence["requirement_id"], evidence["evidence_id"]
            graph.add_evidence_ref(evidence_id)
            graph.add_link(req_id, evidence_id, LinkType.REQUIREMENT_TO_EVIDENCE, evidence_backed=True)
            call = calls.get(evidence.get("tool_call_id"), {})
            result = results.get(evidence.get("tool_call_id"), {})
            path = call.get("arguments", {}).get("path")
            if result.get("success") and path:
                path = Path(path).as_posix()
                for node in graph.graph.implementations:
                    if node.file_path == path:
                        graph.add_link(req_id, node.implementation_id, LinkType.REQUIREMENT_TO_IMPLEMENTATION)
        self._event(TimelineEventType.AGENT_STATE_CHANGED, "Agent state changed",
                    f"{response.request_id}: {response.action_state.value}",
                    [r["requirement_id"] for r in response.data.get("requirements", [])])
        return SuccessResponse(data=response.model_dump(mode="json"))

    def request_agent_execution(self, prompt: str, context_data: Optional[dict] = None, request_id: Optional[str] = None):
        self._agent()
        if not isinstance(prompt, str) or not prompt.strip() or (context_data is not None and not isinstance(context_data, dict)):
            raise ApiError(ErrorCode.INVALID_REQUEST, "A nonempty prompt and optional context object are required.")
        if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()):
            raise ApiError(ErrorCode.INVALID_REQUEST, "Request ID must be a nonempty string.")
        request_id = request_id or str(uuid.uuid4())
        try:
            fingerprint = hashlib.sha256(json.dumps([prompt, context_data], sort_keys=True).encode()).hexdigest()
        except (ValueError, TypeError):
            raise ApiError(ErrorCode.INVALID_REQUEST, "Context must contain JSON values.") from None
        if request_id in self._execution_inputs:
            if self._execution_inputs[request_id] != fingerprint:
                raise ApiError(ErrorCode.ACTION_CONFLICT, "Request ID was already used for different input.")
            return self.get_agent_execution(request_id)
        from app.context.adapter import ProjectIntelligenceContextAdapter
        merged = dict(context_data or {})
        merged.update(ProjectIntelligenceContextAdapter(self).build_bounded_context())
        response = self._call_agent("process_request", AgentRequest(
            request_id=request_id, prompt=prompt, context_data=merged
        ))
        self._execution_inputs[request_id] = fingerprint
        return self._adopt_response(response)

    def get_agent_execution(self, request_id: str):
        return SuccessResponse(data=self._call_agent("get_request", request_id).model_dump(mode="json"))

    def get_evidence(self, request_id: str):
        return SuccessResponse(data=self._call_agent("get_request", request_id).data["evidence"])

    def get_agent_events(self, request_id: str, after_sequence: int = 0):
        if type(after_sequence) is not int or after_sequence < 0:
            raise ApiError(ErrorCode.INVALID_REQUEST, "Event cursor must be a nonnegative integer.")
        response = self._call_agent("get_request", request_id)
        return SuccessResponse(data=[event for event in response.data["events"]
                                     if event["sequence"] > after_sequence])

    def approve_agent_action(self, request_id: str, tool_call_id: str):
        return self._adopt_response(self._call_agent("approve_action", request_id, tool_call_id))

    def resume_agent_execution(self, request_id: str, tool_call_id: str):
        return self._adopt_response(self._call_agent("resume_request", request_id, tool_call_id))

    def deny_agent_action(self, request_id: str, tool_call_id: str):
        return self._adopt_response(self._call_agent("deny_action", request_id, tool_call_id))

    def cancel_agent_execution(self, request_id: str):
        return self._adopt_response(self._call_agent("cancel_request", request_id))

    def shutdown(self):
        """Close between synchronous operations and cancel retained pending work."""
        if not self._closed:
            for request_id in self._execution_inputs:
                response = self._call_agent("get_request", request_id)
                if response.pending_action is not None:
                    self.cancel_agent_execution(request_id)
            self._closed = True
        return SuccessResponse(data={"closed": True})
