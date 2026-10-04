import { beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ handlers: new Map<string, (...args: any[]) => Promise<any>>(), picker: vi.fn() }));
vi.mock('electron', () => ({ dialog: { showOpenDialog: mocks.picker }, ipcMain: { handle: (name: string, fn: any) => mocks.handlers.set(name, fn) } }));
import { registerProjectIpc } from '../electron/project-ipc';
import { projectChannels } from '../shared/project-ipc';
const service = { open: vi.fn(), read: vi.fn(), save: vi.fn(), list: vi.fn(), observe: vi.fn() };
const dirty = { value: false };
beforeEach(() => {
  vi.clearAllMocks(); mocks.handlers.clear(); dirty.value = false;
  registerProjectIpc(service as any, () => ({}) as any, event => (event as any).trusted === true, dirty);
});
it('rejects an untrusted frame before opening a picker', async () => {
  await expect(mocks.handlers.get(projectChannels.open)!({ trusted: false })).rejects.toThrow('Untrusted IPC sender');
  expect(mocks.picker).not.toHaveBeenCalled();
});
it('cancels native picker without changing the project', async () => {
  mocks.picker.mockResolvedValue({ canceled: true, filePaths: [] });
  expect(await mocks.handlers.get(projectChannels.open)!({ trusted: true })).toEqual({ ok: true, data: null });
  expect(service.open).not.toHaveBeenCalled();
});
it('accepts only a native-picked root', async () => {
  mocks.picker.mockResolvedValue({ canceled: false, filePaths: ['C:/selected'] });
  service.open.mockResolvedValue({ ok: true, data: { id: 'project' } });
  await mocks.handlers.get(projectChannels.open)!({ trusted: true });
  expect(service.open).toHaveBeenCalledWith('C:/selected');
  service.open.mockClear();
  const result = await mocks.handlers.get(projectChannels.open)!({ trusted: true }, 'C:/renderer-root');
  expect(result.code).toBe('invalid_request');
  expect(service.open).not.toHaveBeenCalled();
});
it('blocks project replacement with unsaved buffers', async () => {
  dirty.value = true;
  expect((await mocks.handlers.get(projectChannels.open)!({ trusted: true })).code).toBe('conflict');
  expect(mocks.picker).not.toHaveBeenCalled();
});
it('validates save messages before dispatch', async () => {
  const result = await mocks.handlers.get(projectChannels.save)!({ trusted: true }, { projectId: 'x', path: '../outside', content: 'bad' });
  expect(result.code).toBe('invalid_request');
  expect(service.save).not.toHaveBeenCalled();
});
it('dispatches the exact approved editor buffer without a root or executable parameter', async () => {
  const value = { projectId: '12345678-1234-1234-1234-123456789012', path: 'main.py', content: 'pass', revision: 'a'.repeat(64) };
  await mocks.handlers.get(projectChannels.save)!({ trusted: true }, value);
  expect(service.save).toHaveBeenCalledWith(value.projectId, value.path, value.content, value.revision);
});
