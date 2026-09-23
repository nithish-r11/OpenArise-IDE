from typing import List, Dict, Optional
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.traceability.graph import TraceabilityGraphManager
from app.intelligence.models import RequirementBaseline, DriftFinding, DriftState

class RequirementDriftDetector:
    """Detects structural and hash-based drift between a baseline and current project state."""
    
    def detect_drift(self, baseline: RequirementBaseline, 
                     state: ProjectState, blueprint: Optional[ProjectBlueprint],
                     traceability: Optional[TraceabilityGraphManager]) -> DriftFinding:
                     
        finding = DriftFinding(
            requirement_id=baseline.requirement_id,
            state=DriftState.NO_DRIFT,
            reason="No drift detected."
        )
        
        if not blueprint or not traceability:
            finding.state = DriftState.UNRESOLVED
            finding.reason = "Blueprint or traceability graph missing for evaluation."
            return finding
            
        # 1. Structural Checks
        
        # Are the features still present and linked?
        if baseline.requirement_id not in blueprint.requirements:
            finding.state = DriftState.CONFIRMED_STRUCTURAL_DRIFT
            finding.reason = "Requirement was removed from blueprint."
            return finding
            
        # Check associated tasks mapping
        for task_id in baseline.associated_task_ids:
            if not any(t.task_id == task_id for t in blueprint.tasks):
                finding.state = DriftState.CONFIRMED_STRUCTURAL_DRIFT
                finding.reason = f"Required task {task_id} was removed."
                return finding
                
        # Check implementation mapping (from graph)
        # Baseline says it mapped to implementation_ids. Are they still in the graph?
        current_nodes = traceability.graph.nodes
        for impl_id in baseline.implementation_ids:
            node = next((n for n in current_nodes if n.node_id == impl_id), None)
            if not node:
                finding.state = DriftState.CONFIRMED_STRUCTURAL_DRIFT
                finding.reason = f"Mapped implementation {impl_id} was removed from the graph."
                finding.related_implementations.append(impl_id)
                return finding
                
            # If node exists, did its hash change?
            # Find the corresponding file in state
            file_info = next((f for f in state.files if hasattr(node, 'file_path') and f.relative_path == getattr(node, 'file_path', '')), None)
            if file_info and file_info.content_hash != baseline.content_hash:
                finding.state = DriftState.POTENTIAL_DRIFT
                finding.reason = f"Implementation content hash changed for {impl_id}."
                finding.related_implementations.append(impl_id)
                # Do not return immediately, keep checking structural issues which have higher precedence.
                
        return finding
