import json
from app.intelligence.models import (
    TimelineEvent, TimelineEventType, RequirementBaseline, 
    DriftState, DriftFinding, ProjectIntelligenceSnapshot
)

def test_timeline_event_serialization():
    event = TimelineEvent(
        event_type=TimelineEventType.PROJECT_SCANNED,
        title="Scanned",
        description="Project scanned successfully",
        related_requirement_ids=["req_1"]
    )
    
    data = event.model_dump()
    assert data["event_type"] == "PROJECT_SCANNED"
    assert "req_1" in data["related_requirement_ids"]
    
def test_timeline_event_fingerprint():
    event1 = TimelineEvent(
        event_type=TimelineEventType.PROJECT_SCANNED,
        title="Scanned",
        description="Desc"
    )
    event2 = TimelineEvent(
        event_type=TimelineEventType.PROJECT_SCANNED,
        title="Scanned",
        description="Desc"
    )
    
    assert event1.fingerprint() == event2.fingerprint()
    assert event1.event_id != event2.event_id
    
def test_baseline_serialization():
    baseline = RequirementBaseline(
        requirement_id="req_1",
        content_hash="abc",
        associated_task_ids=["task_1"]
    )
    
    data = baseline.model_dump()
    assert data["requirement_id"] == "req_1"
    assert data["content_hash"] == "abc"
    assert "task_1" in data["associated_task_ids"]
