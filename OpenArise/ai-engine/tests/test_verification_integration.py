import pytest
from app.models.schemas import Requirement, EvidenceRecord, EvidenceType, EvidenceStrength, VerificationStatus
from app.verification.evidence import EvidenceLedger
from app.verification.engine import IndependentVerifier
from app.verification.gate import CompletionGate
from app.verification.drift import RequirementDriftDetector


def record(req, **changes):
    values = dict(
        requirement_id=req.requirement_id, evidence_type=EvidenceType.TEST_PASS,
        strength=EvidenceStrength.DIRECT, source="pytest", summary="Test output",
        result={"exit_code": 0, "success": True}, tool_call_id="test",
    )
    values.update(changes)
    return EvidenceRecord(**values)


@pytest.mark.parametrize("facts", [
    {"exit_code": 1, "success": True},
    {"exit_code": 0, "success": False},
])
def test_failed_facts_override_claimed_direct_strength(tmp_path, facts):
    req = Requirement(description="Pass tests")
    ledger = EvidenceLedger()
    ledger.add_evidence(record(req, result=facts))
    gate = CompletionGate(IndependentVerifier(str(tmp_path), ledger))
    assert gate.evaluate("project", [req]).overall_status == VerificationStatus.NOT_VERIFIED


def test_test_fail_type_cannot_be_direct_success(tmp_path):
    req = Requirement(description="Pass tests")
    ledger = EvidenceLedger()
    ledger.add_evidence(record(req, evidence_type=EvidenceType.TEST_FAIL))
    gate = CompletionGate(IndependentVerifier(str(tmp_path), ledger))
    assert gate.evaluate("project", [req]).overall_status == VerificationStatus.NOT_VERIFIED


@pytest.mark.parametrize("reverse", [False, True])
def test_gate_failure_precedence_does_not_depend_on_requirement_order(tmp_path, reverse):
    failed = Requirement(description="Failing requirement")
    unknown = Requirement(description="Unknown requirement")
    ledger = EvidenceLedger()
    ledger.add_evidence(record(failed, evidence_type=EvidenceType.TEST_FAIL))
    reqs = [failed, unknown]
    if reverse:
        reqs.reverse()
    result = CompletionGate(IndependentVerifier(str(tmp_path), ledger)).evaluate("project", reqs)
    assert result.overall_status == VerificationStatus.NOT_VERIFIED
    assert result.report.unverified == 1
    assert result.report.inconclusive == 1


def test_stale_file_evidence_cannot_be_reverified_by_gate(tmp_path):
    source = tmp_path / "feature.py"
    source.write_text("value = 1\n")
    req = Requirement(description="File requirement", status=VerificationStatus.VERIFIED)
    ledger = EvidenceLedger()
    verifier = IndependentVerifier(str(tmp_path), ledger)
    evidence = record(req, evidence_type=EvidenceType.FILE_EXISTS, source="feature.py",
                      file_hash=verifier._hash_file(str(source)))
    ledger.add_evidence(evidence)
    source.write_text("value = 2\n")
    assert RequirementDriftDetector(str(tmp_path), ledger).detect_drift([req])
    result = CompletionGate(verifier).evaluate("project", [req])
    assert result.overall_status == VerificationStatus.INCONCLUSIVE
    assert result.report.verified == 0


def test_invalid_requirement_evidence_reference_blocks_completion(tmp_path):
    req = Requirement(description="Requirement", evidence_references=["missing"])
    ledger = EvidenceLedger()
    ledger.add_evidence(record(req))
    result = CompletionGate(IndependentVerifier(str(tmp_path), ledger)).evaluate("project", [req])
    assert result.overall_status == VerificationStatus.INCONCLUSIVE


def test_symbol_evidence_is_checked_against_actual_ast(tmp_path):
    (tmp_path / "feature.py").write_text("def actual():\n    pass\n")
    req = Requirement(description="Symbol requirement")
    ledger = EvidenceLedger()
    evidence = record(req, evidence_type=EvidenceType.SYMBOL_EXISTS, source="feature.py",
                      result={"symbol_name": "invented"})
    ledger.add_evidence(evidence)
    verifier = IndependentVerifier(str(tmp_path), ledger)
    assert verifier.verify_requirement(req).status == VerificationStatus.INCONCLUSIVE
    evidence.result["symbol_name"] = "actual"
    assert verifier.verify_requirement(req).status == VerificationStatus.VERIFIED


def test_gate_counts_one_test_call_associated_with_multiple_requirements(tmp_path):
    reqs = [Requirement(description="One"), Requirement(description="Two")]
    ledger = EvidenceLedger()
    for req in reqs:
        ledger.add_evidence(record(req))
    result = CompletionGate(IndependentVerifier(str(tmp_path), ledger)).evaluate("project", reqs, recovery_attempts=2)
    assert result.report.tests_executed == 1
    assert result.report.evidence_count == 2
    assert result.report.recovery_attempts == 2
