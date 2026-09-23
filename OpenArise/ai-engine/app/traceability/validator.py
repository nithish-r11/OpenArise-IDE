from typing import Dict, List, Set, Tuple
from app.traceability.models import TraceabilityGraph, LinkType

class TraceabilityValidator:
    """Validates the structure of the TraceabilityGraph."""
    
    def validate(self, graph: TraceabilityGraph) -> Tuple[bool, List[str]]:
        errors = []
        
        # Collect sets for fast lookup
        req_ids = set(graph.requirements)
        feat_ids = set(graph.features)
        task_ids = set(graph.tasks)
        impl_ids = {n.implementation_id for n in graph.implementations}
        test_ids = {n.test_id for n in graph.tests}
        evidence_ids = set(graph.evidence)
        
        # Check node uniqueness
        all_ids = set()
        for item_list in (graph.requirements, graph.features, graph.tasks, impl_ids, test_ids, evidence_ids):
            for item_id in item_list:
                if item_id in all_ids:
                    errors.append(f"Duplicate node ID detected: {item_id}")
                all_ids.add(item_id)
                
        # Validate links
        has_req_to_feat = set()
        has_feat_to_task = set()
        has_task_to_impl = set()
        
        for link in graph.links:
            # Check link ends
            if link.link_type == LinkType.REQUIREMENT_TO_FEATURE:
                if link.source_id not in req_ids:
                    errors.append(f"Link {link.link_id} references unknown requirement {link.source_id}")
                if link.target_id not in feat_ids:
                    errors.append(f"Link {link.link_id} references unknown feature {link.target_id}")
                has_req_to_feat.add(link.source_id)
                has_req_to_feat.add(link.target_id)
                    
            elif link.link_type == LinkType.FEATURE_TO_TASK:
                if link.source_id not in feat_ids:
                    errors.append(f"Link {link.link_id} references unknown feature {link.source_id}")
                if link.target_id not in task_ids:
                    errors.append(f"Link {link.link_id} references unknown task {link.target_id}")
                has_feat_to_task.add(link.source_id)
                has_feat_to_task.add(link.target_id)
                
            elif link.link_type == LinkType.TASK_TO_IMPLEMENTATION:
                if link.source_id not in task_ids:
                    errors.append(f"Link {link.link_id} references unknown task {link.source_id}")
                if link.target_id not in impl_ids:
                    errors.append(f"Link {link.link_id} references unknown implementation {link.target_id}")
                has_task_to_impl.add(link.source_id)
                has_task_to_impl.add(link.target_id)
                
            elif link.link_type == LinkType.IMPLEMENTATION_TO_TEST:
                if link.source_id not in impl_ids:
                    errors.append(f"Link {link.link_id} references unknown implementation {link.source_id}")
                if link.target_id not in test_ids:
                    errors.append(f"Link {link.link_id} references unknown test {link.target_id}")
                    
        # Check for orphans (simple check for requirements and features lacking basic down/up links)
        for req in req_ids:
            if req not in has_req_to_feat:
                errors.append(f"Requirement {req} has no feature mapping (Orphan)")
                
        for feat in feat_ids:
            if feat not in has_req_to_feat:
                errors.append(f"Feature {feat} has no requirement mapping (Orphan)")
            if feat not in has_feat_to_task:
                errors.append(f"Feature {feat} has no task mapping")
                
        for task in task_ids:
            if task not in has_feat_to_task:
                errors.append(f"Task {task} has no feature mapping (Orphan)")
                
        return len(errors) == 0, errors
