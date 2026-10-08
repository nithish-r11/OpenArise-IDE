"""Deterministic provider, real permissions/files/pytest/backend projection.

These regressions are not live model evidence. Packaged live acceptance is separate.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from agent_host import build_service
from agent_projection import project_response
from app.llm.base import LLMProvider
from app.models.schemas import AgentAction, ToolCall, DiagnosisResult, RecoveryPlan, FailureCategory, ConfidenceLevel
from app.tools.permissions import RiskLevel

GOOD = 'def multiply(a, b):\n    return a * b\n'
BAD = 'def multiply(a, b):\n    return a + b\n'
TEST = 'from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n'

class ControlledProvider(LLMProvider):
    def health_check(self): return True
    def generate(self, *args, **kwargs): raise AssertionError('Unexpected text path')
    def generate_structured(self, prompt, schema, **kwargs):
        if schema is AgentAction:
            return AgentAction(action_type='tool_call', tool_calls=[ToolCall(tool_name='write_file', arguments={'path':'math_ops.py','content':BAD,'overwrite':True}), ToolCall(tool_name='execute_tests')])
        if schema is DiagnosisResult:
            return DiagnosisResult(category=FailureCategory.TEST_FAILURE, summary='Actual pytest failed.', probable_root_cause='Addition instead of multiplication.', confidence=ConfidenceLevel.HIGH)
        if schema is RecoveryPlan:
            return RecoveryPlan(failure_id='fixture', goal='Restore multiplication', diagnosis_summary='Repair arithmetic.', expected_result='Original tests pass', risk_level=RiskLevel.WRITE,
                                proposed_actions=[ToolCall(tool_name='write_file', arguments={'path':'math_ops.py','content':GOOD,'overwrite':True})])
        raise AssertionError(schema)

class RecoveryProjectionTests(unittest.TestCase):
    def complete(self, failing):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root/'math_ops.py').write_text(GOOD)
        (root/'test_math_ops.py').write_text(TEST)
        if failing:
            (root/'test_unrecoverable.py').write_text('def test_controlled_failure():\n    assert False, "Intentional failure: preserve this test"\n')
        service = build_service(str(root), ControlledProvider())
        self.addCleanup(lambda: service.dispatch({'request_id':'stop','method':'shutdown','params':{}}))
        def send(command, method, **params):
            raw = service.dispatch({'request_id':command,'method':method,'params':params}).model_dump(mode='json')
            projected = project_response(raw, method, service.workspace)
            self.assertTrue(projected['success'])
            return raw, projected
        raw, projected = send('case', 'request_agent_execution', prompt='Repair only multiplication; preserve original tests.')
        self.assertEqual(projected['data']['status'], 'permission_required')
        self.assertEqual((root/'math_ops.py').read_text(), GOOD)
        decisions = 0
        while projected['data']['pending_action']:
            pending = projected['data']['pending_action']
            self.assertIn(pending['tool_name'], ['write_file','execute_tests'])
            decisions += 1
            self.assertLessEqual(decisions, 6)
            send('allow-'+str(decisions), 'approve_agent_action', request_id='case', tool_call_id=pending['tool_call_id'])
            raw, projected = send('resume-'+str(decisions), 'resume_agent_execution', request_id='case', tool_call_id=pending['tool_call_id'])
        self.assertEqual((root/'test_math_ops.py').read_text(), TEST)
        self.assertEqual(projected['data']['current_state'], raw['data']['current_state'])
        self.assertEqual(projected['data']['data']['verification']['overall_status'], raw['data']['data']['verification']['overall_status'])
        self.assertEqual(projected['data']['data']['recovery']['status'], raw['data']['data']['recovery']['status'])
        self.assertNotIn('<actual result>', json.dumps(projected))
        return projected['data']

    def test_real_failed_retest_and_rollback_survive_desktop_projection(self):
        r = self.complete(True)
        self.assertEqual(r['status'], 'failure')
        self.assertEqual(r['current_state'], 'FAILED')
        self.assertEqual(r['data']['recovery']['status'], 'ROLLED_BACK')
        self.assertEqual(r['data']['verification']['overall_status'], 'NOT_VERIFIED')
        self.assertTrue(any(t['executed'] and not t['success'] and t['exit_code']==1 for t in r['data']['tool_results']))

    def test_real_passing_retest_keeps_verified_recovery_projection(self):
        r = self.complete(False)
        self.assertEqual(r['status'], 'success')
        self.assertEqual(r['data']['recovery']['status'], 'RECOVERED')
        self.assertEqual(r['data']['verification']['overall_status'], 'VERIFIED')
        self.assertTrue(any(e['evidence_type']=='TEST_PASS' and e['exit_code']==0 and not e['stale'] for e in r['data']['evidence']))
