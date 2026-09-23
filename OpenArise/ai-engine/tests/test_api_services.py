import os
import tempfile
import pytest
from app.api.services import ProjectWorkspaceService
from app.api.models import ApiError, ErrorCode

def test_service_invalid_root():
    with pytest.raises(ApiError) as exc:
        ProjectWorkspaceService("/invalid/nonexistent/path")
    assert exc.value.code == ErrorCode.INVALID_PROJECT_ROOT
        
def test_service_read_operations():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a dummy file to scan
        with open(os.path.join(temp_dir, "test.py"), "w") as f:
            f.write("def foo(): pass")
            
        svc = ProjectWorkspaceService(temp_dir)
        
        # Test reads
        info = svc.get_project_information()
        assert info.success
        assert info.data["name"] == os.path.basename(temp_dir)
        
        state = svc.get_project_state()
        assert state.success
        assert len(state.data["files"]) > 0
        
        blueprint = svc.get_blueprint()
        assert blueprint.success
        
        # Timeline
        timeline = svc.get_timeline()
        assert timeline.success
        assert isinstance(timeline.data, list)
        
def test_action_unsupported_without_orchestrator():
    with tempfile.TemporaryDirectory() as temp_dir:
        svc = ProjectWorkspaceService(temp_dir)
        with pytest.raises(ApiError) as exc:
            svc.request_agent_execution("Do something")
        assert exc.value.code == ErrorCode.UNSUPPORTED_OPERATION
