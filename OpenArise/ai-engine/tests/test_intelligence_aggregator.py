from app.intelligence.aggregator import ProjectIntelligenceAggregator
from app.project.models import ProjectState, ProjectInfo
from app.blueprint.models import ProjectBlueprint
from app.environment.models import ProjectHealthReport, EnvironmentInfo, Severity, HealthCheck

def test_project_intelligence_aggregator():
    aggregator = ProjectIntelligenceAggregator()
    
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test_proj"),
    )
    
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="test_proj", requirements=["r1"]
    )
    
    health = ProjectHealthReport(
        project_id="p1",
        environment=EnvironmentInfo(python_available=True),
        checks=[HealthCheck(name="test", status="ok", severity=Severity.INFO, message="ok")]
    )
    
    snapshot = aggregator.build_snapshot(state, blueprint, None, health)
    
    assert snapshot.project_name == "test_proj"
    assert snapshot.blueprint_summary["requirements"] == 1
    assert snapshot.environment_summary["python_available"] is True
    assert snapshot.health_summary["total_checks"] == 1
    assert snapshot.health_summary["blocked"] == 0
