import pytest
import os
import tempfile
import json
from app.models.schemas import Requirement, VerificationStatus, EvidenceType, EvidenceStrength, EvidenceRecord, ConfidenceLevel
from app.verification.requirements import RequirementExtractor
from app.verification.evidence import EvidenceLedger
from app.verification.engine import IndependentVerifier
from app.verification.drift import RequirementDriftDetector
from app.verification.gate import CompletionGate
from tests.mock_llm import MockLLMProvider

def test_requirement_extractor():
    llm = MockLLMProvider()
    extractor = RequirementExtractor(llm)
    reqs = extractor.extract("Build a login api")
    
    # We used fallback for mock testing
    assert len(reqs) == 1
    assert reqs[0].status == VerificationStatus.INCONCLUSIVE
    assert reqs[0].description == "Build a login api"

def test_evidence_ledger():
    ledger = EvidenceLedger()
    record = EvidenceRecord(
        requirement_id="req-1",
        evidence_type=EvidenceType.TEST_PASS,
        strength=EvidenceStrength.DIRECT,
        source="pytest",
        summary="Tests passed",
        result={"exit_code": 0}
    )
    ledger.add_evidence(record)
    
    assert len(ledger.get_by_requirement("req-1")) == 1
    assert ledger.get_evidence(record.evidence_id).source == "pytest"

def test_independent_verifier_deterministic_symbol():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = EvidenceLedger()
        verifier = IndependentVerifier(temp_dir, ledger)
        
        # Test missing file
        assert verifier._check_symbol_exists(os.path.join(temp_dir, "app.py"), "login") is False
        
        # Test python file with symbol
        app_path = os.path.join(temp_dir, "app.py")
        with open(app_path, "w") as f:
            f.write("def login():\n    pass\n")
            
        assert verifier._check_symbol_exists(app_path, "login") is True
        
def test_independent_verifier_logic():
    ledger = EvidenceLedger()
    verifier = IndependentVerifier(".", ledger)
    
    req = Requirement(description="Test requirement")
    
    # No evidence -> INCONCLUSIVE
    res = verifier.verify_requirement(req)
    assert res.status == VerificationStatus.INCONCLUSIVE
    
    # Add weak/supporting evidence -> PARTIALLY_VERIFIED
    ledger.add_evidence(EvidenceRecord(
        requirement_id=req.requirement_id,
        evidence_type=EvidenceType.TOOL_RESULT,
        strength=EvidenceStrength.SUPPORTING,
        source="fs",
        summary="wrote file",
        result={}
    ))
    res = verifier.verify_requirement(req)
    assert res.status == VerificationStatus.PARTIALLY_VERIFIED
    
    # Add direct evidence -> VERIFIED
    ledger.add_evidence(EvidenceRecord(
        requirement_id=req.requirement_id,
        evidence_type=EvidenceType.TEST_PASS,
        strength=EvidenceStrength.DIRECT,
        source="pytest",
        summary="tests passed",
        result={}
    ))
    res = verifier.verify_requirement(req)
    assert res.status == VerificationStatus.VERIFIED
    assert res.confidence == ConfidenceLevel.HIGH

def test_requirement_drift_detector():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = EvidenceLedger()
        
        # Create a file
        file_path = os.path.join(temp_dir, "main.py")
        with open(file_path, "w") as f:
            f.write("v1")
            
        hasher = IndependentVerifier(temp_dir, ledger)._hash_file(file_path)
        
        req = Requirement(description="Test", status=VerificationStatus.VERIFIED)
        
        ledger.add_evidence(EvidenceRecord(
            requirement_id=req.requirement_id,
            evidence_type=EvidenceType.FILE_EXISTS,
            strength=EvidenceStrength.DIRECT,
            source="main.py",
            summary="File created",
            result={},
            file_hash=hasher
        ))
        
        detector = RequirementDriftDetector(temp_dir, ledger)
        
        # No drift
        assert detector.detect_drift([req]) is False
        assert req.status == VerificationStatus.VERIFIED
        
        # Modify file
        with open(file_path, "w") as f:
            f.write("v2")
            
        # Drift should be detected
        assert detector.detect_drift([req]) is True
        assert req.status == VerificationStatus.INCONCLUSIVE

def test_completion_gate():
    ledger = EvidenceLedger()
    verifier = IndependentVerifier(".", ledger)
    gate = CompletionGate(verifier)
    
    req1 = Requirement(description="Verified req")
    ledger.add_evidence(EvidenceRecord(
        requirement_id=req1.requirement_id,
        evidence_type=EvidenceType.TEST_PASS,
        strength=EvidenceStrength.DIRECT,
        source="pytest",
        summary="passed",
        result={}
    ))
    
    req2 = Requirement(description="Unverified req")
    
    res = gate.evaluate("proj1", [req1, req2])
    
    assert res.overall_status == VerificationStatus.INCONCLUSIVE
    assert res.report.verified == 1
    assert res.report.inconclusive == 1
    assert res.report.total_requirements == 2
