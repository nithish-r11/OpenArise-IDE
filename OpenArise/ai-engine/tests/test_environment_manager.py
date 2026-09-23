import tempfile
from app.environment.manager import EnvironmentManager
from app.project.models import ProjectState, ProjectInfo

def test_environment_manager():
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = EnvironmentManager()
        state = ProjectState(
            project_info=ProjectInfo(root_path=temp_dir, name="test")
        )
        
        report = manager.evaluate_project(temp_dir, state)
        assert report.environment.python_available
        assert len(report.checks) > 0
