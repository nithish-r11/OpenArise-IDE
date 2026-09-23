from app.environment.health import HealthEngine
from app.environment.models import EnvironmentInfo, DependencyStatus, DependencyState, Severity
from app.project.models import ProjectState, ProjectInfo

def test_health_engine():
    engine = HealthEngine()
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test"),
        health_signals={"no_tests": True}
    )
    env_info = EnvironmentInfo(python_available=False)
    deps = [
        DependencyStatus(name="flask", status=DependencyState.MISSING)
    ]
    
    report = engine.evaluate(state, None, env_info, deps)
    
    # Python missing is BLOCKED
    assert any(c.severity == Severity.BLOCKED and c.name == "Python Environment" for c in report.checks)
    
    # Missing dep is ERROR
    assert any(c.severity == Severity.ERROR and "flask" in c.name for c in report.checks)
    
    # No tests is WARNING
    assert any(c.severity == Severity.WARNING and c.name == "Test Suite" for c in report.checks)
