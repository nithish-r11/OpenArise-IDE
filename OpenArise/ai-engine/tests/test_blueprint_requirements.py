from app.blueprint.requirements import RequirementManager
from app.models.schemas import RequirementLifecycleStatus

def test_requirement_manager_crud():
    manager = RequirementManager()
    
    req = manager.create_requirement("Login", "Allow users to login")
    assert req is not None
    assert req.title == "Login"
    
    # Duplicate detection (case/space insensitive)
    dup = manager.create_requirement(" login  ", "Allow users to login")
    assert dup is None
    
    # Get
    fetched = manager.get_requirement(req.requirement_id)
    assert fetched == req
    
    # Update
    manager.update_requirement(req.requirement_id, title="User Login", acceptance_criteria=["Must have password"])
    assert req.title == "User Login"
    assert "Must have password" in req.acceptance_criteria
    
    # Status
    manager.mark_status(req.requirement_id, RequirementLifecycleStatus.IN_PROGRESS)
    assert req.lifecycle_status == RequirementLifecycleStatus.IN_PROGRESS
    
    # Associate
    manager.associate_feature(req.requirement_id, "feat-1")
    assert "feat-1" in req.implementation_references
