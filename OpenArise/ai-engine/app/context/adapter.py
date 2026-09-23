from typing import Dict, Any

class ProjectIntelligenceContextAdapter:
    """Adapts the rich intelligence snapshot into a bounded context for the AI Agent."""
    
    def __init__(self, workspace_service):
        self.workspace = workspace_service
        
    def build_bounded_context(self) -> Dict[str, Any]:
        """Builds a deterministic, secret-free context snapshot."""
        try:
            # Avoid direct dependency on internal models, use the safe API response dict
            snapshot_res = self.workspace.get_intelligence_snapshot()
            if not snapshot_res.success or not snapshot_res.data:
                return {}
                
            snapshot_data = snapshot_res.data
            
            # Extract bounded fields
            bounded = {
                "project_name": snapshot_data.get("project_name", "unknown"),
                "total_files": snapshot_data.get("project_state_summary", {}).get("total_files", 0),
                "requirements_count": snapshot_data.get("blueprint_summary", {}).get("requirements", 0),
                "traceability_nodes": snapshot_data.get("traceability_summary", {}).get("nodes", 0),
                "health_issues": snapshot_data.get("health_summary", {}).get("blocked", 0) + snapshot_data.get("health_summary", {}).get("errors", 0),
                "missing_dependencies": snapshot_data.get("health_summary", {}).get("missing_dependencies", 0)
            }
            
            return {
                "intelligence_summary": bounded
            }
        except Exception:
            # Fallback if something fails
            return {"intelligence_summary": "Context unavailable"}
