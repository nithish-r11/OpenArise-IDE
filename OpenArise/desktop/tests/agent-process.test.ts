// @vitest-environment node
import { expect, it } from 'vitest';
import { mkdtemp, rm, readdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { AgentProcess } from '../electron/agent-process';
it('connects the real protected BackendService, returns bounded context and acknowledges shutdown without Ollama', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'openarise-agent-test-'));
  const host = new AgentProcess(root);
  try {
    expect(await host.ready).toBe(true);
    const result = await host.request({ request_id: 'context', method: 'get_intelligence_snapshot', params: {} });
    expect(result).toMatchObject({ kind: 'backend', response: { request_id: 'context', success: true, data: { intelligence_summary: { requirements_count: 0 } } } });
    const environment = await host.request({ request_id: 'environment', method: 'get_environment_status', params: {} });
    expect(environment).toMatchObject({ kind: 'backend', response: { success: true, data: { python_available: true } } });
    await host.close(); expect(host.alive).toBe(false);
  } finally { await host.close(); await rm(root, { recursive: true, force: true }); }
}, 20000);

it('passes every real intelligence DTO through the main-process validator without project writes', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'openarise-intelligence-test-'));
  await writeFile(path.join(root, 'main.py'), 'def welcome():\n    return "private content"\n');
  const host = new AgentProcess(root);
  try {
    expect(await host.ready).toBe(true);
    for (const method of ['refresh_workspace', 'get_project_information', 'get_project_state', 'get_requirements', 'get_blueprint', 'get_traceability_graph', 'get_environment_status', 'get_health_report', 'get_intelligence_snapshot', 'get_timeline'] as const) {
      const result = await host.request({ request_id: method, method, params: {} });
      expect(result, method).toMatchObject({ kind: 'backend', response: { success: true } });
      expect(JSON.stringify(result)).not.toContain('private content');
    }
    expect(await readdir(root)).toEqual(['main.py']);
  } finally { await host.close(); await rm(root, { recursive: true, force: true }); }
}, 20000);