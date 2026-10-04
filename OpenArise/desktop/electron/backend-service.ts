import type { BackendRequest, ClientResult, ConnectionState } from '../src/types/backend';
/** Main-process owner delegates transport to the workspace adapter.
 * Disconnect sends BackendService shutdown after synchronous work and awaits acknowledgement.
 * Forced termination cannot promise rollback.
 */
export interface BackendProcessAdapter {
  connect(): Promise<ConnectionState>;
  request(request: BackendRequest): Promise<ClientResult>;
  disconnect(): Promise<ConnectionState>;
}
export class DisconnectedProcessAdapter implements BackendProcessAdapter {
  async connect(): Promise<ConnectionState> { return { status: 'disconnected', reason: 'transport_not_implemented' }; }
  async request(request: BackendRequest): Promise<ClientResult> {
    return { kind: 'unavailable', request_id: request.request_id, code: 'not_connected', message: 'No workspace backend adapter is configured.' };
  }
  async disconnect(): Promise<ConnectionState> { return { status: 'disconnected', reason: 'closed' }; }
}
export class DesktopBackendService {
  private closed = false;
  private active = 0;
  private pending = '';
  get blocked() { return this.active > 0 || !!this.pending; }
  private closing?: Promise<ConnectionState>;
  private state: ConnectionState = { status: 'disconnected', reason: 'transport_not_implemented' };
  constructor(private readonly adapter: BackendProcessAdapter = new DisconnectedProcessAdapter(), private readonly source: 'backend' | 'test_fixture' = 'backend') {}
  getStatus(): ConnectionState { return { ...this.state }; }
  async connect(): Promise<ConnectionState> {
    if (this.closed) return this.getStatus();
    const state = await this.adapter.connect();
    if (!this.closed) this.state = state;
    return this.getStatus();
  }
  async request(request: BackendRequest): Promise<ClientResult> {
    if (this.closed) return { kind: 'unavailable', request_id: request.request_id, code: 'service_closed', message: 'Desktop backend owner is closed.' };
    this.active++;
    try {
      const result = await this.adapter.request(request);
      if (result.kind === 'backend' && result.response.success && result.response.data && typeof result.response.data === 'object' && !Array.isArray(result.response.data) && 'pending_action' in result.response.data) {
        const data = result.response.data;
        if (data.pending_action) this.pending = String(data.request_id);
        else if (this.pending === data.request_id) this.pending = '';
      }
      return result.kind === 'backend' ? { ...result, source: this.source } : result;
    }
    catch { return { kind: 'unavailable', request_id: request.request_id, code: 'transport_error', message: 'Backend transport failed.' }; }
    finally { this.active--; }
  }
  disconnect(): Promise<ConnectionState> {
    this.closed = true;
    this.state = { status: 'disconnected', reason: 'closed' };
    return this.closing ??= this.adapter.disconnect().then(() => this.getStatus());
  }
}
