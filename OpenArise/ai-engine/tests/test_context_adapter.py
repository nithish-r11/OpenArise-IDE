import tempfile
from app.api.services import ProjectWorkspaceService
from app.context.adapter import ProjectIntelligenceContextAdapter

def test_context_adapter():
    with tempfile.TemporaryDirectory() as temp_dir:
        svc = ProjectWorkspaceService(temp_dir)
        adapter = ProjectIntelligenceContextAdapter(svc)
        
        ctx = adapter.build_bounded_context()
        assert "intelligence_summary" in ctx
        assert "project_name" in ctx["intelligence_summary"]
        # Make sure secrets are not dumped (bounded context checks)
        assert "files" not in ctx["intelligence_summary"] 
