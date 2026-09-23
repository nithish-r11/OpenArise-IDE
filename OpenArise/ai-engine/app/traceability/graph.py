from typing import Dict, List, Optional
from app.traceability.models import TraceabilityGraph, TraceabilityLink, ImplementationNode, TestNode, LinkType

class TraceabilityGraphManager:
    """Manages construction and queries of the traceability graph."""
    
    def __init__(self, project_id: str):
        self.graph = TraceabilityGraph(project_id=project_id)
        
    def add_requirement(self, req_id: str):
        if req_id not in self.graph.requirements:
            self.graph.requirements.append(req_id)
            
    def add_feature(self, feature_id: str):
        if feature_id not in self.graph.features:
            self.graph.features.append(feature_id)
            
    def add_task(self, task_id: str):
        if task_id not in self.graph.tasks:
            self.graph.tasks.append(task_id)
            
    def add_implementation(self, node: ImplementationNode):
        self.graph.implementations.append(node)
        
    def add_test(self, node: TestNode):
        self.graph.tests.append(node)
        
    def add_evidence_ref(self, evidence_id: str):
        if evidence_id not in self.graph.evidence:
            self.graph.evidence.append(evidence_id)
            
    def add_link(self, source_id: str, target_id: str, link_type: LinkType, evidence_backed: bool = False, is_inferred: bool = False):
        link = TraceabilityLink(
            source_id=source_id,
            target_id=target_id,
            link_type=link_type,
            evidence_backed=evidence_backed,
            is_inferred=is_inferred
        )
        self.graph.links.append(link)

    def get_links(self, source_id: Optional[str] = None, target_id: Optional[str] = None, link_type: Optional[LinkType] = None) -> List[TraceabilityLink]:
        results = self.graph.links
        if source_id:
            results = [l for l in results if l.source_id == source_id]
        if target_id:
            results = [l for l in results if l.target_id == target_id]
        if link_type:
            results = [l for l in results if l.link_type == link_type]
        return results
