from app.intelligence.drift import RequirementDriftDetector
from app.intelligence.models import RequirementBaseline, DriftState
from app.project.models import ProjectState, ProjectInfo, FileInfo
from app.blueprint.models import ProjectBlueprint, TaskItem, FeatureItem
from app.traceability.graph import TraceabilityGraphManager
from app.traceability.models import ImplementationNode, LinkType


def production_graph():
    graph = TraceabilityGraphManager("p1")
    graph.add_requirement("req_1")
    graph.add_feature("f1")
    graph.add_task("task_1")
    graph.add_link("req_1", "f1", LinkType.REQUIREMENT_TO_FEATURE)
    graph.add_link("f1", "task_1", LinkType.FEATURE_TO_TASK)
    return graph


def test_drift_detector_no_drift():
    baseline = RequirementBaseline(requirement_id="req_1", associated_task_ids=["task_1"])
    state = ProjectState(project_info=ProjectInfo(root_path="/", name="test"))
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="p1", requirements=["req_1"],
        features=[FeatureItem(feature_id="f1", requirement_ids=["req_1"], title="f", description="d")],
        tasks=[TaskItem(task_id="task_1", feature_id="f1", title="t", description="d")],
    )
    finding = RequirementDriftDetector().detect_drift(baseline, state, blueprint, production_graph())
    assert finding.state == DriftState.NO_DRIFT


def test_drift_detector_structural_drift():
    baseline = RequirementBaseline(requirement_id="req_1", associated_task_ids=["task_1", "task_2"])
    state = ProjectState(project_info=ProjectInfo(root_path="/", name="test"))
    blueprint = ProjectBlueprint(
        project_id="p1", project_name="p1", requirements=["req_1"],
        tasks=[TaskItem(task_id="task_1", feature_id="f1", title="t", description="d")],
    )
    finding = RequirementDriftDetector().detect_drift(baseline, state, blueprint, production_graph())
    assert finding.state == DriftState.CONFIRMED_STRUCTURAL_DRIFT
    assert "task_2" in finding.reason


def test_drift_detector_hash_drift():
    baseline = RequirementBaseline(requirement_id="req_1", content_hash="hash_1", implementation_ids=["impl_1"])
    state = ProjectState(
        project_info=ProjectInfo(root_path="/", name="test"),
        files=[FileInfo(relative_path="app/test.py", file_type="py", size=10, modified_at=0, content_hash="hash_2")],
    )
    blueprint = ProjectBlueprint(project_id="p1", project_name="p1", requirements=["req_1"])
    graph = production_graph()
    graph.add_implementation(ImplementationNode(implementation_id="impl_1", file_path="app/test.py"))
    graph.add_link("req_1", "impl_1", LinkType.REQUIREMENT_TO_IMPLEMENTATION)
    finding = RequirementDriftDetector().detect_drift(baseline, state, blueprint, graph)
    assert finding.state == DriftState.POTENTIAL_DRIFT
    assert finding.related_implementations == ["impl_1"]
