import json
import os
from typing import List
from app.memory.manager import MemoryManager
from app.models.schemas import RecoveryState

class MemoryExporter:
    """Exports structured failure memories to JSONL for future model training."""
    
    def __init__(self, manager: MemoryManager):
        self.manager = manager
        
    def export_jsonl(self, output_path: str, outcomes: List[RecoveryState] = None):
        """
        Exports memories to a JSONL file. 
        If outcomes is None, exports all outcomes.
        Redacted properties are automatically stripped by the MemoryStore prior.
        """
        if outcomes is None:
            outcomes = [RecoveryState.RECOVERED, RecoveryState.FAILED, RecoveryState.BLOCKED, RecoveryState.ROLLED_BACK]
            
        records = self.manager.store.list_recent(self.manager.project_id, limit=10000)
        
        # Ensure output dir exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        with open(output_path, "w") as f:
            for record in records:
                if record.outcome in outcomes:
                    # Format as instructed: failure -> diagnosis -> recovery -> evidence -> outcome
                    export_data = {
                        "failure": record.failure_signature,
                        "diagnosis": record.root_cause or record.summary,
                        "recovery": record.recovery_plan,
                        "evidence": record.test_evidence,
                        "outcome": record.outcome.value if record.outcome else None
                    }
                    f.write(json.dumps(export_data) + "\n")
