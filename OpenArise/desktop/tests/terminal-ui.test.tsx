import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../src/App';
import type { TerminalRequest, TerminalSnapshot } from '../src/types/terminal';
vi.mock('../src/editor/MonacoEditor', () => ({ default: ({ tabs, active, onChange }: any) =>
  <textarea aria-label="Code editor" value={tabs.find((t: any) => t.path === active).content} onChange={e => onChange(active, e.target.value)} /> }));
const id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', sid = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
let snapshot: TerminalSnapshot;
let request: ReturnType<typeof vi.fn>;
beforeEach(() => {
  snapshot = { environment: { executable: 'C:/project/.venv/Scripts/python.exe', version: 'Python 3.13.5', status: 'ready', label: 'Project virtual environment', message: 'Selected project environment.' }, sessions: [] };
  request = vi.fn(async (r: TerminalRequest) => {
    if (r.operation === 'create') snapshot.sessions.push({ id: sid, projectId: id, root: 'C:/project', command: '', startedAt: null, state: 'stopped', exitCode: null, output: [], truncated: false, problem: '', testResult: null });
    return { ok: true, data: structuredClone(snapshot) };
  });
  window.openarise = { getStatus: async () => ({ status: 'disconnected', reason: 'transport_not_implemented' }),
    terminal: { request }, project: {
      openProject: async () => ({ ok: true, data: { id, name: 'project', rootPath: 'C:/project' } }),
      listDirectory: async () => ({ ok: true, data: [{ path: 'main.py', name: 'main.py', kind: 'file' }] }),
      readFile: async () => ({ ok: true, data: { path: 'main.py', content: 'print(1)', revision: 'a'.repeat(64), readOnly: false } }),
      saveFile: async (r: any) => ({ ok: true, data: { ...r, revision: 'b'.repeat(64), readOnly: false } }),
      setDirty: async () => {},
    } } as any;
});
afterEach(() => { cleanup(); delete window.openarise; });
async function open() {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
  fireEvent.click(await screen.findByRole('button', { name: 'main.py' }));
  await screen.findByRole('textbox', { name: 'Code editor' });
  await waitFor(() => expect((screen.getByRole('button', { name: '▷ Run' }) as HTMLButtonElement).disabled).toBe(false));
}
describe('Python workspace integration', () => {
  it('shows detected interpreter and runs the opened saved revision in selected project', async () => {
    await open();
    expect(screen.getByText('C:/project/.venv/Scripts/python.exe')).toBeTruthy();
    expect(screen.getByText('Project virtual environment')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '▷ Run' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith({ projectId: id, sessionId: sid, operation: 'execute', command: 'python main.py', revision: 'a'.repeat(64) }));
  });
  it('blocks unsaved execution, then uses latest confirmed save revision', async () => {
    await open();
    fireEvent.change(screen.getByRole('textbox', { name: 'Code editor' }), { target: { value: 'print(2)' } });
    expect((screen.getByRole('button', { name: '▷ Run' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Test' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /Save Ctrl/ }));
    await waitFor(() => expect((screen.getByRole('button', { name: '▷ Run' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '▷ Run' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(expect.objectContaining({ operation: 'execute', revision: 'b'.repeat(64) })));
  });
  it('runs pytest through the controlled action without an executable or cwd', async () => {
    await open(); fireEvent.click(screen.getByRole('button', { name: 'Test' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith({ projectId: id, sessionId: sid, operation: 'execute', command: 'pytest' }));
  });
  it('shows environment unavailable and blocks Run', async () => {
    snapshot.environment.status = 'unavailable'; snapshot.environment.version = ''; snapshot.environment.message = 'Missing project interpreter. No fallback.';
    render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    fireEvent.click(await screen.findByRole('button', { name: 'main.py' }));
    await screen.findByText('Missing project interpreter. No fallback.');
    expect((screen.getByRole('button', { name: '▷ Run' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('rejects shell input and unopened files locally and shows factual Problems', async () => {
    await open();
    const input = screen.getByRole('textbox', { name: 'Terminal command' });
    fireEvent.change(input, { target: { value: 'cmd /c whoami' } });
    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(screen.getByRole('alert').textContent).toContain('Shell syntax is not supported');
    fireEvent.change(input, { target: { value: 'python other.py' } });
    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(screen.getByRole('alert').textContent).toContain('Open and review');
    fireEvent.click(screen.getByRole('button', { name: /Problems/ }));
    expect(screen.getByRole('log').textContent).toContain('Open and review');
    expect(request.mock.calls.some(([r]) => r.operation === 'execute')).toBe(false);
  });
  it('renders process output, session controls and failure details', async () => {
    snapshot.sessions.push({ id: sid, projectId: id, root: 'C:/project', command: 'python main.py', startedAt: '2026-09-27T00:00:00Z', state: 'failed', exitCode: 1, output: [{ stream: 'stdout', text: 'hello\n' }, { stream: 'stderr', text: 'SyntaxError: invalid syntax' }], truncated: false, problem: 'Python exited with code 1.', testResult: null });
    await open();
    expect(screen.getByLabelText('Terminal output').textContent).toContain('SyntaxError');
    expect(screen.getByText(/exit 1/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Restart' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith({ projectId: id, sessionId: sid, operation: 'restart' }));
  });
});
