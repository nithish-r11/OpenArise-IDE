import ast
import hashlib
from pathlib import Path
from typing import Optional

from app.models.schemas import EvidenceType, EvidenceStrength, VerificationStatus, RequirementResult, ConfidenceLevel
from app.verification.evidence import EvidenceLedger
from app.tools.fs import _is_safe_path


class IndependentVerifier:
    """Validate evidence facts before aggregating their strength."""

    def __init__(self, project_root: str, ledger: EvidenceLedger):
        self.project_root = str(Path(project_root).resolve())
        self.ledger = ledger

    def _safe_file(self, path):
        try:
            resolved = Path(path).resolve()
            relative = resolved.relative_to(Path(self.project_root))
            return _is_safe_path(self.project_root, str(relative)) and resolved.is_file()
        except (OSError, ValueError):
            return False

    def _hash_file(self, abs_path: str) -> Optional[str]:
        if not self._safe_file(abs_path):
            return None
        return hashlib.sha256(Path(abs_path).read_bytes()).hexdigest()

    def _check_symbol_exists(self, abs_path: str, symbol_name: str) -> bool:
        if not self._safe_file(abs_path):
            return False
        try:
            tree = ast.parse(Path(abs_path).read_text(encoding="utf-8"), filename=abs_path)
            return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       and n.name == symbol_name for n in ast.walk(tree))
        except (OSError, SyntaxError, UnicodeError):
            return False

    def verify_requirement(self, req) -> RequirementResult:
        evidence = self.ledger.get_by_requirement(req.requirement_id)
        contradictions = []
        direct = []
        supporting = []
        missing = []
        for ref in req.evidence_references:
            record = self.ledger.get_evidence(ref)
            if record is None or record.requirement_id != req.requirement_id:
                missing.append(f"Invalid evidence reference: {ref}")
        for record in evidence:
            facts = record.result
            if facts.get("superseded") and record.evidence_type == EvidenceType.TEST_PASS:
                continue
            if (record.evidence_type == EvidenceType.TEST_FAIL
                    or record.strength == EvidenceStrength.CONTRADICTORY
                    or facts.get("success") is False
                    or facts.get("exit_code") not in (None, 0)):
                contradictions.append(record.evidence_id)
                continue
            if facts.get("stale"):
                missing.append(f"Stale evidence: {record.evidence_id}")
                continue
            path = str(Path(self.project_root) / record.source)
            if record.file_hash and self._hash_file(path) != record.file_hash:
                missing.append(f"Changed evidence source: {record.source}")
                continue
            if record.evidence_type == EvidenceType.FILE_EXISTS and not self._safe_file(path):
                missing.append(f"Missing evidence source: {record.source}")
                continue
            if record.evidence_type == EvidenceType.SYMBOL_EXISTS:
                symbol = facts.get("symbol_name")
                if not isinstance(symbol, str) or not self._check_symbol_exists(path, symbol):
                    missing.append(f"Unconfirmed symbol: {record.source}")
                    continue
            if record.strength == EvidenceStrength.DIRECT and record.evidence_type in (
                EvidenceType.TEST_PASS, EvidenceType.FILE_EXISTS, EvidenceType.SYMBOL_EXISTS,
            ):
                direct.append(record.evidence_id)
            else:
                supporting.append(record.evidence_id)

        status, confidence, explanation = VerificationStatus.INCONCLUSIVE, ConfidenceLevel.LOW, "Insufficient evidence."
        if contradictions:
            status, confidence = VerificationStatus.NOT_VERIFIED, ConfidenceLevel.HIGH
            explanation = "Failed execution or contradictory evidence prevents verification."
        elif missing:
            explanation = "Missing, invalid, or stale evidence prevents verification."
        elif direct:
            status, confidence = VerificationStatus.VERIFIED, ConfidenceLevel.HIGH
            explanation = "Direct evidence confirms the tracked requirement."
        elif supporting:
            status, confidence = VerificationStatus.PARTIALLY_VERIFIED, ConfidenceLevel.MEDIUM
            explanation = "Supporting evidence exists; direct verification is still required."
        if not direct:
            missing.append("Requires direct test or file evidence")
        return RequirementResult(
            requirement_id=req.requirement_id, status=status,
            evidence_used=direct + supporting + contradictions,
            missing_evidence=missing, contradictions=contradictions,
            explanation=explanation, confidence=confidence,
        )
