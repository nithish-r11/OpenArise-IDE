from app.traceability.graph import TraceabilityGraphManager
from app.traceability.validator import TraceabilityValidator
from app.traceability.models import LinkType

def test_traceability_validator():
    manager = TraceabilityGraphManager("p1")
    manager.add_requirement("r1")
    manager.add_feature("f1")
    manager.add_task("t1")
    manager.add_link("r1", "f1", LinkType.REQUIREMENT_TO_FEATURE)
    manager.add_link("f1", "t1", LinkType.FEATURE_TO_TASK)
    
    validator = TraceabilityValidator()
    valid, errors = validator.validate(manager.graph)
    assert valid
    assert len(errors) == 0

def test_traceability_validator_orphans():
    manager = TraceabilityGraphManager("p1")
    manager.add_requirement("r1") # no feature link
    manager.add_feature("f1") # no req link
    
    validator = TraceabilityValidator()
    valid, errors = validator.validate(manager.graph)
    assert not valid
    assert any("Requirement r1 has no feature mapping (Orphan)" in e for e in errors)
    assert any("Feature f1 has no requirement mapping (Orphan)" in e for e in errors)

def test_traceability_validator_invalid_links():
    manager = TraceabilityGraphManager("p1")
    manager.add_link("unknown_req", "unknown_feat", LinkType.REQUIREMENT_TO_FEATURE)
    
    validator = TraceabilityValidator()
    valid, errors = validator.validate(manager.graph)
    assert not valid
    assert any("references unknown requirement unknown_req" in e for e in errors)
