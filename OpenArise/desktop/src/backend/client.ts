import type { BackendRequest, ClientResult, ConnectionState, DesktopBridge, JsonObject, ReadMethod, RequirementBaseline } from '../types/backend';
/** Browser-safe client. No Node or Electron imports. */
export class BackendClient {
  constructor(private readonly bridge?: DesktopBridge, private readonly projectId?: string) {}
  connect(): Promise<ConnectionState> { return this.bridge?.connect() ?? Promise.resolve({ status: 'disconnected', reason: 'bridge_unavailable' }); }
  disconnect(): Promise<ConnectionState> { return this.bridge?.disconnect() ?? Promise.resolve({ status: 'disconnected', reason: 'bridge_unavailable' }); }
  getStatus(): Promise<ConnectionState> { return this.bridge?.getStatus() ?? Promise.resolve({ status: 'disconnected', reason: 'bridge_unavailable' }); }
  private async send(request: BackendRequest): Promise<ClientResult> {
    if (!this.bridge) return { kind: 'unavailable', request_id: request.request_id, code: 'bridge_unavailable', message: 'Open the desktop app to use its bridge.' };
    try { return await this.bridge.request(request, this.projectId); }
    catch { return { kind: 'unavailable', request_id: request.request_id, code: 'transport_error', message: 'Desktop bridge could not handle the request.' }; }
  }
  private read(method: ReadMethod) { return this.send({ request_id: crypto.randomUUID(), method, params: {} }); }
  refreshWorkspace() { return this.send({ request_id: crypto.randomUUID(), method: 'refresh_workspace', params: {} }); }
  captureBaseline(requirementId: string) { return this.send({ request_id: crypto.randomUUID(), method: 'create_requirement_baseline', params: { requirement_id: requirementId } }); }
  getProjectInfo() { return this.read('get_project_information'); }
  getProjectState() { return this.read('get_project_state'); }
  getBlueprint() { return this.read('get_blueprint'); }
  getRequirements() { return this.read('get_requirements'); }
  getTraceability() { return this.read('get_traceability_graph'); }
  getEnvironment() { return this.read('get_environment_status'); }
  getHealth() { return this.read('get_health_report'); }
  getIntelligence() { return this.read('get_intelligence_snapshot'); }
  getTimeline() { return this.read('get_timeline'); }
  getDrift(baseline: RequirementBaseline) { return this.send({ request_id: crypto.randomUUID(), method: 'get_drift_report', params: { baseline_dict: baseline } }); }
  agentCommand(method: 'approve_agent_action' | 'resume_agent_execution' | 'deny_agent_action', requestId: string, toolId: string, commandId = crypto.randomUUID()) {
    return this.send({ request_id: commandId, method, params: { request_id: requestId, tool_call_id: toolId } });
  }
  cancelAgentRequest(requestId: string, commandId = crypto.randomUUID()) {
    return this.send({ request_id: commandId, method: 'cancel_agent_execution', params: { request_id: requestId } });
  }
  getAgentRequest(requestId: string) {
    return this.send({ request_id: crypto.randomUUID(), method: 'get_agent_execution', params: { request_id: requestId } });
  }
  submitAIRequest(request: import('../types/ai').AIRequest) {
    if (request.projectRef && request.projectRef.id !== this.projectId) return Promise.resolve({ kind: 'unavailable', request_id: request.requestId, code: 'invalid_message', message: 'AI request belongs to another project.' } as ClientResult);
    return this.submitAgentRequest(request.prompt, request.context, request.requestId);
  }
  submitAgentRequest(prompt: string, context?: JsonObject, requestId: string = crypto.randomUUID()) {
    return this.send({ request_id: requestId, method: 'request_agent_execution', params: { prompt, ...(context ? { context_data: context } : {}) } });
  }
}
