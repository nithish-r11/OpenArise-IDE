import logging
from typing import List, Dict, Optional
from app.models.schemas import EvidenceRecord, EvidenceType, EvidenceStrength

logger = logging.getLogger(__name__)

class EvidenceLedger:
    """In-memory tracker of all evidence for verification. Clean interface for future persistent storage."""
    
    def __init__(self):
        self._records: Dict[str, EvidenceRecord] = {}
        
    def add_evidence(self, record: EvidenceRecord) -> str:
        self._records[record.evidence_id] = record
        return record.evidence_id
        
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._records.get(evidence_id)
        
    def get_by_requirement(self, requirement_id: str) -> List[EvidenceRecord]:
        return [r for r in self._records.values() if r.requirement_id == requirement_id]
        
    def get_by_file_hash(self, file_hash: str) -> List[EvidenceRecord]:
        return [r for r in self._records.values() if r.file_hash == file_hash]
        
    def clear(self):
        self._records.clear()
