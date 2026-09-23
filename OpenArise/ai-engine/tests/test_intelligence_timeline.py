from app.intelligence.timeline import TimelineManager
from app.intelligence.models import TimelineEvent, TimelineEventType

def test_timeline_manager_deduplication():
    manager = TimelineManager()
    
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
    
    event3 = TimelineEvent(
        event_type=TimelineEventType.PROJECT_SCANNED,
        title="Scanned Different",
        description="Desc"
    )
    
    assert manager.record_event(event1) is True
    assert manager.record_event(event2) is False # Duplicate of consecutive
    assert manager.record_event(event3) is True # Different title
    
    assert len(manager.get_events()) == 2
    
def test_timeline_manager_clear():
    manager = TimelineManager()
    manager.record_event(TimelineEvent(event_type=TimelineEventType.PROJECT_SCANNED, title="1", description="1"))
    assert len(manager.get_events()) == 1
    manager.clear()
    assert len(manager.get_events()) == 0
