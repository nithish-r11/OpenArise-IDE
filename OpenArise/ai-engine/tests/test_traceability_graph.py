from app.traceability.graph import TraceabilityGraphManager
from app.traceability.models import LinkType, ImplementationNode

def test_traceability_graph_manager():
    manager = TraceabilityGraphManager("p1")
    manager.add_requirement("r1")
    manager.add_feature("f1")
    manager.add_task("t1")
    
    node = ImplementationNode(file_path="a.py")
    manager.add_implementation(node)
    
    manager.add_link("r1", "f1", LinkType.REQUIREMENT_TO_FEATURE, evidence_backed=False)
    
    assert "r1" in manager.graph.requirements
    assert len(manager.get_links(source_id="r1")) == 1
    
    link = manager.get_links(source_id="r1")[0]
    assert link.target_id == "f1"
    assert link.link_type == LinkType.REQUIREMENT_TO_FEATURE
    assert link.evidence_backed is False
