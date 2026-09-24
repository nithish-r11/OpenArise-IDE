from app.models.schemas import VerificationStatus, VerificationResult, CompletionReport, EvidenceType
from app.verification.engine import IndependentVerifier


class CompletionGate:
    """The final verification authority; failures dominate regardless of requirement order."""

    def __init__(self, verifier: IndependentVerifier):
        self.verifier = verifier

    def evaluate(self, project_id, requirements, recovery_attempts=0):
        results = []
        for requirement in requirements:
            result = self.verifier.verify_requirement(requirement)
            requirement.status = result.status
            results.append(result)
        priority = {
            VerificationStatus.VERIFIED: 0,
            VerificationStatus.PARTIALLY_VERIFIED: 1,
            VerificationStatus.INCONCLUSIVE: 2,
            VerificationStatus.NOT_VERIFIED: 3,
        }
        overall = max((r.status for r in results), key=priority.get) if results else VerificationStatus.INCONCLUSIVE
        records = [record for req in requirements for record in self.verifier.ledger.get_by_requirement(req.requirement_id)]
        test_calls = {record.tool_call_id or record.evidence_id for record in records
                      if record.evidence_type in (EvidenceType.TEST_PASS, EvidenceType.TEST_FAIL)}
        report = CompletionReport(
            total_requirements=len(requirements),
            verified=sum(r.status == VerificationStatus.VERIFIED for r in results),
            partially_verified=sum(r.status == VerificationStatus.PARTIALLY_VERIFIED for r in results),
            unverified=sum(r.status == VerificationStatus.NOT_VERIFIED for r in results),
            inconclusive=sum(r.status == VerificationStatus.INCONCLUSIVE for r in results),
            evidence_count=len(records), tests_executed=len(test_calls),
            recovery_attempts=recovery_attempts,
            remaining_issues=[r.explanation for r in results if r.status != VerificationStatus.VERIFIED],
        )
        return VerificationResult(
            project_id=project_id, requirement_results=results, overall_status=overall, report=report
        )
