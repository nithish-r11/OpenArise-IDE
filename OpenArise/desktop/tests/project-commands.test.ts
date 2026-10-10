// @vitest-environment node
import { afterEach, expect, it } from 'vitest';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { ProjectService } from '../electron/project-service';
import { TerminalService } from '../electron/terminal-service';
import type { ProjectCommand } from '../shared/capabilities';
const services: { projects: ProjectService; terminal: TerminalService }[] = [];
afterEach(async () => { for (const s of services.splice(0)) { await s.terminal.close(); await s.projects.close(); } });
async function setup(approve: (command: ProjectCommand) => Promise<boolean>) {
  const root = path.resolve('.packaging/product-tests/commands-' + crypto.randomUUID());
  await mkdir(path.join(root, 'frontend'), { recursive: true });
  await writeFile(path.join(root, 'frontend/package.json'), JSON.stringify({ scripts: { test: 'node --test test.cjs', build: 'node build.cjs', pretest: 'node forbidden.cjs' } }));
  await writeFile(path.join(root, 'frontend/test.cjs'), 'require("node:test")("real frontend",()=>require("node:assert/strict").equal(2+2,4));');
  await writeFile(path.join(root, 'frontend/build.cjs'), 'console.log("ACTUAL_FRONTEND_BUILD");');
  await writeFile(path.join(root, 'frontend/forbidden.cjs'), 'throw Error("pretest lifecycle must be disabled");');
  const projects = new ProjectService();
  const opened = await projects.open(root); if (!opened.ok) throw Error(opened.message);
  const id = opened.data.id;
  const terminal = new TerminalService(projects, { value: false }, approve); services.push({ projects, terminal });
  const observation = await projects.observe(id); if (!observation.ok) throw Error(observation.message);
  const created = await terminal.request({ projectId: id, operation: 'create' }); if (!created.ok) throw Error(created.message);
  return { projects, terminal, id, root, sessionId: created.data.sessions[0].id, commands: observation.data.capabilities!.commands };
}
it('denial leaves the real process unstarted', async () => {
  const s = await setup(async () => false);
  const result = await s.terminal.request({ projectId: s.id, sessionId: s.sessionId, operation: 'executeCapability', capabilityId: s.commands[0].id });
  expect(result).toMatchObject({ ok: false, code: 'permission_required' });
  const snapshot = await s.terminal.request({ projectId: s.id, operation: 'snapshot' });
  expect(snapshot.ok && snapshot.data.sessions[0].startedAt).toBeNull();
});
it('approval runs real project-scoped npm tests without pretest and captures failures', async () => {
  const s = await setup(async command => { expect(command.directory).toBe('frontend'); expect(command.approvalRequired).toBe(true); return true; });
  const test = s.commands.find(c => c.action === 'test')!;
  await s.terminal.request({ projectId: s.id, sessionId: s.sessionId, operation: 'executeCapability', capabilityId: test.id });
  let final;
  for (let i = 0; i < 160; i++) {
    const r = await s.terminal.request({ projectId: s.id, operation: 'snapshot' });
    if (r.ok && ['exited', 'failed'].includes(r.data.sessions[0].state)) { final = r.data.sessions[0]; break; }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  expect(final?.exitCode).toBe(0); expect(final?.testResult).toBe('passed');
  expect(final?.output.map(o => o.text).join('')).toContain('real frontend');
  await writeFile(path.join(s.root, 'frontend/test.cjs'), 'require("node:test")("actual failure",()=>require("node:assert/strict").equal(1,2));');
  await s.terminal.request({ projectId: s.id, sessionId: s.sessionId, operation: 'executeCapability', capabilityId: test.id });
  for (let i = 0; i < 160; i++) {
    const r = await s.terminal.request({ projectId: s.id, operation: 'snapshot' });
    if (r.ok && r.data.sessions[0].state === 'failed') { final = r.data.sessions[0]; break; }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  expect(final?.exitCode).toBe(1); expect(final?.testResult).toBe('failed');
}, 20000);
it('manifest changes during approval block execution', async () => {
  let manifest = '';
  const s = await setup(async () => { await writeFile(manifest, JSON.stringify({ scripts: { build: 'node changed.cjs' } })); return true; });
  manifest = path.join(s.root, 'frontend/package.json');
  const build = s.commands.find(c => c.action === 'build')!;
  expect(await s.terminal.request({ projectId: s.id, sessionId: s.sessionId, operation: 'executeCapability', capabilityId: build.id })).toMatchObject({ ok: false, code: 'conflict' });
});
