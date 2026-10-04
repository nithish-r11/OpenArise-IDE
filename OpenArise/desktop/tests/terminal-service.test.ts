// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtemp, writeFile, mkdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { ProjectService } from '../electron/project-service';
import { TerminalService } from '../electron/terminal-service';
import type { TerminalRequest, TerminalSnapshot } from '../src/types/terminal';
let root: string, projects: ProjectService, service: TerminalService, id: string;
let dirty: { value: boolean };
const value = <T,>(r: { ok: true; data: T } | { ok: false; message: string }): T => { if (!r.ok) throw new Error(r.message); return r.data; };
const request = async (r: Omit<TerminalRequest, 'projectId'>): Promise<TerminalSnapshot> => value(await service.request({ ...r, projectId: id }));
const session = async () => (await request({ operation: 'create' })).sessions.at(-1)!.id;
const until = async (predicate: (s: TerminalSnapshot) => boolean) => {
  for (let i = 0; i < 150; i++) { const s = await request({ operation: 'snapshot' }); if (predicate(s)) return s; await new Promise(r => setTimeout(r, 50)); }
  throw new Error('Process did not reach expected state');
};
beforeEach(async () => {
  root = await mkdtemp(path.join(os.tmpdir(), 'openarise-terminal-test-'));
  await writeFile(path.join(root, 'main.py'), 'import sys\nprint("hello")\nprint("notice", file=sys.stderr)\n');
  projects = new ProjectService(); id = value(await projects.open(root)).id; dirty = { value: false };
  service = new TerminalService(projects, dirty); projects.beforeChange = () => service.reset();
});
afterEach(async () => { await service?.close(); await projects?.close(); await rm(root, { recursive: true, force: true }); });
describe('real Python terminal lifecycle', () => {
  it('detects interpreter and owns multiple bounded sessions', async () => {
    const first = await session(), second = await session();
    const s = await request({ operation: 'snapshot' });
    expect(s.environment.status).toBe('ready'); expect(s.environment.version).toMatch(/^Python/);
    expect(s.environment.executable).toContain('.venv'); expect(s.environment.label).toContain('Backend');
    expect(s.sessions.map(s => s.id)).toEqual([first, second]); expect(s.sessions[0].root).toBe(root);
    expect(s.sessions[0].state).toBe('stopped');
    for (let i = 0; i < 4; i++) await session();
    expect((await service.request({ projectId: id, operation: 'create' })).ok).toBe(false);
    expect((await request({ operation: 'close', sessionId: first })).sessions).toHaveLength(5);
  });
  it('runs saved Python with streamed stdout/stderr and exit status', async () => {
    const sid = await session(); const file = value(await projects.read(id, 'main.py'));
    const started = await request({ operation: 'execute', sessionId: sid, command: 'python main.py', revision: file.revision });
    expect(['starting', 'running']).toContain(started.sessions[0].state);
    const s = (await until(s => s.sessions[0].state === 'exited')).sessions[0];
    expect(s.exitCode).toBe(0); expect(s.startedAt).toBeTruthy();
    expect(s.output.some(o => o.stream === 'stdout' && o.text.includes('hello'))).toBe(true);
    expect(s.output.some(o => o.stream === 'stderr' && o.text.includes('notice'))).toBe(true);
    expect((await request({ operation: 'clear', sessionId: sid })).sessions[0].output).toEqual([]);
  });
  it('reports actual syntax failures', async () => {
    await writeFile(path.join(root, 'bad.py'), 'def broken(\n');
    const file = value(await projects.read(id, 'bad.py')); const sid = await session();
    await request({ operation: 'execute', sessionId: sid, command: 'python bad.py', revision: file.revision });
    const s = (await until(s => s.sessions[0].state === 'failed')).sessions[0];
    expect(s.exitCode).toBe(1); expect(s.problem).toContain('exited with code 1');
    expect(s.output.map(o => o.text).join('')).toContain('SyntaxError');
  });
  it('runs the installed pytest and preserves failure exit codes', async () => {
    await writeFile(path.join(root, 'test_sample.py'), 'def test_one():\n    assert 1 == 2\n');
    const sid = await session();
    await request({ operation: 'execute', sessionId: sid, command: 'pytest' });
    const s = (await until(s => s.sessions[0].state === 'failed')).sessions[0];
    expect(s.testResult).toBe('failed'); expect(s.exitCode).toBe(1);
    expect(s.output.map(o => o.text).join('')).toContain('1 failed');
  });
  it('stops a process tree and restart creates an idle session without rerunning', async () => {
    await writeFile(path.join(root, 'long.py'), 'import subprocess, sys, time\np=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\nprint(p.pid, flush=True)\ntime.sleep(60)\n');
    const f = value(await projects.read(id, 'long.py')); const sid = await session();
    await request({ operation: 'execute', sessionId: sid, command: 'python long.py', revision: f.revision });
    const started = await until(s => s.sessions[0].output.length > 0);
    const pid = Number(started.sessions[0].output.map(o => o.text).join('').trim());
    expect(pid).toBeGreaterThan(0);
    expect((await request({ operation: 'stop', sessionId: sid })).sessions[0].state).toBe('stopped');
    expect(() => process.kill(pid, 0)).toThrow();
    const reset = (await request({ operation: 'restart', sessionId: sid })).sessions[0];
    expect(reset.output).toEqual([]); expect(reset.command).toBe(''); expect(reset.startedAt).toBeNull();
  });
  it('blocks dirty buffers, stale revisions, unopened files and stale project contexts', async () => {
    const sid = await session(); const f = value(await projects.read(id, 'main.py'));
    const command: TerminalRequest = { projectId: id, sessionId: sid, operation: 'execute', command: 'python main.py', revision: f.revision };
    dirty.value = true; expect((await service.request(command)).ok).toBe(false); dirty.value = false;
    await writeFile(path.join(root, 'main.py'), 'print("external")');
    expect(await service.request(command)).toMatchObject({ ok: false, code: 'conflict' });
    expect((await service.request({ ...command, projectId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' })).ok).toBe(false);
    await writeFile(path.join(root, 'unopened.py'), 'print(1)');
    expect((await service.request({ ...command, command: 'python unopened.py' })).ok).toBe(false);
  });
  it('does not fall back when a known project environment is unavailable', async () => {
    await mkdir(path.join(root, '.venv'));
    const sid = await session();
    expect((await request({ operation: 'snapshot' })).environment).toMatchObject({ status: 'unavailable', label: 'Project virtual environment' });
    expect((await service.request({ projectId: id, sessionId: sid, operation: 'execute', command: 'pytest' })).ok).toBe(false);
    expect((await request({ operation: 'snapshot' })).sessions[0].startedAt).toBeNull();
  });
  it('caps output and removes all owned processes on shutdown', async () => {
    await writeFile(path.join(root, 'long.py'), 'import os,time\nprint("x"*200000, flush=True)\nprint("PID="+str(os.getpid()), flush=True)\ntime.sleep(60)\n');
    const f = value(await projects.read(id, 'long.py')); const sid = await session();
    await request({ operation: 'execute', sessionId: sid, command: 'python long.py', revision: f.revision });
    const s = (await until(s => s.sessions[0].output.some(o => o.text.includes('PID=')))).sessions[0];
    expect(s.truncated).toBe(true); expect(s.output.reduce((n, o) => n + o.text.length, 0)).toBeLessThanOrEqual(131072);
    const pid = Number(s.output.map(o => o.text).join('').match(/PID=(\d+)/)![1]);
    await service.close(); expect(() => process.kill(pid, 0)).toThrow();
    expect((await service.request({ projectId: id, operation: 'create' })).ok).toBe(false);
  });
  it('cleans old sessions when switching trusted roots', async () => {
    const sid = await session();
    await mkdir(path.join(root, 'second'));
    const next = value(await projects.open(path.join(root, 'second')));
    id = next.id;
    expect((await request({ operation: 'snapshot' })).sessions).toEqual([]);
    expect((await service.request({ projectId: id, sessionId: sid, operation: 'stop' })).ok).toBe(false);
  });
});
