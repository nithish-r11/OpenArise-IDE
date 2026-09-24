from app.intelligence.service import IntelligenceService
from app.intelligence.models import TimelineEvent, TimelineEventType, RequirementBaseline
from app.project.models import ProjectState, ProjectInfo
from app.blueprint.models import ProjectBlueprint

def test_intelligence_service_facade():
    service = IntelligenceService()
    
    # Timeline facade
    service.record_event(TimelineEvent(event_type=TimelineEventType.PROJECT_CREATED, title="Title", description="Desc"))
    assert len(service.get_timeline()) == 1
    service.clear_timeline()
    assert len(service.get_timeline()) == 0
    
    # Aggregator facade
    state = ProjectState(project_info=ProjectInfo(root_path="/", name="test"))
    blueprint = ProjectBlueprint(project_id="p1", project_name="p1")
    snapshot = service.build_snapshot(state, blueprint)
    assert snapshot.project_name == "test"
    
    # Drift facade
    baseline = RequirementBaseline(requirement_id="req_1")
    from app.traceability.graph import TraceabilityGraphManager
    finding = service.detect_drift(baseline, state, blueprint, TraceabilityGraphManager("p1"))
    # req_1 is not in blueprint, so structural drift
    assert finding.state.value == "CONFIRMED_STRUCTURAL_DRIFT"
