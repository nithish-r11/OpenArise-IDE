import json
from app.traceability.models import TraceabilityGraph, ImplementationNode, TestNode, LinkType, TraceabilityLink

def test_traceability_serialization():
    node = ImplementationNode(file_path="app/auth.py", module_name="auth", symbol_type="module")
    test_node = TestNode(file_path="tests/test_auth.py", test_name="test_auth")
    
    graph = TraceabilityGraph(
        project_id="p1",
        requirements=["r1"],
        implementations=[node],
        tests=[test_node]
    )
    
    data = graph.model_dump()
    assert data["project_id"] == "p1"
    
    # Deserialization
    graph_copy = TraceabilityGraph(**data)
    assert graph_copy.implementations[0].implementation_id == node.implementation_id
    assert graph_copy.tests[0].test_id == test_node.test_id
