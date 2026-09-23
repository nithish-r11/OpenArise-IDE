from typing import List, Optional
from app.intelligence.models import TimelineEvent

class TimelineManager:
    """Manages a deterministic project timeline."""
    
    def __init__(self):
        self._events: List[TimelineEvent] = []
        
    def record_event(self, event: TimelineEvent) -> bool:
        """Records an event. Returns True if recorded, False if skipped due to deduplication."""
        
        # Deduplication check against the most recently recorded equivalent event
        if self._events:
            last_event = self._events[-1]
            if last_event.fingerprint() == event.fingerprint():
                return False
                
        self._events.append(event)
        return True
        
    def get_events(self) -> List[TimelineEvent]:
        return list(self._events)
        
    def clear(self):
        self._events.clear()
