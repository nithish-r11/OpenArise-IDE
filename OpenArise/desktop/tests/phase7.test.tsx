import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { AIPanel } from '../src/components/AI/AIPanel';
import { useAI } from '../src/workspace/useAI';
import { DesktopBackendService } from '../electron/backend-service';
import { validAgentEnvelope } from '../shared/agent-response';
import { agentFixture, stamp } from './ai-fixtures';
import type { AIResult } from '../src/types/ai';
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Orbit', rootPath: 'C:/Orbit' };
let request: ReturnType<typeof vi.fn>;
function Harness({ selected = project }: { selected?: typeof project }) {
  const ai = useAI(selected);
  return <AIPanel ai={ai} project={selected} blocked={false} expanded onToggle={() => {}} />;
}
function respond(status: AIResult['status'], mutate?: (data: AIResult) => void) {
  request.mockImplementation(async (r: any) => {
    const response = agentFixture(r.request_id, status, r.params.request_id ?? r.request_id);
    mutate?.(response.data); response.action_state = response.data.action_state;
    return { kind: 'backend', source: 'test_fixture', response };
  });
}
const send = () => { fireEvent.change(screen.getByLabelText('Ask OpenArise'), { target: { value: 'Phase 7 fixture request' } }); fireEvent.click(screen.getByRole('button', { name: 'Send ↗' })); };
const final = () => within(screen.getByLabelText('Final completion state'));
beforeEach(() => { request = vi.fn(); respond('unverified'); window.openarise = { request } as any; });
afterEach(() => { cleanup(); delete window.openarise; vi.restoreAllMocks(); });

