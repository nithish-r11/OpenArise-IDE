import { describe, expect, it, vi } from 'vitest';
import { validAgentEnvelope } from '../shared/agent-response';
import { isBackendRequest, isScopedBackendRequest } from '../shared/ipc';
import { DesktopBackendService } from '../electron/backend-service';
import { BackendClient } from '../src/backend/client';
import { agentFixture } from './ai-fixtures';
describe('AI contract and projection', () => {
  it('keeps workspace blocked when viewing an older result during a pending request', async () => {
    const adapter = { connect: vi.fn(), disconnect: vi.fn(), request: vi.fn() };
    const service = new DesktopBackendService(adapter);
    adapter.request.mockResolvedValueOnce({ kind: 'backend', response: agentFixture('current', 'permission_required') });
    await service.request({ request_id: 'current', method: 'request_agent_execution', params: { prompt: 'Change' } });
    expect(service.blocked).toBe(true);
    adapter.request.mockResolvedValueOnce({ kind: 'backend', response: agentFixture('read', 'unverified', 'older') });
    await service.request({ request_id: 'read', method: 'get_agent_execution', params: { request_id: 'older' } });
    expect(service.blocked).toBe(true);
    adapter.request.mockResolvedValueOnce({ kind: 'backend', response: agentFixture('cancel', 'cancelled', 'current') });
    await service.request({ request_id: 'cancel', method: 'cancel_agent_execution', params: { request_id: 'current' } });
    expect(service.blocked).toBe(false);
  });
  it('requires the trusted current project reference and rejects root/executable overrides', () => {
    const id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
    const request = { request_id: 'request', method: 'request_agent_execution', params: { prompt: 'Review' } };
    expect(isScopedBackendRequest([request, id], id)).toBe(true);
    expect(isScopedBackendRequest([request], id)).toBe(false);
    expect(isScopedBackendRequest([request, id], 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')).toBe(false);
    expect(isScopedBackendRequest([{ ...request, executable: 'python' }, id], id)).toBe(false);
    expect(isScopedBackendRequest([request, id, 'C:/other'], id)).toBe(false);
    expect(isScopedBackendRequest([{ ...request, request_id: 'bad id' }, id], id)).toBe(false);
  });
  it.each(['approve_agent_action', 'resume_agent_execution', 'deny_agent_action'])('allows exact %s IDs only', method => {
    const request = { request_id: 'command', method, params: { request_id: 'original', tool_call_id: 'tool-1' } };
    expect(isBackendRequest(request)).toBe(true);
    expect(isBackendRequest({ ...request, params: { ...request.params, arguments: { command: 'cmd' } } })).toBe(false);
    expect(isBackendRequest({ ...request, params: { request_id: 'original', tool_call_id: '../bad' } })).toBe(false);
  });
  it.each(['cancel_agent_execution', 'get_agent_execution'])('allows exact %s target', method => {
    expect(isBackendRequest({ request_id: 'command', method, params: { request_id: 'original' } })).toBe(true);
    expect(isBackendRequest({ request_id: 'command', method, params: { request_id: 'original', root: 'C:/' } })).toBe(false);
  });
  it('rejects foreign IDs, raw arguments, output and unbounded events', () => {
    const good = agentFixture('original', 'permission_required');
    expect(validAgentEnvelope(good, 'original', 'request_agent_execution')).toBe(true);
    expect(validAgentEnvelope(good, 'different', 'request_agent_execution')).toBe(false);
    for (const key of ['arguments', 'command', 'content']) {
      const response = structuredClone(good); (response.data.pending_action as any)[key] = 'secret';
      expect(validAgentEnvelope(response, 'original', 'request_agent_execution')).toBe(false);
    }
    const events = structuredClone(good); events.events = Array(201).fill(good.events[0]);
    expect(validAgentEnvelope(events, 'original', 'request_agent_execution')).toBe(false);
  });
  it('accepts unverified outer-success without changing its meaning', () => {
    const response = agentFixture('a');
    expect(validAgentEnvelope(response, 'a', 'request_agent_execution')).toBe(true);
    expect(response.success).toBe(true); expect(response.data.status).toBe('unverified');
  });
  it('scopes requests to a project and preserves original IDs through continuation commands', async () => {
    const request = vi.fn(async () => ({}));
    const client = new BackendClient({ request } as any, 'project-1');
    await client.submitAIRequest({ requestId: 'original', prompt: 'Build it', projectRef: { id: 'project-1' } });
    await client.agentCommand('approve_agent_action', 'original', 'tool-1', 'approval');
    await client.agentCommand('resume_agent_execution', 'original', 'tool-1', 'resume');
    expect(request.mock.calls).toEqual([
      [{ request_id: 'original', method: 'request_agent_execution', params: { prompt: 'Build it' } }, 'project-1'],
      [{ request_id: 'approval', method: 'approve_agent_action', params: { request_id: 'original', tool_call_id: 'tool-1' } }, 'project-1'],
      [{ request_id: 'resume', method: 'resume_agent_execution', params: { request_id: 'original', tool_call_id: 'tool-1' } }, 'project-1'],
    ]);
    expect(await client.submitAIRequest({ requestId: 'x', prompt: 'No', projectRef: { id: 'other' } })).toMatchObject({ kind: 'unavailable' });
    expect(request).toHaveBeenCalledTimes(3);
  });
});
