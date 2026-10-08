import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { agentFixture, stamp } from './ai-fixtures';
import { completionPresentation } from '../src/workspace/completion';
import { activityPresentation } from '../src/workspace/activity';
import { RecoveryCard } from '../src/components/AI/RecoveryCard';
import { validAgentEnvelope } from '../shared/agent-response';
import type { AIHistoryItem } from '../src/types/ai';
// Deterministic UI edge cases only. Live acceptance is electron-live-recovery.cjs.
function recovered(): AIHistoryItem {
  const envelope = agentFixture('recovery-request', 'success');
  const r = envelope.data;
  r.data.recovery = { status: 'RECOVERED', attempts: 1, final_result: 'Fixture actual retest passed; gate decides completion.', tests_run: ['test-1'], timestamp: stamp };
  r.data.tool_results.unshift({ tool_name: 'execute_tests', tool_call_id: 'failed-test', executed: true, success: false, exit_code: 1, timestamp: stamp, resolved_by: 'ev-1' });
  r.data.evidence.unshift({ evidence_id: 'failed-proof', requirement_id: 'req-1', evidence_type: 'TEST_FAIL', strength: 'CONTRADICTORY', summary: 'Fixture failed execution retained.', tool_call_id: 'failed-test', success: false, exit_code: 1, stale: false, superseded: false, timestamp: stamp, resolved_by: 'ev-1', recovery_evidence: 'recovery-proof' });
  r.data.evidence.push({ evidence_id: 'recovery-proof', requirement_id: 'req-1', evidence_type: 'RECOVERY_RESULT', strength: 'SUPPORTING', summary: 'Fixture recovery retest returned.', tool_call_id: null, success: null, exit_code: null, stale: false, superseded: false, timestamp: stamp });
  return { request: { requestId: r.request_id, prompt: 'Recovery fixture' }, timestamp: stamp, state: 'success', result: r, events: [], source: 'test_fixture' };
}
afterEach(cleanup);
it('accepts returned verified recovery with linked fresh passing execution and retained failure', () => {
  const i = recovered(); expect(completionPresentation(i).final).toBe('VERIFIED');
  const e = agentFixture('recovery-request', 'success'); e.data = i.result!;
  expect(validAgentEnvelope(e, 'recovery-request', 'request_agent_execution')).toBe(true);
  render(<RecoveryCard item={i} />); expect(screen.getByText(/Historical failure resolved/)).toBeTruthy();
  expect(screen.getByText('Recovery completed')).toBeTruthy();
});
it.each(['stale', 'superseded', 'foreign requirement', 'unexecuted', 'missing recovery', 'bad link', 'failed recovery', 'gate rejects'] as const)('refuses VERIFIED for a recovery fixture with %s', mode => {
  const i = recovered(), d = i.result!.data;
  const proof = d.evidence.find(e => e.evidence_id === 'ev-1')!;
  if (mode === 'stale') proof.stale = true;
  if (mode === 'superseded') proof.superseded = true;
  if (mode === 'foreign requirement') proof.requirement_id = 'other';
  if (mode === 'unexecuted') d.tool_results.find(t => t.tool_call_id === 'test-1')!.executed = false;
  if (mode === 'missing recovery') d.evidence = d.evidence.filter(e => e.evidence_type !== 'RECOVERY_RESULT');
  if (mode === 'bad link') d.evidence[0].resolved_by = 'not-present';
  if (mode === 'failed recovery') d.recovery!.status = 'FAILED';
  if (mode === 'gate rejects') d.verification!.overall_status = 'NOT_VERIFIED';
  expect(completionPresentation(i).final).not.toBe('VERIFIED');
  expect(activityPresentation(i).verified).toBe(false);
});
it('permits a stale superseded baseline only when fresh recovery proof and gate are verified', () => {
  const i = recovered(); i.result!.data.evidence.push({ ...i.result!.data.evidence.find(e => e.evidence_id === 'ev-1')!, evidence_id: 'baseline', tool_call_id: 'baseline-test', stale: true, superseded: true });
  expect(completionPresentation(i).final).toBe('VERIFIED');
});
it('records actual RETESTING and returned recovery result without claiming streaming', () => {
  const i = recovered(); i.events = [
    { request_id: i.request.requestId, sequence: 1, event_type: 'state_changed', current_state: 'RETESTING', tool_call_id: 'test-1', timestamp: stamp },
    { request_id: i.request.requestId, sequence: 2, event_type: 'recovery_finished', current_state: 'RECOVERING', tool_call_id: null, timestamp: stamp },
  ];
  const p = activityPresentation(i); expect(p.events[0].state).toBe('retesting');
  expect(p.events[0].provenance).toBe('RECORDED_ACTIVITY');
  expect(p.events[1].title).toBe('Recovery attempt returned: RECOVERED');
  expect(p.detail).toBe('CompletionGate returned VERIFIED.');
});
it('rejects unsafe resolution references at the IPC boundary', () => {
  const e = agentFixture('r', 'success'); e.data.data.evidence[0].resolved_by = 'secret=raw';
  expect(validAgentEnvelope(e, 'r', 'request_agent_execution')).toBe(false);
});

it('does not assign a later recovery outcome to earlier attempts or a pending new cycle', () => {
  const i = recovered(); i.events = [
    { request_id: i.request.requestId, sequence: 1, event_type: 'recovery_finished', current_state: 'RECOVERING', tool_call_id: 'earlier', timestamp: '2026-09-27T11:00:00Z' },
    { request_id: i.request.requestId, sequence: 2, event_type: 'recovery_finished', current_state: 'RECOVERING', tool_call_id: 'failed-test', timestamp: stamp },
  ];
  let p = activityPresentation(i);
  expect(p.events[0].title).toBe('Recovery attempt finished (outcome not supplied)');
  expect(p.events[1].title).toBe('Recovery attempt returned: RECOVERED');
  i.result!.data.recovery!.status = 'PERMISSION_REQUIRED';
  i.result!.data.recovery!.timestamp = '2026-09-27T13:00:00Z';
  p = activityPresentation(i);
  expect(p.events.every(e => e.title === 'Recovery attempt finished (outcome not supplied)')).toBe(true);
});
