import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict
from app.models.schemas import FailureMemoryRecord, FailureEvent, DiagnosisResult, RecoveryResult, RecoveryPlan, RecoveryState
from app.memory.store import SQLiteMemoryStore
from app.memory.index import MemoryIndex

logger = logging.getLogger(__name__)

class MemoryManager:
    """High-level abstraction for memory operations."""
    
    def __init__(self, project_root: str):
        # The project_id could be derived from project_root or passed explicitly.
        # For MVP, we'll use a hash of the project_root or just its basename.
        self.project_id = os.path.basename(os.path.abspath(project_root))
        self.store = SQLiteMemoryStore(project_root)
        self.index = MemoryIndex(self.store)
        
    def record_failure(self, failure: FailureEvent) -> FailureMemoryRecord:
        """Create a new memory record for a detected failure."""
        record = FailureMemoryRecord(
            project_id=self.project_id,
            failure_id=failure.failure_id,
            failure_signature=failure.error_signature or "unknown",
            tool_name=failure.tool_name,
            category=failure.category,
            summary=failure.summary,
            affected_file=failure.affected_file
        )
        self.store.save(record)
        return record
        
    def update_with_diagnosis(self, memory_id: str, diagnosis: DiagnosisResult):
        record = self.store.get(memory_id)
        if record:
            record.root_cause = diagnosis.probable_root_cause
            record.diagnosis_confidence = diagnosis.confidence
            record.updated_at = datetime.now(timezone.utc).isoformat()
            self.store.save(record)
            
    def update_with_recovery(self, memory_id: str, result: RecoveryResult, plan: Optional[RecoveryPlan] = None):
        record = self.store.get(memory_id)
        if record:
            record.outcome = result.status
            record.attempt_count += 1
            record.recovery_actions = result.actions_executed
            record.test_evidence = result.evidence
            record.rollback_performed = result.rollback_performed
            if plan:
                record.recovery_plan = plan.model_dump()
            record.updated_at = datetime.now(timezone.utc).isoformat()
            self.store.save(record)
            
    def get_memory(self, memory_id: str) -> Optional[FailureMemoryRecord]:
        return self.store.get(memory_id)
        
    def search_relevant(self, failure: FailureEvent) -> List[FailureMemoryRecord]:
        """Search for relevant past failures to guide current recovery."""
        return self.index.search(
            project_id=self.project_id,
            signature=failure.error_signature or "",
            category=failure.category.value,
            summary=failure.summary
        )
        
    def get_statistics(self) -> Dict[str, int]:
        """Returns basic statistics for the project."""
        records = self.store.list_recent(self.project_id, limit=1000)
        stats = {
            "total_failures": len(records),
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "blocked_recoveries": 0,
            "rolled_back_recoveries": 0
        }
        
        for r in records:
            if r.outcome == RecoveryState.RECOVERED:
                stats["successful_recoveries"] += 1
            elif r.outcome == RecoveryState.FAILED:
                stats["failed_recoveries"] += 1
            elif r.outcome == RecoveryState.BLOCKED:
                stats["blocked_recoveries"] += 1
            elif r.outcome == RecoveryState.ROLLED_BACK:
                stats["rolled_back_recoveries"] += 1
                
        return stats
