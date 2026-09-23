from app.intelligence.drift import RequirementDriftDetector
from app.intelligence.models import RequirementBaseline, DriftState
from app.project.models import ProjectState, ProjectInfo, FileInfo
from app.blueprint.models import ProjectBlueprint, TaskItem

def test_drift_detector_no_drift():
    detector = RequirementDriftDetector()
    
    baseline = RequirementBaseline(
        requirement_id="req_1",
        associated_task_ids=["task_1"]
    )
    
    state = ProjectState(project_info=ProjectInfo(root_path="/", name="test"))
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=["req_1"],
        tasks=[TaskItem(task_id="task_1", feature_id="f1", title="t", description="d")]
    )
    
    # We need a dummy traceability graph that won't fail the loop. Since implementation_ids is empty, it skips.
    class DummyGraphManager:
        class DummyGraph:
            nodes = []
            links = []
        graph = DummyGraph()
        
    traceability = DummyGraphManager()
    
    finding = detector.detect_drift(baseline, state, blueprint, traceability)
    assert finding.state == DriftState.NO_DRIFT
    
def test_drift_detector_structural_drift():
    detector = RequirementDriftDetector()
    
    baseline = RequirementBaseline(
        requirement_id="req_1",
        associated_task_ids=["task_1", "task_2"]
    )
    
    state = ProjectState(project_info=ProjectInfo(root_path="/", name="test"))
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=["req_1"],
        tasks=[TaskItem(task_id="task_1", feature_id="f1", title="t", description="d")] # task_2 is missing
    )
    
    class DummyGraphManager:
        class DummyGraph:
            nodes = []
        graph = DummyGraph()
        
    finding = detector.detect_drift(baseline, state, blueprint, DummyGraphManager())
    assert finding.state == DriftState.CONFIRMED_STRUCTURAL_DRIFT
    assert "task_2" in finding.reason
    
def test_drift_detector_hash_drift():
    detector = RequirementDriftDetector()
    
    baseline = RequirementBaseline(
        requirement_id="req_1",
        content_hash="hash_1",
        implementation_ids=["impl_1"]
    )
    
    # File hash changed to hash_2
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test"),
        files=[FileInfo(relative_path="app/test.py", file_type="py", size=10, modified_at=0, content_hash="hash_2")]
    )
    
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=["req_1"]
    )
    
    class DummyGraphManager:
        class DummyGraph:
            class DummyNode:
                node_id = "impl_1"
                file_path = "app/test.py"
            nodes = [DummyNode()]
        graph = DummyGraph()
        
    finding = detector.detect_drift(baseline, state, blueprint, DummyGraphManager())
    # Factual mapping remains, but hash differs.
    assert finding.state == DriftState.POTENTIAL_DRIFT
    assert finding.related_implementations == ["impl_1"]
