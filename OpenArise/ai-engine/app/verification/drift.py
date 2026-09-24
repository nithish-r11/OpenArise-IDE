import os
import hashlib
import logging
from typing import List
from app.models.schemas import Requirement, VerificationStatus
from app.verification.evidence import EvidenceLedger
from app.tools.fs import _is_safe_path

logger = logging.getLogger(__name__)

class RequirementDriftDetector:
    """Detects if implementation has drifted since verification."""
    
    def __init__(self, project_root: str, ledger: EvidenceLedger):
        self.project_root = os.path.abspath(project_root)
        self.ledger = ledger
        
    def _hash_file(self, abs_path: str) -> str:
        if not os.path.exists(abs_path):
            return ""
        hasher = hashlib.sha256()
        with open(abs_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
        
    def detect_drift(self, requirements: List[Requirement]) -> bool:
        """
        Scans requirements and downgrades verified ones if their evidence source files have changed.
        Returns True if any drift was detected.
        """
        drifted = False
        for req in requirements:
            if req.status == VerificationStatus.VERIFIED:
                evidence_list = self.ledger.get_by_requirement(req.requirement_id)
                for ev in evidence_list:
                    if ev.file_hash and ev.source:
                        abs_path = os.path.join(self.project_root, ev.source)
                        current_hash = self._hash_file(abs_path) if _is_safe_path(self.project_root, ev.source) else ""
                        if current_hash != ev.file_hash:
                            logger.warning(f"Drift detected for req {req.requirement_id}: file {ev.source} changed.")
                            ev.result["stale"] = True
                            req.status = VerificationStatus.INCONCLUSIVE
                            drifted = True
                            break
        return drifted
