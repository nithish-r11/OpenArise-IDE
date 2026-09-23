import os
import hashlib
import ast
import logging
from typing import List, Optional
from app.models.schemas import Requirement, EvidenceRecord, EvidenceType, EvidenceStrength, VerificationStatus, RequirementResult, ConfidenceLevel
from app.verification.evidence import EvidenceLedger

logger = logging.getLogger(__name__)

class IndependentVerifier:
    """Verifies requirements using deterministic checks and evidence."""
    
    def __init__(self, project_root: str, ledger: EvidenceLedger):
        self.project_root = os.path.abspath(project_root)
        self.ledger = ledger
        
    def _hash_file(self, abs_path: str) -> Optional[str]:
        if not os.path.exists(abs_path):
            return None
        hasher = hashlib.sha256()
        with open(abs_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
        
    def _check_symbol_exists(self, abs_path: str, symbol_name: str) -> bool:
        if not os.path.exists(abs_path):
            return False
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=abs_path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == symbol_name:
                        return True
            return False
        except Exception as e:
            logger.error(f"AST parsing failed for {abs_path}: {e}")
            return False

    def verify_requirement(self, req: Requirement) -> RequirementResult:
        """Determines the status of a requirement based on evidence and deterministic checks."""
        evidence = self.ledger.get_by_requirement(req.requirement_id)
        
        has_direct = any(e.strength == EvidenceStrength.DIRECT for e in evidence)
        has_contradictory = any(e.strength == EvidenceStrength.CONTRADICTORY for e in evidence)
        
        status = VerificationStatus.INCONCLUSIVE
        confidence = ConfidenceLevel.LOW
        explanation = "Insufficient evidence."
        
        if has_contradictory:
            status = VerificationStatus.NOT_VERIFIED
            confidence = ConfidenceLevel.HIGH
            explanation = "Contradictory evidence found (e.g. failing tests)."
        elif has_direct:
            status = VerificationStatus.VERIFIED
            confidence = ConfidenceLevel.HIGH
            explanation = "Direct evidence confirms requirement."
        elif evidence:
            status = VerificationStatus.PARTIALLY_VERIFIED
            confidence = ConfidenceLevel.MEDIUM
            explanation = "Only supporting evidence found, missing direct verification."
            
        return RequirementResult(
            requirement_id=req.requirement_id,
            status=status,
            evidence_used=[e.evidence_id for e in evidence],
            missing_evidence=["Requires direct test or file evidence" if not has_direct else ""],
            contradictions=[e.evidence_id for e in evidence if e.strength == EvidenceStrength.CONTRADICTORY],
            explanation=explanation,
            confidence=confidence
        )