describe('Phase 7 fixture UI (no live Ollama)', () => {
  it.each(['WRITE', 'EXECUTE'] as const)('requires explicit permission for %s with safe tool/scope and pending verification', async risk => {
    respond('permission_required', d => { d.pending_action!.risk_level = risk; d.pending_action!.tool_name = risk === 'WRITE' ? 'write_file' : 'execute_tests'; });
    render(<Harness />); send();
    await screen.findByText('OpenArise needs permission');
    const card = screen.getByLabelText('Permission request');
    expect(card.textContent).toContain(risk === 'WRITE' ? 'Allow OpenArise to change this file?' : 'Allow this project command to run?');
    expect(card.textContent).toContain(risk === 'WRITE' ? 'WRITE · write_file' : 'EXECUTE · execute_tests');
    expect(card.textContent).toContain('app/main.py');
    expect(screen.getByLabelText('Verification and evidence').getAttribute('data-state')).toBe('pending');
    expect(final().getByText('BLOCKED')).toBeTruthy();
    expect(request).toHaveBeenCalledTimes(1);
    expect(within(screen.getByLabelText('AI data source')).getByText('TEST FIXTURE')).toBeTruthy();
    expect(screen.getByLabelText('Arise Activity Visualizer').getAttribute('data-source')).toBe('test_fixture');
  });
  it('shows missing scope without accepting arbitrary tool names or code', async () => {
    respond('permission_required', d => { d.pending_action!.resource = null; });
    render(<Harness />); send(); await screen.findByText('Selected project · exact resource not reported');
    const bad = agentFixture('bad', 'permission_required');
    bad.data.pending_action!.tool_name = '<script>run()</script>';
    expect(validAgentEnvelope(bad, 'bad', 'request_agent_execution')).toBe(false);
  });
  it('allows once, displays pending decision/resume, and retains completed permission information', async () => {
    let resolve!: (v: any) => void;
    request.mockImplementation(async (r: any) => {
      if (r.method === 'approve_agent_action') return new Promise(v => { resolve = v; });
      return { kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id, r.method === 'request_agent_execution' ? 'permission_required' : 'unverified', r.params.request_id ?? r.request_id) };
    });
    render(<Harness />); send(); await screen.findByText('OpenArise needs permission');
    fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText('Permission request').getAttribute('data-state')).toBe('pending');
    for (const name of ['Allow', 'Deny', 'Cancel']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true);
    const command = request.mock.calls[1][0];
    resolve({ kind: 'backend', source: 'test_fixture', response: agentFixture(command.request_id, 'approved', command.params.request_id) });
    await screen.findByText('Action completed');
    expect(request.mock.calls.map(([r]) => r.method)).toEqual(['request_agent_execution', 'approve_agent_action', 'resume_agent_execution']);
    expect(request.mock.calls[2][0].params).toEqual(command.params);
    expect(final().getByText('INCONCLUSIVE')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Allow' })).toBeNull();
  });
  it.each(['Deny', 'Cancel'] as const)('shows pending and returned %s and prevents duplicate actions', async name => {
    let resolve!: (v: any) => void;
    request.mockImplementation(async (r: any) => r.method === 'request_agent_execution'
      ? { kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id, 'permission_required') }
      : new Promise(v => { resolve = v; }));
    render(<Harness />); send(); await screen.findByText('OpenArise needs permission');
    fireEvent.click(screen.getByRole('button', { name })); fireEvent.click(screen.getByRole('button', { name }));
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText('Permission request').getAttribute('data-state')).toBe('pending');
    const command = request.mock.calls[1][0];
    resolve({ kind: 'backend', source: 'test_fixture', response: agentFixture(command.request_id, name === 'Deny' ? 'denied' : 'cancelled', command.params.request_id) });
    await waitFor(() => expect(screen.getByLabelText('Permission request').getAttribute('data-state')).toBe(name === 'Deny' ? 'denied' : 'cancelled'));
    expect(final().getByText(name === 'Deny' ? 'DENIED' : 'CANCELLED')).toBeTruthy();
    expect(request.mock.calls.at(-1)![0].method).toBe(name === 'Deny' ? 'deny_agent_action' : 'cancel_agent_execution');
    expect(request).toHaveBeenCalledTimes(2);
  });
  it('shows a rejected approval without resuming or presenting completion', async () => {
    request.mockImplementation(async (r: any) => r.method === 'request_agent_execution'
      ? { kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id, 'permission_required') }
      : { kind: 'unavailable', request_id: r.request_id, code: 'transport_error', message: 'Fixture transport lost.' });
    render(<Harness />); send(); await screen.findByText('OpenArise needs permission'); fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    await screen.findByText('The last decision is unconfirmed. Refresh the request before allowing execution.');
    expect(final().getByText('UNAVAILABLE')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Allow' }) as HTMLButtonElement).disabled).toBe(true);
    expect(request).toHaveBeenCalledTimes(2);
  });
  it('never resumes an approval returned after the project selection changes', async () => {
    let resolve!: (v: any) => void;
    request.mockImplementation(async (r: any) => r.method === 'request_agent_execution'
      ? { kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id, 'permission_required') }
      : new Promise(v => { resolve = v; }));
    const view = render(<Harness />); send(); await screen.findByText('OpenArise needs permission'); fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    view.rerender(<Harness selected={{ ...project, id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' }} />);
    const command = request.mock.calls[1][0]; resolve({ kind: 'backend', source: 'test_fixture', response: agentFixture(command.request_id, 'approved', command.params.request_id) });
    await waitFor(() => expect(screen.getByText('What shall we build?')).toBeTruthy());
    expect(request).toHaveBeenCalledTimes(2);
  });
  it('shows returned failure category, severity and diagnosis without treating dispatch success as success', async () => {
    respond('failure', d => { d.data.failure = { category: 'SYNTAX_ERROR', severity: 'ERROR', summary: 'Fixture syntax failure.', root_cause: 'Fixture diagnosis: missing delimiter.', tool_name: 'execute_python' }; });
    render(<Harness />); send(); await screen.findByText('Fixture syntax failure.');
    expect(screen.getByText('SYNTAX_ERROR')).toBeTruthy(); expect(screen.getByText('ERROR')).toBeTruthy(); expect(screen.getByText('Fixture diagnosis: missing delimiter.')).toBeTruthy();
    expect(final().getByText('FAILED')).toBeTruthy();
    expect(screen.getByLabelText('Failure and recovery').getAttribute('data-state')).toBe('unavailable');
  });
  it('keeps missing recovery, category and severity explicitly unavailable', async () => {
    respond('failure'); render(<Harness />); send();
    await screen.findByText('Recovery details are unavailable in this response.');
    expect(within(screen.getByLabelText('Failure and recovery')).getAllByText('Not reported')).toHaveLength(2);
    expect(screen.queryByText('Recovery completed')).toBeNull();
  });
  it('shows recorded recovery attempts without inferring their outcome', async () => {
    request.mockImplementation(async (r: any) => { const response = agentFixture(r.request_id, 'failure'); response.data.data.verification!.report.recovery_attempts = 1;
      response.events = [{ request_id: r.request_id, sequence: 1, event_type: 'recovery_finished', current_state: 'RECOVERING', tool_call_id: null, timestamp: stamp }];
      return { kind: 'backend', source: 'test_fixture', response }; });
    render(<Harness />); send();
    await screen.findByText(/A recorded recovery attempt has no separately returned outcome/);
    expect(screen.getByLabelText('Failure and recovery').getAttribute('data-state')).toBe('attempted');
    expect(screen.getByText('Recovery attempt finished (outcome not supplied)')).toBeTruthy();
    expect(screen.queryByText('Recovery completed')).toBeNull();
  });
  it.each([['RECOVERED', 'completed'], ['BLOCKED', 'blocked'], ['RETESTING', 'pending'], ['FAILED', 'failed']] as const)('shows explicitly returned recovery %s as %s without verifying completion', async (status, state) => {
    respond('unverified', d => { d.data.recovery = { status, attempts: 1, final_result: 'Fixture recovery outcome.', tests_run: ['Fixture retest recorded'], timestamp: stamp }; });
    render(<Harness />); send(); await screen.findByText('Fixture recovery outcome.');
    expect(screen.getByLabelText('Failure and recovery').getAttribute('data-state')).toBe(state);
    expect(screen.getByText('Fixture retest recorded')).toBeTruthy();
    expect(final().getByText('INCONCLUSIVE')).toBeTruthy();
  });
  it('renders an unverified gate with requirement coverage and missing evidence', async () => {
    render(<Harness />); send(); await final().findByText('INCONCLUSIVE');
    expect(screen.getByText('Tracked requirement')).toBeTruthy(); expect(screen.getByText('Requires direct test or file evidence')).toBeTruthy();
    expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
  });
  it('renders a consistent verified fixture with tests and gate result', async () => {
    respond('success'); render(<Harness />); send(); await final().findByText('VERIFIED');
    expect(screen.getByText('Verified by CompletionGate')).toBeTruthy(); expect(screen.getByText(/Passed execution/)).toBeTruthy();
    expect(screen.getByText(/Test executions are backend test-tool calls/)).toBeTruthy();
    expect(screen.getByLabelText('Arise Activity Visualizer').getAttribute('data-state')).toBe('completed');
  });
  it.each(['gate', 'stale', 'failed evidence', 'missing evidence', 'zero requirements', 'lifecycle', 'denied', 'superseded failure', 'missing coverage', 'remaining issues'] as const)('CompletionGate display prevents false DONE with %s', async mode => {
    respond('success', d => {
      if (mode === 'gate') d.data.verification!.overall_status = 'INCONCLUSIVE';
      if (mode === 'superseded failure') { d.data.evidence[0].success = false; d.data.evidence[0].superseded = true; }
      if (mode === 'missing coverage') d.data.verification!.requirement_results = [];
      if (mode === 'remaining issues') d.data.verification!.remaining_issues = ['Outstanding issue'];
      if (mode === 'stale') d.data.evidence[0].stale = true;
      if (mode === 'failed evidence') d.data.evidence[0].success = false;
      if (mode === 'missing evidence') d.data.verification!.requirement_results[0].missing_evidence = ['Invalid evidence reference: missing'];
      if (mode === 'zero requirements') d.data.verification!.report.total_requirements = 0;
      if (mode === 'lifecycle') d.current_state = 'VERIFYING';
      if (mode === 'denied') { d.status = 'denied'; d.action_state = 'denied'; d.current_state = 'DENIED'; }
    });
    render(<Harness />); send(); await waitFor(() => expect(final().queryByText('VERIFIED')).toBeNull());
    await waitFor(() => expect(screen.getByLabelText('AI result').textContent).toContain('Recorded backend result.'));
    expect(final().queryByText('VERIFIED')).toBeNull(); expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
    expect(screen.getByLabelText('Arise Activity Visualizer').getAttribute('data-state')).not.toBe('completed');
    expect(document.querySelector('.activity-symbol')?.textContent).not.toBe('✓');
    expect(screen.getByRole('option').textContent?.startsWith('Verified ·')).toBe(false);
  });
  it('shows stale and invalid evidence plus explicit failure flags', async () => {
    respond('unverified', d => {
      d.data.verification!.requirement_results[0].missing_evidence = ['Stale evidence: ev-stale', 'Invalid evidence reference: ev-missing'];
      d.data.evidence = [{ evidence_id: 'ev-stale', requirement_id: 'req-1', evidence_type: 'TEST_FAIL', strength: 'CONTRADICTORY', summary: 'Fixture failed evidence.', tool_call_id: 't-1', success: false, exit_code: 1, stale: true, superseded: false, timestamp: stamp }];
    });
    render(<Harness />); send(); await screen.findByText('Stale evidence: ev-stale');
    expect(screen.getByText('Invalid evidence reference: ev-missing')).toBeTruthy();
    expect(screen.getByText('Stale evidence')).toBeTruthy(); expect(screen.getByText('Failed / contradictory evidence')).toBeTruthy();
    expect(final().getByText('FAILED')).toBeTruthy();
  });
  it('does not reuse an earlier verified outcome after refresh fails', async () => {
    respond('success'); render(<Harness />); send(); await final().findByText('VERIFIED');
    request.mockResolvedValue({ kind: 'unavailable', request_id: 'x', code: 'transport_error', message: 'Fixture refresh unavailable.' });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh request result' }));
    await final().findByText('UNAVAILABLE');
    expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
    expect(screen.getByLabelText('Verification and evidence').getAttribute('data-state')).toBe('unavailable');
  });
  it.each(['backend', undefined] as const)('labels explicit %s source independently of fixture validation', async source => {
    request.mockImplementation(async (r: any) => ({ kind: 'backend', source, response: agentFixture(r.request_id) }));
    render(<Harness />); send(); await final().findByText('INCONCLUSIVE');
    const label = screen.getByLabelText('AI data source');
    expect(label.textContent).toContain(source ? 'Local AI' : 'SOURCE NOT REPORTED');
    expect(label.textContent).not.toContain('TEST FIXTURE');
  });
  it('main owns fixture provenance and overrides adapter claims', async () => {
    const adapter = { connect: vi.fn(), disconnect: vi.fn(), request: vi.fn().mockResolvedValue({ kind: 'backend', source: 'backend', response: agentFixture('one') }) };
    const service = new DesktopBackendService(adapter, 'test_fixture');
    expect(await service.request({ request_id: 'one', method: 'request_agent_execution', params: { prompt: 'Fixture' } })).toMatchObject({ source: 'test_fixture' });
  });
  it.each([1320, 1050, 760])('retains permission/verification controls at viewport width %i (geometry is checked in Electron)', async width => {
    Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
    respond('permission_required'); render(<Harness />); send(); await screen.findByText('OpenArise needs permission');
    expect(screen.getByRole('button', { name: 'Allow' })).toBeTruthy(); expect(screen.getByRole('button', { name: 'Deny' })).toBeTruthy(); expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
    expect(screen.getByLabelText('AI workspace').classList.contains('ai-expanded')).toBe(true);
    expect(readFileSync('src/styles/ai.css', 'utf8')).toContain('calc(100% - 65px)');
    expect(readFileSync('src/styles/outcomes.css', 'utf8')).toContain('flex-wrap: wrap');
  });
  it('rejects raw recovery metadata, malformed evidence and unknown severity at the response boundary', () => {
    const base = agentFixture('safe');
    for (const mutation of [
      (d: any) => { d.data.recovery = { status: 'RECOVERED', attempts: 1, final_result: 'Safe', tests_run: [], timestamp: stamp, command: 'cmd.exe' }; },
      (d: any) => { d.data.failure = { category: 'UNKNOWN', severity: 'SECRET', summary: 'Safe', root_cause: null, tool_name: null }; },
      (d: any) => { d.data.evidence = Array(41).fill({}); },
      (d: any) => { d.data.verification.requirement_results[0].raw_output = 'private'; },
    ]) { const bad = structuredClone(base); mutation(bad.data); expect(validAgentEnvelope(bad, 'safe', 'request_agent_execution')).toBe(false); }
  });
});
