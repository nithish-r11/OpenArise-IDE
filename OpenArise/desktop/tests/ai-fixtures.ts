import type { AIResult } from '../src/types/ai';
export const stamp = '2026-09-27T12:00:00Z';
export function agentFixture(command: string, status: AIResult['status'] = 'unverified', target = command) {
  const pending = status === 'permission_required' || status === 'approved';
  const action = status === 'failure' ? 'failed' : status === 'success' || status === 'unverified' ? 'completed' : status;
  const verified = status === 'success';
  const data: AIResult = {
    request_id: target, status, current_state: action.toUpperCase(), action_state: action, message: 'Recorded backend result.',
    pending_action: pending ? { request_id: target, tool_call_id: 'tool-1', tool_name: 'write_file', risk_level: 'WRITE', resource: 'app/main.py', approved: status === 'approved' } : null,
    data: {
      tool_results: verified ? [{ tool_name: 'execute_tests', tool_call_id: 'test-1', success: true, executed: true, exit_code: 0, timestamp: stamp }] : [],
      failure: null, recovery: null, truncated: false, requirements: [{ requirement_id: 'req-1', title: 'Tracked requirement' }],
      evidence: verified ? [{ evidence_id: 'ev-1', requirement_id: 'req-1', evidence_type: 'TEST_PASS', strength: 'DIRECT', summary: 'Test execution returned exit 0.', tool_call_id: 'test-1', success: true, exit_code: 0, stale: false, superseded: false, timestamp: stamp }] : [],
      verification: pending ? null : { overall_status: verified ? 'VERIFIED' : 'INCONCLUSIVE', timestamp: stamp,
        report: { total_requirements: 1, verified: verified ? 1 : 0, partially_verified: 0, unverified: 0, inconclusive: verified ? 0 : 1, evidence_count: verified ? 1 : 0, tests_executed: verified ? 1 : 0, recovery_attempts: 0 },
        requirement_results: [{ requirement_id: 'req-1', status: verified ? 'VERIFIED' : 'INCONCLUSIVE', evidence_used: verified ? ['ev-1'] : [], missing_evidence: verified ? [] : ['Requires direct test or file evidence'], contradictions: [], explanation: verified ? 'Direct evidence confirms the tracked requirement.' : 'Insufficient evidence.', confidence: verified ? 'HIGH' : 'LOW' }],
        remaining_issues: verified ? [] : ['Insufficient evidence.'], truncated: false },
    },
  };
  return { request_id: command, success: true, action_state: action, error: null,
    events: [{ request_id: target, sequence: 1, event_type: 'state_changed', current_state: data.current_state, tool_call_id: null, timestamp: stamp }], data };
}