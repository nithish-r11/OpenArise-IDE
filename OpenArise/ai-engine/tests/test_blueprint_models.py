import json
from app.blueprint.models import ProjectBlueprint, FeatureItem, TaskItem, BlueprintStatus
from app.models.schemas import Requirement, RequirementLifecycleStatus, VerificationStatus

def test_requirement_backward_compatibility():
    # Ensure Person 1 defaults are preserved
    req = Requirement(description="Test")
    assert req.status == VerificationStatus.PENDING
    assert req.lifecycle_status == RequirementLifecycleStatus.PENDING
    assert req.title == "Untitled Requirement"

def test_blueprint_serialization():
    task = TaskItem(feature_id="f1", title="Task 1", description="Desc")
    feature = FeatureItem(requirement_ids=["r1"], title="Feat 1", description="Desc")
    blueprint = ProjectBlueprint(project_id="p1", project_name="Proj", requirements=["r1"], features=[feature], tasks=[task])
    
    data = blueprint.model_dump()
    assert data["project_id"] == "p1"
    
    # deserialize
    blueprint_copy = ProjectBlueprint(**data)
    assert blueprint_copy.features[0].feature_id == feature.feature_id
