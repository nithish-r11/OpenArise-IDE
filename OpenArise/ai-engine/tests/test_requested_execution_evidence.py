"""Passing an unrelated/baseline check cannot prove omitted explicit steps."""
import pytest
from app.verification.requirements import RequirementExtractor, requested_execution_criteria
from app.models.schemas import EvidenceRecord, EvidenceType, EvidenceStrength, VerificationStatus
from app.verification.evidence import EvidenceLedger
from app.verification.engine import IndependentVerifier
from app.verification.gate import CompletionGate
from app.verification.snapshot import project_snapshot


def test_explicit_steps_and_repetitions_preserve_requested_criteria():
    criteria = requested_execution_criteria('Demonstrate controlled recovery. execute_tests for baseline; write_file the fault; execute_tests to detect it. Never call execute_python or build_project.')
    assert set(criteria) == {'required_tool_count:execute_tests:2', 'required_tool_count:write_file:1', 'required_recovery'}


@pytest.mark.parametrize('prompt', [
    'Use write_file to change code; execute_tests to verify.',
    'Demonstrate controlled recovery; execute_tests for baseline.',
    'execute_tests for baseline; execute_tests for fresh retest.',
])
def test_one_passing_baseline_cannot_prove_omitted_requested_steps(tmp_path, prompt):
    req = RequirementExtractor(None).extract(prompt)[0]
    ledger = EvidenceLedger()
    ledger.add_evidence(EvidenceRecord(requirement_id=req.requirement_id, source='execute_tests',
        evidence_type=EvidenceType.TEST_PASS, strength=EvidenceStrength.DIRECT, summary='Actual baseline', tool_call_id='baseline',
        result={'success': True, 'executed': True, 'exit_code': 0, 'project_snapshot': project_snapshot(str(tmp_path))}))
    result = CompletionGate(IndependentVerifier(str(tmp_path), ledger)).evaluate('p', [req])
    assert result.overall_status != VerificationStatus.VERIFIED
    assert result.requirement_results[0].missing_evidence


def test_negative_tool_mentions_do_not_require_execution():
    assert requested_execution_criteria('Explain the file. Do not call write_file or execute_tests.') == []


def test_explaining_a_tool_does_not_require_calling_it():
    assert requested_execution_criteria('Explain execute_tests and write_file.') == []


def test_negative_suffix_does_not_erase_prior_explicit_steps():
    assert requested_execution_criteria('Use write_file, do not call execute_tests.') == ['required_tool_count:write_file:1']


def test_explicit_node_steps_verify_after_actual_recovery(tmp_path):
    from tests.test_project_commands import project, agent
    from tests.test_resumable_recovery import complete
    from app.models.schemas import AgentRequest
    project(tmp_path)
    instance = agent(tmp_path)
    result, _ = complete(instance, instance.process_request(AgentRequest(
        prompt='Use write_file to change the implementation; execute_project_tests to detect it. Demonstrate controlled recovery.')))
    assert result.status == 'success'
    assert result.data['recovery']['status'] == 'RECOVERED'
    assert result.data['verification']['overall_status'] == 'VERIFIED'
