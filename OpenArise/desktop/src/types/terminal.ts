import type { Result } from './project';
export type ProcessState = 'starting' | 'running' | 'stopped' | 'exited' | 'failed';
export interface PythonEnvironment { executable: string; version: string; status: 'ready' | 'unavailable'; label: string; message: string }
export interface TerminalSession {
  id: string; projectId: string; root: string; startedAt: string | null;
  state: ProcessState; exitCode: number | null; command: string;
  output: { stream: 'stdout' | 'stderr'; text: string }[];
  truncated: boolean; problem: string; testResult: 'running' | 'passed' | 'failed' | null;
}
export interface TerminalRequest {
  projectId: string; operation: 'snapshot' | 'refresh' | 'create' | 'execute' | 'executeCapability' | 'stop' | 'clear' | 'close' | 'restart';
  sessionId?: string; command?: string; revision?: string; capabilityId?: string;
}
export interface TerminalSnapshot { environment: PythonEnvironment; sessions: TerminalSession[] }
export interface TerminalBridge { request(request: TerminalRequest): Promise<Result<TerminalSnapshot>> }
