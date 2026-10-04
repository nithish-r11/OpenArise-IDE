import { createTerminalBridge } from './terminal-ipc';
import { createProjectBridge, validId } from './project-ipc';
import { readMethods } from '../src/types/backend';
import type { BackendRequest, DesktopBridge } from '../src/types/backend';
export const channels = Object.freeze({ connect: 'openarise:connect', disconnect: 'openarise:disconnect', status: 'openarise:status', request: 'openarise:request' });
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function json(value: unknown, depth = 0): boolean {
  if (depth > 20) return false;
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every((item) => json(item, depth + 1));
  return object(value) && Object.entries(value).every(([key, item]) => !['__proto__', 'constructor', 'prototype'].includes(key) && json(item, depth + 1));
}
export function isBackendRequest(value: unknown): value is BackendRequest {
  if (!object(value) || Object.keys(value).sort().join(',') !== 'method,params,request_id') return false;
  if (typeof value.request_id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(value.request_id)) return false;
  if (!object(value.params) || !json(value)) return false;
  if (JSON.stringify(value).length > 65_536) return false;
  const { method, params } = value;
  if (method === 'refresh_workspace') return Object.keys(params).length === 0;
  if (method === 'create_requirement_baseline') return Object.keys(params).join() === 'requirement_id' && typeof params.requirement_id === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(params.requirement_id);
  if (readMethods.some((item) => item === method)) return Object.keys(params).length === 0;
  if (method === 'get_drift_report') return Object.keys(params).join(',') === 'baseline_dict' && object(params.baseline_dict) && Object.keys(params.baseline_dict).join() === 'requirement_id' && typeof params.baseline_dict.requirement_id === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(params.baseline_dict.requirement_id);
  if (method === 'request_agent_execution') return Object.keys(params).every((key) => ['prompt', 'context_data'].includes(key))
    && typeof params.prompt === 'string' && params.prompt.trim().length > 0 && (params.context_data === undefined || object(params.context_data));
  const identifier = (v: unknown) => typeof v === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(v);
  if (['approve_agent_action', 'resume_agent_execution', 'deny_agent_action'].includes(String(method)))
    return Object.keys(params).sort().join() === 'request_id,tool_call_id' && identifier(params.request_id) && identifier(params.tool_call_id);
  if (['cancel_agent_execution', 'get_agent_execution'].includes(String(method)))
    return Object.keys(params).join() === 'request_id' && identifier(params.request_id);
  return false;
}
export function isScopedBackendRequest(args: unknown[], projectId?: string): args is [BackendRequest, string] {
  return args.length === 2 && isBackendRequest(args[0]) && validId(args[1]) && args[1] === projectId;
}
/** Never expose invoke or ipcRenderer itself. */
export function createBridge(invoke: (channel: string, ...args: unknown[]) => Promise<unknown>): DesktopBridge {
  return Object.freeze({
    project: createProjectBridge(invoke),
    terminal: createTerminalBridge(invoke),
    connect: () => invoke(channels.connect) as ReturnType<DesktopBridge['connect']>,
    disconnect: () => invoke(channels.disconnect) as ReturnType<DesktopBridge['disconnect']>,
    getStatus: () => invoke(channels.status) as ReturnType<DesktopBridge['getStatus']>,
    request: (request: BackendRequest, projectId?: string) => (projectId ? invoke(channels.request, request, projectId) : invoke(channels.request, request)) as ReturnType<DesktopBridge['request']>,
  });
}
