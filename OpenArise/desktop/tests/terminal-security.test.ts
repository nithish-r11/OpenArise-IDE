import { describe, it, expect, vi } from 'vitest';
import { createTerminalBridge, parseCommand, validTerminalRequest, terminalChannel } from '../shared/terminal-ipc';
const id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
describe('terminal command boundary', () => {
  it.each(['cmd', 'powershell', 'pip install pytest', 'python -c print(1)', 'python ../secret.py', 'python C:/file.py',
    'python /tmp/file.py', 'python a.py;calc', 'python a.py|cmd', 'python a.py\n', 'pytest --rootdir=/',
    'python ' + 'x'.repeat(2100) + '.py'])('rejects forbidden command %s', command => expect(parseCommand(command)).toBeNull());
  it('allows only version, pytest and a relative Python path including spaces', () => {
    expect(parseCommand('python --version')).toEqual({ kind: 'version' });
    expect(parseCommand('pytest')).toEqual({ kind: 'pytest' });
    expect(parseCommand('python app/my file.py')).toEqual({ kind: 'run', path: 'app/my file.py' });
  });
  it('requires saved revision for Python execution', () => {
    const request = { projectId: id, sessionId: id, operation: 'execute', command: 'python main.py' };
    expect(validTerminalRequest(request)).toBe(false);
    expect(validTerminalRequest({ ...request, revision: 'a'.repeat(64) })).toBe(true);
  });
  it('rejects arbitrary cwd, executable, root and extra arguments', () => {
    const request = { projectId: id, sessionId: id, operation: 'execute', command: 'pytest' };
    for (const key of ['cwd', 'root', 'executable', 'args', 'revision']) expect(validTerminalRequest({ ...request, [key]: 'x' })).toBe(false);
  });
  it('rejects missing project, invalid session and unsupported operations', () => {
    for (const r of [{ operation: 'create' }, { projectId: id, operation: 'stop', sessionId: '../' },
      { projectId: id, operation: 'shell' }, { projectId: id, operation: 'snapshot', sessionId: id }]) expect(validTerminalRequest(r)).toBe(false);
  });
  it('exposes a frozen typed request wrapper, never invoke or process APIs', async () => {
    const invoke = vi.fn(async () => ({}));
    const bridge = createTerminalBridge(invoke);
    expect(Object.keys(bridge)).toEqual(['request']); expect(Object.isFrozen(bridge)).toBe(true);
    await bridge.request({ projectId: id, operation: 'create' });
    expect(invoke).toHaveBeenCalledWith(terminalChannel, { projectId: id, operation: 'create' });
  });
});
