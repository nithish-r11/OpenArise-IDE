import os
import logging
from typing import Optional, List
from app.project.state import ProjectStateManager
from app.blueprint.requirements import RequirementManager
from app.blueprint.manager import BlueprintManager
from app.traceability.graph import TraceabilityGraphManager
from app.traceability.mapper import ImplementationMapper
from app.environment.manager import EnvironmentManager
from app.intelligence.service import IntelligenceService
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentRequest, AgentResponse
from app.api.models import ApiError, ErrorCode, SuccessResponse

logger = logging.getLogger(__name__)

class ProjectWorkspaceService:
    """Facade for the Person 3 Desktop UI. Provides strictly read-only intelligence endpoints
    and delegates mutating actions to the Person 1 AgentOrchestrator."""
    
    def __init__(self, project_root: str, orchestrator: Optional[AgentOrchestrator] = None):
        self._validate_root(project_root)
        self.project_root = project_root
        
        # Subsystems
        self.state_manager = ProjectStateManager(project_root)
        self.req_manager = RequirementManager()
        self.blueprint_manager = BlueprintManager(self.req_manager)
        self.current_blueprint = None
        self.traceability_graph = TraceabilityGraphManager(project_id="default")
        self.traceability_mapper = ImplementationMapper(project_id="default")
        self.environment_manager = EnvironmentManager()
        self.intelligence_service = IntelligenceService()
        
        # Action Orchestrator
        self.orchestrator = orchestrator
        
        # Load initial state
        self._refresh_state()
        
    def _validate_root(self, project_root: str):
        if not os.path.exists(project_root) or not os.path.isdir(project_root):
            raise ApiError(ErrorCode.INVALID_PROJECT_ROOT, "Provided project root does not exist or is not a directory.")
            
    def _refresh_state(self):
        """Internal helper to load state without mutating the project itself."""
        try:
            # Phase 1: State
            self.state_manager.refresh()
        except Exception as e:
            logger.error(f"Error refreshing state: {e}")
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Failed to parse project state.", details={"error": str(e)})

    # ==========================================
    # READ OPERATIONS (Side-effect free)
    # ==========================================
    
    def get_project_information(self) -> SuccessResponse:
        state = self.state_manager.state
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
        return SuccessResponse(data=state.project_info.model_dump())
        
    def get_project_state(self) -> SuccessResponse:
        state = self.state_manager.state
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
        return SuccessResponse(data=state.model_dump())
        
    def get_blueprint(self) -> SuccessResponse:
        if not self.current_blueprint:
            state = self.state_manager.state
            if state:
                self.current_blueprint = self.blueprint_manager.generate_initial_blueprint(state, "Initial load")
        
        if not self.current_blueprint:
            return SuccessResponse(data=None)
        return SuccessResponse(data=self.current_blueprint.model_dump())
        
    def get_requirements(self) -> SuccessResponse:
        reqs = self.req_manager.list_requirements()
        return SuccessResponse(data=[r.model_dump() for r in reqs])
        
    def get_traceability_graph(self) -> SuccessResponse:
        return SuccessResponse(data={
            "requirements": self.traceability_graph.graph.requirements,
            "features": self.traceability_graph.graph.features,
            "tasks": self.traceability_graph.graph.tasks,
            "implementations": [n.model_dump() for n in self.traceability_graph.graph.implementations],
            "tests": [n.model_dump() for n in self.traceability_graph.graph.tests],
            "evidence": self.traceability_graph.graph.evidence,
            "links": [l.model_dump() for l in self.traceability_graph.graph.links]
        })
        
    def get_environment_status(self) -> SuccessResponse:
        state = self.state_manager.state
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
            
        blueprint = self.current_blueprint
        report = self.environment_manager.evaluate_project(self.project_root, state, blueprint)
        return SuccessResponse(data=report.environment.model_dump())
        
    def get_health_report(self) -> SuccessResponse:
        state = self.state_manager.state
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
            
        blueprint = self.current_blueprint
        report = self.environment_manager.evaluate_project(self.project_root, state, blueprint)
        return SuccessResponse(data=report.model_dump())
        
    def get_intelligence_snapshot(self) -> SuccessResponse:
        state = self.state_manager.state
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
            
        blueprint = self.current_blueprint
        health = self.environment_manager.evaluate_project(self.project_root, state, blueprint)
        
        snapshot = self.intelligence_service.build_snapshot(
            state=state,
            blueprint=blueprint,
            traceability=self.traceability_graph,
            health=health
        )
        return SuccessResponse(data=snapshot.model_dump())
        
    def get_timeline(self) -> SuccessResponse:
        return SuccessResponse(data=[e.model_dump() for e in self.intelligence_service.get_timeline()])
        
    def get_drift_report(self, baseline_dict: dict) -> SuccessResponse:
        from app.intelligence.models import RequirementBaseline
        try:
            baseline = RequirementBaseline(**baseline_dict)
        except Exception:
            raise ApiError(ErrorCode.UNSUPPORTED_OPERATION, "Invalid baseline format provided.")
            
        state = self.state_manager.get_current_state()
        if not state:
            raise ApiError(ErrorCode.PROJECT_STATE_UNAVAILABLE, "Project state is not available.")
            
        blueprint = self.current_blueprint
        finding = self.intelligence_service.detect_drift(baseline, state, blueprint, self.traceability_graph)
        return SuccessResponse(data=finding.model_dump())

    # ==========================================
    # ACTION OPERATIONS (Mutating, delegated)
    # ==========================================
    
    def request_agent_execution(self, prompt: str, context_data: Optional[dict] = None) -> SuccessResponse:
        """Delegates agent execution strictly to the AgentOrchestrator."""
        if not self.orchestrator:
            raise ApiError(ErrorCode.UNSUPPORTED_OPERATION, "AgentOrchestrator is not configured for this workspace.")
            
        # We will import the adapter dynamically to avoid circular dependencies
        from app.context.adapter import ProjectIntelligenceContextAdapter
        adapter = ProjectIntelligenceContextAdapter(self)
        bounded_context = adapter.build_bounded_context()
        
        merged_context = bounded_context
        if context_data:
            merged_context.update(context_data)
            
        req = AgentRequest(prompt=prompt, context_data=merged_context)
        
        try:
            res: AgentResponse = self.orchestrator.process_request(req)
            # Re-read state in case orchestrator changed anything
            self._refresh_state()
            return SuccessResponse(data=res.model_dump())
        except Exception as e:
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Agent execution failed.", details={"error": str(e)})
