from app.blueprint.manager import BlueprintManager
from app.blueprint.requirements import RequirementManager
from app.blueprint.models import ProjectBlueprint, FeatureItem, TaskItem
from app.project.models import ProjectState, ProjectInfo

def test_blueprint_traceability():
    req_manager = RequirementManager()
    req = req_manager.create_requirement("Req 1", "Desc")
    manager = BlueprintManager(req_manager)
    
    # Valid blueprint
    task1 = TaskItem(task_id="t1", feature_id="f1", title="T1", description="D1")
    task2 = TaskItem(task_id="t2", feature_id="f1", title="T2", description="D2", dependencies=["t1"])
    feature = FeatureItem(feature_id="f1", requirement_ids=[req.requirement_id], title="F1", description="D1")
    
    bp = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=[req.requirement_id], features=[feature], tasks=[task1, task2]
    )
    
    valid, errors = manager.validate_traceability(bp)
    assert valid
    assert len(errors) == 0

def test_blueprint_circular_dependency():
    req_manager = RequirementManager()
    manager = BlueprintManager(req_manager)
    
    task1 = TaskItem(task_id="t1", feature_id="f1", title="T1", description="D1", dependencies=["t2"])
    task2 = TaskItem(task_id="t2", feature_id="f1", title="T2", description="D2", dependencies=["t1"])
    feature = FeatureItem(feature_id="f1", requirement_ids=["r1"], title="F1", description="D1")
    
    bp = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=["r1"], features=[feature], tasks=[task1, task2]
    )
    
    valid, errors = manager.validate_traceability(bp)
    assert not valid
    assert any("Circular dependency" in e for e in errors)

def test_blueprint_orphans():
    req_manager = RequirementManager()
    manager = BlueprintManager(req_manager)
    
    task = TaskItem(task_id="t1", feature_id="unknown_f", title="T1", description="D")
    feature = FeatureItem(feature_id="f1", requirement_ids=["unknown_r"], title="F1", description="D")
    
    bp = ProjectBlueprint(
        project_id="p1", project_name="p1", 
        requirements=["r1"], features=[feature], tasks=[task]
    )
    
    valid, errors = manager.validate_traceability(bp)
    assert not valid
    assert any("references unknown requirement" in e for e in errors)
    assert any("references unknown feature" in e for e in errors)
