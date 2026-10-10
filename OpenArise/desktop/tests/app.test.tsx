import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import App from '../src/App';
import { AppShell } from '../src/components/AppShell';
import { sections } from '../src/components/Sidebar';
import type { ProjectBridge, Result, FileBuffer } from '../src/types/project';
import { useWorkspace } from '../src/workspace/useWorkspace';
vi.mock('../src/editor/MonacoEditor', () => ({
  default: ({ tabs, active, onChange }: any) => {
    const tab = tabs.find((t: any) => t.path === active);
    return <textarea aria-label="Code editor" readOnly={tab.readOnly} value={tab.content} onChange={e => onChange(active, e.target.value)} />;
  },
}));
const project = { id: '12345678-1234-1234-1234-123456789012', name: 'demo', rootPath: 'C:/demo' };
const buffer = (path: string): FileBuffer => ({ path, content: 'print("hello")\n', revision: 'a'.repeat(64), readOnly: path.endsWith('.md') });
let bridge: ProjectBridge;
beforeEach(() => {
  bridge = {
    openProject: vi.fn(async () => ({ ok: true, data: project })),
    listDirectory: vi.fn(async ({ path }) => ({ ok: true, data: path === '' ?
      [{ name: 'app', path: 'app', kind: 'folder' }, { name: 'README.md', path: 'README.md', kind: 'file' }] :
      [{ name: 'main.py', path: 'app/main.py', kind: 'file' }] })),
    readFile: vi.fn(async ({ path }) => ({ ok: true, data: buffer(path) })),
    saveFile: vi.fn(async request => ({ ok: true, data: { ...buffer(request.path), content: request.content, revision: 'b'.repeat(64) } })),
    observeProject: vi.fn(async () => ({ ok: true, data: { files: 2, modules: 1, observedAt: '2026-09-26' } })),
    setDirty: vi.fn(async () => {}),
    createFile: vi.fn(async ({ path }) => ({ ok: true, data: { ...buffer(path), content: '', readOnly: false } })),
    createFolder: vi.fn(async ({ path }) => ({ ok: true, data: { path, kind: 'folder' } })),
    inspectRename: vi.fn(async ({ path }) => ({ ok: true, data: { path, kind: 'file', revision: 'a'.repeat(64) } })),
    renamePath: vi.fn(async ({ destination }) => ({ ok: true, data: { path: destination, kind: 'file' } })),
    searchFiles: vi.fn(async () => ({ ok: true, data: [] })),
    recentProjects: vi.fn(async () => ({ ok: true, data: [] })),
    openRecent: vi.fn(async () => ({ ok: true, data: project })),
  };
  window.openarise = { project: bridge, getStatus: async () => ({ status: 'disconnected', reason: 'transport_not_implemented' }) } as any;
});
afterEach(() => { cleanup(); delete window.openarise; });
async function openFile() {
  fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
  fireEvent.click(await screen.findByRole('button', { name: /app$/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'main.py' }));
  return screen.findByRole('textbox', { name: 'Code editor' });
}
describe('Phase 2 workspace', () => {
  it('renders the app, supplied logo and all navigation sections', async () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('clearer space');
    expect(screen.getAllByAltText('OpenArise IDE').length).toBeGreaterThan(0);
    for (const name of sections) expect(screen.getByRole('button', { name })).toBeTruthy();
  });
  it('opens a project, expands folders, selects a file and renders its editor', async () => {
    render(<AppShell connection={{ status: 'disconnected', reason: 'transport_not_implemented' }} />);
    const editor = await openFile();
    expect(bridge.openProject).toHaveBeenCalledTimes(1);
    expect(bridge.listDirectory).toHaveBeenCalledWith({ projectId: project.id, path: 'app' });
    expect((editor as HTMLTextAreaElement).value).toBe(buffer('app/main.py').content);
    expect(screen.getByRole('tab', { name: 'main.py' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('button', { name: 'main.py' }).getAttribute('aria-current')).toBe('true');
  });
  it('shows loading states and preserves the workspace when picker is cancelled', async () => {
    let resolve!: (v: Result<typeof project | null>) => void;
    bridge.openProject = vi.fn(() => new Promise(r => { resolve = r; }));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    expect(screen.getAllByText('Opening project...').length).toBeGreaterThan(0);
    resolve({ ok: true, data: null });
    await screen.findByRole('button', { name: 'Open Project' });
    expect(screen.queryByRole('tab')).toBeNull();
  });
  it('marks edits dirty and routes the exact buffer and revision through save', async () => {
    render(<App />);
    fireEvent.change(await openFile(), { target: { value: 'print("changed")\n' } });
    expect(screen.getAllByText('Unsaved changes').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /Save Ctrl S/ }));
    await waitFor(() => expect(bridge.saveFile).toHaveBeenCalledWith({ projectId: project.id, path: 'app/main.py', content: 'print("changed")\n', revision: 'a'.repeat(64) }));
    await waitFor(() => expect(screen.getAllByText('Saved').length).toBeGreaterThan(0));
  });
  it('preserves edits made while an earlier save is pending', async () => {
    let resolve!: (r: Result<FileBuffer>) => void;
    bridge.saveFile = vi.fn(() => new Promise(r => { resolve = r; }));
    render(<App />);
    const editor = await openFile();
    fireEvent.change(editor, { target: { value: 'first' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Ctrl S/ }));
    fireEvent.change(editor, { target: { value: 'second' } });
    resolve({ ok: true, data: { ...buffer('app/main.py'), content: 'first', revision: 'b'.repeat(64) } });
    await waitFor(() => expect(screen.queryByText('Saving…')).toBeNull());
    expect((editor as HTMLTextAreaElement).value).toBe('second');
    expect(screen.getAllByText('Unsaved changes').length).toBeGreaterThan(0);
  });
  it('retains dirty text after a save conflict', async () => {
    bridge.saveFile = vi.fn(async () => ({ ok: false, code: 'conflict', message: 'File changed on disk.' }));
    render(<App />);
    const editor = await openFile();
    fireEvent.change(editor, { target: { value: 'keep my text' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Ctrl S/ }));
    expect(await screen.findByText('File changed on disk.')).toBeTruthy();
    expect((editor as HTMLTextAreaElement).value).toBe('keep my text');
  });
  it('acknowledges a real save whose returned Windows line endings are normalized', async () => {
    bridge.saveFile = vi.fn(async request => ({ ok: true, data: { ...buffer(request.path), content: request.content.replaceAll('\r\n', '\n'), revision: 'b'.repeat(64) } }));
    const { result } = renderHook(() => useWorkspace(bridge));
    await act(async () => { await result.current.openProject(); });
    await act(async () => { await result.current.openFile('config.json'); });
    act(() => result.current.change('config.json', '{"label":"actual"}\r\n'));
    await act(async () => { await result.current.save('config.json'); });
    expect(bridge.saveFile).toHaveBeenCalledWith({ projectId: project.id, path: 'config.json', content: '{"label":"actual"}\r\n', revision: 'a'.repeat(64) });
    expect(result.current.tabs[0].content).toBe('{"label":"actual"}\n');
    expect(result.current.dirty).toBe(false);
    expect(result.current.tabs[0].revision).toBe('b'.repeat(64));
  });
  it('preserves newer edits when a pending save returns normalized line endings', async () => {
    let resolve!: (r: Result<FileBuffer>) => void;
    bridge.saveFile = vi.fn(() => new Promise(r => { resolve = r; }));
    const { result } = renderHook(() => useWorkspace(bridge));
    await act(async () => { await result.current.openProject(); });
    await act(async () => { await result.current.openFile('config.json'); });
    act(() => result.current.change('config.json', '{"label":"first"}\r\n'));
    let saving!: Promise<void>;
    act(() => { saving = result.current.save('config.json'); });
    act(() => result.current.change('config.json', '{"label":"newer"}\r\n'));
    await act(async () => { resolve({ ok: true, data: { ...buffer('config.json'), content: '{"label":"first"}\n', revision: 'b'.repeat(64) } }); await saving; });
    expect(result.current.tabs[0].content).toBe('{"label":"newer"}\r\n');
    expect(result.current.tabs[0].savedContent).toBe('{"label":"first"}\n');
    expect(result.current.dirty).toBe(true);
  });
  it('requires a discard choice before closing dirty tabs', async () => {
    render(<App />);
    fireEvent.change(await openFile(), { target: { value: 'unsaved' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close app/main.py' }));
    expect(screen.getByRole('button', { name: 'Keep editing' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    expect(screen.getByRole('tab')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Close app/main.py' }));
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    expect(screen.queryByRole('tab')).toBeNull();
  });
  it('supports multiple tabs, readonly text and closing the active tab', async () => {
    render(<App />);
    await openFile();
    fireEvent.click(screen.getByRole('button', { name: 'README.md' }));
    await screen.findByRole('tab', { name: 'README.md' });
    expect(screen.getAllByRole('tab')).toHaveLength(2);
    expect((screen.getByRole('textbox', { name: 'Code editor' }) as HTMLTextAreaElement).readOnly).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Close README.md' }));
    expect(screen.getByRole('tab', { name: 'main.py' }).getAttribute('aria-selected')).toBe('true');
  });
  it('blocks switching projects with unsaved buffers', async () => {
    render(<App />);
    fireEvent.change(await openFile(), { target: { value: 'unsaved' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    expect(await screen.findByText('Save or close unsaved tabs before opening another project.')).toBeTruthy();
    expect(bridge.openProject).toHaveBeenCalledTimes(1);
  });
  it('reloads current disk contents only after an explicit discard decision', async () => {
    render(<App />);
    fireEvent.change(await openFile(), { target: { value: 'unsaved edits' } });
    bridge.readFile = vi.fn(async ({ path }) => ({ ok: true, data: { ...buffer(path), content: 'actual disk contents', revision: 'b'.repeat(64) } }));
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    expect(bridge.readFile).not.toHaveBeenCalled();
    expect((screen.getByRole('textbox', { name: 'Code editor' }) as HTMLTextAreaElement).value).toBe('unsaved edits');
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    fireEvent.click(screen.getByRole('button', { name: 'Discard and reload' }));
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Code editor' }) as HTMLTextAreaElement).value).toBe('actual disk contents'));
    expect(screen.queryByLabelText('Unsaved changes')).toBeNull();
  });
  it('locks duplicate file creation and opens the actual empty returned buffer', async () => {
    let resolve!: (result: Result<FileBuffer>) => void;
    bridge.createFile = vi.fn(() => new Promise(r => { resolve = r; }));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    await screen.findByRole('button', { name: /app$/ });
    await waitFor(() => expect((screen.getByRole('button', { name: 'New file' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'New file' }));
    fireEvent.change(screen.getByLabelText('New file in this project'), { target: { value: 'app/new.tsx' } });
    const create = screen.getByRole('button', { name: 'Create file' });
    fireEvent.click(create); fireEvent.click(create);
    expect(bridge.createFile).toHaveBeenCalledTimes(1);
    resolve({ ok: true, data: { path: 'app/new.tsx', content: '', revision: 'a'.repeat(64), readOnly: false } });
    await screen.findByRole('tab', { name: 'new.tsx' });
    expect((screen.getByRole('textbox', { name: 'Code editor' }) as HTMLTextAreaElement).value).toBe('');
  });
  it('opens a session recent project by retained ID, never by a renderer path', async () => {
    bridge.recentProjects = vi.fn(async () => ({ ok: true, data: [project] }));
    render(<App />);
    fireEvent.click(await screen.findByText('Recent projects · this session'));
    fireEvent.click(screen.getByRole('button', { name: 'demo' }));
    await waitFor(() => expect(bridge.openRecent).toHaveBeenCalledWith(project.id));
    expect(bridge.openProject).not.toHaveBeenCalled();
  });
  it('shows an empty project honestly', async () => {
    bridge.listDirectory = vi.fn(async () => ({ ok: true, data: [] }));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    expect(await screen.findByText('This project has no visible files.')).toBeTruthy();
  });
  it('shows file errors without opening a fabricated tab', async () => {
    bridge.readFile = vi.fn(async () => ({ ok: false, code: 'access_denied', message: 'Access denied.' }));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
    fireEvent.click(await screen.findByRole('button', { name: 'README.md' }));
    expect(await screen.findByText('Unable to open file: Access denied.')).toBeTruthy();
    expect(screen.queryByRole('tab')).toBeNull();
  });
  it('resizes Explorer with keyboard and collapses the terminal', () => {
    render(<App />);
    const divider = screen.getByRole('separator');
    fireEvent.keyDown(divider, { key: 'ArrowRight' });
    expect(divider.getAttribute('aria-valuenow')).toBe('240');
    fireEvent.click(screen.getByRole('button', { name: /TERMINAL/ }));
    expect(screen.queryByRole('textbox', { name: 'Terminal command' })).toBeNull();
  });
});
