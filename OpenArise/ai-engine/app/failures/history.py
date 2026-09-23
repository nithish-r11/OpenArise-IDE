from typing import Dict, List, Optional
from collections import OrderedDict
from app.models.schemas import FailureEvent

class FailureHistoryManager:
    """Manages failure history with bounded memory and basic loop detection."""
    
    def __init__(self, max_history: int = 50, loop_threshold: int = 3):
        self.max_history = max_history
        self.loop_threshold = loop_threshold
        # Use OrderedDict as a simple FIFO cache bounded to max_history
        self._history: OrderedDict[str, FailureEvent] = OrderedDict()
        
    def record_failure(self, failure: FailureEvent):
        """Records a new failure event, evicting the oldest if over limit."""
        self._history[failure.failure_id] = failure
        
        if len(self._history) > self.max_history:
            self._history.popitem(last=False)
            
    def get_failure(self, failure_id: str) -> Optional[FailureEvent]:
        return self._history.get(failure_id)
        
    def list_recent(self, limit: int = 10) -> List[FailureEvent]:
        """Returns the most recent failures, newest first."""
        events = list(self._history.values())
        return list(reversed(events))[:limit]
        
    def detect_loop(self, tool_name: str, error_signature: str) -> bool:
        """
        Returns True if the same tool and error signature have failed 
        consecutively >= loop_threshold times in recent history.
        """
        if not error_signature:
            return False
            
        recent = self.list_recent(limit=self.loop_threshold)
        if len(recent) < self.loop_threshold:
            return False
            
        for event in recent:
            if event.tool_name != tool_name or event.error_signature != error_signature:
                return False
                
        return True
