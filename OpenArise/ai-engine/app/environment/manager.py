from typing import Optional
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.environment.models import ProjectHealthReport
from app.environment.detector import EnvironmentDetector
from app.environment.dependencies import DependencyInspector
from app.environment.health import HealthEngine

class EnvironmentManager:
    """Orchestrates environment detection, dependency inspection, and health evaluation."""
    
    def __init__(self):
        self.detector = EnvironmentDetector()
        self.inspector = DependencyInspector()
        self.health_engine = HealthEngine()
        
    def evaluate_project(self, project_root: str, state: ProjectState, blueprint: Optional[ProjectBlueprint] = None) -> ProjectHealthReport:
        # 1. Detect environment
        env_info = self.detector.detect(project_root)
        
        # 2. Inspect dependencies
        deps = self.inspector.inspect(state, env_info)
        
        # 3. Evaluate health
        report = self.health_engine.evaluate(state, blueprint, env_info, deps)
        
        return report
