import type { TerminalBridge } from './terminal';
import type { ProjectBridge } from './project';
/** Public JSON boundary from docs/BACKEND_PROCESS_CONTRACT.md. */
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export type RequestId = string;
export type ActionState = 'running' | 'permission_required' | 'approved' | 'completed' | 'failed' | 'denied' | 'cancelled';
export type BackendErrorCode = 'project_not_found' | 'invalid_project_root' | 'project_state_unavailable' | 'environment_unavailable' | 'unsupported_operation' | 'permission_required' | 'verification_unavailable' | 'internal_error' | 'invalid_request' | 'request_not_found' | 'action_conflict' | 'service_closed';
export interface BackendError { success: false; code: BackendErrorCode; message: string; details: JsonObject }
export interface BackendEvent { request_id: RequestId; sequence: number; event_type: string; current_state: string; tool_call_id: string | null; timestamp: string }
interface ResponseFields { request_id: RequestId; events: BackendEvent[] }
export type BackendResponse<T = JsonValue> =
  | (ResponseFields & { success: true; action_state: ActionState; data: T; error: null })
  | (ResponseFields & { success: false; action_state: null; data: null; error: BackendError });
// Outer success means dispatch succeeded, not task verification.
export interface AgentResponse {
  request_id: RequestId | null;
  status: 'permission_required' | 'approved' | 'success' | 'unverified' | 'failure' | 'denied' | 'cancelled';
  current_state: string; action_state: ActionState; message: string;
  pending_action: JsonObject | null; data: JsonObject | null;
}
export interface RequirementBaseline extends JsonObject { requirement_id: string }
export const readMethods = [
  'get_project_information', 'get_project_state', 'get_blueprint', 'get_requirements',
  'get_traceability_graph', 'get_environment_status', 'get_health_report',
  'get_intelligence_snapshot', 'get_timeline',
] as const;
export type ReadMethod = typeof readMethods[number];
export type BackendRequest = { request_id: RequestId } & (
  | { method: ReadMethod; params: Record<string, never> }
  | { method: 'refresh_workspace'; params: Record<string, never> }
  | { method: 'create_requirement_baseline'; params: { requirement_id: string } }
  | { method: 'get_drift_report'; params: { baseline_dict: RequirementBaseline } }
  | { method: 'approve_agent_action' | 'resume_agent_execution' | 'deny_agent_action'; params: { request_id: string; tool_call_id: string } }
  | { method: 'cancel_agent_execution' | 'get_agent_execution'; params: { request_id: string } }
  | { method: 'request_agent_execution'; params: { prompt: string; context_data?: JsonObject } }
);
// Desktop errors are separate from Python error codes and envelopes.
export type ClientErrorCode = 'not_connected' | 'invalid_message' | 'service_closed' | 'bridge_unavailable' | 'transport_error' | 'backend_startup_failed' | 'backend_timeout';
export type ClientResult<T = JsonValue> =
  | { kind: 'backend'; response: BackendResponse<T>; source?: 'backend' | 'test_fixture' }
  | { kind: 'unavailable'; request_id: RequestId; code: ClientErrorCode; message: string };
export interface ConnectionState { status: 'disconnected' | 'connected'; reason: 'transport_not_implemented' | 'closed' | 'bridge_unavailable' | 'ready' | 'no_project' | 'transport_error' }
export interface DesktopBridge {
  project: ProjectBridge;
  terminal: TerminalBridge;
  connect(): Promise<ConnectionState>;
  disconnect(): Promise<ConnectionState>;
  getStatus(): Promise<ConnectionState>;
  request(request: BackendRequest, projectId?: string): Promise<ClientResult>;
}

/** Host-only shutdown command; never part of the renderer's allowlist. */
export interface ShutdownRequest { request_id: RequestId; method: 'shutdown'; params: Record<string, never> }
export type ShutdownResponse = BackendResponse<{ closed: true }>;
