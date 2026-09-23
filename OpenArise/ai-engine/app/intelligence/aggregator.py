from typing import Optional
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.traceability.graph import TraceabilityGraphManager
from app.environment.models import ProjectHealthReport, Severity, DependencyState
from app.intelligence.models import ProjectIntelligenceSnapshot

class ProjectIntelligenceAggregator:
    """Aggregates read-only views of the project into a snapshot."""
    
    def build_snapshot(self, state: ProjectState, blueprint: Optional[ProjectBlueprint],
                       traceability: Optional[TraceabilityGraphManager],
                       health: Optional[ProjectHealthReport]) -> ProjectIntelligenceSnapshot:
                       
        snapshot = ProjectIntelligenceSnapshot(
            project_id=state.project_info.project_id,
            project_name=state.project_info.name,
            scan_timestamp=state.scan_timestamp
        )
        
        # 1. Project State Summary
        snapshot.project_state_summary = {
            "total_files": len(state.files),
            "python_modules": len(state.python_modules),
            "dependencies_declared": len(state.dependencies)
        }
        
        # 2. Blueprint Summary
        if blueprint:
            snapshot.blueprint_summary = {
                "requirements": len(blueprint.requirements),
                "features": len(blueprint.features),
                "tasks": len(blueprint.tasks)
            }
            
        # 3. Traceability Summary
        if traceability:
            total_nodes = (
                len(traceability.graph.requirements) +
                len(traceability.graph.features) +
                len(traceability.graph.tasks) +
                len(traceability.graph.implementations) +
                len(traceability.graph.tests) +
                len(traceability.graph.evidence)
            )
            snapshot.traceability_summary = {
                "nodes": total_nodes,
                "links": len(traceability.graph.links)
            }
            
        # 4. Environment & Health Summary
        if health:
            snapshot.environment_summary = {
                "python_available": health.environment.python_available,
                "virtualenv_present": health.environment.virtualenv_present,
                "git_available": health.environment.git_available
            }
            
            snapshot.health_summary = {
                "total_checks": len(health.checks),
                "blocked": sum(1 for c in health.checks if c.severity == Severity.BLOCKED),
                "errors": sum(1 for c in health.checks if c.severity == Severity.ERROR),
                "warnings": sum(1 for c in health.checks if c.severity == Severity.WARNING),
                "missing_dependencies": sum(1 for d in health.dependency_status if d.status == DependencyState.MISSING)
            }
            
        return snapshot
