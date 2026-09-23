import logging
from typing import List
from app.models.schemas import Requirement, VerificationStatus, VerificationResult, CompletionReport, RequirementResult
from app.verification.engine import IndependentVerifier

logger = logging.getLogger(__name__)

class CompletionGate:
    """Evaluates final verification results and prevents false completion."""
    
    def __init__(self, verifier: IndependentVerifier):
        self.verifier = verifier
        
    def evaluate(self, project_id: str, requirements: List[Requirement]) -> VerificationResult:
        """Runs the independent verification and builds the CompletionReport."""
        req_results: List[RequirementResult] = []
        verified_count = 0
        partially_verified = 0
        inconclusive = 0
        unverified = 0
        
        overall_status = VerificationStatus.VERIFIED
        
        for req in requirements:
            res = self.verifier.verify_requirement(req)
            req.status = res.status
            req_results.append(res)
            
            if res.status == VerificationStatus.VERIFIED:
                verified_count += 1
            elif res.status == VerificationStatus.PARTIALLY_VERIFIED:
                partially_verified += 1
                if overall_status == VerificationStatus.VERIFIED:
                    overall_status = VerificationStatus.PARTIALLY_VERIFIED
            elif res.status == VerificationStatus.INCONCLUSIVE:
                inconclusive += 1
                overall_status = VerificationStatus.INCONCLUSIVE
            elif res.status == VerificationStatus.NOT_VERIFIED:
                unverified += 1
                overall_status = VerificationStatus.NOT_VERIFIED
                
        # If there are no requirements, we can't be VERIFIED
        if not requirements:
            overall_status = VerificationStatus.INCONCLUSIVE
            
        report = CompletionReport(
            total_requirements=len(requirements),
            verified=verified_count,
            partially_verified=partially_verified,
            unverified=unverified,
            inconclusive=inconclusive,
            evidence_count=len(self.verifier.ledger._records),
            tests_executed=0, # To be populated by evidence
            recovery_attempts=0
        )
        
        return VerificationResult(
            project_id=project_id,
            requirement_results=req_results,
            overall_status=overall_status,
            report=report
        )
