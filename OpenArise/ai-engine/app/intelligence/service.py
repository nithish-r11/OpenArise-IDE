from typing import Optional, List
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.traceability.graph import TraceabilityGraphManager
from app.environment.models import ProjectHealthReport
from app.intelligence.models import ProjectIntelligenceSnapshot, TimelineEvent, RequirementBaseline, DriftFinding
from app.intelligence.aggregator import ProjectIntelligenceAggregator
from app.intelligence.timeline import TimelineManager
from app.intelligence.drift import RequirementDriftDetector

class IntelligenceService:
    """Facade for project intelligence, timeline, and drift operations."""
    
    def __init__(self):
        self.aggregator = ProjectIntelligenceAggregator()
        self.timeline = TimelineManager()
        self.drift_detector = RequirementDriftDetector()
        
    def build_snapshot(self, state: ProjectState, blueprint: Optional[ProjectBlueprint] = None,
                       traceability: Optional[TraceabilityGraphManager] = None,
                       health: Optional[ProjectHealthReport] = None) -> ProjectIntelligenceSnapshot:
        return self.aggregator.build_snapshot(state, blueprint, traceability, health)
        
    def record_event(self, event: TimelineEvent) -> bool:
        return self.timeline.record_event(event)
        
    def get_timeline(self) -> List[TimelineEvent]:
        return self.timeline.get_events()
        
    def clear_timeline(self):
        self.timeline.clear()
        
    def detect_drift(self, baseline: RequirementBaseline, state: ProjectState, 
                     blueprint: Optional[ProjectBlueprint] = None,
                     traceability: Optional[TraceabilityGraphManager] = None) -> DriftFinding:
        return self.drift_detector.detect_drift(baseline, state, blueprint, traceability)
