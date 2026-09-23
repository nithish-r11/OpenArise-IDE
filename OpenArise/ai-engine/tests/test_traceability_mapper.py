from app.traceability.mapper import ImplementationMapper
from app.project.models import ProjectState, ProjectInfo, PythonModuleInfo
from app.blueprint.models import ProjectBlueprint, FeatureItem, TaskItem
from app.traceability.models import LinkType

def test_implementation_mapper():
    state = ProjectState(
        project_info=ProjectInfo(root_path="/test", name="test_proj"),
        python_modules=[
            PythonModuleInfo(relative_path="app/auth.py", module_name="auth"),
            PythonModuleInfo(relative_path="tests/test_auth.py", module_name="test_auth")
        ]
    )
    
    bp = ProjectBlueprint(
        project_id="p1", project_name="p1", requirements=["r1"],
        features=[FeatureItem(feature_id="f1", requirement_ids=["r1"], title="f", description="d")],
        tasks=[TaskItem(task_id="t1", feature_id="f1", title="t", description="d")]
    )
    
    mapper = ImplementationMapper("p1")
    graph = mapper.build_from_state_and_blueprint(state, bp)
    
    assert "r1" in graph.requirements
    assert "f1" in graph.features
    assert "t1" in graph.tasks
    assert len(graph.implementations) == 1
    assert len(graph.tests) == 1
    
    # Check inferred link between test_auth.py and auth.py
    test_links = [l for l in graph.links if l.link_type == LinkType.IMPLEMENTATION_TO_TEST]
    assert len(test_links) == 1
    assert test_links[0].is_inferred is True
    assert test_links[0].evidence_backed is False
