import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import type { BackendRequest, ClientResult, ConnectionState, ShutdownRequest } from '../src/types/backend';
import type { BackendProcessAdapter } from './backend-service';
import type { ProjectService } from './project-service';
import { validAgentEnvelope } from '../shared/agent-response';
import { backendPython, backendRoot, desktopPython } from './runtime-paths';
const supported = new Set(['get_project_information', 'get_project_state', 'get_requirements', 'get_blueprint', 'get_traceability_graph', 'get_health_report', 'get_timeline', 'get_drift_report', 'refresh_workspace', 'create_requirement_baseline', 'get_intelligence_snapshot', 'get_environment_status', 'request_agent_execution',
  'get_agent_execution', 'approve_agent_action', 'resume_agent_execution', 'deny_agent_action', 'cancel_agent_execution']);
const unavailable = (id: string, message: string): ClientResult => ({ kind: 'unavailable', request_id: id, code: 'transport_error', message });
export class AgentProcess {
  private child: ChildProcessWithoutNullStreams;
  private stopped = false;
  private buffer = '';
  private pending?: { request: BackendRequest | ShutdownRequest; resolve: (r: ClientResult) => void };
  private readyResolve!: (v: boolean) => void;
  get alive() { return !this.stopped; }
  readonly ready = new Promise<boolean>(r => { this.readyResolve = r; });
  private done: Promise<void>;
  constructor(root: string) {
    this.child = spawn(backendPython(), ['-I', '-B', '-u', desktopPython('agent_host.py'), root], {
      cwd: backendRoot(), shell: false, windowsHide: true, stdio: 'pipe', detached: process.platform !== 'win32',
    });
    const timer = setTimeout(() => this.fail(), 15000);
    void this.ready.then(() => clearTimeout(timer));
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', (chunk: string) => this.receive(chunk));
    this.child.stderr.on('data', () => {}); // Never forward Python logs or tracebacks.
    this.child.stdin.on('error', () => this.fail());
    this.child.on('error', () => this.fail());
    this.done = new Promise(resolve => this.child.once('close', () => { this.fail(); resolve(); }));
  }
  private fail() {
    this.stopped = true; this.readyResolve(false);
    this.pending?.resolve(unavailable(this.pending.request.request_id, 'Agent connection was lost. Side effects may have occurred; inspect the project before retrying.'));
    this.pending = undefined;
    try {
      if (process.platform !== 'win32' && this.child.pid) process.kill(-this.child.pid, 'SIGKILL');
      else this.child.kill();
    } catch { /* Already stopped. */ }
  }
  private receive(chunk: string) {
    this.buffer += chunk;
    if (this.buffer.length > 524288) { this.fail(); return; }
    let end: number;
    while ((end = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, end); this.buffer = this.buffer.slice(end + 1);
      try {
        const value = JSON.parse(line);
        if (value.ready === true && Object.keys(value).length === 1 && !this.pending) { this.readyResolve(true); continue; }
        const pending = this.pending;
        if (!pending || !validAgentEnvelope(value, pending.request.request_id, pending.request.method)) throw new Error();
        this.pending = undefined;
        pending.resolve({ kind: 'backend', response: value });
      } catch { this.fail(); return; }
    }
  }
  async request(request: BackendRequest | ShutdownRequest): Promise<ClientResult> {
    if (this.stopped || this.pending || !await this.ready) return unavailable(request.request_id, 'Agent host is unavailable or busy.');
    return new Promise(resolve => {
      this.pending = { request, resolve };
      this.child.stdin.write(JSON.stringify(request) + '\n');
    });
  }
  async close() {
    if (!this.stopped) {
      await this.request({ request_id: randomUUID(), method: 'shutdown', params: {} });
      this.child.stdin.end();
    }
    await this.done;
  }
}
export class WorkspaceBackendAdapter implements BackendProcessAdapter {
  private host?: AgentProcess;
  private projectId = '';
  private connecting?: Promise<ConnectionState>;
  private active?: Promise<ClientResult>;
  private waitingApproval = '';
  private closed = false;
  constructor(private projects: ProjectService) {}
  get blocked() { return !!this.active || !!this.connecting || (!!this.waitingApproval && !!this.host?.alive); }
  async connect(): Promise<ConnectionState> {
    if (this.closed) return { status: 'disconnected', reason: 'closed' };
    const project = this.projects.current;
    if (!project) return { status: 'disconnected', reason: 'no_project' };
    if (this.connecting) return this.connecting;
    if (this.host && this.projectId === project.id) return { status: await this.host.ready && this.host.alive ? 'connected' : 'disconnected', reason: await this.host.ready && this.host.alive ? 'ready' : 'transport_error' };
    this.connecting = (async () => {
      await this.host?.close();
      this.host = new AgentProcess(project.rootPath); this.projectId = project.id;
      const ready = await this.host.ready;
      return { status: ready ? 'connected' : 'disconnected', reason: ready ? 'ready' : 'transport_error' } as ConnectionState;
    })();
    try { return await this.connecting; } finally { this.connecting = undefined; }
  }
  async request(request: BackendRequest): Promise<ClientResult> {
    if (!supported.has(request.method)) return unavailable(request.request_id, 'This backend method is not exposed by the desktop presentation adapter.');
    if (this.active) return unavailable(request.request_id, 'The synchronous backend is busy. Wait for the recorded result.');
    // Reserve before connect to reject duplicate submissions during initialization.
    const work = async () => {
      if ((await this.connect()).status !== 'connected' || !this.host) return unavailable(request.request_id, 'Agent host unavailable. Your prompt is retained.');
      const result = await this.host.request(request);
      if (result.kind === 'backend' && result.response.success && result.response.data && typeof result.response.data === 'object' && !Array.isArray(result.response.data)) {
        const data = result.response.data;
        if ('pending_action' in data) {
          if (data.pending_action) this.waitingApproval = String(data.request_id);
          else if (this.waitingApproval === data.request_id) this.waitingApproval = '';
        }
      }
      return result;
    };
    this.active = work();
    try { return await this.active; } finally { this.active = undefined; }
  }
  async reset() {
    await this.connecting; await this.active;
    await this.host?.close(); this.host = undefined; this.projectId = ''; this.waitingApproval = '';
  }
  async disconnect(): Promise<ConnectionState> { this.closed = true; await this.reset(); return { status: 'disconnected', reason: 'closed' }; }
}
