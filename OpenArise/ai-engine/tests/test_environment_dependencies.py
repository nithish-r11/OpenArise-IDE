from app.environment.dependencies import DependencyInspector
from app.environment.models import EnvironmentInfo, InspectionScope, DependencyState, InstallationAction
from app.project.models import ProjectState, ProjectInfo, DependencyInfo

def test_dependency_inspector_not_available():
    inspector = DependencyInspector()
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test"),
        dependencies=[DependencyInfo(name="pytest", source_file="req.txt")]
    )
    env_info = EnvironmentInfo(inspection_scope=InspectionScope.PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED)
    
    deps = inspector.inspect(state, env_info)
    assert len(deps) == 1
    assert deps[0].status == DependencyState.INSPECTION_NOT_AVAILABLE
    
def test_dependency_inspector_current_env():
    inspector = DependencyInspector()
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test"),
        dependencies=[
            DependencyInfo(name="pydantic", source_file="req.txt", version_specifier="==2.0.0"),
            DependencyInfo(name="nonexistent_pkg_123", source_file="req.txt")
        ]
    )
    env_info = EnvironmentInfo(inspection_scope=InspectionScope.CURRENT_ENVIRONMENT)
    
    deps = inspector.inspect(state, env_info)
    assert len(deps) == 2
    
    pydantic_dep = next(d for d in deps if d.name == "pydantic")
    missing_dep = next(d for d in deps if d.name == "nonexistent_pkg_123")
    
    assert pydantic_dep.status in [DependencyState.INSTALLED, DependencyState.VERSION_MISMATCH]
    assert missing_dep.status == DependencyState.MISSING
    assert missing_dep.action == InstallationAction.INSTALL_REQUIRED
