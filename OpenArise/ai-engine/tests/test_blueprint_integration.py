from app.blueprint.manager import BlueprintManager
from app.blueprint.requirements import RequirementManager
from app.project.models import ProjectState, ProjectInfo

def test_blueprint_integration():
    req_manager = RequirementManager()
    manager = BlueprintManager(req_manager)
    
    state = ProjectState(
        project_info=ProjectInfo(root_path="/test", name="test_proj"),
        health_signals={"no_tests": True}
    )
    
    bp = manager.generate_initial_blueprint(state, "Build a web server")
    
    # Assert project state integration without mutation
    assert bp.project_name == "test_proj"
    assert bp.source_request == "Build a web server"
    assert "Project lacks tests" in bp.description
    
    # Assert state is unmutated
    assert state.health_signals["no_tests"] is True
