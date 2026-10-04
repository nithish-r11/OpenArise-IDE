import { describe, expect, it, vi } from 'vitest';
import { BackendClient } from '../src/backend/client';
import { DesktopBackendService, DisconnectedProcessAdapter } from '../electron/backend-service';
import { createBridge, isBackendRequest, channels } from '../shared/ipc';
import { readMethods } from '../src/types/backend';
import type { BackendRequest, DesktopBridge } from '../src/types/backend';
const request: BackendRequest = { request_id: 'test-1', method: 'get_project_information', params: {} };
describe('backend boundary', () => {
  it('can instantiate without a backend and does not report success', async () => {
    const client = new BackendClient();
    expect(await client.connect()).toEqual({ status: 'disconnected', reason: 'bridge_unavailable' });
    expect(await client.getProjectInfo()).toMatchObject({ kind: 'unavailable', code: 'bridge_unavailable' });
  });
  it('maps every client method to the existing contract with fresh command IDs', async () => {
    const invoke = vi.fn(async (_channel: string, value?: BackendRequest) => ({ kind: 'unavailable', request_id: value?.request_id, code: 'not_connected' }));
    const client = new BackendClient(createBridge(invoke));
    await client.getProjectInfo(); await client.getProjectState(); await client.getBlueprint();
    await client.getRequirements(); await client.getTraceability(); await client.getEnvironment();
    await client.getHealth(); await client.getIntelligence(); await client.getTimeline();
    await client.getDrift({ requirement_id: 'r1' });
    await client.submitAgentRequest('Inspect project', { selected: [] }, 'agent-id');
    const commands = invoke.mock.calls.map((call) => call[1]!);
    expect(commands.map((r) => r.method)).toEqual([...readMethods, 'get_drift_report', 'request_agent_execution']);
    expect(commands.every(isBackendRequest)).toBe(true);
    expect(new Set(commands.map((r) => r.request_id)).size).toBe(11);
    expect(commands[10].request_id).toBe('agent-id');
    expect(commands[10].params).not.toHaveProperty('request_id');
  });
  it('sanitizes IPC rejections', async () => {
    const bridge = createBridge(async () => { throw new Error('private information'); });
    expect(await new BackendClient(bridge).getProjectInfo()).toMatchObject({ kind: 'unavailable', code: 'transport_error', message: 'Desktop bridge could not handle the request.' });
  });
  it('reports disconnected and preserves the request ID', async () => {
    const service = new DesktopBackendService();
    expect(await service.connect()).toEqual({ status: 'disconnected', reason: 'transport_not_implemented' });
    expect(await service.request(request)).toMatchObject({ kind: 'unavailable', request_id: 'test-1', code: 'not_connected' });
  });
  it('closes once and refuses later requests or reconnection', async () => {
    const adapter = new DisconnectedProcessAdapter();
    const stop = vi.spyOn(adapter, 'disconnect');
    const start = vi.spyOn(adapter, 'connect');
    const service = new DesktopBackendService(adapter);
    await Promise.all([service.disconnect(), service.disconnect()]);
    expect(stop).toHaveBeenCalledTimes(1);
    expect(await service.request(request)).toMatchObject({ code: 'service_closed' });
    expect(await service.connect()).toEqual({ status: 'disconnected', reason: 'closed' });
    expect(start).not.toHaveBeenCalled();
  });
  it('exposes only fixed bridge methods and channels', async () => {
    const invoke = vi.fn(async () => ({}));
    const bridge: DesktopBridge = createBridge(invoke);
    expect(Object.keys(bridge).sort()).toEqual(['connect', 'disconnect', 'getStatus', 'project', 'request', 'terminal']);
    expect(Object.isFrozen(bridge)).toBe(true);
    await bridge.connect(); await bridge.disconnect(); await bridge.getStatus(); await bridge.request(request);
    expect(invoke.mock.calls).toEqual([[channels.connect], [channels.disconnect], [channels.status], [channels.request, request]]);
  });
});
describe('IPC request validation', () => {
  it.each(readMethods)('accepts public read method %s', (method) => expect(isBackendRequest({ ...request, method })).toBe(true));
  it.each([
    null, {}, { ...request, request_id: '' }, { ...request, request_id: ' ' },
    { ...request, method: '__dict__' }, { ...request, method: 'shutdown' },
    { ...request, executable: 'python' }, { ...request, params: { arbitrary: true } },
    { ...request, method: 'request_agent_execution', params: { prompt: '' } },
    { ...request, method: 'request_agent_execution', params: { prompt: 'go', request_id: 'override' } },
    { ...request, method: 'request_agent_execution', params: { prompt: 'go', context_data: { bad: Infinity } } },
    { ...request, method: 'request_agent_execution', params: { prompt: 'x'.repeat(66000) } },
    { ...request, method: 'get_drift_report', params: {} },
    { ...request, method: 'get_drift_report', params: { baseline_dict: {} } },
  ])('rejects invalid or unsupported message %#', (value) => expect(isBackendRequest(value)).toBe(false));
  it('rejects cycles', () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    expect(isBackendRequest({ ...request, params: cyclic })).toBe(false);
  });
});
