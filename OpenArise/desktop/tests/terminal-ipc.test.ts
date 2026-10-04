// @vitest-environment node
import { expect, it, vi } from 'vitest';
const handle = vi.hoisted(() => vi.fn());
vi.mock('electron', () => ({ ipcMain: { handle } }));
import { registerTerminalIpc } from '../electron/terminal-ipc';
import { terminalChannel } from '../shared/terminal-ipc';
it('rejects untrusted senders before dispatch', () => {
  const request = vi.fn();
  registerTerminalIpc({ request } as any, () => false);
  const handler = handle.mock.calls.at(-1)![1];
  expect(handle.mock.calls.at(-1)![0]).toBe(terminalChannel);
  expect(() => handler({}, { projectId: 'a'.repeat(36), operation: 'snapshot' })).toThrow('Untrusted');
  expect(request).not.toHaveBeenCalled();
});
it('rejects extra arguments and root overrides before dispatch', () => {
  const request = vi.fn();
  registerTerminalIpc({ request } as any, () => true);
  const handler = handle.mock.calls.at(-1)![1];
  const good = { projectId: 'a'.repeat(36), operation: 'snapshot' };
  expect(handler({}, good, 'extra')).toMatchObject({ ok: false });
  expect(handler({}, { ...good, root: 'C:/other' })).toMatchObject({ ok: false });
  expect(request).not.toHaveBeenCalled();
});
