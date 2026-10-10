import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { backendPython, backendRoot, desktopPython } from './runtime-paths';
import type { Entry, FileBuffer, Project, ProjectObservation, Result, RenameInspection } from '../src/types/project';
import { validCapabilities, validProjectCommand } from '../shared/capabilities';

const error = (message: string): Result<never> => ({ ok: false, code: 'unavailable', message });
const isObject = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
function validData(method: string, value: unknown): boolean {
  if (method === 'list' || method === 'search') return Array.isArray(value) && value.length <= (method === 'search' ? 200 : 2000) && value.every(v =>
    isObject(v) && typeof v.name === 'string' && typeof v.path === 'string' && ['file', 'folder'].includes(String(v.kind)));
  if (!isObject(value)) return false;
  if (method === 'environment') return typeof value.executable === 'string' && typeof value.label === 'string' && typeof value.message === 'string' && ['ready', 'unavailable'].includes(String(value.status));
  if (method === 'validate_run') return typeof value.path === 'string';
  if (method === 'info') return typeof value.name === 'string' && typeof value.rootPath === 'string';
  if (['create_folder', 'rename', 'inspect_rename'].includes(method)) return typeof value.path === 'string' && ['folder', 'file'].includes(String(value.kind))
    && (method !== 'inspect_rename' || typeof value.revision === 'string' && /^[a-f0-9]{64}$/.test(value.revision));
  if (method === 'read' || method === 'save' || method === 'create') return typeof value.path === 'string' && typeof value.content === 'string'
    && typeof value.readOnly === 'boolean' && typeof value.revision === 'string' && /^[a-f0-9]{64}$/.test(value.revision);
  if (method === 'observe') return Number.isSafeInteger(value.files) && Number.isSafeInteger(value.modules) && typeof value.observedAt === 'string' && validCapabilities(value.capabilities);
  if (method === 'command_capability') return validProjectCommand(value);
  if (method === 'prepare_command') return typeof value.executable === 'string' && path.isAbsolute(value.executable)
    && Array.isArray(value.arguments) && value.arguments.length === 4 && value.arguments.every(v => typeof v === 'string')
    && value.arguments[1] === 'run' && ['test', 'build'].includes(value.arguments[2]) && value.arguments[3] === '--ignore-scripts'
    && typeof value.directory === 'string' && path.isAbsolute(value.directory) && typeof value.label === 'string' && typeof value.test === 'boolean';
  return method === 'shutdown' && value.closed === true;
}
export class FileProcess {
  private child: ChildProcessWithoutNullStreams;
  private pending = new Map<string, { method: string; resolve: (r: Result<unknown>) => void; timer: ReturnType<typeof setTimeout> }>();
  private stopped = false;
  private buffer = '';
  constructor(root: string) {
    this.child = spawn(backendPython(), ['-I', '-B', '-u', desktopPython('file_host.py'), root], {
      cwd: backendRoot(), windowsHide: true, shell: false, stdio: 'pipe',
    });
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', (chunk: string) => this.receive(chunk));
    // Never forward backend diagnostics, environment values or tracebacks to React.
    this.child.stderr.on('data', () => {});
    this.child.on('error', () => this.fail('Python file host is unavailable. Check the existing backend virtual environment.'));
    this.child.on('exit', () => this.fail('The project file host stopped. Reopen the project to reconnect.'));
    this.child.stdin.on('error', () => this.fail('The project file connection closed.'));
  }
  private fail(message: string) {
    this.stopped = true;
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.resolve(error(message)); }
    this.pending.clear();
    if (this.child.exitCode === null) this.child.kill();
  }
  private receive(chunk: string) {
    this.buffer += chunk;
    if (this.buffer.length > 16 * 1024 * 1024) { this.fail('Invalid file host response.'); return; }
    let end: number;
    while ((end = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, end); this.buffer = this.buffer.slice(end + 1);
      try {
        const response: unknown = JSON.parse(line);
        if (!isObject(response) || typeof response.id !== 'string') throw new Error();
        const pending = this.pending.get(response.id);
        if (!pending) throw new Error();
        if (response.ok === true ? !validData(pending.method, response.data) :
          response.ok !== false || typeof response.code !== 'string' || typeof response.message !== 'string') throw new Error();
        clearTimeout(pending.timer);
        this.pending.delete(response.id);
        pending.resolve(response as unknown as Result<unknown>);
      } catch { this.fail('Invalid file host response.'); return; }
    }
  }
  request<T>(method: string, params: object = {}): Promise<Result<T>> {
    if (this.stopped) return Promise.resolve(error('The project file host is closed.'));
    const id = randomUUID();
    return new Promise(resolve => {
      const timer = setTimeout(() => this.fail('File operation timed out. Check the file on disk before retrying a save.'), 60_000);
      this.pending.set(id, { method, timer, resolve: resolve as (r: Result<unknown>) => void });
      this.child.stdin.write(JSON.stringify({ id, method, params }) + '\n');
    });
  }
  async close() {
    if (!this.stopped) {
      // This host serializes commands; shutdown follows any synchronous save.
      const timer = setTimeout(() => this.fail('File host shutdown timed out.'), 5000);
      await this.request('shutdown');
      clearTimeout(timer);
      this.child.stdin.end();
    }
  }
}
export class ProjectService {
  private recent: Project[] = [];
  private session?: { project: Project; host: FileProcess };
  private busy = false;
  beforeChange?: () => Promise<void>;
  canChange?: () => boolean;
  get current() { return this.busy ? undefined : this.session?.project; }
  async open(root: string): Promise<Result<Project>> {
    if (this.busy) return error('A project is already opening.');
    if (this.canChange && !this.canChange()) return error('Finish or cancel the active AI request before switching projects.');
    this.busy = true;
    const host = new FileProcess(root);
    try {
      const result = await host.request<{ name: string; rootPath: string }>('info');
      if (!result.ok) { await host.close(); return result; }
      await this.beforeChange?.();
      const previous = this.session;
      const project = { ...result.data, id: randomUUID() };
      this.session = { project, host };
      this.recent = [project, ...this.recent.filter(p => p.rootPath !== project.rootPath)].slice(0, 6);
      if (previous) await previous.host.close();
      return { ok: true, data: project };
    } finally { this.busy = false; }
  }
  call<T>(id: string, method: string, params: object = {}): Promise<Result<T>> {
    if (!this.session) return Promise.resolve({ ok: false, code: 'no_project', message: 'No project open' });
    if (id !== this.session.project.id) return Promise.resolve({ ok: false, code: 'stale_project', message: 'This file belongs to a different project.' });
    return this.session.host.request<T>(method, params);
  }
  list(id: string, filePath: string) { return this.call<Entry[]>(id, 'list', { path: filePath }); }
  read(id: string, filePath: string) { return this.call<FileBuffer>(id, 'read', { path: filePath }); }
  save(id: string, filePath: string, content: string, revision: string) { return this.call<FileBuffer>(id, 'save', { path: filePath, content, revision }); }
  create(id: string, filePath: string) { return this.call<FileBuffer>(id, 'create', { path: filePath }); }
  createFolder(id: string, filePath: string) { return this.call<{ path: string; kind: 'folder' }>(id, 'create_folder', { path: filePath }); }
  inspectRename(id: string, filePath: string) { return this.call<RenameInspection>(id, 'inspect_rename', { path: filePath }); }
  rename(id: string, filePath: string, destination: string, revision: string) { return this.call<{ path: string; kind: 'folder' | 'file' }>(id, 'rename', { path: filePath, destination, revision }); }
  recentProjects(): Result<Project[]> { return { ok: true, data: this.recent.map(p => ({ ...p })) }; }
  openRecent(id: string): Promise<Result<Project>> {
    const project = this.recent.find(p => p.id === id);
    return project ? this.open(project.rootPath) : Promise.resolve(error('This recent project is no longer in the current session. Use Open Project.'));
  }
  search(id: string, query: string) { return this.call<Entry[]>(id, 'search', { query }); }
  observe(id: string) { return this.call<ProjectObservation>(id, 'observe'); }
  async close() { const current = this.session; this.session = undefined; await current?.host.close(); }
}
