// Test-only main-process fixture. Production exposes no fixture toggle or injection IPC.
const assert = require('node:assert/strict');
module.exports = function smokeBackend() {
  let closed = false, submissions = 0;
  const commands = [], requests = new Map();
  const stamp = '2026-09-27T12:00:00Z';
  return {
    getStats() { return [...commands]; },
    async connect() { return { status: 'connected', reason: 'ready' }; },
    async disconnect() { closed = true; return { status: 'disconnected', reason: 'closed' }; },
    async request(request) {
      assert.equal(closed, false);
      const method = request.method;
      commands.push(method);
      const fixture = require('./intelligence.json')[method];
      if (fixture) return { kind: 'backend', response: { request_id: request.request_id, success: true, action_state: 'completed', error: null, events: [], data: fixture } };
      let record;
      if (method === 'request_agent_execution') {
        submissions++;
        const prompt = request.params.prompt.toLowerCase();
        const scenario = prompt.startsWith('phase7') ? prompt : submissions === 1 ? 'permission' : submissions === 2 ? 'failure' : 'verified';
        record = { id: request.request_id, scenario, status: scenario.includes('permission') || scenario.includes('deny') || scenario.includes('cancel') ? 'permission_required' : scenario.includes('false done') || scenario === 'verified' ? 'success' : scenario.includes('failure') || scenario.includes('attempted') || scenario.includes('blocked') ? 'failure' : 'unverified' };
        requests.set(record.id, record);
        await new Promise(resolve => setTimeout(resolve, 600));
      } else {
        record = requests.get(request.params.request_id);
        assert.ok(record, 'Fixture target exists');
        if (method !== 'get_agent_execution') {
          if (method !== 'cancel_agent_execution') assert.equal(request.params.tool_call_id, 'smoke-tool');
          record.status = method === 'approve_agent_action' ? 'approved' : method === 'deny_agent_action' ? 'denied' : method === 'cancel_agent_execution' ? 'cancelled' : 'unverified';
          await new Promise(resolve => setTimeout(resolve, 300));
        }
      }
      const { id, status, scenario } = record;
      const pending = status === 'permission_required' || status === 'approved';
      const action = pending ? status : status === 'failure' ? 'failed' : status === 'denied' || status === 'cancelled' ? status : 'completed';
      const gate = status === 'success' && !scenario.includes('false done') ? 'VERIFIED' : 'INCONCLUSIVE';
      const execute = scenario.includes('phase7') && (scenario.includes('permission') || scenario.includes('deny') || scenario.includes('cancel'));
      const recoveryState = scenario.includes('recovery completed') ? 'RECOVERED' : scenario.includes('recovery blocked') ? 'BLOCKED' : null;
      const attempted = scenario.includes('recovery') || status === 'success';
      const stale = scenario.includes('stale');
      const tools = pending ? [] : [{ tool_name: gate === 'VERIFIED' || execute ? 'execute_tests' : 'write_file', tool_call_id: 'smoke-tool', success: status !== 'failure' && status !== 'denied', executed: status !== 'denied' && status !== 'cancelled', exit_code: gate === 'VERIFIED' ? 0 : status === 'failure' ? 1 : null, timestamp: stamp }];
      const evidence = pending || status === 'denied' || status === 'cancelled' ? [] : [{
        evidence_id: 'ev-smoke', requirement_id: 'req-smoke', evidence_type: status === 'failure' ? 'TEST_FAIL' : gate === 'VERIFIED' || stale ? 'TEST_PASS' : 'TOOL_RESULT',
        strength: status === 'failure' ? 'CONTRADICTORY' : gate === 'VERIFIED' || stale ? 'DIRECT' : 'SUPPORTING', summary: 'Deterministic fixture evidence.',
        tool_call_id: 'smoke-tool', success: status !== 'failure', exit_code: status === 'failure' ? 1 : 0, stale, superseded: false, timestamp: stamp
      }];
      const missing = gate === 'VERIFIED' ? [] : stale ? ['Stale evidence: ev-smoke', 'Invalid evidence reference: ev-missing'] : ['Requires direct test or file evidence'];
      const verification = pending ? null : { overall_status: gate, timestamp: stamp, report: {
        total_requirements: 1, verified: gate === 'VERIFIED' ? 1 : 0, partially_verified: 0, unverified: 0, inconclusive: gate === 'VERIFIED' ? 0 : 1,
        evidence_count: evidence.length, tests_executed: tools.filter(t => t.tool_name === 'execute_tests' && t.executed).length, recovery_attempts: attempted ? 1 : 0
      }, requirement_results: [{ requirement_id: 'req-smoke', status: gate, evidence_used: evidence.map(e => e.evidence_id), missing_evidence: missing,
        contradictions: status === 'failure' ? ['ev-smoke'] : [], explanation: gate === 'VERIFIED' ? 'Fixture direct evidence confirms the requirement.' : 'Fixture evidence does not verify completion.', confidence: gate === 'VERIFIED' ? 'HIGH' : 'LOW' }],
        remaining_issues: gate === 'VERIFIED' ? [] : ['Fixture completion remains unverified.'], truncated: false };
      const states = attempted && !pending ? ['EXECUTING', 'RECOVERING', 'VERIFYING', action.toUpperCase()] : [pending ? status.toUpperCase() : action.toUpperCase()];
      return { kind: 'backend', response: {
        request_id: request.request_id, success: true, action_state: action, error: null,
        events: states.map((state, i) => ({ request_id: id, sequence: i + 1, event_type: 'state_changed', current_state: state, tool_call_id: null, timestamp: stamp })),
        data: { request_id: id, status, action_state: action, current_state: action.toUpperCase(), message: 'Offline smoke fixture result.',
          pending_action: pending ? { request_id: id, tool_call_id: 'smoke-tool', risk_level: execute ? 'EXECUTE' : 'WRITE', tool_name: execute ? 'execute_tests' : 'write_file', resource: execute ? null : 'app/example.py', approved: status === 'approved' } : null,
          data: { tool_results: tools, verification, evidence, requirements: [{ requirement_id: 'req-smoke', title: 'Fixture requirement' }], truncated: false,
            failure: status === 'failure' ? { category: 'TEST_FAILURE', severity: null, summary: 'Fixture test execution failed.', root_cause: 'Fixture diagnosis: assertion differs from expected output.', tool_name: 'execute_tests' } : null,
            recovery: recoveryState ? { status: recoveryState, attempts: 1, final_result: 'Fixture recovery result returned.', tests_run: recoveryState === 'RECOVERED' ? ['Fixture retest execution recorded'] : [], timestamp: stamp } : null },
        },
      } };
    },
  };
};