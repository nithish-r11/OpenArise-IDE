import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { AIPanel } from '../src/components/AI/AIPanel';
import { useAI } from '../src/workspace/useAI';
import { agentFixture, stamp } from './ai-fixtures';
import { validAgentEnvelope } from '../shared/agent-response';
import { DesktopBackendService } from '../electron/backend-service';
import type { AIResult } from '../src/types/ai';

// Deterministic UI/provenance regressions, visibly labelled as fixtures.
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Failure fixture', rootPath: 'C:/Fixture' };
function Harness() {
  const ai = useAI(project);
  return <AIPanel ai={ai} project={project} blocked={false} expanded onToggle={() => {}} />;
}
function response(command: string, status: AIResult['status'] = 'failure') {
  const envelope = agentFixture(command, status), r = envelope.data;
  if (status === 'failure') {
    r.message = 'Fixture: mandatory whole-project retest failed; recovery rolled back.';
    r.data.tool_results = [{ tool_name: 'execute_tests', tool_call_id: 'retest', success: false, executed: true, exit_code: 1, timestamp: stamp }];
    r.data.verification!.overall_status = 'NOT_VERIFIED';
    r.data.verification!.requirement_results[0].status = 'NOT_VERIFIED';
  }
  r.data.recovery = { status: status === 'success' ? 'RECOVERED' : 'ROLLED_BACK', attempts: 1,
    final_result: status === 'success' ? 'Fixture: mandatory retest passed.' : 'Fixture: restored the checkpoint after the failed retest.', tests_run: ['retest'], timestamp: stamp };
  return envelope;
}
async function show(status: AIResult['status'] = 'failure') {
  window.openarise = { request: vi.fn(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: response(r.request_id, status) })) } as any;
  render(<Harness />);
  fireEvent.change(screen.getByLabelText('Ask OpenArise'), { target: { value: 'Deterministic failure fixture' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send ↗' }));
  await within(screen.getByLabelText('Final completion state')).findByText(status === 'success' ? 'VERIFIED' : 'FAILED');
}
afterEach(() => { cleanup(); delete window.openarise; vi.restoreAllMocks(); });

it('displays FAILED, ROLLED_BACK and exact NOT_VERIFIED gate without placeholders', async () => {
  expect(validAgentEnvelope(response('regression'), 'regression', 'request_agent_execution')).toBe(true);
  await show();
  const recovery = screen.getByLabelText('Failure and recovery');
  expect(recovery.getAttribute('data-state')).toBe('failed');
  expect(recovery.getAttribute('data-recovery-status')).toBe('ROLLED_BACK');
  expect(within(recovery).getByText('Recovery rolled back')).toBeTruthy();
  expect(within(recovery).getByText('ROLLED_BACK')).toBeTruthy();
  const verification = screen.getByLabelText('Verification and evidence');
  expect(verification.getAttribute('data-verification-status')).toBe('NOT_VERIFIED');
  expect(verification.querySelector('header')?.textContent).toContain('NOT_VERIFIED');
  expect(within(screen.getByLabelText('Returned backend states')).getByText('FAILED')).toBeTruthy();
  expect(verification.textContent).toContain('CompletionGate result: NOT_VERIFIED');
  expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
  expect(document.body.textContent).not.toContain('<actual result>');
});

it('retains successful returned recovery and VERIFIED CompletionGate', async () => {
  await show('success');
  expect(screen.getByLabelText('Failure and recovery').getAttribute('data-recovery-status')).toBe('RECOVERED');
  expect(screen.getByText('Recovery completed')).toBeTruthy();
  expect(screen.getByLabelText('Verification and evidence').getAttribute('data-verification-status')).toBe('VERIFIED');
  expect(screen.getByText('Verified by CompletionGate')).toBeTruthy();
});

it('shows fixture provenance beside fixture success and failed outcomes', async () => {
  await show();
  const source = screen.getByLabelText('AI data source');
  expect(source.textContent).toContain('TEST FIXTURE');
  expect(source.textContent).toContain('no live AI validation');
  expect(source.textContent).not.toContain('BACKEND RESPONSE');
  expect(screen.getByLabelText('Arise Activity Visualizer').getAttribute('data-source')).toBe('test_fixture');
});

it('test adapter cannot relabel its fixture response as production backend data', async () => {
  const adapter = { connect: vi.fn(), disconnect: vi.fn(), request: vi.fn(async () => ({ kind: 'backend' as const, source: 'backend' as const, response: response('regression') })) };
  const service = new DesktopBackendService(adapter, 'test_fixture');
  expect(await service.request({ request_id: 'regression', method: 'request_agent_execution', params: { prompt: 'Fixture only' } })).toMatchObject({ source: 'test_fixture', response: { data: { status: 'failure', data: { recovery: { status: 'ROLLED_BACK' } } } } });
});
