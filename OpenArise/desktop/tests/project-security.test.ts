import { expect, it, vi } from 'vitest';
import { validAddress, validPath, createProjectBridge, projectChannels } from '../shared/project-ipc';
const address = { projectId: '12345678-1234-1234-1234-123456789012', path: 'app/main.py' };
it.each(['../main.py', '/root/main.py', 'C:/main.py', 'app\\main.py', 'a/./b', 'a//b', 'a\0b'])('rejects unsafe path %s', path => expect(validPath(path)).toBe(false));
it('validates exact read and save shapes', () => {
  expect(validAddress(address)).toBe(true);
  expect(validAddress({ ...address, root: 'C:/' })).toBe(false);
  expect(validAddress({ ...address, projectId: '' })).toBe(false);
  expect(validAddress({ ...address, content: 'pass', revision: 'a'.repeat(64) }, true)).toBe(true);
  expect(validAddress({ ...address, content: 'pass', revision: 'x' }, true)).toBe(false);
  expect(validAddress({ ...address, content: 'x'.repeat(2 * 1024 * 1024 + 1), revision: 'a'.repeat(64) }, true)).toBe(false);
});
it('exposes only dedicated project operations and fixed IPC channels', async () => {
  const invoke = vi.fn(async () => ({}));
  const bridge = createProjectBridge(invoke);
  expect(Object.isFrozen(bridge)).toBe(true);
  expect(Object.keys(bridge).sort()).toEqual(['listDirectory','observeProject','openProject','readFile','saveFile','setDirty']);
  await bridge.openProject(); await bridge.listDirectory(address); await bridge.readFile(address);
  await bridge.saveFile({ ...address, content: 'pass', revision: 'a'.repeat(64) });
  await bridge.observeProject(address.projectId); await bridge.setDirty(true);
  expect(invoke.mock.calls.map(call => call[0])).toEqual(Object.values(projectChannels));
});
