import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Explorer } from '../src/components/Explorer';
import { ProjectCapabilities } from '../src/components/ProjectCapabilities';
import { validCapabilities } from '../shared/capabilities';
import { validTerminalRequest } from '../shared/terminal-ipc';
import { editorLanguage } from '../src/editor/language';
import { completionPresentation } from '../src/workspace/completion';
import { agentFixture } from './ai-fixtures';
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'actual', rootPath: 'C:/actual' };
afterEach(cleanup);
it('searches actual returned project files, handles empty results and keeps paths visible', async () => {
  const bridge = { listDirectory: vi.fn(async () => ({ ok: true, data: [] })), searchFiles: vi.fn(async () => ({ ok: true, data: [{ name: 'App.tsx', path: 'frontend/src/App.tsx', kind: 'file' }] })) };
  const open = vi.fn();
  render(<Explorer project={project} bridge={bridge as any} active="" onOpen={open} opening={false} />);
  fireEvent.change(screen.getByLabelText('Search project filenames'), { target: { value: 'App' } });
  fireEvent.click(await screen.findByRole('button', { name: /frontend\/src\/App.tsx/ }));
  expect(open).toHaveBeenCalledWith('frontend/src/App.tsx');
  expect(bridge.searchFiles).toHaveBeenCalledWith({ projectId: project.id, query: 'App' });
  bridge.searchFiles.mockResolvedValue({ ok: true, data: [] });
  fireEvent.change(screen.getByLabelText('Search project filenames'), { target: { value: 'absent' } });
  await screen.findByText('0 matches');
});
it('creates only a reviewed relative path and exposes cancel and pending states', async () => {
  const create = vi.fn(async () => true), refresh = vi.fn();
  const bridge = { listDirectory: vi.fn(async () => ({ ok: true, data: [] })) };
  render(<Explorer project={project} bridge={bridge as any} active="" onOpen={() => {}} opening={false} onCreate={create} onRefresh={refresh} />);
  fireEvent.click(screen.getByRole('button', { name: 'New file' }));
  fireEvent.change(screen.getByLabelText('New file in this project'), { target: { value: '../outside.py' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create file' }));
  expect(create).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('New file in this project'), { target: { value: 'frontend/view.tsx' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create file' }));
  await waitFor(() => expect(create).toHaveBeenCalledWith('frontend/view.tsx'));
  await waitFor(() => expect(screen.queryByLabelText('New file in this project')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'Refresh Explorer' })); expect(refresh).toHaveBeenCalledOnce();
});
it('shows capability scan and unavailable states without inventing a technology', () => {
  const view = render(<ProjectCapabilities loading blocked={false} onCommand={() => {}} />);
  expect(screen.getByRole('status').textContent).toContain('Scanning');
  view.rerender(<ProjectCapabilities loading={false} blocked={false} onCommand={() => {}} />);
  expect(screen.getByText(/Capabilities not loaded/)).toBeTruthy();
  expect(screen.queryByText('React')).toBeNull();
});
it('rejects command executable overrides and arbitrary shell commands across IPC', () => {
  const request = { projectId: project.id, sessionId: project.id, operation: 'executeCapability', capabilityId: 'a'.repeat(24) };
  expect(validTerminalRequest(request)).toBe(true);
  expect(validTerminalRequest({ ...request, command: 'npm install' })).toBe(false);
  expect(validTerminalRequest({ ...request, executable: 'cmd.exe' })).toBe(false);
  expect(validTerminalRequest({ ...request, capabilityId: '../shell' })).toBe(false);
  expect(validCapabilities({ projectType: 'React' })).toBe(false);
});
it.each([['main.py', 'python'], ['App.tsx', 'typescript'], ['app.jsx', 'javascript'], ['index.html', 'html'], ['site.css', 'css'], ['package.json', 'json']])('selects bundled syntax for %s', (file, language) => expect(editorLanguage(file)).toBe(language));
it.each([['unverified', 'INCONCLUSIVE'], ['denied', 'DENIED'], ['cancelled', 'CANCELLED']] as const)('preserves the exact %s outcome instead of verified completion', (status, final) => {
  const response = agentFixture('request', status);
  expect(completionPresentation({ request: { requestId: 'request', prompt: 'fixture' }, state: status, result: response.data, timestamp: '', events: [] }).final).toBe(final);
});
