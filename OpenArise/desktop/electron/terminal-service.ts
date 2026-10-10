import { spawn, type ChildProcess } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { backendPython, desktopPython } from './runtime-paths';
import { parseCommand, validTerminalRequest } from '../shared/terminal-ipc';
import type { Result } from '../src/types/project';
import type { PythonEnvironment, TerminalRequest, TerminalSession, TerminalSnapshot } from '../src/types/terminal';
import type { ProjectService } from './project-service';
import type { ProjectCommand } from '../shared/capabilities';
const unavailable = (message: string): Result<never> => ({ ok: false, code: 'unavailable', message });
type Owned = { data: TerminalSession; child?: ChildProcess; done?: Promise<void>; cancel: boolean };
export class TerminalService {
  private sessions = new Map<string, Owned>();
  private environment: PythonEnvironment = { executable: '', version: '', label: 'Python', status: 'unavailable', message: 'Environment not inspected.' };
  private environmentProject = '';
  private queue: Promise<unknown> = Promise.resolve();
  private closed = false;
  constructor(private projects: ProjectService, private dirty: { value: boolean },
    private approveScript: (command: ProjectCommand) => Promise<boolean> = async () => false) {}
  private serial<T>(work: () => Promise<T>): Promise<T> {
    const next = this.queue.then(work, work); this.queue = next.catch(() => {}); return next;
  }
  private spawn(args: string[], root: string) {
    return spawn(backendPython(), ['-I', '-B', '-u', desktopPython('process_supervisor.py'), ...args], {
      cwd: root, shell: false, windowsHide: true, detached: process.platform !== 'win32',
      stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
    });
  }
  private kill(child: ChildProcess) {
    if (!child.pid) return;
    try {
      if (process.platform === 'win32') child.kill();
      else process.kill(-child.pid, 'SIGKILL');
    } catch { /* Process/group has already exited. */ }
  }
  private async inspect(id: string, root: string) {
    const detected = await this.projects.call<Omit<PythonEnvironment, 'version'>>(id, 'environment');
    if (!detected.ok) { this.environment = { executable: '', version: '', label: 'Python', status: 'unavailable', message: detected.message }; return; }
    this.environment = { ...detected.data, version: '' };
    this.environmentProject = id;
    if (this.environment.status !== 'ready') return;
    const version = await new Promise<string>(resolve => {
      let output = '';
      const child = this.spawn([this.environment.executable, '-I', '-S', '--version'], root);
      const timer = setTimeout(() => this.kill(child), 5000);
      child.stdout?.on('data', b => { output = (output + b.toString()).slice(-1024); });
      child.stderr?.on('data', b => { output = (output + b.toString()).slice(-1024); });
      child.once('error', () => { clearTimeout(timer); resolve(''); });
      child.once('close', code => { clearTimeout(timer); this.kill(child); resolve(code === 0 && /^Python \d+\.\d+\.\d+[^\r\n]*\s*$/.test(output) ? output.trim() : ''); });
    });
    if (version) this.environment.version = version;
    else { this.environment.status = 'unavailable'; this.environment.message = 'Selected interpreter could not start under process supervision. No fallback was selected.'; }
  }
  private snapshot(): Result<TerminalSnapshot> {
    return { ok: true, data: { environment: { ...this.environment }, sessions: [...this.sessions.values()].map(s => ({ ...s.data, output: s.data.output.map(o => ({ ...o })) })) } };
  }
  request(request: TerminalRequest): Promise<Result<TerminalSnapshot>> {
    if (!validTerminalRequest(request)) return Promise.resolve({ ok: false, code: 'invalid_request', message: 'Allowed commands: python --version, python <opened saved file.py>, pytest. No shell syntax or executable overrides.' });
    return this.serial(async () => {
      const project = this.projects.current;
      if (this.closed || !project || request.projectId !== project.id) return unavailable('Select the current project before using the terminal.');
      if (this.environmentProject !== project.id || request.operation === 'refresh') await this.inspect(project.id, project.rootPath);
      if (request.operation === 'snapshot' || request.operation === 'refresh') return this.snapshot();
      if (request.operation === 'create') {
        if (this.sessions.size >= 6) return unavailable('Close a terminal before opening another (maximum 6).');
        const data: TerminalSession = { id: randomUUID(), projectId: project.id, root: project.rootPath, startedAt: null,
          state: 'stopped', exitCode: null, command: '', output: [], truncated: false, problem: '', testResult: null };
        this.sessions.set(data.id, { data, cancel: false }); return this.snapshot();
      }
      const owned = this.sessions.get(request.sessionId!);
      if (!owned || owned.data.projectId !== project.id) return unavailable('This terminal session is no longer available.');
      if (request.operation === 'stop' || request.operation === 'close' || request.operation === 'restart') {
        await this.stop(owned);
        if (request.operation === 'close') this.sessions.delete(owned.data.id);
        if (request.operation === 'restart') Object.assign(owned.data, { state: 'stopped', output: [], truncated: false, problem: '', command: '', startedAt: null, exitCode: null, testResult: null });
        return this.snapshot();
      }
      if (request.operation === 'clear') { owned.data.output = []; owned.data.truncated = false; return this.snapshot(); }
      if (owned.child) return unavailable('Stop the running command before starting another.');
      if (this.dirty.value) return unavailable('Save or discard all unsaved changes before running a command.');
      if (this.projects.canChange && !this.projects.canChange()) return unavailable('Finish or cancel the active AI request before running a manual command.');
      let args: string[], executable = this.environment.executable, directory = project.rootPath, label = request.command!, test = false;
      if (request.operation === 'executeCapability') {
        const descriptor = await this.projects.call<ProjectCommand>(project.id, 'command_capability', { capabilityId: request.capabilityId });
        if (!descriptor.ok) return descriptor;
        if (!descriptor.data.supported) return unavailable(descriptor.data.reason);
        if (!await this.approveScript(descriptor.data)) return { ok: false, code: 'permission_required', message: 'Project script denied or cancelled. No command ran.' };
        const prepared = await this.projects.call<{ executable: string; arguments: string[]; directory: string; label: string; test: boolean }>(project.id, 'prepare_command', { capabilityId: request.capabilityId, revision: descriptor.data.revision, approved: true });
        if (!prepared.ok) return prepared;
        ({ executable, directory, label, test } = prepared.data); args = prepared.data.arguments;
      } else {
        await this.inspect(project.id, project.rootPath);
        if (this.environment.status !== 'ready') return unavailable(this.environment.message);
        executable = this.environment.executable;
        const parsed = parseCommand(request.command)!;
        test = parsed.kind === 'pytest';
        if (parsed.kind === 'run') {
          const validated = await this.projects.call<{ path: string }>(project.id, 'validate_run', { path: parsed.path, revision: request.revision });
          if (!validated.ok) return validated;
          args = ['-u', validated.data.path];
        } else args = parsed.kind === 'pytest' ? ['-m', 'pytest'] : ['--version'];
      }
      if (this.dirty.value || this.projects.current?.id !== project.id) return unavailable('Project or saved state changed; review it before running.');
      if (this.projects.canChange && !this.projects.canChange()) return unavailable('An AI request started while this command was being reviewed. Resolve it before running.');
      Object.assign(owned.data, { state: 'starting', startedAt: new Date().toISOString(), exitCode: null,
        command: label, output: [], truncated: false, problem: '', testResult: test ? 'running' : null });
      owned.cancel = false;
      const child = this.spawn([executable, ...args], directory);
      owned.child = child;
      const append = (stream: 'stdout' | 'stderr', text: string) => {
        const output = owned.data.output;
        if (output.at(-1)?.stream === stream) output[output.length - 1].text += text;
        else output.push({ stream, text });
        let size = output.reduce((sum, o) => sum + o.text.length, 0);
        while (size > 131072 || output.length > 512) {
          const extra = Math.max(size - 131072, output.length > 512 ? output[0].text.length : 0);
          const remove = Math.min(extra, output[0].text.length);
          output[0].text = output[0].text.slice(remove); size -= remove;
          if (!output[0].text) output.shift();
          owned.data.truncated = true;
        }
      };
      child.stdout?.setEncoding('utf8'); child.stderr?.setEncoding('utf8');
      child.stdout?.on('data', (text: string) => append('stdout', text));
      child.stderr?.on('data', (text: string) => append('stderr', text));
      child.once('spawn', () => { owned.data.state = 'running'; });
      owned.done = new Promise(resolve => {
        child.once('error', () => { owned.data.problem = 'Process could not start.'; });
        child.once('close', code => {
          this.kill(child);
          owned.child = undefined;
          owned.data.exitCode = code;
          owned.data.state = owned.cancel ? 'stopped' : code === 0 ? 'exited' : 'failed';
          if (test) owned.data.testResult = owned.cancel ? null : code === 0 ? 'passed' : 'failed';
          if (!owned.cancel && code !== 0) owned.data.problem ||= label + ' exited with code ' + String(code) + '. See terminal output for details.';
          resolve();
        });
      });
      return this.snapshot();
    });
  }
  private async stop(owned: Owned) {
    if (!owned.child) return;
    owned.cancel = true; this.kill(owned.child); await owned.done;
  }
  reset() {
    return this.serial(async () => {
      await Promise.all([...this.sessions.values()].map(s => this.stop(s)));
      this.sessions.clear(); this.environmentProject = '';
    });
  }
  async close() { this.closed = true; await this.reset(); }
}
