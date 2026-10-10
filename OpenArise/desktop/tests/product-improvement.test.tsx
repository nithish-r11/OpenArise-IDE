import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { AIPanel } from '../src/components/AI/AIPanel';
import { Explorer } from '../src/components/Explorer';
import { useWorkspace } from '../src/workspace/useWorkspace';
import { resultSummary } from '../src/workspace/resultSummary';
import { completionPresentation } from '../src/workspace/completion';
import { PermissionCard } from '../src/components/AI/PermissionCard';
import { validAgentEnvelope } from '../shared/agent-response';
import { agentFixture } from './ai-fixtures';
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Actual project', rootPath: 'C:/actual' };
const item = (status: any = 'unverified') => ({ request: { requestId: 'r', prompt: 'Inspect the files.' }, timestamp: '', state: status, events: [], result: agentFixture('r', status).data, source: 'test_fixture' as const });
afterEach(cleanup);
it('requires reviewed npm script metadata and rejects arbitrary executable fields', () => {
  const response = agentFixture('r', 'permission_required');
  response.data.pending_action!.risk_level = 'EXECUTE'; response.data.pending_action!.tool_name = 'build_project';
  response.data.pending_action!.resource = 'frontend/package.json';
  const i = { ...item('permission_required'), result: response.data };
  const command = vi.fn();
  const view = render(<PermissionCard item={i} busy={false} blocked={false} command={command} inFlight={undefined} />);
  expect((screen.getByRole('button', { name: 'Allow' }) as HTMLButtonElement).disabled).toBe(true);
  response.data.pending_action!.command = { label: 'npm run build', script: 'vite build', revision: 'b'.repeat(64) };
  view.rerender(<PermissionCard item={i} busy={false} blocked={false} command={command} inFlight={undefined} />);
  expect(validAgentEnvelope(response, 'r', 'request_agent_execution')).toBe(true);
  expect(screen.getByText('vite build')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Allow' })); expect(command).toHaveBeenCalledWith('allow', false);
  (response.data.pending_action!.command as any).executable = 'cmd.exe';
  expect(validAgentEnvelope(response, 'r', 'request_agent_execution')).toBe(false);
});
it('puts the answer first while keeping authoritative unverified details collapsed', () => {
  const current = item(); current.result.data.model_response = 'This project has a React UI and Python API, as shown in frontend/main.tsx and backend/main.py.';
  render(<AIPanel project={project} blocked={false} expanded onToggle={() => {}} ai={{ current, items: [], contextState: 'not_loaded', prompt: '', mode: 'text_only', busy: false, setPrompt: vi.fn(), command: vi.fn() } as any} />);
  expect(screen.getByLabelText('Model response').textContent).toContain('backend/main.py');
  expect(document.querySelector('.ai-result>strong')?.textContent).toBe('Answer');
  expect(document.querySelector<HTMLDetailsElement>('.ai-technical')?.open).toBe(false);
  expect(screen.getByLabelText('Final completion state').closest('details')).toBe(document.querySelector('.ai-technical'));
  expect(screen.getByLabelText('Final completion state').textContent).toContain('INCONCLUSIVE');
  expect(screen.getByText('TEST FIXTURE')).toBeTruthy();
});
it.each(['unverified', 'failure', 'denied', 'cancelled'] as const)('never simplifies %s into verified', status => {
  const i = item(status);
  expect(resultSummary(i).title).not.toBe('Verified');
  expect(completionPresentation(i).final).not.toBe('VERIFIED');
});
it('uses rolled back only for actual returned rollback, and keeps failed gate', () => {
  const i = item('failure');
  i.result.data.recovery = { status: 'ROLLED_BACK', attempts: 1, final_result: 'Rolled back.', tests_run: [], timestamp: '2026-10-08T00:00:00Z' };
  expect(resultSummary(i).title).toBe('Rolled back');
  expect(completionPresentation(i).final).toBe('FAILED');
  i.result.data.recovery.status = 'FAILED'; expect(resultSummary(i).title).toBe('Failed');
});
it('keeps build evidence distinct from tests across the completion projection', () => {
  const i = item('success'); i.result.data.evidence[0].evidence_type = 'BUILD_PASS';
  i.result.data.tool_results[0].tool_name = 'build_project'; i.result.data.verification!.report.tests_executed = 0;
  expect(resultSummary(i).title).toBe('Verified');
  i.result.data.evidence[0].stale = true; expect(resultSummary(i).title).not.toBe('Verified');
});
it('creates an actual requested folder and retains the exact reviewed rename revision', async () => {
  const create = vi.fn(async () => true), rename = vi.fn(async () => true);
  const bridge = { listDirectory: vi.fn(async () => ({ ok: true, data: [{ path: 'src', name: 'src', kind: 'folder' }] })), inspectRename: vi.fn(async () => ({ ok: true, data: { path: 'src', kind: 'folder', revision: 'b'.repeat(64) } })) };
  render(<Explorer project={project} bridge={bridge as any} active="" opening={false} onOpen={() => {}} onCreateFolder={create} onRename={rename} />);
  fireEvent.click(screen.getByRole('button', { name: 'New folder' }));
  fireEvent.change(screen.getByLabelText('New folder in this project'), { target: { value: 'components' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create folder' }));
  await act(async () => {}); expect(create).toHaveBeenCalledWith('components');
  fireEvent.click(await screen.findByRole('button', { name: /src$/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Rename selected path' }));
  fireEvent.change(await screen.findByLabelText('New name or relative path'), { target: { value: 'source' } });
  fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
  await act(async () => {}); expect(rename).toHaveBeenCalledWith({ path: 'src', kind: 'folder', revision: 'b'.repeat(64) }, 'source');
});
it('blocks rename with unsaved edits and prevents duplicate folder submissions', async () => {
  let resolve!: (v: any) => void;
  const bridge = { openProject: async () => ({ ok: true, data: project }), setDirty: async () => {}, observeProject: async () => ({ ok: true, data: {} }),
    readFile: async () => ({ ok: true, data: { path: 'main.py', revision: 'a'.repeat(64), content: 'original', readOnly: false } }),
    renamePath: vi.fn(), createFolder: vi.fn(() => new Promise(r => { resolve = r; })) };
  const { result } = renderHook(() => useWorkspace(bridge as any));
  await act(async () => { await result.current.openProject(); await result.current.openFile('main.py'); });
  act(() => result.current.change('main.py', 'unsaved'));
  await act(async () => { expect(await result.current.renamePath({ path: 'main.py', kind: 'file', revision: 'a'.repeat(64) }, 'new.py')).toBe(false); });
  expect(bridge.renamePath).not.toHaveBeenCalled(); expect(result.current.tabs[0].content).toBe('unsaved');
  let first!: Promise<boolean>;
  act(() => { first = result.current.createFolder('folder'); void result.current.createFolder('folder'); });
  expect(bridge.createFolder).toHaveBeenCalledTimes(1);
  await act(async () => { resolve({ ok: true, data: { path: 'folder', kind: 'folder' } }); await first; });
});
