import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AIPanel } from '../src/components/AI/AIPanel';
import { useAI } from '../src/workspace/useAI';
import { agentFixture, stamp } from './ai-fixtures';
import intelligence from './fixtures/intelligence.json';
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Orbit', rootPath: 'C:/Orbit' };
let request: ReturnType<typeof vi.fn>;
function Harness({ blocked = false }: { blocked?: boolean }) {
  const ai = useAI(project);
  return <AIPanel ai={ai} project={project} blocked={blocked} expanded onToggle={() => {}} />;
}
beforeEach(() => {
  request = vi.fn(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id) }));
  window.openarise = { request } as any;
});
afterEach(() => { cleanup(); delete window.openarise; });
const draft = (text = 'Implement a focused change') => fireEvent.change(screen.getByLabelText('Ask OpenArise'), { target: { value: text } });
const send = () => fireEvent.click(screen.getByRole('button', { name: 'Send ↗' }));
describe('AI workspace', () => {
  it('shows empty state, existing logo, context placeholder and disabled empty submit', () => {
    render(<Harness />);
    expect(screen.getByText('What shall we build?')).toBeTruthy();
    expect(screen.getByAltText('OpenArise IDE')).toBeTruthy();
    expect(screen.getByText('Context not loaded')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Send ↗' }) as HTMLButtonElement).disabled).toBe(true);
    expect(request).not.toHaveBeenCalled();
  });
  it('keeps multiline draft with Shift+Enter and submits with Enter preserving request ID', async () => {
    render(<Harness />); draft('First line\nSecond line');
    fireEvent.keyDown(screen.getByLabelText('Ask OpenArise'), { key: 'Enter', shiftKey: true });
    expect(request).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByLabelText('Ask OpenArise'), { key: 'Enter' });
    await within(screen.getByLabelText('AI result')).findByText('Not verified');
    const [envelope, selected] = request.mock.calls[0];
    expect(selected).toBe(project.id); expect(envelope.params).toEqual({ prompt: 'First line\nSecond line' });
    expect(envelope.request_id).toMatch(/^[a-f0-9-]{36}$/);
    expect(screen.getByLabelText('AI result').textContent).toContain('Recorded backend result');
  });
  it('clears a draft without submitting', () => {
    render(<Harness />); draft(); fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect((screen.getByLabelText('Ask OpenArise') as HTMLTextAreaElement).value).toBe('');
    expect(request).not.toHaveBeenCalled();
  });
  it('prevents duplicate submits while in flight and does not invent activity', async () => {
    let complete!: (v: any) => void;
    request.mockImplementation(() => new Promise(r => { complete = r; }));
    render(<Harness />); draft(); send();
    fireEvent.keyDown(screen.getByLabelText('Ask OpenArise'), { key: 'Enter' });
    expect(request).toHaveBeenCalledTimes(1);
    expect(within(screen.getByLabelText('AI result')).getByText('Working…')).toBeTruthy();
    expect(screen.queryByLabelText('AI data source')).toBeNull();
    expect(screen.queryByText(/Recorded activity/)).toBeNull();
    expect(screen.getByText(/You can cancel at the next permission request/)).toBeTruthy();
    const result = agentFixture(request.mock.calls[0][0].request_id); result.events = [];
    complete({ kind: 'backend', source: 'test_fixture', response: result });
    await within(screen.getByLabelText('AI result')).findByText('Not verified');
    expect(screen.queryByText(/Recorded activity/)).toBeNull();
  });
  it('retains prompt and shows backend unavailable without claiming success', async () => {
    request.mockResolvedValue({ kind: 'unavailable', code: 'transport_error', message: 'Backend is unavailable.', request_id: 'x' });
    render(<Harness />); draft('Keep my request'); send();
    await screen.findByText('backend unavailable');
    expect((screen.getByLabelText('Ask OpenArise') as HTMLTextAreaElement).value).toBe('Keep my request');
    expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
  });
  it.each([['success', 'Verified'], ['unverified', 'Not verified'], ['failure', 'Failed'], ['denied', 'Denied'], ['cancelled', 'Cancelled']] as const)('renders %s independently of outer success', async (status, label) => {
    request.mockImplementation(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id, status) }));
    render(<Harness />); draft(); send();
    await within(screen.getByLabelText('AI result')).findByText(label);
    expect(!!screen.queryByText('Verified by CompletionGate')).toBe(status === 'success');
    if (status === 'failure') expect((screen.getByLabelText('Ask OpenArise') as HTMLTextAreaElement).value).not.toBe('');
  });
  it('delegates Allow to backend approval then separate resume with retained target/tool IDs', async () => {
    request.mockImplementation(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id,
      r.method === 'request_agent_execution' ? 'permission_required' : r.method === 'approve_agent_action' ? 'approved' : 'unverified',
      r.params.request_id ?? r.request_id) }));
    render(<Harness />); draft(); send();
    await screen.findByText('OpenArise needs permission');
    expect(screen.getByText('WRITE · write_file')).toBeTruthy();
    expect(screen.getByText('app/main.py')).toBeTruthy();
    expect(request).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    await within(screen.getByLabelText('AI result')).findByText('Not verified');
    expect(request.mock.calls.map(([r]) => r.method)).toEqual(['request_agent_execution', 'approve_agent_action', 'resume_agent_execution']);
    expect(request.mock.calls[1][0].params).toEqual({ request_id: request.mock.calls[0][0].request_id, tool_call_id: 'tool-1' });
    expect(request.mock.calls[2][0].params).toEqual(request.mock.calls[1][0].params);
    expect(new Set(request.mock.calls.map(([r]) => r.request_id)).size).toBe(3);
  });
  it.each(['Deny', 'Cancel'] as const)('delegates %s without resuming', async button => {
    request.mockImplementation(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: agentFixture(r.request_id,
      r.method === 'request_agent_execution' ? 'permission_required' : button === 'Deny' ? 'denied' : 'cancelled', r.params.request_id ?? r.request_id) }));
    render(<Harness />); draft(); send(); await screen.findByText('OpenArise needs permission');
    fireEvent.click(screen.getByRole('button', { name: button }));
    await within(screen.getByLabelText('AI result')).findByText(button === 'Deny' ? 'Denied' : 'Cancelled');
    expect(request.mock.calls.at(-1)![0].method).toBe(button === 'Deny' ? 'deny_agent_action' : 'cancel_agent_execution');
    expect(request).toHaveBeenCalledTimes(2);
  });
  it.each(['tool_call_id', 'tool_name', 'risk_level', 'resource', 'approved'] as const)('does not resume a mismatched approval %s', async field => {
    request.mockImplementation(async (r: any) => {
      const response = agentFixture(r.request_id, r.method === 'request_agent_execution' ? 'permission_required' : 'approved', r.params.request_id ?? r.request_id);
      if (r.method === 'approve_agent_action') {
        Object.assign(response.data.pending_action!, { [field]: { tool_call_id: 'other-tool', tool_name: 'execute_python', risk_level: 'EXECUTE', resource: 'other.py', approved: false }[field] });
      }
      return { kind: 'backend', source: 'test_fixture', response };
    });
    render(<Harness />); draft(); send(); await screen.findByText('OpenArise needs permission');
    fireEvent.click(screen.getByRole('button', { name: 'Allow' }));
    await screen.findAllByText('Approval did not match the reviewed action. Execution was not resumed.');
    expect(request.mock.calls.map(([r]) => r.method)).toEqual(['request_agent_execution', 'approve_agent_action']);
  });
  it('shows only backend-reported recovery activity without assuming recovery success', async () => {
    request.mockImplementation(async (r: any) => {
      const response = agentFixture(r.request_id, 'failure');
      response.events = [{ request_id: r.request_id, sequence: 1, event_type: 'recovery_finished', current_state: 'RECOVERING', tool_call_id: null, timestamp: stamp }];
      response.data.data.verification!.report.recovery_attempts = 1;
      return { kind: 'backend', response };
    });
    render(<Harness />); draft(); send();
    await screen.findByText('Recovery attempt finished (outcome not supplied)');
    expect(screen.getByText(/1 recovery attempt/)).toBeTruthy();
    expect(screen.queryByText('Recovery succeeded')).toBeNull();
  });
  it('loads bounded context counts and environment with fixed read methods', async () => {
    request.mockImplementation(async (r: any) => ({ kind: 'backend', source: 'test_fixture', response: { request_id: r.request_id, success: true, action_state: 'completed', error: null, events: [],
      data: r.method === 'refresh_workspace' ? { ...intelligence.get_intelligence_snapshot, intelligence_summary: { ...intelligence.get_intelligence_snapshot.intelligence_summary, total_files: 4, requirements_count: 2, health_issues: 1, traceability_nodes: 3 } } :
      { python_available: true, python_version: '3.13.5', virtualenv_present: false, virtualenv_usable: false, inspection_scope: 'current_environment' } } }));
    render(<Harness />); fireEvent.click(screen.getByRole('button', { name: 'Refresh context' }));
    await screen.findByText(/4 files · 2 requirements/);
    expect(screen.getByText(/1 health findings · 3 traceability nodes/)).toBeTruthy();
    expect(screen.getByText(/Backend Python 3.13.5/)).toBeTruthy();
    expect(request.mock.calls.map(([r]) => r.method)).toEqual(['refresh_workspace', 'get_environment_status']);
  });
  it('retains session history and can select earlier results', async () => {
    render(<Harness />); draft('First'); send(); await within(screen.getByLabelText('AI result')).findByText('Not verified');
    draft('Second'); send();
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(2));
    const first = request.mock.calls[0][0].request_id;
    fireEvent.change(screen.getByLabelText('Session history'), { target: { value: first } });
    expect(screen.getByText('First')).toBeTruthy();
  });
  it('blocks submission with unsaved editor state', () => {
    render(<Harness blocked />); draft(); send();
    expect(request).not.toHaveBeenCalled();
    expect(screen.getByText(/Save or discard editor changes/)).toBeTruthy();
  });
});
