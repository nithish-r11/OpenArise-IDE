import tempfile
from unittest.mock import MagicMock
from app.api.services import ProjectWorkspaceService
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentAction

def test_e2e_agent_execution_delegation():
    """Prove that ProjectWorkspaceService successfully delegates to Person 1's orchestrator."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock LLM provider to avoid real network call
        mock_llm = MagicMock()
        mock_action = AgentAction(action_type="done", tool_calls=[], rationale="Done")
        mock_llm.generate_structured.return_value = mock_action
        
        # Init Person 1 Orchestrator
        orchestrator = AgentOrchestrator(llm_provider=mock_llm, project_root=temp_dir)
        
        svc = ProjectWorkspaceService(temp_dir, orchestrator=orchestrator)
        
        # Person 3 requests an action
        res = svc.request_agent_execution("Check project health")
        
        assert res.success
        # Check that context adapter successfully injected context
        assert "intelligence_summary" in orchestrator.context.project_state
