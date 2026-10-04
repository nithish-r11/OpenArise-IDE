import { validId, validPath } from './project-ipc';
import type { TerminalBridge, TerminalRequest } from '../src/types/terminal';
export const terminalChannel = 'openarise:terminal';
export type Command = { kind: 'version' | 'pytest' } | { kind: 'run'; path: string };
export function parseCommand(input: unknown): Command | null {
  if (typeof input !== 'string' || input.length > 2100) return null;
  if (input === 'python --version') return { kind: 'version' };
  if (input === 'pytest') return { kind: 'pytest' };
  if (!input.startsWith('python ')) return null;
  const path = input.slice(7);
  if (!validPath(path) || !/\.pyw?$/i.test(path) || /[;&|<>\x7f`$"'*?]/.test(path) || path.startsWith('-')) return null;
  return { kind: 'run', path };
}
export function validTerminalRequest(value: unknown): value is TerminalRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  if (!validId(r.projectId)) return false;
  if (r.operation === 'snapshot' || r.operation === 'refresh' || r.operation === 'create') return Object.keys(r).sort().join() === 'operation,projectId';
  if (!validId(r.sessionId)) return false;
  if (r.operation === 'execute') {
    const cmd = parseCommand(r.command);
    if (!cmd) return false;
    const keys = cmd.kind === 'run' ? 'command,operation,projectId,revision,sessionId' : 'command,operation,projectId,sessionId';
    return Object.keys(r).sort().join() === keys && (cmd.kind !== 'run' || typeof r.revision === 'string' && /^[a-f0-9]{64}$/.test(r.revision));
  }
  return ['stop', 'clear', 'close', 'restart'].includes(String(r.operation))
    && Object.keys(r).sort().join() === 'operation,projectId,sessionId';
}
export function createTerminalBridge(invoke: (channel: string, ...args: unknown[]) => Promise<unknown>): TerminalBridge {
  return Object.freeze({ request: (request: TerminalRequest) => invoke(terminalChannel, request) as ReturnType<TerminalBridge['request']> });
}
